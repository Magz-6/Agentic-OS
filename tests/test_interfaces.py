"""Unit tests for Core Abstract Interfaces.

Verifies:
- GoalRuntimeInterface, WorkflowRuntimeInterface, and GlobalAgentManagerInterface expose expected methods
- ABC enforcement prevents incomplete implementations
- Test double classes can cleanly implement and satisfy the contracts
"""

import unittest
import sys
import subprocess
from typing import Dict, Any, List
from src.core.context import TraceContext
from src.core.errors import NotFoundError
from src.goal_runtime.interface import GoalRuntimeInterface
from src.workflow_runtime.interface import WorkflowRuntimeInterface
from src.agent_manager.interface import GlobalAgentManagerInterface


class DummyGoalRuntime(GoalRuntimeInterface):
    """Minimal test double implementing GoalRuntimeInterface."""

    def __init__(self):
        self.goals = {}

    def create_goal(self, intent_payload: Dict[str, Any], trace_context: TraceContext) -> Dict[str, Any]:
        goal_id = "goal-test-01"
        record = {
            "goal_id": goal_id,
            "intent_id": intent_payload.get("intent_id"),
            "state": "SUBMITTED",
            "priority": 5,
            "constraints": {},
            "parameters": intent_payload.get("parameters", {}),
            "trace_context": trace_context.to_dict()
        }
        self.goals[goal_id] = record
        return record

    def get_goal(self, goal_id: str, trace_context: TraceContext) -> Dict[str, Any]:
        if goal_id not in self.goals:
            raise NotFoundError(f"Goal '{goal_id}' not found", trace_context=trace_context)
        return self.goals[goal_id]

    def update_goal(self, goal_id: str, updates: Dict[str, Any], trace_context: TraceContext) -> Dict[str, Any]:
        goal = self.get_goal(goal_id, trace_context)
        goal.update(updates)
        return goal

    def cancel_goal(self, goal_id: str, reason: str, trace_context: TraceContext) -> Dict[str, Any]:
        goal = self.get_goal(goal_id, trace_context)
        goal["state"] = "CANCELLED"
        goal["cancellation_reason"] = reason
        return goal

    def replan_goal(self, goal_id: str, trigger_reason: str, trace_context: TraceContext) -> Dict[str, Any]:
        goal = self.get_goal(goal_id, trace_context)
        goal["state"] = "REPLANNING"
        goal["replan_reason"] = trigger_reason
        return goal


class DummyWorkflowRuntime(WorkflowRuntimeInterface):
    """Minimal test double implementing WorkflowRuntimeInterface."""

    def __init__(self):
        self.workflows = {}

    def create_workflow(self, goal_definition: Dict[str, Any], trace_context: TraceContext) -> Dict[str, Any]:
        wf_id = "wf-test-01"
        record = {
            "workflow_id": wf_id,
            "goal_id": goal_definition.get("goal_id"),
            "plan_state": "PLANNED",
            "steps": [],
            "trace_context": trace_context.to_dict()
        }
        self.workflows[wf_id] = record
        return record

    def get_workflow(self, workflow_id: str, trace_context: TraceContext) -> Dict[str, Any]:
        if workflow_id not in self.workflows:
            raise NotFoundError(f"Workflow '{workflow_id}' not found", trace_context=trace_context)
        return self.workflows[workflow_id]

    def dispatch_workflow(self, workflow_id: str, trace_context: TraceContext) -> Dict[str, Any]:
        wf = self.get_workflow(workflow_id, trace_context)
        wf["plan_state"] = "EXECUTING"
        return {"workflow_id": workflow_id, "status": "EXECUTING"}

    def replan_workflow(self, workflow_id: str, failed_step_id: str, failure_reason: str, trace_context: TraceContext) -> Dict[str, Any]:
        wf = self.get_workflow(workflow_id, trace_context)
        wf["plan_state"] = "PLANNED"
        return wf


class DummyAgentManager(GlobalAgentManagerInterface):
    """Minimal test double implementing GlobalAgentManagerInterface."""

    def __init__(self):
        self.registry = {}
        self.assignments = {}

    def register_agent(self, agent_descriptor: Dict[str, Any], trace_context: TraceContext) -> Dict[str, Any]:
        agent_id = agent_descriptor["agent_id"]
        self.registry[agent_id] = agent_descriptor
        return {"agent_id": agent_id, "status": "REGISTERED"}

    def discover_agents(self, capability: str, trace_context: TraceContext) -> List[Dict[str, Any]]:
        return [
            agent for agent in self.registry.values()
            if capability in agent.get("capabilities", [])
        ]

    def allocate_agent(self, step_requirement: Dict[str, Any], trace_context: TraceContext) -> Dict[str, Any]:
        assignment_id = "asg-test-01"
        assignment = {
            "assignment_id": assignment_id,
            "step_id": step_requirement.get("step_id"),
            "agent_id": "agent-test-worker",
            "status": "ALLOCATED",
            "deadline_utc": "2026-09-27T12:05:00Z",
            "trace_context": trace_context.to_dict()
        }
        self.assignments[assignment_id] = assignment
        return assignment

    def release_agent(self, assignment_id: str, final_status: str, trace_context: TraceContext) -> Dict[str, Any]:
        return {"assignment_id": assignment_id, "status": "RELEASED"}

    def update_agent_health(self, agent_id: str, status: str, trace_context: TraceContext) -> Dict[str, Any]:
        return {"agent_id": agent_id, "status": status}


class TestCoreInterfaces(unittest.TestCase):
    """Test suite verifying interface definitions and ABC enforcement."""

    def test_abc_prevents_incomplete_subclass(self):
        """Verifies that an incomplete implementation raises TypeError."""
        class IncompleteGoalRuntime(GoalRuntimeInterface):
            pass

        with self.assertRaises(TypeError):
            IncompleteGoalRuntime()

    def test_goal_runtime_interface_implementation(self):
        """Verify DummyGoalRuntime satisfies GoalRuntimeInterface."""
        runtime = DummyGoalRuntime()
        trace = TraceContext.new_root()
        
        goal = runtime.create_goal({"intent_id": "int-01", "parameters": {}}, trace)
        self.assertEqual(goal["state"], "SUBMITTED")

        fetched = runtime.get_goal("goal-test-01", trace)
        self.assertEqual(fetched["goal_id"], "goal-test-01")

        updated = runtime.update_goal("goal-test-01", {"priority": 8}, trace)
        self.assertEqual(updated["priority"], 8)

        cancelled = runtime.cancel_goal("goal-test-01", "User cancelled", trace)
        self.assertEqual(cancelled["state"], "CANCELLED")

        replanned = runtime.replan_goal("goal-test-01", "Step failure", trace)
        self.assertEqual(replanned["state"], "REPLANNING")

    def test_workflow_runtime_interface_implementation(self):
        """Verify DummyWorkflowRuntime satisfies WorkflowRuntimeInterface."""
        runtime = DummyWorkflowRuntime()
        trace = TraceContext.new_root()

        wf = runtime.create_workflow({"goal_id": "goal-01"}, trace)
        self.assertEqual(wf["plan_state"], "PLANNED")

        fetched = runtime.get_workflow("wf-test-01", trace)
        self.assertEqual(fetched["workflow_id"], "wf-test-01")

        dispatched = runtime.dispatch_workflow("wf-test-01", trace)
        self.assertEqual(dispatched["status"], "EXECUTING")

        replanned = runtime.replan_workflow("wf-test-01", "step-1", "Timeout", trace)
        self.assertEqual(replanned["plan_state"], "PLANNED")

    def test_agent_manager_interface_implementation(self):
        """Verify DummyAgentManager satisfies GlobalAgentManagerInterface."""
        manager = DummyAgentManager()
        trace = TraceContext.new_root()

        reg = manager.register_agent({
            "agent_id": "agent-01",
            "capabilities": ["file.compress", "file.read"]
        }, trace)
        self.assertEqual(reg["status"], "REGISTERED")

        discovered = manager.discover_agents("file.compress", trace)
        self.assertEqual(len(discovered), 1)

        allocated = manager.allocate_agent({"step_id": "step-compress"}, trace)
        self.assertEqual(allocated["status"], "ALLOCATED")

        released = manager.release_agent("asg-test-01", "COMPLETED", trace)
        self.assertEqual(released["status"], "RELEASED")

        health = manager.update_agent_health("agent-01", "IDLE", trace)
        self.assertEqual(health["status"], "IDLE")

    def test_import_order_independence_fresh_processes(self):
        """Regression test: verify importing goal_runtime and core in any order is completely safe."""
        statements = [
            "from src.goal_runtime import GoalRuntime; from src.core import TraceContext",
            "from src.core import TraceContext; from src.goal_runtime import GoalRuntime",
            "from src.goal_runtime import GoalRuntime; from src.core import RequestLifecycle",
            "from src.core import RequestLifecycle; from src.goal_runtime import GoalRuntime",
            "from src.goal_runtime import GoalRuntimeInterface; from src.core import RequestLifecycle",
        ]
        for stmt in statements:
            proc = subprocess.run(
                [sys.executable, "-c", stmt],
                capture_output=True,
                text=True
            )
            self.assertEqual(
                proc.returncode,
                0,
                f"Failed import order statement '{stmt}':\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
            )


if __name__ == "__main__":
    unittest.main()
