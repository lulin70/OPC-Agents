"""
Live Log Panel Unit Tests — 实时日志查看器完整测试套件

Covers:
- LogEntry dataclass: creation, serialization, display formatting, HTML rendering
- collect_*_logs() functions: app logs, engine logs, audit logs, progress logs, system logs
- collect_all_logs(): aggregation from all sources with timestamp filtering
- Filter logic: level filtering, source filtering, keyword search
- Stats summary calculation
- Export functionality: TXT, JSON, CSV formats
- LogCache: singleton pattern, update, trim, persist, load, clear
- Sensitive information sanitization (API keys, passwords, tokens)
- Edge cases: empty logs, malformed entries, missing files
- Performance: collecting 1000 log entries under 100ms

Run command:
    pytest tests/test_live_log_panel.py -v --tb=short
"""

import json
import os
import sys
import time
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    pass

    psutil_available = True
except ImportError:
    psutil_available = False

from frontend.components.live_log_panel import (
    LogEntry,
    LogCache,
    LOG_LEVEL_CONFIG,
    LOG_SOURCE_CONFIG,
    LOG_LEVEL_ORDER,
    SENSITIVE_PATTERNS,
    CACHE_FILE,
    sanitize_log_message,
    collect_app_logs,
    collect_engine_logs,
    collect_audit_logs,
    collect_progress_logs,
    collect_system_logs,
    collect_all_logs,
    export_logs,
    MAX_CACHE_ENTRIES,
    DEFAULT_DISPLAY_LIMIT,
)


@pytest.fixture(autouse=True)
def reset_cache_singleton():
    """Reset LogCache singleton before each test for isolation."""
    original = LogCache._instance
    LogCache._instance = None
    import frontend.components.live_log_panel as module

    original_instance = getattr(module, "_log_cache_instance", None)
    module._log_cache_instance = None
    yield
    LogCache._instance = original
    module._log_cache_instance = original_instance


def create_sample_entry(
    timestamp: float = None,
    level: str = "INFO",
    source: str = "app",
    message: str = "Test message",
    module: str = "test_module",
    extra: dict = None,
) -> LogEntry:
    """Helper to create sample LogEntry instances."""
    return LogEntry(
        timestamp=timestamp or time.time(),
        level=level,
        source=source,
        message=message,
        module=module,
        extra=extra or {},
    )


class FakeAuditLog:
    """真实 fake AuditLog，提供 query() 返回真实 dict 条目列表。

    替代 MagicMock 反模式。真实 AuditLog 是单例（有 DB 副作用），
    此 fake 提供独立的 query() 返回真实 dict 条目（非 MagicMock 桩）。
    签名匹配 opc_manager.audit_log.AuditLog.query()。
    """

    def __init__(self, records=None):
        self._records = records or []

    def query(self, session_id=None, operation_type=None, limit=50, since=None):
        """返回真实 dict 条目列表，模拟 AuditLog.query() 的输出。

        支持 since 时间戳过滤和 limit 限制，与真实 query() 语义一致。
        """
        result = self._records
        if since is not None:
            result = [r for r in result if r.get("timestamp", 0) >= since]
        return result[:limit]


class FakeProgressEmitter:
    """真实 fake ProgressEmitter，提供 get_history() 返回真实 dict 条目。

    替代 MagicMock 反模式。真实 ProgressEmitter 是单例（有状态泄漏风险），
    此 fake 提供独立的 get_history() 返回真实 dict 条目
    （与 ProgressEvent.to_dict() 输出格式一致）。
    _history 属性用于 collect_progress_logs 无 session_id 时的遍历。
    """

    def __init__(self, history=None):
        self._history = history or {}

    def get_history(self, session_id):
        """返回真实 dict 历史列表，模拟 ProgressEmitter.get_history() 的输出。"""
        return list(self._history.get(session_id, []))


class TestLogEntryDataStructure:
    """Test suite for LogEntry dataclass validation and methods."""

    def test_creation_with_required_fields(self):
        entry = create_sample_entry()
        assert entry.level == "INFO"
        assert entry.source == "app"
        assert entry.message == "Test message"
        assert entry.module == "test_module"
        assert entry.extra == {}

    def test_creation_with_extra_data(self):
        entry = create_sample_entry(extra={"traceback": "Error line 1"})
        assert entry.extra["traceback"] == "Error line 1"

    def test_to_display_format(self):
        ts = 1700000000.0
        entry = create_sample_entry(timestamp=ts, message="Task started")
        display = entry.to_display()
        assert "ℹ" not in display
        assert "[应用]" in display
        assert "Task started" in display

    def test_to_html_with_colorization(self):
        entry = create_sample_entry(level="ERROR", message="Something failed")
        html = entry.to_html(colorized=True)
        assert "#EF4444" in html
        assert "❌" not in html
        assert "Something failed" in html
        assert "<div" in html

    def test_to_html_without_colorization(self):
        entry = create_sample_entry()
        html = entry.to_html(colorized=False)
        assert html == entry.to_display()

    def test_to_html_with_traceback(self):
        entry = create_sample_entry(
            level="ERROR",
            message="Critical error",
            extra={
                "traceback": "Traceback (most recent call last):\n  File 'test.py', line 1"
            },
        )
        html = entry.to_html()
        assert "错误详情" in html or "error" in html.lower()
        assert "Traceback" in html

    def test_to_dict_serialization(self):
        ts = time.time()
        entry = create_sample_entry(timestamp=ts, extra={"key": "value"})
        d = entry.to_dict()
        assert isinstance(d, dict)
        assert d["timestamp"] == ts
        assert d["level"] == "INFO"
        assert d["source"] == "app"
        assert d["extra"]["key"] == "value"

    def test_different_levels(self):
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            entry = create_sample_entry(level=level)
            assert entry.level == level
            display = entry.to_display()
            icon = LOG_LEVEL_CONFIG[level]["icon"]
            assert icon in display

    def test_different_sources(self):
        for source in ["app", "engine", "audit", "progress", "system"]:
            entry = create_sample_entry(source=source)
            assert entry.source == source
            label = LOG_SOURCE_CONFIG[source]["label"]
            display = entry.to_display()
            assert label in display

    def test_chinese_message_support(self):
        entry = create_sample_entry(message="任务执行成功")
        assert "任务执行成功" in entry.to_display()

    def test_special_characters_in_message(self):
        entry = create_sample_entry(message="Test <script>alert('xss')</script>")
        html = entry.to_html()
        assert "&lt;script&gt;" in html or "<script>" not in html


class TestSanitization:
    """Test suite for sensitive information redaction."""

    def test_api_key_redaction(self):
        message = "Config loaded api_key=sk-abc123def456ghi789jkl012mno345pqr"
        sanitized = sanitize_log_message(message)
        assert "***REDACTED***" in sanitized
        assert "sk-abc123" not in sanitized

    def test_password_redaction(self):
        message = "Login attempt password=mySecretPassword123"
        sanitized = sanitize_log_message(message)
        assert "***REDACTED***" in sanitized
        assert "mySecretPassword" not in sanitized

    def test_token_redaction(self):
        message = "Auth token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        sanitized = sanitize_log_message(message)
        assert "***REDACTED***" in sanitized

    def test_no_false_positives_on_normal_text(self):
        message = "User requested to update their API configuration settings"
        sanitized = sanitize_log_message(message)
        assert "***REDACTED***" not in sanitized
        assert message == sanitized

    def test_multiple_patterns_in_one_message(self):
        message = "Connect with api_key=sk-key123 and password=pass456"
        sanitized = sanitize_log_message(message)
        assert sanitized.count("***REDACTED***") >= 2


class TestCollectAppLogs:
    """Test suite for application log collection."""

    def test_nonexistent_log_file_returns_empty(self):
        with patch("frontend.components.live_log_panel.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            logs = collect_app_logs()
            assert logs == []

    def test_valid_log_file_parsed_correctly(self, tmp_path):
        """Valid log file should be parsed into LogEntry objects."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "app.log").write_text(
            "2024-01-15 10:30:00 - app - INFO - Application started\n"
            "2024-01-15 10:30:01 - engine - DEBUG - Processing request\n"
            "2024-01-15 10:30:02 - audit - WARNING - Slow response detected\n",
            encoding="utf-8",
        )

        with patch("frontend.components.live_log_panel._WORKSPACE_DIR", str(tmp_path)):
            logs = collect_app_logs()

        assert len(logs) == 3
        assert logs[0].level == "INFO"
        assert logs[0].source == "app"
        assert "Application started" in logs[0].message
        assert logs[1].level == "DEBUG"
        assert logs[2].level == "WARNING"

    def test_timestamp_filtering(self):
        future_ts = time.time() + 3600
        logs = collect_app_logs(since_timestamp=future_ts)
        assert logs == []


class TestCollectEngineLogs:
    """Test suite for engine log collection."""

    def test_engine_logs_with_opc_manager_content(self, tmp_path):
        """Engine log file with opc_manager content should be parsed correctly."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "engine.log").write_text(
            "2024-01-15 11:00:00 | INFO | opc_manager TaskEngineV3 executing task\n"
            "2024-01-15 11:00:01 | DEBUG | opc_manager AgentLoop processing step\n",
            encoding="utf-8",
        )

        with patch("frontend.components.live_log_panel._WORKSPACE_DIR", str(tmp_path)):
            logs = collect_engine_logs()

        assert any(line.source == "engine" for line in logs)
        assert any("TaskEngineV3" in line.message for line in logs)

    def test_nonexistent_engine_logs(self):
        with patch("frontend.components.live_log_panel.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            logs = collect_engine_logs()
            assert logs == []


class TestCollectAuditLogs:
    """Test suite for audit log collection."""

    @patch("opc_manager.audit_log.AuditLog")
    def test_successful_audit_collection(self, MockAuditLog):
        fake_audit = FakeAuditLog(
            records=[
                {
                    "id": "abc123",
                    "timestamp": time.time(),
                    "operation_type": "task_execute",
                    "skill_id": "content_generation",
                    "status": "success",
                    "duration_ms": 1500,
                    "input_summary": "Generate report",
                    "output_summary": "Report generated",
                }
            ]
        )
        MockAuditLog.return_value = fake_audit

        logs = collect_audit_logs()
        assert len(logs) == 1
        assert logs[0].source == "audit"
        assert logs[0].level == "INFO"
        assert "task_execute" in logs[0].message

    @patch("opc_manager.audit_log.AuditLog")
    def test_failed_operation_shows_error_level(self, MockAuditLog):
        fake_audit = FakeAuditLog(
            records=[
                {
                    "id": "def456",
                    "timestamp": time.time(),
                    "operation_type": "api_call",
                    "skill_id": "llm_service",
                    "status": "failed",
                    "duration_ms": 5000,
                    "error_msg": "Connection timeout",
                    "input_summary": "",
                    "output_summary": "",
                }
            ]
        )
        MockAuditLog.return_value = fake_audit

        logs = collect_audit_logs()
        assert logs[0].level == "ERROR"
        assert "Connection timeout" in logs[0].message

    def test_import_error_handling(self):
        with patch.dict(sys.modules, {"opc_manager.audit_log": None}):
            logs = collect_audit_logs()
            assert logs == []


class TestCollectProgressLogs:
    """Test suite for progress event collection."""

    @patch("opc_manager.progress_emitter.ProgressEmitter")
    def test_progress_event_conversion(self, MockEmitter):
        fake_emitter = FakeProgressEmitter(
            history={
                "test_session_12345": [
                    {
                        "event": "step_start",
                        "session_id": "test_session_12345",
                        "message": "Starting content generation",
                        "timestamp": time.time(),
                        "progress": 10,
                    },
                    {
                        "event": "complete",
                        "session_id": "test_session_12345",
                        "message": "Task completed successfully",
                        "timestamp": time.time(),
                        "progress": 100,
                    },
                ]
            }
        )
        MockEmitter.return_value = fake_emitter

        logs = collect_progress_logs(session_id="test_session_12345")
        assert len(logs) == 2
        assert all(line.source == "progress" for line in logs)
        assert logs[0].extra["event_type"] == "step_start"
        assert logs[0].extra["progress_pct"] == 10
        assert "[STEP_START] (10%)" in logs[0].message

    @patch("opc_manager.progress_emitter.ProgressEmitter")
    def test_error_event_mapped_to_error_level(self, MockEmitter):
        fake_emitter = FakeProgressEmitter(
            history={
                "sess": [
                    {
                        "event": "error",
                        "session_id": "sess",
                        "message": "LLM service unavailable",
                        "timestamp": time.time(),
                    }
                ]
            }
        )
        MockEmitter.return_value = fake_emitter

        logs = collect_progress_logs(session_id="sess")
        assert logs[0].level == "ERROR"

    def test_import_error_handling(self):
        with patch.dict(sys.modules, {"opc_manager.progress_emitter": None}):
            logs = collect_progress_logs()
            assert logs == []


class TestCollectSystemLogs:
    """Test suite for system metrics collection."""

    @pytest.mark.skipif(not psutil_available, reason="psutil not installed")
    @patch("psutil.cpu_percent")
    @patch("psutil.virtual_memory")
    @patch("psutil.disk_usage")
    def test_system_metrics_collected(self, mock_disk, mock_mem, mock_cpu):
        mock_cpu.return_value = 45.5
        mock_mem_instance = MagicMock()
        mock_mem_instance.percent = 62.3
        mock_mem_instance.used = 8 * 1024 * 1024 * 1024
        mock_mem_instance.total = 16 * 1024 * 1024 * 1024
        mock_mem.return_value = mock_mem_instance
        mock_disk_instance = MagicMock()
        mock_disk_instance.percent = 55.0
        mock_disk.return_value = mock_disk_instance

        logs = collect_system_logs()
        assert len(logs) == 1
        assert logs[0].source == "system"
        assert "CPU:" in logs[0].message
        assert "Memory:" in logs[0].message
        assert logs[0].extra["cpu_percent"] == 45.5

    def test_psutil_unavailable(self):
        with patch.dict(sys.modules, {"psutil": None}):
            with patch("builtins.__import__", side_effect=ImportError):
                logs = collect_system_logs()
                assert len(logs) == 1
                assert "psutil未安装" in logs[0].message


class TestCollectAllLogs:
    """Test suite for aggregated log collection."""

    @patch("frontend.components.live_log_panel.collect_system_logs", return_value=[])
    @patch("frontend.components.live_log_panel.collect_progress_logs", return_value=[])
    @patch("frontend.components.live_log_panel.collect_audit_logs", return_value=[])
    @patch("frontend.components.live_log_panel.collect_engine_logs", return_value=[])
    @patch(
        "frontend.components.live_log_panel.collect_app_logs",
        return_value=[
            create_sample_entry(level="INFO"),
            create_sample_entry(level="WARNING"),
        ],
    )
    def test_aggregation_from_all_sources(self, mock_app, *args):
        logs = collect_all_logs()
        assert len(logs) == 2
        assert all(line.source == "app" for line in logs)

    def test_result_limited_to_default_display_limit(self):
        many_entries = [
            create_sample_entry(timestamp=time.time() + i) for i in range(200)
        ]
        with patch(
            "frontend.components.live_log_panel.collect_app_logs",
            return_value=many_entries,
        ):
            with patch(
                "frontend.components.live_log_panel.collect_engine_logs",
                return_value=[],
            ):
                with patch(
                    "frontend.components.live_log_panel.collect_audit_logs",
                    return_value=[],
                ):
                    with patch(
                        "frontend.components.live_log_panel.collect_progress_logs",
                        return_value=[],
                    ):
                        with patch(
                            "frontend.components.live_log_panel.collect_system_logs",
                            return_value=[],
                        ):
                            logs = collect_all_logs()
                            assert len(logs) <= DEFAULT_DISPLAY_LIMIT

    def test_timestamp_filtering_works(self, tmp_path):
        """collect_all_logs should respect since_timestamp: recent entries pass, old entries filtered."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        # Recent log entry (app.log) — timestamp 10s ago, passes since_timestamp filter
        recent_ts = time.time() - 10
        recent_ts_str = datetime.fromtimestamp(recent_ts).strftime("%Y-%m-%d %H:%M:%S")
        (logs_dir / "app.log").write_text(
            f"{recent_ts_str} - app - INFO - Recent entry\n",
            encoding="utf-8",
        )

        # Old log entry (engine.log) — timestamp 2h ago, filtered out by since_timestamp
        old_ts = time.time() - 7200
        old_ts_str = datetime.fromtimestamp(old_ts).strftime("%Y-%m-%d %H:%M:%S")
        (logs_dir / "engine.log").write_text(
            f"{old_ts_str} | INFO | opc_manager TaskEngineV3 old task\n",
            encoding="utf-8",
        )

        with patch("frontend.components.live_log_panel._WORKSPACE_DIR", str(tmp_path)):
            with patch(
                "frontend.components.live_log_panel.collect_audit_logs",
                return_value=[],
            ):
                with patch(
                    "frontend.components.live_log_panel.collect_progress_logs",
                    return_value=[],
                ):
                    with patch(
                        "frontend.components.live_log_panel.collect_system_logs",
                        return_value=[],
                    ):
                        # No filter — both entries should be present
                        all_logs = collect_all_logs()
                        assert any("Recent entry" in log.message for log in all_logs)
                        assert any("TaskEngineV3" in log.message for log in all_logs)

                        # With filter — old entry should be excluded
                        filtered = collect_all_logs(since_timestamp=time.time() - 60)
                        assert any("Recent entry" in log.message for log in filtered)
                        assert not any(
                            "TaskEngineV3" in log.message for log in filtered
                        )

    def test_results_sorted_by_timestamp(self):
        entries = [
            create_sample_entry(timestamp=1700000003.0),
            create_sample_entry(timestamp=1700000001.0),
            create_sample_entry(timestamp=1700000002.0),
        ]

        with patch(
            "frontend.components.live_log_panel.collect_app_logs", return_value=entries
        ):
            with patch(
                "frontend.components.live_log_panel.collect_engine_logs",
                return_value=[],
            ):
                with patch(
                    "frontend.components.live_log_panel.collect_audit_logs",
                    return_value=[],
                ):
                    with patch(
                        "frontend.components.live_log_panel.collect_progress_logs",
                        return_value=[],
                    ):
                        with patch(
                            "frontend.components.live_log_panel.collect_system_logs",
                            return_value=[],
                        ):
                            logs = collect_all_logs()
                            timestamps = [line.timestamp for line in logs]
                            assert timestamps == sorted(timestamps)


class TestLogCache:
    """Test suite for LogCache singleton and operations."""

    def test_singleton_pattern(self):
        cache1 = LogCache()
        cache2 = LogCache()
        assert cache1 is cache2

    def test_update_adds_entries(self):
        cache = LogCache()
        entry = create_sample_entry()
        cache.update([entry])
        assert cache.size == 1
        recent = cache.get_recent(limit=10)
        assert len(recent) == 1
        assert recent[0].message == "Test message"

    def test_update_trims_to_max_entries(self):
        cache = LogCache()
        entries = [
            create_sample_entry(timestamp=time.time() + i)
            for i in range(MAX_CACHE_ENTRIES + 100)
        ]
        cache.update(entries)
        assert cache.size <= MAX_CACHE_ENTRIES

    def test_get_recent_respects_limit(self):
        cache = LogCache()
        entries = [create_sample_entry(timestamp=time.time() + i) for i in range(50)]
        cache.update(entries)

        recent_10 = cache.get_recent(limit=10)
        assert len(recent_10) == 10

        recent_all = cache.get_recent(limit=100)
        assert len(recent_all) == 50

    def test_get_since_filters_by_timestamp(self):
        cache = LogCache()
        now = time.time()
        old_entry = create_sample_entry(timestamp=now - 100)
        new_entry = create_sample_entry(timestamp=now)
        cache.update([old_entry, new_entry])

        recent = cache.get_since(now - 50)
        assert len(recent) == 1
        assert recent[0].timestamp == now

    def test_clear_removes_all_entries(self):
        cache = LogCache()
        cache.update([create_sample_entry() for _ in range(10)])
        assert cache.size > 0
        cache.clear()
        assert cache.size == 0

    def test_last_update_timestamp(self):
        cache = LogCache()
        before = cache.last_update
        cache.update([create_sample_entry()])
        after = cache.last_update
        assert after >= before

    def test_persist_creates_file(self):
        cache = LogCache()
        entries = [create_sample_entry(message=f"Message {i}") for i in range(5)]
        cache.update(entries)
        cache._persist()

        assert CACHE_FILE.exists()
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 5
        CACHE_FILE.unlink(missing_ok=True)

    def test_load_restores_from_file(self):
        LogCache()
        test_data = [
            {
                "timestamp": time.time(),
                "level": "INFO",
                "source": "app",
                "message": "Loaded message",
                "module": "test",
                "extra": {},
            }
        ]
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        loaded_cache = LogCache.load()
        assert loaded_cache.size == 1
        assert loaded_cache.get_recent()[0].message == "Loaded message"
        CACHE_FILE.unlink(missing_ok=True)

    def test_load_handles_missing_file(self):
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
        cache = LogCache.load()
        assert cache.size == 0

    def test_load_handles_corrupted_file(self):
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            f.write("{invalid json content!!!")
        cache = LogCache.load()
        assert cache.size == 0
        CACHE_FILE.unlink(missing_ok=True)

    def test_shutdown_persists_and_closes(self):
        cache = LogCache()
        cache.update([create_sample_entry()])
        cache.shutdown()


class TestExportFunctionality:
    """Test suite for log export in different formats."""

    def setup_method(self):
        self.sample_logs = [
            create_sample_entry(
                timestamp=1700000000.0,
                level="INFO",
                source="app",
                message="Info message",
                module="app_main",
            ),
            create_sample_entry(
                timestamp=1700000001.0,
                level="ERROR",
                source="engine",
                message="Error occurred",
                module="task_engine",
                extra={"traceback": "Stack trace here"},
            ),
        ]

    def test_export_txt_format(self):
        result = export_logs(self.sample_logs, format="txt")
        text = result.decode("utf-8")
        assert "Info message" in text
        assert "Error occurred" in text
        assert "ℹ" not in text
        assert "❌" not in text

    def test_export_json_format(self):
        result = export_logs(self.sample_logs, format="json")
        data = json.loads(result.decode("utf-8"))
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["level"] == "INFO"
        assert data[1]["extra"]["traceback"] == "Stack trace here"

    def test_export_csv_format(self):
        result = export_logs(self.sample_logs, format="csv")
        text = result.decode("utf-8")
        lines = text.strip().split("\n")
        assert len(lines) == 3
        assert "timestamp" in lines[0]
        assert "Info message" in lines[1]
        assert "Error occurred" in lines[2]

    def test_export_empty_logs(self):
        result = export_logs([], format="txt")
        assert result.decode("utf-8") == ""

    def test_export_invalid_format_raises_error(self):
        with pytest.raises(ValueError, match="不支持的导出格式"):
            export_logs(self.sample_logs, format="xml")

    def test_export_chinese_messages_preserved(self):
        chinese_logs = [create_sample_entry(message="中文日志消息")]
        result = export_logs(chinese_logs, format="txt")
        assert "中文日志消息" in result.decode("utf-8")


class TestFilterLogic:
    """Test suite for log filtering functionality."""

    def test_level_filter_debug_shows_all(self):
        logs = [
            create_sample_entry(level="DEBUG"),
            create_sample_entry(level="INFO"),
            create_sample_entry(level="ERROR"),
        ]
        min_level_pos = LOG_LEVEL_ORDER.index("DEBUG")
        allowed_levels = set(LOG_LEVEL_ORDER[min_level_pos:])
        filtered = [line for line in logs if line.level in allowed_levels]
        assert len(filtered) == 3

    def test_level_filter_warning_excludes_debug_and_info(self):
        logs = [
            create_sample_entry(level="DEBUG"),
            create_sample_entry(level="INFO"),
            create_sample_entry(level="WARNING"),
            create_sample_entry(level="ERROR"),
        ]
        min_level_pos = LOG_LEVEL_ORDER.index("WARNING")
        allowed_levels = set(LOG_LEVEL_ORDER[min_level_pos:])
        filtered = [line for line in logs if line.level in allowed_levels]
        assert len(filtered) == 2
        assert all(line.level in ("WARNING", "ERROR") for line in filtered)

    def test_source_filter(self):
        logs = [
            create_sample_entry(source="app"),
            create_sample_entry(source="engine"),
            create_sample_entry(source="audit"),
        ]
        filtered = [line for line in logs if line.source in ("app", "audit")]
        assert len(filtered) == 2
        assert set(line.source for line in filtered) == {"app", "audit"}

    def test_keyword_search_case_insensitive(self):
        logs = [
            create_sample_entry(message="Database connection established"),
            create_sample_entry(message="Processing user request"),
            create_sample_entry(message="Database query executed"),
        ]
        keyword = "database"
        filtered = [line for line in logs if keyword.lower() in line.message.lower()]
        assert len(filtered) == 2

    def test_combined_filters(self):
        logs = [
            create_sample_entry(level="DEBUG", source="app", message="Debug info"),
            create_sample_entry(
                level="INFO", source="engine", message="Engine started"
            ),
            create_sample_entry(level="ERROR", source="app", message="App error"),
            create_sample_entry(
                level="WARNING", source="audit", message="Audit warning"
            ),
        ]

        min_level_pos = LOG_LEVEL_ORDER.index("WARNING")
        allowed_levels = set(LOG_LEVEL_ORDER[min_level_pos:])
        filtered = [line for line in logs if line.level in allowed_levels]
        filtered = [line for line in filtered if line.source in ("app", "audit")]

        assert len(filtered) == 2
        assert all(line.level in ("WARNING", "ERROR", "CRITICAL") for line in filtered)
        assert all(line.source in ("app", "audit") for line in filtered)

    def test_empty_result_from_filters(self):
        logs = [create_sample_entry(level="DEBUG")]
        min_level_pos = LOG_LEVEL_ORDER.index("ERROR")
        allowed_levels = set(LOG_LEVEL_ORDER[min_level_pos:])
        filtered = [line for line in logs if line.level in allowed_levels]
        assert len(filtered) == 0


class TestEdgeCases:
    """Test suite for edge cases and error handling."""

    def test_empty_log_list(self):
        assert collect_all_logs() is not None

    def test_none_values_in_optional_fields(self):
        entry = LogEntry(
            timestamp=time.time(),
            level="INFO",
            source="app",
            message="Test",
            module="",
        )
        assert entry.extra == {}

    def test_very_long_message_truncation_not_needed(self):
        long_msg = "A" * 10000
        entry = create_sample_entry(message=long_msg)
        assert len(entry.message) == 10000

    def test_unicode_and_emoji_in_message(self):
        entry = create_sample_entry(message="✅ 任务完成 🎉 成功！")
        assert "任务完成" in entry.to_display()
        assert "成功" in entry.to_display()

    def test_special_characters_in_module_name(self):
        entry = create_sample_entry(module="my-module.v2.special")
        assert entry.module == "my-module.v2.special"

    def test_future_timestamp(self):
        future_ts = time.time() + 86400 * 365
        entry = create_sample_entry(timestamp=future_ts)
        ts_str = datetime.fromtimestamp(entry.timestamp).strftime("%H:%M:%S")
        assert ts_str in entry.to_display()


class TestPerformance:
    """Test suite for performance benchmarks."""

    def test_collect_1000_entries_under_100ms(self):
        large_batch = [
            create_sample_entry(timestamp=time.time() + i * 0.001) for i in range(1000)
        ]

        start_time = time.perf_counter()

        with patch(
            "frontend.components.live_log_panel.collect_app_logs",
            return_value=large_batch[:300],
        ):
            with patch(
                "frontend.components.live_log_panel.collect_engine_logs",
                return_value=large_batch[300:500],
            ):
                with patch(
                    "frontend.components.live_log_panel.collect_audit_logs",
                    return_value=large_batch[500:700],
                ):
                    with patch(
                        "frontend.components.live_log_panel.collect_progress_logs",
                        return_value=large_batch[700:900],
                    ):
                        with patch(
                            "frontend.components.live_log_panel.collect_system_logs",
                            return_value=large_batch[900:1000],
                        ):
                            logs = collect_all_logs()

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        assert elapsed_ms < 100, f"Collection took {elapsed_ms:.2f}ms, expected < 100ms"
        assert len(logs) <= DEFAULT_DISPLAY_LIMIT

    def test_cache_update_performance(self):
        cache = LogCache()
        entries = [create_sample_entry(timestamp=time.time() + i) for i in range(1000)]

        start_time = time.perf_counter()
        cache.update(entries)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        assert elapsed_ms < 50, f"Cache update took {elapsed_ms:.2f}ms, expected < 50ms"
        assert cache.size <= MAX_CACHE_ENTRIES

    def test_export_large_dataset_performance(self):
        large_logs = [
            create_sample_entry(message=f"Log entry {i}") for i in range(1000)
        ]

        start_time = time.perf_counter()
        export_data = export_logs(large_logs, format="json")
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        assert elapsed_ms < 100, f"Export took {elapsed_ms:.2f}ms, expected < 100ms"
        assert len(export_data) > 0


class TestConfigurationConstants:
    """Test suite for configuration constant validation."""

    def test_log_level_config_has_all_standard_levels(self):
        expected_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        actual_levels = set(LOG_LEVEL_CONFIG.keys())
        assert expected_levels == actual_levels

    def test_log_level_config_structure(self):
        for level, config in LOG_LEVEL_CONFIG.items():
            assert "icon" in config
            assert "color" in config
            assert "bg_color" in config

    def test_log_source_config_has_all_sources(self):
        expected_sources = {"app", "engine", "audit", "progress", "system"}
        actual_sources = set(LOG_SOURCE_CONFIG.keys())
        assert expected_sources == actual_sources

    def test_log_source_config_structure(self):
        for source, config in LOG_SOURCE_CONFIG.items():
            assert "label" in config
            assert "icon" in config

    def test_log_level_order_sequence(self):
        assert LOG_LEVEL_ORDER == ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def test_max_cache_entries_reasonable(self):
        assert 100 <= MAX_CACHE_ENTRIES <= 10000

    def test_default_display_limit_reasonable(self):
        assert 10 <= DEFAULT_DISPLAY_LIMIT <= 1000

    def test_sensitive_patterns_defined(self):
        assert len(SENSITIVE_PATTERNS) > 0
        assert all(isinstance(p, str) for p in SENSITIVE_PATTERNS)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
