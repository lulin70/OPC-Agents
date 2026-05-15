"""
Async Task Executor v3.6 — P0-3 Failure Recovery Enhancement

Core problem solved:
- User waits 5-10 seconds after input, Streamlit synchronous blocking causes timeout crash
- "Is it still processing? Is it frozen?" — Extremely poor user experience
- Tasks stuck in RUNNING/PENDING forever with no recovery — production reliability risk

=== Design Decision (ADR-010) ===
Decision: Keep Streamlit, switch to async execution + polling pattern (minimal change approach)
Reasons:
  1. No new framework risk (FastAPI/Gradio learning cost)
  2. Reuse existing TaskEngineV3 logic
  3. Minimal frontend changes (submit→poll→display three steps)

=== Core Architecture ===
  User input → submit(prompt) → immediately return task_id (<1ms)
    ↓ (background thread)
  TaskEngineV3.execute() + save_deliverable()
    ↓ (complete)
  Update task status to done → frontend polls and discovers → display result

=== Failure Recovery (v3.6) ===
  1. Auto-retry: Failed tasks auto-retry up to max_retries (exponential backoff)
  2. Running timeout: RUNNING tasks exceeding timeout auto-marked as FAILED
  3. Zombie cleanup: Periodic scan for stuck PENDING/RUNNING tasks
  4. State persistence: Task states saved to JSON for crash recovery
  5. Graceful shutdown: On shutdown, save all active task states

=== Data Flow ===
  submit() → _tasks[task_id] = {status:'pending', ...}
    → threading.Thread(target=_run_worker)
      → status: 'running'
      → engine.execute()
        → status: 'done' / 'failed' → retry if retries left → 'done' / 'failed'

=== Performance Metrics ===
  - submit() latency: < 10ms (only create dict + start thread)
  - get_status() latency: < 1ms (only read dict)
  - Concurrency support: Default max 5 simultaneously running tasks
  - Memory usage: ~1KB metadata per task

=== Version History ===
  v3.6.0: Failure recovery — auto-retry, running timeout, zombie cleanup, state persistence
  v3.5.0: Initial version, supports submit/poll/cancel/timeout auto-cleanup
"""

import json
import hashlib
import os
import threading
import time
import uuid
import logging
from typing import Dict, Optional, Any, Callable, List
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task status enum

    State transitions:
    pending → running → done/failed/cancelled
    failed → retrying → running (if retries remain)
    """

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass
class AsyncTask:
    """Async task data container

    Design intent:
    - Lightweight data structure to avoid serialization overhead
    - Contains complete status info and result data
    - Supports thread-safe read/write (protected by executor lock)
    - Tracks retry count and next retry time for failure recovery
    """

    task_id: str
    prompt: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result_content: Optional[str] = None
    result_success: bool = False
    result_filepath: Optional[str] = None
    result_task_type: Optional[str] = None
    result_deliverable_record: Optional[dict] = None
    result_exportable_formats: Optional[list] = None
    error_message: Optional[str] = None
    thread_ref: Optional[threading.Thread] = None
    execute_func: Optional[Any] = None
    cancel_event: Optional[threading.Event] = field(default_factory=threading.Event)
    retry_count: int = 0
    max_retries: int = 2
    next_retry_at: Optional[float] = None
    last_error: Optional[str] = None


class AsyncTaskExecutor:
    """Async Task Executor — Solves Streamlit timeout crash issue

    Core capabilities:
    1. Instant submit: submit() returns task_id immediately, doesn't block frontend
    2. Background execution: Calls TaskEngineV3 in separate thread
    3. Status polling: get_status() non-blocking query progress
    4. Task cancellation: cancel() gracefully terminates background thread
    5. Auto cleanup: Timed-out tasks auto-marked as failed and resources released

    Usage example:
        >>> executor = AsyncTaskExecutor(max_concurrent=3, default_timeout=120)
        >>> task_id = executor.submit("帮我写Q2营销方案")
        >>> print(f"Submitted: {task_id}")
        >>>
        >>> import time
        >>> while True:
        ...     status = executor.get_status(task_id)
        ...     if status['status'] in ['done', 'failed', 'cancelled']:
        ...         break
        ...     time.sleep(1)
        ...     print(f"Processing... ({status.get('elapsed',0):.1f}s)")
        >>>
        >>> if status['status'] == 'done':
        ...     print(status['result_content'][:100])

    Thread safety:
    - All public methods are thread-safe
    - Internal use of threading.Lock protects shared state
    - Cancellation via threading.Event

    Degradation strategy:
    - Background thread exception → auto-mark as FAILED, no main thread crash
    - Timeout not completed → auto-mark as FAILED, release resources
    - Concurrency limit reached → submit() returns None (caller should prompt user to retry later)
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        default_timeout: int = 120,
        max_history: int = 50,
        save_callback=None,
        max_retries: int = 2,
        retry_backoff_base: float = 5.0,
        zombie_check_interval: int = 30,
        persist_dir: Optional[str] = None,
    ):
        """Initialize async executor

        Args:
            max_concurrent: Maximum simultaneously running tasks (prevents resource exhaustion)
            default_timeout: Default timeout (seconds), auto-marked as failed after this time
            max_history: Maximum retained historical tasks (oldest cleaned up when exceeded)
            save_callback: Deliverable save callback, signature: (content, prompt, task_type) -> filepath
            max_retries: Maximum retry attempts for failed tasks (0=no retry, 2=retry twice)
            retry_backoff_base: Base delay for exponential backoff (seconds), actual = base * 2^retry_count
            zombie_check_interval: Interval for zombie task scan (seconds)
            persist_dir: Directory for task state persistence (None=disabled)
        """
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        self.max_history = max_history
        self._save_callback = save_callback
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base
        self.zombie_check_interval = zombie_check_interval
        self.persist_dir = persist_dir

        self._tasks: Dict[str, AsyncTask] = {}
        self._lock = threading.RLock()
        self._shutdown = False

        self._load_persisted_tasks()

        self._zombie_timer = threading.Thread(
            target=self._zombie_scan_loop, daemon=True
        )
        self._zombie_timer.start()

        logger.info(
            f"[AsyncTaskExecutor] Initialized: "
            f"max_concurrent={max_concurrent}, timeout={default_timeout}s, "
            f"max_retries={max_retries}, persist={'on' if persist_dir else 'off'}"
        )

    def submit(
        self, prompt: str, execute_func: Optional[Callable] = None, **execute_kwargs
    ) -> Optional[str]:
        """Submit task, immediately return task_id (non-blocking)

        This is the core "non-blocking submit" interface:
        - Create task record (<1ms)
        - Start background thread (<5ms)
        - Return task_id for subsequent polling

        Args:
            prompt: User's original input text
            execute_func: Optional custom execution function (defaults to built-in _default_execute)
            **execute_kwargs: Additional arguments passed to execute_func

        Returns:
            task_id: UUID-format task ID on success
            None: When concurrency limit reached or invalid parameters
        """
        if not prompt or not prompt.strip():
            logger.warning("[AsyncTaskExecutor] Empty prompt submitted")
            return None

        with self._lock:
            running_count = sum(
                1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING
            )

            if running_count >= self.max_concurrent:
                logger.warning(
                    f"[AsyncTaskExecutor] Concurrency limit ({self.max_concurrent}) reached, rejecting new task"
                )
                return None

            task_id = f"task-{uuid.uuid4().hex[:12]}"

            task = AsyncTask(
                task_id=task_id,
                prompt=prompt.strip(),
                status=TaskStatus.PENDING,
                max_retries=self.max_retries,
            )

            self._tasks[task_id] = task
            self._cleanup_old_tasks()

        execute_func = execute_func or self._default_execute
        task.execute_func = execute_func

        thread = threading.Thread(
            target=self._run_worker,
            args=(task_id, execute_func),
            kwargs=execute_kwargs,
            daemon=True,
        )
        task.thread_ref = thread
        thread.start()

        logger.info(
            f"[AsyncTaskExecutor] Task submitted: {task_id} "
            f"(current concurrency: {running_count + 1}/{self.max_concurrent})"
        )

        return task_id

    def get_status(self, task_id: str) -> Dict[str, Any]:
        """Polling interface: return task status and result info

        Non-blocking design:
        - Only reads in-memory task status (<1ms latency)
        - Does not trigger any computation or I/O operations
        - Returns complete serializable dict for frontend use

        Args:
            task_id: Task ID returned by submit()

        Returns:
            Status dict containing the following fields:
            - status: Current status ('pending'/'running'/'done'/'failed'/'cancelled')
            - elapsed: Elapsed time (seconds)
            - result_content: Content text when completed (only for 'done' status)
            - result_success: Whether successful
            - result_filepath: Generated file path (if any)
            - result_task_type: Task type (if any)
            - error_message: Error info (only for 'failed' status)
            - exists: Whether task ID exists
        """
        with self._lock:
            task = self._tasks.get(task_id)

            if not task:
                return {
                    "status": "not_found",
                    "elapsed": 0,
                    "exists": False,
                }

            elapsed = time.time() - task.created_at

            if task.status == TaskStatus.PENDING and elapsed > self.default_timeout:
                task.status = TaskStatus.FAILED
                task.completed_at = time.time()
                task.error_message = f"Task stuck in PENDING for {elapsed:.0f}s (timeout: {self.default_timeout}s)"
                logger.warning("[AsyncTaskExecutor] PENDING timeout: %s", task_id)
                self._schedule_retry(task)

            if task.status == TaskStatus.RUNNING:
                if task.started_at is not None:
                    running_elapsed = time.time() - task.started_at
                    if running_elapsed > self.default_timeout:
                        task.status = TaskStatus.FAILED
                        task.completed_at = time.time()
                        task.error_message = f"Task RUNNING for {running_elapsed:.0f}s (timeout: {self.default_timeout}s)"
                        logger.warning("[AsyncTaskExecutor] RUNNING timeout: %s", task_id)
                        self._schedule_retry(task)

            return {
                "status": task.status.value,
                "elapsed": elapsed,
                "result_content": task.result_content,
                "result_success": task.result_success,
                "result_filepath": task.result_filepath,
                "result_task_type": task.result_task_type,
                "result_deliverable_record": task.result_deliverable_record,
                "_exportable_formats": task.result_exportable_formats,
                "error_message": task.error_message,
                "exists": True,
                "created_at": task.created_at,
                "retry_count": task.retry_count,
                "max_retries": task.max_retries,
                "last_error": task.last_error,
            }

    def cancel(self, task_id: str) -> bool:
        """Cancel a running task

        Cancellation mechanism:
        1. Set cancel_event flag
        2. Background thread checks this flag at safe points and exits
        3. If task is already completed/non-existent, returns False

        Args:
            task_id: Task ID to cancel

        Returns:
            bool: Whether cancellation was successfully initiated

        Note:
            - cancel() is asynchronous, after calling you need to wait for get_status() to confirm status becomes cancelled
            - For long-running search/LLM calls, it may take a few seconds to respond to cancellation
        """
        with self._lock:
            task = self._tasks.get(task_id)

            if not task:
                logger.warning("[AsyncTaskExecutor] Cancel failed: task %s not found", task_id)
                return False

            if task.status not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                logger.info(
                    f"[AsyncTaskExecutor] Cancel skipped: task {task_id} status is {task.status.value}"
                )
                return False

            task.cancel_event.set()
            task.status = TaskStatus.CANCELLED
            task.completed_at = time.time()
            task.last_error = f"Cancelled at {time.strftime('%Y-%m-%dT%H:%M:%S')}"

        logger.info("[AsyncTaskExecutor] Cancel signal sent: %s", task_id)

        return True

    def list_active_tasks(self) -> List[Dict[str, Any]]:
        """List all active tasks (pending + running)

        Used for management interface to display current load.

        Returns:
            Active task list, each element contains task_id/status/prompt/elapsed
        """
        with self._lock:
            active = []
            for task in self._tasks.values():
                if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.RETRYING]:
                    active.append(
                        {
                            "task_id": task.task_id,
                            "status": task.status.value,
                            "prompt": task.prompt[:50]
                            + ("..." if len(task.prompt) > 50 else ""),
                            "elapsed": time.time() - task.created_at,
                        }
                    )
            return active

    def cleanup(self, task_id: str) -> bool:
        """Manually cleanup completed task record (release memory)

        Usually no need to call manually, _cleanup_old_tasks() handles it automatically.
        But in high-frequency scenarios can proactively cleanup to reduce memory usage.

        Args:
            task_id: Task ID to cleanup

        Returns:
            bool: Whether cleanup was successful
        """
        with self._lock:
            task = self._tasks.pop(task_id, None)
            return task is not None

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
            logger.error("[AsyncTaskExecutor] Worker startup failed: task %s not found", task_id)
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
                logger.info("[AsyncTaskExecutor] Task cancelled before execution: %s", task_id)
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
                        logger.info("[AsyncTaskExecutor] Task cancelled after completion: %s", task_id)
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
            logger.info("[AsyncTaskExecutor] Task interrupted and cancelled: %s", task_id)

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
            logger.debug("[AsyncTaskExecutor] Cleaned up %s old task records", len(to_remove))

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
                        task.task_id, running_count, self.max_concurrent,
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

    def _zombie_scan_loop(self):
        """Background loop that periodically scans for zombie tasks

        Zombie tasks are tasks stuck in PENDING or RUNNING state beyond timeout.
        This is a safety net in case get_status() is not called frequently enough.
        """
        while not self._shutdown:
            time.sleep(self.zombie_check_interval)
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
                    logger.warning("[AsyncTaskExecutor] Zombie PENDING: %s", task.task_id)
                    retry_candidates.append(task)

                elif task.status == TaskStatus.RUNNING:
                    if task.started_at is not None:
                        running_elapsed = now - task.started_at
                        if running_elapsed > self.default_timeout:
                            task.status = TaskStatus.FAILED
                            task.completed_at = now
                            task.error_message = f"Zombie scan: RUNNING for {running_elapsed:.0f}s"
                            logger.warning("[AsyncTaskExecutor] Zombie RUNNING: %s", task.task_id)
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

    def _load_persisted_tasks(self):
        """Load task states from persistence directory on startup

        Only loads tasks that were active (PENDING/RUNNING/RETRYING) at crash time.
        These tasks are marked as FAILED and scheduled for retry.
        """
        if not self.persist_dir:
            return

        state_file = Path(self.persist_dir) / "async_tasks_state.json"
        if not state_file.exists():
            return

        try:
            with open(state_file, "r") as f:
                data = json.load(f)

            saved_checksum = data.pop("sha256", None)
            if saved_checksum:
                verify_json = json.dumps(data, indent=2)
                verify_checksum = hashlib.sha256(verify_json.encode()).hexdigest()
                if verify_checksum != saved_checksum:
                    logger.warning("[AsyncTaskExecutor] State file checksum mismatch, discarding")
                    state_file.unlink(missing_ok=True)
                    return

            active_count = 0
            recovered_tasks = []
            for task_data in data.get("tasks", []):
                status_str = task_data.get("status", "")
                if status_str in ("pending", "running", "retrying"):
                    task = AsyncTask(
                        task_id=task_data["task_id"],
                        prompt=task_data["prompt"],
                        status=TaskStatus.FAILED,
                        created_at=task_data.get("created_at", time.time()),
                        retry_count=task_data.get("retry_count", 0),
                        max_retries=task_data.get("max_retries", self.max_retries),
                        error_message="Recovered from crash (previous state: {})".format(status_str),
                    )
                    self._tasks[task.task_id] = task
                    recovered_tasks.append(task)
                    active_count += 1

            for task in recovered_tasks:
                self._schedule_retry(task)

            if active_count > 0:
                logger.info(
                    f"[AsyncTaskExecutor] Recovered {active_count} tasks from crash"
                )

            state_file.unlink(missing_ok=True)

        except Exception as e:
            logger.warning("[AsyncTaskExecutor] Failed to load persisted tasks: %s", e)

    def _persist_active_tasks(self):
        """Save active task states to disk for crash recovery

        Called during shutdown to preserve task states.
        On next startup, _load_persisted_tasks will recover them.
        """
        if not self.persist_dir:
            return

        try:
            os.makedirs(self.persist_dir, exist_ok=True)
            state_file = Path(self.persist_dir) / "async_tasks_state.json"

            active_tasks = []
            with self._lock:
                for task in self._tasks.values():
                    if task.status in (
                        TaskStatus.PENDING,
                        TaskStatus.RUNNING,
                        TaskStatus.RETRYING,
                    ):
                        active_tasks.append(
                            {
                                "task_id": task.task_id,
                                "prompt": task.prompt,
                                "status": task.status.value,
                                "created_at": task.created_at,
                                "retry_count": task.retry_count,
                                "max_retries": task.max_retries,
                            }
                        )

            if active_tasks:
                payload = {"tasks": active_tasks, "saved_at": time.time()}
                payload_json = json.dumps(payload, indent=2)
                checksum = hashlib.sha256(payload_json.encode()).hexdigest()
                payload["sha256"] = checksum
                with open(state_file, "w") as f:
                    json.dump(payload, f, indent=2)
                os.chmod(state_file, 0o600)
                logger.info(
                    f"[AsyncTaskExecutor] Persisted {len(active_tasks)} active tasks"
                )
            else:
                state_file.unlink(missing_ok=True)

        except Exception as e:
            logger.warning("[AsyncTaskExecutor] Failed to persist tasks: %s", e)

    def shutdown(self):
        """Graceful shutdown: persist active tasks and stop zombie scanner

        Call this before process exit to enable crash recovery on restart.
        """
        self._shutdown = True
        self._persist_active_tasks()
        logger.info("[AsyncTaskExecutor] Shutdown complete")
