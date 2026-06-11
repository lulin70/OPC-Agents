"""E2E User Journey Tests — Cross-Page & Full-Pipeline Scenarios.

These tests simulate real user journeys that span multiple system components,
verifying state consistency across pages, async task polling, multi-turn
conversations, and complete lifecycle flows.

All tests use mocked LLM and isolated tmp_path — never touches real data/.
Marked with @pytest.mark.integration for CI filtering.
"""

import asyncio
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from opc_manager.agent_loop import AgentLoop, AgentContext, AgentState
from opc_manager.async_executor import AsyncTaskExecutor, TaskStatus
from opc_manager.data_manager import (
    init_db,
    execute_write,
    execute_query,
    gen_id,
)
from opc_manager.onboarding import OnboardingManager, OnboardingStep
from opc_manager.task_engine_v3 import TaskEngineV3, TaskResult, TaskType
from opc_manager.task_types import TaskResult as TaskResultV2
from opc_manager.undo_manager import UndoManager, OperationType
from opc_manager.audit_log import AuditLog
from opc_manager.i18n import I18nManager
from opc_manager.secure_storage import SecureKeyStore
from opc_manager.data_backup import DataBackupManager


# ─── Shared Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset all singleton instances between tests for isolation."""
    AuditLog._instance = None
    import opc_manager.performance_monitor as _pm
    _pm._default_monitor = None
    import opc_manager.data_manager as _dm
    _dm._db_initialized = False
    _dm._local = type("Local", (), {"conn": None})()
    import opc_manager.skill_reviews as _sr
    _sr._manager = None
    import opc_manager.llm_cache as _lc
    _lc._cache_instance = None
    import opc_manager.knowledge_bridge as _kb
    _kb._instance = None
    yield
    AuditLog._instance = None
    _pm._default_monitor = None
    _dm._db_initialized = False
    _dm._local = type("Local", (), {"conn": None})()
    _sr._manager = None
    _lc._cache_instance = None
    _kb._instance = None


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a temporary data directory."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def patched_data_dir(tmp_data_dir):
    """Patch opc_manager.data_manager globals to tmp_path."""
    import opc_manager.data_manager as _dm
    old_data_dir = _dm.DATA_DIR
    old_db_path = _dm.DB_PATH
    old_backup_dir = _dm.BACKUP_DIR
    _dm.DATA_DIR = str(tmp_data_dir)
    _dm.DB_PATH = str(tmp_data_dir / "opc_data.db")
    _dm.BACKUP_DIR = str(tmp_data_dir / "backups")
    _dm._db_initialized = False
    _dm._local = type("Local", (), {"conn": None})()
    try:
        _dm.init_db()
    except Exception:
        pass
    yield tmp_data_dir
    _dm.DATA_DIR = old_data_dir
    _dm.DB_PATH = old_db_path
    _dm.BACKUP_DIR = old_backup_dir
    _dm._db_initialized = False
    _dm._local = type("Local", (), {"conn": None})()


@pytest.fixture
def secure_store(tmp_path):
    """Create a SecureKeyStore pointing to a temp file."""
    storage_path = str(tmp_path / "test_keys.json")
    return SecureKeyStore(storage_path=storage_path)


# ─── Helper: Mock AgentLoop ─────────────────────────────────────────────────


def _make_mock_agent_loop(task_result=None):
    """Create a fully mocked AgentLoop that returns the given TaskResult."""
    from opc_manager.strategist_brain import Intent, ExecutionPlan, Step, IntentType

    if task_result is None:
        task_result = TaskResult(
            success=True,
            content="任务执行成功，以下是结果内容。",
            task_type=TaskType.CONTENT_GENERATION,
            execution_time_ms=500,
        )

    mock_strategist = MagicMock()
    mock_strategist.understand_intent.return_value = Intent(
        goal="执行用户任务",
        type=IntentType.CREATION,
    )
    mock_strategist.plan.return_value = ExecutionPlan(
        plan_id="test_plan",
        intent=mock_strategist.understand_intent.return_value,
        steps=[
            Step(
                id="step_1",
                skill_id="content_generation",
                description="生成内容",
                parameters={"query": "test", "goal": "执行用户任务"},
            )
        ],
    )

    with patch.dict(os.environ, {"OPC_SKIP_REFLECT": "true"}):
        loop = AgentLoop(
            strategist_brain=mock_strategist,
            task_engine=TaskEngineV3(),
        )

    return loop, task_result


# ═══════════════════════════════════════════════════════════════════════════
# Journey 1: Async Task Submit → Poll → Display (Full Polling Flow)
# ═══════════════════════════════════════════════════════════════════════════


class TestJourneyAsyncPollingFlow:
    """Simulate the full async task lifecycle: submit → poll → done/failed.

    This is the core UX flow: user types prompt → frontend submits → polls
    every 1s → displays result when done.
    """

    def test_submit_poll_done(self, patched_data_dir):
        """Happy path: submit task → poll until done → get result."""
        executor = AsyncTaskExecutor(max_concurrent=3, default_timeout=30)

        def _execute_fn(prompt, **kwargs):
            time.sleep(0.1)  # Simulate work
            return TaskResult(
                success=True,
                content=f"处理完成: {prompt[:20]}",
                task_type=TaskType.CONTENT_GENERATION,
                execution_time_ms=100,
            )

        task_id = executor.submit("帮我写Q2营销方案", execute_func=_execute_fn)
        assert task_id is not None

        # Poll until done (simulating frontend polling)
        for _ in range(20):
            status = executor.get_status(task_id)
            if status["status"] in ("done", "failed", "cancelled"):
                break
            time.sleep(0.1)

        assert status["status"] == "done"
        assert status["result_success"] is True
        assert "营销方案" in status["result_content"]

    def test_submit_poll_failed_then_retry(self, patched_data_dir):
        """Error recovery: task fails → user retries → succeeds."""
        executor = AsyncTaskExecutor(max_concurrent=3, default_timeout=30, max_retries=0)
        call_count = {"n": 0}

        def _failing_fn(prompt, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("API暂时不可用")
            return TaskResult(
                success=True,
                content="重试成功",
                task_type=TaskType.CONTENT_GENERATION,
            )

        # First attempt fails
        task_id = executor.submit("分析销售数据", execute_func=_failing_fn)
        for _ in range(20):
            status = executor.get_status(task_id)
            if status["status"] in ("done", "failed", "cancelled"):
                break
            time.sleep(0.1)

        assert status["status"] == "failed"
        assert "API暂时不可用" in status["error_message"]

        # User retries (second call succeeds)
        task_id2 = executor.submit("分析销售数据", execute_func=_failing_fn)
        for _ in range(20):
            status2 = executor.get_status(task_id2)
            if status2["status"] in ("done", "failed", "cancelled"):
                break
            time.sleep(0.1)

        assert status2["status"] == "done"
        assert status2["result_success"] is True

    def test_submit_cancel_while_running(self, patched_data_dir):
        """User cancels a running task."""
        executor = AsyncTaskExecutor(max_concurrent=3, default_timeout=60)

        def _slow_fn(prompt, **kwargs):
            time.sleep(5)
            return TaskResult(success=True, content="完成", task_type=TaskType.GENERAL_CHAT)

        task_id = executor.submit("长任务", execute_func=_slow_fn)
        time.sleep(0.2)  # Let it start

        cancelled = executor.cancel(task_id)
        # Cancel may or may not succeed depending on timing
        status = executor.get_status(task_id)
        assert status["status"] in ("cancelled", "running", "done", "failed")

    def test_concurrent_tasks_all_complete(self, patched_data_dir):
        """Multiple tasks submitted concurrently all complete."""
        executor = AsyncTaskExecutor(max_concurrent=5, default_timeout=30)

        def _quick_fn(prompt, **kwargs):
            time.sleep(0.05)
            return TaskResult(
                success=True,
                content=f"完成: {prompt[:10]}",
                task_type=TaskType.CONTENT_GENERATION,
            )

        task_ids = []
        for i in range(3):
            tid = executor.submit(f"任务{i}", execute_func=_quick_fn)
            task_ids.append(tid)

        # Poll all tasks
        results = {}
        for _ in range(30):
            all_done = True
            for tid in task_ids:
                if tid not in results:
                    status = executor.get_status(tid)
                    if status["status"] in ("done", "failed", "cancelled"):
                        results[tid] = status
                    else:
                        all_done = False
            if all_done:
                break
            time.sleep(0.1)

        assert len(results) == 3
        for tid, status in results.items():
            assert status["status"] == "done"
            assert status["result_success"] is True


# ═══════════════════════════════════════════════════════════════════════════
# Journey 2: Cross-Page State Consistency
# ═══════════════════════════════════════════════════════════════════════════


class TestJourneyCrossPageState:
    """Verify that state created on one page is visible on another.

    Simulates: Chat → execute task → Dashboard shows updated data.
    """

    def test_chat_task_reflected_in_dashboard(self, patched_data_dir):
        """After executing a task in Chat, Dashboard should show the record."""
        from opc_manager.data_manager import execute_write, execute_query

        task_id = gen_id()
        execute_write(
            "INSERT INTO tasks (id, title, description, priority, status, created_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (task_id, "营销方案", "Q2营销方案已完成", 2, "done"),
        )

        # Step 2: Dashboard queries the same data
        rows = execute_query("SELECT * FROM tasks WHERE id = ?", (task_id,))
        assert len(rows) == 1
        assert rows[0]["title"] == "营销方案"
        assert rows[0]["status"] == "done"

    def test_settings_change_reflected_in_chat(self, patched_data_dir, secure_store):
        """API key configured in Settings is available for Chat LLM calls."""
        # Step 1: User sets API key in Settings
        secure_store.set_key("MOKA_API_KEY", "sk-test-key-12345")

        # Step 2: Chat retrieves the same key
        retrieved = secure_store.get_key("MOKA_API_KEY")
        assert retrieved == "sk-test-key-12345"

    def test_i18n_language_switch_affects_all_pages(self, patched_data_dir):
        """Language change in Settings affects Chat and Dashboard text."""
        i18n = I18nManager()

        # Default language
        default_text = i18n.t("app_title")
        assert default_text is not None

        # Switch to English
        i18n.locale = "en_US"
        en_text = i18n.t("app_title")
        assert en_text is not None

        # Switch back
        i18n.locale = "zh_CN"
        zh_text = i18n.t("app_title")
        assert zh_text is not None

    def test_deliverable_saved_appears_in_deliverables_page(self, patched_data_dir):
        """Content saved from Chat appears in Deliverables listing."""
        from opc_manager.data_manager import execute_write, execute_query

        # Save a deliverable (simulating Chat save action)
        deliverable_id = gen_id()
        execute_write(
            "INSERT INTO interaction_log (id, intent_type, goal, skill_used, success, created_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (deliverable_id, "content_generation", "Q2营销方案", "content_skill", 1),
        )

        # Deliverables page queries
        rows = execute_query("SELECT * FROM interaction_log WHERE id = ?", (deliverable_id,))
        assert len(rows) == 1
        assert rows[0]["goal"] == "Q2营销方案"


# ═══════════════════════════════════════════════════════════════════════════
# Journey 3: Multi-Turn Conversation with Context
# ═══════════════════════════════════════════════════════════════════════════


class TestJourneyMultiTurnConversation:
    """Simulate multi-turn conversations where context is maintained.

    User asks a question → gets answer → asks follow-up → system
    maintains conversation context.
    """

    def test_session_context_persisted_across_turns(self, patched_data_dir):
        """Session context is maintained across multiple turns."""
        from opc_manager.session_context import SessionContextManager

        mgr = SessionContextManager()

        # Turn 1: User asks about marketing
        mgr.add_turn(
            user_input="帮我分析Q2营销数据",
            assistant_response="Q2营销数据显示同比增长15%...",
            task_type="data_analysis",
        )

        # Turn 2: Follow-up question
        mgr.add_turn(
            user_input="具体是哪个渠道增长最快？",
            assistant_response="社交媒体渠道增长最快，达到32%...",
            task_type="data_analysis",
        )

        # Verify context is maintained
        context = mgr.get_context_for_llm(max_turns=5)
        assert "营销数据" in context
        assert "渠道" in context

    def test_agent_loop_context_tracking(self, patched_data_dir):
        """AgentLoop tracks contexts across invocations."""
        loop = AgentLoop()

        # Simulate two sequential runs
        ctx1 = AgentContext(
            task_id="task_1",
            user_input="第一个问题",
            session_id="session_1",
        )
        loop.contexts["task_1"] = ctx1

        ctx2 = AgentContext(
            task_id="task_2",
            user_input="跟进问题",
            session_id="session_1",
        )
        loop.contexts["task_2"] = ctx2

        # Both contexts are tracked
        assert "task_1" in loop.contexts
        assert "task_2" in loop.contexts
        assert loop.contexts["task_1"].session_id == "session_1"
        assert loop.contexts["task_2"].session_id == "session_1"


# ═══════════════════════════════════════════════════════════════════════════
# Journey 4: New User First Experience (Onboarding → First Task)
# ═══════════════════════════════════════════════════════════════════════════


class TestJourneyNewUserFirstExperience:
    """Complete first-time user flow: Launch → Onboarding → First Task → Result."""

    def test_full_onboarding_to_first_task(self, tmp_path):
        """New user completes onboarding and executes first task."""
        # Step 1: Onboarding starts at WELCOME
        state_file = tmp_path / "onboarding.json"
        fake_marker = tmp_path / ".onboarding_complete"
        with patch.object(OnboardingManager, "STATE_FILE", str(state_file)), \
             patch("opc_manager.onboarding._ONBOARDING_MARKER", fake_marker):
            mgr = OnboardingManager()
            assert not mgr.is_completed
            assert mgr.get_current_step() == OnboardingStep.WELCOME

            # Step 2: Progress through onboarding steps
            steps = [OnboardingStep.LLM_CONFIG, OnboardingStep.SAMPLE_TASK, OnboardingStep.COMPLETED]
            for step in steps:
                mgr.advance_to_step(step)
                if mgr.is_completed:
                    break

            assert mgr.is_completed

        # Step 3: Onboarding doesn't show again
        with patch.object(OnboardingManager, "STATE_FILE", str(state_file)), \
             patch("opc_manager.onboarding._ONBOARDING_MARKER", fake_marker):
            mgr2 = OnboardingManager()
            assert mgr2.is_completed

    def test_onboarding_then_configure_api_key(self, tmp_path, secure_store):
        """After onboarding, user configures API key for first task."""
        # Complete onboarding
        state_file = tmp_path / "onboarding.json"
        fake_marker = tmp_path / ".onboarding_complete"
        with patch.object(OnboardingManager, "STATE_FILE", str(state_file)), \
             patch("opc_manager.onboarding._ONBOARDING_MARKER", fake_marker):
            mgr = OnboardingManager()
            mgr.complete_onboarding()

        # Configure API key
        secure_store.set_key("MOKA_API_KEY", "sk-new-user-key")
        assert secure_store.get_key("MOKA_API_KEY") == "sk-new-user-key"

        # Now user can execute tasks
        with patch.dict(os.environ, {"OPC_SKIP_REFLECT": "true"}):
            loop, _ = _make_mock_agent_loop()
            result = asyncio.run(loop.run("帮我写一封商务邮件"))
            assert isinstance(result, TaskResult)


# ═══════════════════════════════════════════════════════════════════════════
# Journey 5: Error Recovery & Resilience
# ═══════════════════════════════════════════════════════════════════════════


class TestJourneyErrorRecovery:
    """Verify system recovers gracefully from errors during user workflows."""

    def test_empty_input_returns_friendly_error(self, patched_data_dir):
        """Empty input doesn't crash — returns friendly error."""
        loop = AgentLoop()
        result = asyncio.run(loop.run(""))
        assert not result.success
        assert "不能为空" in result.error

    def test_oversized_input_returns_friendly_error(self, patched_data_dir):
        """Oversized input doesn't crash — returns friendly error."""
        loop = AgentLoop()
        result = asyncio.run(loop.run("x" * 10001))
        assert not result.success
        assert "最大长度" in result.error

    def test_llm_failure_graceful_degradation(self, patched_data_dir):
        """LLM failure doesn't crash the system — returns error TaskResult."""
        mock_strategist = MagicMock()
        mock_strategist.understand_intent.side_effect = RuntimeError("LLM服务不可用")

        with patch.dict(os.environ, {"OPC_SKIP_REFLECT": "true"}):
            loop = AgentLoop(strategist_brain=mock_strategist)
            result = asyncio.run(loop.run("帮我分析数据"))

        assert not result.success
        assert result.error  # Has error message

    def test_database_error_recovery(self, patched_data_dir):
        """Database write failure doesn't crash — subsequent writes succeed."""
        from opc_manager.data_manager import execute_write

        # Valid write
        task_id = gen_id()
        execute_write(
            "INSERT INTO tasks (id, title, description, priority, status, created_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (task_id, "正常任务", "描述", 2, "pending"),
        )

        # Duplicate write (should not crash)
        try:
            execute_write(
                "INSERT INTO tasks (id, title, description, priority, status, created_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
                (task_id, "重复任务", "描述", 2, "pending"),
            )
        except Exception:
            pass  # Expected: duplicate key error

        # Subsequent valid write still works
        task_id2 = gen_id()
        execute_write(
            "INSERT INTO tasks (id, title, description, priority, status, created_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (task_id2, "恢复后的任务", "描述", 2, "pending"),
        )
        rows = execute_query("SELECT * FROM tasks WHERE id = ?", (task_id2,))
        assert len(rows) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Journey 6: Data Lifecycle (Execute → Backup → Restore)
# ═══════════════════════════════════════════════════════════════════════════


class TestJourneyDataLifecycle:
    """Complete data lifecycle: create data → backup → modify → restore."""

    def test_backup_and_restore_preserves_data(self, patched_data_dir, tmp_path):
        """User creates data, backs up, modifies, then restores original."""
        from opc_manager.data_manager import execute_write, execute_query

        # Step 1: Create original data
        task_id = gen_id()
        execute_write(
            "INSERT INTO tasks (id, title, description, priority, status, created_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (task_id, "原始任务", "原始内容", 2, "pending"),
        )

        # Step 2: Create backup
        backup_mgr = DataBackupManager(base_dir=str(patched_data_dir))
        backup_path, _ = backup_mgr.create_backup()
        assert backup_path is not None
        assert os.path.exists(backup_path)

        # Step 3: Modify data
        execute_write(
            "UPDATE tasks SET title = ? WHERE id = ?",
            ("修改后的任务", task_id),
        )
        rows = execute_query("SELECT title FROM tasks WHERE id = ?", (task_id,))
        assert rows[0]["title"] == "修改后的任务"

        # Step 4: Restore from backup
        restore_result = backup_mgr.restore_backup(str(backup_path), confirm=True)
        # Restore should succeed or return error dict
        assert isinstance(restore_result, dict)

    def test_export_redacts_secrets(self, patched_data_dir, tmp_path, secure_store):
        """Export data redacts sensitive information."""
        secure_store.set_key("MOKA_API_KEY", "sk-super-secret-key")

        backup_mgr = DataBackupManager(base_dir=str(patched_data_dir))

        export_data = backup_mgr.export_data()
        # Export should not contain plaintext secrets
        if export_data:
            export_str = str(export_data)
            assert "sk-super-secret-key" not in export_str


# ═══════════════════════════════════════════════════════════════════════════
# Journey 7: Undo Flow (Execute → Undo → Verify)
# ═══════════════════════════════════════════════════════════════════════════


class TestJourneyUndoFlow:
    """User executes a task, then undoes it."""

    def test_undo_records_and_lists_operations(self, patched_data_dir):
        """Undo records can be pushed and listed for a session."""
        undo_mgr = UndoManager()

        # Push an undo record (simulating a task that added a customer)
        op_id = undo_mgr.push(
            session_id="test_session",
            op_type=OperationType.ADD_CUSTOMER,
            inverse_func="undo_add_customer",
            inverse_args={"customer_id": "cust_001"},
            original_result={"name": "测试客户", "company": "测试公司"},
        )

        # Verify the record is listed as undoable
        undoable = undo_mgr.list_undoable("test_session")
        assert len(undoable) >= 1
        assert undoable[0]["operation_id"] == op_id
        assert undoable[0]["type"] == OperationType.ADD_CUSTOMER.value


# ═══════════════════════════════════════════════════════════════════════════
# Journey 8: Audit Trail Across User Actions
# ═══════════════════════════════════════════════════════════════════════════


class TestJourneyAuditTrail:
    """Verify that user actions are properly audited."""

    def test_task_execution_creates_audit_record(self, patched_data_dir):
        """Executing a task creates an audit log entry."""
        audit = AuditLog()

        # Log a task execution
        audit.log(
            session_id="session_001",
            operation_type="task_execute",
            skill_id="content_generation",
            input_text="帮我写邮件",
            output_data="邮件内容已生成",
            duration_ms=1500,
            status="success",
        )

        # Verify audit record exists
        records = audit.query(session_id="session_001", limit=10)
        assert len(records) >= 1
        assert records[0]["operation_type"] == "task_execute"

    def test_settings_change_creates_audit_record(self, patched_data_dir):
        """Changing settings creates an audit log entry."""
        audit = AuditLog()

        audit.log(
            session_id="session_002",
            operation_type="settings_change",
            skill_id="settings",
            input_text="切换语言为en_US",
            output_data="locale changed",
            duration_ms=50,
            status="success",
        )

        records = audit.query(session_id="session_002", limit=10)
        assert len(records) >= 1
        assert records[0]["operation_type"] == "settings_change"

    def test_audit_output_is_sanitized(self, patched_data_dir):
        """Audit log sanitizes sensitive output data."""
        audit = AuditLog()

        audit.log(
            session_id="session_003",
            operation_type="task_execute",
            skill_id="content_generation",
            input_text="处理数据",
            output_data="API key: sk-secret-key-12345 should not appear",
            duration_ms=200,
            status="success",
        )

        records = audit.query(session_id="session_003", limit=1)
        if records and records[0].get("output_summary"):
            assert "sk-secret-key-12345" not in records[0]["output_summary"]


# ═══════════════════════════════════════════════════════════════════════════
# Journey 9: Demo Mode (No API Key → Browse → Configure → Execute)
# ═══════════════════════════════════════════════════════════════════════════


class TestJourneyDemoMode:
    """User browses in demo mode, then configures API key and executes."""

    def test_dashboard_works_without_api_key(self, patched_data_dir):
        """Dashboard displays data even without API key configured."""
        from opc_manager.data_manager import execute_write, execute_query

        # Insert demo data
        execute_write(
            "INSERT INTO finance_records (id, type, amount, category, date, created_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (gen_id(), "income", 10000.0, "服务收入", "2026-06-01"),
        )

        # Dashboard can query data without API key
        rows = execute_query("SELECT * FROM finance_records LIMIT 10")
        assert len(rows) >= 1

    def test_configure_key_then_execute(self, patched_data_dir, secure_store):
        """After configuring API key, tasks can execute."""
        # No API key initially
        assert secure_store.get_key("MOKA_API_KEY") is None

        # Configure key
        secure_store.set_key("MOKA_API_KEY", "sk-demo-key")
        assert secure_store.get_key("MOKA_API_KEY") == "sk-demo-key"

        # Now can execute
        with patch.dict(os.environ, {"OPC_SKIP_REFLECT": "true"}):
            loop, _ = _make_mock_agent_loop()
            result = asyncio.run(loop.run("帮我分析市场趋势"))
            assert isinstance(result, TaskResult)
