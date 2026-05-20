"""Timeline filter and grouping components for OPC-Agents frontend.

Provides filtering, grouping, and statistics for timeline events,
extracted from timeline_view.py:
- _render_timeline_filters: Filter control panel UI
- _apply_filters: Apply filter criteria to event list
- _group_events_by_time: Group events by hour or day
- _render_timeline_stats: Statistics summary dashboard
"""

import streamlit as st
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from collections import defaultdict

from opc_manager.i18n import t as _t

from frontend.components.timeline_data import (
    TimelineEvent,
    _get_category_labels,
    _get_status_labels,
)

logger = logging.getLogger(__name__)

__all__ = [
    "_render_timeline_filters",
    "_apply_filters",
    "_group_events_by_time",
    "_render_timeline_stats",
]


def _render_timeline_stats(events: List[TimelineEvent]):
    """渲染时间线顶部统计摘要

    显示：
    - 总操作数
    - 各状态计数（成功/错误/撤销/待确认）
    - 总工作时长估算
    - 最活跃时段
    """
    total = len(events)
    success_count = sum(1 for e in events if e.status == "success")
    error_count = sum(1 for e in events if e.status == "error")
    undone_count = sum(1 for e in events if e.status in ("undone", "cancelled"))

    total_duration = sum(e.duration_ms for e in events if e.duration_ms > 0)
    duration_min = total_duration / 60000 if total_duration > 0 else 0

    hour_counts = defaultdict(int)
    for e in events:
        try:
            dt = datetime.fromtimestamp(e.timestamp)
            hour_counts[dt.hour] += 1
        except (ValueError, OSError):
            pass

    peak_hour = max(hour_counts.items(), key=lambda x: x[1])[0] if hour_counts else 0
    peak_range = f"{peak_hour:02d}:00-{(peak_hour+1)%24:02d}:00"

    cols = st.columns(5)
    with cols[0]:
        st.metric(_t("timeline_total_ops"), _t("timeline_times", count=total))
    with cols[1]:
        st.metric(
            _t("timeline_status_success"), f"{success_count}", delta_color="normal"
        )
    with cols[2]:
        if error_count > 0:
            st.metric(
                _t("timeline_status_error"), f"{error_count}", delta_color="inverse"
            )
        else:
            st.metric(_t("timeline_status_error"), "0")
    with cols[3]:
        st.metric(_t("timeline_undone_cancelled"), f"{undone_count}")
    with cols[4]:
        if duration_min > 0:
            st.metric(
                _t("timeline_work_duration"), _t("timeline_minutes", min=duration_min)
            )
        else:
            st.metric(_t("timeline_work_duration"), "-")

    if total > 0:
        st.caption(
            _t(
                "timeline_peak_period",
                range=peak_range,
                rate=success_count / total * 100,
            )
        )


def _render_timeline_filters(
    events: List[TimelineEvent],
) -> Tuple[List[TimelineEvent], Dict]:
    """渲染筛选控制面板

    提供：
    - 时间范围选择（今天/本周/本月/全部）
    - 类别筛选（复选框）
    - 状态筛选（复选框）
    - 关键词搜索

    Returns:
        (过滤后的事件列表, 当前筛选参数字典)
    """
    category_labels = _get_category_labels()
    status_labels = _get_status_labels()

    with st.expander(_t("timeline_filter_search"), expanded=False):

        col_time, col_search = st.columns([1, 1])

        with col_time:
            time_range = st.selectbox(
                _t("timeline_time_range"),
                options=["all", "today", "week", "month"],
                format_func=lambda x: {
                    "all": _t("timeline_time_all"),
                    "today": _t("timeline_today"),
                    "week": _t("timeline_this_week"),
                    "month": _t("timeline_this_month"),
                }.get(x, x),
                key="timeline_time_range",
            )

        with col_search:
            keyword = st.text_input(
                _t("timeline_keyword_search"),
                placeholder=_t("timeline_search_placeholder"),
                key="timeline_keyword",
            )

        col_cat, col_status = st.columns(2)

        with col_cat:
            categories = st.multiselect(
                _t("timeline_event_category"),
                options=list(category_labels.keys()),
                format_func=lambda x: category_labels.get(x, x),
                default=list(category_labels.keys()),
                key="timeline_categories",
            )

        with col_status:
            statuses = st.multiselect(
                _t("timeline_event_status"),
                options=list(status_labels.keys()),
                format_func=lambda x: status_labels.get(x, x),
                default=list(status_labels.keys()),
                key="timeline_statuses",
            )

        group_by = st.selectbox(
            _t("timeline_group_by"),
            options=["hour", "day"],
            format_func=lambda x: {
                "hour": _t("timeline_group_by_hour"),
                "day": _t("timeline_group_by_day"),
            }.get(x, x),
            index=0,
            key="timeline_group_by",
        )

    filters = {
        "time_range": time_range,
        "keyword": keyword,
        "categories": categories,
        "statuses": statuses,
        "group_by": group_by,
    }

    filtered = _apply_filters(events, filters)

    return filtered, filters


def _apply_filters(events: List[TimelineEvent], filters: Dict) -> List[TimelineEvent]:
    """应用筛选条件到事件列表

    Args:
        events: 原始事件列表
        filters: 筛选参数字典

    Returns:
        过滤后的事件列表
    """
    category_labels = _get_category_labels()
    status_labels = _get_status_labels()
    result = events.copy()

    time_range = filters.get("time_range", "all")
    now = datetime.now()

    if time_range == "today":
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        result = [e for e in result if e.timestamp >= today_start]

    elif time_range == "week":
        week_start = (
            (now - timedelta(days=now.weekday()))
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .timestamp()
        )
        result = [e for e in result if e.timestamp >= week_start]

    elif time_range == "month":
        month_start = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ).timestamp()
        result = [e for e in result if e.timestamp >= month_start]

    keyword = filters.get("keyword", "").strip()
    if keyword:
        keyword_lower = keyword.lower()
        result = [
            e
            for e in result
            if keyword_lower in e.title.lower()
            or keyword_lower in e.description.lower()
        ]

    categories = filters.get("categories", [])
    if categories and set(categories) != set(category_labels.keys()):
        result = [e for e in result if e.category in categories]

    statuses = filters.get("statuses", [])
    if statuses and set(statuses) != set(status_labels.keys()):
        result = [e for e in result if e.status in statuses]

    limit = st.session_state.get("timeline_limit", 50)
    if len(result) > limit:
        result = result[:limit]

    return result


def _group_events_by_time(
    events: List[TimelineEvent], group_by: str = "hour"
) -> Dict[str, List[TimelineEvent]]:
    """按时间分组事件

    Args:
        events: 事件列表
        group_by: 分组方式（"hour"/"day"）

    Returns:
        分组后的字典 {组标签: 事件列表}
    """
    groups = defaultdict(list)
    now = datetime.now()

    for event in events:
        try:
            dt = datetime.fromtimestamp(event.timestamp)
        except (ValueError, OSError):
            dt = now

        if group_by == "hour":
            if dt.date() == now.date():
                label = _t("timeline_today_label", time=dt.strftime("%H:%M"))
            elif dt.date() == (now - timedelta(days=1)).date():
                label = _t("timeline_yesterday_label", time=dt.strftime("%H:%M"))
            else:
                label = dt.strftime("%m-%d %H:%M")

        elif group_by == "day":
            if dt.date() == now.date():
                label = _t("timeline_today")
            elif dt.date() == (now - timedelta(days=1)).date():
                label = _t("timeline_yesterday")
            elif (now - dt.date()).days <= 7:
                label = dt.strftime("%A")
            else:
                label = dt.strftime("%Y-%m-%d")
        else:
            label = dt.strftime("%Y-%m-%d %H:%M")

        groups[label].append(event)

    sorted_groups = dict(
        sorted(
            groups.items(), key=lambda x: x[1][0].timestamp if x[1] else 0, reverse=True
        )
    )
    return sorted_groups
