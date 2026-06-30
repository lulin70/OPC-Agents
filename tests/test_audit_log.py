"""
Audit Log Unit Tests — Operation auditing and logging validation.

Covers:
- AuditRecord dataclass defaults
- _audit_sanitize: redacts sensitive patterns, truncates normal text
- log: creates record, returns ID, handles empty input, different statuses
- query: filter by session_id, operation_type, limit validation, since timestamp
- get_stats: total/success/failed/rate/duration calculations
- cleanup: removes old records
- MAX_MEMORY_LOGS cap (1000)
- Singleton pattern: same instance returned

Run command:
    pytest tests/test_audit_log.py -v --tb=short
"""

import time

import pytest
from opc_manager.audit_log import (
    AuditRecord,
    AuditLog,
    AUDIT_MAX_MEMORY_LOGS,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset AuditLog singleton before each test for isolation."""
    original = AuditLog._instance
    if original is not None:
        original.stop(wait=True)
    AuditLog._instance = None
    yield
    # Stop any instance created during the test to release DB connections.
    current = AuditLog._instance
    if current is not None and current is not original:
        current.stop(wait=True)
    AuditLog._instance = original


@pytest.fixture
def audit_log():
    """Provide a fresh AuditLog singleton instance."""
    import opc_manager.audit_log as al_module

    if not hasattr(al_module, "MAX_QUERY_OUTPUT_LENGTH"):
        al_module.MAX_QUERY_OUTPUT_LENGTH = 500
    return AuditLog()


class TestAuditRecordDefaults:
    """Test suite for AuditRecord dataclass default values."""

    def test_default_error_msg_empty(self):
        record = AuditRecord(
            id="abc123",
            session_id="sess1",
            user_id="user1",
            timestamp=time.time(),
            operation_type="EMAIL_SEND",
            skill_id="email_skill",
            input_hash="hash123",
            input_summary="test input",
            output_summary="test output",
            duration_ms=50,
            status="success",
        )
        assert record.error_msg == ""

    def test_all_fields_populated(self):
        record = AuditRecord(
            id="id1",
            session_id="s1",
            user_id="u1",
            timestamp=1000.0,
            operation_type="SEARCH",
            skill_id="search_skill",
            input_hash="aabbcc",
            input_summary="search query",
            output_summary="results here",
            duration_ms=120,
            status="success",
            error_msg="",
        )
        assert record.id == "id1"
        assert record.session_id == "s1"
        assert record.operation_type == "SEARCH"
        assert record.status == "success"


class TestAuditSanitize:
    """Test suite for _audit_sanitize redaction and truncation."""

    def test_redacts_password(self):
        result = AuditLog._audit_sanitize("enter password=secret123")
        assert result == "***REDACTED***"

    def test_redacts_credit_card(self):
        result = AuditLog._audit_sanitize("card_number=4111111111111111")
        assert result == "***REDACTED***"

    def test_redacts_ssn(self):
        result = AuditLog._audit_sanitize("ssn=123-45-6789")
        assert result == "***REDACTED***"

    def test_truncates_long_text(self):
        long_text = "x" * 300
        result = AuditLog._audit_sanitize(long_text)
        assert len(result) <= 200
        assert result == "x" * 200

    def test_short_text_unchanged(self):
        text = "normal log message"
        result = AuditLog._audit_sanitize(text)
        assert result == text

    def test_empty_text_returns_empty(self):
        result = AuditLog._audit_sanitize("")
        assert result == ""


class TestLogMethod:
    """Test suite for AuditLog.log()."""

    def test_log_creates_record_and_returns_id(self, audit_log):
        record_id = audit_log.log(
            session_id="sess1",
            operation_type="EMAIL_SEND",
            skill_id="email_skill",
            input_text="send hello email",
            output_data={"status": "sent"},
            duration_ms=42,
        )
        assert isinstance(record_id, str)
        assert len(record_id) == 12
        assert len(audit_log._logs) == 1

    def test_log_handles_empty_input_text(self, audit_log):
        record_id = audit_log.log(
            session_id="sess1",
            operation_type="SEARCH",
            skill_id="search",
            input_text="",
            output_data=None,
            duration_ms=10,
        )
        assert record_id is not None
        record = list(audit_log._logs)[-1]
        assert record.input_summary == ""

    def test_log_with_failed_status(self, audit_log):
        audit_log.log(
            session_id="sess1",
            operation_type="EMAIL_SEND",
            skill_id="email",
            input_text="send mail",
            output_data=None,
            duration_ms=100,
            status="failed",
            error_msg="SMTP connection failed",
        )
        record = list(audit_log._logs)[-1]
        assert record.status == "failed"
        assert "SMTP" in record.error_msg

    def test_log_with_cancelled_status(self, audit_log):
        audit_log.log(
            session_id="sess1",
            operation_type="TASK_CREATE",
            skill_id="task",
            input_text="create task",
            output_data=None,
            duration_ms=5,
            status="cancelled",
        )
        record = list(audit_log._logs)[-1]
        assert record.status == "cancelled"

    def test_log_stores_input_hash(self, audit_log):
        audit_log.log(
            session_id="sess1",
            operation_type="SEARCH",
            skill_id="search",
            input_text="test input text",
            output_data="result",
            duration_ms=10,
        )
        record = list(audit_log._logs)[-1]
        assert len(record.input_hash) == 64
        assert all(c in "0123456789abcdef" for c in record.input_hash)

    def test_log_truncates_output_summary(self, audit_log):
        long_output = "y" * 600
        audit_log.log(
            session_id="sess1",
            operation_type="SEARCH",
            skill_id="search",
            input_text="q",
            output_data=long_output,
            duration_ms=10,
        )
        record = list(audit_log._logs)[-1]
        assert len(record.output_summary) <= 500


class TestQueryMethod:
    """Test suite for AuditLog.query()."""

    def _seed_logs(self, audit_log, count=5):
        for i in range(count):
            audit_log.log(
                session_id=f"sess_{i % 2}",
                operation_type="EMAIL_SEND" if i % 2 == 0 else "SEARCH",
                skill_id="skill",
                input_text=f"input {i}",
                output_data={"i": i},
                duration_ms=i * 10,
            )

    def test_query_returns_records(self, audit_log):
        self._seed_logs(audit_log, 3)
        results = audit_log.query()
        assert len(results) == 3

    def test_query_filter_by_session_id(self, audit_log):
        self._seed_logs(audit_log, 4)
        results = audit_log.query(session_id="sess_0")
        assert len(results) >= 1

    def test_query_filter_by_operation_type(self, audit_log):
        self._seed_logs(audit_log, 4)
        results = audit_log.query(operation_type="SEARCH")
        assert all(r["operation_type"] == "SEARCH" for r in results)

    def test_query_limit_works(self, audit_log):
        self._seed_logs(audit_log, 10)
        results = audit_log.query(limit=3)
        assert len(results) <= 3

    def test_query_limit_must_be_positive(self, audit_log):
        with pytest.raises(ValueError, match="positive integer"):
            audit_log.query(limit=0)

    def test_query_limit_exceeds_max(self, audit_log):
        with pytest.raises(ValueError, match="exceed 1000"):
            audit_log.query(limit=1001)

    def test_query_since_timestamp_filters_old(self, audit_log):
        audit_log.log("sess1", "OP", "sk", "old", None, 10)
        time.sleep(0.05)
        recent_time = time.time()
        time.sleep(0.05)
        audit_log.log("sess1", "OP", "sk", "new", None, 10)
        results = audit_log.query(since=recent_time)
        assert len(results) >= 1

    def test_query_result_format(self, audit_log):
        audit_log.log("s1", "EMAIL", "em", "in", {"out": True}, 50)
        results = audit_log.query()
        assert len(results) == 1
        row = results[0]
        assert "id" in row
        assert "timestamp" in row
        assert "operation_type" in row
        assert "skill_id" in row
        assert "status" in row
        assert "duration_ms" in row


class TestGetStats:
    """Test suite for AuditLog.get_stats()."""

    def test_stats_empty(self, audit_log):
        stats = audit_log.get_stats()
        assert stats["total"] == 0
        assert stats["success"] == 0
        assert stats["failed"] == 0
        assert stats["success_rate"] == "0.0%"

    def test_stats_all_success(self, audit_log):
        for _ in range(5):
            audit_log.log("s1", "OP", "sk", "in", "out", 10, status="success")
        stats = audit_log.get_stats()
        assert stats["total"] == 5
        assert stats["success"] == 5
        assert stats["failed"] == 0
        assert stats["success_rate"] == "100.0%"

    def test_stats_mixed_results(self, audit_log):
        audit_log.log("s1", "OP", "sk", "in", "ok", 10, status="success")
        audit_log.log("s1", "OP", "sk", "in", None, 20, status="failed")
        audit_log.log("s1", "OP", "sk", "in", None, 5, status="cancelled")
        stats = audit_log.get_stats()
        assert stats["total"] == 3
        assert stats["success"] == 1
        assert stats["failed"] == 2

    def test_stats_avg_duration(self, audit_log):
        audit_log.log("s1", "OP", "sk", "in", "out", 100)
        audit_log.log("s1", "OP", "sk", "in", "out", 200)
        stats = audit_log.get_stats()
        assert stats["avg_duration_ms"] == 150

    def test_stats_filter_by_session(self, audit_log):
        audit_log.log("s1", "OP", "sk", "in", "out", 10, status="success")
        audit_log.log("s2", "OP", "sk", "in", None, 10, status="failed")
        stats = audit_log.get_stats(session_id="s1")
        assert stats["total"] == 1
        assert stats["success"] == 1


class TestCleanup:
    """Test suite for AuditLog.cleanup()."""

    def test_cleanup_removes_old_records(self, audit_log):
        audit_log.log("s1", "OP", "sk", "old", None, 10)
        future_time = time.time() + 86400
        audit_log.cleanup(before_timestamp=future_time)
        assert len(audit_log._logs) == 0

    def test_cleanup_keeps_recent_records(self, audit_log):
        audit_log.log("s1", "OP", "sk", "new", None, 10)
        past_time = time.time() - 86400
        audit_log.cleanup(before_timestamp=past_time)
        assert len(audit_log._logs) >= 1


class TestMaxMemoryLogsCap:
    """Test suite for AUDIT_MAX_MEMORY_LOGS cap behavior."""

    def test_logs_capped_at_max(self, audit_log):
        for i in range(AUDIT_MAX_MEMORY_LOGS + 50):
            audit_log.log("s1", "OP", "sk", f"in{i}", f"out{i}", 1)
        assert len(audit_log._logs) <= AUDIT_MAX_MEMORY_LOGS


class TestSingletonPattern:
    """Test suite for singleton behavior."""

    def test_same_instance_returned(self):
        a1 = AuditLog()
        a2 = AuditLog()
        assert a1 is a2

    def test_reset_allows_new_instance(self):
        a1 = AuditLog()
        a1.stop(wait=True)
        AuditLog._instance = None
        a2 = AuditLog()
        assert a1 is not a2


class TestChainHash:
    """Test suite for audit log chain hash (防篡改链式哈希)."""

    @pytest.fixture(autouse=True)
    def clean_audit_db(self):
        """清空 audit_log 表并重置 _last_hash，保证测试隔离。"""
        try:
            from opc_manager.data_manager import init_db, execute_write
            init_db()
            execute_write("DELETE FROM audit_log", (), many=False)
        except Exception:
            pass
        yield
        # 测试后再清空，避免影响后续测试
        try:
            from opc_manager.data_manager import init_db, execute_write
            init_db()
            execute_write("DELETE FROM audit_log", (), many=False)
        except Exception:
            pass

    def _setup_genesis(self, audit_log):
        """设置 genesis 起点并跳过 DB 恢复（测试隔离）。"""
        audit_log._last_hash = "0" * 64
        audit_log._started = True  # 跳过 log() 中的 _recover_last_hash 调用
        # 手动启动 writer（_started=True 时 log() 不会自动启动）
        audit_log._start_background_writer()

    def test_first_record_uses_genesis_prev_hash(self, audit_log):
        """首条记录 prev_hash = GENESIS_HASH（全零）。"""
        self._setup_genesis(audit_log)
        audit_log.log(
            session_id="s1", operation_type="TEST", skill_id="test",
            input_text="first", output_data="ok", duration_ms=10,
        )
        audit_log.stop(wait=True)
        with audit_log._lock:
            records = list(audit_log._logs)
        assert len(records) == 1
        assert records[0].prev_hash == "0" * 64
        assert records[0].current_hash != ""
        assert records[0].current_hash != "0" * 64

    def test_chain_links_consecutive_records(self, audit_log):
        """连续记录链式链接：第二条 prev_hash = 第一条 current_hash。"""
        self._setup_genesis(audit_log)
        audit_log.log(
            session_id="s1", operation_type="OP1", skill_id="test",
            input_text="first", output_data="ok", duration_ms=10,
        )
        audit_log.log(
            session_id="s1", operation_type="OP2", skill_id="test",
            input_text="second", output_data="ok", duration_ms=10,
        )
        audit_log.stop(wait=True)
        with audit_log._lock:
            records = list(audit_log._logs)
        assert len(records) == 2
        assert records[1].prev_hash == records[0].current_hash
        assert records[0].current_hash != records[1].current_hash

    def test_current_hash_deterministic(self, audit_log):
        """相同输入产生相同 current_hash（可重算验证）。"""
        import hashlib

        self._setup_genesis(audit_log)
        audit_log.log(
            session_id="s1", operation_type="DETERMINISTIC", skill_id="test",
            input_text="payload", output_data="ok", duration_ms=5,
        )
        audit_log.stop(wait=True)
        with audit_log._lock:
            r = audit_log._logs[-1]
        # 重算 current_hash
        recomputed = hashlib.sha256(
            f"{r.prev_hash}{r.timestamp}{r.operation_type}{r.input_hash}".encode()
        ).hexdigest()
        assert r.current_hash == recomputed

    def test_last_hash_updated_after_log(self, audit_log):
        """log() 后 _last_hash 更新为最新 current_hash。"""
        self._setup_genesis(audit_log)
        audit_log.log(
            session_id="s1", operation_type="UPDATE", skill_id="test",
            input_text="x", output_data="y", duration_ms=1,
        )
        audit_log.stop(wait=True)
        with audit_log._lock:
            last_record = audit_log._logs[-1]
        assert audit_log._last_hash == last_record.current_hash

    def test_verify_chain_valid_after_multiple_logs(self, audit_log):
        """多条记录后内存 _logs 链式哈希完整。"""
        import hashlib
        self._setup_genesis(audit_log)
        for i in range(5):
            audit_log.log(
                session_id="s1", operation_type=f"OP{i}", skill_id="test",
                input_text=f"input{i}", output_data="ok", duration_ms=i,
            )
        audit_log.stop(wait=True)
        with audit_log._lock:
            records = list(audit_log._logs)
        # 验证内存链完整性（不依赖 writer 线程 DB 写入时序）
        assert len(records) == 5
        prev_expected = "0" * 64
        for r in records:
            assert r.prev_hash == prev_expected
            recomputed = hashlib.sha256(
                f"{r.prev_hash}{r.timestamp}{r.operation_type}{r.input_hash}".encode()
            ).hexdigest()
            assert r.current_hash == recomputed
            prev_expected = r.current_hash

    def test_verify_chain_empty_db_valid(self, audit_log):
        """空 DB 时 verify_chain() 返回 valid=True。"""
        # 主动清空 DB（避免其他测试 writer 线程遗留数据）
        try:
            from opc_manager.data_manager import init_db, execute_write
            init_db()
            execute_write("DELETE FROM audit_log", (), many=False)
        except Exception:
            pass
        result = audit_log.verify_chain(limit=100)
        assert result["valid"] is True
        assert result["total"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
