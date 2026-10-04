#!/usr/bin/env python3
"""
AgenticOS - Persistent Operation Store
Owner: Magesh (Linux/OS Integration)

Durable persistence boundary for OS-level adapter operations.

This module records operation lifecycle state so a restarted service can
determine whether an operation completed, failed, or requires recovery.
It does not implement Goal Runtime state.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Optional


class OperationStatus:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


class OperationStore:
    """Durable JSON-backed operation journal."""

    VALID_STATUSES = {
        OperationStatus.PENDING,
        OperationStatus.RUNNING,
        OperationStatus.COMPLETED,
        OperationStatus.FAILED,
        OperationStatus.RECOVERY_REQUIRED,
    }

    def __init__(self, root: Path | str = "/var/lib/agenticos/operations"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        operation: str,
        parameters: Optional[Dict[str, Any]] = None,
        operation_id: Optional[str] = None,
        retry_safe: bool = False,
    ) -> Dict[str, Any]:
        """Create a new durable operation record."""
        op_id = operation_id or str(uuid.uuid4())

        if self.get(op_id) is not None:
            raise ValueError(f"Operation already exists: {op_id}")

        record = {
            "operation_id": op_id,
            "operation": operation,
            "parameters": parameters or {},
            "retry_safe": bool(retry_safe),
            "status": OperationStatus.PENDING,
            "result": None,
        }

        self._write(op_id, record)
        return record

    def get(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Load an operation record, or None if it does not exist."""
        path = self.root / f"{operation_id}.json"

        if not path.exists():
            return None

        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def update(
        self,
        operation_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Atomically update an operation status and result."""
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid operation status: {status}")

        record = self.get(operation_id)

        if record is None:
            raise KeyError(f"Unknown operation: {operation_id}")

        record["status"] = status
        record["result"] = result

        self._write(operation_id, record)
        return record

    def recover(self, operation_id: str) -> Dict[str, Any]:
        """
        Determine safe recovery state after a restart.

        COMPLETED operations are never repeated.
        RUNNING operations are either marked RECOVERY_REQUIRED or returned
        as retryable when the original operation was explicitly declared safe.
        """
        record = self.get(operation_id)

        if record is None:
            raise KeyError(f"Unknown operation: {operation_id}")

        status = record["status"]

        if status == OperationStatus.COMPLETED:
            return record

        if status == OperationStatus.RUNNING:
            if record.get("retry_safe", False):
                record["status"] = OperationStatus.PENDING
            else:
                record["status"] = OperationStatus.RECOVERY_REQUIRED

            self._write(operation_id, record)

        return record

    def _write(self, operation_id: str, record: Dict[str, Any]) -> None:
        """Atomically replace the operation record."""
        destination = self.root / f"{operation_id}.json"

        fd, temp_name = tempfile.mkstemp(
            prefix=f".{operation_id}.",
            suffix=".tmp",
            dir=self.root,
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(record, handle, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(temp_name, destination)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
