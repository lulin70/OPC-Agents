"""
Shortcuts Handler Unit Tests — Apple Shortcuts integration for OPC-Agents v0.2.0

Covers:
- ShortcutResult serialization (to_json, to_shortcuts_output)
- quick_task: valid input, empty input, LLM mock
- query_status: structured output with/without data
- create_deliverable: creates DB record, missing title fails
- record_income: valid amount, zero/negative amount fails
- daily_report: formatted output generation
- CLI argument parsing via subprocess

Run command:
    pytest tests/test_shortcuts_handler.py -v --tb=short --no-header -q
"""

import json
import os
import subprocess
import sys
from unittest.mock import patch, MagicMock

import pytest

from opc_manager.shortcuts_handler import (
    ShortcutResult,
    ShortcutsHandler,
    main as cli_main,
)


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Set up a temporary database environment for each test."""
    db_dir = tmp_path / "data"
    db_dir.mkdir()
    monkeypatch.setenv("OPC_DATA_DIR", str(db_dir))
    monkeypatch.setenv("OPC_ENCRYPTION_KEY", "test-key-for-encryption-32chars!!")
    import opc_manager.data_manager as dm

    _orig_initialized = dm._db_initialized
    from opc_manager.data_manager import _local

    _orig_conn = getattr(_local, "conn", None)
    dm._db_initialized = False
    if hasattr(_local, "conn") and _local.conn is not None:
        try:
            _local.conn.close()
        except Exception:
            pass
        _local.conn = None
    yield db_dir
    if hasattr(_local, "conn") and _local.conn is not None:
        try:
            _local.conn.close()
        except Exception:
            pass
        _local.conn = None
    dm._db_initialized = _orig_initialized


class TestShortcutResultSerialization:
    """Test suite for ShortcutResult serialization methods."""

    def test_success_output_format(self):
        result = ShortcutResult(True, "操作成功")
        output = result.to_shortcuts_output()
        assert "操作成功" in output

    def test_failure_output_format(self):
        result = ShortcutResult(False, "出错了")
        output = result.to_shortcuts_output()
        assert "出错了" in output

    def test_to_json_success(self):
        result = ShortcutResult(True, "ok", {"key": "value"})
        j = json.loads(result.to_json())
        assert j["success"] is True
        assert j["message"] == "ok"
        assert j["data"]["key"] == "value"
        assert "timestamp" in j

    def test_to_json_failure(self):
        result = ShortcutResult(False, "err")
        j = json.loads(result.to_json())
        assert j["success"] is False
        assert j["message"] == "err"

    def test_to_json_ensure_ascii_false(self):
        result = ShortcutResult(True, "中文测试消息 🎉")
        j_str = result.to_json()
        assert "中文" in j_str
        assert "\\u" not in j_str or "中文" in j_str

    def test_default_data_is_empty_dict(self):
        result = ShortcutResult(True, "test")
        assert result.data == {}
        assert isinstance(result.data, dict)

    def test_json_round_trip(self):
        original = ShortcutResult(True, "msg", {"n": 42})
        parsed = json.loads(original.to_json())
        restored = ShortcutResult(parsed["success"], parsed["message"], parsed["data"])
        assert restored.success == original.success
        assert restored.message == original.message
        assert restored.data["n"] == 42


class TestQuickTask:
    """Test suite for quick_task action."""

    def test_quick_task_empty_input_fails(self, temp_db):
        handler = ShortcutsHandler()
        result = handler.quick_task("")
        assert result.success is False
        assert "不能为空" in result.message

    def test_quick_task_whitespace_input_fails(self, temp_db):
        handler = ShortcutsHandler()
        result = handler.quick_task("   \t  ")
        assert result.success is False

    @patch("opc_manager.simple_llm_service.SimpleLLMService")
    def test_quick_task_valid_input_calls_llm(self, MockLLM, temp_db):
        mock_instance = MockLLM.return_value
        mock_instance.complete.return_value = "这是AI生成的回复内容"

        handler = ShortcutsHandler()
        result = handler.quick_task("写一封邮件")

        assert result.success is True
        assert "任务完成" in result.message
        assert "这是AI生成的回复内容" in result.message
        assert result.data["action"] == "quick_task"
        mock_instance.complete.assert_called_once()

    @patch("opc_manager.simple_llm_service.SimpleLLMService")
    def test_quick_task_llm_returns_empty(self, MockLLM, temp_db):
        mock_instance = MockLLM.return_value
        mock_instance.complete.return_value = ""

        handler = ShortcutsHandler()
        result = handler.quick_task("测试任务")

        assert result.success is False
        assert "未返回有效结果" in result.message

    @patch("opc_manager.simple_llm_service.SimpleLLMService")
    def test_quick_task_output_truncated_at_500(self, MockLLM, temp_db):
        mock_instance = MockLLM.return_value
        long_response = "x" * 1000
        mock_instance.complete.return_value = long_response

        handler = ShortcutsHandler()
        result = handler.quick_task("长回复测试")

        assert result.success is True
        assert len(result.message) <= 500 + len("任务完成:\n")

    @patch(
        "opc_manager.simple_llm_service.SimpleLLMService",
        side_effect=Exception("API连接失败"),
    )
    def test_quick_task_exception_handled_gracefully(self, MockLLM, temp_db):
        handler = ShortcutsHandler()
        result = handler.quick_task("触发异常")

        assert result.success is False
        assert "执行失败" in result.message
        assert "API连接失败" in result.message


class TestQueryStatus:
    """Test suite for query_status action."""

    def test_query_status_returns_structured_output(self, temp_db):
        handler = ShortcutsHandler()
        result = handler.query_status()

        assert result.success is True
        assert "今日状态" in result.message
        assert "任务数:" in result.message
        assert "收入总计:" in result.message
        assert isinstance(result.data["tasks"], int)
        assert isinstance(result.data["income"], float)
        assert "date" in result.data

    def test_query_status_increments_with_new_tasks(self, temp_db):
        from opc_manager.data_manager import execute_write, gen_id

        handler = ShortcutsHandler()
        before = handler.query_status()

        today = __import__("datetime").date.today().isoformat()
        for i in range(3):
            execute_write(
                "INSERT INTO tasks (id, title, status, created_at) VALUES (?,?,?,?)",
                (gen_id(), f"qs_task_{i}", "done", f"{today}T12:00:00"),
            )

        after = handler.query_status()
        assert after.data["tasks"] == before.data["tasks"] + 3

    def test_query_status_increments_with_income(self, temp_db):
        from opc_manager.data_manager import execute_write, gen_id

        handler = ShortcutsHandler()
        before = handler.query_status()

        today = __import__("datetime").date.today().isoformat()
        now = __import__("datetime").datetime.now().isoformat()
        execute_write(
            "INSERT INTO finance_records (id, type, amount, category, source, date, note, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (gen_id(), "income", 5000, "咨询费", "咨询费", today, "qs_client", now),
        )
        execute_write(
            "INSERT INTO finance_records (id, type, amount, category, source, date, note, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (gen_id(), "income", 3000, "服务费", "服务费", today, "qs_client2", now),
        )

        after = handler.query_status()
        assert after.data["income"] == before.data["income"] + 8000.0


class TestCreateDeliverable:
    """Test suite for create_deliverable action."""

    def test_create_deliverable_without_title_fails(self, temp_db):
        handler = ShortcutsHandler()
        result = handler.create_deliverable("")
        assert result.success is False
        assert "标题不能为空" in result.message

    def test_create_deliverable_whitespace_title_fails(self, temp_db):
        handler = ShortcutsHandler()
        result = handler.create_deliverable("   ")
        assert result.success is False

    def test_create_deliverable_creates_record(self, temp_db):
        handler = ShortcutsHandler()
        result = handler.create_deliverable(title="Q2季度报告", dtype="report")

        assert result.success is True
        assert "Q2季度报告" in result.message
        assert "报告已创建" in result.message
        assert result.data["type"] == "report"
        assert result.data["title"] == "Q2季度报告"
        assert "id" in result.data

    def test_create_deliverable_stored_in_db(self, temp_db):
        from opc_manager.data_manager import execute_query, gen_id

        unique_title = f"db验证_{gen_id()[:8]}"
        handler = ShortcutsHandler()
        handler.create_deliverable(title=unique_title, dtype="document")

        rows = execute_query("SELECT * FROM tasks WHERE title=?", (unique_title,))
        assert len(rows) == 1
        assert rows[0]["status"] == "done"
        assert "deliverable:document" in rows[0]["tags"]

    def test_create_deliverable_different_types(self, temp_db):
        handler = ShortcutsHandler()
        type_tests = [
            ("proposal", "方案已创建"),
            ("invoice", "发票已创建"),
            ("unknown_type", "文件已创建"),
        ]
        for dtype, expected_label in type_tests:
            result = handler.create_deliverable(title=f"test_{dtype}", dtype=dtype)
            assert expected_label in result.message, f"Failed for type {dtype}"

    def test_create_deliverable_with_content(self, temp_db):
        from opc_manager.data_manager import execute_query

        handler = ShortcutsHandler()
        handler.create_deliverable(
            title="带内容的成果物", dtype="document", content="这是详细内容描述"
        )
        rows = execute_query(
            "SELECT description FROM tasks WHERE title='带内容的成果物'"
        )
        assert rows[0]["description"] == "这是详细内容描述"


class TestRecordIncome:
    """Test suite for record_income action."""

    def test_record_income_zero_amount_fails(self, temp_db):
        handler = ShortcutsHandler()
        result = handler.record_income(amount=0)
        assert result.success is False
        assert "金额必须大于0" in result.message

    def test_record_income_negative_amount_fails(self, temp_db):
        handler = ShortcutsHandler()
        result = handler.record_income(amount=-100)
        assert result.success is False

    def test_record_income_valid_amount(self, temp_db):
        handler = ShortcutsHandler()
        result = handler.record_income(amount=5000, client="张三", source="咨询费")

        assert result.success is True
        assert "5,000" in result.message or "5000" in result.message
        assert "张三" in result.message
        assert "咨询费" in result.message
        assert result.data["amount"] == 5000
        assert result.data["client"] == "张三"

    def test_record_income_stored_in_db(self, temp_db):
        from opc_manager.data_manager import execute_query, gen_id
        import time

        unique_amt = round(55555.55 + time.monotonic_ns() % 10000, 2)
        handler = ShortcutsHandler()
        handler.record_income(amount=unique_amt, client="李四db验证", source="项目费")

        rows = execute_query(
            "SELECT * FROM finance_records WHERE type='income' AND amount=? AND note='李四db验证'",
            (unique_amt,),
        )
        assert len(rows) == 1
        assert rows[0]["note"] == "李四db验证"

    def test_record_income_defaults_for_optional_fields(self, temp_db):
        handler = ShortcutsHandler()
        result = handler.record_income(amount=1000)

        assert result.success is True
        assert "未知" in result.message
        assert "其他" in result.message


class TestDailyReport:
    """Test suite for daily_report action."""

    def test_daily_report_empty_day(self, temp_db):
        handler = ShortcutsHandler()
        result = handler.daily_report()

        assert result.success is True
        assert "OPC-Agent 日报" in result.message
        assert "今日收入" in result.message
        assert "今日成果" in result.message
        assert "近期任务" in result.message
        assert "自动生成" in result.message
        assert isinstance(result.data["income_total"], (int, float))
        assert isinstance(result.data["task_count"], int)

    def test_daily_report_with_mixed_data(self, temp_db):
        from opc_manager.data_manager import execute_write, gen_id, execute_query

        today = __import__("datetime").date.today().isoformat()
        now = __import__("datetime").datetime.now().isoformat()

        unique_tag = "dr_mix_" + gen_id()[:8]
        tid = gen_id()
        execute_write(
            "INSERT INTO tasks (id, title, status, tags, created_at) VALUES (?,?,?,?,?)",
            (tid, f"重要任务_{unique_tag}", "in_progress", "", f"{today}T10:00:00"),
        )
        did = gen_id()
        execute_write(
            "INSERT INTO tasks (id, title, status, tags, created_at) VALUES (?,?,?,?,?)",
            (
                did,
                f"周报文档_{unique_tag}",
                "done",
                f"deliverable:report",
                f"{today}T11:00:00",
            ),
        )
        iid = gen_id()
        execute_write(
            "INSERT INTO finance_records (id, type, amount, category, source, date, note, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (iid, "income", 6000, "咨询", "咨询", today, f"王五_{unique_tag}", now),
        )

        handler = ShortcutsHandler()
        result = handler.daily_report()

        assert result.success is True
        task_rows = execute_query(
            "SELECT COUNT(*) as cnt FROM tasks WHERE title LIKE ?", (f"%{unique_tag}%",)
        )
        inc_rows = execute_query(
            "SELECT COALESCE(SUM(amount),0) as total FROM finance_records WHERE note LIKE ?",
            (f"%{unique_tag}%",),
        )
        del_rows = execute_query(
            "SELECT COUNT(*) as cnt FROM tasks WHERE tags LIKE 'deliverable:%' AND title LIKE ?",
            (f"%{unique_tag}%",),
        )

        assert task_rows[0]["cnt"] >= 2
        assert inc_rows[0]["total"] >= 6000
        assert del_rows[0]["cnt"] >= 1
        assert result.data["task_count"] >= 2
        assert result.data["deliverable_count"] >= 1
        assert result.data["income_total"] >= 6000

    def test_daily_report_contains_date(self, temp_db):
        handler = ShortcutsHandler()
        result = handler.daily_report()
        today_str = __import__("datetime").date.today().strftime("%Y-%m-%d")
        assert today_str in result.message
        assert result.data["date"] == today_str


class TestCliArgumentParsing:
    """Test suite for CLI argument parsing via subprocess."""

    def test_cli_help_runs(self):
        proc = subprocess.run(
            [sys.executable, "-m", "opc_manager.shortcuts_handler", "--help"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert proc.returncode == 0
        assert "OPC-Agents Apple Shortcuts Handler" in proc.stdout
        assert "quick_task" in proc.stdout
        assert "query_status" in proc.stdout
        assert "create_deliverable" in proc.stdout
        assert "record_income" in proc.stdout
        assert "daily_report" in proc.stdout

    def test_cli_no_action_shows_help_and_exits_1(self):
        proc = subprocess.run(
            [sys.executable, "-m", "opc_manager.shortcuts_handler"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert proc.returncode == 1

    def test_cli_quick_task_missing_text(self):
        proc = subprocess.run(
            [sys.executable, "-m", "opc_manager.shortcuts_handler", "quick_task"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert proc.returncode != 0

    def test_cli_create_deliverable_missing_title(self):
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "opc_manager.shortcuts_handler",
                "create_deliverable",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert proc.returncode != 0

    def test_cli_record_income_missing_amount(self):
        proc = subprocess.run(
            [sys.executable, "-m", "opc_manager.shortcuts_handler", "record_income"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert proc.returncode != 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
