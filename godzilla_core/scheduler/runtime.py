"""In-process recurring job runtime for sync and backup orchestration.

REQ: ACC-ACCT-006, TECH-ACCT-006-RUNTIME, ACC-BKP-005
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SchedulerPlan:
    """Current persisted scheduling configuration.

    REQ: ACC-ACCT-006, ACC-BKP-005
    """

    sync_enabled: bool
    sync_frequency_minutes: int
    backup_enabled: bool
    backup_frequency_minutes: int


class JobCoordinator:
    """Single-flight coordinator shared by manual and scheduled jobs.

    REQ: ACC-ACCT-006, TECH-ACCT-006-RUNTIME, ACC-BKP-005
    """

    def __init__(self) -> None:
        """Initialize single-flight locks for each supported job type."""
        self._locks = {
            "sync": threading.Lock(),
            "backup": threading.Lock(),
        }

    def run_exclusive(self, job_type: str, fn: Callable[[], object]) -> tuple[bool, object | None]:
        """Run a callback only when the named job lock is available.

        REQ: ACC-ACCT-006, ACC-BKP-005
        """
        lock = self._locks[job_type]
        if not lock.acquire(blocking=False):
            return False, None
        try:
            return True, fn()
        finally:
            lock.release()


class LocalSchedulerRuntime:
    """Minimal recurring scheduler for desktop-side background work.

    REQ: ACC-ACCT-006, TECH-ACCT-006-RUNTIME, ACC-BKP-005
    """

    def __init__(
        self,
        *,
        load_plan: Callable[[], SchedulerPlan],
        run_sync_job: Callable[[], None],
        run_backup_job: Callable[[], None],
        poll_seconds: float = 1.0,
    ) -> None:
        """Initialize the scheduler with persisted plan loading and job callbacks."""
        self._load_plan = load_plan
        self._run_sync_job = run_sync_job
        self._run_backup_job = run_backup_job
        self._poll_seconds = poll_seconds
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._state_lock = threading.Lock()
        self._cached_plan: SchedulerPlan | None = None
        self._next_sync_at: datetime | None = None
        self._next_backup_at: datetime | None = None

    def start(self) -> None:
        """Start the background scheduler thread.

        REQ: ACC-ACCT-006, ACC-BKP-005
        """
        with self._state_lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._wake_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop, daemon=True, name="godzilla-scheduler"
            )
            self._thread.start()

    def stop(self) -> None:
        """Stop the background scheduler thread.

        REQ: ACC-ACCT-006, ACC-BKP-005
        """
        self._stop_event.set()
        self._wake_event.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=5)

    def reload(self) -> None:
        """Wake the background loop after settings changes.

        REQ: ACC-ACCT-006, ACC-BKP-005
        """
        self._wake_event.set()

    def _run_loop(self) -> None:
        """Background loop that checks persisted plan state and runs due jobs.

        REQ: ACC-ACCT-006, ACC-BKP-005
        """
        while not self._stop_event.is_set():
            self._sync_plan_state()
            now = datetime.now(timezone.utc)
            if self._next_sync_at and now >= self._next_sync_at:
                self._run_sync_job()
                self._next_sync_at = now + timedelta(
                    minutes=max(self._cached_plan.sync_frequency_minutes, 5)
                )
            if self._next_backup_at and now >= self._next_backup_at:
                self._run_backup_job()
                self._next_backup_at = now + timedelta(
                    minutes=max(self._cached_plan.backup_frequency_minutes, 5)
                )
            self._wake_event.wait(timeout=self._poll_seconds)
            self._wake_event.clear()

    def _sync_plan_state(self) -> None:
        plan = self._load_plan()
        now = datetime.now(timezone.utc)
        if plan != self._cached_plan:
            logger.info(
                "scheduler_plan_updated",
                extra={"sync": plan.sync_enabled, "backup": plan.backup_enabled},
            )
            self._cached_plan = plan
            self._next_sync_at = (
                now + timedelta(minutes=max(plan.sync_frequency_minutes, 5))
                if plan.sync_enabled
                else None
            )
            self._next_backup_at = (
                now + timedelta(minutes=max(plan.backup_frequency_minutes, 5))
                if plan.backup_enabled
                else None
            )
            return
        if not plan.sync_enabled:
            self._next_sync_at = None
        if not plan.backup_enabled:
            self._next_backup_at = None
