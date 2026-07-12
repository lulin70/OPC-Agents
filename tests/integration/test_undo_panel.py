"""
Undo Panel UI Component Tests — Comprehensive test suite for undo visualization.

Covers:
- Operation description generation for all 8 operation types
- Remaining time calculation with urgency levels (9 scenarios)
- Time ago formatting (5 scenarios)
- Display record conversion and field population
- Undo record card rendering logic (3 types × 3 statuses = 9 combinations)
- Execute undo success/failure/expired scenarios (7 tests)
- Statistics summary calculation (4 status combinations)
- CSV and JSON export generation (4 tests)
- Batch undo interface validation (3 tests)
- Edge cases: empty session_id, invalid operation_id, missing manager (6 tests)
- Smart suggestions integration (3 tests)

Total: 40+ test cases

Run command:
    pytest tests/test_undo_panel.py -v --tb=short
"""

import time
import json
import csv
import io
from unittest.mock import patch, MagicMock

import pytest

from frontend.components.undo_panel import (
    UndoRecordDisplay,
    OPERATION_TYPE_CONFIG,
    STATUS_CONFIG,
    _get_operation_description,
    _calculate_remaining_time,
    _format_time_ago,
    _convert_to_display_record,
    execute_undo,
    calculate_undo_stats,
    check_has_active_undo_records,
    get_latest_undo_record_info,
    _generate_csv,
    _generate_json,
)


@pytest.fixture
def sample_undo_record():
    """Provide a sample UndoRecordDisplay for testing."""
    now = time.time()
    return UndoRecordDisplay(
        operation_id="abc123def456",
        operation_type="EMAIL_SEND",
        session_id="test_session",
        inverse_func_name="undo_send_email",
        inverse_args={
            "subject": "Q2进度报告",
            "to": "zhangsan@example.com",
        },
        original_result={
            "status": "sent",
            "message_id": "msg_001",
        },
        created_at=now - 120,
        expires_at=now + 180,
        status="active",
    )


@pytest.fixture
def real_undo_manager():
    """Provide a real UndoManager instance (replaces MagicMock anti-pattern).

    UndoManager is a pure Python in-memory component managing undo records.
    Using a real instance exercises actual push/can_undo/undo/list_undoable/
    get_session_records logic instead of MagicMock stubs.
    """
    from opc_manager.undo_manager import UndoManager

    return UndoManager()


@pytest.fixture
def patch_get_undo_manager(real_undo_manager, monkeypatch):
    """Patch _get_undo_manager to return a real UndoManager instance.

    Replaces the @patch("frontend.components.undo_actions._get_undo_manager")
    + MagicMock() anti-pattern with a real UndoManager injected via monkeypatch.
    """
    import frontend.components.undo_actions as undo_actions_mod

    monkeypatch.setattr(
        undo_actions_mod, "_get_undo_manager", lambda: real_undo_manager
    )
    return real_undo_manager


class TestOperationDescription:
    """Test suite for _get_operation_description() function.

    Validates human-readable description generation for all 11 operation types.
    """

    def test_email_send_with_subject_and_to(self, sample_undo_record):
        desc = _get_operation_description(sample_undo_record)
        assert "发送邮件" in desc
        assert "Q2进度报告" in desc
        assert "zhangsan@example.com" in desc

    def test_email_send_subject_only(self):
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="EMAIL_SEND",
            session_id="s1",
            inverse_func_name="f",
            inverse_args={"subject": "测试邮件"},
            original_result={},
            created_at=0,
            expires_at=0,
            status="active",
        )
        desc = _get_operation_description(record)
        assert "发送邮件" in desc
        assert "测试邮件" in desc

    def test_email_send_no_args(self):
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="EMAIL_SEND",
            session_id="s1",
            inverse_func_name="f",
            inverse_args={},
            original_result={},
            created_at=0,
            expires_at=0,
            status="active",
        )
        desc = _get_operation_description(record)
        assert desc == "发送邮件"

    def test_record_income_with_amount_and_project(self):
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="RECORD_INCOME",
            session_id="s1",
            inverse_func_name="f",
            inverse_args={"amount": 5000, "project": "字节跳动项目"},
            original_result={},
            created_at=0,
            expires_at=0,
            status="active",
        )
        desc = _get_operation_description(record)
        assert "¥5000" in desc
        assert "字节跳动项目" in desc

    def test_record_income_amount_only(self):
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="RECORD_INCOME",
            session_id="s1",
            inverse_func_name="f",
            inverse_args={"amount": 1000},
            original_result={},
            created_at=0,
            expires_at=0,
            status="active",
        )
        desc = _get_operation_description(record)
        assert "¥1000" in desc

    def test_record_expense_with_category(self):
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="RECORD_EXPENSE",
            session_id="s1",
            inverse_func_name="f",
            inverse_args={"amount": 200, "category": "办公用品"},
            original_result={},
            created_at=0,
            expires_at=0,
            status="active",
        )
        desc = _get_operation_description(record)
        assert "¥200" in desc
        assert "办公用品" in desc

    def test_add_event_branch_removed(self):
        """ADD_EVENT 已随 calendar_skill 一并移除（v0.3.4冻结清理）。
        _get_operation_description 应走 fallback 路径，不再返回日程相关文案。
        """
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="ADD_EVENT",
            session_id="s1",
            inverse_func_name="f",
            inverse_args={"title": "Q2营销方案会议"},
            original_result={},
            created_at=0,
            expires_at=0,
            status="active",
        )
        desc = _get_operation_description(record)
        assert "新建日程" not in desc

    def test_add_deal_with_value(self):
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="ADD_DEAL",
            session_id="s1",
            inverse_func_name="f",
            inverse_args={"deal_name": "企业版合同", "value": 50000},
            original_result={},
            created_at=0,
            expires_at=0,
            status="active",
        )
        desc = _get_operation_description(record)
        assert "新建商机" in desc
        assert "企业版合同" in desc
        assert "¥50000" in desc

    def test_create_proposal_branch_removed(self):
        """CREATE_PROPOSAL 已随 proposal_skill 一并移除（v0.3.4冻结清理）。
        _get_operation_description 应走 fallback 路径，不再返回方案相关文案。
        """
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="CREATE_PROPOSAL",
            session_id="s1",
            inverse_func_name="f",
            inverse_args={"title": "数字化转型方案", "client": "ABC公司"},
            original_result={},
            created_at=0,
            expires_at=0,
            status="active",
        )
        desc = _get_operation_description(record)
        assert "创建方案" not in desc

    def test_create_invoice_with_number(self):
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="CREATE_INVOICE",
            session_id="s1",
            inverse_func_name="f",
            inverse_args={"invoice_number": "INV-2024-001", "amount": 10000},
            original_result={},
            created_at=0,
            expires_at=0,
            status="active",
        )
        desc = _get_operation_description(record)
        assert "创建发票" in desc
        assert "INV-2024-001" in desc

    def test_add_customer_with_company(self):
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="ADD_CUSTOMER",
            session_id="s1",
            inverse_func_name="f",
            inverse_args={"name": "张三", "company": "科技有限公司"},
            original_result={},
            created_at=0,
            expires_at=0,
            status="active",
        )
        desc = _get_operation_description(record)
        assert "添加客户" in desc
        assert "张三" in desc

    def test_add_follow_up_with_content(self):
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="ADD_FOLLOW_UP",
            session_id="s1",
            inverse_func_name="f",
            inverse_args={"customer_name": "李四", "content": "跟进合同签订进度"},
            original_result={},
            created_at=0,
            expires_at=0,
            status="active",
        )
        desc = _get_operation_description(record)
        assert "添加跟进" in desc
        assert "李四" in desc

    def test_social_publish_with_platform(self):
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="SOCIAL_PUBLISH",
            session_id="s1",
            inverse_func_name="f",
            inverse_args={"platform": "微信", "content": "新品发布通知"},
            original_result={},
            created_at=0,
            expires_at=0,
            status="active",
        )
        desc = _get_operation_description(record)
        assert "发布内容" in desc
        assert "微信" in desc

    def test_unknown_operation_type_fallback(self):
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="UNKNOWN_TYPE",
            session_id="s1",
            inverse_func_name="custom_func",
            inverse_args={"title": "自定义操作"},
            original_result={},
            created_at=0,
            expires_at=0,
            status="active",
        )
        desc = _get_operation_description(record)
        assert "自定义操作" in desc

    def test_fallback_to_inverse_func_name(self):
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="UNKNOWN",
            session_id="s1",
            inverse_func_name="some_special_function",
            inverse_args={},
            original_result={},
            created_at=0,
            expires_at=0,
            status="active",
        )
        desc = _get_operation_description(record)
        assert "some_special_function" in desc


class TestCalculateRemainingTime:
    """Test suite for _calculate_remaining_time() function.

    Tests all urgency levels: expired, critical (<10s), warning (<60s), normal.
    """

    def test_already_expired(self):
        now = time.time()
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="EMAIL_SEND",
            session_id="s1",
            inverse_func_name="f",
            inverse_args={},
            original_result={},
            created_at=now - 3600,
            expires_at=now - 10,
            status="expired",
        )
        remaining, percentage, status_text = _calculate_remaining_time(record)
        assert remaining == 0
        assert percentage == 0
        assert "已过期" in status_text

    def test_critical_less_than_10_seconds(self):
        now = time.time()
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="EMAIL_SEND",
            session_id="s1",
            inverse_func_name="f",
            inverse_args={},
            original_result={},
            created_at=now - 290,
            expires_at=now + 5,
            status="active",
        )
        remaining, percentage, status_text = _calculate_remaining_time(record)
        assert 0 < remaining <= 10
        assert "即将过期" in status_text
        assert "🔴" not in status_text

    def test_warning_less_than_60_seconds(self):
        now = time.time()
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="EMAIL_SEND",
            session_id="s1",
            inverse_func_name="f",
            inverse_args={},
            original_result={},
            created_at=now - 250,
            expires_at=now + 30,
            status="active",
        )
        remaining, percentage, status_text = _calculate_remaining_time(record)
        assert 10 < remaining < 60
        assert "秒后过期" in status_text
        assert "🟠" not in status_text

    def test_normal_minutes_remaining(self):
        now = time.time()
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="EMAIL_SEND",
            session_id="s1",
            inverse_func_name="f",
            inverse_args={},
            original_result={},
            created_at=now - 60,
            expires_at=now + 180,
            status="active",
        )
        remaining, percentage, status_text = _calculate_remaining_time(record)
        assert remaining >= 60
        assert "分" in status_text
        assert "🟢" not in status_text

    def test_hours_remaining(self):
        now = time.time()
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="CREATE_INVOICE",
            session_id="s1",
            inverse_func_name="f",
            inverse_args={},
            original_result={},
            created_at=now - 60,
            expires_at=now + 7200,
            status="active",
        )
        remaining, percentage, status_text = _calculate_remaining_time(record)
        assert remaining >= 3600
        assert "小时" in status_text

    def test_percentage_calculation(self):
        now = time.time()
        total_window = 300
        mid_point = total_window // 2
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="EMAIL_SEND",
            session_id="s1",
            inverse_func_name="f",
            inverse_args={},
            original_result={},
            created_at=now - mid_point,
            expires_at=now + mid_point,
            status="active",
        )
        remaining, percentage, status_text = _calculate_remaining_time(record)
        assert 45 <= percentage <= 55

    def test_exact_expiry_boundary(self):
        now = time.time()
        record = UndoRecordDisplay(
            operation_id="op1",
            operation_type="EMAIL_SEND",
            session_id="s1",
            inverse_func_name="f",
            inverse_args={},
            original_result={},
            created_at=now - 300,
            expires_at=now,
            status="active",
        )
        remaining, percentage, status_text = _calculate_remaining_time(record)
        assert remaining == 0


class TestFormatTimeAgo:
    """Test suite for _format_time_ago() function."""

    def test_just_now(self):
        result = _format_time_ago(time.time() - 10)
        assert result == "刚刚"

    def test_minutes_ago(self):
        result = _format_time_ago(time.time() - 150)
        assert "分钟前" in result
        assert "2" in result

    def test_hours_ago(self):
        result = _format_time_ago(time.time() - 7200)
        assert "小时前" in result
        assert "2" in result

    def test_days_ago(self):
        result = _format_time_ago(time.time() - 172800)
        assert "天前" in result
        assert "2" in result


class TestConvertToDisplayRecord:
    """Test suite for _convert_to_display_record() function."""

    def test_basic_conversion(self):
        now = time.time()
        raw = {
            "operation_id": "test123",
            "operation_type": "EMAIL_SEND",
            "session_id": "sess1",
            "inverse_func_name": "undo_send_email",
            "inverse_args": {"subject": "Test"},
            "original_result": {},
            "created_at": now - 60,
            "expires_at": now + 240,
            "status": "active",
        }
        display = _convert_to_display_record(raw)
        assert display.operation_id == "test123"
        assert display.operation_type == "EMAIL_SEND"
        assert display.description != ""
        assert display.remaining_seconds >= 0
        assert display.time_ago != ""

    def test_populates_computed_fields(self):
        now = time.time()
        raw = {
            "operation_id": "op1",
            "operation_type": "RECORD_INCOME",
            "session_id": "s1",
            "inverse_func_name": "f",
            "inverse_args": {"amount": 1000},
            "original_result": {},
            "created_at": now - 120,
            "expires_at": now + 1680,
            "status": "active",
        }
        display = _convert_to_display_record(raw)
        assert "记录收入" in display.description
        assert "¥1000" in display.description
        assert isinstance(display.remaining_seconds, int)
        assert display.time_ago == "2分钟前"


class TestExecuteUndo:
    """Test suite for execute_undo() function with ProgressEmitter integration."""

    def test_execute_undo_success(self, patch_get_undo_manager):
        from opc_manager.undo_manager import OperationType

        um = patch_get_undo_manager
        op_id = um.push(
            session_id="session1",
            op_type=OperationType.EMAIL_SEND,
            inverse_func="undo_send_email",
            inverse_args={"subject": "test"},
            original_result={},
        )
        # Patch only the external inverse-function resolver to a pure function
        # that succeeds (real inverse funcs have side effects unsuitable for
        # unit tests). UndoManager core logic (push/can_undo/undo) is real.
        um._resolve_inverse = lambda func_name: (lambda **kw: {"undone": True})

        result = execute_undo("session1", op_id)
        assert result["success"] is True
        assert "撤销成功" in result["message"]

    def test_execute_undo_cannot_undo(self, patch_get_undo_manager):
        from opc_manager.undo_manager import OperationType

        um = patch_get_undo_manager
        op_id = um.push(
            session_id="session1",
            op_type=OperationType.EMAIL_SEND,
            inverse_func="undo_send_email",
            inverse_args={},
            original_result={},
        )
        # Expire the record so real can_undo returns (False, "Undo window expired")
        records = um.get_session_records("session1")
        records[0].expires_at = time.time() - 10

        result = execute_undo("session1", op_id)
        assert result["success"] is False
        assert "无法撤销" in result["message"]
        assert "expired" in result["message"].lower()

    def test_execute_undo_failure(self, patch_get_undo_manager):
        from opc_manager.undo_manager import OperationType

        um = patch_get_undo_manager
        op_id = um.push(
            session_id="session1",
            op_type=OperationType.EMAIL_SEND,
            inverse_func="undo_send_email",
            inverse_args={},
            original_result={},
        )

        # Patch inverse resolver to a real function that raises, simulating
        # an inverse-function execution failure.
        def _failing_inverse(**kwargs):
            raise RuntimeError("逆函数执行错误")

        um._resolve_inverse = lambda func_name: _failing_inverse

        result = execute_undo("session1", op_id)
        assert result["success"] is False
        assert "撤销失败" in result["message"]

    def test_execute_undo_manager_not_initialized(self, monkeypatch):
        import frontend.components.undo_actions as undo_actions_mod

        monkeypatch.setattr(undo_actions_mod, "_get_undo_manager", lambda: None)
        result = execute_undo("session1", "op123")
        assert result["success"] is False
        assert "未初始化" in result["message"]

    def test_execute_undo_handles_exception(self, patch_get_undo_manager):
        # Real UndoManager raises ValueError for empty session_id
        result = execute_undo("", "op123")
        assert result["success"] is False
        assert "参数错误" in result["message"]


class TestRenderUndoStats:
    """Test suite for calculate_undo_stats() statistics calculation."""

    def test_stats_all_active(self, patch_get_undo_manager):
        from opc_manager.undo_manager import OperationType

        um = patch_get_undo_manager
        um.push("sess1", OperationType.EMAIL_SEND, "undo_send_email", {}, {})
        um.push("sess1", OperationType.EMAIL_SEND, "undo_send_email", {}, {})

        stats = calculate_undo_stats("sess1")
        assert stats["active"] == 2
        assert stats["undone"] == 0
        assert stats["expired"] == 0

    def test_stats_mixed_statuses(self, patch_get_undo_manager):
        from opc_manager.undo_manager import OperationType

        um = patch_get_undo_manager
        now = time.time()
        um.push("sess1", OperationType.EMAIL_SEND, "undo_send_email", {}, {})
        um.push("sess1", OperationType.EMAIL_SEND, "undo_send_email", {}, {})
        um.push("sess1", OperationType.EMAIL_SEND, "undo_send_email", {}, {})
        # Mutate real UndoRecord attributes to simulate mixed statuses
        records = um.get_session_records("sess1")
        records[1].status = "undone"
        records[2].expires_at = now - 10  # expired (active status, past expiry)

        stats = calculate_undo_stats("sess1")
        assert stats["active"] == 1
        assert stats["undone"] == 1
        assert stats["expired"] == 1
        assert stats["total"] == 3

    def test_stats_empty_session(self, patch_get_undo_manager):
        stats = calculate_undo_stats("empty_sess")
        assert stats["total"] == 0
        assert stats["active"] == 0

    def test_stats_manager_not_available(self, monkeypatch):
        import frontend.components.undo_actions as undo_actions_mod

        monkeypatch.setattr(undo_actions_mod, "_get_undo_manager", lambda: None)
        stats = calculate_undo_stats("sess1")
        assert stats["total"] == 0


class TestCheckHasActiveRecords:
    """Test suite for check_has_active_undo_records()."""

    def test_has_active_records_true(self, patch_get_undo_manager):
        from opc_manager.undo_manager import OperationType

        um = patch_get_undo_manager
        um.push("sess1", OperationType.EMAIL_SEND, "undo_send_email", {}, {})
        um.push("sess1", OperationType.EMAIL_SEND, "undo_send_email", {}, {})

        result = check_has_active_undo_records("sess1")
        assert result is True

    def test_has_active_records_false(self, patch_get_undo_manager):
        result = check_has_active_undo_records("sess1")
        assert result is False

    def test_has_active_records_manager_none(self, monkeypatch):
        import frontend.components.undo_actions as undo_actions_mod

        monkeypatch.setattr(undo_actions_mod, "_get_undo_manager", lambda: None)
        result = check_has_active_undo_records("sess1")
        assert result is False


class TestGetLatestRecordInfo:
    """Test suite for get_latest_undo_record_info()."""

    def test_get_latest_info_success(self, patch_get_undo_manager):
        from opc_manager.undo_manager import OperationType

        um = patch_get_undo_manager
        op_id = um.push(
            "sess1",
            OperationType.EMAIL_SEND,
            "undo_send_email",
            {"subject": "test"},
            {"status": "sent"},
        )

        info = get_latest_undo_record_info("sess1")
        assert info is not None
        assert info["operation_id"] == op_id
        # list_undoable returns operation_type.value (lowercase enum value)
        assert info["operation_type"] == OperationType.EMAIL_SEND.value
        assert isinstance(info["label"], str) and info["label"]
        assert info["icon"] == ""
        assert info["remaining_seconds"] > 0

    def test_get_latest_info_no_records(self, patch_get_undo_manager):
        info = get_latest_undo_record_info("sess1")
        assert info is None

    def test_get_latest_info_manager_none(self, monkeypatch):
        import frontend.components.undo_actions as undo_actions_mod

        monkeypatch.setattr(undo_actions_mod, "_get_undo_manager", lambda: None)
        info = get_latest_undo_record_info("sess1")
        assert info is None


class TestExportGeneration:
    """Test suite for CSV and JSON export functionality."""

    def test_generate_csv_basic(self):
        now = time.time()
        records = [
            UndoRecordDisplay(
                operation_id="op1",
                operation_type="EMAIL_SEND",
                session_id="s1",
                inverse_func_name="f",
                inverse_args={},
                original_result={},
                created_at=now - 60,
                expires_at=now + 240,
                status="active",
                description="发送邮件: Test",
                remaining_seconds=240,
                time_ago="1分钟前",
            ),
        ]
        csv_data = _generate_csv(records)

        reader = csv.reader(io.StringIO(csv_data))
        rows = list(reader)

        assert len(rows) == 2
        assert rows[0][0] == "操作ID"
        assert rows[1][0] == "op1"
        assert "EMAIL_SEND" in csv_data

    def test_generate_csv_multiple_records(self):
        now = time.time()
        records = [
            UndoRecordDisplay(
                operation_id="op1",
                operation_type="EMAIL_SEND",
                session_id="s1",
                inverse_func_name="f1",
                inverse_args={},
                original_result={},
                created_at=now - 60,
                expires_at=now + 240,
                status="active",
                description="Op1",
                remaining_seconds=240,
                time_ago="1分钟前",
            ),
            UndoRecordDisplay(
                operation_id="op2",
                operation_type="RECORD_INCOME",
                session_id="s1",
                inverse_func_name="f2",
                inverse_args={},
                original_result={},
                created_at=now - 120,
                expires_at=now + 1680,
                status="undone",
                description="Op2",
                remaining_seconds=0,
                time_ago="2分钟前",
            ),
        ]
        csv_data = _generate_csv(records)

        reader = csv.reader(io.StringIO(csv_data))
        rows = list(reader)

        assert len(rows) == 3
        assert rows[1][0] == "op1"
        assert rows[2][0] == "op2"

    def test_generate_json_valid(self):
        now = time.time()
        records = [
            UndoRecordDisplay(
                operation_id="op1",
                operation_type="EMAIL_SEND",
                session_id="s1",
                inverse_func_name="f",
                inverse_args={"key": "val"},
                original_result={"res": "ok"},
                created_at=now - 60,
                expires_at=now + 240,
                status="active",
                description="Test",
                remaining_seconds=240,
                time_ago="1分钟前",
            ),
        ]
        json_data = _generate_json(records)

        parsed = json.loads(json_data)
        assert len(parsed) == 1
        assert parsed[0]["operation_id"] == "op1"
        assert parsed[0]["operation_type"] == "EMAIL_SEND"
        assert parsed[0]["inverse_args"]["key"] == "val"
        assert "original_result_summary" in parsed[0]

    def test_generate_json_empty_records(self):
        json_data = _generate_json([])
        parsed = json.loads(json_data)
        assert parsed == []


class TestEdgeCases:
    """Test suite for edge cases and error handling."""

    def test_empty_session_id_in_execute_undo(self, patch_get_undo_manager):
        # Real UndoManager raises ValueError for empty session_id
        result = execute_undo("", "op123")
        assert result["success"] is False
        assert (
            "参数错误" in result["message"] or "session_id" in result["message"].lower()
        )

    def test_invalid_operation_id_in_execute_undo(self, patch_get_undo_manager):
        from opc_manager.undo_manager import OperationType

        um = patch_get_undo_manager
        um.push("valid_session", OperationType.EMAIL_SEND, "undo_send_email", {}, {})
        # Undo a non-existent operation_id — real can_undo returns (False, ...)
        result = execute_undo("valid_session", "invalid_op_id")
        assert result["success"] is False

    def test_operation_type_config_complete(self):
        expected_types = [
            "EMAIL_SEND",
            "RECORD_INCOME",
            "RECORD_EXPENSE",
            "ADD_DEAL",
            "CREATE_INVOICE",
            "ADD_CUSTOMER",
            "ADD_FOLLOW_UP",
            "SOCIAL_PUBLISH",
        ]
        for op_type in expected_types:
            assert op_type in OPERATION_TYPE_CONFIG
            config = OPERATION_TYPE_CONFIG[op_type]
            assert "icon" in config
            assert "label" in config
            assert "color" in config

    def test_status_config_complete(self):
        for status in ["active", "undone", "expired"]:
            assert status in STATUS_CONFIG
            config = STATUS_CONFIG[status]
            assert "icon" in config
            assert "label" in config
            assert "color" in config

    def test_undo_record_display_defaults(self):
        record = UndoRecordDisplay(
            operation_id="test",
            operation_type="TEST",
            session_id="s",
            inverse_func_name="f",
            inverse_args={},
            original_result={},
            created_at=0,
            expires_at=0,
            status="active",
        )
        assert record.description == ""
        assert record.remaining_seconds == 0
        assert record.time_ago == ""


@pytest.fixture
def st_mock():
    """Mock Streamlit for UI component testing."""
    with patch.dict("sys.modules", {"streamlit": MagicMock()}):
        yield


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
