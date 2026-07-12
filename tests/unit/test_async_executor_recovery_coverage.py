"""Coverage tests for opc_manager.async_executor_recovery.RecoveryMixin

Tests zombie-task scanning and retry processing.
"""

import threading
import time
from unittest.mock import MagicMock


from opc_manager.async_executor import AsyncTask, TaskStatus
from opc_manager.async_executor_recovery import RecoveryMixin


class FakeExecutor(RecoveryMixin):
    """Minimal facade supplying cross-mixin attributes."""

    def __init__(self, tasks=None, default_timeout=60, zombie_check_interval=1.0):
        self._tasks = tasks if tasks is not None else {}
        self._lock = threading.RLock()
        self._shutdown = False
        self._shutdown_event = threading.Event()
        self.default_timeout = default_timeout
        self.zombie_check_interval = zombie_check_interval
        self._schedule_retry = MagicMock()
        self._run_worker = MagicMock()
        self._default_execute = MagicMock()


class TestScanZombies:
    def test_no_tasks_no_action(self):
        executor = FakeExecutor()
        executor._scan_zombies()
        executor._schedule_retry.assert_not_called()

    def test_pending_task_within_timeout_not_marked(self):
        task = AsyncTask("t1", "p", status=TaskStatus.PENDING)
        executor = FakeExecutor(tasks={"t1": task}, default_timeout=60)
        executor._scan_zombies()
        assert task.status == TaskStatus.PENDING
        executor._schedule_retry.assert_not_called()

    def test_pending_task_beyond_timeout_marked_failed(self):
        task = AsyncTask(
            "t1", "p", status=TaskStatus.PENDING, created_at=time.time() - 120
        )
        executor = FakeExecutor(tasks={"t1": task}, default_timeout=60)
        executor._scan_zombies()
        assert task.status == TaskStatus.FAILED
        assert "Zombie scan: PENDING" in task.error_message
        assert task.completed_at is not None
        executor._schedule_retry.assert_called_once_with(task)

    def test_running_task_within_timeout_not_marked(self):
        task = AsyncTask("t1", "p", status=TaskStatus.RUNNING, started_at=time.time())
        executor = FakeExecutor(tasks={"t1": task}, default_timeout=60)
        executor._scan_zombies()
        assert task.status == TaskStatus.RUNNING

    def test_running_task_beyond_timeout_marked_failed(self):
        task = AsyncTask(
            "t1", "p", status=TaskStatus.RUNNING, started_at=time.time() - 120
        )
        executor = FakeExecutor(tasks={"t1": task}, default_timeout=60)
        executor._scan_zombies()
        assert task.status == TaskStatus.FAILED
        assert "Zombie scan: RUNNING" in task.error_message
        executor._schedule_retry.assert_called_once()

    def test_running_task_no_started_at_skipped(self):
        task = AsyncTask("t1", "p", status=TaskStatus.RUNNING, started_at=None)
        executor = FakeExecutor(tasks={"t1": task}, default_timeout=60)
        executor._scan_zombies()
        assert task.status == TaskStatus.RUNNING
        executor._schedule_retry.assert_not_called()

    def test_completed_task_skipped(self):
        task = AsyncTask("t1", "p", status=TaskStatus.DONE)
        executor = FakeExecutor(tasks={"t1": task}, default_timeout=0)
        executor._scan_zombies()
        assert task.status == TaskStatus.DONE

    def test_failed_task_skipped(self):
        task = AsyncTask("t1", "p", status=TaskStatus.FAILED)
        executor = FakeExecutor(tasks={"t1": task}, default_timeout=0)
        executor._scan_zombies()
        executor._schedule_retry.assert_not_called()

    def test_multiple_zombies_all_marked(self):
        t1 = AsyncTask(
            "t1", "p", status=TaskStatus.PENDING, created_at=time.time() - 200
        )
        t2 = AsyncTask(
            "t2", "p", status=TaskStatus.RUNNING, started_at=time.time() - 200
        )
        executor = FakeExecutor(tasks={"t1": t1, "t2": t2}, default_timeout=60)
        executor._scan_zombies()
        assert t1.status == TaskStatus.FAILED
        assert t2.status == TaskStatus.FAILED
        assert executor._schedule_retry.call_count == 2


class TestProcessRetries:
    def test_no_tasks_no_action(self):
        executor = FakeExecutor()
        executor._process_retries()
        # No threads started
        assert len(executor._tasks) == 0

    def test_retrying_task_not_ready_skipped(self):
        task = AsyncTask(
            "t1", "p", status=TaskStatus.RETRYING, next_retry_at=time.time() + 100
        )
        executor = FakeExecutor(tasks={"t1": task})
        executor._process_retries()
        assert task.status == TaskStatus.RETRYING

    def test_retrying_task_ready_relaunched(self):
        task = AsyncTask(
            "t1", "p", status=TaskStatus.RETRYING, next_retry_at=time.time() - 1
        )
        task.execute_func = MagicMock()
        executor = FakeExecutor(tasks={"t1": task})
        executor._process_retries()
        assert task.status == TaskStatus.PENDING
        assert task.next_retry_at is None
        assert task.thread_ref is not None
        # Give thread a moment to start
        time.sleep(0.05)

    def test_retrying_task_no_next_retry_at_skipped(self):
        task = AsyncTask("t1", "p", status=TaskStatus.RETRYING, next_retry_at=None)
        executor = FakeExecutor(tasks={"t1": task})
        executor._process_retries()
        assert task.status == TaskStatus.RETRYING

    def test_non_retrying_task_skipped(self):
        task = AsyncTask("t1", "p", status=TaskStatus.PENDING)
        executor = FakeExecutor(tasks={"t1": task})
        executor._process_retries()
        assert task.status == TaskStatus.PENDING

    def test_uses_default_execute_when_no_execute_func(self):
        task = AsyncTask(
            "t1",
            "p",
            status=TaskStatus.RETRYING,
            next_retry_at=time.time() - 1,
        )
        task.execute_func = None
        executor = FakeExecutor(tasks={"t1": task})
        executor._process_retries()
        assert task.status == TaskStatus.PENDING
        time.sleep(0.05)


class TestZombieScanLoop:
    def test_loop_exits_on_shutdown(self):
        executor = FakeExecutor(zombie_check_interval=0.01)
        # Set shutdown before loop starts, so it exits immediately
        executor._shutdown = True
        executor._shutdown_event.set()
        # Should return quickly without blocking
        executor._zombie_scan_loop()

    def test_loop_processes_then_exits(self):
        executor = FakeExecutor(zombie_check_interval=0.01)
        task = AsyncTask(
            "t1",
            "p",
            status=TaskStatus.PENDING,
            created_at=time.time() - 200,
        )
        executor._tasks["t1"] = task

        # Run loop in a thread, shut it down after a short time
        def run_and_shutdown():
            time.sleep(0.05)
            executor._shutdown = True
            executor._shutdown_event.set()

        shutdown_thread = threading.Thread(target=run_and_shutdown)
        shutdown_thread.start()
        executor._zombie_scan_loop()
        shutdown_thread.join()
        # Task should have been scanned and marked
        assert task.status == TaskStatus.FAILED

    def test_loop_catches_exceptions_and_continues(self):
        executor = FakeExecutor(zombie_check_interval=0.01)

        # Make _scan_zombies raise on first call
        call_count = [0]

        def failing_scan():
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("scan error")
            # Second call: shut down
            executor._shutdown = True
            executor._shutdown_event.set()

        executor._scan_zombies = failing_scan
        executor._process_retries = MagicMock()
        executor._zombie_scan_loop()
        # Loop should have continued past the first exception
        assert call_count[0] >= 2
