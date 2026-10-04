"""Unit tests for Core Foundation Primitives.

Verifies:
- TraceContext and RequestContext generation and propagation
- Structured error handling and serialization
- ExecutionResult and VerificationReport structures
- Status enum integrity
"""

import unittest
from src.core.context import TraceContext, RequestContext
from src.core.status import GoalStatus, WorkflowStatus, StepStatus, AgentStatus
from src.core.errors import AgenticOSError, ValidationError, PolicyViolationError, TimeoutError
from src.core.results import ExecutionResult, VerificationCheck, VerificationReport


class TestCorePrimitives(unittest.TestCase):
    """Test suite for foundation primitives in src/core."""

    def test_trace_context_creation_and_child_span(self):
        """Verify root TraceContext generation and child span propagation."""
        root = TraceContext.new_root()
        self.assertTrue(root.request_id.startswith("req-"))
        self.assertTrue(root.trace_id.startswith("tr-"))
        self.assertTrue(root.span_id.startswith("span-"))
        self.assertIsNone(root.parent_span_id)
        self.assertIsNotNone(root.timestamp)

        # Spawn child span for downstream layer
        child = root.child_span()
        self.assertEqual(child.request_id, root.request_id, "Child must inherit request_id")
        self.assertEqual(child.trace_id, root.trace_id, "Child must inherit trace_id")
        self.assertNotEqual(child.span_id, root.span_id, "Child must generate new span_id")
        self.assertEqual(child.parent_span_id, root.span_id, "Child parent_span_id must equal root span_id")

        # Verify dictionary serialization and round-trip
        data = child.to_dict()
        reconstructed = TraceContext.from_dict(data)
        self.assertEqual(reconstructed.request_id, child.request_id)
        self.assertEqual(reconstructed.trace_id, child.trace_id)
        self.assertEqual(reconstructed.span_id, child.span_id)
        self.assertEqual(reconstructed.parent_span_id, child.parent_span_id)

    def test_request_context_creation(self):
        """Verify RequestContext creation with embedded TraceContext."""
        ctx = RequestContext.create(
            user_id="usr-vivek",
            session_id="term-01",
            privilege_level="admin"
        )
        self.assertEqual(ctx.user_id, "usr-vivek")
        self.assertEqual(ctx.session_id, "term-01")
        self.assertEqual(ctx.privilege_level, "admin")
        self.assertIsNotNone(ctx.trace.request_id)

        serialized = ctx.to_dict()
        self.assertIn("trace_context", serialized)
        self.assertEqual(serialized["user_id"], "usr-vivek")

    def test_structured_errors_to_dict(self):
        """Verify structured errors retain error codes and trace context."""
        trace = TraceContext.new_root()
        err = PolicyViolationError(
            message="Direct root shell access is forbidden",
            trace_context=trace,
            details={"attempted_layer": "Linux Kernel", "rule": "ADR-0002"}
        )
        self.assertIsInstance(err, AgenticOSError)
        payload = err.to_dict()
        self.assertTrue(payload["error"])
        self.assertEqual(payload["error_code"], "SECURITY_POLICY_VIOLATION")
        self.assertEqual(payload["message"], "Direct root shell access is forbidden")
        self.assertEqual(payload["trace_context"]["trace_id"], trace.trace_id)
        self.assertEqual(payload["details"]["rule"], "ADR-0002")

    def test_execution_result_helpers(self):
        """Verify ExecutionResult successful and failed factories."""
        trace = TraceContext.new_root()

        res_ok = ExecutionResult.successful(
            trace_context=trace,
            data={"archive_path": "/tmp/test.tar.gz"},
            metrics={"duration_ms": 42}
        )
        self.assertTrue(res_ok.success)
        self.assertEqual(res_ok.data["archive_path"], "/tmp/test.tar.gz")
        self.assertEqual(res_ok.metrics["duration_ms"], 42)

        res_fail = ExecutionResult.failed(
            trace_context=trace,
            error_message="Disk full",
            error_code="STORAGE_RESOURCE_EXHAUSTED"
        )
        self.assertFalse(res_fail.success)
        self.assertEqual(res_fail.error["error_code"], "STORAGE_RESOURCE_EXHAUSTED")

    def test_verification_report_structure(self):
        """Verify VerificationReport and individual check items."""
        trace = TraceContext.new_root()
        report = VerificationReport(
            goal_id="goal-101",
            verified=True,
            status="SUCCESS",
            user_message="Archive verified successfully.",
            trace_context=trace,
            checks=[
                VerificationCheck("file_exists", True, "File found at /tmp/test.tar.gz"),
                VerificationCheck("checksum_matches", True, "sha256 verified")
            ]
        )
        dict_rep = report.to_dict()
        self.assertEqual(dict_rep["goal_id"], "goal-101")
        self.assertTrue(dict_rep["verified"])
        self.assertEqual(len(dict_rep["checks"]), 2)

    def test_status_enums(self):
        """Verify standard lifecycle values across enums."""
        self.assertEqual(GoalStatus.SUBMITTED.value, "SUBMITTED")
        self.assertEqual(GoalStatus.ACTIVE.value, "ACTIVE")
        self.assertEqual(GoalStatus.CANCELLED.value, "CANCELLED")

        self.assertEqual(WorkflowStatus.PLANNED.value, "PLANNED")
        self.assertEqual(WorkflowStatus.EXECUTING.value, "EXECUTING")

        self.assertEqual(StepStatus.PENDING.value, "PENDING")
        self.assertEqual(StepStatus.RUNNING.value, "RUNNING")

        self.assertEqual(AgentStatus.IDLE.value, "IDLE")
        self.assertEqual(AgentStatus.ALLOCATED.value, "ALLOCATED")
        self.assertEqual(AgentStatus.UNHEALTHY.value, "UNHEALTHY")


if __name__ == "__main__":
    unittest.main()
