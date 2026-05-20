"""Undo display data models and helpers for OPC-Agents frontend.

Provides display-layer data structures and formatting extracted from undo_panel.py:
- UndoRecordDisplay: Data model for display-ready undo record
- OPERATION_TYPE_CONFIG: Operation type icons/labels/colors
- STATUS_CONFIG: Status icons/labels/colors
- _get_operation_description: Generate human-readable description
- _calculate_remaining_time: Countdown timer with urgency levels
- _format_time_ago: Relative time formatting
- _convert_to_display_record: Convert raw dict to UndoRecordDisplay
"""

import time
import logging
from datetime import datetime
from typing import Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = [
    "UndoRecordDisplay",
    "OPERATION_TYPE_CONFIG",
    "STATUS_CONFIG",
    "_get_operation_description",
    "_calculate_remaining_time",
    "_format_time_ago",
    "_convert_to_display_record",
]


@dataclass
class UndoRecordDisplay:
    """Display-ready representation of an undo record."""

    operation_id: str
    operation_type: str
    session_id: str
    inverse_func_name: str
    inverse_args: dict
    original_result: dict
    created_at: float
    expires_at: float
    status: str
    description: str = ""
    remaining_seconds: int = 0
    time_ago: str = ""


OPERATION_TYPE_CONFIG = {
    "EMAIL_SEND": {
        "icon": "📧",
        "label": "发送邮件",
        "color": "#3B82F6",
        "bg_color": "#EFF6FF",
    },
    "RECORD_INCOME": {
        "icon": "💰",
        "label": "记录收入",
        "color": "#10B981",
        "bg_color": "#ECFDF5",
    },
    "RECORD_EXPENSE": {
        "icon": "💸",
        "label": "记录支出",
        "color": "#F59E0B",
        "bg_color": "#FFFBEB",
    },
    "ADD_EVENT": {
        "icon": "📅",
        "label": "添加日程",
        "color": "#8B5CF6",
        "bg_color": "#F5F3FF",
    },
    "ADD_DEAL": {
        "icon": "🤝",
        "label": "添加商机",
        "color": "#06B6D4",
        "bg_color": "#ECFEFF",
    },
    "CREATE_PROPOSAL": {
        "icon": "📋",
        "label": "创建方案",
        "color": "#6366F1",
        "bg_color": "#EEF2FF",
    },
    "CREATE_INVOICE": {
        "icon": "🧾",
        "label": "创建发票",
        "color": "#14B8A6",
        "bg_color": "#F0FDFA",
    },
    "ADD_CUSTOMER": {
        "icon": "👥",
        "label": "添加客户",
        "color": "#F97316",
        "bg_color": "#FFF7ED",
    },
    "ADD_FOLLOW_UP": {
        "icon": "📞",
        "label": "添加跟进",
        "color": "#EC4899",
        "bg_color": "#FDF2F8",
    },
    "SOCIAL_PUBLISH": {
        "icon": "📱",
        "label": "发布内容",
        "color": "#EF4444",
        "bg_color": "#FEF2F2",
    },
}

STATUS_CONFIG = {
    "active": {
        "icon": "✅",
        "label": "可撤销",
        "color": "#10B981",
        "text_color": "green",
    },
    "undone": {
        "icon": "⚪",
        "label": "已撤销",
        "color": "#9CA3AF",
        "text_color": "gray",
    },
    "expired": {
        "icon": "❌",
        "label": "已过期",
        "color": "#EF4444",
        "text_color": "red",
    },
}


def _get_operation_description(record: UndoRecordDisplay) -> str:
    """Generate human-readable description from inverse_args and original_result.

    Args:
        record: UndoRecordDisplay object with operation details

    Returns:
        Human-readable Chinese description string
    """
    op_type = record.operation_type
    args = record.inverse_args or {}
    result = record.original_result or {}

    if op_type in ("EMAIL_SEND",):
        subject = args.get("subject", "") or result.get("subject", "")
        to_email = args.get("to", "") or result.get("to", "")
        if subject and to_email:
            return f"发送邮件: 「{subject[:30]}」→ {to_email}"
        elif subject:
            return f"发送邮件: 「{subject[:30]}」"
        return "发送邮件"

    elif op_type in ("RECORD_INCOME",):
        amount = args.get("amount", 0) or result.get("amount", 0)
        project = args.get("project", "") or result.get("project", "")
        desc = args.get("description", "") or result.get("description", "")
        if amount and project:
            return f"记录收入: ¥{amount} ({project})"
        elif amount:
            return f"记录收入: ¥{amount}"
        return "记录收入"

    elif op_type in ("RECORD_EXPENSE",):
        amount = args.get("amount", 0) or result.get("amount", 0)
        category = args.get("category", "") or result.get("category", "")
        if amount and category:
            return f"记录支出: ¥{amount} ({category})"
        elif amount:
            return f"记录支出: ¥{amount}"
        return "记录支出"

    elif op_type in ("ADD_EVENT",):
        title = args.get("title", "") or result.get("title", "")
        if title:
            return f"新建日程: 「{title[:30]}」"
        return "新建日程"

    elif op_type in ("ADD_DEAL",):
        deal_name = args.get("deal_name", "") or result.get("deal_name", "")
        value = args.get("value", 0) or result.get("value", 0)
        if deal_name and value:
            return f"新建商机: {deal_name} (¥{value})"
        elif deal_name:
            return f"新建商机: {deal_name}"
        return "新建商机"

    elif op_type in ("CREATE_PROPOSAL",):
        title = args.get("title", "") or result.get("title", "")
        client = args.get("client", "") or result.get("client", "")
        if title and client:
            return f"创建方案: 「{title[:25]}」({client})"
        elif title:
            return f"创建方案: 「{title[:30]}」"
        return "创建方案"

    elif op_type in ("CREATE_INVOICE",):
        invoice_num = args.get("invoice_number", "") or result.get("invoice_number", "")
        amount = args.get("amount", 0) or result.get("amount", 0)
        if invoice_num and amount:
            return f"创建发票: {invoice_num} (¥{amount})"
        elif invoice_num:
            return f"创建发票: {invoice_num}"
        return "创建发票"

    elif op_type in ("ADD_CUSTOMER",):
        name = args.get("name", "") or result.get("name", "")
        company = args.get("company", "") or result.get("company", "")
        if name and company:
            return f"添加客户: {name} ({company})"
        elif name:
            return f"添加客户: {name}"
        return "添加客户"

    elif op_type in ("ADD_FOLLOW_UP",):
        customer = args.get("customer_name", "") or result.get("customer_name", "")
        content = args.get("content", "") or result.get("content", "")
        if customer and content:
            return f"添加跟进: {customer} - {content[:20]}"
        elif customer:
            return f"添加跟进: {customer}"
        return "添加跟进"

    elif op_type in ("SOCIAL_PUBLISH",):
        platform = args.get("platform", "") or result.get("platform", "")
        content = args.get("content", "") or result.get("content", "")
        if platform and content:
            return f"发布内容: [{platform}] {content[:25]}"
        elif platform:
            return f"发布内容: [{platform}]"
        return "发布内容"

    fallback_title = args.get("title", "") or result.get("title", "")
    if fallback_title:
        return f"操作: {fallback_title[:40]}"

    return f"操作: {record.inverse_func_name}"


def _calculate_remaining_time(record: UndoRecordDisplay) -> Tuple[int, int, str]:
    """Calculate remaining time until expiry with status text.

    Args:
        record: UndoRecordDisplay object with timing info

    Returns:
        Tuple of (remaining_seconds, percentage, status_text)
    """
    now = time.time()
    created = record.created_at
    expires = record.expires_at

    total_window = max(expires - created, 1)
    remaining = max(0, int(expires - now))
    percentage = int((remaining / total_window) * 100) if total_window > 0 else 0

    if remaining <= 0:
        status_text = "❌ 已过期"
    elif remaining < 10:
        status_text = f"🔴 即将过期 ({remaining}秒)"
    elif remaining < 60:
        status_text = f"🟠 {remaining}秒后过期"
    else:
        mins, secs = divmod(remaining, 60)
        if mins >= 60:
            hours, remainder_mins = divmod(mins, 60)
            status_text = f"🟢 还剩{hours}小时{remainder_mins}分"
        else:
            status_text = f"🟢 还剩{mins}分{secs}秒"

    return remaining, percentage, status_text


def _format_time_ago(timestamp: float) -> str:
    """Format timestamp as relative time string (e.g., '2分钟前').

    Args:
        timestamp: Unix timestamp

    Returns:
        Relative time string in Chinese
    """
    now = time.time()
    diff = now - timestamp

    if diff < 60:
        return "刚刚"
    elif diff < 3600:
        mins = int(diff // 60)
        return f"{mins}分钟前"
    elif diff < 86400:
        hours = int(diff // 3600)
        return f"{hours}小时前"
    else:
        days = int(diff // 86400)
        return f"{days}天前"


def _convert_to_display_record(record_dict: dict) -> UndoRecordDisplay:
    """Convert raw record dict to UndoRecordDisplay with computed fields.

    Args:
        record_dict: Raw dictionary from UndoManager

    Returns:
        Populated UndoRecordDisplay instance
    """
    display = UndoRecordDisplay(
        operation_id=record_dict.get("operation_id", ""),
        operation_type=record_dict.get(
            "type", record_dict.get("operation_type", "unknown")
        ),
        session_id=record_dict.get("session_id", ""),
        inverse_func_name=record_dict.get("inverse_func_name", ""),
        inverse_args=record_dict.get("inverse_args", {}),
        original_result=record_dict.get("original_result", {}),
        created_at=record_dict.get("created_at", 0),
        expires_at=record_dict.get("expires_at", 0),
        status=record_dict.get("status", "active"),
    )

    display.description = _get_operation_description(display)
    display.remaining_seconds, _, _ = _calculate_remaining_time(display)
    display.time_ago = _format_time_ago(display.created_at)

    return display
