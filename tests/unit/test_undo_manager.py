"""
Undo Manager Unit Tests — Operation undo functionality validation.

Covers:
- OperationType enum values and undo windows
- UndoRecord dataclass defaults
- push: creates record, returns ID, enforces max per session
- can_undo: active record within window, expired record, not found, already undone
- undo: success execution (mocked), expired rejection, not found, invalid func name
- list_undoable: returns sorted list, filters by status
- cleanup_expired: removes expired records
- _validate_session_id: empty string, too long
- Thread safety basics

Run command:
    pytest tests/test_undo_manager.py -v --tb=short
"""

import time
import threading
from unittest.mock import patch, MagicMock

import pytest
from opc_manager.undo_manager import (
    OperationType,
    UNDO_WINDOWS_SECONDS,
    UndoRecord,
    UndoManager,
    UNDO_MAX_PER_SESSION,
    MAX_SESSION_ID_LENGTH,
)


@pytest.fixture
def manager():
    """Provide a fresh UndoManager instance per test."""
    return UndoManager()


class TestOperationTypeEnum:
    """Test suite for OperationType enum values."""

    def test_email_send_value(self):
        assert OperationType.EMAIL_SEND.value == "email_send"

    def test_record_income_value(self):
        assert OperationType.RECORD_INCOME.value == "record_income"

    def test_social_publish_value(self):
        assert OperationType.SOCIAL_PUBLISH.value == "social_publish"

    def test_all_operation_types_covered(self):
        types = list(OperationType)
        assert len(types) >= 8
        assert OperationType.CREATE_INVOICE in types
        assert OperationType.EMAIL_SEND in types


class TestUndoWindows:
    """Test suite for UNDO_WINDOWS_SECONDS configuration."""

    def test_email_window_is_300s(self):
        assert UNDO_WINDOWS_SECONDS[OperationType.EMAIL_SEND] == 300

    def test_social_publish_shortest_window(self):
        assert UNDO_WINDOWS_SECONDS[OperationType.SOCIAL_PUBLISH] == 60

    def test_record_income_window(self):
        assert UNDO_WINDOWS_SECONDS[OperationType.RECORD_INCOME] == 1800


class TestUndoRecordDefaults:
    """Test suite for UndoRecord dataclass default values."""

    def test_default_status_active(self):
        record = UndoRecord(
            operation_id="op1",
            operation_type=OperationType.EMAIL_SEND,
            session_id="sess1",
            inverse_func_name="undo_send_email",
            inverse_args={},
            original_result={"status": "sent"},
        )
        assert record.status == "active"
        assert record.expires_at == 0
        assert isinstance(record.created_at, float)

    def test_record_with_all_fields(self):
        record = UndoRecord(
            operation_id="op2",
            operation_type=OperationType.RECORD_INCOME,
            session_id="sess2",
            inverse_func_name="undo_record_income",
            inverse_args={"amount": 1000},
            original_result={"id": "rec1"},
            created_at=1000.0,
            expires_at=4600.0,
            status="active",
        )
        assert record.inverse_args == {"amount": 1000}
        assert record.expires_at == 4600.0


class TestPush:
    """Test suite for UndoManager.push()."""

    def test_push_returns_operation_id(self, manager):
        op_id = manager.push(
            "sess1", OperationType.EMAIL_SEND, "undo_send_email", {}, {"status": "sent"}
        )
        assert isinstance(op_id, str)
        assert len(op_id) > 0

    def test_push_creates_stored_record(self, manager):
        op_id = manager.push(
            "sess1", OperationType.EMAIL_SEND, "undo_send_email", {}, {"msg": "ok"}
        )
        assert "sess1" in manager._records
        records = manager._records["sess1"]
        assert len(records) == 1
        assert records[0].operation_id == op_id
        assert records[0].inverse_func_name == "undo_send_email"

    def test_push_sets_expires_at(self, manager):
        now = time.time()
        manager.push(
            "sess1", OperationType.SOCIAL_PUBLISH, "undo_publish_content", {}, {}
        )
        record = manager._records["sess1"][0]
        assert record.expires_at >= now + 59
        assert record.expires_at <= now + 61

    def test_push_enforces_max_per_session(self, manager):
        for i in range(UNDO_MAX_PER_SESSION + 10):
            manager.push(
                "sess1", OperationType.EMAIL_SEND, "undo_send_email", {}, {"i": i}
            )
        assert len(manager._records["sess1"]) <= UNDO_MAX_PER_SESSION

    def test_push_rejects_empty_session_id(self, manager):
        with pytest.raises(ValueError, match="session_id"):
            manager.push("", OperationType.EMAIL_SEND, "func", {}, {})

    def test_push_rejects_empty_inverse_func(self, manager):
        with pytest.raises(ValueError, match="inverse_func"):
            manager.push("sess1", OperationType.EMAIL_SEND, "", {}, {})


class TestCanUndo:
    """Test suite for UndoManager.can_undo()."""

    def test_can_undo_active_within_window(self, manager):
        op_id = manager.push(
            "sess1", OperationType.EMAIL_SEND, "undo_send_email", {}, {}
        )
        can, reason = manager.can_undo("sess1", op_id)
        assert can is True
        assert reason == ""

    def test_cannot_undo_expired_record(self, manager):
        op_id = manager.push(
            "sess1", OperationType.SOCIAL_PUBLISH, "undo_publish_content", {}, {}
        )
        record = manager._records["sess1"][0]
        record.expires_at = time.time() - 1
        can, reason = manager.can_undo("sess1", op_id)
        assert can is False
        assert "expired" in reason.lower()

    def test_cannot_undo_not_found(self, manager):
        can, reason = manager.can_undo("sess1", "nonexistent_id")
        assert can is False
        assert "not found" in reason.lower()

    def test_cannot_undo_already_undone(self, manager):
        op_id = manager.push(
            "sess1", OperationType.EMAIL_SEND, "undo_send_email", {}, {}
        )
        manager._records["sess1"][0].status = "undone"
        can, reason = manager.can_undo("sess1", op_id)
        assert can is False

    def test_can_undo_rejects_empty_session_id(self, manager):
        with pytest.raises(ValueError, match="session_id"):
            manager.can_undo("", "some_op_id")


class TestUndo:
    """Test suite for UndoManager.undo()."""

    @patch.object(UndoManager, "_resolve_inverse")
    def test_undo_success(self, mock_resolve, manager):
        mock_func = MagicMock(return_value={"undone": True})
        mock_resolve.return_value = mock_func

        op_id = manager.push(
            "sess1",
            OperationType.EMAIL_SEND,
            "undo_send_email",
            {"email_id": "em1"},
            {"status": "sent"},
        )
        result = manager.undo("sess1", op_id)

        assert result["success"] is True
        mock_func.assert_called_once_with(email_id="em1")
        assert manager._records["sess1"][0].status == "undone"

    def test_undo_expired_rejected(self, manager):
        op_id = manager.push(
            "sess1", OperationType.SOCIAL_PUBLISH, "undo_publish_content", {}, {}
        )
        manager._records["sess1"][0].expires_at = time.time() - 1
        result = manager.undo("sess1", op_id)
        assert result["success"] is False

    def test_undo_not_found(self, manager):
        result = manager.undo("sess1", "nonexistent")
        assert result["success"] is False

    @patch.object(UndoManager, "_resolve_inverse")
    def test_undo_invalid_func_name(self, mock_resolve, manager):
        mock_resolve.side_effect = ValueError("Unauthorized inverse function: bad_func")
        op_id = manager.push("sess1", OperationType.EMAIL_SEND, "bad_func", {}, {})
        result = manager.undo("sess1", op_id)
        assert result["success"] is False
        assert "error" in result


class TestListUndoable:
    """Test suite for UndoManager.list_undoable()."""

    def test_list_returns_sorted_desc(self, manager):
        id1 = manager.push("sess1", OperationType.EMAIL_SEND, "f", {}, {})
        import time as _time

        _time.sleep(0.01)
        id2 = manager.push("sess1", OperationType.CREATE_INVOICE, "f", {}, {})
        items = manager.list_undoable("sess1")
        assert items[0]["operation_id"] == id2
        assert items[1]["operation_id"] == id1

    def test_list_filters_out_non_active(self, manager):
        manager.push("sess1", OperationType.EMAIL_SEND, "f", {}, {})
        manager._records["sess1"][0].status = "undone"
        items = manager.list_undoable("sess1")
        assert len(items) == 0

    def test_list_empty_for_no_records(self, manager):
        items = manager.list_undoable("sess_new")
        assert items == []

    def test_list_includes_remaining_seconds(self, manager):
        manager.push(
            "sess1",
            OperationType.EMAIL_SEND,
            "undo_send_email",
            {},
            {"summary": "test summary data"},
        )
        items = manager.list_undoable("sess1")
        assert len(items) == 1
        assert "remaining_seconds" in items[0]
        assert items[0]["remaining_seconds"] >= 0
        assert "original_summary" in items[0]


class TestCleanupExpired:
    """Test suite for UndoManager.cleanup_expired()."""

    def test_cleanup_removes_expired_records(self, manager):
        manager.push("sess1", OperationType.SOCIAL_PUBLISH, "f", {}, {})
        manager.push("sess1", OperationType.EMAIL_SEND, "f", {}, {})
        manager._records["sess1"][0].expires_at = time.time() - 1
        manager.cleanup_expired()
        assert len(manager._records["sess1"]) == 1

    def test_cleanup_removes_empty_sessions(self, manager):
        manager.push("sess1", OperationType.SOCIAL_PUBLISH, "f", {}, {})
        manager._records["sess1"][0].expires_at = time.time() - 1
        manager.cleanup_expired()
        assert "sess1" not in manager._records

    def test_cleanup_keeps_active_records(self, manager):
        manager.push("sess1", OperationType.EMAIL_SEND, "f", {}, {})
        manager.cleanup_expired()
        assert len(manager._records["sess1"]) == 1


class TestValidateSessionId:
    """Test suite for _validate_session_id static method."""

    def test_reject_empty_string(self):
        with pytest.raises(ValueError, match="session_id"):
            UndoManager._validate_session_id("")

    def test_reject_none(self):
        with pytest.raises(ValueError, match="session_id"):
            UndoManager._validate_session_id(None)

    def test_reject_too_long(self):
        long_id = "a" * (MAX_SESSION_ID_LENGTH + 1)
        with pytest.raises(ValueError, match="maximum length"):
            UndoManager._validate_session_id(long_id)

    def test_accept_valid_session_id(self):
        UndoManager._validate_session_id("valid-session-id-123")


class TestGenId:
    """Test suite for _gen_id static method."""

    def test_gen_id_format(self):
        op_id = UndoManager._gen_id()
        assert isinstance(op_id, str)
        assert len(op_id) == 12
        assert all(c in "0123456789abcdef" for c in op_id)

    def test_gen_ids_are_unique(self):
        ids = {UndoManager._gen_id() for _ in range(100)}
        assert len(ids) == 100


class TestThreadSafetyBasics:
    """Basic thread safety checks for UndoManager."""

    def test_concurrent_pushes_do_not_crash(self, manager):
        errors = []

        def push_worker():
            try:
                for i in range(20):
                    manager.push(
                        f"sess_{threading.current_thread().ident}",
                        OperationType.EMAIL_SEND,
                        "undo_send_email",
                        {},
                        {"i": i},
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=push_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent pushes raised errors: {errors}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
