"""
Persistence Mixin for AsyncTaskExecutor

Extracted from async_executor.py to reduce the God Class size.
Contains the task-state persistence logic (JSON file with SHA-256 checksum):
- _load_persisted_tasks: load active task states from disk on startup and
  schedule retries for them (crash recovery)
- _persist_active_tasks: save active task states to disk on shutdown

=== Design Notes ===
Implemented as a mixin class to preserve all method signatures.
AsyncTaskExecutor inherits from this mixin, so all external callers see no
change. Cross-mixin dependencies are resolved at runtime via the composed
facade instance:
- self._tasks / self._lock / self.persist_dir / self.max_retries
  (facade — set by __init__)
- self._schedule_retry (provided by WorkerMixin)

TaskStatus and AsyncTask are imported from the facade module; the facade
defines them before importing the mixins to keep the import cycle safe
(see async_executor.py).
"""

import json
import hashlib
import os
import time
import logging
import threading
from pathlib import Path
from typing import Any, Optional

from .async_executor import AsyncTask, TaskStatus

logger = logging.getLogger(__name__)


class PersistenceMixin:
    """Mixin class containing the task-state persistence logic for
    AsyncTaskExecutor.

    Cross-mixin calls (e.g. self._schedule_retry) are resolved at runtime on
    the composed facade instance via Python's MRO.
    """

    # Attributes provided by the composed facade (AsyncTaskExecutor) at runtime
    persist_dir: Optional[str]
    max_retries: int
    _tasks: dict
    _lock: threading.RLock
    _schedule_retry: Any

    def _load_persisted_tasks(self) -> None:
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
                    logger.warning(
                        "[AsyncTaskExecutor] State file checksum mismatch, discarding"
                    )
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
                        error_message="Recovered from crash (previous state: {})".format(
                            status_str
                        ),
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

    def _persist_active_tasks(self) -> None:
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
