"""Timeline export functionality for OPC-Agents frontend.

Provides export capabilities for timeline data, extracted from timeline_view.py:
- _render_export_section: Export UI section
- export_timeline: Main export dispatcher
- _export_to_csv: CSV format export
- _export_to_markdown: Markdown report export
- _export_to_png: PNG image export (HTML+CSS rendering)
- _escape_html: HTML special character escaping
"""

import streamlit as st
import csv
import io
import logging
from datetime import datetime
from typing import List, Optional

from opc_manager.i18n import t as _t

from frontend.components.timeline_data import (
    TimelineEvent,
    EVENT_TYPE_CONFIG,
    _get_category_labels,
    _get_status_labels,
)

logger = logging.getLogger(__name__)

__all__ = [
    "_render_export_section",
    "export_timeline",
    "_export_to_csv",
    "_export_to_markdown",
    "_export_to_png",
    "_escape_html",
]


def _render_export_section(events: List[TimelineEvent]):
    """渲染导出功能区域

    支持3种导出格式：
    - PNG图片（HTML Canvas渲染）
    - CSV数据（电子表格友好）
    - Markdown报告（文字说明）
    """
    with st.expander(_t("timeline_export"), expanded=False):
        export_format = st.selectbox(
            _t("timeline_select_export_format"),
            options=["csv", "markdown"],
            format_func=lambda x: {
                "csv": _t("timeline_export_csv"),
                "markdown": _t("timeline_export_markdown"),
                "png": _t("timeline_export_png"),
            }.get(x, x.upper()),
            key="timeline_export_format",
        )

        if st.button(
            _t("timeline_export_btn"), key="export_timeline_btn", type="primary"
        ):
            exported = export_timeline(events, export_format)

            if exported:
                file_ext = {"csv": "csv", "markdown": "md", "png": "png"}.get(
                    export_format, "txt"
                )
                mime_types = {
                    "csv": "text/csv",
                    "markdown": "text/markdown",
                    "png": "image/png",
                }
                st.download_button(
                    label=_t("timeline_download_file", fmt=export_format.upper()),
                    data=exported,
                    file_name=f"timeline_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_ext}",
                    mime=mime_types.get(export_format, "application/octet-stream"),
                    key=f"dl_timeline_{export_format}",
                )


def export_timeline(
    events: List[TimelineEvent], format: str = "csv"
) -> Optional[bytes]:
    """导出时间线数据

    Args:
        events: TimelineEvent列表
        format: 导出格式（csv/markdown/png）

    Returns:
        导出的字节数据，如果失败返回None
    """
    if not events:
        st.warning(_t("timeline_no_export_data"))
        return None

    try:
        if format == "csv":
            return _export_to_csv(events)
        elif format == "markdown":
            return _export_to_markdown(events).encode("utf-8")
        elif format == "png":
            return _export_to_png(events)
        else:
            st.error(_t("timeline_unsupported_format", fmt=format))
            return None
    except Exception as e:
        logger.error("[timeline] export failed: %s", e)
        st.error(_t("timeline_export_failed", error=e))
        return None


def _export_to_csv(events: List[TimelineEvent]) -> bytes:
    """导出为CSV格式"""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(
        [
            _t("timeline_csv_header_timestamp"),
            _t("timeline_csv_header_time"),
            _t("timeline_csv_header_event_type"),
            _t("timeline_csv_header_title"),
            _t("timeline_csv_header_desc"),
            _t("timeline_csv_header_category"),
            _t("timeline_csv_header_status"),
            _t("timeline_csv_header_duration_ms"),
            _t("timeline_csv_header_icon"),
            _t("timeline_csv_header_event_id"),
        ]
    )

    for event in events:
        try:
            time_str = datetime.fromtimestamp(event.timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except (ValueError, OSError):
            time_str = ""

        writer.writerow(
            [
                event.timestamp,
                time_str,
                event.event_type,
                event.title,
                event.description,
                event.category,
                event.status,
                event.duration_ms,
                event.icon,
                event.id,
            ]
        )

    return output.getvalue().encode("utf-8-sig")


def _export_to_markdown(events: List[TimelineEvent]) -> str:
    """导出为Markdown格式的报告"""
    category_labels = _get_category_labels()
    status_labels = _get_status_labels()

    lines = []
    lines.append(f"{_t('timeline_md_report_title')}\n")
    lines.append(
        f"{_t('timeline_md_export_time')}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    lines.append(f"{_t('timeline_md_total_events')}: {len(events)}\n")
    lines.append("---\n")

    current_date = None
    for event in events:
        try:
            dt = datetime.fromtimestamp(event.timestamp)
            date_str = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%H:%M")
        except (ValueError, OSError):
            date_str = ""
            time_str = ""

        if date_str != current_date:
            current_date = date_str
            lines.append(f"\n## {date_str}\n")

        config = EVENT_TYPE_CONFIG.get(event.event_type, {})
        event_label = (
            _t(config["i18n_key"]) if "i18n_key" in config else event.event_type
        )
        lines.append(f"### {time_str} {event.icon} {event.title}\n")
        lines.append(f"- {_t('timeline_md_type')}: {event_label}\n")
        lines.append(f"- {_t('timeline_md_desc')}: {event.description}\n")
        lines.append(
            f"- {_t('timeline_md_category')}: {category_labels.get(event.category, event.category)}\n"
        )
        lines.append(
            f"- {_t('timeline_md_status')}: {status_labels.get(event.status, event.status)}\n"
        )

        if event.duration_ms > 0:
            lines.append(
                f"- {_t('timeline_md_duration')}: {_t('timeline_md_duration_sec', sec=event.duration_ms)}\n"
            )

        if event.metadata:
            lines.append(f"- {_t('timeline_md_metadata')}: `{event.metadata}`\n")

        lines.append("\n---\n")

    return "\n".join(lines)


def _export_to_png(events: List[TimelineEvent]) -> bytes:
    """导出为PNG图片（使用HTML+CSS渲染）"""
    html_parts = [
        """
    <html>
    <head><meta charset="utf-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 40px; background: #f9fafb; }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { color: #1f2937; margin-bottom: 8px; }
        .event { display: flex; align-items: flex-start; margin-bottom: 20px; position: relative; padding-left: 40px; }
        .event::before { content: ''; position: absolute; left: 15px; top: 30px; bottom: -20px; width: 2px; background: #e5e7eb; }
        .event:last-child::before { display: none; }
        .dot { position: absolute; left: 8px; top: 8px; width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 0 2px #e5e7eb; }
        .time { font-family: monospace; color: #6b7280; font-size: 13px; min-width: 50px; }
        .card { flex: 1; background: white; border-radius: 8px; padding: 12px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
        .card-title { font-weight: 600; color: #1f2937; margin-bottom: 4px; }
        .card-desc { font-size: 13px; color: #6b7280; }
    </style></head><body>
    """
    ]

    html_parts.append(f'<div class="header"><h1>{_t("timeline_png_title")}</h1>')
    html_parts.append(
        f'<p>{_t("timeline_png_record_count", count=len(events), time=datetime.now().strftime("%Y-%m-%d %H:%M"))}</p></div>'
    )

    for event in events[:50]:
        config = EVENT_TYPE_CONFIG.get(event.event_type, {})
        color = config.get("color", "#6b7280")

        try:
            time_str = datetime.fromtimestamp(event.timestamp).strftime("%H:%M")
        except (ValueError, OSError):
            time_str = "--:--"

        escaped_title = (
            event.title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        escaped_desc = (
            event.description.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        html_parts.append(
            f"""
        <div class="event">
            <div class="dot" style="background: {color};"></div>
            <div class="time">{time_str}</div>
            <div class="card">
                <div class="card-title">{event.icon} {escaped_title}</div>
                <div class="card-desc">{escaped_desc}</div>
            </div>
        </div>
        """
        )

    html_parts.append("</body></html>")

    return "\n".join(html_parts).encode("utf-8")


def _escape_html(text: str) -> str:
    """转义HTML特殊字符"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )
