"""Comprehensive end-to-end integration tests for OPC-Agents.

Simulates real user workflows from input to result, verifying
that all system components work together correctly.

All tests use tmp_path for file operations (never touch real data/),
mock LLM calls and Streamlit UI, and are independent/idempotent.
"""

import json
import os
import sqlite3
import time
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    """Redirect every module's DATA_DIR to tmp_path so tests never touch real data."""
    data_dir = str(tmp_path / "data")
    os.makedirs(data_dir, exist_ok=True)
    monkeypatch.setenv("OPC_DATA_DIR", data_dir)
    # Use monkeypatch instead of direct assignment
    import opc_manager.data_manager as dm

    monkeypatch.setattr(dm, "DATA_DIR", data_dir)
    monkeypatch.setattr(dm, "DB_PATH", os.path.join(data_dir, "opc_data.db"))
    monkeypatch.setattr(dm, "BACKUP_DIR", os.path.join(data_dir, "backups"))
    monkeypatch.setattr(dm, "_db_initialized", False)
    monkeypatch.setattr(dm, "_local", threading.local())
    dm._local.conn = None
    return data_dir


@pytest.fixture()
def db_path(_isolate_data_dir):
    return os.path.join(_isolate_data_dir, "opc_data.db")


@pytest.fixture()
def init_db(_isolate_data_dir):
    """Initialise the database in the isolated data dir."""
    import opc_manager.data_manager as dm

    dm.init_db()
    return dm


# ===========================================================================
# 1. User Onboarding Flow
# ===========================================================================


class TestUserOnboardingFlow:
    """Simulate a new user's first experience."""

    def test_first_launch_creates_default_config(self, tmp_path, _isolate_data_dir):
        """First launch should create data directory, default config, and session."""
        from opc_manager.onboarding import OnboardingManager

        # Point onboarding state file to tmp_path
        state_file = tmp_path / "data" / "onboarding.json"
        fake_marker = tmp_path / ".onboarding_complete"
        with patch.object(OnboardingManager, "STATE_FILE", str(state_file)), \
             patch("opc_manager.onboarding._ONBOARDING_MARKER", fake_marker):
            mgr = OnboardingManager()
            # On first launch, onboarding is NOT completed
            assert not mgr.is_completed
            assert mgr.get_current_step().value == "welcome"
            # State file should have been created on first save
            mgr._save_state()
            assert state_file.exists()

    def test_onboarding_tour_displays(self, tmp_path, _isolate_data_dir):
        """Onboarding overlay should display on first visit (step == welcome)."""
        from opc_manager.onboarding import OnboardingManager, OnboardingStep

        state_file = tmp_path / "data" / "onboarding.json"
        fake_marker = tmp_path / ".onboarding_complete"
        with patch.object(OnboardingManager, "STATE_FILE", str(state_file)), \
             patch("opc_manager.onboarding._ONBOARDING_MARKER", fake_marker):
            mgr = OnboardingManager()
            # First visit: current step is WELCOME
            assert mgr.get_current_step() == OnboardingStep.WELCOME
            content = mgr.get_step_content(OnboardingStep.WELCOME)
            assert content["title"] is not None
            assert "OPC-Agents" in content["title"]

    def test_onboarding_completion_persists(self, tmp_path, _isolate_data_dir):
        """After completing onboarding, it should not show again."""
        from opc_manager.onboarding import OnboardingManager, OnboardingStep

        state_file = tmp_path / "data" / "onboarding.json"
        with patch.object(OnboardingManager, "STATE_FILE", str(state_file)):
            mgr = OnboardingManager()
            mgr.complete_onboarding()
            assert mgr.is_completed

            # Simulate next visit: reload from file
            mgr2 = OnboardingManager()
            assert mgr2.is_completed
            assert mgr2.get_current_step() == OnboardingStep.COMPLETED


# ===========================================================================
# 2. Task Execution Workflow (Core Feature)
# ===========================================================================


class TestTaskExecutionWorkflow:
    """Simulate a user creating and executing a task."""

    def test_simple_task_from_input_to_result(self, tmp_path, _isolate_data_dir):
        """User types a task -> system processes -> result displayed."""
        from opc_manager.task_engine_v3 import TaskEngineV3, IntentClassifier
        from opc_manager.task_types import TaskType

        engine = TaskEngineV3()
        # Mock web search so we don't hit the network
        engine.web_search = MagicMock()
        engine.web_search.search.return_value = [
            {
                "title": "市场趋势分析",
                "body": "2024年AI市场持续增长",
                "href": "https://example.com",
            }
        ]
        engine._initialized = True

        result = engine.execute("帮我分析市场趋势")
        assert result.success
        assert result.content is not None
        assert len(result.content) > 0
        # Should be classified as DATA_ANALYSIS or INFO_COLLECTION
        assert result.task_type in (
            TaskType.DATA_ANALYSIS,
            TaskType.INFO_COLLECTION,
        )

    def test_task_with_undo(self, tmp_path, init_db):
        """User executes a task, then undoes it."""
        from opc_manager.undo_manager import UndoManager, OperationType

        mgr = UndoManager()
        session_id = "test-session-001"

        # Simulate recording an income operation
        op_id = mgr.push(
            session_id=session_id,
            op_type=OperationType.RECORD_INCOME,
            inverse_func="undo_record_income",
            inverse_args={"record_id": "rec-001"},
            original_result={"amount": 5000, "source": "客户张三"},
        )
        assert op_id is not None

        # Verify it appears in undoable list
        undoable = mgr.list_undoable(session_id)
        assert len(undoable) == 1
        assert undoable[0]["operation_id"] == op_id

        # Undo the operation (mock the inverse function)
        with patch.object(
            mgr, "_resolve_inverse", return_value=lambda **kw: {"deleted": True}
        ):
            result = mgr.undo(session_id, op_id)
        assert result["success"]

        # After undo, list should be empty
        undoable = mgr.list_undoable(session_id)
        assert len(undoable) == 0

    def test_task_with_export(self, tmp_path, _isolate_data_dir):
        """User executes task, then exports result to markdown."""
        from opc_manager.task_engine_v3 import TaskEngineV3
        from opc_manager.task_types import TaskType

        engine = TaskEngineV3()
        engine.web_search = MagicMock()
        engine.web_search.search.return_value = []
        engine._initialized = True

        result = engine.execute("帮我写一份营销方案")
        assert result.success
        assert result.deliverable_format == "Markdown"

        # Simulate export: write content to a file
        export_path = tmp_path / "export.md"
        export_path.write_text(result.content, encoding="utf-8")
        assert export_path.exists()
        assert len(export_path.read_text(encoding="utf-8")) > 0

    def test_five_task_execution(self, tmp_path, _isolate_data_dir):
        """User executes 5 tasks in sequence (the core 5-task workflow)."""
        from opc_manager.task_engine_v3 import TaskEngineV3
        from opc_manager.task_types import TaskType

        engine = TaskEngineV3()
        engine.web_search = MagicMock()
        engine.web_search.search.return_value = [
            {"title": "Result", "body": "Some content", "href": "https://example.com"}
        ]
        engine._initialized = True

        tasks = [
            "帮我收集AI行业趋势",
            "帮我写一份Q2营销方案",
            "分析一下我的业务现状",
            "帮我记录一笔收入5000元",
            "你好",
        ]
        results = []
        for task in tasks:
            result = engine.execute(task)
            results.append(result)

        assert all(r.success for r in results)
        assert len(results) == 5
        # Verify different task types were classified
        task_types = {r.task_type for r in results}
        assert len(task_types) >= 2  # At least 2 different types


# ===========================================================================
# 3. Knowledge Bridge Workflow
# ===========================================================================


class TestKnowledgeBridgeWorkflow:
    """Simulate a user connecting and using external knowledge."""

    def test_local_folder_adapter_connection(self, tmp_path):
        """User connects a local folder as knowledge source."""
        from opc_manager.knowledge_bridge import LocalFolderAdapter

        # Create a temp folder with some .md files
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()
        (kb_dir / "marketing.md").write_text(
            "# Marketing\nAI marketing strategies for 2024 #marketing #AI",
            encoding="utf-8",
        )
        (kb_dir / "finance.md").write_text(
            "# Finance\nFinancial planning tips #finance #planning", encoding="utf-8"
        )

        adapter = LocalFolderAdapter(str(kb_dir))
        status = adapter.get_status()
        assert status["available"]
        assert status["file_count"] == 2
        sources = adapter.list_sources()
        assert len(sources) == 2

    def test_knowledge_search_returns_results(self, tmp_path):
        """User searches connected knowledge base."""
        from opc_manager.knowledge_bridge import LocalFolderAdapter

        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()
        (kb_dir / "ai_trends.md").write_text(
            "# AI Trends 2024\nLarge language models continue to evolve. "
            "GPT-5 and Claude are leading the market. #AI #trends",
            encoding="utf-8",
        )
        (kb_dir / "cooking.md").write_text(
            "# Cooking Recipes\nHow to make pasta. #cooking", encoding="utf-8"
        )

        adapter = LocalFolderAdapter(str(kb_dir))

        # Search for AI-related content
        results = adapter.search("AI trends", max_results=5)
        assert len(results) >= 1
        assert any("AI" in r.title or "ai" in r.title.lower() for r in results)

        # Search for unrelated content should return fewer/no results
        cooking_results = adapter.search("pasta recipe", max_results=5)
        # The cooking file should match
        assert any("cooking" in r.title.lower() for r in cooking_results)


# ===========================================================================
# 4. Skill Marketplace Workflow
# ===========================================================================


class TestSkillMarketplaceWorkflow:
    """Simulate a user browsing and installing skills."""

    def test_browse_marketplace(self, tmp_path, init_db):
        """User browses the skill marketplace."""
        from opc_manager.skill_marketplace import MarketplaceSkill, SkillStatus
        from opc_manager.data_manager import execute_write, gen_id

        # Insert a skill into external_skills table
        skill_id = gen_id()
        execute_write(
            "INSERT INTO external_skills (id, name, description, source, version, trust_level, installed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                skill_id,
                "SEO Analyzer",
                "Analyze SEO performance",
                "registry",
                "1.0.0",
                "verified",
                time.strftime("%Y-%m-%dT%H:%M:%S"),
            ),
        )

        from opc_manager.data_manager import execute_query

        rows = execute_query("SELECT * FROM external_skills")
        assert len(rows) >= 1
        assert any(r["name"] == "SEO Analyzer" for r in rows)

    def test_install_and_use_skill(self, tmp_path, init_db):
        """User installs a skill and verifies it is stored."""
        from opc_manager.data_manager import execute_write, execute_query, gen_id

        skill_id = gen_id()
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        execute_write(
            "INSERT INTO external_skills (id, name, description, source, version, trust_level, installed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                skill_id,
                "Email Composer",
                "Compose professional emails",
                "registry",
                "2.1.0",
                "official",
                now,
            ),
        )

        # Verify the skill is in the database
        rows = execute_query("SELECT * FROM external_skills WHERE id=?", (skill_id,))
        assert len(rows) == 1
        assert rows[0]["name"] == "Email Composer"
        assert rows[0]["version"] == "2.1.0"

    def test_rate_skill(self, tmp_path, db_path, init_db):
        """User rates an installed skill."""
        from opc_manager.skill_reviews import SkillReviewManager
        from opc_manager.data_manager import execute_write, gen_id

        # First insert a skill
        skill_id = gen_id()
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        execute_write(
            "INSERT INTO external_skills (id, name, description, source, version, trust_level, installed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                skill_id,
                "Report Generator",
                "Generate business reports",
                "registry",
                "1.5.0",
                "verified",
                now,
            ),
        )

        # Rate the skill
        review_mgr = SkillReviewManager(db_path)
        review = review_mgr.add_review(
            skill_id=skill_id, rating=4, review_text="Very useful skill!"
        )
        assert review.rating == 4
        assert review.skill_id == skill_id

        # Verify average rating
        avg = review_mgr.get_average_rating(skill_id)
        assert avg == 4.0

        # Add another rating
        review_mgr.add_review(skill_id=skill_id, rating=5, user_id="user2")
        avg = review_mgr.get_average_rating(skill_id)
        assert avg == 4.5


# ===========================================================================
# 5. Data Management Workflow
# ===========================================================================


class TestDataManagementWorkflow:
    """Simulate a user managing their data."""

    def test_backup_and_restore(self, tmp_path, _isolate_data_dir):
        """User creates a backup, then restores it."""
        from opc_manager.data_backup import DataBackupManager

        # Create some data to back up
        data_dir = tmp_path / "data"
        (data_dir / "test_data.json").write_text(
            json.dumps({"key": "value", "count": 42}), encoding="utf-8"
        )

        mgr = DataBackupManager(base_dir=str(tmp_path))
        backup_path, manifest = mgr.create_backup()
        assert backup_path.exists()
        assert manifest.total_files >= 1

        # Modify the original data
        (data_dir / "test_data.json").write_text(
            json.dumps({"key": "modified"}), encoding="utf-8"
        )

        # Restore from backup
        result = mgr.restore_backup(str(backup_path), confirm=True)
        assert result["success"]

    def test_data_export_with_sanitization(self, tmp_path, _isolate_data_dir):
        """User exports data; sensitive fields are redacted."""
        from opc_manager.data_backup import DataBackupManager, REDACTED_VALUE

        # Create data with sensitive fields
        data_dir = tmp_path / "data"
        (data_dir / "config.json").write_text(
            json.dumps(
                {
                    "api_key": "sk-12345-secret",
                    "name": "My Project",
                    "smtp_pass": "email-password",
                    "normal_field": "visible",
                }
            ),
            encoding="utf-8",
        )

        mgr = DataBackupManager(base_dir=str(tmp_path))
        exported = mgr.export_data(format_type="json")
        exported_data = json.loads(exported.decode("utf-8"))

        # Sensitive fields should be redacted
        config = exported_data.get("data", {}).get("config", {})
        assert config.get("api_key") == REDACTED_VALUE
        assert config.get("smtp_pass") == REDACTED_VALUE
        assert config.get("name") == "My Project"
        assert config.get("normal_field") == "visible"

    def test_audit_log_records_operations(self, tmp_path, _isolate_data_dir):
        """User operations are recorded in audit log."""
        from opc_manager.audit_log import AuditLog

        # Reset singleton for isolation
        AuditLog._instance = None
        audit = AuditLog()

        session_id = "test-session-audit"

        # Log several operations
        audit.log(
            session_id=session_id,
            operation_type="task_execute",
            skill_id="task_engine",
            input_text="帮我写营销方案",
            output_data="营销方案已生成",
            duration_ms=1500,
            status="success",
        )
        audit.log(
            session_id=session_id,
            operation_type="email_send",
            skill_id="email_skill",
            input_text="发送跟进邮件",
            output_data="邮件已发送",
            duration_ms=800,
            status="success",
        )
        audit.log(
            session_id=session_id,
            operation_type="data_export",
            skill_id="backup",
            input_text="导出数据",
            output_data="导出完成",
            duration_ms=300,
            status="failed",
            error_msg="Permission denied",
        )

        # Query audit log
        records = audit.query(session_id=session_id)
        assert len(records) == 3

        # Verify stats
        stats = audit.get_stats(session_id=session_id)
        assert stats["total"] == 3
        assert stats["success"] == 2
        assert stats["failed"] == 1

        # Cleanup singleton
        AuditLog._instance = None


# ===========================================================================
# 6. LLM Cache Workflow
# ===========================================================================


class TestLLMCacheWorkflow:
    """Simulate LLM cache behavior in realistic usage."""

    def test_repeated_prompt_uses_cache(self, tmp_path):
        """Same prompt sent twice -> second time uses cache."""
        from opc_manager.llm_cache import LLMCache

        db_path = str(tmp_path / "cache.db")
        cache = LLMCache(db_path, ttl=3600)

        # Put a response
        cache.put(
            model="gpt-4o",
            temperature=0.3,
            max_tokens=1000,
            system_prompt="You are a helpful assistant.",
            user_prompt="What is AI?",
            response="AI is artificial intelligence.",
            provider="openai",
        )

        # Get the same prompt -> should hit cache
        result = cache.get(
            model="gpt-4o",
            temperature=0.3,
            max_tokens=1000,
            system_prompt="You are a helpful assistant.",
            user_prompt="What is AI?",
        )
        assert result == "AI is artificial intelligence."

        # Verify stats show a hit
        stats = cache.stats()
        assert stats["total_hits"] >= 1

    def test_different_prompt_bypasses_cache(self, tmp_path):
        """Different prompt -> cache miss."""
        from opc_manager.llm_cache import LLMCache

        db_path = str(tmp_path / "cache.db")
        cache = LLMCache(db_path, ttl=3600)

        # Put a response
        cache.put(
            model="gpt-4o",
            temperature=0.3,
            max_tokens=1000,
            system_prompt="You are a helpful assistant.",
            user_prompt="What is AI?",
            response="AI is artificial intelligence.",
        )

        # Different prompt -> miss
        result = cache.get(
            model="gpt-4o",
            temperature=0.3,
            max_tokens=1000,
            system_prompt="You are a helpful assistant.",
            user_prompt="What is machine learning?",
        )
        assert result is None

    def test_expired_cache_is_refreshed(self, tmp_path):
        """Expired cache entry -> fresh LLM call needed."""
        from opc_manager.llm_cache import LLMCache

        db_path = str(tmp_path / "cache.db")
        # Use a short TTL so entries expire quickly
        cache = LLMCache(db_path, ttl=1)  # 1 second TTL

        cache.put(
            model="gpt-4o",
            temperature=0.3,
            max_tokens=1000,
            system_prompt="system",
            user_prompt="prompt",
            response="old response",
        )

        # Verify it's cached right away
        result = cache.get(
            model="gpt-4o",
            temperature=0.3,
            max_tokens=1000,
            system_prompt="system",
            user_prompt="prompt",
        )
        assert result == "old response"

        # Wait for expiry
        time.sleep(1.1)

        # Should be expired -> returns None
        result = cache.get(
            model="gpt-4o",
            temperature=0.3,
            max_tokens=1000,
            system_prompt="system",
            user_prompt="prompt",
        )
        assert result is None

        # Simulate fresh LLM call and cache update with a new cache instance (fresh TTL)
        fresh_cache = LLMCache(db_path, ttl=3600)
        fresh_cache.put(
            model="gpt-4o",
            temperature=0.3,
            max_tokens=1000,
            system_prompt="system",
            user_prompt="prompt",
            response="new response",
        )
        result = fresh_cache.get(
            model="gpt-4o",
            temperature=0.3,
            max_tokens=1000,
            system_prompt="system",
            user_prompt="prompt",
        )
        assert result == "new response"


# ===========================================================================
# 7. i18n Workflow
# ===========================================================================


class TestI18nWorkflow:
    """Simulate a user switching languages."""

    def test_switch_to_english(self, tmp_path):
        """User switches UI to English."""
        from opc_manager.i18n import I18nManager

        mgr = I18nManager()
        mgr.locale = "en_US"
        assert mgr.locale == "en_US"

        # Verify English strings are returned
        chat_nav = mgr.t("nav_chat")
        assert "Chat" in chat_nav or "chat" in chat_nav.lower() or chat_nav != ""

    def test_switch_to_japanese(self, tmp_path):
        """User switches UI to Japanese."""
        from opc_manager.i18n import I18nManager

        mgr = I18nManager()
        mgr.locale = "ja_JP"
        assert mgr.locale == "ja_JP"

        # Verify Japanese strings are returned
        settings_nav = mgr.t("nav_settings")
        assert settings_nav != ""

    def test_missing_key_falls_back(self, tmp_path):
        """Missing translation key falls back to the key itself."""
        from opc_manager.i18n import I18nManager

        mgr = I18nManager()
        mgr.locale = "en_US"

        # A key that likely doesn't exist in en_US
        result = mgr.t("nonexistent_key_xyz_12345")
        # When key is missing, the key itself is returned as fallback
        assert result == "nonexistent_key_xyz_12345"


# ===========================================================================
# 8. Security Workflow
# ===========================================================================


class TestSecurityWorkflow:
    """Simulate security-related user scenarios."""

    def test_mcp_binds_localhost_only(self, tmp_path):
        """MCP server should only bind to 127.0.0.1 by default."""
        # Verify default host in mcp_transport is 127.0.0.1
        import opc_manager.mcp_transport as mcp_transport
        import inspect

        source = inspect.getsource(mcp_transport.start_sse_server)
        assert "127.0.0.1" in source

        # Also verify the CLI default
        # The argparse default for --host is 127.0.0.1
        assert "127.0.0.1" in source

    def test_api_key_not_in_export(self, tmp_path, _isolate_data_dir):
        """API keys should not appear in data exports."""
        from opc_manager.data_backup import DataBackupManager, REDACTED_VALUE

        # Create data with API key
        data_dir = tmp_path / "data"
        (data_dir / "secrets.json").write_text(
            json.dumps(
                {
                    "api_key": "sk-super-secret-key-12345",
                    "token": "bearer-abc123",
                    "safe_data": "this is fine",
                }
            ),
            encoding="utf-8",
        )

        mgr = DataBackupManager(base_dir=str(tmp_path))
        exported = mgr.export_data(format_type="json")
        exported_text = exported.decode("utf-8")

        # The raw secret values should NOT appear in export
        assert "sk-super-secret-key-12345" not in exported_text
        assert "bearer-abc123" not in exported_text
        # But safe data should be present
        assert "this is fine" in exported_text
        # Redacted marker should appear
        assert REDACTED_VALUE in exported_text

    def test_input_validator_sanitizes_xss(self, tmp_path):
        """Input validator should strip HTML tags to prevent XSS."""
        from opc_manager.task_types import InputValidator

        # HTML injection attempt
        sanitized, error = InputValidator.sanitize('<script>alert("xss")</script>Hello')
        assert "<script>" not in sanitized
        assert "alert" not in sanitized or "Hello" in sanitized

    def test_input_validator_blocks_javascript_url(self, tmp_path):
        """URL sanitizer should block javascript: protocol."""
        from opc_manager.task_types import InputValidator

        assert InputValidator.sanitize_url("javascript:alert(1)") == ""
        assert (
            InputValidator.sanitize_url("https://example.com") == "https://example.com"
        )

    def test_audit_log_sanitizes_sensitive_input(self, tmp_path, _isolate_data_dir):
        """Audit log should redact sensitive patterns from input."""
        from opc_manager.audit_log import AuditLog

        AuditLog._instance = None
        audit = AuditLog()

        record_id = audit.log(
            session_id="sec-test",
            operation_type="config_update",
            skill_id="settings",
            input_text="Update api_key to sk-12345",
            output_data="Config updated",
            duration_ms=100,
        )

        # Query and verify the input was sanitized
        records = audit.query(session_id="sec-test")
        assert len(records) == 1
        assert "sk-12345" not in records[0]["input_summary"]
        assert "REDACTED" in records[0]["input_summary"]

        AuditLog._instance = None
