"""Progress indicator components for OPC-Agents frontend.

Provides progress visualization utilities extracted from shared.py:
- _event_type_label: Map event types to localized labels
- _get_phase_from_event: Map event types to phase icons/labels
- _event_emoji: Map event types to emoji icons
- _render_progress_indicator: SSE-based real-time progress display
- _get_phase_icon: Enhanced phase icon mapping
- _render_timeline: Phase timeline visualization
- _auto_refresh_progress: Auto-refresh mechanism for progress updates
"""

import streamlit as st
import logging
from datetime import datetime

from opc_manager.i18n import t as _t

logger = logging.getLogger(__name__)

__all__ = [
    "_event_type_label",
    "_get_phase_from_event",
    "_event_emoji",
    "_render_progress_indicator",
    "_get_phase_icon",
    "_render_timeline",
    "_auto_refresh_progress",
]

EVENT_TYPE_CONFIG = {
    "PLAN_START": {
        "label": _t("event_plan_start"),
        "phase": "planning",
        "emoji": "",
    },
    "INTENT_DETECTED": {
        "label": _t("event_intent_detected"),
        "phase": "intent",
        "emoji": "",
    },
    "CONFIRM_REQUESTED": {
        "label": _t("event_confirm_requested"),
        "phase": "confirm",
        "emoji": "",
    },
    "CONFIRMED": {
        "label": _t("event_confirmed"),
        "phase": "confirm",
        "emoji": "",
    },
    "STEP_START": {
        "label": _t("event_step_start"),
        "phase": "executing",
        "emoji": "",
    },
    "STEP_PROGRESS": {
        "label": _t("event_step_progress"),
        "phase": "executing",
        "emoji": "",
    },
    "STEP_COMPLETE": {
        "label": _t("event_step_complete"),
        "phase": "executing",
        "emoji": "",
    },
    "COLLAB_START": {
        "label": _t("event_collab_start"),
        "phase": "collab",
        "emoji": "",
    },
    "REFLECT_START": {
        "label": _t("event_reflect_start"),
        "phase": "reflect",
        "emoji": "",
    },
    "COMPLETE": {
        "label": _t("event_complete"),
        "phase": "complete",
        "emoji": "",
    },
    "ERROR": {
        "label": _t("event_error"),
        "phase": "error",
        "emoji": "",
    },
    "CANCELLED": {
        "label": _t("event_cancelled"),
        "phase": "cancelled",
        "emoji": "",
    },
}


def _event_type_label(event_type: str) -> str:
    cfg = EVENT_TYPE_CONFIG.get(
        event_type, EVENT_TYPE_CONFIG.get(event_type.upper(), {})
    )
    return cfg.get("label", event_type.replace("_", " ").title())


def _get_phase_from_event(event_type: str) -> tuple:
    cfg = EVENT_TYPE_CONFIG.get(
        event_type, EVENT_TYPE_CONFIG.get(event_type.upper(), {})
    )
    phase = cfg.get("phase", "unknown")
    phase_labels = {
        "planning": ("", _t("phase_task_start")),
        "intent": ("", _t("phase_intent_detected")),
        "executing": ("", _t("phase_executing")),
        "complete": ("", _t("phase_task_complete")),
        "error": ("", _t("phase_exec_error")),
        "cancelled": ("", _t("event_cancelled")),
    }
    return phase_labels.get(phase, ("", _t("phase_executing")))


def _event_emoji(event_type: str) -> str:
    cfg = EVENT_TYPE_CONFIG.get(
        event_type, EVENT_TYPE_CONFIG.get(event_type.upper(), {})
    )
    return cfg.get("emoji", "")


def _render_progress_indicator(session_id: str):
    """渲染基于SSE的实时进度指示器（增强版）

    显示功能：
    - 动画进度条，通过Server-Sent Events更新
    - 阶段图标映射（PLAN_START→, INTENT_DETECTED→等）
    - 阶段时间线可视化
    - 错误状态特殊样式（红色高亮）
    - 如果SSE不可用则回退到静态进度显示
    """
    try:
        from opc_manager.progress_emitter import (
            get_progress_emitter,
        )
    except ImportError:
        return

    try:
        emitter = get_progress_emitter()
        history = emitter.get_history(session_id)
    except Exception as e:
        logger.debug("[frontend] 获取进度历史失败: %s", e)
        return

    if not history:
        return

    latest = history[-1]
    event_type = latest.get("event", latest.get("event_type", ""))
    progress_pct = latest.get("progress", latest.get("progress_pct", 0))
    message = latest.get("message", "")
    is_error = event_type in ("error", "ERROR")

    phase_icon = _get_phase_icon(event_type)
    status_label = _event_type_label(event_type)

    if is_error:
        st.markdown(f"#### {phase_icon} {_t('current_status')} :red[{status_label}]")
    else:
        st.markdown(f"#### {phase_icon} {_t('current_status')}: {status_label}")

    "error" if is_error else None
    st.progress(min(progress_pct / 100.0, 1.0))

    cols_info = st.columns(3)
    with cols_info[0]:
        if is_error:
            st.metric(_t("progress"), f":red[{progress_pct}%]")
        else:
            st.metric(_t("progress"), f"{progress_pct}%")
    with cols_info[1]:
        stage_name = event_type.replace("_", " ").title() if event_type else "-"
        st.metric(_t("stage"), stage_name)
    with cols_info[2]:
        display_msg = message[:50] + "..." if len(message) > 50 else (message or "-")
        if is_error:
            st.metric(_t("message"), f":red[{display_msg}]")
        else:
            st.metric(_t("message"), display_msg)

    if len(history) > 1:
        st.markdown("---")
        st.markdown(f"** {_t('execution_timeline')}**")

        _render_timeline(history)

        with st.expander(" " + _t("operation_log_details"), expanded=False):
            for evt in reversed(history[-10:]):
                etype = evt.get("event", evt.get("event_type", "UNKNOWN"))
                epct = evt.get("progress", evt.get("progress_pct", 0))
                emsg = evt.get("message", "")
                etime = evt.get("timestamp", "")
                emoji = _event_emoji(etype)
                evt_is_error = etype in ("error", "ERROR")

                if etime:
                    try:
                        time_str = datetime.fromtimestamp(etime).strftime("%H:%M:%S")
                    except (TypeError, ValueError):
                        time_str = str(etime)
                else:
                    time_str = ""

                if evt_is_error:
                    st.markdown(
                        f"{emoji} `{time_str}` :red[**{etype}**] ({epct}%) - :red[{emsg}]"
                    )
                else:
                    st.markdown(f"{emoji} `{time_str}` **{etype}** ({epct}%) - {emsg}")


def _get_phase_icon(event_type: str) -> str:
    """获取阶段对应的增强图标

    Args:
        event_type: 事件类型字符串

    Returns:
        对应的emoji图标
    """
    icon_mapping = {
        "plan_start": "",
        "intent_detected": "",
        "confirm_requested": "",
        "confirmed": "",
        "step_start": "",
        "step_progress": "",
        "step_complete": "",
        "complete": "",
        "error": "",
        "cancelled": "",
    }
    event_key = event_type.lower().replace("-", "_")
    return icon_mapping.get(event_key, "")


def _render_timeline(history: list):
    timeline_phases = [
        ("plan_start", " " + _t("timeline_plan_start")),
        ("intent_detected", " " + _t("timeline_intent_detected")),
        ("step_start", " " + _t("timeline_step_start")),
        ("step_complete", " " + _t("event_step_complete")),
        ("complete", " " + _t("timeline_task_complete")),
    ]

    completed_phases = set()
    current_phase_idx = 0

    for i, evt in enumerate(history):
        etype = evt.get("event", evt.get("event_type", "")).lower().replace("-", "_")
        completed_phases.add(etype)
        if etype in [p[0] for p in timeline_phases]:
            phase_names = [p[0] for p in timeline_phases]
            if etype in phase_names:
                current_phase_idx = max(current_phase_idx, phase_names.index(etype))

    cols = st.columns(len(timeline_phases))
    for idx, (phase_key, phase_label) in enumerate(timeline_phases):
        with cols[idx]:
            is_completed = phase_key in completed_phases
            is_current = (idx == current_phase_idx) and not is_completed

            if is_completed:
                st.success(phase_label)
            elif is_current:
                st.info(phase_label)
            else:
                st.caption(f"~~{phase_label}~~")


def _auto_refresh_progress(session_id: str, interval_sec: int = 2):
    """为进度更新添加自动刷新机制

    注意：Streamlit不支持真正的推送更新。
    此函数使用st.empty() + 刷新按钮模式作为变通方案。
    """
    placeholder = st.empty()

    with placeholder.container():
        _render_progress_indicator(session_id)

    col_refresh, col_close = st.columns([1, 3])
    with col_refresh:
        if st.button(" " + _t("refresh_progress"), key="refresh_prog"):
            st.rerun()
    with col_close:
        st.caption(_t("click_refresh_hint"))
