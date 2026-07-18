"""Undo management system for OPC-Agents.

Provides operation undo functionality with time-windowed reversibility.
Supports undo for various business operations like email sending,
financial records, CRM actions, etc.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import logging
import threading
import time

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """Types of operations that can be undone."""

    EMAIL_SEND = "email_send"
    RECORD_INCOME = "record_income"
    RECORD_EXPENSE = "record_expense"
    ADD_DEAL = "add_deal"
    CREATE_INVOICE = "create_invoice"
    ADD_CUSTOMER = "add_customer"
    ADD_FOLLOW_UP = "add_follow_up"
    SOCIAL_PUBLISH = "social_publish"


UNDO_WINDOWS_SECONDS = {
    OperationType.EMAIL_SEND: 300,
    OperationType.RECORD_INCOME: 1800,
    OperationType.RECORD_EXPENSE: 1800,
    OperationType.ADD_DEAL: 3600,
    OperationType.CREATE_INVOICE: 3600,
    OperationType.ADD_CUSTOMER: 300,
    OperationType.ADD_FOLLOW_UP: 1800,
    OperationType.SOCIAL_PUBLISH: 60,
}

UNDOABLE_TYPES = set(OperationType)

UNDO_MAX_PER_SESSION = 50
UNDO_CLEANUP_INTERVAL = 3600
DEFAULT_UNDO_WINDOW = 3600
ORIGINAL_SUMMARY_TRUNCATE = 100
MAX_SESSION_ID_LENGTH = 256
MAX_UNDO_HISTORY = 100
MAX_UNDO_STACK = 50

ALLOWED_FUNC_NAMES = {
    "undo_record_income",
    "undo_record_expense",
    "undo_add_customer",
    "undo_send_email",
    "undo_create_invoice",
    "undo_publish_content",
    "undo_complete_task",
    "undo_add_deal",
    "undo_add_follow_up",
}


@dataclass
class UndoRecord:
    """Represents a single undo record.

    Attributes:
        operation_id: Unique identifier for this operation.
        operation_type: Type of the operation.
        session_id: Session this operation belongs to.
        inverse_func_name: Name of the inverse function to call.
        inverse_args: Arguments to pass to the inverse function.
        original_result: Result of the original operation.
        created_at: Timestamp when record was created.
        expires_at: Timestamp when undo window expires.
        status: Current status ('active', 'undone', 'expired').
    """

    operation_id: str
    operation_type: OperationType
    session_id: str
    inverse_func_name: str
    inverse_args: dict
    original_result: dict
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0
    status: str = "active"


class UndoManager:
    """Manages undo records for reversible operations.

    Thread-safe implementation with per-session record limits and
    automatic expiration based on operation type time windows.

    Attributes:
        _records: Dictionary mapping session_id to list of UndoRecord.
        _lock: Threading lock for thread safety.
        MAX_PER_SESSION: Maximum undo records per session (from UNDO_MAX_PER_SESSION).
        CLEANUP_INTERVAL: Seconds between cleanup cycles (from UNDO_CLEANUP_INTERVAL).
    """

    def __init__(self) -> None:
        """Initialize UndoManager with empty records and lock."""
        self.MAX_PER_SESSION = UNDO_MAX_PER_SESSION
        self.CLEANUP_INTERVAL = UNDO_CLEANUP_INTERVAL
        self._records: Dict[str, List[UndoRecord]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _validate_session_id(session_id: str) -> None:
        """Validate session_id format and length."""
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")
        if len(session_id) > MAX_SESSION_ID_LENGTH:
            raise ValueError(
                f"session_id exceeds maximum length of {MAX_SESSION_ID_LENGTH}"
            )

    def push(
        self,
        session_id: str,
        op_type: OperationType,
        inverse_func: str,
        inverse_args: dict,
        original_result: dict,
    ) -> str:
        """Push a new undo record.

        Args:
            session_id: Session identifier.
            op_type: Type of operation being recorded.
            inverse_func: Name of the inverse function.
            inverse_args: Arguments for the inverse function.
            original_result: Result of the original operation.

        Returns:
            The operation_id of the created record.

        Raises:
            ValueError: If session_id or inverse_func is invalid.
        """
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")
        if not isinstance(inverse_func, str) or not inverse_func:
            raise ValueError("inverse_func must be a non-empty string")
        self._validate_session_id(session_id)
        record = UndoRecord(
            operation_id=self._gen_id(),
            operation_type=op_type,
            session_id=session_id,
            inverse_func_name=inverse_func,
            inverse_args=inverse_args or {},
            original_result=original_result or {},
        )
        window = UNDO_WINDOWS_SECONDS.get(op_type, DEFAULT_UNDO_WINDOW)
        record.expires_at = time.time() + window

        with self._lock:
            if session_id not in self._records:
                self._records[session_id] = []
            records = self._records[session_id]
            records.append(record)
            if len(records) > self.MAX_PER_SESSION:
                self._records[session_id] = records[-self.MAX_PER_SESSION :]
            # Trim total undo stack across all sessions
            total = sum(len(v) for v in self._records.values())
            limit = MAX_UNDO_HISTORY
            if total > limit:
                sids = sorted(
                    self._records.keys(),
                    key=lambda s: min(r.created_at for r in self._records[s]),
                )
                while total > limit and sids:
                    oldest_sid = sids[0]
                    self._records[oldest_sid].pop(0)
                    total -= 1
                    if not self._records[oldest_sid]:
                        del self._records[oldest_sid]
                        sids.pop(0)

        return record.operation_id

    def can_undo(self, session_id: str, operation_id: str) -> Tuple[bool, str]:
        """Check if an operation can be undone.

        Args:
            session_id: Session identifier.
            operation_id: Operation to check.

        Returns:
            Tuple of (can_undo: bool, reason: str).
        """
        self._validate_session_id(session_id)
        with self._lock:
            for r in self._records.get(session_id, []):
                if r.operation_id == operation_id:
                    if r.status != "active":
                        return False, f"Record is {r.status}"
                    if time.time() >= r.expires_at:
                        r.status = "expired"
                        return False, "Undo window expired"
                    return True, ""
            return False, "Record not found"

    def undo(self, session_id: str, operation_id: str) -> Dict[str, Any]:
        """Execute undo for an operation.

        Args:
            session_id: Session identifier.
            operation_id: Operation to undo.

        Returns:
            Dict with 'success' bool and optional 'error'/'result'.
        """
        self._validate_session_id(session_id)
        can, reason = self.can_undo(session_id, operation_id)
        if not can:
            return {"success": False, "error": reason}

        record = None
        with self._lock:
            for r in self._records.get(session_id, []):
                if r.operation_id == operation_id:
                    r.status = "undone"
                    record = r
                    break

        if record is None:
            return {"success": False, "error": "Record not found"}

        try:
            func = self._resolve_inverse(record.inverse_func_name)
            if func is None:
                return {
                    "success": False,
                    "error": f"Unknown inverse function: {record.inverse_func_name}",
                }
            result = func(**record.inverse_args)
            logger.info(
                "Undo succeeded: %s (%s)", operation_id, record.inverse_func_name
            )
            return {"success": True, "operation_id": operation_id, "result": result}
        except (KeyError, TypeError) as e:
            logger.error("Undo parameter error: %s - %s", operation_id, e)
            return {"success": False, "error": f"Invalid parameters: {e}"}
        except (IOError, OSError) as e:
            logger.error("Undo I/O error: %s - %s", operation_id, e)
            return {"success": False, "error": f"I/O error: {e}"}
        except Exception as e:
            logger.error(
                "Undo failed for operation %s (%s): %s",
                operation_id,
                record.inverse_func_name,
                e,
            )
            return {"success": False, "error": f"Undo failed for {operation_id}: {e}"}

    def list_undoable(self, session_id: str) -> List[dict]:
        """List all undoable operations for a session.

        Args:
            session_id: Session identifier.

        Returns:
            List of dicts with operation details, sorted by creation time desc.
        """
        self._validate_session_id(session_id)
        now = time.time()
        results = []
        with self._lock:
            for r in self._records.get(session_id, []):
                if r.status == "active":
                    remaining = max(0, int(r.expires_at - now))
                    results.append(
                        {
                            "operation_id": r.operation_id,
                            "type": r.operation_type.value,
                            "created_at": r.created_at,
                            "remaining_seconds": remaining,
                            "original_summary": str(r.original_result)[
                                :ORIGINAL_SUMMARY_TRUNCATE
                            ],
                        }
                    )
        return sorted(results, key=lambda x: x["created_at"], reverse=True)

    def get_session_records(self, session_id: str) -> List[UndoRecord]:
        """Get all undo records for a session.

        Args:
            session_id: Session identifier.

        Returns:
            List of UndoRecord objects for the session.
        """
        self._validate_session_id(session_id)
        with self._lock:
            return list(self._records.get(session_id, []))

    def cleanup_expired(self) -> None:
        """Remove all expired undo records."""
        now = time.time()
        with self._lock:
            for sid in list(self._records.keys()):
                self._records[sid] = [
                    r
                    for r in self._records[sid]
                    if r.status == "active" and r.expires_at > now
                ]
                if not self._records[sid]:
                    del self._records[sid]

    @staticmethod
    def _gen_id() -> str:
        """Generate a unique operation ID."""
        import uuid

        return uuid.uuid4().hex[:12]

    @staticmethod
    def _resolve_inverse(func_name: str) -> Optional[Callable]:
        """Resolve inverse function name to callable.

        Args:
            func_name: Name of the inverse function.

        Returns:
            Callable or None if not found.

        Raises:
            ValueError: If function name is not in ALLOWED_FUNC_NAMES.
        """
        if func_name not in ALLOWED_FUNC_NAMES:
            raise ValueError(f"Unauthorized inverse function: {func_name}")

        from opc_manager import (
            finance_skill,
            crm_skill,
            email_skill,
            invoice_skill,
            social_skill,
            task_skill,
        )

        mapping: Dict[str, Callable[..., Any]] = {
            "undo_record_income": finance_skill.undo_record_income,
            "undo_record_expense": finance_skill.undo_record_expense,
            "undo_add_customer": crm_skill.undo_add_customer,
            "undo_send_email": email_skill.undo_send_email,
            "undo_create_invoice": invoice_skill.undo_create_invoice,
            "undo_publish_content": social_skill.undo_publish_content,
            "undo_complete_task": task_skill.undo_complete_task,
            "undo_add_deal": crm_skill.undo_add_deal,
            "undo_add_follow_up": crm_skill.undo_add_follow_up,
        }
        func = mapping.get(func_name)
        if func is None:
            raise ValueError(f"Inverse function not found: {func_name}")
        return func
