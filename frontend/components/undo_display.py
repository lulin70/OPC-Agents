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
from typing import Tuple
from dataclasses import dataclass

from opc_manager.i18n import t as _t

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
        "icon": "",
        "label": _t("undo_op_email_send"),
        "color": "#3B82F6",
        "bg_color": "#EFF6FF",
    },
    "RECORD_INCOME": {
        "icon": "",
        "label": _t("undo_op_record_income"),
        "color": "#10B981",
        "bg_color": "#ECFDF5",
    },
    "RECORD_EXPENSE": {
        "icon": "",
        "label": _t("undo_op_record_expense"),
        "color": "#F59E0B",
        "bg_color": "#FFFBEB",
    },
    "ADD_DEAL": {
        "icon": "",
        "label": _t("undo_op_add_deal"),
        "color": "#06B6D4",
        "bg_color": "#ECFEFF",
    },
    "CREATE_INVOICE": {
        "icon": "",
        "label": _t("undo_op_create_invoice"),
        "color": "#14B8A6",
        "bg_color": "#F0FDFA",
    },
    "ADD_CUSTOMER": {
        "icon": "",
        "label": _t("undo_op_add_customer"),
        "color": "#F97316",
        "bg_color": "#FFF7ED",
    },
    "ADD_FOLLOW_UP": {
        "icon": "",
        "label": _t("undo_op_add_follow_up"),
        "color": "#EC4899",
        "bg_color": "#FDF2F8",
    },
    "SOCIAL_PUBLISH": {
        "icon": "",
        "label": _t("undo_op_social_publish"),
        "color": "#EF4444",
        "bg_color": "#FEF2F2",
    },
}

STATUS_CONFIG = {
    "active": {
        "icon": "",
        "label": _t("undo_status_active"),
        "color": "#10B981",
        "text_color": "green",
    },
    "undone": {
        "icon": "",
        "label": _t("undo_status_undone"),
        "color": "#9CA3AF",
        "text_color": "gray",
    },
    "expired": {
        "icon": "",
        "label": _t("undo_status_expired"),
        "color": "#EF4444",
        "text_color": "red",
    },
}


def _get_operation_description(record: UndoRecordDisplay) -> str:
    """Generate human-readable description from inverse_args and original_result.

    Args:
        record: UndoRecordDisplay object with operation details

    Returns:
        Human-readable description string
    """
    op_type = record.operation_type
    args = record.inverse_args or {}
    result = record.original_result or {}

    if op_type in ("EMAIL_SEND",):
        subject = args.get("subject", "") or result.get("subject", "")
        to_email = args.get("to", "") or result.get("to", "")
        if subject and to_email:
            return _t("undo_desc_email_to", subject=subject[:30], to=to_email)
        elif subject:
            return _t("undo_desc_email", subject=subject[:30])
        return _t("undo_op_email_send")

    elif op_type in ("RECORD_INCOME",):
        amount = args.get("amount", 0) or result.get("amount", 0)
        project = args.get("project", "") or result.get("project", "")
        if amount and project:
            return _t("undo_desc_income_project", amount=amount, project=project)
        elif amount:
            return _t("undo_desc_income", amount=amount)
        return _t("undo_op_record_income")

    elif op_type in ("RECORD_EXPENSE",):
        amount = args.get("amount", 0) or result.get("amount", 0)
        category = args.get("category", "") or result.get("category", "")
        if amount and category:
            return _t("undo_desc_expense_category", amount=amount, category=category)
        elif amount:
            return _t("undo_desc_expense", amount=amount)
        return _t("undo_op_record_expense")

    elif op_type in ("ADD_DEAL",):
        deal_name = args.get("deal_name", "") or result.get("deal_name", "")
        value = args.get("value", 0) or result.get("value", 0)
        if deal_name and value:
            return _t("undo_desc_deal_value", deal_name=deal_name, value=value)
        elif deal_name:
            return _t("undo_desc_deal", deal_name=deal_name)
        return _t("undo_op_add_deal")

    elif op_type in ("CREATE_INVOICE",):
        invoice_num = args.get("invoice_number", "") or result.get("invoice_number", "")
        amount = args.get("amount", 0) or result.get("amount", 0)
        if invoice_num and amount:
            return _t("undo_desc_invoice_amount", invoice=invoice_num, amount=amount)
        elif invoice_num:
            return _t("undo_desc_invoice", invoice=invoice_num)
        return _t("undo_op_create_invoice")

    elif op_type in ("ADD_CUSTOMER",):
        name = args.get("name", "") or result.get("name", "")
        company = args.get("company", "") or result.get("company", "")
        if name and company:
            return _t("undo_desc_customer_company", name=name, company=company)
        elif name:
            return _t("undo_desc_customer", name=name)
        return _t("undo_op_add_customer")

    elif op_type in ("ADD_FOLLOW_UP",):
        customer = args.get("customer_name", "") or result.get("customer_name", "")
        content = args.get("content", "") or result.get("content", "")
        if customer and content:
            return _t("undo_desc_followup", customer=customer, content=content[:20])
        elif customer:
            return _t("undo_desc_followup_customer", customer=customer)
        return _t("undo_op_add_follow_up")

    elif op_type in ("SOCIAL_PUBLISH",):
        platform = args.get("platform", "") or result.get("platform", "")
        content = args.get("content", "") or result.get("content", "")
        if platform and content:
            return _t("undo_desc_social", platform=platform, content=content[:25])
        elif platform:
            return _t("undo_desc_social_platform", platform=platform)
        return _t("undo_op_social_publish")

    fallback_title = args.get("title", "") or result.get("title", "")
    if fallback_title:
        return _t("undo_desc_fallback", title=fallback_title[:40])

    return _t("undo_desc_operation", func=record.inverse_func_name)


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
        status_text = " " + _t("undo_time_expired")
    elif remaining < 10:
        status_text = " " + _t("undo_time_expiring_soon", secs=remaining)
    elif remaining < 60:
        status_text = " " + _t("undo_time_seconds", secs=remaining)
    else:
        mins, secs = divmod(remaining, 60)
        if mins >= 60:
            hours, remainder_mins = divmod(mins, 60)
            status_text = " " + _t(
                "undo_time_hours_mins", hours=hours, mins=remainder_mins
            )
        else:
            status_text = " " + _t("undo_time_mins_secs", mins=mins, secs=secs)

    return remaining, percentage, status_text


def _format_time_ago(timestamp: float) -> str:
    """Format timestamp as relative time string.

    Args:
        timestamp: Unix timestamp

    Returns:
        Relative time string
    """
    now = time.time()
    diff = now - timestamp

    if diff < 60:
        return _t("time_just_now")
    elif diff < 3600:
        mins = int(diff // 60)
        return _t("time_minutes_ago", mins=mins)
    elif diff < 86400:
        hours = int(diff // 3600)
        return _t("time_hours_ago", hours=hours)
    else:
        days = int(diff // 86400)
        return _t("time_days_ago", days=days)


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
