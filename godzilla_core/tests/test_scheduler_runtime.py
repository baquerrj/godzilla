"""Scheduler runtime tests.

REQ: ACC-ACCT-006, TECH-ACCT-006-RUNTIME, ACC-BKP-005
"""

from __future__ import annotations

import unittest

from godzilla_core.scheduler.runtime import JobCoordinator, LocalSchedulerRuntime, SchedulerPlan


class JobCoordinatorTests(unittest.TestCase):
    """Unit tests for single-flight scheduling locks.

    REQ: ACC-ACCT-006, TECH-ACCT-006-RUNTIME, ACC-BKP-005
    """

    def test_run_exclusive_blocks_reentrant_execution(self) -> None:
        """A second caller cannot enter the same job while it already holds the lock.

        REQ: ACC-ACCT-006, TECH-ACCT-006-RUNTIME
        """

        coordinator = JobCoordinator()

        def nested_call() -> tuple[bool, object | None]:
            return coordinator.run_exclusive("sync", lambda: "nested")

        def outer_call() -> tuple[bool, object | None]:
            return nested_call()

        ran, nested_result = coordinator.run_exclusive("sync", outer_call)
        self.assertTrue(ran)
        self.assertEqual(nested_result, (False, None))


class LocalSchedulerRuntimeTests(unittest.TestCase):
    """Unit tests for the in-process recurring scheduler state machine.

    REQ: ACC-ACCT-006, TECH-ACCT-006-RUNTIME, ACC-BKP-005
    """

    def test_sync_plan_state_recomputes_next_due_times(self) -> None:
        """Plan changes recalculate which recurring jobs are eligible.

        REQ: ACC-ACCT-006, ACC-BKP-005
        """

        state = {
            "plan": SchedulerPlan(
                sync_enabled=True,
                sync_frequency_minutes=0,
                backup_enabled=False,
                backup_frequency_minutes=0,
            )
        }
        runtime = LocalSchedulerRuntime(
            load_plan=lambda: state["plan"],
            run_sync_job=lambda: None,
            run_backup_job=lambda: None,
            poll_seconds=0.01,
        )
        runtime._sync_plan_state()
        self.assertIsNotNone(runtime._next_sync_at)
        self.assertIsNone(runtime._next_backup_at)

        state["plan"] = SchedulerPlan(
            sync_enabled=False,
            sync_frequency_minutes=0,
            backup_enabled=True,
            backup_frequency_minutes=0,
        )
        runtime._sync_plan_state()
        self.assertIsNone(runtime._next_sync_at)
        self.assertIsNotNone(runtime._next_backup_at)
