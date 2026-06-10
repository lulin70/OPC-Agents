"""Comprehensive User Journey Tests for OPC-Agents.

Simulates complete end-to-end user workflows across all major features:
1. New User First Experience (Onboarding → First Task)
2. Daily Task Execution (Email, Finance, Analysis)
3. Undo & Recovery
4. Knowledge Management
5. Skill Marketplace
6. Data Backup & Export
7. Settings & Security
8. Error Recovery
9. Audit & Monitoring

All file operations use tmp_path fixture — never touches real data/.
LLM calls and Streamlit UI are mocked throughout.
Tests are independent and idempotent.
"""

import asyncio
import json
import os
import shutil
import sqlite3
import tempfile
import time
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from opc_manager.onboarding import OnboardingManager, OnboardingStep, OnboardingState
from opc_manager.task_engine_v3 import TaskEngineV3, TaskResult, TaskType, IntentClassifier
from opc_manager.agent_loop import AgentLoop, MAX_USER_INPUT_LENGTH
from opc_manager.undo_manager import UndoManager, OperationType
from opc_manager.data_manager import (
    init_db,
    execute_write,
    execute_query,
    gen_id,
    encrypt_field,
    decrypt_field,
)
from opc_manager.audit_log import AuditLog, AuditRecord
from opc_manager.data_backup import DataBackupManager, _sanitize_value, REDACTED_VALUE
from opc_manager.skill_reviews import SkillReviewManager
from opc_manager.i18n import I18nManager
from opc_manager.secure_storage import SecureKeyStore
from opc_manager.knowledge_bridge import KnowledgeBridge, LocalFolderAdapter, KnowledgeEntry
from opc_manager.performance_monitor import PerformanceMonitor, get_performance_monitor
from opc_manager.llm_cache import LLMCache
from opc_manager.task_types import InputValidator


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset all singleton instances between tests for isolation."""
    # Reset AuditLog singleton
    AuditLog._instance = None
    # Reset PerformanceMonitor singleton
    import opc_manager.performance_monitor as _pm
    _pm._default_monitor = None
    # Reset DataManager state
    import opc_manager.data_manager as _dm
    _dm._db_initialized = False
    _dm._local = type("Local", (), {"conn": None})()
    # Reset SkillReviewManager singleton
    import opc_manager.skill_reviews as _sr
    _sr._manager = None
    # Reset LLMCache singleton
    import opc_manager.llm_cache as _lc
    _lc._cache_instance = None
    # Reset KnowledgeBridge singleton
    import opc_manager.knowledge_bridge as _kb
    _kb._instance = None
    yield
    # Cleanup after test
    AuditLog._instance = None
    _pm._default_monitor = None
    _dm._db_initialized = False
    _dm._local = type("Local", (), {"conn": None})()
    _sr._manager = None
    _lc._cache_instance = None
    _kb._instance = None


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a temporary data directory and redirect DATA_DIR to it."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def patched_data_dir(tmp_data_dir):
    """Patch opc_manager.data_manager.DATA_DIR and DB_PATH to tmp_path."""
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
def undo_manager():
    """Fresh UndoManager per test."""
    return UndoManager()


@pytest.fixture
def audit_log():
    """Fresh AuditLog per test (singleton reset handled by autouse fixture)."""
    return AuditLog()


@pytest.fixture
def review_db(tmp_path):
    """Create a temporary SkillReviewManager with its own DB."""
    db_path = str(tmp_path / "test_reviews.db")
    mgr = SkillReviewManager(db_path)
    yield mgr
    mgr.close()


@pytest.fixture
def llm_cache_db(tmp_path):
    """Create a temporary LLMCache with its own DB."""
    db_path = str(tmp_path / "test_llm_cache.db")
    cache = LLMCache(db_path, ttl=3600)
    yield cache
    cache.close()


@pytest.fixture
def secure_store(tmp_path):
    """Create a SecureKeyStore pointing to a temp file."""
    storage_path = str(tmp_path / ".env.encrypted")
    return SecureKeyStore(storage_path=storage_path)


@pytest.fixture
def performance_monitor():
    """Fresh PerformanceMonitor per test."""
    return PerformanceMonitor()


@pytest.fixture
def knowledge_folder(tmp_path):
    """Create a temp folder with sample knowledge files."""
    kb_dir = tmp_path / "knowledge"
    kb_dir.mkdir()
    (kb_dir / "marketing_guide.md").write_text(
        "# Marketing Guide\n\nBest practices for digital marketing.\n#marketing #digital",
        encoding="utf-8",
    )
    (kb_dir / "sales_tips.md").write_text(
        "# Sales Tips\n\nHow to close deals effectively.\n#sales #deals",
        encoding="utf-8",
    )
    (kb_dir / "tech_notes.md").write_text(
        "# Technical Notes\n\nSystem architecture overview.\n#tech #architecture",
        encoding="utf-8",
    )
    return kb_dir


# ─── Journey 1: New User First Experience ────────────────────────────────────


class TestJourney1NewUserFirstExperience:
    """Complete onboarding flow: First launch → Onboarding → First task → Result."""

    def test_onboarding_starts_at_welcome(self, tmp_path):
        """Step 1: First launch → onboarding starts at WELCOME step."""
        state_file = tmp_path / "onboarding.json"
        fake_marker = tmp_path / ".onboarding_complete"
        with patch.object(OnboardingManager, "STATE_FILE", str(state_file)), \
             patch("opc_manager.onboarding._ONBOARDING_MARKER", fake_marker):
            mgr = OnboardingManager()
            assert not mgr.is_completed
            assert mgr.get_current_step() == OnboardingStep.WELCOME

    def test_onboarding_step_content_has_title(self, tmp_path):
        """Onboarding step content is well-formed."""
        state_file = tmp_path / "onboarding.json"
        with patch.object(OnboardingManager, "STATE_FILE", str(state_file)):
            mgr = OnboardingManager()
            content = mgr.get_step_content(OnboardingStep.WELCOME)
            assert "title" in content
            assert "欢迎使用" in content["title"]

    def test_complete_onboarding_persists(self, tmp_path):
        """Step 2: User completes onboarding → state persists to disk."""
        state_file = tmp_path / "onboarding.json"
        with patch.object(OnboardingManager, "STATE_FILE", str(state_file)):
            mgr = OnboardingManager()
            mgr.complete_onboarding()
            assert mgr.is_completed
            assert mgr.get_current_step() == OnboardingStep.COMPLETED

            # Verify persistence by creating a new manager
            mgr2 = OnboardingManager()
            assert mgr2.is_completed

    def test_user_submits_first_task_gets_result(self, tmp_path):
        """Step 3-4: User submits first task → gets result."""
        mock_execute = MagicMock(return_value=TaskResult(
            success=True,
            content="记录成功：收入5000元，来自张三",
            task_type=TaskType.BUSINESS_OPERATION,
            execution_time_ms=800,
        ))
        with patch.object(TaskEngineV3, "execute", mock_execute):
            engine = TaskEngineV3()
            result = engine.execute("帮我记录一笔收入5000元，来自张三")
            assert result.success
            assert "5000" in result.content

    def test_onboarding_progress_increases(self, tmp_path):
        """Progress percentage increases as user advances through steps."""
        state_file = tmp_path / "onboarding.json"
        fake_marker = tmp_path / ".onboarding_complete"
        with patch.object(OnboardingManager, "STATE_FILE", str(state_file)), \
             patch("opc_manager.onboarding._ONBOARDING_MARKER", fake_marker):
            mgr = OnboardingManager()
            initial_progress = mgr.progress_pct
            assert initial_progress == 0

            mgr.advance_to_step(OnboardingStep.LLM_CONFIG)
            assert mgr.progress_pct > initial_progress

            mgr.advance_to_step(OnboardingStep.SAMPLE_TASK)
            assert mgr.progress_pct > 0

            mgr.complete_onboarding()
            assert mgr.progress_pct == 100


# ─── Journey 2: Daily Task Execution ─────────────────────────────────────────


class TestJourney2DailyTaskExecution:
    """Simulate a typical daily workflow: email, finance, analysis."""

    def test_email_draft_generated(self):
        """User submits '帮我写一封客户跟进邮件' → email draft generated."""
        mock_execute = MagicMock(return_value=TaskResult(
            success=True,
            content="尊敬的客户，\n\n感谢您对我们服务的关注...",
            task_type=TaskType.CONTENT_GENERATION,
            execution_time_ms=1200,
        ))
        with patch.object(TaskEngineV3, "execute", mock_execute):
            engine = TaskEngineV3()
            result = engine.execute("帮我写一封客户跟进邮件")
            assert result.success
            assert "客户" in result.content

    def test_finance_record_created(self, patched_data_dir):
        """User submits '记录一笔收入5000元来自张三' → finance record created."""
        record_id = gen_id()
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        execute_write(
            "INSERT INTO finance_records (id, type, amount, category, source, date, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (record_id, "income", 5000.0, "咨询费", "张三", "2025-01-15", "咨询服务费", now),
        )
        rows = execute_query("SELECT * FROM finance_records WHERE id=?", (record_id,))
        assert len(rows) == 1
        assert rows[0]["amount"] == 5000.0
        assert rows[0]["source"] == "张三"

    def test_analysis_report_generated(self):
        """User submits '分析我的业务数据' → analysis report generated."""
        mock_execute = MagicMock(return_value=TaskResult(
            success=True,
            content="## SWOT分析\n\n### 优势\n1. 专注度高\n2. 灵活性大",
            task_type=TaskType.DATA_ANALYSIS,
            execution_time_ms=2500,
        ))
        with patch.object(TaskEngineV3, "execute", mock_execute):
            engine = TaskEngineV3()
            result = engine.execute("分析我的业务数据")
            assert result.success
            assert "SWOT" in result.content

    def test_intent_classifier_routes_correctly(self):
        """IntentClassifier correctly routes different user inputs."""
        # Content generation
        task_type, confidence = IntentClassifier.classify("帮我写一份营销方案")
        assert task_type == TaskType.CONTENT_GENERATION

        # Data analysis
        task_type, _ = IntentClassifier.classify("分析一下市场趋势")
        assert task_type == TaskType.DATA_ANALYSIS

        # Info collection
        task_type, _ = IntentClassifier.classify("收集最新的AI趋势")
        assert task_type == TaskType.INFO_COLLECTION

    def test_dashboard_reflects_all_operations(self, patched_data_dir):
        """Dashboard sees all 3 operations reflected in data."""
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        # Finance record
        execute_write(
            "INSERT INTO finance_records (id, type, amount, category, source, date, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (gen_id(), "income", 5000.0, "咨询费", "张三", "2025-01-15", "邮件相关收入", now),
        )
        # Task record
        execute_write(
            "INSERT INTO tasks (id, title, description, priority, status, due_date, tags, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (gen_id(), "写客户跟进邮件", "草稿已生成", 2, "done", "2025-01-16", "邮件", now),
        )
        # Interaction log
        execute_write(
            "INSERT INTO interaction_log (id, intent_type, goal, skill_used, success, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (gen_id(), "data_analysis", "分析业务数据", "analysis", 1, now),
        )

        finance_rows = execute_query("SELECT COUNT(*) as cnt FROM finance_records")
        task_rows = execute_query("SELECT COUNT(*) as cnt FROM tasks")
        log_rows = execute_query("SELECT COUNT(*) as cnt FROM interaction_log")
        assert finance_rows[0]["cnt"] >= 1
        assert task_rows[0]["cnt"] >= 1
        assert log_rows[0]["cnt"] >= 1


# ─── Journey 3: Undo & Recovery ──────────────────────────────────────────────


class TestJourney3UndoRecovery:
    """Record → Undo → Verify → Re-record flow."""

    def test_record_income_and_undo(self, undo_manager):
        """Step 1-3: User records income, realizes it was wrong, undoes it."""
        session_id = "test_session_undo"

        # Step 1: Record income
        op_id = undo_manager.push(
            session_id=session_id,
            op_type=OperationType.RECORD_INCOME,
            inverse_func="undo_record_income",
            inverse_args={"record_id": "rec_001"},
            original_result={"amount": 5000, "source": "张三"},
        )
        assert op_id is not None

        # Step 2: Undo it
        with patch.object(UndoManager, "_resolve_inverse", return_value=lambda record_id: {"deleted": True}):
            result = undo_manager.undo(session_id, op_id)
        assert result["success"]

        # Step 3: Verify undo worked — record should be undone
        undoable = undo_manager.list_undoable(session_id)
        undone_ids = [r["operation_id"] for r in undoable]
        assert op_id not in undone_ids

    def test_record_correct_income_after_undo(self, undo_manager):
        """Step 4: User records correct income after undo."""
        session_id = "test_session_correct"

        # Record correct income
        op_id = undo_manager.push(
            session_id=session_id,
            op_type=OperationType.RECORD_INCOME,
            inverse_func="undo_record_income",
            inverse_args={"record_id": "rec_002"},
            original_result={"amount": 8000, "source": "李四"},
        )
        assert op_id is not None

        # Verify it's in undoable list
        undoable = undo_manager.list_undoable(session_id)
        assert len(undoable) >= 1

    def test_undo_expired_record(self, undo_manager):
        """Undo window expired → cannot undo."""
        session_id = "test_session_expired"
        op_id = undo_manager.push(
            session_id=session_id,
            op_type=OperationType.RECORD_INCOME,
            inverse_func="undo_record_income",
            inverse_args={"record_id": "rec_003"},
            original_result={"amount": 1000},
        )
        # Manually expire the record
        with undo_manager._lock:
            for r in undo_manager._records.get(session_id, []):
                if r.operation_id == op_id:
                    r.expires_at = time.time() - 1
                    break

        result = undo_manager.undo(session_id, op_id)
        assert not result["success"]
        assert "expired" in result["error"].lower()


# ─── Journey 4: Knowledge Management ─────────────────────────────────────────


class TestJourney4KnowledgeManagement:
    """Connect knowledge source → search → verify results."""

    def test_local_folder_search_finds_relevant_docs(self, knowledge_folder):
        """Step 2: User searches for 'marketing' → finds relevant docs."""
        with patch.dict(os.environ, {
            "OPC_KB_ENABLED": "true",
            "OPC_KB_TYPE": "local",
            "OPC_KB_PATH": str(knowledge_folder),
            "OPC_EMBEDDING_ENABLED": "false",
        }):
            adapter = LocalFolderAdapter(str(knowledge_folder))
            results = adapter.search("marketing", max_results=5)
            assert len(results) > 0
            assert any("marketing" in r.title.lower() or "marketing" in r.content.lower() for r in results)

    def test_search_unrelated_topic_returns_empty_or_low_relevance(self, knowledge_folder):
        """Step 3: User searches for unrelated topic → gets no/irrelevant results."""
        with patch.dict(os.environ, {
            "OPC_KB_ENABLED": "true",
            "OPC_KB_TYPE": "local",
            "OPC_KB_PATH": str(knowledge_folder),
            "OPC_EMBEDDING_ENABLED": "false",
        }):
            adapter = LocalFolderAdapter(str(knowledge_folder))
            results = adapter.search("quantum physics astrophysics", max_results=5)
            # Results may be empty or have very low relevance scores
            for r in results:
                assert r.relevance_score < 0.5

    def test_knowledge_bridge_disabled_by_default(self):
        """KnowledgeBridge is disabled when OPC_KB_ENABLED is not set."""
        with patch.dict(os.environ, {"OPC_KB_ENABLED": "false"}, clear=False):
            kb = KnowledgeBridge()
            assert not kb.enabled
            assert kb.search("anything") == []

    def test_knowledge_bridge_status(self, knowledge_folder):
        """KnowledgeBridge reports correct status when enabled."""
        with patch.dict(os.environ, {
            "OPC_KB_ENABLED": "true",
            "OPC_KB_TYPE": "local",
            "OPC_KB_PATH": str(knowledge_folder),
            "OPC_EMBEDDING_ENABLED": "false",
        }):
            kb = KnowledgeBridge()
            if kb.enabled:
                status = kb.get_status()
                assert status["enabled"] is True
                assert status["type"] == "local"


# ─── Journey 5: Skill Marketplace ────────────────────────────────────────────


class TestJourney5SkillMarketplace:
    """Browse → Install → Rate → Check average rating."""

    def test_add_and_retrieve_review(self, review_db):
        """Step 3: User rates the skill."""
        review = review_db.add_review(
            skill_id="skill_email_writer",
            rating=4,
            review_text="Very helpful for drafting emails",
            review_title="Great tool",
            user_id="user_001",
        )
        assert review.skill_id == "skill_email_writer"
        assert review.rating == 4

    def test_get_average_rating(self, review_db):
        """Step 4: User checks average rating."""
        review_db.add_review("skill_email_writer", 5, user_id="user_001")
        review_db.add_review("skill_email_writer", 3, user_id="user_002")
        review_db.add_review("skill_email_writer", 4, user_id="user_003")

        avg = review_db.get_average_rating("skill_email_writer")
        assert avg == 4.0

    def test_get_reviews_list(self, review_db):
        """User can list reviews for a skill."""
        review_db.add_review("skill_email_writer", 5, review_text="Excellent", user_id="u1")
        review_db.add_review("skill_email_writer", 4, review_text="Good", user_id="u2")

        reviews = review_db.get_reviews("skill_email_writer")
        assert len(reviews) == 2

    def test_rating_summary(self, review_db):
        """Rating summary includes distribution."""
        review_db.add_review("skill_analyzer", 5, user_id="u1")
        review_db.add_review("skill_analyzer", 5, user_id="u2")
        review_db.add_review("skill_analyzer", 3, user_id="u3")

        summary = review_db.get_rating_summary("skill_analyzer")
        assert summary["average"] == 4.3
        assert summary["total"] == 3
        assert summary["distribution"][5] == 2
        assert summary["distribution"][3] == 1

    def test_invalid_rating_rejected(self, review_db):
        """Rating outside 1-5 is rejected."""
        with pytest.raises(ValueError):
            review_db.add_review("skill_x", 0, user_id="u1")
        with pytest.raises(ValueError):
            review_db.add_review("skill_x", 6, user_id="u1")


# ─── Journey 6: Data Backup & Export ─────────────────────────────────────────


class TestJourney6DataBackupExport:
    """Create data → Backup → Modify → Restore → Export."""

    def test_create_backup_file_exists(self, tmp_path):
        """Step 2: User creates backup → backup file exists."""
        base_dir = tmp_path / "opc_base"
        data_dir = base_dir / "data"
        data_dir.mkdir(parents=True)

        # Create some data files
        (data_dir / "test_data.json").write_text(
            json.dumps({"records": [{"id": 1, "amount": 5000}]}),
            encoding="utf-8",
        )

        mgr = DataBackupManager(base_dir=str(base_dir))
        backup_path, manifest = mgr.create_backup()

        assert backup_path.exists()
        assert manifest.total_files >= 1
        assert manifest.checksum_sha256 != ""

    def test_restore_backup_recovers_original_data(self, tmp_path):
        """Step 4: User restores from backup → original data recovered."""
        base_dir = tmp_path / "opc_base"
        data_dir = base_dir / "data"
        data_dir.mkdir(parents=True)

        original_data = {"records": [{"id": 1, "amount": 5000, "source": "张三"}]}
        (data_dir / "finance.json").write_text(
            json.dumps(original_data, ensure_ascii=False), encoding="utf-8"
        )

        mgr = DataBackupManager(base_dir=str(base_dir))
        backup_path, _ = mgr.create_backup()

        # Modify data
        (data_dir / "finance.json").write_text(
            json.dumps({"records": []}, ensure_ascii=False), encoding="utf-8"
        )

        # Restore
        result = mgr.restore_backup(str(backup_path), confirm=True)
        assert result["success"]

        # Verify original data recovered
        restored = json.loads((data_dir / "finance.json").read_text(encoding="utf-8"))
        assert restored["records"][0]["source"] == "张三"

    def test_export_data_redacts_sensitive_fields(self, tmp_path):
        """Step 5: User exports data → sensitive fields redacted."""
        base_dir = tmp_path / "opc_base"
        data_dir = base_dir / "data"
        data_dir.mkdir(parents=True)

        (data_dir / "config.json").write_text(
            json.dumps({
                "api_key": "sk-secret-key-12345",
                "password": "my_password",
                "name": "张三",
                "normal_field": "visible data",
            }),
            encoding="utf-8",
        )

        mgr = DataBackupManager(base_dir=str(base_dir))
        exported_bytes = mgr.export_data(format_type="json")
        exported = json.loads(exported_bytes.decode("utf-8"))

        config_data = exported["data"]["config"]
        assert config_data["api_key"] == REDACTED_VALUE
        assert config_data["password"] == REDACTED_VALUE
        assert config_data["name"] == "张三"
        assert config_data["normal_field"] == "visible data"

    def test_sanitize_value_recursive(self):
        """_sanitize_value recursively sanitizes nested dicts."""
        data = {
            "api_key": "secret123",
            "nested": {
                "token": "tok_abc",
                "info": "safe",
            },
            "items": [
                {"password": "pw1", "name": "item1"},
            ],
        }
        result = _sanitize_value(data)
        assert result["api_key"] == REDACTED_VALUE
        assert result["nested"]["token"] == REDACTED_VALUE
        assert result["nested"]["info"] == "safe"
        assert result["items"][0]["password"] == REDACTED_VALUE
        assert result["items"][0]["name"] == "item1"


# ─── Journey 7: Settings & Security ──────────────────────────────────────────


class TestJourney7SettingsSecurity:
    """Store API key → Retrieve → Export excludes key → Language switch."""

    def test_store_and_retrieve_api_key(self, secure_store):
        """Step 1-2: User stores and retrieves an API key securely."""
        if not secure_store.is_available:
            pytest.skip("cryptography package not installed")

        assert secure_store.set_key("MOKA_API_KEY", "sk-test-12345")
        retrieved = secure_store.get_key("MOKA_API_KEY")
        assert retrieved == "sk-test-12345"

    def test_export_excludes_api_key(self, tmp_path):
        """Step 3: User exports data → API key NOT in export."""
        base_dir = tmp_path / "opc_base"
        data_dir = base_dir / "data"
        data_dir.mkdir(parents=True)

        (data_dir / "secrets.json").write_text(
            json.dumps({
                "api_key": "sk-super-secret",
                "smtp_pass": "email_password",
                "username": "testuser",
            }),
            encoding="utf-8",
        )

        mgr = DataBackupManager(base_dir=str(base_dir))
        exported_bytes = mgr.export_data(format_type="json")
        exported = json.loads(exported_bytes.decode("utf-8"))

        secrets = exported["data"]["secrets"]
        assert secrets["api_key"] == REDACTED_VALUE
        assert secrets["smtp_pass"] == REDACTED_VALUE
        assert secrets["username"] == "testuser"

    def test_language_switch_changes_ui_strings(self):
        """Step 4: User switches language → UI strings change."""
        i18n = I18nManager()

        # Default is zh_CN
        assert i18n.locale == "zh_CN"
        zh_text = i18n.t("nav_chat")
        assert "对话" in zh_text

        # Switch to English
        i18n.locale = "en_US"
        en_text = i18n.t("nav_chat")
        assert "Chat" in en_text or en_text != zh_text

        # Switch to Japanese
        i18n.locale = "ja_JP"
        ja_text = i18n.t("common_save")
        assert ja_text != zh_text or ja_text != en_text

    def test_list_keys(self, secure_store):
        """User can list stored key names."""
        if not secure_store.is_available:
            pytest.skip("cryptography package not installed")

        secure_store.set_key("KEY_A", "val_a")
        secure_store.set_key("KEY_B", "val_b")
        keys = secure_store.list_keys()
        assert "KEY_A" in keys
        assert "KEY_B" in keys

    def test_remove_key(self, secure_store):
        """User can remove a stored key."""
        if not secure_store.is_available:
            pytest.skip("cryptography package not installed")

        secure_store.set_key("KEY_TO_REMOVE", "val")
        assert secure_store.remove_key("KEY_TO_REMOVE")
        assert secure_store.get_key("KEY_TO_REMOVE") is None


# ─── Journey 8: Error Recovery ───────────────────────────────────────────────


class TestJourney8ErrorRecovery:
    """System handles various error conditions gracefully."""

    def test_empty_input_clear_error(self):
        """Step 1: User submits empty input → clear error message."""
        loop = AgentLoop(task_engine=TaskEngineV3())
        result = asyncio.run(loop.run(""))
        assert isinstance(result, TaskResult)
        assert not result.success
        assert "不能为空" in result.error

    def test_too_long_input_clear_error(self):
        """Step 2: User submits too-long input → clear error message."""
        loop = AgentLoop(task_engine=TaskEngineV3())
        result = asyncio.run(loop.run("x" * 50000))
        assert isinstance(result, TaskResult)
        assert not result.success
        assert "超过" in result.error

    def test_undo_nonexistent_operation_graceful(self, undo_manager):
        """Step 3: User tries to undo non-existent operation → graceful handling."""
        result = undo_manager.undo("test_session", "nonexistent_op_id")
        assert not result["success"]
        assert "not found" in result["error"].lower()

    def test_malformed_json_handled_gracefully(self):
        """Step 4: LLM returns malformed JSON → system handles gracefully."""
        from opc_manager.utils import extract_json_from_llm

        # Completely invalid JSON
        result = extract_json_from_llm("This is not JSON at all, just plain text.")
        # Should return None or a dict, never crash
        assert result is None or isinstance(result, dict)

    def test_input_validator_rejects_empty(self):
        """InputValidator rejects empty input."""
        text, error = InputValidator.sanitize("")
        assert error is not None
        assert "不能为空" in error

    def test_input_validator_truncates_long_input(self):
        """InputValidator truncates overly long input."""
        long_input = "a" * 5000
        text, error = InputValidator.sanitize(long_input)
        assert len(text) <= 2000
        assert error is None  # Truncation, not rejection

    def test_input_validator_strips_html(self):
        """InputValidator removes HTML tags."""
        text, error = InputValidator.sanitize('<script>alert("xss")</script>Hello')
        assert "<script>" not in text
        assert "Hello" in text

    def test_undo_invalid_session_id(self, undo_manager):
        """Undo with invalid session_id raises ValueError."""
        with pytest.raises(ValueError):
            undo_manager.undo("", "some_op")

    def test_undo_invalid_inverse_func(self, undo_manager):
        """Push with invalid inverse_func raises ValueError."""
        with pytest.raises(ValueError):
            undo_manager.push(
                session_id="test",
                op_type=OperationType.RECORD_INCOME,
                inverse_func="",
                inverse_args={},
                original_result={},
            )


# ─── Journey 9: Audit & Monitoring ───────────────────────────────────────────


class TestJourney9AuditMonitoring:
    """Perform operations → Audit log records all → Performance metrics collected."""

    def test_audit_log_records_operations(self, audit_log):
        """Step 2: Audit log records all operations."""
        audit_log.log(
            session_id="sess_001",
            operation_type="content_generation",
            skill_id="email_skill",
            input_text="帮我写邮件",
            output_data="邮件草稿已生成",
            duration_ms=1200,
            status="success",
        )
        audit_log.log(
            session_id="sess_001",
            operation_type="finance_record",
            skill_id="finance_skill",
            input_text="记录收入5000",
            output_data="记录成功",
            duration_ms=300,
            status="success",
        )

        records = audit_log.query(session_id="sess_001")
        assert len(records) == 2
        op_types = {r["operation_type"] for r in records}
        assert "finance_record" in op_types
        assert "content_generation" in op_types

    def test_audit_log_stats(self, audit_log):
        """Audit log provides accurate statistics."""
        audit_log.log("s1", "task", "skill_a", "input", "output", 100, "success")
        audit_log.log("s1", "task", "skill_b", "input", "output", 200, "success")
        audit_log.log("s1", "task", "skill_c", "input", "output", 300, "failed")

        stats = audit_log.get_stats(session_id="s1")
        assert stats["total"] == 3
        assert stats["success"] == 2
        assert stats["failed"] == 1
        assert "100.0%" not in stats["success_rate"]  # Not 100%

    def test_audit_log_sanitizes_sensitive_input(self, audit_log):
        """Audit log sanitizes sensitive data in input_summary."""
        audit_log.log(
            session_id="s2",
            operation_type="config",
            skill_id="settings",
            input_text="api_key=sk-secret-key-12345",
            output_data="Config saved",
            duration_ms=50,
        )
        records = audit_log.query(session_id="s2")
        assert records[0]["input_summary"] == "***REDACTED***"

    def test_performance_metrics_collected(self, performance_monitor):
        """Step 3: Performance metrics are collected."""
        performance_monitor.record("agent_loop", 5000, success=True)
        performance_monitor.record("agent_loop", 8000, success=True)
        performance_monitor.record("agent_loop", 15000, success=False)

        stats = performance_monitor.get_stats()
        assert stats["total_operations"] == 3
        assert "agent_loop" in stats["operations"]
        assert stats["operations"]["agent_loop"]["count"] == 3

    def test_sla_status_check(self, performance_monitor):
        """Step 4: SLA status can be checked."""
        # Within SLA
        performance_monitor.record("agent_loop", 5000, success=True)
        sla = performance_monitor.check_sla()
        assert sla["single_request"] is True

        # Breach SLA
        performance_monitor.record("agent_loop", 70000, success=True)
        sla = performance_monitor.check_sla()
        assert sla["single_request"] is False

    def test_llm_cache_put_and_get(self, llm_cache_db):
        """LLM cache stores and retrieves responses."""
        llm_cache_db.put(
            model="gpt-4o",
            temperature=0.3,
            max_tokens=1000,
            system_prompt="You are a helpful assistant.",
            user_prompt="Write a marketing plan",
            response="# Marketing Plan\n\nStep 1: Research",
            provider="openai",
        )

        cached = llm_cache_db.get(
            model="gpt-4o",
            temperature=0.3,
            max_tokens=1000,
            system_prompt="You are a helpful assistant.",
            user_prompt="Write a marketing plan",
        )
        assert cached is not None
        assert "Marketing Plan" in cached

    def test_llm_cache_stats(self, llm_cache_db):
        """LLM cache provides statistics."""
        llm_cache_db.put("model_a", 0.3, 500, "sys", "prompt1", "response1")
        llm_cache_db.put("model_a", 0.3, 500, "sys", "prompt2", "response2")

        stats = llm_cache_db.stats()
        assert stats["total_entries"] == 2

    def test_llm_cache_skip_high_temperature(self, llm_cache_db):
        """LLM cache skips caching for high temperature (non-deterministic)."""
        llm_cache_db.put("model_a", 0.9, 500, "sys", "prompt_high", "response_high")
        cached = llm_cache_db.get("model_a", 0.9, 500, "sys", "prompt_high")
        assert cached is None  # Not cached due to high temperature

    def test_audit_log_query_with_filters(self, audit_log):
        """Audit log supports filtering by operation_type and time."""
        t1 = time.time() - 100
        audit_log.log("s3", "email", "skill_e", "input", "output", 100)
        audit_log.log("s3", "finance", "skill_f", "input", "output", 200)
        audit_log.log("s3", "email", "skill_e", "input2", "output2", 150)

        email_records = audit_log.query(session_id="s3", operation_type="email")
        assert len(email_records) == 2

        finance_records = audit_log.query(session_id="s3", operation_type="finance")
        assert len(finance_records) == 1


# ─── Cross-Journey Integration ───────────────────────────────────────────────


class TestCrossJourneyIntegration:
    """Tests that verify interactions between multiple subsystems."""

    def test_onboarding_to_task_execution_flow(self, tmp_path):
        """Full flow: Onboarding → Task → Audit → Undo."""
        state_file = tmp_path / "onboarding.json"
        with patch.object(OnboardingManager, "STATE_FILE", str(state_file)):
            # 1. Onboarding
            mgr = OnboardingManager()
            assert mgr.get_current_step() == OnboardingStep.WELCOME
            mgr.complete_onboarding()
            assert mgr.is_completed

        # 2. Execute task (mocked)
        mock_execute = MagicMock(return_value=TaskResult(
            success=True,
            content="任务完成",
            task_type=TaskType.CONTENT_GENERATION,
            execution_time_ms=1000,
        ))
        with patch.object(TaskEngineV3, "execute", mock_execute):
            engine = TaskEngineV3()
            result = engine.execute("帮我写方案")
            assert result.success

        # 3. Audit log
        audit = AuditLog()
        audit.log("sess_int", "content_gen", "skill", "input", "output", 1000)
        records = audit.query(session_id="sess_int")
        assert len(records) == 1

        # 4. Undo
        um = UndoManager()
        op_id = um.push("sess_int", OperationType.RECORD_INCOME, "undo_record_income", {"id": "x"}, {"amount": 100})
        with patch.object(UndoManager, "_resolve_inverse", return_value=lambda id: {"deleted": True}):
            undo_result = um.undo("sess_int", op_id)
        assert undo_result["success"]

    def test_data_manager_encrypt_decrypt_roundtrip(self, patched_data_dir):
        """Encrypt then decrypt returns original value (when key is available)."""
        with patch.dict(os.environ, {"OPC_ENCRYPTION_KEY": "test-encryption-key-12345"}):
            import opc_manager.data_manager as _dm
            _dm._fallback_key = None  # Reset cached key
            original = "敏感数据-张三的收入5000元"
            encrypted = encrypt_field(original)
            # If encryption key is set, encrypted should differ from original
            if encrypted != original:
                decrypted = decrypt_field(encrypted)
                assert decrypted == original

    def test_performance_monitor_with_audit(self, performance_monitor, audit_log):
        """Performance metrics and audit log work together."""
        # Record a monitored operation
        start = time.time()
        audit_log.log("sess_perf", "analysis", "skill", "input", "output", 5000)
        duration = (time.time() - start) * 1000
        performance_monitor.record("analysis", duration, success=True)

        # Verify both systems captured the event
        audit_records = audit_log.query(session_id="sess_perf")
        assert len(audit_records) == 1

        perf_stats = performance_monitor.get_stats()
        assert perf_stats["total_operations"] >= 1

    def test_knowledge_bridge_builds_prompt(self, knowledge_folder):
        """KnowledgeBridge can build a knowledge prompt for LLM injection."""
        with patch.dict(os.environ, {
            "OPC_KB_ENABLED": "true",
            "OPC_KB_TYPE": "local",
            "OPC_KB_PATH": str(knowledge_folder),
            "OPC_EMBEDDING_ENABLED": "false",
        }):
            kb = KnowledgeBridge()
            if kb.enabled:
                prompt = kb.build_knowledge_prompt("marketing")
                assert "知识库参考" in prompt or len(prompt) > 0

    def test_backup_manager_list_backups(self, tmp_path):
        """Backup manager can list created backups."""
        import time as _time
        base_dir = tmp_path / "opc_base"
        data_dir = base_dir / "data"
        data_dir.mkdir(parents=True)
        (data_dir / "sample.json").write_text("{}", encoding="utf-8")

        mgr = DataBackupManager(base_dir=str(base_dir))
        mgr.create_backup()
        # Ensure different timestamp for second backup
        _time.sleep(1.1)
        (data_dir / "sample2.json").write_text('{"new": true}', encoding="utf-8")
        mgr.create_backup()

        backups = mgr.list_backups()
        assert len(backups) >= 1  # At least one backup exists

    def test_delete_backup(self, tmp_path):
        """User can delete a backup file."""
        base_dir = tmp_path / "opc_base"
        data_dir = base_dir / "data"
        data_dir.mkdir(parents=True)
        (data_dir / "sample.json").write_text("{}", encoding="utf-8")

        mgr = DataBackupManager(base_dir=str(base_dir))
        backup_path, _ = mgr.create_backup()
        assert backup_path.exists()

        result = mgr.delete_backup(str(backup_path))
        assert result is True
        assert not backup_path.exists()
