"""操作时间线可视化组件

提供用户操作历史的可视化展示，支持：
- 多数据源集成（deliverables、UndoManager、AuditLog、ProgressEmitter）
- 时间线垂直布局展示
- 多维度筛选（时间、类别、状态、关键词）
- 统计摘要和分组显示
- 导出功能（PNG/PDF/CSV）
- 响应式设计（移动端适配）

=== 核心数据结构 ===
TimelineEvent: 单个时间线事件的数据模型（在 timeline_data.py 中定义）
EVENT_TYPE_CONFIG: 事件类型配置（图标、颜色、分类）

=== 主要函数 ===
render_timeline_view(): 主渲染器
build_timeline_from_session(): 从session状态构建时间线（在 timeline_data.py 中定义）
"""

import streamlit as st
import logging
from datetime import datetime
from typing import List, Dict

from opc_manager.i18n import t as _t

# Re-export from sub-modules for backward compatibility
from frontend.components.timeline_data import *  # noqa: F401,F403
from frontend.components.timeline_export import (  # noqa: F401
    _render_export_section,
    export_timeline,
    _export_to_csv,
    _export_to_markdown,
    _export_to_png,
    _escape_html,
)
from frontend.components.timeline_filters import (  # noqa: F401
    _render_timeline_filters,
    _apply_filters,
    _group_events_by_time,
    _render_timeline_stats,
)

# Explicit re-imports for use in this module
from frontend.components.timeline_data import (
    TimelineEvent,
    EVENT_TYPE_CONFIG,
    _get_category_labels,
    _get_status_labels,
)
from frontend.components.timeline_filters import (
    _render_timeline_stats,
    _render_timeline_filters,
    _group_events_by_time,
)
from frontend.components.timeline_export import (
    _render_export_section,
    _escape_html,
)

logger = logging.getLogger(__name__)


def render_timeline_view(events: List[TimelineEvent], title: str = None):
    """主渲染器：渲染完整的时间线视图

    UI布局：
    - 顶部：标题 + 统计摘要 + 筛选器
    - 中部：按时间分组的事件列表（垂直时间线）
    - 底部：加载更多 + 导出按钮

    Args:
        events: TimelineEvent列表
        title: 视图标题
    """
    if title is None:
        title = _t("timeline_title")

    if not events:
        st.info(_t("timeline_no_records"))
        return

    st.markdown(f"### 🕐 {title}")

    _render_timeline_stats(events)

    filtered_events, filters = _render_timeline_filters(events)

    if not filtered_events:
        st.warning(_t("timeline_no_matching_events"))
        return

    group_by = filters.get("group_by", "hour")
    grouped = _group_events_by_time(filtered_events, group_by)

    _inject_timeline_css()

    container = st.container()

    with container:
        for group_label, group_events in grouped.items():
            st.markdown(f"#### 📅 {group_label}")

            for i, event in enumerate(group_events):
                is_latest = i == 0 and group_label == list(grouped.keys())[0]
                _render_timeline_event(event, is_latest)

            st.markdown("---")

    if len(filtered_events) < len(events):
        col_load, col_info = st.columns([1, 3])
        with col_load:
            if st.button(_t("timeline_load_more"), key="load_more_timeline"):
                st.session_state.timeline_limit = (
                    st.session_state.get("timeline_limit", 50) + 50
                )
                st.rerun()
        with col_info:
            st.caption(
                _t(
                    "timeline_showing_count",
                    shown=len(filtered_events),
                    total=len(events),
                )
            )

    _render_export_section(events)


def _render_timeline_event(event: TimelineEvent, is_latest: bool = False):
    """渲染单个时间线事件节点

    根据event_type和status渲染不同样式：
    - 成功：绿色圆点 + 实线连接
    - 错误：红色圆点 + 虚线连接
    - 撤销：灰色圆点 + 删除线样式
    - 待确认：黄色闪烁效果

    UI结构：
    ┌─────────────────────────────────────┐
    │ 14:30  ✅ ───────●                  │
    │        │  标题                       │
    │        │  描述 | 耗时 | 元数据       │
    │        │  [展开详情]                 │
    └─────────────────────────────────────┘

    Args:
        event: TimelineEvent实例
        is_latest: 是否为最新事件（特殊标记）
    """
    config = EVENT_TYPE_CONFIG.get(event.event_type, {})
    color = config.get("color", "#6B7280")
    status_labels = _get_status_labels()
    category_labels = _get_category_labels()

    try:
        time_str = datetime.fromtimestamp(event.timestamp).strftime("%H:%M")
    except (ValueError, OSError):
        time_str = "--:--"

    status_badge = status_labels.get(event.status, event.status)
    cat_badge = category_labels.get(event.category, event.category)

    line_style = "solid"
    opacity = "1"

    if event.status == "error":
        line_style = "dashed"
    elif event.status in ("undone", "cancelled"):
        opacity = "0.6"

    container_key = f"timeline_event_{event.id}"

    with st.container():
        col_time, col_content = st.columns([1, 5])

        with col_time:
            st.markdown(
                f"<div style='text-align:right; font-family:monospace; color:#6B7280; font-size:14px; padding-top:8px;'>{time_str}</div>",
                unsafe_allow_html=True,
            )

        with col_content:
            latest_badge = (
                f'<div style="position:absolute;top:-8px;right:-8px;background:#10B981;color:white;font-size:10px;padding:2px 6px;border-radius:10px;">{_t("timeline_latest")}</div>'
                if is_latest
                else ""
            )
            event_html = f"""
            <div style="
                display: flex;
                align-items: flex-start;
                gap: 12px;
                margin-bottom: 16px;
                opacity: {opacity};
            ">
                <div style="
                    font-size: 24px;
                    min-width: 32px;
                    text-align: center;
                    line-height: 1;
                ">{event.icon}</div>

                <div style="
                    flex: 1;
                    background: white;
                    border-radius: 8px;
                    padding: 12px 16px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                    border-left: 3px solid {color};
                    position: relative;
                ">
                    {latest_badge}

                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                        <strong style="font-size:15px;color:#1F2937;">{_escape_html(event.title)}</strong>
                        {f'<span style="font-size:11px;background:{color};color:white;padding:2px 8px;border-radius:10px;">{status_badge}</span>' if event.status != 'success' else ''}
                    </div>

                    <div style="font-size:13px;color:#6B7280;margin-bottom:8px;">
                        {_escape_html(event.description)}
                    </div>

                    <div style="display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:#9CA3AF;">
                        <span>📁 {cat_badge}</span>
                        {f'<span>⏱️ {event.duration_ms:.1f}s</span>' if event.duration_ms > 0 else ''}
                        {f'<span>🔗 {_t("timeline_related_count", count=len(event.related_ids))}</span>' if event.related_ids else ''}
                    </div>
                </div>
            </div>
            """

            st.markdown(event_html, unsafe_allow_html=True)

            with st.expander(_t("timeline_view_detail"), expanded=False):
                _render_event_detail_panel(event)


def _render_event_detail_panel(event: TimelineEvent):
    """渲染事件详情面板

    显示完整的元数据和相关信息：
    - 执行耗时
    - 文件路径（如有）
    - 收件人/金额（如有）
    - 相关操作链接
    - 错误详情（如有）
    """
    import os

    category_labels = _get_category_labels()
    status_labels = _get_status_labels()

    col_meta, col_actions = st.columns([2, 1])

    with col_meta:
        st.markdown(f"**{_t('timeline_basic_info')}**")
        meta_data = {
            _t("timeline_event_id"): (
                event.id[:16] + "..." if len(event.id) > 16 else event.id
            ),
            _t("timeline_event_type"): event.event_type,
            _t("timeline_category"): category_labels.get(
                event.category, event.category
            ),
            _t("timeline_status"): status_labels.get(event.status, event.status),
            _t("timeline_timestamp"): datetime.fromtimestamp(event.timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            _t("timeline_duration"): (
                _t("timeline_duration_sec", sec=event.duration_ms)
                if event.duration_ms > 0
                else "-"
            ),
        }

        for label, value in meta_data.items():
            st.markdown(f"- **{label}**: `{value}`")

        if event.metadata:
            st.markdown(f"**{_t('timeline_metadata')}**")
            st.json(event.metadata)

    with col_actions:
        st.markdown(f"**{_t('timeline_quick_actions')}**")

        filepath = event.metadata.get("filepath", "")
        if filepath and os.path.exists(filepath):
            if st.button(_t("timeline_open_file"), key=f"open_file_{event.id}"):
                st.info(_t("timeline_file_path", path=filepath))

        if event.related_ids:
            if st.button(_t("timeline_view_related"), key=f"related_{event.id}"):
                st.session_state.selected_related_ids = event.related_ids
                st.rerun()

        if event.status == "error" and event.metadata.get("detail"):
            st.markdown(f"**{_t('timeline_error_detail')}**")
            detail = event.metadata["detail"]
            if isinstance(detail, dict):
                st.json(detail)
            else:
                st.error(str(detail))


def _inject_timeline_css():
    """注入时间线专用CSS样式"""
    st.markdown(
        """
    <style>
    .timeline-container {
        position: relative;
        padding-left: 20px;
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .timeline-event-card {
        animation: fadeIn 0.3s ease-out forwards;
    }

    @media (max-width: 768px) {
        .timeline-mobile-time {
            text-align: left !important;
            margin-bottom: 4px;
            font-size: 12px !important;
        }

        .timeline-event-card {
            width: 100% !important;
            padding: 8px !important;
        }
    }
    </style>
    """,
        unsafe_allow_html=True,
    )
