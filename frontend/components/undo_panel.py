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
import logging

from opc_manager.i18n import t as _t

# Re-export from sub-modules for backward compatibility
from frontend.components.undo_display import *  # noqa: F401,F403
from frontend.components.undo_export import *  # noqa: F401,F403
from frontend.components.undo_actions import *  # noqa: F401,F403

# Explicit imports for use in this module
from frontend.components.session_utils import _get_undo_manager
from frontend.components.undo_display import (
    UndoRecordDisplay,
    OPERATION_TYPE_CONFIG,
    STATUS_CONFIG,
    _calculate_remaining_time,
    _convert_to_display_record,
)
from frontend.components.undo_actions import (
    execute_undo,
    calculate_undo_stats,
)
from frontend.components.undo_export import (
    _render_export_options,
)

logger = logging.getLogger(__name__)


def _render_undo_record(
    record: UndoRecordDisplay, index: int, show_actions: bool = True
):
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
    op_config = OPERATION_TYPE_CONFIG.get(
        record.operation_type,
        {
            "icon": "",
            "label": "操作",
            "color": "#6B7280",
            "bg_color": "#F9FAFB",
        },
    )
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

    st.markdown(
        f"""
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
            <span> {record.time_ago}</span>
            <span>{status_text}</span>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    if show_actions and record.status == "active":
        col_undo, col_space = st.columns([1, 3])
        with col_undo:
            is_destructive = record.operation_type in ("SOCIAL_PUBLISH",)

            btn_type = "secondary" if not is_destructive else None
            help_text = "此操作将执行逆操作恢复原始状态"

            if is_destructive:
                help_text = " 此操作将删除已发布的内容，不可恢复"

            if st.button(
                " 撤销此操作",
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
    warning_icon = "" if is_destructive else ""
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

    st.markdown(
        f"""
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
    """,
        unsafe_allow_html=True,
    )

    col_confirm, col_cancel = st.columns([1, 1])

    with col_confirm:
        if st.button(
            " 确认撤销",
            key=f"confirm_undo_{record.operation_id}_{index}",
            type="primary" if not is_destructive else None,
            use_container_width=True,
        ):
            result = execute_undo(record.session_id, record.operation_id)
            if result["success"]:
                st.success(f" {result['message']}")
                st.toast(_t("undo_success_toast"), icon="")
                del st.session_state[f"pending_undo_{record.operation_id}"]
                time.sleep(1)
                st.rerun()
            else:
                st.error(f" {result['message']}")

    with col_cancel:
        if st.button(
            "取消",
            key=f"cancel_undo_{record.operation_id}_{index}",
            use_container_width=True,
        ):
            del st.session_state[f"pending_undo_{record.operation_id}"]
            st.rerun()


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
            label=" 可撤销",
            value=stats["active"],
            delta=None,
            help="当前在时间窗口内且可执行撤销的操作数",
        )

    with col_undone:
        st.metric(
            label=" 已撤销",
            value=stats["undone"],
            delta=None,
            help="已经执行过撤销的操作数",
        )

    with col_expired:
        st.metric(
            label=" 已过期",
            value=stats["expired"],
            delta=None,
            help="超过撤销窗口期的操作数",
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
    │  撤销历史 (最近5分钟内的操作)               │
    │ ─────────────────────────────────────────── │
    │  可撤销: 3项 | 已撤销: 1项 | 已过期: 2项   │
    │                                              │
    │  新建任务: "Q2营销方案"                    │
    │    2分钟前 |  还剩28秒可撤销                │
    │    [撤销此操作]                              │
    │                                              │
    │ [ 清除所有已过期记录]                       │
    └─────────────────────────────────────────────┘

    Args:
        session_id: Current session identifier
        expand: Whether to expand panel by default
    """
    um = _get_undo_manager()
    if not um:
        from opc_manager.i18n import t as _t

        st.info(_t("undo_not_ready"))
        return

    st.markdown(
        """
    <div style="
        background: linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%);
        border-left: 4px solid #6366F1;
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 16px;
    ">
        <span style="font-size: 18px; margin-right: 8px;"></span>
        <strong style="color: #3730A3;">撤销历史</strong>
        <span style="color: #6366F1; font-size: 12px;">（最近可撤销的操作）</span>
    </div>
    """,
        unsafe_allow_html=True,
    )

    stats = render_undo_stats(session_id)

    if stats["total"] == 0:
        st.info(" 暂无操作记录。执行任务后可在此查看和撤销操作。")
        return

    all_records_raw = []
    try:
        records_list = getattr(um, "_records", {}).get(session_id, [])
        for r in records_list:
            all_records_raw.append(
                {
                    "operation_id": r.operation_id,
                    "operation_type": (
                        r.operation_type.value
                        if hasattr(r.operation_type, "value")
                        else str(r.operation_type)
                    ),
                    "session_id": r.session_id,
                    "inverse_func_name": r.inverse_func_name,
                    "inverse_args": r.inverse_args,
                    "original_result": r.original_result,
                    "created_at": r.created_at,
                    "expires_at": r.expires_at,
                    "status": r.status,
                }
            )
    except Exception as e:
        logger.warning("[undo_panel] Failed to get raw records: %s", e)
        return

    sorted_records = sorted(
        all_records_raw, key=lambda x: x.get("created_at", 0), reverse=True
    )

    display_records = [_convert_to_display_record(r) for r in sorted_records]

    if expand or st.session_state.get("show_all_undo", False):
        records_to_show = display_records
    else:
        records_to_show = display_records[:5]

    st.caption(f"显示 {len(records_to_show)} 条记录（共 {len(display_records)} 条）")

    for idx, record in enumerate(records_to_show):
        with st.container():
            _render_undo_record(record, index=idx, show_actions=True)
            st.divider()

    if len(display_records) > 5 and not (
        expand or st.session_state.get("show_all_undo", False)
    ):
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
            " 清除所有已过期记录",
            key="cleanup_expired",
            use_container_width=True,
            help="移除所有已过期的撤销记录，不会影响已撤销的记录",
        ):
            um.cleanup_expired()
            st.success(" 已清除过期记录")
            st.rerun()

    export_col, _ = st.columns([1, 3])
    with export_col:
        if st.button(
            " 导出撤销历史",
            key="export_undo_history",
            use_container_width=True,
            help="导出为CSV或JSON格式（审计用途）",
        ):
            _render_export_options(display_records)


def render_mini_undo_hint(session_id: str, task_id: str = "latest"):
    """Render mini undo hint after task completion (Option B).

    Shows compact hint that this action can be undone within the window.
    Designed to be placed below result cards in chat area.

    Layout:
    ┌──────────────────────────────────────────┐
    │  此操作可在5分钟内撤销 [查看撤销历史]  │
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
        op_icon = op_config.get("icon", "")

        if remaining < 60:
            time_hint = f"{remaining}秒"
        else:
            mins = remaining // 60
            time_hint = f"{mins}分钟"

        st.markdown(
            f"""
        <div style="
            background: linear-gradient(135deg, #ECFDF5 0%, #D1FAE5 100%);
            border-left: 3px solid #10B981;
            padding: 10px 14px;
            border-radius: 6px;
            margin-top: 12px;
            font-size: 13px;
        ">
            <span style="font-size: 16px; margin-right: 6px;"></span>
            <strong>此操作可在 {time_hint} 内撤销</strong>
            <span style="color: #059669; margin-left: 8px;">
                {op_icon} {op_label}
            </span>
        </div>
        """,
            unsafe_allow_html=True,
        )

        col_hint, col_view = st.columns([2, 1])

        with col_hint:
            if st.button(
                " 立即撤销",
                key=f"mini_undo_{task_id}_{op_id}",
                type="secondary",
                use_container_width=True,
                help="点击立即撤销此操作",
            ):
                result = execute_undo(session_id, op_id)
                if result["success"]:
                    st.success(f" {result['message']}")
                    st.toast(_t("undo_success_toast"), icon="")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f" {result['message']}")

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
        records_list = getattr(um, "_records", {}).get(session_id, [])
        active_records = [
            r
            for r in records_list
            if r.status == "active" and r.expires_at > time.time()
        ]

        if len(active_records) < 2:
            st.info(" 批量撤销需要至少2个可撤销的操作")
            return

        st.markdown("####  批量撤销")

        st.caption(f"选择要撤销的操作（共 {len(active_records)} 个可撤销）")

        selected_ids = []

        for idx, r in enumerate(active_records):
            display = _convert_to_display_record(
                {
                    "operation_id": r.operation_id,
                    "operation_type": (
                        r.operation_type.value
                        if hasattr(r.operation_type, "value")
                        else str(r.operation_type)
                    ),
                    "session_id": r.session_id,
                    "inverse_func_name": r.inverse_func_name,
                    "inverse_args": r.inverse_args,
                    "original_result": r.original_result,
                    "created_at": r.created_at,
                    "expires_at": r.expires_at,
                    "status": r.status,
                }
            )

            col_check, col_info = st.columns([1, 4])

            with col_check:
                if st.checkbox(
                    "选择",
                    key=f"batch_select_{r.operation_id}_{idx}",
                    value=False,
                ):
                    selected_ids.append(r.operation_id)

            with col_info:
                st.markdown(f"**{display.description}**")
                st.caption(
                    f"{display.time_ago} | {_calculate_remaining_time(display)[2]}"
                )

        if selected_ids:
            st.divider()

            if st.button(
                f" 批量撤销选中项 ({len(selected_ids)}个)",
                key="batch_undo_execute",
                type="primary",
                use_container_width=True,
            ):
                progress_bar = st.progress(0, text="准备批量撤销...")

                success_count = 0
                fail_count = 0

                for i, op_id in enumerate(selected_ids):
                    progress = int(((i + 1) / len(selected_ids)) * 100)
                    progress_bar.progress(
                        progress, text=f"正在撤销 ({i+1}/{len(selected_ids)})..."
                    )

                    result = execute_undo(session_id, op_id)
                    if result["success"]:
                        success_count += 1
                    else:
                        fail_count += 1
                    time.sleep(0.3)

                progress_bar.progress(100, text=" 批量撤销完成!")

                st.success(
                    f" 批量撤销完成: 成功 {success_count} 个, 失败 {fail_count} 个"
                )
                time.sleep(1)
                st.rerun()
        else:
            st.caption(_t("undo_select_hint"))

    except Exception as e:
        logger.error("[undo_panel] Batch undo error: %s", e)
        st.error(_t("undo_batch_error"))
