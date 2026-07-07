"""Timeline data models and builders for OPC-Agents frontend.

Provides the core data layer for the timeline view, extracted from timeline_view.py:
- TimelineEvent: Data model for a single timeline event
- EVENT_TYPE_CONFIG: Event type configuration (icons, colors, categories)
- MAX_TIMELINE_EVENTS: Maximum number of events to keep
- TIMELINE_BUILD_TIMEOUT_MS: Build timeout threshold
- build_timeline_from_session: Build complete timeline from session state
- _build_from_deliverables: Build events from deliverables records
- _build_from_undo_manager: Build events from UndoManager records
- _build_from_audit_log: Build events from AuditLog entries
- _build_from_progress_emitter: Build events from ProgressEmitter history
- _build_from_chat_history: Build events from chat history (heuristic)
- _get_undo_description: Generate undo operation description text
- _map_audit_operation_to_event: Map AuditLog operation types to event types
- _get_category_labels / _get_status_labels: Label lookup functions
- CATEGORY_LABELS / STATUS_LABELS: Cached label dictionaries
"""

import streamlit as st
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Tuple, Optional

from opc_manager.i18n import t as _t

logger = logging.getLogger(__name__)

__all__ = [
    "TimelineEvent",
    "EVENT_TYPE_CONFIG",
    "MAX_TIMELINE_EVENTS",
    "TIMELINE_BUILD_TIMEOUT_MS",
    "build_timeline_from_session",
    "_build_from_deliverables",
    "_build_from_undo_manager",
    "_build_from_audit_log",
    "_build_from_progress_emitter",
    "_build_from_chat_history",
    "_get_undo_description",
    "_map_audit_operation_to_event",
    "_get_category_labels",
    "_get_status_labels",
    "CATEGORY_LABELS",
    "STATUS_LABELS",
]

MAX_TIMELINE_EVENTS = 500
TIMELINE_BUILD_TIMEOUT_MS = 200


@dataclass
class TimelineEvent:
    """时间线事件数据模型

    Attributes:
        id: 事件唯一标识符
        timestamp: Unix时间戳
        event_type: 事件类型（task_complete/income_recorded/email_sent等）
        title: 简短标题（<50字符）
        description: 详细描述
        icon: emoji图标
        category: 分类（work/finance/communication/system）
        metadata: 附加元数据
        duration_ms: 操作耗时（毫秒）
        status: 状态（success/error/pending/cancelled）
        related_ids: 相关事件ID列表（用于连线）
    """

    id: str
    timestamp: float
    event_type: str
    title: str
    description: str
    icon: str
    category: str
    metadata: dict = field(default_factory=dict)
    duration_ms: float = 0
    status: str = "success"
    related_ids: list = field(default_factory=list)

    def __post_init__(self):
        if len(self.title) > 50:
            self.title = self.title[:47] + "..."


EVENT_TYPE_CONFIG = {
    "task_complete": {
        "icon": "",
        "color": "#10B981",
        "category": "work",
        "i18n_key": "timeline_task_complete",
    },
    "income_recorded": {
        "icon": "",
        "color": "#F59E0B",
        "category": "finance",
        "i18n_key": "timeline_income_recorded",
    },
    "expense_recorded": {
        "icon": "",
        "color": "#EF4444",
        "category": "finance",
        "i18n_key": "timeline_expense_recorded",
    },
    "email_sent": {
        "icon": "",
        "color": "#3B82F6",
        "category": "communication",
        "i18n_key": "timeline_email_sent",
    },
    "error_occurred": {
        "icon": "",
        "color": "#EF4444",
        "category": "system",
        "i18n_key": "timeline_error",
    },
    "undo_action": {
        "icon": "",
        "color": "#6B7280",
        "category": "system",
        "i18n_key": "timeline_undo_action",
    },
    "confirmation_required": {
        "icon": "",
        "color": "#F59E0B",
        "category": "system",
        "i18n_key": "timeline_confirmation_required",
    },
    "skill_executed": {
        "icon": "",
        "color": "#06B6D4",
        "category": "work",
        "i18n_key": "timeline_skill_executed",
    },
    "dashboard_viewed": {
        "icon": "",
        "color": "#3B82F6",
        "category": "work",
        "i18n_key": "timeline_dashboard_viewed",
    },
}


def _get_category_labels():
    return {
        "work": _t("timeline_cat_work"),
        "finance": _t("timeline_cat_finance"),
        "communication": _t("timeline_cat_communication"),
        "system": _t("timeline_cat_system"),
    }


def _get_status_labels():
    return {
        "success": _t("timeline_status_success"),
        "error": _t("timeline_status_error"),
        "pending": _t("timeline_status_pending"),
        "cancelled": _t("timeline_status_cancelled"),
        "undone": _t("timeline_status_undone"),
    }


CATEGORY_LABELS = _get_category_labels()
STATUS_LABELS = _get_status_labels()


def build_timeline_from_session(session_id: str = "") -> List[TimelineEvent]:
    """从当前session状态构建完整时间线

    集成多个数据源：
    1. deliverables_records → task_complete事件
    2. UndoManager records → undo_action/task_complete事件
    3. AuditLog entries → email_sent, income_recorded等
    4. ProgressEmitter history → confirmation_required, error_occurred
    5. Chat history → dashboard_viewed, skill_executed（启发式推断）

    Args:
        session_id: 会话标识符

    Returns:
        按时间戳降序排列的事件列表（最新在前）
    """
    start_time = time.time()
    events = []

    try:
        events.extend(_build_from_deliverables())
    except Exception as e:
        logger.warning("[timeline] build deliverables events failed: %s", e)

    try:
        events.extend(_build_from_undo_manager(session_id))
    except Exception as e:
        logger.warning("[timeline] build undo_manager events failed: %s", e)

    try:
        events.extend(_build_from_audit_log())
    except Exception as e:
        logger.warning("[timeline] build audit_log events failed: %s", e)

    try:
        events.extend(_build_from_progress_emitter(session_id))
    except Exception as e:
        logger.warning("[timeline] build progress_emitter events failed: %s", e)

    try:
        events.extend(_build_from_chat_history())
    except Exception as e:
        logger.warning("[timeline] build chat_history events failed: %s", e)

    events.sort(key=lambda x: x.timestamp, reverse=True)

    if len(events) > MAX_TIMELINE_EVENTS:
        events = events[:MAX_TIMELINE_EVENTS]

    elapsed_ms = (time.time() - start_time) * 1000
    if elapsed_ms > TIMELINE_BUILD_TIMEOUT_MS:
        logger.warning(
            "[timeline] build took %.1fms (exceeds %dms limit)",
            elapsed_ms,
            TIMELINE_BUILD_TIMEOUT_MS,
        )

    return events


def _build_from_deliverables() -> List[TimelineEvent]:
    """从deliverables记录构建task_complete事件"""
    events = []
    deliverables = st.session_state.get("deliverables", [])

    for record in deliverables:
        if not isinstance(record, dict):
            continue

        created_at = record.get("created_at", 0)
        if isinstance(created_at, str):
            try:
                created_at = datetime.strptime(
                    created_at, "%Y-%m-%d %H:%M:%S"
                ).timestamp()
            except ValueError:
                created_at = 0

        events.append(
            TimelineEvent(
                id=record.get("id", f"del_{hash(str(record))}"),
                timestamp=created_at,
                event_type="task_complete",
                title=record.get("prompt", _t("timeline_task_complete"))[:50],
                description=f"{_t('timeline_generated')} {record.get('task_type', _t('timeline_document'))}",
                icon="",
                category="work",
                metadata={
                    "filepath": record.get("filepath", ""),
                    "filename": record.get("filename", ""),
                    "task_type": record.get("task_type", ""),
                    "size_kb": record.get("size_kb", 0),
                },
                status="success",
            )
        )

    return events


def _build_from_undo_manager(session_id: str) -> List[TimelineEvent]:
    """从UndoManager记录构建undo_action/task_complete事件"""
    events = []

    try:
        from opc_manager.undo_manager import get_undo_manager

        undo_mgr = get_undo_manager()

        if not undo_mgr or not session_id:
            return events

        records = undo_mgr.list_records(session_id)

        for record in records:
            if not hasattr(record, "operation_id"):
                continue

            is_undone = getattr(record, "status", "") == "undone"
            operation_type = getattr(record, "operation_type", None)
            op_type_str = operation_type.value if operation_type else "unknown"

            events.append(
                TimelineEvent(
                    id=getattr(record, "operation_id", ""),
                    timestamp=getattr(record, "created_at", 0),
                    event_type="undo_action" if is_undone else "task_complete",
                    title=_get_undo_description(record),
                    description=f"{op_type_str} {_t('timeline_operation')}",
                    icon="" if is_undone else "",
                    category="system",
                    metadata={
                        "operation_type": op_type_str,
                        "inverse_func": getattr(record, "inverse_func_name", ""),
                    },
                    status="undone" if is_undone else "success",
                )
            )
    except ImportError:
        pass
    except Exception as e:
        logger.debug("[timeline] UndoManager integration exception: %s", e)

    return events


def _get_undo_description(record) -> str:
    """生成撤销操作的描述文本"""
    op_type = getattr(record, "operation_type", None)
    op_str = op_type.value if op_type else _t("timeline_operation")

    type_label_keys = {
        "email_send": "timeline_op_email_send",
        "record_income": "timeline_op_record_income",
        "record_expense": "timeline_op_record_expense",
        "add_deal": "timeline_op_add_deal",
        "create_invoice": "timeline_op_create_invoice",
        "add_customer": "timeline_op_add_customer",
        "add_follow_up": "timeline_op_add_follow_up",
        "social_publish": "timeline_op_social_publish",
    }

    i18n_key = type_label_keys.get(op_str)
    label = _t(i18n_key) if i18n_key else op_str
    status = getattr(record, "status", "")

    if status == "undone":
        return _t("timeline_undone_prefix", label=label)
    return _t("timeline_executed_prefix", label=label)


def _build_from_audit_log() -> List[TimelineEvent]:
    """从AuditLog条目构建各类业务事件"""
    events = []
    status_labels = _get_status_labels()

    try:
        from opc_manager.audit_log import AuditLog

        audit = AuditLog()

        entries = (
            audit.get_recent_entries(limit=30)
            if hasattr(audit, "get_recent_entries")
            else []
        )

        for entry in entries:
            if not isinstance(entry, dict) and not hasattr(entry, "operation_type"):
                continue

            op_type = (
                getattr(entry, "operation_type", "")
                if hasattr(entry, "operation_type")
                else entry.get("operation_type", "")
            )
            event_info = _map_audit_operation_to_event(op_type)

            if not event_info:
                continue

            event_type, icon, category = event_info

            timestamp = (
                getattr(entry, "timestamp", 0)
                if hasattr(entry, "timestamp")
                else entry.get("timestamp", 0)
            )
            input_summary = (
                getattr(entry, "input_summary", "")
                if hasattr(entry, "input_summary")
                else entry.get("input_summary", "")
            )
            output_summary = (
                getattr(entry, "output_summary", "")
                if hasattr(entry, "output_summary")
                else entry.get("output_summary", "")
            )
            duration = (
                getattr(entry, "duration_ms", 0)
                if hasattr(entry, "duration_ms")
                else entry.get("duration_ms", 0)
            )
            status = (
                getattr(entry, "status", "success")
                if hasattr(entry, "status")
                else entry.get("status", "success")
            )

            events.append(
                TimelineEvent(
                    id=(
                        getattr(entry, "id", f"audit_{hash(str(entry))}")
                        if hasattr(entry, "id")
                        else entry.get("id", f"audit_{hash(str(entry))}")
                    ),
                    timestamp=timestamp,
                    event_type=event_type,
                    title=input_summary[:50] if input_summary else event_type,
                    description=output_summary[:100] if output_summary else op_type,
                    icon=icon,
                    category=category,
                    metadata={
                        "operation_type": op_type,
                        "skill_id": (
                            getattr(entry, "skill_id", "")
                            if hasattr(entry, "skill_id")
                            else entry.get("skill_id", "")
                        ),
                    },
                    duration_ms=float(duration),
                    status=status if status in status_labels else "success",
                )
            )
    except ImportError:
        pass
    except Exception as e:
        logger.debug("[timeline] AuditLog integration exception: %s", e)

    return events


def _map_audit_operation_to_event(
    operation_type: str,
) -> Optional[Tuple[str, str, str]]:
    """将AuditLog的operation_type映射到时间线事件类型"""
    mapping = {
        "email_send": ("email_sent", "", "communication"),
        "send_email": ("email_sent", "", "communication"),
        "record_income": ("income_recorded", "", "finance"),
        "income_record": ("income_recorded", "", "finance"),
        "record_expense": ("expense_recorded", "", "finance"),
        "expense_record": ("expense_recorded", "", "finance"),
        "execute_skill": ("skill_executed", "", "work"),
        "skill_run": ("skill_executed", "", "work"),
    }
    return mapping.get(operation_type.lower())


def _build_from_progress_emitter(session_id: str) -> List[TimelineEvent]:
    """从ProgressEmitter历史构建confirm_required和error_occurred事件"""
    events = []

    try:
        from opc_manager.progress_emitter import get_progress_emitter

        emitter = get_progress_emitter()

        if not emitter or not session_id:
            return events

        history = emitter.get_history(session_id)

        for evt in history:
            if not isinstance(evt, dict):
                continue

            event_val = evt.get("event", evt.get("event_type", ""))

            if event_val in ("confirm_requested", "CONFIRM_REQUESTED"):
                events.append(
                    TimelineEvent(
                        id=f"prog_confirm_{evt.get('timestamp', 0)}",
                        timestamp=evt.get("timestamp", 0),
                        event_type="confirmation_required",
                        title=evt.get("message", _t("timeline_waiting_confirm"))[:50],
                        description=_t("timeline_need_user_confirm"),
                        icon="",
                        category="system",
                        metadata={"progress": evt.get("progress", 0)},
                        status="pending",
                    )
                )

            elif event_val in ("error", "ERROR"):
                events.append(
                    TimelineEvent(
                        id=f"prog_error_{evt.get('timestamp', 0)}",
                        timestamp=evt.get("timestamp", 0),
                        event_type="error_occurred",
                        title=evt.get("message", _t("timeline_error_occurred"))[:50],
                        description=(
                            evt.get("detail", {}).get("error_msg", "")[:100]
                            if evt.get("detail")
                            else ""
                        ),
                        icon="",
                        category="system",
                        metadata={"detail": evt.get("detail", {})},
                        status="error",
                    )
                )
    except ImportError:
        pass
    except Exception as e:
        logger.debug("[timeline] ProgressEmitter integration exception: %s", e)

    return events


def _build_from_chat_history() -> List[TimelineEvent]:
    """从聊天历史启发式推断dashboard_viewed和skill_executed事件"""
    events = []
    messages = st.session_state.get("messages", [])

    dashboard_keywords = ["仪表盘", "dashboard", "统计", "报表", "数据概览"]
    skill_keywords = ["执行技能", "运行技能", "skill", "调用"]

    for msg in messages[-20:]:
        if not isinstance(msg, dict):
            continue

        content = msg.get("content", "")
        timestamp = msg.get("timestamp", time.time())

        if isinstance(timestamp, str):
            try:
                timestamp = datetime.strptime(
                    timestamp, "%Y-%m-%d %H:%M:%S"
                ).timestamp()
            except (ValueError, TypeError):
                timestamp = time.time()

        role = msg.get("role", "")

        if any(kw in content.lower() for kw in dashboard_keywords):
            events.append(
                TimelineEvent(
                    id=f"chat_dash_{timestamp}",
                    timestamp=timestamp,
                    event_type="dashboard_viewed",
                    title=_t("timeline_dashboard_viewed"),
                    description=_t("timeline_viewed_dashboard_desc"),
                    icon="",
                    category="work",
                    status="success",
                )
            )

        elif role == "assistant" and any(
            kw in content.lower() for kw in skill_keywords
        ):
            events.append(
                TimelineEvent(
                    id=f"chat_skill_{timestamp}",
                    timestamp=timestamp,
                    event_type="skill_executed",
                    title=_t("timeline_skill_executed"),
                    description=content[:80],
                    icon="",
                    category="work",
                    status="success",
                )
            )

    return events
