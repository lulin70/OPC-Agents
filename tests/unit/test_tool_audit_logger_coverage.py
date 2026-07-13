"""AuditLogger 覆盖率补充测试

覆盖 async writer loop、shutdown、log_async、query、_write_sync error handling
等未覆盖路径。
"""

import asyncio
import os

import pytest

from opc_manager.tool_audit_logger import AuditLogger


@pytest.fixture(autouse=True)
def _reset_audit_logger(tmp_path):
    """每个测试前重置 AuditLogger 类级状态，使用 tmp_path 避免污染。"""
    log_file = str(tmp_path / "audit.jsonl")
    AuditLogger.configure(log_file)
    AuditLogger._write_queue = None
    AuditLogger._writer_task = None
    AuditLogger._shutdown_event = None
    yield
    # 清理：关闭 writer task
    if AuditLogger._writer_task and not AuditLogger._writer_task.done():
        AuditLogger._writer_task.cancel()
    AuditLogger._write_queue = None
    AuditLogger._writer_task = None
    AuditLogger._shutdown_event = None


class TestAuditLoggerAsync:
    """覆盖 log_async / _start_writer / shutdown async 路径。"""

    @pytest.mark.asyncio
    async def test_log_async_writes_record(self):
        await AuditLogger.log_async("TEST_EVENT", {"key": "value"})
        # 给 writer 一点时间处理
        await asyncio.sleep(0.2)
        await AuditLogger.shutdown()

        records = AuditLogger.query()
        assert any(r["event_type"] == "TEST_EVENT" for r in records)

    @pytest.mark.asyncio
    async def test_log_async_multiple_records(self):
        for i in range(5):
            await AuditLogger.log_async("BATCH_EVENT", {"index": i})
        await asyncio.sleep(0.3)
        await AuditLogger.shutdown()

        records = AuditLogger.query(event_type="BATCH_EVENT")
        assert len(records) == 5

    @pytest.mark.asyncio
    async def test_shutdown_drains_queue(self):
        for i in range(3):
            await AuditLogger.log_async("DRAIN_EVENT", {"i": i})
        await AuditLogger.shutdown()

        records = AuditLogger.query(event_type="DRAIN_EVENT")
        assert len(records) == 3

    @pytest.mark.asyncio
    async def test_shutdown_when_not_started(self):
        # shutdown should be safe even if writer was never started
        await AuditLogger.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_cancels_stale_task(self):
        await AuditLogger.log_async("EVENT", {})
        await asyncio.sleep(0.1)
        # Don't set shutdown event, just cancel
        await AuditLogger.shutdown()


class TestAuditLoggerSync:
    """覆盖 log() sync fallback 和 _write_sync。"""

    def test_log_sync_outside_event_loop(self):
        # log() called outside async context falls back to _write_sync
        AuditLogger.log("SYNC_EVENT", {"data": "test"})

        records = AuditLogger.query(event_type="SYNC_EVENT")
        assert len(records) == 1
        assert records[0]["details"]["data"] == "test"

    def test_log_sync_writes_timestamp(self):
        AuditLogger.log("TS_EVENT", {})

        records = AuditLogger.query(event_type="TS_EVENT")
        assert len(records) == 1
        assert "timestamp" in records[0]

    def test_write_sync_creates_directory(self, tmp_path):
        nested = str(tmp_path / "nested" / "deep" / "audit.jsonl")
        AuditLogger.configure(nested)
        AuditLogger.log("NESTED_EVENT", {})

        assert os.path.isfile(nested)
        records = AuditLogger.query(event_type="NESTED_EVENT")
        assert len(records) == 1


class TestAuditLoggerQuery:
    """覆盖 query() 过滤逻辑。"""

    def test_query_by_event_type(self):
        AuditLogger.log("TYPE_A", {})
        AuditLogger.log("TYPE_B", {})
        AuditLogger.log("TYPE_A", {})

        a_records = AuditLogger.query(event_type="TYPE_A")
        assert len(a_records) == 2

    def test_query_empty_log_file(self, tmp_path):
        AuditLogger.configure(str(tmp_path / "nonexistent.jsonl"))
        records = AuditLogger.query()
        assert records == []

    def test_query_with_time_filter(self):
        AuditLogger.log("TIME_EVENT", {})
        # Query with future end_time should return the record
        records = AuditLogger.query(
            event_type="TIME_EVENT",
            start_time="2000-01-01",
            end_time="2099-12-31",
        )
        assert len(records) == 1

        # Query with past end_time should return nothing
        records_past = AuditLogger.query(
            event_type="TIME_EVENT",
            start_time="2000-01-01",
            end_time="2000-01-02",
        )
        assert len(records_past) == 0


class TestAuditLoggerConfigure:
    """覆盖 configure()。"""

    def test_configure_changes_log_file(self, tmp_path):
        new_file = str(tmp_path / "custom.jsonl")
        AuditLogger.configure(new_file)
        AuditLogger.log("CUSTOM_EVENT", {})

        assert os.path.isfile(new_file)
        records = AuditLogger.query(event_type="CUSTOM_EVENT")
        assert len(records) == 1
