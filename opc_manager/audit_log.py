import threading
import time
import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional
from collections import deque
from queue import Queue, Empty
from opc_manager.utils import SECONDS_PER_DAY

logger = logging.getLogger(__name__)

"""Audit logging system for OPC-Agents.

Provides comprehensive operation auditing with in-memory storage,
background database persistence, and query capabilities.
Implements singleton pattern for global access.
"""


@dataclass
class AuditRecord:
    """Represents a single audit log entry.

    Attributes:
        id: Unique record identifier (12-char hex).
        session_id: Session this operation belongs to.
        user_id: User who performed the operation.
        timestamp: Unix timestamp of the operation.
        operation_type: Type of operation performed.
        skill_id: Skill/module that executed the operation.
        input_hash: SHA-256 hash of input for integrity checking.
        input_summary: Truncated input text (max 200 chars).
        output_summary: Truncated output text (max 500 chars).
        duration_ms: Operation duration in milliseconds.
        status: Operation status ('success', 'failed', 'cancelled').
        error_msg: Error message if operation failed.
        prev_hash: Previous record's current_hash (chain integrity).
        current_hash: This record's hash = sha256(prev_hash + timestamp
            + operation_type + input_hash). First record uses GENESIS_HASH.
    """

    id: str
    session_id: str
    user_id: str
    timestamp: float
    operation_type: str
    skill_id: str
    input_hash: str
    input_summary: str
    output_summary: str
    duration_ms: int
    status: str
    error_msg: str = ""
    prev_hash: str = ""
    current_hash: str = ""


# Genesis hash for the first record in the chain (64 hex zeros).
GENESIS_HASH = "0" * 64

AUDIT_MAX_MEMORY_LOGS = 1000
AUDIT_WRITE_BATCH_SIZE = 10
AUDIT_RETENTION_DAYS = 90
AUDIT_MAX_QUERY_OUTPUT_LENGTH = 500
MAX_AUDIT_ENTRIES = 10000
AUDIT_MAX_DB_ROWS = 100000

AUDIT_SENSITIVE_PATTERNS = [
    "password",
    "passwd",
    "pwd",
    "secret",
    "api_key",
    "apikey",
    "token",
    "auth",
    "credential",
    "private_key",
    "access_key",
    "credit_card",
    "card_number",
    "ssn",
    "social_security",
]


class AuditLog:
    """Singleton audit log manager with background persistence.

    Thread-safe implementation using deque for in-memory storage
    with configurable retention and batch database writes.

    Attributes:
        _instance: Singleton instance.
        _lock: Threading lock for thread safety.
    """

    _instance = None
    _lock = threading.Lock()

    # Instance attributes initialized in __new__
    _logs: Deque[AuditRecord]
    _write_queue: Queue
    _started: bool
    _stop_event: threading.Event
    _cleanup_counter: int
    _cleanup_needed: bool
    _writer_thread: Optional[threading.Thread]
    _last_hash: str  # 链式哈希：最后一条记录的 current_hash

    def __new__(cls) -> "AuditLog":
        """Create or return singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._logs = deque(maxlen=AUDIT_MAX_MEMORY_LOGS)
                    cls._instance._write_queue = Queue()
                    cls._instance._started = False
                    cls._instance._stop_event = threading.Event()
                    cls._instance._cleanup_counter = 0
                    cls._instance._cleanup_needed = False
                    cls._instance._writer_thread = None
                    cls._instance._last_hash = GENESIS_HASH
        return cls._instance

    @staticmethod
    def _audit_sanitize(text: str, max_length: int = 200) -> str:
        text_lower = text.lower()
        for pattern in AUDIT_SENSITIVE_PATTERNS:
            if pattern in text_lower:
                return "***REDACTED***"
        return text[:max_length]

    def __init__(self) -> None:
        pass

    def _init_db_connection(self) -> None:
        try:
            from opc_manager.data_manager import init_db

            init_db()
            logger.info("AuditLog database connection initialized")
        except Exception as e:
            logger.warning("AuditLog failed to initialize database connection: %s", e)

    def _recover_last_hash(self) -> None:
        """进程重启后从 DB 恢复链式哈希的最后一条 current_hash。

        保证重启后新日志与旧日志形成连续链，防止链断裂导致防篡改失效。
        仅在首次 log() 时调用一次（持有 _lock）。
        """
        try:
            from opc_manager.data_manager import init_db, execute_query

            init_db()
            rows = execute_query(
                "SELECT current_hash FROM audit_log "
                "WHERE current_hash != '' ORDER BY timestamp DESC LIMIT 1"
            )
            if rows and rows[0]["current_hash"]:
                self._last_hash = rows[0]["current_hash"]
                logger.info("AuditLog chain hash recovered from DB")
        except Exception as e:
            logger.warning("AuditLog failed to recover chain hash: %s", e)

    def log(
        self,
        session_id: str,
        operation_type: str,
        skill_id: str,
        input_text: str,
        output_data: Any,
        duration_ms: int,
        status: str = "success",
        error_msg: str = "",
        user_id: str = "default",
    ) -> str:
        import uuid

        input_text = input_text or ""
        input_hash = hashlib.sha256(input_text.encode()).hexdigest()
        timestamp = time.time()
        with self._lock:
            # 首次调用时从 DB 恢复链式哈希（进程重启后保证链连续）
            if not self._started and self._last_hash == GENESIS_HASH:
                self._recover_last_hash()
            # 链式哈希计算（持有锁，保证链顺序与 log() 调用顺序一致）
            prev_hash = self._last_hash
            current_hash = hashlib.sha256(
                f"{prev_hash}{timestamp}{operation_type}{input_hash}".encode()
            ).hexdigest()
            self._last_hash = current_hash

            record = AuditRecord(
                id=uuid.uuid4().hex[:12],
                session_id=session_id,
                user_id=user_id,
                timestamp=timestamp,
                operation_type=operation_type,
                skill_id=skill_id,
                input_hash=input_hash,
                input_summary=self._audit_sanitize(input_text),
                output_summary=(
                    self._audit_sanitize(str(output_data))[:500] if output_data else ""
                ),
                duration_ms=duration_ms,
                status=status,
                error_msg=error_msg[:500],
                prev_hash=prev_hash,
                current_hash=current_hash,
            )
            self._logs.append(record)
            self._write_queue.put(record)

        if not self._started:
            self._start_background_writer()

        # Throttle DB row cleanup and offload it to the background writer to
        # avoid synchronous DB lock contention on the caller thread.
        self._cleanup_counter += 1
        if self._cleanup_counter % 100 == 0:
            self._cleanup_needed = True

        return record.id

    def query(
        self,
        session_id: Optional[str] = None,
        operation_type: Optional[str] = None,
        limit: int = 50,
        since: Optional[float] = None,
    ) -> List[dict]:
        if not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        if limit > 1000:
            raise ValueError("limit must not exceed 1000")
        results = []
        with self._lock:
            for r in self._logs:
                if session_id and r.session_id != session_id:
                    continue
                if operation_type and r.operation_type != operation_type:
                    continue
                if since and r.timestamp < since:
                    continue
                results.append(
                    {
                        "id": r.id,
                        "timestamp": r.timestamp,
                        "operation_type": r.operation_type,
                        "skill_id": r.skill_id,
                        "status": r.status,
                        "duration_ms": r.duration_ms,
                        "input_summary": r.input_summary,
                        "output_summary": r.output_summary[
                            :AUDIT_MAX_QUERY_OUTPUT_LENGTH
                        ],
                    }
                )
        return results[:limit]

    def verify_chain(self, limit: int = 1000) -> Dict[str, Any]:
        """验证审计日志链式哈希完整性。

        从 DB 读取最近 limit 条记录，验证：
        1. 每条 current_hash = sha256(prev_hash + timestamp + operation_type + input_hash)
        2. 每条 prev_hash = 上一条 current_hash（首条 prev_hash = GENESIS_HASH 或空）

        Returns:
            {"valid": bool, "total": int, "verified": int, "broken_at": Optional[str]}
            broken_at 为断裂处的 record id（如有）
        """
        try:
            from opc_manager.data_manager import init_db, execute_query

            init_db()
            rows = execute_query(
                "SELECT id, timestamp, operation_type, input_hash, "
                "prev_hash, current_hash FROM audit_log "
                "WHERE current_hash != '' ORDER BY timestamp ASC LIMIT ?",
                (limit,),
            )
        except Exception as e:
            logger.warning("AuditLog verify_chain query failed: %s", e)
            return {
                "valid": False,
                "total": 0,
                "verified": 0,
                "broken_at": None,
                "error": str(e),
            }

        if not rows:
            return {"valid": True, "total": 0, "verified": 0, "broken_at": None}

        prev_expected = GENESIS_HASH
        verified = 0
        for row in rows:
            # prev_hash 连续性检查
            if row["prev_hash"] and row["prev_hash"] != prev_expected:
                return {
                    "valid": False,
                    "total": len(rows),
                    "verified": verified,
                    "broken_at": row["id"],
                    "error": f"prev_hash mismatch at {row['id']}",
                }
            # current_hash 重算验证
            recomputed = hashlib.sha256(
                f"{row['prev_hash']}{row['timestamp']}{row['operation_type']}{row['input_hash']}".encode()
            ).hexdigest()
            if recomputed != row["current_hash"]:
                return {
                    "valid": False,
                    "total": len(rows),
                    "verified": verified,
                    "broken_at": row["id"],
                    "error": f"current_hash mismatch at {row['id']}",
                }
            verified += 1
            prev_expected = row["current_hash"]

        return {
            "valid": True,
            "total": len(rows),
            "verified": verified,
            "broken_at": None,
        }

    def get_stats(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        total = success = failed = 0
        total_duration = 0
        with self._lock:
            for r in self._logs:
                if session_id and r.session_id != session_id:
                    continue
                total += 1
                total_duration += r.duration_ms
                if r.status == "success":
                    success += 1
                elif r.status in ("failed", "cancelled"):
                    failed += 1
        return {
            "total": total,
            "success": success,
            "failed": failed,
            "success_rate": f"{success / max(total, 1) * 100:.1f}%",
            "avg_duration_ms": total_duration // max(total, 1),
        }

    def cleanup(self, before_timestamp: Optional[float] = None) -> int:
        if before_timestamp is None:
            before_timestamp = time.time() - AUDIT_RETENTION_DAYS * SECONDS_PER_DAY
        with self._lock:
            self._logs = deque(
                [r for r in self._logs if r.timestamp >= before_timestamp],
                maxlen=AUDIT_MAX_MEMORY_LOGS,
            )
            return len(self._logs)

    def _start_background_writer(self) -> None:
        self._started = True

        def writer() -> None:
            from opc_manager.data_manager import init_db, execute_write

            try:
                init_db()
            except Exception as e:
                logger.warning("AuditLog DB init failed: %s", e)
                return

            batch = []
            while not self._stop_event.is_set():
                try:
                    item = self._write_queue.get(timeout=30)
                    if item is None:
                        # Sentinel value requested by stop(); drain remaining
                        # records and exit cleanly.
                        break
                    batch.append(item)
                    while len(batch) < AUDIT_WRITE_BATCH_SIZE:
                        try:
                            item = self._write_queue.get_nowait()
                            if item is None:
                                break
                            batch.append(item)
                        except Empty:
                            break

                    if not batch:
                        break

                    try:
                        values = [
                            (
                                r.id,
                                r.session_id,
                                r.user_id,
                                r.timestamp,
                                r.operation_type,
                                r.skill_id,
                                r.input_hash,
                                r.input_summary,
                                r.output_summary,
                                r.duration_ms,
                                r.status,
                                r.error_msg,
                                r.prev_hash,
                                r.current_hash,
                            )
                            for r in batch
                        ]
                        execute_write(
                            """
                            INSERT OR IGNORE INTO audit_log
                            (id, session_id, user_id, timestamp, operation_type,
                             skill_id, input_hash, input_summary, output_summary,
                             duration_ms, status, error_msg, prev_hash, current_hash)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                            values,
                            many=True,
                        )
                        # Offloaded cleanup runs in the writer thread so it does
                        # not contend with the caller's DB operations.
                        if self._cleanup_needed:
                            try:
                                self._cleanup_db_rows()
                                self._cleanup_needed = False
                            except Exception as e:
                                logger.warning("AuditLog cleanup failed: %s", e)
                    except (IOError, OSError) as e:
                        logger.warning("AuditLog I/O write failed: %s", e)
                        time.sleep(0.1)
                    except Exception as e:
                        logger.warning("AuditLog background write failed: %s", e)
                        time.sleep(0.1)
                    finally:
                        batch = []
                except (KeyboardInterrupt, SystemExit):
                    break
                except Exception as e:
                    logger.warning("[AuditLog] Writer loop error: %s", e)
                    break

            # Flush any remaining records before exiting.
            # Drain queue: sentinel may have arrived before all records were processed.
            while True:
                try:
                    remaining = self._write_queue.get_nowait()
                    if remaining is None:
                        continue
                    batch.append(remaining)
                except Empty:
                    break
            if batch:
                try:
                    values = [
                        (
                            r.id,
                            r.session_id,
                            r.user_id,
                            r.timestamp,
                            r.operation_type,
                            r.skill_id,
                            r.input_hash,
                            r.input_summary,
                            r.output_summary,
                            r.duration_ms,
                            r.status,
                            r.error_msg,
                            r.prev_hash,
                            r.current_hash,
                        )
                        for r in batch
                    ]
                    execute_write(
                        """
                        INSERT OR IGNORE INTO audit_log
                        (id, session_id, user_id, timestamp, operation_type,
                         skill_id, input_hash, input_summary, output_summary,
                         duration_ms, status, error_msg, prev_hash, current_hash)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                        values,
                        many=True,
                    )
                except Exception as e:
                    logger.warning("AuditLog final flush failed: %s", e)

        self._writer_thread = threading.Thread(target=writer, daemon=True)
        self._writer_thread.start()
        logger.debug("AuditLog background writer started")

    def _cleanup_db_rows(self) -> int:
        """Prune audit_log table when row count exceeds MAX_AUDIT_ENTRIES."""
        try:
            from opc_manager.data_manager import init_db, execute_query, execute_write

            init_db()
            count_row = execute_query("SELECT COUNT(*) as cnt FROM audit_log")
            count = count_row[0]["cnt"] if count_row else 0
            if count > MAX_AUDIT_ENTRIES:
                cutoff = count - MAX_AUDIT_ENTRIES
                execute_write(
                    "DELETE FROM audit_log WHERE rowid IN (SELECT rowid FROM audit_log ORDER BY rowid ASC LIMIT ?)",
                    (cutoff,),
                )
                logger.info(
                    "AuditLog pruned %d old rows (limit: %d)", cutoff, MAX_AUDIT_ENTRIES
                )
                return cutoff
        except Exception as e:
            logger.warning("AuditLog DB row cleanup failed: %s", e)
        return 0

    def stop(self, wait: bool = False) -> None:
        """Signal the background writer to stop and optionally wait for it.

        Sending a sentinel wakes the writer immediately so it can release its
        database connection and exit, preventing lock contention in tests.
        The join timeout is long enough to let any in-flight DB write complete
        or time out after the configured busy timeout.
        """
        self._stop_event.set()
        try:
            self._write_queue.put_nowait(None)
        except Exception:
            pass
        if wait and self._writer_thread is not None and self._writer_thread.is_alive():
            self._writer_thread.join(timeout=10)
        self._started = False
