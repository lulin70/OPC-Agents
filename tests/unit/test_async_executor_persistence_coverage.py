"""Coverage tests for opc_manager.async_executor_persistence.PersistenceMixin

Targets crash-recovery load and shutdown persist paths, including SHA-256
checksum verification, status filtering, and exception handling.
"""

import json
import hashlib
import os
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch


from opc_manager.async_executor import AsyncTask, TaskStatus
from opc_manager.async_executor_persistence import PersistenceMixin


class FakeExecutor(PersistenceMixin):
    """Minimal facade that supplies the cross-mixin attributes."""

    def __init__(self, persist_dir=None, max_retries=3, tasks=None):
        self.persist_dir = persist_dir
        self.max_retries = max_retries
        self._tasks = tasks if tasks is not None else {}
        self._lock = threading.RLock()
        self._schedule_retry = MagicMock()


def _make_state_payload(tasks):
    payload = {"tasks": tasks, "saved_at": 1234567890.0}
    payload_json = json.dumps(payload, indent=2)
    checksum = hashlib.sha256(payload_json.encode()).hexdigest()
    payload["sha256"] = checksum
    return payload


def _write_state_file(persist_dir, tasks, corrupt_checksum=False):
    os.makedirs(persist_dir, exist_ok=True)
    state_file = Path(persist_dir) / "async_tasks_state.json"
    payload = _make_state_payload(tasks)
    if corrupt_checksum:
        payload["sha256"] = "deadbeef" * 8
    with open(state_file, "w") as f:
        json.dump(payload, f, indent=2)
    return state_file


class TestLoadPersistedTasks:
    def test_no_persist_dir_returns_early(self):
        executor = FakeExecutor(persist_dir=None)
        executor._load_persisted_tasks()
        assert executor._tasks == {}
        executor._schedule_retry.assert_not_called()

    def test_no_state_file_returns_early(self, tmp_path):
        executor = FakeExecutor(persist_dir=str(tmp_path))
        executor._load_persisted_tasks()
        assert executor._tasks == {}
        executor._schedule_retry.assert_not_called()

    def test_checksum_mismatch_discards_file(self, tmp_path):
        tasks = [
            {
                "task_id": "t1",
                "prompt": "do X",
                "status": "running",
                "created_at": 1.0,
                "retry_count": 0,
                "max_retries": 3,
            }
        ]
        state_file = _write_state_file(str(tmp_path), tasks, corrupt_checksum=True)
        executor = FakeExecutor(persist_dir=str(tmp_path))
        executor._load_persisted_tasks()
        assert executor._tasks == {}
        executor._schedule_retry.assert_not_called()
        assert not state_file.exists()

    def test_recover_pending_task(self, tmp_path):
        tasks = [
            {
                "task_id": "t1",
                "prompt": "do X",
                "status": "pending",
                "created_at": 1.0,
                "retry_count": 0,
                "max_retries": 3,
            }
        ]
        _write_state_file(str(tmp_path), tasks)
        executor = FakeExecutor(persist_dir=str(tmp_path))
        executor._load_persisted_tasks()
        assert "t1" in executor._tasks
        task = executor._tasks["t1"]
        assert task.status == TaskStatus.FAILED
        assert "Recovered from crash" in task.error_message
        executor._schedule_retry.assert_called_once_with(task)

    def test_recover_running_task(self, tmp_path):
        tasks = [
            {
                "task_id": "t2",
                "prompt": "do Y",
                "status": "running",
                "created_at": 2.0,
                "retry_count": 1,
                "max_retries": 5,
            }
        ]
        _write_state_file(str(tmp_path), tasks)
        executor = FakeExecutor(persist_dir=str(tmp_path))
        executor._load_persisted_tasks()
        task = executor._tasks["t2"]
        assert task.status == TaskStatus.FAILED
        assert task.retry_count == 1
        assert task.max_retries == 5

    def test_recover_retrying_task(self, tmp_path):
        tasks = [
            {
                "task_id": "t3",
                "prompt": "do Z",
                "status": "retrying",
                "created_at": 3.0,
                "retry_count": 2,
                "max_retries": 3,
            }
        ]
        _write_state_file(str(tmp_path), tasks)
        executor = FakeExecutor(persist_dir=str(tmp_path))
        executor._load_persisted_tasks()
        assert "t3" in executor._tasks

    def test_skip_completed_tasks(self, tmp_path):
        tasks = [
            {
                "task_id": "done",
                "prompt": "finished",
                "status": "completed",
                "created_at": 1.0,
                "retry_count": 0,
                "max_retries": 3,
            },
            {
                "task_id": "fail",
                "prompt": "failed",
                "status": "failed",
                "created_at": 2.0,
                "retry_count": 0,
                "max_retries": 3,
            },
            {
                "task_id": "pend",
                "prompt": "pending",
                "status": "pending",
                "created_at": 3.0,
                "retry_count": 0,
                "max_retries": 3,
            },
        ]
        _write_state_file(str(tmp_path), tasks)
        executor = FakeExecutor(persist_dir=str(tmp_path))
        executor._load_persisted_tasks()
        assert set(executor._tasks.keys()) == {"pend"}
        executor._schedule_retry.assert_called_once()

    def test_missing_fields_use_defaults(self, tmp_path):
        tasks = [
            {
                "task_id": "minimal",
                "prompt": "p",
                "status": "pending",
            }
        ]
        _write_state_file(str(tmp_path), tasks)
        executor = FakeExecutor(persist_dir=str(tmp_path), max_retries=7)
        executor._load_persisted_tasks()
        task = executor._tasks["minimal"]
        assert task.created_at > 0  # defaulted to time.time()
        assert task.retry_count == 0
        assert task.max_retries == 7  # defaulted to executor.max_retries

    def test_state_file_unlinked_after_load(self, tmp_path):
        tasks = [
            {
                "task_id": "t1",
                "prompt": "p",
                "status": "pending",
                "created_at": 1.0,
                "retry_count": 0,
                "max_retries": 3,
            }
        ]
        state_file = _write_state_file(str(tmp_path), tasks)
        assert state_file.exists()
        executor = FakeExecutor(persist_dir=str(tmp_path))
        executor._load_persisted_tasks()
        assert not state_file.exists()

    def test_exception_during_load_logged_and_swallowed(self, tmp_path):
        state_file = Path(str(tmp_path)) / "async_tasks_state.json"
        os.makedirs(str(tmp_path), exist_ok=True)
        with open(state_file, "w") as f:
            f.write("{ not valid json }")
        executor = FakeExecutor(persist_dir=str(tmp_path))
        executor._load_persisted_tasks()
        assert executor._tasks == {}
        executor._schedule_retry.assert_not_called()

    def test_recover_multiple_tasks(self, tmp_path):
        tasks = [
            {
                "task_id": f"t{i}",
                "prompt": f"p{i}",
                "status": "pending",
                "created_at": float(i),
                "retry_count": 0,
                "max_retries": 3,
            }
            for i in range(5)
        ]
        _write_state_file(str(tmp_path), tasks)
        executor = FakeExecutor(persist_dir=str(tmp_path))
        executor._load_persisted_tasks()
        assert len(executor._tasks) == 5
        assert executor._schedule_retry.call_count == 5


class TestPersistActiveTasks:
    def test_no_persist_dir_returns_early(self):
        executor = FakeExecutor(persist_dir=None)
        executor._persist_active_tasks()
        # No file created, no exceptions

    def test_no_active_tasks_unlinks_existing_file(self, tmp_path):
        state_file = Path(str(tmp_path)) / "async_tasks_state.json"
        os.makedirs(str(tmp_path), exist_ok=True)
        with open(state_file, "w") as f:
            f.write('{"old": "state"}')
        executor = FakeExecutor(persist_dir=str(tmp_path), tasks={})
        executor._persist_active_tasks()
        assert not state_file.exists()

    def test_no_active_tasks_when_no_existing_file(self, tmp_path):
        executor = FakeExecutor(persist_dir=str(tmp_path), tasks={})
        executor._persist_active_tasks()
        state_file = Path(str(tmp_path)) / "async_tasks_state.json"
        assert not state_file.exists()

    def test_persists_pending_task(self, tmp_path):
        task = AsyncTask(
            task_id="t1",
            prompt="do X",
            status=TaskStatus.PENDING,
        )
        executor = FakeExecutor(
            persist_dir=str(tmp_path),
            tasks={"t1": task},
        )
        executor._persist_active_tasks()
        state_file = Path(str(tmp_path)) / "async_tasks_state.json"
        assert state_file.exists()

        with open(state_file) as f:
            data = json.load(f)
        assert "sha256" in data
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["task_id"] == "t1"
        assert data["tasks"][0]["status"] == "pending"

    def test_persists_running_and_retrying(self, tmp_path):
        tasks = {
            "r1": AsyncTask("r1", "p1", status=TaskStatus.RUNNING),
            "r2": AsyncTask("r2", "p2", status=TaskStatus.RETRYING),
        }
        executor = FakeExecutor(persist_dir=str(tmp_path), tasks=tasks)
        executor._persist_active_tasks()
        state_file = Path(str(tmp_path)) / "async_tasks_state.json"
        with open(state_file) as f:
            data = json.load(f)
        statuses = {t["status"] for t in data["tasks"]}
        assert statuses == {"running", "retrying"}

    def test_skips_done_failed_cancelled(self, tmp_path):
        tasks = {
            "d": AsyncTask("d", "p", status=TaskStatus.DONE),
            "f": AsyncTask("f", "p", status=TaskStatus.FAILED),
            "x": AsyncTask("x", "p", status=TaskStatus.CANCELLED),
        }
        executor = FakeExecutor(persist_dir=str(tmp_path), tasks=tasks)
        executor._persist_active_tasks()
        state_file = Path(str(tmp_path)) / "async_tasks_state.json"
        assert not state_file.exists()

    def test_checksum_verifies_round_trip(self, tmp_path):
        task = AsyncTask(
            task_id="round-trip",
            prompt="verify me",
            status=TaskStatus.PENDING,
            retry_count=2,
            max_retries=5,
        )
        executor = FakeExecutor(
            persist_dir=str(tmp_path),
            tasks={"round-trip": task},
        )
        executor._persist_active_tasks()

        state_file = Path(str(tmp_path)) / "async_tasks_state.json"
        with open(state_file) as f:
            data = json.load(f)
        saved_checksum = data.pop("sha256")
        verify_json = json.dumps(data, indent=2)
        verify_checksum = hashlib.sha256(verify_json.encode()).hexdigest()
        assert saved_checksum == verify_checksum

    def test_file_permissions_0o600(self, tmp_path):
        task = AsyncTask("t1", "p", status=TaskStatus.PENDING)
        executor = FakeExecutor(persist_dir=str(tmp_path), tasks={"t1": task})
        executor._persist_active_tasks()
        state_file = Path(str(tmp_path)) / "async_tasks_state.json"
        mode = oct(state_file.stat().st_mode & 0o777)
        assert mode == oct(0o600)

    def test_creates_persist_dir_if_missing(self, tmp_path):
        nested = tmp_path / "nested" / "deep"
        task = AsyncTask("t1", "p", status=TaskStatus.PENDING)
        executor = FakeExecutor(persist_dir=str(nested), tasks={"t1": task})
        executor._persist_active_tasks()
        state_file = nested / "async_tasks_state.json"
        assert state_file.exists()

    def test_exception_during_persist_swallowed(self, tmp_path):
        executor = FakeExecutor(persist_dir=str(tmp_path), tasks={})
        # Force an exception inside the try block by making os.makedirs fail
        with patch("opc_manager.async_executor_persistence.os.makedirs") as m:
            m.side_effect = OSError("disk full")
            executor._persist_active_tasks()  # should not raise

    def test_round_trip_persist_then_load(self, tmp_path):
        task = AsyncTask(
            task_id="rt",
            prompt="round trip",
            status=TaskStatus.RUNNING,
            retry_count=1,
            max_retries=4,
        )
        executor1 = FakeExecutor(
            persist_dir=str(tmp_path),
            tasks={"rt": task},
        )
        executor1._persist_active_tasks()

        executor2 = FakeExecutor(persist_dir=str(tmp_path))
        executor2._load_persisted_tasks()
        assert "rt" in executor2._tasks
        recovered = executor2._tasks["rt"]
        assert recovered.status == TaskStatus.FAILED
        assert recovered.prompt == "round trip"
        assert recovered.retry_count == 1
        assert recovered.max_retries == 4
        executor2._schedule_retry.assert_called_once()
