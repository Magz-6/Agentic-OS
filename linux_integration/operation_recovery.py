#!/usr/bin/env python3
"""
AgenticOS - Adapter Operation Recovery
Owner: Magesh (Linux/OS Integration)

Coordinates crash recovery for persisted adapter operations.

This module does not implement Goal Runtime state or agent dispatch.
It only decides whether an interrupted adapter operation may safely resume.
"""

from __future__ import annotations

from typing import Any, Dict

from adapters.base import BaseAdapter
from .operation_store import OperationStatus, OperationStore


class OperationRecovery:
    """Recover persisted adapter operations after a service restart."""

    def __init__(self, store: OperationStore):
        self.store = store

    def recover(
        self,
        operation_id: str,
        adapter: BaseAdapter,
    ) -> Dict[str, Any]:
        """Recover one persisted operation using the adapter safety contract."""

        record = self.store.get(operation_id)

        if record is None:
            raise KeyError(f"Unknown operation: {operation_id}")

        status = record["status"]

        # A completed operation must never be executed again.
        if status == OperationStatus.COMPLETED:
            return record

        # An operation already requiring manual recovery must remain there.
        if status == OperationStatus.RECOVERY_REQUIRED:
            return record

        # Failed operations are only retryable when the adapter explicitly
        # declares the action safe to repeat.
        if status in {
            OperationStatus.RUNNING,
            OperationStatus.FAILED,
        }:
            action = record["operation"]
            parameters = dict(record.get("parameters") or {})

            if not adapter.is_retry_safe(action, parameters):
                return self.store.update(
                    operation_id,
                    OperationStatus.RECOVERY_REQUIRED,
                    {
                        "success": False,
                        "message": (
                            "Automatic retry blocked because the adapter "
                            "does not declare this operation retry-safe."
                        ),
                        "operation": action,
                    },
                )

            self.store.update(operation_id, OperationStatus.PENDING)

        # PENDING operations are safe to execute only when the adapter
        # explicitly permits retry.
        record = self.store.get(operation_id)

        if record["status"] == OperationStatus.PENDING:
            action = record["operation"]
            parameters = dict(record.get("parameters") or {})

            if not adapter.is_retry_safe(action, parameters):
                return self.store.update(
                    operation_id,
                    OperationStatus.RECOVERY_REQUIRED,
                    {
                        "success": False,
                        "message": (
                            "Automatic execution blocked because the adapter "
                            "does not declare this operation retry-safe."
                        ),
                        "operation": action,
                    },
                )

            self.store.update(operation_id, OperationStatus.RUNNING)

            result = adapter.run(action, parameters)
            result_dict = result.to_dict()

            if result.success:
                return self.store.update(
                    operation_id,
                    OperationStatus.COMPLETED,
                    result_dict,
                )

            return self.store.update(
                operation_id,
                OperationStatus.FAILED,
                result_dict,
            )

        return self.store.get(operation_id) or record
