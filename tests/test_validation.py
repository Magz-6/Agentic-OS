"""Unit tests for Provisional Schema Validation Harness.

Verifies:
- Valid provisional payloads conforming to docs/api-draft.md are accepted
- Invalid or incomplete payloads are rejected with clear ValidationError
"""

import unittest
from src.core.validation import DraftSchemaValidator
from src.core.errors import ValidationError


class TestSchemaValidation(unittest.TestCase):
    """Test suite for DraftSchemaValidator."""

    def setUp(self):
        self.valid_trace = {
            "request_id": "req-12345",
            "trace_id": "tr-67890",
            "span_id": "span-11111",
            "parent_span_id": None,
            "timestamp": "2026-09-27T12:00:00Z"
        }

    def test_trace_context_validation(self):
        """Verify TraceContext validation."""
        # Valid
        DraftSchemaValidator.validate_trace_context(self.valid_trace)

        # Missing field
        invalid_trace = dict(self.valid_trace)
        del invalid_trace["trace_id"]
        with self.assertRaises(ValidationError):
            DraftSchemaValidator.validate_trace_context(invalid_trace)

        # Empty string
        invalid_trace_empty = dict(self.valid_trace, span_id="  ")
        with self.assertRaises(ValidationError):
            DraftSchemaValidator.validate_trace_context(invalid_trace_empty)

    def test_intent_payload_validation(self):
        """Verify IntentPayload validation."""
        valid_intent = {
            "trace_context": self.valid_trace,
            "intent_id": "int-01",
            "user_id": "usr-vivek",
            "action_name": "backup_directory",
            "parameters": {"path": "/home/user/docs"},
            "confidence_score": 0.95
        }
        DraftSchemaValidator.validate_intent_payload(valid_intent)

        # Invalid confidence score (> 1.0)
        invalid_intent = dict(valid_intent, confidence_score=1.5)
        with self.assertRaises(ValidationError):
            DraftSchemaValidator.validate_intent_payload(invalid_intent)

        # Missing required parameter
        invalid_intent_missing = dict(valid_intent)
        del invalid_intent_missing["action_name"]
        with self.assertRaises(ValidationError):
            DraftSchemaValidator.validate_intent_payload(invalid_intent_missing)

    def test_goal_definition_validation(self):
        """Verify GoalDefinition validation."""
        valid_goal = {
            "trace_context": self.valid_trace,
            "goal_id": "goal-101",
            "intent_id": "int-01",
            "state": "SUBMITTED",
            "priority": 5,
            "constraints": {"timeout_seconds": 60},
            "parameters": {"target": "/backup"}
        }
        DraftSchemaValidator.validate_goal_definition(valid_goal)

        # Invalid priority (out of 1-10 range)
        invalid_priority = dict(valid_goal, priority=12)
        with self.assertRaises(ValidationError):
            DraftSchemaValidator.validate_goal_definition(invalid_priority)

        # Invalid state enum
        invalid_state = dict(valid_goal, state="RUNNING_NOW")
        with self.assertRaises(ValidationError):
            DraftSchemaValidator.validate_goal_definition(invalid_state)

    def test_workflow_plan_validation(self):
        """Verify WorkflowPlan validation."""
        valid_workflow = {
            "trace_context": self.valid_trace,
            "workflow_id": "wf-201",
            "goal_id": "goal-101",
            "plan_state": "PLANNED",
            "steps": [
                {
                    "step_id": "step-1",
                    "step_name": "scan_files",
                    "dependencies": [],
                    "required_capabilities": ["filesystem.read"],
                    "status": "READY"
                }
            ]
        }
        DraftSchemaValidator.validate_workflow_plan(valid_workflow)

        # Empty steps list
        invalid_empty_steps = dict(valid_workflow, steps=[])
        with self.assertRaises(ValidationError):
            DraftSchemaValidator.validate_workflow_plan(invalid_empty_steps)

        # Invalid plan_state
        invalid_plan_state = dict(valid_workflow, plan_state="UNKNOWN_STATE")
        with self.assertRaises(ValidationError):
            DraftSchemaValidator.validate_workflow_plan(invalid_plan_state)

    def test_agent_task_assignment_validation(self):
        """Verify AgentTaskAssignment validation."""
        valid_assignment = {
            "trace_context": self.valid_trace,
            "assignment_id": "asg-301",
            "step_id": "step-1",
            "agent_id": "agent-01",
            "status": "ALLOCATED",
            "deadline_utc": "2026-09-27T12:05:00Z"
        }
        DraftSchemaValidator.validate_agent_task_assignment(valid_assignment)

        # Invalid status
        invalid_status = dict(valid_assignment, status="INVALID_STATUS")
        with self.assertRaises(ValidationError):
            DraftSchemaValidator.validate_agent_task_assignment(invalid_status)

    def test_capability_invocation_validation(self):
        """Verify CapabilityInvocation validation."""
        valid_cap = {
            "trace_context": self.valid_trace,
            "invocation_id": "cap-inv-01",
            "capability_name": "fs_scan_directory",
            "caller_agent_id": "agent-01",
            "parameters": {"path": "/tmp"}
        }
        DraftSchemaValidator.validate_capability_invocation(valid_cap)

        # Missing caller
        invalid_cap = dict(valid_cap)
        del invalid_cap["caller_agent_id"]
        with self.assertRaises(ValidationError):
            DraftSchemaValidator.validate_capability_invocation(invalid_cap)

    def test_verification_report_validation(self):
        """Verify VerificationReport validation."""
        valid_report = {
            "trace_context": self.valid_trace,
            "goal_id": "goal-101",
            "verified": True,
            "status": "SUCCESS",
            "user_message": "Done"
        }
        DraftSchemaValidator.validate_verification_report(valid_report)

        # Invalid verified type (string instead of bool)
        invalid_verified = dict(valid_report, verified="yes")
        with self.assertRaises(ValidationError):
            DraftSchemaValidator.validate_verification_report(invalid_verified)


if __name__ == "__main__":
    unittest.main()
