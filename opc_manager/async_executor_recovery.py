"""
Recovery Mixin for AsyncTaskExecutor

Extracted from async_executor.py to reduce the God Class size.
Contains the zombie-task scan and retry-processing logic:
- _zombie_scan_loop: background loop that periodically scans for zombies
- _scan_zombies: mark PENDING/RUNNING tasks stuck beyond timeout as FAILED
  and schedule retries
- _process_retries: relaunch tasks whose scheduled retry time has arrived

=== Design Notes ===
Implemented as a mixin class to preserve all method signatures.
AsyncTaskExecutor inherits from this mixin, so all external callers see no
change. Cross-mixin dependencies are resolved at runtime via the composed
facade instance:
- self._tasks / self._lock / self._shutdown / self._shutdown_event
  / self.zombie_check_interval / self.default_timeout (facade — set by __init__)
- self._scan_zombies / self._process_retries (provided by this mixin)
- self._schedule_retry / self._run_worker / self._default_execute
  (provided by WorkerMixin)

TaskStatus is imported from the facade module; the facade defines it before
importing the mixins to keep the import cycle safe (see async_executor.py).
"""

import threading
import time
import logging

from .async_executor import TaskStatus

logger = logging.getLogger(__name__)


class RecoveryMixin:
    """Mixin class containing the zombie-task scan and retry-processing
    logic for AsyncTaskExecutor.

    Cross-mixin calls (e.g. self._schedule_retry, self._run_worker) are
    resolved at runtime on the composed facade instance via Python's MRO.
    """

    def _zombie_scan_loop(self):
        """Background loop that periodically scans for zombie tasks

        Zombie tasks are tasks stuck in PENDING or RUNNING state beyond timeout.
        This is a safety net in case get_status() is not called frequently enough.
        """
        while not self._shutdown:
            # Use Event.wait so shutdown() can wake the loop immediately
            # instead of waiting out the full sleep interval.
            self._shutdown_event.wait(timeout=self.zombie_check_interval)
            if self._shutdown:
                break
            try:
                self._scan_zombies()
                self._process_retries()
            except Exception as e:
                logger.error("[AsyncTaskExecutor] Zombie scan error: %s", e)

    def _scan_zombies(self):
        now = time.time()
        retry_candidates = []
        with self._lock:
            for task in self._tasks.values():
                elapsed = now - task.created_at
                if task.status == TaskStatus.PENDING and elapsed > self.default_timeout:
                    task.status = TaskStatus.FAILED
                    task.completed_at = now
                    task.error_message = f"Zombie scan: PENDING for {elapsed:.0f}s"
                    logger.warning(
                        "[AsyncTaskExecutor] Zombie PENDING: %s", task.task_id
                    )
                    retry_candidates.append(task)

                elif task.status == TaskStatus.RUNNING:
                    if task.started_at is not None:
                        running_elapsed = now - task.started_at
                        if running_elapsed > self.default_timeout:
                            task.status = TaskStatus.FAILED
                            task.completed_at = now
                            task.error_message = (
                                f"Zombie scan: RUNNING for {running_elapsed:.0f}s"
                            )
                            logger.warning(
                                "[AsyncTaskExecutor] Zombie RUNNING: %s", task.task_id
                            )
                            retry_candidates.append(task)

        for task in retry_candidates:
            self._schedule_retry(task)

    def _process_retries(self):
        now = time.time()
        to_retry = []
        with self._lock:
            for task in list(self._tasks.values()):
                if (
                    task.status == TaskStatus.RETRYING
                    and task.next_retry_at
                    and now >= task.next_retry_at
                ):
                    task.status = TaskStatus.PENDING
                    task.next_retry_at = None
                    to_retry.append(task)

        for task in to_retry:
            thread = threading.Thread(
                target=self._run_worker,
                args=(task.task_id, task.execute_func or self._default_execute),
                daemon=True,
            )
            task.thread_ref = thread
            thread.start()
            logger.info("[AsyncTaskExecutor] Retry triggered: %s", task.task_id)
