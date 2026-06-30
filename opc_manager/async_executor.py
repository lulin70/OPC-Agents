"""
Async Task Executor v3.6 — P0-3 Failure Recovery Enhancement

Core problem solved:
- User waits 5-10s after input, Streamlit sync blocking causes timeout crash ("is it frozen?")
- Tasks stuck in RUNNING/PENDING forever with no recovery — production reliability risk

=== Design Decision (ADR-010) ===
Decision: Keep Streamlit, switch to async execution + polling pattern (minimal change approach)
Reasons: no new framework risk; reuse TaskEngineV3; minimal frontend (submit→poll→display).

=== Core Architecture (Mixin-based facade) ===
  submit(prompt) → return task_id (<1ms) → background thread _run_worker
    → TaskEngineV3.execute() + save_deliverable() → status: done/failed
    → retry if retries left → frontend polls get_status() → displays result.

  AsyncTaskExecutor is a facade composing three mixins (each in its own module):
    WorkerMixin      — _run_worker / _default_execute / _cleanup_old_tasks / _schedule_retry
    RecoveryMixin    — _zombie_scan_loop / _scan_zombies / _process_retries
    PersistenceMixin — _load_persisted_tasks / _persist_active_tasks
  This facade retains the public API (submit/get_status/cancel/list_active_tasks/
  cleanup/shutdown); cross-mixin calls resolve at runtime via Python's MRO.
  TaskStatus/AsyncTask are defined here before the mixin imports to keep the
  import cycle safe.

=== Failure Recovery (v3.6) ===
  1. Auto-retry: failed tasks retry up to max_retries (exponential backoff)
  2. Running timeout: RUNNING tasks exceeding timeout auto-marked FAILED
  3. Zombie cleanup: periodic scan for stuck PENDING/RUNNING tasks
  4. State persistence (JSON) + graceful shutdown save active task states

=== Performance / Version History ===
  submit()<10ms | get_status()<1ms | max 5 concurrent | ~1KB/task | v3.6.0 failure recovery
"""

import threading
import time
import uuid
import logging
from typing import Dict, Optional, Any, Callable, List
from dataclasses import dataclass, field
from enum import Enum

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
    cancel_event: threading.Event = field(default_factory=threading.Event)
    retry_count: int = 0
    max_retries: int = 2
    next_retry_at: Optional[float] = None
    last_error: Optional[str] = None


from .async_executor_worker import WorkerMixin  # noqa: E402
from .async_executor_recovery import RecoveryMixin  # noqa: E402
from .async_executor_persistence import PersistenceMixin  # noqa: E402


class AsyncTaskExecutor(WorkerMixin, RecoveryMixin, PersistenceMixin):
    """Async Task Executor — Solves Streamlit timeout crash issue

    Core capabilities:
    1. Instant submit: submit() returns task_id immediately, doesn't block frontend
    2. Background execution: Calls TaskEngineV3 in separate thread
    3. Status polling: get_status() non-blocking query progress
    4. Task cancellation: cancel() gracefully terminates background thread
    5. Auto cleanup: Timed-out tasks auto-marked as failed and resources released

    Usage example:
        >>> executor = AsyncTaskExecutor(max_concurrent=3, default_timeout=120)
        >>> task_id = executor.submit("帮我写Q2营销方案")  # returns immediately
        >>> while executor.get_status(task_id)['status'] not in ['done','failed','cancelled']:
        ...     time.sleep(1)  # poll until terminal state
        >>> print(executor.get_status(task_id).get('result_content', '')[:100])

    Thread safety:
    - All public methods are thread-safe
    - Internal use of threading.Lock protects shared state
    - Cancellation via threading.Event

    Degradation strategy:
    - Background thread exception → auto-mark as FAILED, no main thread crash
    - Timeout not completed → auto-mark as FAILED, release resources
    - Concurrency limit reached → submit() returns None (caller should prompt user to retry later)

    Architecture: mixin-based facade — see module docstring for the three
    behavior mixins (Worker / Recovery / Persistence) and MRO resolution.
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
        self._shutdown_event = threading.Event()

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

    def shutdown(self, wait: bool = False):
        """Graceful shutdown: cancel active tasks and stop background threads.

        Call this before process exit to enable crash recovery on restart.
        Tests may call shutdown(wait=False) to signal cancellation without
        blocking; worker threads will exit once their current operation
        observes the cancel event.

        Args:
            wait: If True, block until background threads exit with a timeout.
        """
        self._shutdown = True
        self._shutdown_event.set()

        # Cancel all active tasks so worker threads can release resources
        # (including database connections) as soon as possible.
        with self._lock:
            active_task_ids = [
                task_id
                for task_id, task in self._tasks.items()
                if task.status
                in (TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.RETRYING)
            ]
        for task_id in active_task_ids:
            self.cancel(task_id)

        self._persist_active_tasks()

        if wait:
            if self._zombie_timer.is_alive():
                self._zombie_timer.join(timeout=self.zombie_check_interval + 1)
            # Give worker threads a bounded window to exit after cancellation.
            with self._lock:
                worker_threads = [
                    task.thread_ref
                    for task in self._tasks.values()
                    if task.thread_ref is not None and task.thread_ref.is_alive()
                ]
            for t in worker_threads:
                t.join(timeout=2)

        logger.info("[AsyncTaskExecutor] Shutdown complete")

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
                        task.error_message = (
                            f"Task RUNNING for {running_elapsed:.0f}s "
                            f"(timeout: {self.default_timeout}s)"
                        )
                        logger.warning(
                            "[AsyncTaskExecutor] RUNNING timeout: %s", task_id
                        )
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
            - cancel() is asynchronous, after calling you need to wait for
              get_status() to confirm status becomes cancelled
            - For long-running search/LLM calls, it may take a few seconds to
              respond to cancellation
        """
        with self._lock:
            task = self._tasks.get(task_id)

            if not task:
                logger.warning(
                    "[AsyncTaskExecutor] Cancel failed: task %s not found", task_id
                )
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
                if task.status in [
                    TaskStatus.PENDING,
                    TaskStatus.RUNNING,
                    TaskStatus.RETRYING,
                ]:
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
