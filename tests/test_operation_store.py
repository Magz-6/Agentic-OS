import tempfile
import unittest
from pathlib import Path

from linux_integration.operation_store import (
    OperationStatus,
    OperationStore,
)


class TestOperationStore(unittest.TestCase):

    def test_operation_survives_store_recreation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            # First process/service instance
            store1 = OperationStore(root)
            created = store1.create(
                operation="filesystem.inspect_path",
                parameters={"path": "/tmp/example"},
                operation_id="op-restart-001",
            )

            store1.update(
                "op-restart-001",
                OperationStatus.COMPLETED,
                {"verified": True},
            )

            # Simulate service restart by creating a new store instance
            store2 = OperationStore(root)
            recovered = store2.get("op-restart-001")

            self.assertIsNotNone(recovered)
            self.assertEqual(
                recovered["status"],
                OperationStatus.COMPLETED,
            )
            self.assertEqual(
                recovered["result"],
                {"verified": True},
            )

    def test_completed_operation_is_not_lost(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = OperationStore(tmp)

            store.create(
                operation="system.read_status",
                operation_id="op-complete-001",
            )

            store.update(
                "op-complete-001",
                OperationStatus.COMPLETED,
                {"healthy": True},
            )

            record = store.get("op-complete-001")

            self.assertEqual(
                record["status"],
                OperationStatus.COMPLETED,
            )

    def test_duplicate_operation_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = OperationStore(tmp)

            store.create(
                operation="filesystem.inspect_path",
                operation_id="op-duplicate-001",
            )

            with self.assertRaises(ValueError):
                store.create(
                    operation="filesystem.inspect_path",
                    operation_id="op-duplicate-001",
                )


if __name__ == "__main__":
    unittest.main()


class TestOperationRecovery(unittest.TestCase):

    def test_recovery_identifies_incomplete_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = OperationStore(tmp)

            store.create(
                operation="filesystem.inspect_path",
                operation_id="op-recovery-001",
            )

            store.update(
                "op-recovery-001",
                OperationStatus.RUNNING,
            )

            # Simulate service restart
            restarted_store = OperationStore(tmp)
            recovered = restarted_store.get("op-recovery-001")

            self.assertIsNotNone(recovered)
            self.assertEqual(
                recovered["status"],
                OperationStatus.RUNNING,
            )

            # The recovery layer can now decide to verify/retry.
            self.assertNotEqual(
                recovered["status"],
                OperationStatus.COMPLETED,
            )


if __name__ == "__main__":
    unittest.main()


class TestOperationAdapterBoundary(unittest.TestCase):

    def test_adapter_operation_can_be_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = OperationStore(tmp)

            operation = store.create(
                operation="filesystem.inspect_path",
                parameters={"path": "/tmp"},
                operation_id="op-adapter-001",
            )

            self.assertEqual(
                operation["status"],
                OperationStatus.PENDING,
            )

            # Adapter execution begins.
            store.update(
                "op-adapter-001",
                OperationStatus.RUNNING,
            )

            # Adapter completed successfully.
            store.update(
                "op-adapter-001",
                OperationStatus.COMPLETED,
                {
                    "adapter": "filesystem",
                    "action": "inspect_path",
                    "verified": True,
                },
            )

            recovered = store.get("op-adapter-001")

            self.assertEqual(
                recovered["status"],
                OperationStatus.COMPLETED,
            )
            self.assertTrue(
                recovered["result"]["verified"]
            )


if __name__ == "__main__":
    unittest.main()
