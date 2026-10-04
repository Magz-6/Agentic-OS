"""Unit and Integration Tests for Goal Runtime (Layer 3).

Covers formal project tests:
- G01: Create Goal
- G02: Update Goal
- G03: Cancel Goal
- G04: Replan Goal

Plus supporting tests:
- Unique Goal IDs
- Trace and Request ID preservation
- Priority validation and boundary checking
- Constraint validation (timeouts, retries)
- Terminal-state update prevention
- Invalid lifecycle state transitions
- Goal decomposition and refinement hierarchy
- End-to-end integration with RequestLifecycle
"""

import unittest
from src.core.context import TraceContext, RequestContext
from src.core.status import GoalStatus, RequestStatus
from src.core.errors import NotFoundError, ValidationError, AgenticOSError
from src.core.validation import DraftSchemaValidator
from src.core.request_lifecycle import RequestLifecycle
from src.goal_runtime.runtime import GoalRuntime
from src.goal_runtime.models import Goal


class TestGoalRuntime(unittest.TestCase):
    """Test suite for GoalRuntime concrete implementation."""

    def setUp(self):
        self.runtime = GoalRuntime(default_priority=5, default_timeout_seconds=120)
        self.trace = TraceContext.new_root()
        self.valid_intent = {
            "intent_id": "int-test-001",
            "user_id": "usr-vivek",
            "action_name": "backup_directory",
            "parameters": {"source": "/home/user/docs", "target": "/backup"},
            "confidence_score": 0.95,
            "priority": 5,
            "constraints": {"timeout_seconds": 120, "max_retries": 2}
        }

    # -------------------------------------------------------------------------
    # Formal Test Matrix Tests (G01 - G04)
    # -------------------------------------------------------------------------

    def test_g01_create_goal(self):
        """G01: Verify Goal Runtime accepts a valid intent and creates an active Goal."""
        goal_record = self.runtime.create_goal(self.valid_intent, self.trace)

        # Objective & Preconditions verification
        self.assertIsNotNone(goal_record["goal_id"])
        self.assertTrue(goal_record["goal_id"].startswith("goal-"))
        self.assertEqual(goal_record["intent_id"], "int-test-001")
        self.assertEqual(goal_record["action_name"], "backup_directory")
        self.assertEqual(goal_record["state"], GoalStatus.ACTIVE.value)
        self.assertEqual(goal_record["priority"], 5)
        self.assertEqual(goal_record["constraints"]["timeout_seconds"], 120)
        self.assertEqual(goal_record["parameters"]["target"], "/backup")

        # Identity and tracing preservation
        goal_trace = goal_record["trace_context"]
        self.assertEqual(goal_trace["request_id"], self.trace.request_id)
        self.assertEqual(goal_trace["trace_id"], self.trace.trace_id)
        self.assertEqual(goal_trace["parent_span_id"], self.trace.span_id)

        # Verify conformance to provisional GoalDefinition schema
        DraftSchemaValidator.validate_goal_definition(goal_record)

    def test_g02_update_goal(self):
        """G02: Verify that an existing goal's priority, constraints, or parameters can be updated dynamically."""
        created = self.runtime.create_goal(self.valid_intent, self.trace)
        goal_id = created["goal_id"]

        # Patch request modifying timeout from 120s to 300s and priority to 9
        updates = {
            "priority": 9,
            "constraints": {"timeout_seconds": 300, "max_retries": 3},
            "parameters": {"compression": "gzip"}
        }
        updated = self.runtime.update_goal(goal_id, updates, self.trace)

        # Expected result verification
        self.assertEqual(updated["goal_id"], goal_id, "goal_id must remain unchanged")
        self.assertEqual(updated["priority"], 9)
        self.assertEqual(updated["constraints"]["timeout_seconds"], 300)
        self.assertEqual(updated["constraints"]["max_retries"], 3)
        self.assertEqual(updated["parameters"]["compression"], "gzip")
        self.assertEqual(updated["parameters"]["source"], "/home/user/docs", "Unmodified parameters preserved")

        # Verify persistence via get_goal
        fetched = self.runtime.get_goal(goal_id, self.trace)
        self.assertEqual(fetched["priority"], 9)
        self.assertEqual(fetched["constraints"]["timeout_seconds"], 300)

    def test_g03_cancel_goal(self):
        """G03: Verify that an active goal can be aborted gracefully."""
        created = self.runtime.create_goal(self.valid_intent, self.trace)
        goal_id = created["goal_id"]

        cancelled = self.runtime.cancel_goal(goal_id, reason="User requested abort", trace_context=self.trace)

        # Expected result verification
        self.assertEqual(cancelled["state"], GoalStatus.CANCELLED.value)
        self.assertEqual(cancelled["cancellation_reason"], "User requested abort")

        # Verify audit history logged cancellation
        history = cancelled["history"]
        self.assertTrue(len(history) >= 2) # SUBMITTED -> ACTIVE -> CANCELLED
        self.assertEqual(history[-1]["to_state"], GoalStatus.CANCELLED.value)

    def test_g04_replan_goal(self):
        """G04: Verify that when a goal encounters an unrecoverable step failure, replanning is triggered."""
        created = self.runtime.create_goal(self.valid_intent, self.trace)
        goal_id = created["goal_id"]

        replanned = self.runtime.replan_goal(goal_id, trigger_reason="STEP_FAILED_UNRECOVERABLE", trace_context=self.trace)

        # Expected result verification
        self.assertEqual(replanned["state"], GoalStatus.REPLANNING.value)
        self.assertEqual(replanned["replan_reason"], "STEP_FAILED_UNRECOVERABLE")

        # Verify identity preserved
        self.assertEqual(replanned["goal_id"], goal_id)
        self.assertEqual(replanned["trace_context"]["request_id"], self.trace.request_id)

    # -------------------------------------------------------------------------
    # Supporting Tests: Identifiers & Tracing
    # -------------------------------------------------------------------------

    def test_unique_goal_ids(self):
        """Verify distinct goals receive distinct unique identifiers."""
        g1 = self.runtime.create_goal(self.valid_intent, self.trace)
        g2 = self.runtime.create_goal(self.valid_intent, self.trace)
        self.assertNotEqual(g1["goal_id"], g2["goal_id"])

    def test_get_nonexistent_goal_raises_not_found(self):
        """Verify querying unknown goal raises NotFoundError."""
        with self.assertRaises(NotFoundError):
            self.runtime.get_goal("goal-nonexistent-999", self.trace)

    # -------------------------------------------------------------------------
    # Supporting Tests: Priority & Constraint Validation
    # -------------------------------------------------------------------------

    def test_priority_validation(self):
        """Verify priority validation boundaries (1 to 10)."""
        # Valid boundary priorities
        intent_min = dict(self.valid_intent, priority=1)
        g_min = self.runtime.create_goal(intent_min, self.trace)
        self.assertEqual(g_min["priority"], 1)

        intent_max = dict(self.valid_intent, priority=10)
        g_max = self.runtime.create_goal(intent_max, self.trace)
        self.assertEqual(g_max["priority"], 10)

        # Out of bounds (< 1)
        intent_low = dict(self.valid_intent, priority=0)
        with self.assertRaises(ValidationError):
            self.runtime.create_goal(intent_low, self.trace)

        # Out of bounds (> 10)
        intent_high = dict(self.valid_intent, priority=11)
        with self.assertRaises(ValidationError):
            self.runtime.create_goal(intent_high, self.trace)

        # Non-integer / boolean
        intent_bool = dict(self.valid_intent, priority=True)
        with self.assertRaises(ValidationError):
            self.runtime.create_goal(intent_bool, self.trace)

    def test_constraints_validation(self):
        """Verify constraint field validation (timeout_seconds, max_retries)."""
        # Invalid timeout_seconds (<= 0)
        bad_timeout = dict(self.valid_intent, constraints={"timeout_seconds": 0})
        with self.assertRaises(ValidationError):
            self.runtime.create_goal(bad_timeout, self.trace)

        # Invalid max_retries (< 0)
        bad_retries = dict(self.valid_intent, constraints={"max_retries": -1})
        with self.assertRaises(ValidationError):
            self.runtime.create_goal(bad_retries, self.trace)

        # Non-dict constraints
        bad_constraints_type = dict(self.valid_intent, constraints="invalid")
        with self.assertRaises(ValidationError):
            self.runtime.create_goal(bad_constraints_type, self.trace)

    # -------------------------------------------------------------------------
    # Supporting Tests: Terminal State Behavior & State Machine
    # -------------------------------------------------------------------------

    def test_immutable_goal_id_update_rejected(self):
        """Verify attempting to modify goal_id during update raises ValidationError."""
        created = self.runtime.create_goal(self.valid_intent, self.trace)
        with self.assertRaises(ValidationError):
            self.runtime.update_goal(created["goal_id"], {"goal_id": "new-goal-id"}, self.trace)

    def test_terminal_state_goal_cannot_be_updated(self):
        """Verify updates are rejected when goal is in terminal state."""
        created = self.runtime.create_goal(self.valid_intent, self.trace)
        goal_id = created["goal_id"]

        # Cancel the goal (making it terminal)
        self.runtime.cancel_goal(goal_id, "User cancelled", self.trace)

        # Attempt to update cancelled goal
        with self.assertRaises(AgenticOSError) as ctx:
            self.runtime.update_goal(goal_id, {"priority": 8}, self.trace)
        self.assertEqual(ctx.exception.error_code, "GOAL_TERMINAL_STATE")

    def test_terminal_state_goal_cannot_be_replanned(self):
        """Verify replanning is rejected when goal is already cancelled."""
        created = self.runtime.create_goal(self.valid_intent, self.trace)
        goal_id = created["goal_id"]

        self.runtime.cancel_goal(goal_id, "User cancelled", self.trace)

        with self.assertRaises(AgenticOSError) as ctx:
            self.runtime.replan_goal(goal_id, "Replan attempt", self.trace)
        self.assertEqual(ctx.exception.error_code, "INVALID_STATE_TRANSITION")

    # -------------------------------------------------------------------------
    # Supporting Tests: Decomposition / Refinement
    # -------------------------------------------------------------------------

    def test_goal_decomposition_and_refinement(self):
        """Verify parent goal can decompose into child sub-goals."""
        parent = self.runtime.create_goal(self.valid_intent, self.trace)
        parent_id = parent["goal_id"]

        sub_goals_data = [
            {"action_name": "fs_scan_files", "parameters": {"path": "/home/user/docs"}},
            {"action_name": "fs_compress_archive", "parameters": {"format": "tar.gz"}}
        ]

        sub_records = self.runtime.decompose_goal(parent_id, sub_goals_data, self.trace)

        self.assertEqual(len(sub_records), 2)
        self.assertEqual(sub_records[0]["parent_goal_id"], parent_id)
        self.assertEqual(sub_records[1]["parent_goal_id"], parent_id)

        # Verify parent registered child IDs
        parent_updated = self.runtime.get_goal(parent_id, self.trace)
        self.assertEqual(len(parent_updated["sub_goal_ids"]), 2)
        self.assertIn(sub_records[0]["goal_id"], parent_updated["sub_goal_ids"])
        self.assertIn(sub_records[1]["goal_id"], parent_updated["sub_goal_ids"])

        # Verify get_sub_goals retrieval
        fetched_children = self.runtime.get_sub_goals(parent_id, self.trace)
        self.assertEqual(len(fetched_children), 2)

    # -------------------------------------------------------------------------
    # Supporting Tests: RequestLifecycle Integration
    # -------------------------------------------------------------------------

    def test_request_lifecycle_integration_with_real_goal_runtime(self):
        """Verify full path: Request -> RequestLifecycle -> Intent Validation -> GoalRuntime -> Goal Created."""
        lifecycle = RequestLifecycle(goal_runtime=self.runtime, confidence_threshold=0.70)
        raw_request = {
            "user_id": "usr-vivek",
            "intent_id": "int-lifecycle-e2e",
            "action_name": "backup_directory",
            "parameters": {"source": "/home/user/docs", "target": "/backup"},
            "confidence_score": 0.98,
            "priority": 7,
            "constraints": {"timeout_seconds": 180}
        }

        result = lifecycle.execute(raw_request)

        self.assertTrue(result.success)
        self.assertEqual(result.status, RequestStatus.COMPLETED)
        self.assertIsNotNone(result.goal_record)

        # Verify GoalRuntime actually created and stored the goal
        created_goal_id = result.goal_record["goal_id"]
        stored_goal = self.runtime.get_goal(created_goal_id, self.trace)
        self.assertEqual(stored_goal["action_name"], "backup_directory")
        self.assertEqual(stored_goal["priority"], 7)
        self.assertEqual(stored_goal["constraints"]["timeout_seconds"], 180)
        self.assertEqual(stored_goal["state"], GoalStatus.ACTIVE.value)

        # Tracing context checks
        self.assertEqual(stored_goal["trace_context"]["request_id"], result.request_id)
        self.assertEqual(stored_goal["trace_context"]["trace_id"], result.trace_id)


if __name__ == "__main__":
    unittest.main()
