"""Shared UI components and utilities for OPC-Agents frontend.

Extracted from monolithic app.py to enable modular page/component architecture.
Contains export helpers, progress indicators, undo panel, theme/language selectors,
and other reusable UI components.
"""

import streamlit as st
import time
import logging

from opc_manager.i18n import t as _t

from frontend.components.session_utils import (
    _get_undo_manager,
    _get_current_session_id,
)
from frontend.components.export_helpers import (
    _get_export_bytes,
    _do_get_export_bytes,
    _get_mime_type,
    _render_batch_export_section,
    _execute_batch_export,
    _render_single_export_buttons,
    _render_export_preview,
    _export_single_with_preview,
    _export_single,
    _render_export_buttons,
)
from frontend.components.progress_indicator import (
    _event_type_label,
    _get_phase_from_event,
    _event_emoji,
    _render_progress_indicator,
    _get_phase_icon,
    _render_timeline,
    _auto_refresh_progress,
)
from frontend.components.toast_notifications import (
    show_success,
    show_error,
    show_info,
)
from frontend.components.theme_manager import (
    THEME_CONFIGS,
    apply_theme,
    _get_theme_css,
)

__all__ = [
    # session_utils
    "_get_undo_manager",
    "_get_current_session_id",
    # export_helpers
    "_get_export_bytes",
    "_do_get_export_bytes",
    "_get_mime_type",
    "_render_batch_export_section",
    "_execute_batch_export",
    "_render_single_export_buttons",
    "_render_export_preview",
    "_export_single_with_preview",
    "_export_single",
    "_render_export_buttons",
    # progress_indicator
    "_event_type_label",
    "_get_phase_from_event",
    "_event_emoji",
    "_render_progress_indicator",
    "_get_phase_icon",
    "_render_timeline",
    "_auto_refresh_progress",
    # toast_notifications
    "show_success",
    "show_error",
    "show_info",
    # theme_manager
    "THEME_CONFIGS",
    "apply_theme",
    "_get_theme_css",
]

logger = logging.getLogger(__name__)


@st.cache_data(ttl=5)
def _cached_list_undoable(session_id: str) -> list:
    """Cached version of list_undoable to avoid repeated calls.

    Args:
        session_id: Current session identifier

    Returns:
        List of undoable operation records
    """
    um = _get_undo_manager()
    if not um:
        return []
    try:
        return um.list_undoable(session_id)
    except Exception as e:
        logger.warning("[frontend] list_undoable error: %s", e)
        return []


def _render_undo_panel():
    """Render the Undo operation panel in sidebar.

    Displays a collapsible panel showing all undoable operations
    for the current session with action buttons and status indicators.
    """
    um = _get_undo_manager()
    if not um:
        return

    st.divider()

    if st.button(
        "↩️ " + _t("undo_operations"),
        use_container_width=True,
        help=_t("undo_operations_help"),
    ):
        st.session_state.show_undo = not st.session_state.get("show_undo", False)

    if st.session_state.get("show_undo", False):
        st.markdown("#### ↩️ " + _t("undoable_operations"))

        session_id = _get_current_session_id()
        if not session_id:
            st.warning("⚠️ " + _t("cannot_get_session_id"))
            return

        undoable = _cached_list_undoable(session_id)

        if not undoable:
            st.info(_t("no_undoable_operations"))
            return

        st.caption(_t("total_undoable_count", count=len(undoable)))

        for record in undoable[-10:]:
            op_type = record.get("operation_type", "unknown")
            created_at = record.get("created_at", "")
            op_id = record.get("operation_id", "")

            can_undo, reason = um.can_undo(session_id, op_id)

            with st.expander(f"↩️ {op_type} — {created_at}"):
                col_info, col_action = st.columns([3, 1])

                with col_info:
                    st.json(
                        {
                            _t("type"): op_type,
                            _t("time"): created_at,
                            _t("status"): (
                                _t("can_undo")
                                if can_undo
                                else f"{_t('cannot_undo')}: {reason}"
                            ),
                            "ID": op_id[:12] if op_id else "",
                        }
                    )

                with col_action:
                    if can_undo:
                        confirmed = st.checkbox(
                            _t("confirm_undo"),
                            key=f"undo_confirm_{op_id}",
                            help=_t("confirm_undo_help"),
                        )

                        if confirmed:
                            if st.button(
                                _t("undo"),
                                key=f"undo_{op_id}",
                                type="secondary",
                                help=_t("undo_warning"),
                            ):
                                with st.spinner(_t("undoing")):
                                    result = um.undo(session_id, op_id)
                                    if result.get("success"):
                                        st.success(
                                            f"✅ {_t('undo_success', msg=result.get('message', ''))}"
                                        )
                                        st.toast("操作已撤销", icon="✅")
                                        _cached_list_undoable.clear()
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error(
                                            f"❌ {_t('undo_failed', error=result.get('error', _t('unknown_error')))}"
                                        )
                    else:
                        st.caption(f"❌ {reason}")

                        expires_at = record.get("expires_at", 0)
                        if expires_at and not can_undo:
                            remaining = max(0, expires_at - time.time())
                            if remaining > 0:
                                mins, secs = divmod(int(remaining), 60)
                                st.caption(
                                    f"⏰ {_t('remaining_time', mins=mins, secs=secs)}"
                                )
                            else:
                                st.caption("⏰ " + _t("undo_window_expired"))


def _render_theme_selector():
    """Render theme selector in sidebar."""
    from opc_manager.i18n import t as _t

    themes = {
        "light": _t("theme_light"),
        "dark": _t("theme_dark"),
        "sunset": _t("theme_sunset"),
        "forest": _t("theme_forest"),
        "ocean": _t("theme_ocean"),
    }

    current = st.session_state.get("theme", "light")
    selected = st.selectbox(
        _t("theme_label"),
        options=list(themes.keys()),
        format_func=lambda x: themes[x],
        index=list(themes.keys()).index(current) if current in themes else 0,
        key="theme_selector",
    )

    if selected != current:
        st.session_state.theme = selected
        apply_theme(selected)


def _render_language_selector():
    """Render language selector in sidebar."""
    from opc_manager.i18n import get_i18n, t as _t

    i18n = get_i18n()
    locales = i18n.get_available_locales()
    current = i18n.locale
    selected = st.selectbox(
        _t("lang_selector"),
        options=[l["code"] for l in locales],
        format_func=lambda x: next(l["name"] for l in locales if l["code"] == x),
        index=[l["code"] for l in locales].index(current),
        key="lang_selector",
    )
    if selected != current:
        i18n.locale = selected
        st.rerun()


def _render_shortcuts_help():
    """Render operation tips help panel (shortcuts that actually work in Streamlit)."""
    from opc_manager.i18n import t as _t

    with st.expander(_t("tips_title")):
        tips = [
            ("Enter", _t("shortcut_send")),
            ("Esc", _t("shortcut_cancel")),
            ("/", _t("tip_slash_command")),
        ]
        for keys, desc in tips:
            st.code(f"{keys:12s} → {desc}")
        st.caption(_t("tips_hint"))


def _maybe_show_shortcut_hints():
    """Show operation tips hint bubble on first visit to chat page."""
    from opc_manager.i18n import t as _t

    if "shortcuts_shown" not in st.session_state:
        st.session_state.shortcuts_shown = False

    if not st.session_state.shortcuts_shown:
        with st.expander(_t("tips_title"), expanded=True):
            st.markdown(f"""
            | {_t('tips_title')} | |
            |--------|------|
            | `Enter` | {_t('shortcut_send')} |
            | `Esc` | {_t('shortcut_cancel')} |
            | `/` | {_t('tip_slash_command')} |

            {_t('tips_hint')}
            """)

        col_dismiss, col_later = st.columns([1, 1])
        with col_dismiss:
            if st.button(_t("shortcut_dismiss_btn"), key="dismiss_shortcuts"):
                st.session_state.shortcuts_shown = True
                st.rerun()
        with col_later:
            if st.button(_t("shortcut_later_btn"), key="shortcuts_later"):
                st.session_state.shortcuts_shown = True


def _render_floating_help_button():
    """Render a small floating '?' button that re-shows shortcut hints."""
    st.markdown(
        """
    <div style="
        position: fixed;
        bottom: 80px;
        right: 24px;
        z-index: 998;
    >
    </div>
    """,
        unsafe_allow_html=True,
    )
    if st.button(
        _t("floating_help_btn"), key="floating_help_btn", help=_t("floating_help_desc")
    ):
        st.session_state.shortcuts_shown = False
        st.rerun()


def _render_quick_undo_button(task_id: str, operation_type: str = None):
    """Render a quick undo button in chat response area.

    Args:
        task_id: Unique identifier for the task/operation
        operation_type: Type of operation (optional, for display)
    """
    um = _get_undo_manager()
    if not um:
        return

    session_id = _get_current_session_id()
    if not session_id:
        return

    try:
        undoable = um.list_undoable(session_id)
        if not undoable:
            return

        last_record = undoable[-1] if undoable else None
        if not last_record:
            return

        op_id = last_record.get("operation_id", "")
        can_undo, reason = um.can_undo(session_id, op_id)

        if not can_undo:
            return

        st.divider()

        col_undo, col_space = st.columns([1, 4])
        with col_undo:
            label = f"↩️ {_t('undo_last_step', op=operation_type or last_record.get('operation_type', _t('operation'))) }"

            if st.button(label, key=f"quick_undo_{task_id}", type="secondary"):
                confirmed = st.checkbox(
                    "✅ " + _t("confirm_undo_this_operation"),
                    key=f"quick_undo_confirm_{task_id}",
                    help=_t("undo_destructive_help"),
                )

                if confirmed:
                    with st.spinner(_t("undoing")):
                        result = um.undo(session_id, op_id)
                        if result.get("success"):
                            st.success(
                                f"✅ {_t('undo_success', msg=result.get('message', ''))}"
                            )
                            st.toast("操作已撤销", icon="✅")
                            _cached_list_undoable.clear()
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(
                                f"❌ {_t('undo_failed', error=result.get('error', _t('unknown_error')))}"
                            )

    except Exception as e:
        logger.warning("[frontend] Quick undo button error: %s", e)
