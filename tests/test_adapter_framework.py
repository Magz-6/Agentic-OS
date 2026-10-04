#!/usr/bin/env python3
"""Unit tests for AgenticOS Adapter Framework base and registry.

Verifies:
1. BaseAdapter contract enforcement and execution template.
2. AdapterRegistry registration, retrieval, listing, override, and type guards.
3. AdapterResult serialization and status code integrity.
4. Exception containment: unhandled errors become EXECUTION_ERROR.
"""

from __future__ import annotations

import unittest
from typing import Any, Dict, Optional, Set, Tuple

from adapters.base import BaseAdapter
from adapters.registry import (
    AdapterRegistry,
    DuplicateAdapterError,
    InvalidAdapterError,
)
from adapters.result import AdapterResult, AdapterStatus


class DummyTestAdapter(BaseAdapter):
    """Mock adapter for testing framework contracts."""

    @property
    def name(self) -> str:
        return "mock_adapter"

    @property
    def supported_actions(self) -> Set[str]:
        return {"echo", "fail_action", "crash_action"}

    def validate(
        self, action: str, parameters: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        if action not in self.supported_actions:
            return False, f"Action '{action}' not supported"
        if action == "echo":
            if "message" not in parameters:
                return False, "Missing required parameter 'message'"
            if not isinstance(parameters["message"], str):
                return False, "Parameter 'message' must be a string"
        return True, None

    def execute(self, action: str, parameters: Dict[str, Any]) -> AdapterResult:
        if action == "echo":
            return AdapterResult.success_result(
                adapter=self.name,
                action=action,
                message="Echo completed",
                data={"echo": parameters["message"]},
            )
        elif action == "fail_action":
            return AdapterResult.execution_error(
                adapter=self.name,
                action=action,
                message="Controlled failure occurred",
            )
        elif action == "crash_action":
            raise RuntimeError("Simulated unexpected crash")

        return AdapterResult.unsupported_action(self.name, action)


class TestAdapterFramework(unittest.TestCase):
    """Test suite for BaseAdapter, AdapterResult, and AdapterRegistry."""

    def setUp(self):
        self.registry = AdapterRegistry()
        self.adapter = DummyTestAdapter()

    def test_adapter_properties(self):
        """Verify adapter metadata properties."""
        self.assertEqual(self.adapter.name, "mock_adapter")
        self.assertEqual(
            self.adapter.supported_actions, {"echo", "fail_action", "crash_action"}
        )

    def test_adapter_successful_execution(self):
        """Verify successful action validation and execution flow."""
        res = self.adapter.run("echo", {"message": "hello world"})
        self.assertTrue(res.success)
        self.assertEqual(res.status, AdapterStatus.SUCCESS)
        self.assertEqual(res.adapter, "mock_adapter")
        self.assertEqual(res.action, "echo")
        self.assertEqual(res.data, {"echo": "hello world"})
        self.assertIsNone(res.error)

    def test_adapter_unsupported_action(self):
        """Verify that unsupported action is rejected without executing."""
        res = self.adapter.run("nonexistent_action", {})
        self.assertFalse(res.success)
        self.assertEqual(res.status, AdapterStatus.UNSUPPORTED_ACTION)
        self.assertIn("nonexistent_action", res.message)
        self.assertIsNotNone(res.error)

    def test_adapter_validation_failure(self):
        """Verify parameter validation failure returns VALIDATION_ERROR."""
        # Missing message parameter
        res1 = self.adapter.run("echo", {})
        self.assertFalse(res1.success)
        self.assertEqual(res1.status, AdapterStatus.VALIDATION_ERROR)
        self.assertIn("Missing required parameter 'message'", res1.message)

        # Invalid type for message parameter
        res2 = self.adapter.run("echo", {"message": 12345})
        self.assertFalse(res2.success)
        self.assertEqual(res2.status, AdapterStatus.VALIDATION_ERROR)

    def test_adapter_crash_containment(self):
        """Verify that unhandled exceptions inside execute are caught and converted to EXECUTION_ERROR."""
        res = self.adapter.run("crash_action", {})
        self.assertFalse(res.success)
        self.assertEqual(res.status, AdapterStatus.EXECUTION_ERROR)
        self.assertIn("Simulated unexpected crash", res.message)
        self.assertEqual(res.error.get("exception_type"), "RuntimeError")

    def test_registry_register_and_get(self):
        """Verify registration and retrieval from AdapterRegistry."""
        self.assertFalse(self.registry.has("mock_adapter"))
        self.registry.register(self.adapter)
        self.assertTrue(self.registry.has("mock_adapter"))

        retrieved = self.registry.get("mock_adapter")
        self.assertIs(retrieved, self.adapter)

    def test_registry_duplicate_registration_guard(self):
        """Verify duplicate registration raises DuplicateAdapterError unless overridden."""
        self.registry.register(self.adapter)
        with self.assertRaises(DuplicateAdapterError):
            self.registry.register(self.adapter)

        # Allow override succeeds
        self.registry.register(self.adapter, allow_override=True)
        self.assertIs(self.registry.get("mock_adapter"), self.adapter)

    def test_registry_type_safety_guard(self):
        """Verify registering an object that is not a BaseAdapter raises InvalidAdapterError."""
        with self.assertRaises(InvalidAdapterError):
            self.registry.register("not an adapter")  # type: ignore

    def test_registry_listing_and_unregister(self):
        """Verify listing and removing adapters from registry."""
        self.registry.register(self.adapter)
        self.assertEqual(self.registry.list_adapters(), ["mock_adapter"])

        removed = self.registry.unregister("mock_adapter")
        self.assertTrue(removed)
        self.assertFalse(self.registry.has("mock_adapter"))
        self.assertIsNone(self.registry.get("mock_adapter"))

        # Unregistering nonexistent returns False
        self.assertFalse(self.registry.unregister("mock_adapter"))

    def test_result_to_dict_serialization(self):
        """Verify AdapterResult dictionary serialization format."""
        res = AdapterResult.success_result(
            adapter="test", action="act", message="done", data={"k": "v"}
        )
        d = res.to_dict()
        self.assertEqual(d["success"], True)
        self.assertEqual(d["status"], "SUCCESS")
        self.assertEqual(d["adapter"], "test")
        self.assertEqual(d["action"], "act")
        self.assertEqual(d["message"], "done")
        self.assertEqual(d["data"], {"k": "v"})


if __name__ == "__main__":
    unittest.main()
