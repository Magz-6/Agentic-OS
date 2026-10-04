"""Unit tests for Request Lifecycle Coordinator.

Verifies:
- Valid request acceptance and end-to-end lifecycle completion
- RequestContext and TraceContext preservation (request_id, trace_id)
- Child span propagation down to the Goal Runtime boundary
- Rejection of malformed requests and missing identity
- Rejection of incomplete or invalid intent payloads
- Ambiguity detection and structured clarification prompt generation
- Goal Runtime boundary invocation
- Safe conversion of Goal Runtime errors into structured failures
- Lifecycle state transitions and invalid transition prevention
"""

import unittest
from typing import Dict, Any, List
from src.core.context import TraceContext, RequestContext
from src.core.status import RequestStatus
from src.core.errors import AgenticOSError, PolicyViolationError
from src.core.request_lifecycle import RequestLifecycle, RequestLifecycleResult
from src.goal_runtime.interface import GoalRuntimeInterface


class MockGoalRuntime(GoalRuntimeInterface):
    """Test double for GoalRuntimeInterface used in lifecycle testing."""

    def __init__(self, should_fail: bool = False, failure_error: Exception = None):
        self.should_fail = should_fail
        self.failure_error = failure_error
        self.calls: List[Dict[str, Any]] = []

    def create_goal(self, intent_payload: Dict[str, Any], trace_context: TraceContext) -> Dict[str, Any]:
        self.calls.append({
            "intent_payload": intent_payload,
            "trace_context": trace_context
        })
        if self.should_fail:
            if self.failure_error:
                raise self.failure_error
            raise AgenticOSError(
                message="Goal policy check failed: target directory restricted",
                error_code="SECURITY_POLICY_VIOLATION",
                trace_context=trace_context
            )
        return {
            "goal_id": "goal-lifecycle-001",
            "intent_id": intent_payload.get("intent_id"),
            "state": "ACTIVE",
            "priority": 5,
            "constraints": {"timeout_seconds": 60},
            "parameters": intent_payload.get("parameters", {}),
            "trace_context": trace_context.to_dict()
        }

    def get_goal(self, goal_id: str, trace_context: TraceContext) -> Dict[str, Any]:
        return {"goal_id": goal_id, "state": "ACTIVE"}

    def update_goal(self, goal_id: str, updates: Dict[str, Any], trace_context: TraceContext) -> Dict[str, Any]:
        return {"goal_id": goal_id, **updates}

    def cancel_goal(self, goal_id: str, reason: str, trace_context: TraceContext) -> Dict[str, Any]:
        return {"goal_id": goal_id, "state": "CANCELLED"}

    def replan_goal(self, goal_id: str, trigger_reason: str, trace_context: TraceContext) -> Dict[str, Any]:
        return {"goal_id": goal_id, "state": "REPLANNING"}


class TestRequestLifecycle(unittest.TestCase):
    """Test suite for RequestLifecycle coordinator."""

    def setUp(self):
        self.mock_goal_runtime = MockGoalRuntime()
        self.lifecycle = RequestLifecycle(
            goal_runtime=self.mock_goal_runtime,
            confidence_threshold=0.70
        )
        self.valid_request = {
            "user_id": "usr-vivek",
            "intent_id": "int-901",
            "action_name": "backup_directory",
            "parameters": {"source": "/home/user/docs", "target": "/backup"},
            "confidence_score": 0.95
        }

    def test_valid_request_accepted_and_lifecycle_completed(self):
        """Verify standard request is accepted, validated, processed, and completed."""
        result = self.lifecycle.execute(self.valid_request)
        self.assertTrue(result.success)
        self.assertEqual(result.status, RequestStatus.COMPLETED)
        self.assertIsNotNone(result.goal_record)
        self.assertEqual(result.goal_record["goal_id"], "goal-lifecycle-001")
        self.assertFalse(result.clarification_required)
        self.assertIsNone(result.error)

    def test_request_context_and_ids_preserved(self):
        """Verify request_id and trace_id from RequestContext are preserved."""
        req_ctx = RequestContext.create(
            user_id="usr-vivek",
            request_id="custom-req-uuid-42"
        )
        result = self.lifecycle.execute(self.valid_request, request_context=req_ctx)
        self.assertTrue(result.success)
        self.assertEqual(result.request_id, "custom-req-uuid-42")
        self.assertEqual(result.trace_id, req_ctx.trace.trace_id)

    def test_child_span_propagation(self):
        """Verify child spans are generated and linked across the boundary."""
        result = self.lifecycle.execute(self.valid_request)
        self.assertTrue(result.success)
        self.assertEqual(len(self.mock_goal_runtime.calls), 1)

        goal_call = self.mock_goal_runtime.calls[0]
        goal_trace: TraceContext = goal_call["trace_context"]

        # Tracing assertions
        self.assertEqual(goal_trace.request_id, result.request_id)
        self.assertEqual(goal_trace.trace_id, result.trace_id)
        self.assertIsNotNone(goal_trace.parent_span_id)
        self.assertNotEqual(goal_trace.span_id, goal_trace.parent_span_id)

    def test_malformed_request_rejected(self):
        """Verify non-dictionary request payload fails gracefully."""
        result = self.lifecycle.execute("invalid non-dict string")
        self.assertFalse(result.success)
        self.assertEqual(result.status, RequestStatus.REJECTED)
        self.assertEqual(result.error["error_code"], "MALFORMED_REQUEST")

    def test_missing_user_identity_rejected(self):
        """Verify request lacking user identity fails validation."""
        req_without_user = dict(self.valid_request)
        del req_without_user["user_id"]
        result = self.lifecycle.execute(req_without_user)
        self.assertFalse(result.success)
        self.assertEqual(result.status, RequestStatus.REJECTED)
        self.assertEqual(result.error["error_code"], "MISSING_USER_CONTEXT")

    def test_malformed_intent_missing_fields_rejected(self):
        """Verify intent missing action_name or parameters is rejected."""
        req_missing_action = dict(self.valid_request)
        del req_missing_action["action_name"]
        result = self.lifecycle.execute(req_missing_action)
        self.assertFalse(result.success)
        self.assertEqual(result.status, RequestStatus.REJECTED)
        self.assertEqual(result.error["error_code"], "VALIDATION_ERROR")

    def test_invalid_confidence_score_rejected(self):
        """Verify out-of-bounds or non-numeric confidence score is rejected."""
        req_bad_conf = dict(self.valid_request, confidence_score=1.42)
        result = self.lifecycle.execute(req_bad_conf)
        self.assertFalse(result.success)
        self.assertEqual(result.status, RequestStatus.REJECTED)
        self.assertEqual(result.error["error_code"], "INVALID_CONFIDENCE_SCORE")

    def test_ambiguous_intent_requires_clarification(self):
        """Verify low-confidence intent (< 0.70) triggers clarification prompt."""
        req_ambiguous = dict(self.valid_request, confidence_score=0.45)
        result = self.lifecycle.execute(req_ambiguous)
        self.assertFalse(result.success)
        self.assertEqual(result.status, RequestStatus.REJECTED)
        self.assertTrue(result.clarification_required)
        self.assertIn("ambiguous", result.clarification_prompt.lower())
        self.assertEqual(result.error["error_code"], "AMBIGUOUS_INTENT")
        # Ensure GoalRuntime was not invoked for ambiguous intent
        self.assertEqual(len(self.mock_goal_runtime.calls), 0)

    def test_goal_runtime_handoff_invoked(self):
        """Verify GoalRuntimeInterface.create_goal receives expected payload."""
        result = self.lifecycle.execute(self.valid_request)
        self.assertTrue(result.success)
        self.assertEqual(len(self.mock_goal_runtime.calls), 1)

        payload = self.mock_goal_runtime.calls[0]["intent_payload"]
        self.assertEqual(payload["action_name"], "backup_directory")
        self.assertEqual(payload["user_id"], "usr-vivek")
        self.assertIn("trace_context", payload)

    def test_goal_runtime_failure_converted_to_structured_failure(self):
        """Verify GoalRuntime exception is safely caught and converted to FAILED state."""
        failing_runtime = MockGoalRuntime(should_fail=True)
        lifecycle = RequestLifecycle(goal_runtime=failing_runtime)

        result = lifecycle.execute(self.valid_request)
        self.assertFalse(result.success)
        self.assertEqual(result.status, RequestStatus.FAILED)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error["error_code"], "SECURITY_POLICY_VIOLATION")

    def test_goal_runtime_unhandled_exception_handled_safely(self):
        """Verify unexpected runtime errors are caught without crashing."""
        broken_runtime = MockGoalRuntime(
            should_fail=True,
            failure_error=RuntimeError("Database connection lost")
        )
        lifecycle = RequestLifecycle(goal_runtime=broken_runtime)

        result = lifecycle.execute(self.valid_request)
        self.assertFalse(result.success)
        self.assertEqual(result.status, RequestStatus.FAILED)
        self.assertEqual(result.error["error_code"], "GOAL_RUNTIME_INVOCATION_ERROR")
        self.assertIn("Database connection lost", result.error["message"])

    def test_invalid_state_transition_fails_safely(self):
        """Verify illegal state transitions raise structured AgenticOSError."""
        lifecycle = RequestLifecycle()
        # Direct transition from RECEIVED to COMPLETED is illegal
        with self.assertRaises(AgenticOSError) as ctx:
            lifecycle.transition_to(RequestStatus.COMPLETED)
        self.assertEqual(ctx.exception.error_code, "INVALID_STATE_TRANSITION")

    def test_state_history_tracking(self):
        """Verify state transitions are recorded in history."""
        result = self.lifecycle.execute(self.valid_request)
        self.assertTrue(result.success)

        # Expected flow: RECEIVED -> VALIDATING -> VALIDATED -> PROCESSING -> COMPLETED
        history_states = [h.to_state for h in result.history]
        self.assertEqual(history_states, [
            RequestStatus.VALIDATING,
            RequestStatus.VALIDATED,
            RequestStatus.PROCESSING,
            RequestStatus.COMPLETED
        ])

    def test_serialization_to_dict(self):
        """Verify RequestLifecycleResult serializes cleanly to dict."""
        result = self.lifecycle.execute(self.valid_request)
        d = result.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["status"], "COMPLETED")
        self.assertTrue(d["success"])
        self.assertIsInstance(d["trace_context"], dict)
        self.assertIsInstance(d["history"], list)


if __name__ == "__main__":
    unittest.main()
