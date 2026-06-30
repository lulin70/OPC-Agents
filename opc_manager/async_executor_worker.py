"""
Worker Mixin for AsyncTaskExecutor

Extracted from async_executor.py to reduce the God Class size.
Contains the task-execution worker logic:
- _run_worker: background worker thread that executes a task end-to-end
  (status transitions, cancel checks, result handling, exception catch)
- _default_execute: default execute_func calling TaskEngineV3 + save callback
- _cleanup_old_tasks: trim completed task records to control memory usage
- _schedule_retry: schedule an exponential-backoff retry for a failed task

=== Design Notes ===
Implemented as a mixin class to preserve all method signatures.
AsyncTaskExecutor inherits from this mixin, so all external callers see no
change. Cross-mixin dependencies are resolved at runtime via the composed
facade instance:
- self._tasks / self._lock / self._shutdown (facade — set by __init__)
- self.max_concurrent / self.max_history / self.retry_backoff_base
  / self._save_callback (facade — set by __init__)
- self._run_worker / self._default_execute / self._schedule_retry
  (provided by this mixin; also called by RecoveryMixin / PersistenceMixin)

TaskStatus and AsyncTask are imported from the facade module; the facade
defines them before importing the mixins to keep the import cycle safe
(see async_executor.py).
"""

from __future__ import annotations

import threading
import time
import logging
from typing import Callable, Dict, Optional

from .async_executor import AsyncTask, TaskStatus

logger = logging.getLogger(__name__)


class WorkerMixin:
    """Mixin class containing the task-execution worker logic for
    AsyncTaskExecutor.

    Cross-mixin calls (e.g. self._schedule_retry) are resolved at runtime on
    the composed facade instance via Python's MRO.
    """

    # 类型声明（由 facade AsyncTaskExecutor.__init__ 设置，mixin 模式下需显式声明供 mypy 识别）
    _lock: threading.RLock
    _tasks: Dict[str, AsyncTask]
    _save_callback: Optional[Callable]
    max_concurrent: int
    max_history: int
    retry_backoff_base: float

    def _run_worker(self, task_id: str, execute_func: Callable, **kwargs):
        """Background worker thread: execute actual task

        Execution flow:
        1. Check cancel flag (if already cancelled, exit immediately)
        2. Update status to RUNNING
        3. Call execute_func(prompt, cancel_event, **kwargs)
        4. Update task status and result based on return value
        5. Exception catching: any exception is marked as FAILED rather than crashing

        Thread safety:
        - All modifications to task fields are done within lock
        - cancel_event serves as inter-thread communication mechanism
        - Even if execute_func throws an exception, it won't affect other tasks
        """
        with self._lock:
            task = self._tasks.get(task_id)

        if not task:
            logger.error(
                "[AsyncTaskExecutor] Worker startup failed: task %s not found", task_id
            )
            return

        if task.cancel_event.is_set():
            with self._lock:
                task.status = TaskStatus.CANCELLED
                task.completed_at = time.time()
            return

        try:
            with self._lock:
                if task.cancel_event.is_set():
                    task.status = TaskStatus.CANCELLED
                    task.completed_at = time.time()
                    return
                task.status = TaskStatus.RUNNING
                task.started_at = time.time()

            logger.info("[AsyncTaskExecutor] Started execution: %s", task_id)

            if task.cancel_event.is_set():
                with self._lock:
                    task.status = TaskStatus.CANCELLED
                    task.completed_at = time.time()
                logger.info(
                    "[AsyncTaskExecutor] Task cancelled before execution: %s", task_id
                )
                return

            result = execute_func(
                prompt=task.prompt, cancel_event=task.cancel_event, **kwargs
            )

            if task.cancel_event.is_set():
                with self._lock:
                    task.status = TaskStatus.CANCELLED
                    task.completed_at = time.time()
                logger.info("[AsyncTaskExecutor] Task cancelled: %s", task_id)
                return

            if isinstance(result, dict):
                with self._lock:
                    if task.cancel_event.is_set():
                        task.status = TaskStatus.CANCELLED
                        task.completed_at = time.time()
                        logger.info(
                            "[AsyncTaskExecutor] Task cancelled after completion: %s",
                            task_id,
                        )
                        return
                    is_success = result.get("success", True)
                    task.status = TaskStatus.DONE if is_success else TaskStatus.FAILED
                    task.completed_at = time.time()
                    task.result_content = result.get("content")
                    task.result_success = is_success
                    task.result_filepath = result.get("filepath")
                    task.result_task_type = result.get("task_type")
                    task.result_deliverable_record = result.get("deliverable_record")
                    task.result_exportable_formats = result.get("_exportable_formats")
                    task.error_message = result.get("error", "")
            elif isinstance(result, tuple) and len(result) >= 2:
                with self._lock:
                    is_success = result[1]
                    task.status = TaskStatus.DONE if is_success else TaskStatus.FAILED
                    task.completed_at = time.time()
                    task.result_content = result[0]
                    task.result_success = is_success
                    if len(result) >= 3:
                        task.result_filepath = result[2]
                    if len(result) >= 4:
                        task.result_task_type = result[3]
            else:
                with self._lock:
                    task.status = TaskStatus.DONE
                    task.completed_at = time.time()
                    task.result_content = str(result) if result else ""
                    task.result_success = True

            elapsed = (task.completed_at or time.time()) - (
                task.started_at or task.created_at
            )
            logger.info(
                f"[AsyncTaskExecutor] Execution complete: {task_id} "
                f"(duration: {elapsed:.1f}s, success: {task.result_success})"
            )

        except InterruptedError:
            with self._lock:
                task.status = TaskStatus.CANCELLED
                task.completed_at = time.time()
            logger.info(
                "[AsyncTaskExecutor] Task interrupted and cancelled: %s", task_id
            )

        except Exception as e:
            with self._lock:
                task.status = TaskStatus.FAILED
                task.completed_at = time.time()
                task.error_message = str(e)
                task.last_error = str(e)

            self._schedule_retry(task)

            logger.error(
                f"[AsyncTaskExecutor] Execution failed: {task_id} -> {e}",
                exc_info=True,
            )

    def _default_execute(self, prompt: str, cancel_event: threading.Event) -> Dict:
        """Default execution function: calls TaskEngineV3 + save_deliverable

        This is a sample implementation showing how to integrate with existing systems.
        In practice, you can pass a custom function via submit(execute_func=custom_func).

        Args:
            prompt: User input
            cancel_event: Cancel event (for checking if cancelled)

        Returns:
            Result dict: {content, success, filepath, task_type}
        """
        from opc_manager.task_engine_v3 import task_engine_v3

        result = task_engine_v3.execute(prompt)

        filepath = None
        if result.success and result.content and self._save_callback:
            try:
                filepath = self._save_callback(
                    result.content,
                    prompt,
                    result.task_type.value if result.task_type else "general",
                )
            except Exception as e:
                logger.warning("[AsyncTaskExecutor] save_callback failed: %s", e)

        return {
            "content": result.content,
            "success": result.success,
            "filepath": filepath,
            "task_type": result.task_type.value if result.task_type else None,
            "sources": result.sources,
        }

    def _cleanup_old_tasks(self):
        """Cleanup old task records to control memory usage

        Cleanup strategy:
        1. Keep all active tasks (pending/running)
        2. Keep most recent N completed tasks (for user history viewing)
        3. Delete earlier completed/failed/cancelled tasks
        """
        if len(self._tasks) <= self.max_history:
            return

        completed_tasks = [
            (tid, t)
            for tid, t in self._tasks.items()
            if t.status in [TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED]
        ]

        completed_tasks.sort(key=lambda x: x[1].completed_at or 0, reverse=True)

        keep_recent = completed_tasks[: self.max_history // 2]
        to_remove = set(tid for tid, _ in completed_tasks) - set(
            tid for tid, _ in keep_recent
        )

        for tid in to_remove:
            del self._tasks[tid]

        if to_remove:
            logger.debug(
                "[AsyncTaskExecutor] Cleaned up %s old task records", len(to_remove)
            )

    def _schedule_retry(self, task: AsyncTask):
        if task.cancel_event.is_set():
            return

        with self._lock:
            if task.retry_count >= task.max_retries:
                logger.info(
                    f"[AsyncTaskExecutor] No more retries for {task.task_id} "
                    f"({task.retry_count}/{task.max_retries})"
                )
                return

            if task.status == TaskStatus.RETRYING:
                logger.debug(
                    f"[AsyncTaskExecutor] Retry already scheduled for {task.task_id}, skipping duplicate"
                )
                return

            task.retry_count += 1
            delay = self.retry_backoff_base * (2 ** (task.retry_count - 1))
            task.status = TaskStatus.RETRYING
            task.next_retry_at = time.time() + delay

        logger.info(
            f"[AsyncTaskExecutor] Retry {task.retry_count}/{task.max_retries} "
            f"scheduled for {task.task_id} in {delay:.0f}s"
        )

        def _do_retry():
            time.sleep(delay)
            if self._shutdown or task.cancel_event.is_set():
                return
            with self._lock:
                if task.status != TaskStatus.RETRYING:
                    return
                running_count = sum(
                    1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING
                )
                if running_count >= self.max_concurrent:
                    task.status = TaskStatus.PENDING
                    task.completed_at = None
                    task.error_message = None
                    logger.info(
                        "[AsyncTaskExecutor] Retry deferred for %s: concurrency limit reached (%d/%d)",
                        task.task_id,
                        running_count,
                        self.max_concurrent,
                    )
                    return
                task.status = TaskStatus.PENDING
                task.completed_at = None
                task.error_message = None
                task.created_at = time.time()
                task.started_at = None

            thread = threading.Thread(
                target=self._run_worker,
                args=(task.task_id, task.execute_func or self._default_execute),
                daemon=True,
            )
            task.thread_ref = thread
            thread.start()
            logger.info("[AsyncTaskExecutor] Retry executing: %s", task.task_id)

        retry_thread = threading.Thread(target=_do_retry, daemon=True)
        retry_thread.start()
