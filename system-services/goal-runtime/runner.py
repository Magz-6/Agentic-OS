#!/usr/bin/env python3
"""AgenticOS Goal Runtime Service Daemon Runner.

Layer 12: Linux Integration Boundary & Layer 10: System Services.
Service: agenticos-goal-runtime.service
Owner: Magesh (Linux Integration & System Services Lead)
Component: Vivek's Goal Runtime (Layer 3)

Architectural Boundary:
- Vivek owns: Goal Runtime implementation (src.goal_runtime), lifecycle state machine,
  domain models, and validation logic.
- Magesh owns: Linux daemon lifecycle, systemd service integration, unprivileged sandboxing,
  and OS-level process management.
- Zero network exposure: Does NOT open HTTP ports, sockets, or unauthorized IPC channels.
- State Persistence Boundary: Vivek's runtime is in-memory. Persistent storage across
  reboots is currently BLOCKED / PENDING TEAM APPROVAL.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
from typing import Optional

# Ensure repository root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from src.goal_runtime.runtime import GoalRuntime
    from src.goal_runtime.interface import GoalRuntimeInterface
    from src.core.context import TraceContext
except ImportError as err:
    sys.stderr.write(f"FATAL: Failed to import Vivek's Goal Runtime modules: {err}\n")
    sys.exit(1)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [agenticos-goal-runtime] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("goal-runtime-service")


class GoalRuntimeServiceRunner:
    """Manages the OS-level systemd daemon lifecycle for Vivek's Goal Runtime."""

    def __init__(self, default_priority: int = 5, default_timeout_seconds: int = 120) -> None:
        self.default_priority = default_priority
        self.default_timeout_seconds = default_timeout_seconds
        self.shutdown_event = threading.Event()
        self.runtime: Optional[GoalRuntimeInterface] = None

    def initialize_runtime(self) -> GoalRuntimeInterface:
        """Instantiate Vivek's Goal Runtime without altering its internal logic."""
        logger.info("Initializing Vivek's Goal Runtime (Layer 3)...")
        self.runtime = GoalRuntime(
            default_priority=self.default_priority,
            default_timeout_seconds=self.default_timeout_seconds,
        )
        logger.info("Goal Runtime instance initialized successfully in memory.")
        return self.runtime

    def health_check(self) -> dict:
        """Perform an in-process diagnostic check of runtime readiness."""
        if self.runtime is None:
            return {"status": "uninitialized", "healthy": False}
        
        try:
            # Query runtime list without modifying state
            goals = self.runtime.list_goals()
            return {
                "status": "healthy",
                "healthy": True,
                "service": "agenticos-goal-runtime",
                "layer": 3,
                "active_goals_count": len(goals),
                "persistence": "in-memory (disk persistence pending team approval)",
            }
        except Exception as e:
            return {"status": "error", "healthy": False, "error": str(e)}

    def handle_signal(self, signum: int, frame) -> None:
        """Handle Linux process termination signals cleanly."""
        sig_name = signal.Signals(signum).name
        logger.info(f"Received signal {sig_name} ({signum}). Initiating graceful service shutdown...")
        self.shutdown_event.set()

    def run(self) -> int:
        """Main service execution loop under systemd."""
        logger.info(f"Starting AgenticOS Goal Runtime Service (PID: {os.getpid()})...")
        
        # Register signal handlers for systemd lifecycle management
        signal.signal(signal.SIGTERM, self.handle_signal)
        signal.signal(signal.SIGINT, self.handle_signal)

        self.initialize_runtime()

        health = self.health_check()
        logger.info(f"Service health check: {health['status'].upper()} (persistence: {health['persistence']})")
        logger.info("Goal Runtime service is active and ready.")

        # Block cleanly until systemd issues SIGTERM or SIGINT
        while not self.shutdown_event.is_set():
            self.shutdown_event.wait(timeout=1.0)

        logger.info("Goal Runtime service shutdown completed cleanly.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="AgenticOS Goal Runtime Service Runner")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run self-diagnostic health check and exit with status code",
    )
    args = parser.parse_args()

    runner = GoalRuntimeServiceRunner()

    if args.check:
        runner.initialize_runtime()
        health = runner.health_check()
        print(f"Health Status: {health}")
        return 0 if health.get("healthy") else 1

    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
