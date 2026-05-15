import threading
import time
import json
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List
from collections import deque
from queue import Queue, Empty

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

AUDIT_MAX_MEMORY_LOGS = 1000
AUDIT_WRITE_BATCH_SIZE = 10
AUDIT_RETENTION_DAYS = 90

AUDIT_SENSITIVE_PATTERNS = [
    'password', 'passwd', 'pwd', 'secret', 'api_key', 'apikey',
    'token', 'auth', 'credential', 'private_key', 'access_key',
    'credit_card', 'card_number', 'ssn', 'social_security',
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

    def __new__(cls):
        """Create or return singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._logs = deque(maxlen=AUDIT_MAX_MEMORY_LOGS)
                    cls._instance._write_queue = Queue()
                    cls._instance._started = False
        return cls._instance

    @staticmethod
    def _audit_sanitize(text: str, max_length: int = 200) -> str:
        text_lower = text.lower()
        for pattern in AUDIT_SENSITIVE_PATTERNS:
            if pattern in text_lower:
                return "***REDACTED***"
        return text[:max_length]

    def __init__(self):
        pass

    def _init_db_connection(self):
        try:
            from opc_manager.data_manager import init_db
            init_db()
            logger.info("AuditLog database connection initialized")
        except Exception as e:
            logger.warning("AuditLog failed to initialize database connection: %s", e)

    def log(self, session_id: str, operation_type: str, skill_id: str,
            input_text: str, output_data: Any, duration_ms: int,
            status: str = "success", error_msg: str = "",
            user_id: str = "default"):
        import uuid
        input_text = input_text or ""
        record = AuditRecord(
            id=uuid.uuid4().hex[:12],
            session_id=session_id,
            user_id=user_id,
            timestamp=time.time(),
            operation_type=operation_type,
            skill_id=skill_id,
            input_hash=hashlib.sha256(input_text.encode()).hexdigest(),
            input_summary=self._audit_sanitize(input_text),
            output_summary=str(output_data)[:500] if output_data else "",
            duration_ms=duration_ms,
            status=status,
            error_msg=error_msg[:500],
        )
        with self._lock:
            self._logs.append(record)
            self._write_queue.put(record)

        if not self._started:
            self._start_background_writer()

        return record.id

    def query(self, session_id: str = None, operation_type: str = None,
              limit: int = 50, since: float = None) -> List[dict]:
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
                results.append({
                    "id": r.id,
                    "timestamp": r.timestamp,
                    "operation_type": r.operation_type,
                    "skill_id": r.skill_id,
                    "status": r.status,
                    "duration_ms": r.duration_ms,
                    "input_summary": r.input_summary,
                    "output_summary": r.output_summary[:MAX_QUERY_OUTPUT_LENGTH],
                })
        return results[:limit]

    def get_stats(self, session_id: str = None) -> dict:
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

    def cleanup(self, before_timestamp: float = None):
        if before_timestamp is None:
            before_timestamp = time.time() - AUDIT_RETENTION_DAYS * 86400
        with self._lock:
            self._logs = deque([r for r in self._logs if r.timestamp >= before_timestamp], maxlen=AUDIT_MAX_MEMORY_LOGS)

    def _start_background_writer(self):
        self._started = True

        def writer():
            from opc_manager.data_manager import init_db, execute_write
            if self._db_connection is None:
                try:
                    init_db()
                except Exception as e:
                    logger.warning("AuditLog DB init failed: %s", e)

            batch = []
            while not self._stop_event.is_set():
                try:
                    item = self._write_queue.get(timeout=30)
                    batch.append(item)
                    while len(batch) < AUDIT_WRITE_BATCH_SIZE:
                        try:
                            item = self._write_queue.get_nowait()
                            batch.append(item)
                        except Empty:
                            break

                    try:
                        init_db()
                        values = [(r.id, r.session_id, r.user_id, r.timestamp,
                                 r.operation_type, r.skill_id, r.input_hash,
                                 r.input_summary, r.output_summary, r.duration_ms,
                                 r.status, r.error_msg) for r in batch]
                        execute_write("""
                            INSERT OR IGNORE INTO audit_log
                            (id, session_id, user_id, timestamp, operation_type,
                             skill_id, input_hash, input_summary, output_summary,
                             duration_ms, status, error_msg)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                        """, values, many=True)
                    except (IOError, OSError) as e:
                        logger.warning("AuditLog I/O write failed: %s", e)
                    except Exception as e:
                        logger.warning("AuditLog background write failed: %s", e)
                    finally:
                        batch = []
                except (KeyboardInterrupt, SystemExit):
                    break
                except Exception:
                    break

        t = threading.Thread(target=writer, daemon=True)
        t.start()
        logger.debug("AuditLog background writer started")

    def stop(self):
        self._stop_event.set()
