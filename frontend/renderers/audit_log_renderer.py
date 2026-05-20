"""Audit log page renderer — extracted from app.py to fix NameError ordering bugs."""

import streamlit as st
import time as _time
import logging
from datetime import datetime

from opc_manager.i18n import t as _t
from opc_manager.error_handler import ErrorHandler

logger = logging.getLogger(__name__)


def _render_audit_log_page():
    """Render the Audit Log viewer page."""
    try:
        from opc_manager.audit_log import AuditLog

        audit_log = AuditLog()

        st.markdown(_t("audit_title"))

        stats = audit_log.get_stats()
        total_ops = stats.get("total", 0)
        success_rate = stats.get("success_rate", "0%")
        avg_duration = stats.get("avg_duration_ms", 0)

        col_total, col_success, col_avg = st.columns(3)
        with col_total:
            st.metric(_t("audit_total_ops"), total_ops)
        with col_success:
            st.metric(_t("audit_success_rate"), success_rate)
        with col_avg:
            st.metric(
                _t("audit_avg_duration"), _t("audit_duration_ms", ms=avg_duration)
            )

        if total_ops == 0:
            st.info(_t("audit_empty"))
            return

        st.divider()

        filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([2, 2, 2, 2])

        with filter_col1:
            op_types = [_t("audit_time_all")] + list(
                set(
                    r.get("operation_type", "")
                    for r in audit_log.query(limit=200)
                    if r.get("operation_type")
                )
            )
            selected_type = st.selectbox(
                _t("audit_op_type"),
                op_types,
                key="audit_op_type",
                help=_t("audit_op_type"),
            )

        with filter_col2:
            status_options = [_t("audit_time_all"), "success", "failed", "cancelled"]
            selected_status = st.selectbox(
                _t("audit_status"),
                status_options,
                key="audit_status",
                help=_t("audit_status"),
            )

        with filter_col3:
            session_search = st.text_input(
                label=_t("audit_session_id"),
                placeholder=_t("audit_session_placeholder"),
                key="audit_session_search",
                help=_t("audit_session_help"),
            )

        with filter_col4:
            time_range_options = [
                _t("audit_time_all"),
                _t("audit_time_today"),
                _t("audit_time_7d"),
                _t("audit_time_30d"),
            ]
            selected_time_range = st.selectbox(
                _t("audit_time_range"),
                time_range_options,
                key="audit_time_range",
                help=_t("audit_time_range"),
            )

        since_timestamp = None
        if selected_time_range == _t("audit_time_today"):
            since_timestamp = _time.time() - 86400
        elif selected_time_range == _t("audit_time_7d"):
            since_timestamp = _time.time() - 7 * 86400
        elif selected_time_range == _t("audit_time_30d"):
            since_timestamp = _time.time() - 30 * 86400

        query_params = {
            "limit": 50,
            "since": since_timestamp,
        }
        if selected_type != _t("audit_time_all"):
            query_params["operation_type"] = selected_type
        if session_search.strip():
            query_params["session_id"] = session_search.strip()

        try:
            records = audit_log.query(**query_params)
        except Exception as e:
            logger.warning("[frontend] 审计日志查询失败: %s", e)
            st.error(_t("audit_query_failed"))
            return

        if selected_status != _t("audit_time_all"):
            records = [r for r in records if r.get("status") == selected_status]

        filtered_flag = (
            selected_type != _t("audit_time_all")
            or selected_status != _t("audit_time_all")
            or session_search
            or selected_time_range != _t("audit_time_all")
        )
        st.caption(
            _t("audit_showing", count=len(records))
            + (_t("audit_filtered") if filtered_flag else "")
        )

        if not records:
            st.info(_t("audit_no_match"))
            return

        for idx, record in enumerate(records):
            timestamp_str = datetime.fromtimestamp(record.get("timestamp", 0)).strftime(
                "%H:%M:%S"
            )
            op_type = record.get("operation_type", "unknown")
            skill_id = record.get("skill_id", "unknown")
            status = record.get("status", "unknown")
            duration = record.get("duration_ms", 0)
            session_id = record.get("id", "")[:12]
            input_summary = record.get("input_summary", "")
            output_summary = record.get("output_summary", "")

            status_emoji = {
                "success": "✅",
                "failed": "❌",
                "cancelled": "⚪",
            }.get(status, "❓")

            status_color = {
                "success": "green",
                "failed": "red",
                "cancelled": "gray",
            }.get(status, "gray")

            with st.expander(
                f"{status_emoji} **{op_type}** | {skill_id} | {timestamp_str} ({duration}ms)",
                expanded=(idx == 0),
            ):
                col_meta, col_detail = st.columns([1, 2])

                with col_meta:
                    st.markdown(
                        f"**{_t('audit_status_label')}**: :{status_color}[{status.upper()}]"
                    )
                    st.markdown(f"**{_t('audit_session_label')}**: `{session_id}`")
                    st.markdown(f"**{_t('audit_duration_label')}**: {duration}ms")
                    st.markdown(f"**{_t('audit_skill_label')}**: `{skill_id}`")

                with col_detail:
                    if input_summary:
                        st.markdown(_t("audit_input_summary") + ":")
                        st.text(input_summary[:200])
                    if output_summary:
                        st.markdown(_t("audit_output_summary") + ":")
                        st.text(output_summary[:300])

        if len(records) >= 50:
            if st.button(_t("audit_load_more"), key="audit_load_more"):
                st.info(_t("audit_max_records"))

    except ImportError:
        st.warning(_t("audit_module_not_ready"))
    except Exception as e:
        friendly_error = ErrorHandler.translate(e, context=_t("audit_load_context"))
        st.error(friendly_error.user_message)
        if friendly_error.suggestion:
            st.info(friendly_error.suggestion)
        logger.error("[frontend] 操作日志页面错误: %s", friendly_error.traceback_str)
