"""Provisional Schema Validation Harness for AgenticOS v0.1 Alpha.

This module provides validation logic for the draft data contracts defined in
`docs/api-draft.md`.

Note:
These schemas are PROVISIONAL DRAFTS and are not frozen.
This lightweight harness uses standard-library Python to validate payloads,
ensuring clean separation while ADR-0004 (Schema Specification Standard)
remains under team review.
"""

from typing import Dict, Any, List, Optional
from .errors import ValidationError
from .status import GoalStatus, WorkflowStatus, StepStatus, AgentStatus


class DraftSchemaValidator:
    """Validates dictionaries against provisional AgenticOS draft contracts."""

    @staticmethod
    def _require_fields(data: Dict[str, Any], required: List[str], schema_name: str) -> None:
        """Ensure all required fields exist in data."""
        if not isinstance(data, dict):
            raise ValidationError(
                message=f"Expected {schema_name} payload to be a dict, got {type(data).__name__}",
                details={"schema": schema_name}
            )
        missing = [f for f in required if f not in data]
        if missing:
            raise ValidationError(
                message=f"Missing required field(s) in {schema_name}: {missing}",
                details={"schema": schema_name, "missing_fields": missing}
            )

    @classmethod
    def validate_trace_context(cls, data: Dict[str, Any]) -> None:
        """Validate TraceContext provisional schema."""
        required = ["request_id", "trace_id", "span_id", "timestamp"]
        cls._require_fields(data, required, "TraceContext")
        for f in required:
            if not isinstance(data[f], str) or not data[f].strip():
                raise ValidationError(
                    f"Field '{f}' in TraceContext must be a non-empty string",
                    details={"field": f, "value": data[f]}
                )

    @classmethod
    def validate_intent_payload(cls, data: Dict[str, Any]) -> None:
        """Validate IntentPayload provisional schema."""
        required = [
            "trace_context", "intent_id", "user_id",
            "action_name", "parameters", "confidence_score"
        ]
        cls._require_fields(data, required, "IntentPayload")
        cls.validate_trace_context(data["trace_context"])
        
        if not isinstance(data["confidence_score"], (int, float)):
            raise ValidationError("Field 'confidence_score' must be a float/number")
        if not (0.0 <= data["confidence_score"] <= 1.0):
            raise ValidationError("Field 'confidence_score' must be between 0.0 and 1.0")
        if not isinstance(data["parameters"], dict):
            raise ValidationError("Field 'parameters' must be a dictionary")

    @classmethod
    def validate_goal_definition(cls, data: Dict[str, Any]) -> None:
        """Validate GoalDefinition provisional schema."""
        required = [
            "trace_context", "goal_id", "intent_id",
            "state", "priority", "constraints", "parameters"
        ]
        cls._require_fields(data, required, "GoalDefinition")
        cls.validate_trace_context(data["trace_context"])

        valid_states = [s.value for s in GoalStatus]
        if data["state"] not in valid_states:
            raise ValidationError(
                f"Invalid goal state '{data['state']}'. Must be one of {valid_states}",
                details={"state": data["state"], "allowed": valid_states}
            )

        if not isinstance(data["priority"], int) or not (1 <= data["priority"] <= 10):
            raise ValidationError("Field 'priority' must be an integer between 1 and 10")
        if not isinstance(data["constraints"], dict):
            raise ValidationError("Field 'constraints' must be a dictionary")
        if not isinstance(data["parameters"], dict):
            raise ValidationError("Field 'parameters' must be a dictionary")

    @classmethod
    def validate_workflow_plan(cls, data: Dict[str, Any]) -> None:
        """Validate WorkflowPlan provisional schema."""
        required = ["trace_context", "workflow_id", "goal_id", "plan_state", "steps"]
        cls._require_fields(data, required, "WorkflowPlan")
        cls.validate_trace_context(data["trace_context"])

        valid_plan_states = [s.value for s in WorkflowStatus]
        if data["plan_state"] not in valid_plan_states:
            raise ValidationError(
                f"Invalid workflow plan_state '{data['plan_state']}'. Must be one of {valid_plan_states}"
            )

        if not isinstance(data["steps"], list) or len(data["steps"]) == 0:
            raise ValidationError("Field 'steps' in WorkflowPlan must be a non-empty list")

        for idx, step in enumerate(data["steps"]):
            step_req = ["step_id", "step_name", "dependencies", "required_capabilities", "status"]
            cls._require_fields(step, step_req, f"WorkflowPlan.step[{idx}]")
            if not isinstance(step["dependencies"], list):
                raise ValidationError(f"Step[{idx}] dependencies must be a list")
            if not isinstance(step["required_capabilities"], list):
                raise ValidationError(f"Step[{idx}] required_capabilities must be a list")

    @classmethod
    def validate_agent_task_assignment(cls, data: Dict[str, Any]) -> None:
        """Validate AgentTaskAssignment provisional schema."""
        required = ["trace_context", "assignment_id", "step_id", "agent_id", "status", "deadline_utc"]
        cls._require_fields(data, required, "AgentTaskAssignment")
        cls.validate_trace_context(data["trace_context"])

        valid_statuses = ["OFFERED", "ALLOCATED", "RUNNING", "COMPLETED", "TIMEOUT", "FAILED"]
        if data["status"] not in valid_statuses:
            raise ValidationError(f"Invalid assignment status '{data['status']}'")

    @classmethod
    def validate_capability_invocation(cls, data: Dict[str, Any]) -> None:
        """Validate CapabilityInvocation provisional schema."""
        required = ["trace_context", "invocation_id", "capability_name", "parameters", "caller_agent_id"]
        cls._require_fields(data, required, "CapabilityInvocation")
        cls.validate_trace_context(data["trace_context"])
        if not isinstance(data["parameters"], dict):
            raise ValidationError("Field 'parameters' in CapabilityInvocation must be a dict")

    @classmethod
    def validate_verification_report(cls, data: Dict[str, Any]) -> None:
        """Validate VerificationReport provisional schema."""
        required = ["trace_context", "goal_id", "verified", "status", "user_message"]
        cls._require_fields(data, required, "VerificationReport")
        cls.validate_trace_context(data["trace_context"])
        if not isinstance(data["verified"], bool):
            raise ValidationError("Field 'verified' must be a boolean")
        valid_statuses = ["SUCCESS", "FAILED_VERIFICATION", "SYSTEM_ERROR"]
        if data["status"] not in valid_statuses:
            raise ValidationError(f"Invalid verification status '{data['status']}'")
