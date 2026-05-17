"""Undo Panel UI Component — Enhanced visualization for OPC-Agents undo system.

Provides:
- Main undo panel with visual record cards
- Operation type icons and status indicators
- Countdown timers with color-coded urgency
- One-click undo execution with confirmation
- Statistics summary dashboard
- Batch operations and export functionality
- Integration with ProgressEmitter and Smart Suggestions

Design Principles:
- Chinese interface with clear status indicators
- Color-coded operation types (CREATE=green, UPDATE=blue, DELETE=red)
- Real-time countdown refresh on each rerun
- Confirmation dialogs for destructive operations
- Responsive layout for sidebar and inline usage
"""

import streamlit as st
import time
import json
import csv
import io
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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


def _get_undo_manager():
    """Safe wrapper to get UndoManager instance."""
    try:
        from opc_manager.undo_manager import get_undo_manager
        return get_undo_manager()
    except ImportError:
        return None
    except Exception as e:
        logger.warning("[undo_panel] UndoManager init failed: %s", e)
        return None


def _get_current_session_id() -> str:
    """Get current session ID from session context."""
    try:
        session_ctx = st.session_state.get("session_ctx")
        if session_ctx and hasattr(session_ctx, '_session_id'):
            return session_ctx._session_id
        elif session_ctx and hasattr(session_ctx, 'session_id'):
            return session_ctx.session_id
    except Exception:
        pass
    return st.session_state.get("session_id", "default")


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
        return f"发送邮件"

    elif op_type in ("RECORD_INCOME",):
        amount = args.get("amount", 0) or result.get("amount", 0)
        project = args.get("project", "") or result.get("project", "")
        desc = args.get("description", "") or result.get("description", "")
        if amount and project:
            return f"记录收入: ¥{amount} ({project})"
        elif amount:
            return f"记录收入: ¥{amount}"
        return f"记录收入"

    elif op_type in ("RECORD_EXPENSE",):
        amount = args.get("amount", 0) or result.get("amount", 0)
        category = args.get("category", "") or result.get("category", "")
        if amount and category:
            return f"记录支出: ¥{amount} ({category})"
        elif amount:
            return f"记录支出: ¥{amount}"
        return f"记录支出"

    elif op_type in ("ADD_EVENT",):
        title = args.get("title", "") or result.get("title", "")
        if title:
            return f"新建日程: 「{title[:30]}」"
        return f"新建日程"

    elif op_type in ("ADD_DEAL",):
        deal_name = args.get("deal_name", "") or result.get("deal_name", "")
        value = args.get("value", 0) or result.get("value", 0)
        if deal_name and value:
            return f"新建商机: {deal_name} (¥{value})"
        elif deal_name:
            return f"新建商机: {deal_name}"
        return f"新建商机"

    elif op_type in ("CREATE_PROPOSAL",):
        title = args.get("title", "") or result.get("title", "")
        client = args.get("client", "") or result.get("client", "")
        if title and client:
            return f"创建方案: 「{title[:25]}」({client})"
        elif title:
            return f"创建方案: 「{title[:30]}」"
        return f"创建方案"

    elif op_type in ("CREATE_INVOICE",):
        invoice_num = args.get("invoice_number", "") or result.get("invoice_number", "")
        amount = args.get("amount", 0) or result.get("amount", 0)
        if invoice_num and amount:
            return f"创建发票: {invoice_num} (¥{amount})"
        elif invoice_num:
            return f"创建发票: {invoice_num}"
        return f"创建发票"

    elif op_type in ("ADD_CUSTOMER",):
        name = args.get("name", "") or result.get("name", "")
        company = args.get("company", "") or result.get("company", "")
        if name and company:
            return f"添加客户: {name} ({company})"
        elif name:
            return f"添加客户: {name}"
        return f"添加客户"

    elif op_type in ("ADD_FOLLOW_UP",):
        customer = args.get("customer_name", "") or result.get("customer_name", "")
        content = args.get("content", "") or result.get("content", "")
        if customer and content:
            return f"添加跟进: {customer} - {content[:20]}"
        elif customer:
            return f"添加跟进: {customer}"
        return f"添加跟进"

    elif op_type in ("SOCIAL_PUBLISH",):
        platform = args.get("platform", "") or result.get("platform", "")
        content = args.get("content", "") or result.get("content", "")
        if platform and content:
            return f"发布内容: [{platform}] {content[:25]}"
        elif platform:
            return f"发布内容: [{platform}]"
        return f"发布内容"

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
        operation_type=record_dict.get("type", record_dict.get("operation_type", "unknown")),
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


def _render_undo_record(record: UndoRecordDisplay, index: int, show_actions: bool = True):
    """Render a single undo record as a styled card.

    Visual design includes:
    - Operation type icon with color-coded background
    - Human-readable description
    - Relative timestamp
    - Countdown timer with urgency colors
    - Status indicator (active/undone/expired)
    - Action button (only when active)

    Args:
        record: UndoRecordDisplay object to render
        index: Index for unique Streamlit keys
        show_actions: Whether to show action buttons
    """
    op_config = OPERATION_TYPE_CONFIG.get(record.operation_type, {
        "icon": "📝",
        "label": "操作",
        "color": "#6B7280",
        "bg_color": "#F9FAFB",
    })
    status_config = STATUS_CONFIG.get(record.status, STATUS_CONFIG["active"])

    remaining, percentage, status_text = _calculate_remaining_time(record)

    card_bg = "#FFFFFF"
    border_left = op_config["color"]

    if record.status == "expired":
        card_bg = "#FEF2F2"
        border_left = "#EF4444"
    elif record.status == "undone":
        card_bg = "#F9FAFB"
        border_left = "#D1D5DB"

    st.markdown(f"""
    <div style="
        background: {card_bg};
        border-left: 4px solid {border_left};
        border-radius: 8px;
        padding: 12px 16px;
        margin: 8px 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    ">
        <div style="display: flex; align-items: center; margin-bottom: 8px;">
            <span style="
                font-size: 20px;
                margin-right: 8px;
                background: {op_config['bg_color']};
                padding: 4px 8px;
                border-radius: 6px;
            ">{op_config['icon']}</span>
            <div>
                <span style="font-weight: 600; font-size: 14px; color: #1F2937;">
                    {record.description}
                </span>
            </div>
        </div>

        <div style="display: flex; align-items: center; gap: 16px; font-size: 12px; color: #6B7280;">
            <span>🕐 {record.time_ago}</span>
            <span>{status_text}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if show_actions and record.status == "active":
        col_undo, col_space = st.columns([1, 3])
        with col_undo:
            is_destructive = record.operation_type in (
                "SOCIAL_PUBLISH",
            )

            btn_type = "secondary" if not is_destructive else None
            help_text = "此操作将执行逆操作恢复原始状态"

            if is_destructive:
                help_text = "⚠️ 此操作将删除已发布的内容，不可恢复"

            if st.button(
                "↩️ 撤销此操作",
                key=f"undo_btn_{record.operation_id}_{index}",
                type=btn_type,
                use_container_width=True,
                help=help_text,
            ):
                st.session_state[f"pending_undo_{record.operation_id}"] = True

        if st.session_state.get(f"pending_undo_{record.operation_id}", False):
            _render_confirmation_dialog(
                record=record,
                index=index,
                is_destructive=is_destructive,
            )
    elif record.status == "undone":
        st.caption(f"{status_config['icon']} 此操作已被撤销")
    elif record.status == "expired":
        st.caption(f"{status_config['icon']} 已过撤销窗口期，无法撤销")


def _render_confirmation_dialog(
    record: UndoRecordDisplay,
    index: int,
    is_destructive: bool = False,
):
    """Render confirmation dialog before executing undo.

    For destructive operations (DELETE type), shows enhanced warning.

    Args:
        record: Record to be undone
        index: Index for unique keys
        is_destructive: Whether this is a destructive operation
    """
    warning_icon = "⚠️" if is_destructive else "💡"
    warning_color = "#DC2626" if is_destructive else "#D97706"
    bg_color = "#FEF2F2" if is_destructive else "#FFFBEB"

    if is_destructive:
        warning_text = f"""
        **确定要撤销此操作吗？**

        这将执行以下逆操作：
        - **类型**: {OPERATION_TYPE_CONFIG.get(record.operation_type, {}).get('label', '未知')}
        - **内容**: {record.description}
        - **影响**: 此操作**不可恢复**，请谨慎操作
        """
    else:
        warning_text = f"""
        **确认撤销此操作？**

        - **操作**: {record.description}
        - **结果**: 系统将执行逆操作 `{record.inverse_func_name}` 恢复到操作前的状态
        """

    st.markdown(f"""
    <div style="
        background: {bg_color};
        border: 2px solid {warning_color};
        border-radius: 8px;
        padding: 16px;
        margin: 8px 0;
    ">
        <div style="font-size: 18px; margin-bottom: 8px;">{warning_icon}</div>
        {warning_text}
    </div>
    """, unsafe_allow_html=True)

    col_confirm, col_cancel = st.columns([1, 1])

    with col_confirm:
        if st.button(
            "✅ 确认撤销",
            key=f"confirm_undo_{record.operation_id}_{index}",
            type="primary" if not is_destructive else None,
            use_container_width=True,
        ):
            result = execute_undo(record.session_id, record.operation_id)
            if result["success"]:
                st.success(f"✅ {result['message']}")
                st.balloons()
                del st.session_state[f"pending_undo_{record.operation_id}"]
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"❌ {result['message']}")

    with col_cancel:
        if st.button(
            "取消",
            key=f"cancel_undo_{record.operation_id}_{index}",
            use_container_width=True,
        ):
            del st.session_state[f"pending_undo_{record.operation_id}"]
            st.rerun()


def execute_undo(session_id: str, operation_id: str) -> dict:
    """Execute undo operation with ProgressEmitter integration.

    Flow:
    1. Emit STEP_START event via ProgressEmitter
    2. Call UndoManager.undo()
    3. Emit STEP_COMPLETE or ERROR based on result
    4. Return standardized result dict

    Args:
        session_id: Session identifier
        operation_id: Operation to undo

    Returns:
        Dict with 'success' bool and 'message' str
    """
    um = _get_undo_manager()
    if not um:
        return {"success": False, "message": "UndoManager未初始化"}

    try:
        try:
            from opc_manager.progress_emitter import ProgressEmitter, EventType
            emitter = ProgressEmitter()
            emitter.emit(
                session_id=session_id,
                event_type=EventType.STEP_START,
                message=f"正在撤销操作: {operation_id[:8]}...",
                progress=0,
            )
        except ImportError:
            logger.debug("[undo_panel] ProgressEmitter not available")
        except Exception as e:
            logger.warning("[undo_panel] Emit STEP_START failed: %s", e)

        can_undo, reason = um.can_undo(session_id, operation_id)
        if not can_undo:
            return {"success": False, "message": f"无法撤销: {reason}"}

        result = um.undo(session_id, operation_id)

        if result.get("success"):
            try:
                from opc_manager.progress_emitter import ProgressEmitter, EventType
                emitter = ProgressEmitter()
                emitter.emit(
                    session_id=session_id,
                    event_type=EventType.STEP_COMPLETE,
                    message=f"撤销成功: {operation_id[:8]}",
                    progress=100,
                )
            except ImportError:
                pass
            except Exception as e:
                logger.warning("[undo_panel] Emit STEP_COMPLETE failed: %s", e)

            return {
                "success": True,
                "message": f"撤销成功！已执行逆操作恢复数据",
                "operation_id": operation_id,
            }
        else:
            error_msg = result.get("error", "未知错误")
            try:
                from opc_manager.progress_emitter import ProgressEmitter, EventType
                emitter = ProgressEmitter()
                emitter.emit(
                    session_id=session_id,
                    event_type=EventType.ERROR,
                    message=f"撤销失败: {error_msg}",
                    progress=0,
                )
            except ImportError:
                pass
            except Exception as e:
                logger.warning("[undo_panel] Emit ERROR failed: %s", e)

            return {"success": False, "message": f"撤销失败: {error_msg}"}

    except ValueError as e:
        return {"success": False, "message": f"参数错误: {str(e)}"}
    except Exception as e:
        logger.error("[undo_panel] execute_undo exception: %s", e)
        return {"success": False, "message": f"系统错误: {str(e)}"}


def calculate_undo_stats(session_id: str) -> dict:
    """Calculate undo statistics without UI rendering.

    Args:
        session_id: Session identifier

    Returns:
        Dict with statistics: {active: int, undone: int, expired: int, total: int}
    """
    um = _get_undo_manager()
    if not um:
        return {"active": 0, "undone": 0, "expired": 0, "total": 0}

    stats = {"active": 0, "undone": 0, "expired": 0, "total": 0}

    try:
        all_records = getattr(um, '_records', {}).get(session_id, [])
        stats["total"] = len(all_records)

        now = time.time()
        for r in all_records:
            if r.status == "active":
                if r.expires_at > now:
                    stats["active"] += 1
                else:
                    stats["expired"] += 1
            elif r.status == "undone":
                stats["undone"] += 1
            else:
                stats["expired"] += 1
    except Exception as e:
        logger.warning("[undo_panel] Stats calculation error: %s", e)

    return stats


def render_undo_stats(session_id: str) -> dict:
    """Render statistics summary of undo records.

    Shows counts by status: active, undone, expired

    Args:
        session_id: Session identifier

    Returns:
        Dict with statistics: {active: int, undone: int, expired: int, total: int}
    """
    stats = calculate_undo_stats(session_id)

    col_active, col_undone, col_expired = st.columns(3)

    with col_active:
        st.metric(
            label="🟢 可撤销",
            value=stats["active"],
            delta=None,
            help="当前在时间窗口内且可执行撤销的操作数"
        )

    with col_undone:
        st.metric(
            label="⚪ 已撤销",
            value=stats["undone"],
            delta=None,
            help="已经执行过撤销的操作数"
        )

    with col_expired:
        st.metric(
            label="🔴 已过期",
            value=stats["expired"],
            delta=None,
            help="超过撤销窗口期的操作数"
        )

    return stats


def render_undo_panel(session_id: str, expand: bool = False):
    """Main undo panel rendering function.

    Renders complete undo history panel with:
    - Statistics summary at top
    - List of undoable records (most recent first)
    - Each record shows type icon, description, countdown, status
    - Action buttons for active records
    - Cleanup button for expired records

    Visual Layout:
    ┌─────────────────────────────────────────────┐
    │ ↩️ 撤销历史 (最近5分钟内的操作)               │
    │ ─────────────────────────────────────────── │
    │ 📊 可撤销: 3项 | 已撤销: 1项 | 已过期: 2项   │
    │                                              │
    │ 📝 新建任务: "Q2营销方案"                    │
    │    2分钟前 | ⏱️ 还剩28秒可撤销                │
    │    [撤销此操作]                              │
    │                                              │
    │ [🗑️ 清除所有已过期记录]                       │
    └─────────────────────────────────────────────┘

    Args:
        session_id: Current session identifier
        expand: Whether to expand panel by default
    """
    um = _get_undo_manager()
    if not um:
        st.warning("⚠️ 撤销系统未初始化")
        return

    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%);
        border-left: 4px solid #6366F1;
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 16px;
    ">
        <span style="font-size: 18px; margin-right: 8px;">↩️</span>
        <strong style="color: #3730A3;">撤销历史</strong>
        <span style="color: #6366F1; font-size: 12px;">（最近可撤销的操作）</span>
    </div>
    """, unsafe_allow_html=True)

    stats = render_undo_stats(session_id)

    if stats["total"] == 0:
        st.info("💡 暂无操作记录。执行任务后可在此查看和撤销操作。")
        return

    all_records_raw = []
    try:
        records_list = getattr(um, '_records', {}).get(session_id, [])
        for r in records_list:
            all_records_raw.append({
                "operation_id": r.operation_id,
                "operation_type": r.operation_type.value if hasattr(r.operation_type, 'value') else str(r.operation_type),
                "session_id": r.session_id,
                "inverse_func_name": r.inverse_func_name,
                "inverse_args": r.inverse_args,
                "original_result": r.original_result,
                "created_at": r.created_at,
                "expires_at": r.expires_at,
                "status": r.status,
            })
    except Exception as e:
        logger.warning("[undo_panel] Failed to get raw records: %s", e)
        return

    sorted_records = sorted(all_records_raw, key=lambda x: x.get("created_at", 0), reverse=True)

    display_records = [_convert_to_display_record(r) for r in sorted_records]

    active_count = sum(1 for r in display_records if r.status == "active")

    if expand or st.session_state.get("show_all_undo", False):
        records_to_show = display_records
    else:
        records_to_show = display_records[:5]

    st.caption(f"显示 {len(records_to_show)} 条记录（共 {len(display_records)} 条）")

    for idx, record in enumerate(records_to_show):
        with st.container():
            _render_undo_record(record, index=idx, show_actions=True)
            st.divider()

    if len(display_records) > 5 and not (expand or st.session_state.get("show_all_undo", False)):
        if st.button(
            f"查看全部 {len(display_records)} 条记录 ▼",
            key="show_more_undo",
            use_container_width=True,
        ):
            st.session_state.show_all_undo = True
            st.rerun()

    has_expired = any(r.status == "expired" for r in display_records)
    if has_expired:
        st.divider()
        if st.button(
            "🗑️ 清除所有已过期记录",
            key="cleanup_expired",
            use_container_width=True,
            help="移除所有已过期的撤销记录，不会影响已撤销的记录",
        ):
            um.cleanup_expired()
            st.success("✅ 已清除过期记录")
            st.rerun()

    export_col, _ = st.columns([1, 3])
    with export_col:
        if st.button(
            "📥 导出撤销历史",
            key="export_undo_history",
            use_container_width=True,
            help="导出为CSV或JSON格式（审计用途）",
        ):
            _render_export_options(display_records)


def _render_export_options(records: List[UndoRecordDisplay]):
    """Render export format selection dialog.

    Args:
        records: List of records to export
    """
    st.markdown("#### 📤 导出撤销历史")

    format_option = st.radio(
        "选择导出格式",
        options=["CSV表格", "JSON数据"],
        horizontal=True,
        key="undo_export_format",
    )

    if format_option == "CSV表格":
        csv_data = _generate_csv(records)
        st.download_button(
            label="⬇️ 下载 CSV 文件",
            data=csv_data,
            file_name=f"undo_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            key="download_undo_csv",
            use_container_width=True,
            type="primary",
        )
    else:
        json_data = _generate_json(records)
        st.download_button(
            label="⬇️ 下载 JSON 文件",
            data=json_data,
            file_name=f"undo_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            key="download_undo_json",
            use_container_width=True,
            type="primary",
        )


def _generate_csv(records: List[UndoRecordDisplay]) -> str:
    """Generate CSV formatted string from records.

    Args:
        records: List of UndoRecordDisplay objects

    Returns:
        CSV formatted string
    """
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "操作ID",
        "操作类型",
        "描述",
        "状态",
        "创建时间",
        "过期时间",
        "剩余秒数",
        "逆函数名",
    ])

    for r in records:
        created_str = datetime.fromtimestamp(r.created_at).strftime("%Y-%m-%d %H:%M:%S")
        expires_str = datetime.fromtimestamp(r.expires_at).strftime("%Y-%m-%d %H:%M:%S")

        writer.writerow([
            r.operation_id,
            r.operation_type,
            r.description,
            r.status,
            created_str,
            expires_str,
            r.remaining_seconds,
            r.inverse_func_name,
        ])

    return output.getvalue()


def _generate_json(records: List[UndoRecordDisplay]) -> str:
    """Generate JSON formatted string from records.

    Args:
        records: List of UndoRecordDisplay objects

    Returns:
        JSON formatted string
    """
    export_data = []

    for r in records:
        export_data.append({
            "operation_id": r.operation_id,
            "operation_type": r.operation_type,
            "description": r.description,
            "status": r.status,
            "created_at": datetime.fromtimestamp(r.created_at).isoformat(),
            "expires_at": datetime.fromtimestamp(r.expires_at).isoformat(),
            "remaining_seconds": r.remaining_seconds,
            "time_ago": r.time_ago,
            "inverse_func_name": r.inverse_func_name,
            "inverse_args": r.inverse_args,
            "original_result_summary": str(r.original_result)[:200],
        })

    return json.dumps(export_data, ensure_ascii=False, indent=2)


def render_mini_undo_hint(session_id: str, task_id: str = "latest"):
    """Render mini undo hint after task completion (Option B).

    Shows compact hint that this action can be undone within the window.
    Designed to be placed below result cards in chat area.

    Layout:
    ┌──────────────────────────────────────────┐
    │ 💡 此操作可在5分钟内撤销 [查看撤销历史]  │
    └──────────────────────────────────────────┘

    Args:
        session_id: Current session identifier
        task_id: Task identifier for unique keys
    """
    um = _get_undo_manager()
    if not um:
        return

    try:
        undoable = um.list_undoable(session_id)
        if not undoable:
            return

        latest = undoable[0] if undoable else None
        if not latest:
            return

        op_id = latest.get("operation_id", "")
        can_undo, reason = um.can_undo(session_id, op_id)

        if not can_undo:
            return

        remaining = latest.get("remaining_seconds", 0)
        op_type = latest.get("type", "operation")

        op_config = OPERATION_TYPE_CONFIG.get(op_type, {})
        op_label = op_config.get("label", "操作")
        op_icon = op_config.get("icon", "📝")

        if remaining < 60:
            time_hint = f"{remaining}秒"
        else:
            mins = remaining // 60
            time_hint = f"{mins}分钟"

        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #ECFDF5 0%, #D1FAE5 100%);
            border-left: 3px solid #10B981;
            padding: 10px 14px;
            border-radius: 6px;
            margin-top: 12px;
            font-size: 13px;
        ">
            <span style="font-size: 16px; margin-right: 6px;">💡</span>
            <strong>此操作可在 {time_hint} 内撤销</strong>
            <span style="color: #059669; margin-left: 8px;">
                {op_icon} {op_label}
            </span>
        </div>
        """, unsafe_allow_html=True)

        col_hint, col_view = st.columns([2, 1])

        with col_hint:
            if st.button(
                f"↩️ 立即撤销",
                key=f"mini_undo_{task_id}_{op_id}",
                type="secondary",
                use_container_width=True,
                help="点击立即撤销此操作",
            ):
                result = execute_undo(session_id, op_id)
                if result["success"]:
                    st.success(f"✅ {result['message']}")
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ {result['message']}")

        with col_view:
            if st.button(
                "查看撤销历史",
                key=f"view_undo_{task_id}",
                use_container_width=True,
            ):
                st.session_state.show_undo_panel = True
                st.rerun()

    except Exception as e:
        logger.warning("[undo_panel] Mini undo hint error: %s", e)


def render_batch_undo(session_id: str):
    """Render batch undo interface for selecting multiple records.

    Allows user to select multiple active records and undo them all at once
    with a progress indicator.

    Args:
        session_id: Current session identifier
    """
    um = _get_undo_manager()
    if not um:
        return

    try:
        records_list = getattr(um, '_records', {}).get(session_id, [])
        active_records = [r for r in records_list if r.status == "active" and r.expires_at > time.time()]

        if len(active_records) < 2:
            st.info("⚠️ 批量撤销需要至少2个可撤销的操作")
            return

        st.markdown("#### 📦 批量撤销")

        st.caption(f"选择要撤销的操作（共 {len(active_records)} 个可撤销）")

        selected_ids = []

        for idx, r in enumerate(active_records):
            display = _convert_to_display_record({
                "operation_id": r.operation_id,
                "operation_type": r.operation_type.value if hasattr(r.operation_type, 'value') else str(r.operation_type),
                "session_id": r.session_id,
                "inverse_func_name": r.inverse_func_name,
                "inverse_args": r.inverse_args,
                "original_result": r.original_result,
                "created_at": r.created_at,
                "expires_at": r.expires_at,
                "status": r.status,
            })

            col_check, col_info = st.columns([1, 4])

            with col_check:
                if st.checkbox(
                    f"选择",
                    key=f"batch_select_{r.operation_id}_{idx}",
                    value=False,
                ):
                    selected_ids.append(r.operation_id)

            with col_info:
                st.markdown(f"**{display.description}**")
                st.caption(f"{display.time_ago} | {_calculate_remaining_time(display)[2]}")

        if selected_ids:
            st.divider()

            if st.button(
                f"↩️ 批量撤销选中项 ({len(selected_ids)}个)",
                key="batch_undo_execute",
                type="primary",
                use_container_width=True,
            ):
                progress_bar = st.progress(0, text="准备批量撤销...")

                success_count = 0
                fail_count = 0

                for i, op_id in enumerate(selected_ids):
                    progress = int(((i + 1) / len(selected_ids)) * 100)
                    progress_bar.progress(progress, text=f"正在撤销 ({i+1}/{len(selected_ids)})...")

                    result = execute_undo(session_id, op_id)
                    if result["success"]:
                        success_count += 1
                    else:
                        fail_count += 1
                    time.sleep(0.3)

                progress_bar.progress(100, text="✅ 批量撤销完成!")

                st.success(f"✅ 批量撤销完成: 成功 {success_count} 个, 失败 {fail_count} 个")
                time.sleep(1)
                st.rerun()
        else:
            st.caption("☝️ 请勾选上方要撤销的操作")

    except Exception as e:
        logger.error("[undo_panel] Batch undo error: %s", e)
        st.error("❌ 批量撤销出错")


def check_has_active_undo_records(session_id: str) -> bool:
    """Check if session has any active (undoable) records.

    Used by smart_suggestions system to determine whether
    to suggest undo action.

    Args:
        session_id: Session identifier

    Returns:
        True if there are active undo records
    """
    um = _get_undo_manager()
    if not um:
        return False

    try:
        undoable = um.list_undoable(session_id)
        return len(undoable) > 0
    except Exception:
        return False


def get_latest_undo_record_info(session_id: str) -> Optional[dict]:
    """Get information about the most recent active undo record.

    Used by smart_suggestions to generate contextual undo suggestion.

    Args:
        session_id: Session identifier

    Returns:
        Dict with record info or None if no active records
    """
    um = _get_undo_manager()
    if not um:
        return None

    try:
        undoable = um.list_undoable(session_id)
        if not undoable:
            return None

        latest = undoable[0]
        op_type = latest.get("type", "unknown")
        op_config = OPERATION_TYPE_CONFIG.get(op_type, {})

        return {
            "operation_id": latest.get("operation_id", ""),
            "operation_type": op_type,
            "label": op_config.get("label", "操作"),
            "icon": op_config.get("icon", "📝"),
            "remaining_seconds": latest.get("remaining_seconds", 0),
            "description": latest.get("original_summary", ""),
        }
    except Exception:
        return None
