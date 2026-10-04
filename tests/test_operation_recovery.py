import tempfile
import unittest
from pathlib import Path

from adapters.application_adapter import ApplicationAdapter
from adapters.system_adapter import SystemAdapter

from linux_integration.operation_recovery import OperationRecovery
from linux_integration.operation_store import OperationStatus, OperationStore


class TestOperationRecovery(unittest.TestCase):

    def test_completed_operation_is_never_repeated(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = OperationStore(Path(tmp))
            record = store.create(
                "get_hostname",
                operation_id="completed-op",
                retry_safe=True,
            )

            store.update(
                record["operation_id"],
                OperationStatus.COMPLETED,
                {"hostname": "agenticos-test"},
            )

            recovery = OperationRecovery(store)
            result = recovery.recover(
                record["operation_id"],
                SystemAdapter(),
            )

            self.assertEqual(result["status"], OperationStatus.COMPLETED)
            self.assertEqual(
                result["result"]["hostname"],
                "agenticos-test",
            )

    def test_read_only_running_operation_is_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = OperationStore(Path(tmp))
            record = store.create(
                "get_hostname",
                operation_id="safe-retry-op",
                retry_safe=True,
            )

            store.update(
                record["operation_id"],
                OperationStatus.RUNNING,
            )

            recovery = OperationRecovery(store)
            result = recovery.recover(
                record["operation_id"],
                SystemAdapter(),
            )

            self.assertEqual(result["status"], OperationStatus.COMPLETED)
            self.assertTrue(result["result"]["success"])

    def test_application_launch_is_not_blindly_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = OperationStore(Path(tmp))
            record = store.create(
                "launch_application",
                {"application": "python"},
                operation_id="unsafe-launch-op",
                retry_safe=False,
            )

            store.update(
                record["operation_id"],
                OperationStatus.RUNNING,
            )

            recovery = OperationRecovery(store)
            result = recovery.recover(
                record["operation_id"],
                ApplicationAdapter(),
            )

            self.assertEqual(
                result["status"],
                OperationStatus.RECOVERY_REQUIRED,
            )
            self.assertFalse(result["result"]["success"])


if __name__ == "__main__":
    unittest.main()
