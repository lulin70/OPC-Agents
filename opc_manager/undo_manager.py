import time
import threading
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class OperationType(Enum):
    EMAIL_SEND = "email_send"
    RECORD_INCOME = "record_income"
    RECORD_EXPENSE = "record_expense"
    ADD_EVENT = "add_event"
    ADD_DEAL = "add_deal"
    CREATE_PROPOSAL = "create_proposal"
    CREATE_INVOICE = "create_invoice"
    ADD_CUSTOMER = "add_customer"
    ADD_FOLLOW_UP = "add_follow_up"
    SOCIAL_PUBLISH = "social_publish"

UNDO_WINDOWS_SECONDS = {
    OperationType.EMAIL_SEND: 300,
    OperationType.RECORD_INCOME: 1800,
    OperationType.RECORD_EXPENSE: 1800,
    OperationType.ADD_EVENT: 3600,
    OperationType.ADD_DEAL: 3600,
    OperationType.CREATE_PROPOSAL: 3600,
    OperationType.CREATE_INVOICE: 3600,
    OperationType.ADD_CUSTOMER: 300,
    OperationType.ADD_FOLLOW_UP: 1800,
    OperationType.SOCIAL_PUBLISH: 60,
}

UNDOABLE_TYPES = set(OperationType)


@dataclass
class UndoRecord:
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
    MAX_PER_SESSION = 50
    CLEANUP_INTERVAL = 3600

    def __init__(self):
        self._records: Dict[str, List[UndoRecord]] = {}
        self._lock = threading.Lock()

    def push(self, session_id: str, op_type: OperationType,
             inverse_func: str, inverse_args: dict,
             original_result: dict) -> str:
        record = UndoRecord(
            operation_id=self._gen_id(),
            operation_type=op_type,
            session_id=session_id,
            inverse_func_name=inverse_func,
            inverse_args=inverse_args or {},
            original_result=original_result or {},
        )
        window = UNDO_WINDOWS_SECONDS.get(op_type, 3600)
        record.expires_at = time.time() + window

        with self._lock:
            if session_id not in self._records:
                self._records[session_id] = []
            records = self._records[session_id]
            records.append(record)
            if len(records) > self.MAX_PER_SESSION:
                self._records[session_id] = records[-self.MAX_PER_SESSION:]

        return record.operation_id

    def can_undo(self, session_id: str, operation_id: str) -> tuple:
        with self._lock:
            for r in self._records.get(session_id, []):
                if r.operation_id == operation_id and r.status == "active":
                    if time.time() < r.expires_at:
                        return True, ""
                    else:
                        r.status = "expired"
                        return False, "已过撤销窗口期"
            return False, "记录不存在或已撤销"

    def undo(self, session_id: str, operation_id: str) -> dict:
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
            return {"success": False, "error": "记录不存在"}

        try:
            func = self._resolve_inverse(record.inverse_func_name)
            result = func(**record.inverse_args)
            logger.info("Undo succeeded: %s (%s)", operation_id, record.inverse_func_name)
            return {"success": True, "operation_id": operation_id, "result": result}
        except Exception as e:
            logger.error("Undo failed: %s - %s", operation_id, e)
            return {"success": False, "error": str(e)}

    def list_undoable(self, session_id: str) -> List[dict]:
        now = time.time()
        results = []
        with self._lock:
            for r in self._records.get(session_id, []):
                if r.status == "active":
                    remaining = max(0, int(r.expires_at - now))
                    results.append({
                        "operation_id": r.operation_id,
                        "type": r.operation_type.value,
                        "created_at": r.created_at,
                        "remaining_seconds": remaining,
                        "original_summary": str(r.original_result)[:100],
                    })
        return sorted(results, key=lambda x: x["created_at"], reverse=True)

    def cleanup_expired(self):
        now = time.time()
        with self._lock:
            for sid in list(self._records.keys()):
                self._records[sid] = [r for r in self._records[sid]
                                       if r.status == "active" and r.expires_at > now]
                if not self._records[sid]:
                    del self._records[sid]

    @staticmethod
    def _gen_id() -> str:
        import uuid
        return uuid.uuid4().hex[:12]

    @staticmethod
    def _resolve_inverse(func_name: str):
        from opc_manager import finance_skill, crm_skill, email_skill, calendar_skill, proposal_skill, invoice_skill, social_skill, task_skill
        mapping = {
            "undo_record_income": finance_skill.undo_record_income,
            "undo_record_expense": finance_skill.undo_record_expense,
            "undo_add_customer": crm_skill.undo_add_customer,
            "undo_send_email": email_skill.undo_send_email,
            "undo_add_event": calendar_skill.undo_add_event,
            "undo_create_proposal": proposal_skill.undo_create_proposal,
            "undo_create_invoice": invoice_skill.undo_create_invoice,
            "undo_publish_content": social_skill.undo_publish_content,
            "undo_complete_task": task_skill.undo_complete_task,
            "undo_add_deal": crm_skill.undo_add_deal,
            "undo_add_follow_up": crm_skill.undo_add_follow_up,
        }
        return mapping.get(func_name)
