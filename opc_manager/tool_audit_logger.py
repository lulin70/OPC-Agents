"""
Tool Audit Logger - Async audit logging for tool operations.

Extracted from tool_system.py for separation of concerns:
- Audit layer: async write queue, JSONL persistence, query (this module)
- Tool layer: registration, execution, permission (tool_system.py)

AuditLogger is self-contained: depends only on stdlib + AUDIT_LOG_FILE constant.
Dependency direction (one-way): tool_system.py --> tool_audit_logger.py (re-export)
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

AUDIT_LOG_FILE = "logs/security_audit.jsonl"


class AuditLogger:
    _log_file = AUDIT_LOG_FILE
    _write_queue: Optional[asyncio.Queue] = None
    _writer_task: Optional[asyncio.Task] = None
    _shutdown_event: Optional[asyncio.Event] = None

    @classmethod
    def configure(cls, log_file: str) -> None:
        cls._log_file = log_file

    @classmethod
    def _ensure_queue(cls) -> asyncio.Queue:
        if cls._write_queue is None:
            cls._write_queue = asyncio.Queue(maxsize=1000)
        return cls._write_queue

    @classmethod
    async def _start_writer(cls) -> None:
        if cls._writer_task is not None and not cls._writer_task.done():
            return
        queue = cls._ensure_queue()
        if cls._shutdown_event is None:
            cls._shutdown_event = asyncio.Event()
        shutdown = cls._shutdown_event

        async def _writer() -> None:
            try:
                os.makedirs(os.path.dirname(cls._log_file), exist_ok=True)
            except OSError:
                pass
            while not shutdown.is_set():
                try:
                    record = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                try:
                    with open(cls._log_file, "a") as f:
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")
                except Exception as e:
                    logger.error("审计日志写入失败: %s", e)
                finally:
                    queue.task_done()
            while not queue.empty():
                try:
                    record = queue.get_nowait()
                    with open(cls._log_file, "a") as f:
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    queue.task_done()
                except Exception as e:
                    logger.warning("[ToolSystem] Writer loop error: %s", e)
                    break

        cls._writer_task = asyncio.create_task(_writer())

    @classmethod
    async def shutdown(cls) -> None:
        if cls._shutdown_event is not None:
            cls._shutdown_event.set()
        if cls._writer_task is not None and not cls._writer_task.done():
            try:
                await asyncio.wait_for(cls._writer_task, timeout=5.0)
            except asyncio.TimeoutError:
                cls._writer_task.cancel()
        cls._writer_task = None
        cls._shutdown_event = None

    @classmethod
    async def log_async(cls, event_type: str, details: Dict[str, Any]) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "details": details,
        }
        try:
            await cls._start_writer()
            queue = cls._ensure_queue()
            try:
                queue.put_nowait(record)
            except asyncio.QueueFull:
                logger.warning("审计日志队列已满，同步写入")
                cls._write_sync(record)
        except RuntimeError:
            cls._write_sync(record)

    @classmethod
    def log(cls, event_type: str, details: Dict[str, Any]) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "details": details,
        }
        try:
            asyncio.get_running_loop()
            queue = cls._ensure_queue()
            try:
                queue.put_nowait(record)
                if cls._writer_task is None or cls._writer_task.done():
                    asyncio.create_task(cls._start_writer())
            except asyncio.QueueFull:
                cls._write_sync(record)
        except RuntimeError:
            cls._write_sync(record)

    @classmethod
    def _write_sync(cls, record: Dict[str, Any]) -> None:
        try:
            os.makedirs(os.path.dirname(cls._log_file), exist_ok=True)
            with open(cls._log_file, "a") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("审计日志写入失败: %s", e)

    @classmethod
    def flush(cls) -> None:
        """同步刷新所有待写入的审计记录到文件.

        Sprint 4.3 fix: AuditLogger.log() 在有 event loop 时走异步队列路径，
        测试中调用 query() 前需确保队列中的记录已持久化.
        此方法将队列中所有待写入记录同步写入文件，确保测试能查询到.
        """
        if cls._write_queue is None:
            return
        # 从队列中取出所有待写入记录，同步写入文件
        while not cls._write_queue.empty():
            try:
                record = cls._write_queue.get_nowait()
                cls._write_sync(record)
                cls._write_queue.task_done()
            except Exception:
                break

    @classmethod
    def query(
        cls,
        event_type: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> List[Dict]:
        results = []
        try:
            with open(cls._log_file, "r") as f:
                for line in f:
                    record = json.loads(line.strip())
                    if event_type and record.get("event_type") != event_type:
                        continue
                    ts = record.get("timestamp", "")
                    if start_time and ts < start_time:
                        continue
                    if end_time and ts > end_time:
                        continue
                    results.append(record)
        except FileNotFoundError:
            pass
        return results
