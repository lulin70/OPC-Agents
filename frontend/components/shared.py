"""Shared UI components and utilities for OPC-Agents frontend.

Extracted from monolithic app.py to enable modular page/component architecture.
Contains export helpers, progress indicators, undo panel, theme/language selectors,
and other reusable UI components.
"""

import streamlit as st
import os
import time
import logging
from datetime import datetime

from opc_manager.i18n import t as _t

logger = logging.getLogger(__name__)


def show_success(message: str, icon: str = "✅", duration: int = 3):
    """Show a success toast notification that auto-dismisses."""
    placeholder = st.empty()
    with placeholder.container():
        st.markdown(
            f"""
        <div class="opc-toast opc-toast-success">
            {icon} {message}
        </div>
        <style>
        .opc-toast {{
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: linear-gradient(135deg, #10b981, #059669);
            color: white;
            padding: 14px 24px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 999;
            font-size: 15px;
            animation: slideIn 0.3s ease-out;
        }}
        @keyframes slideIn {{
            from {{ transform: translateX(100%); opacity: 0; }}
            to {{ transform: translateX(0); opacity: 1; }}
        }}
        @media (max-width: 768px) {{
            .opc-toast {{
                left: 50%;
                right: auto;
                transform: translateX(-50%);
                bottom: 16px;
                width: 90%;
                max-width: 360px;
                text-align: center;
                font-size: 14px;
                padding: 12px 16px;
            }}
        }}
        </style>
        """,
            unsafe_allow_html=True,
        )

    import time as _time

    _time.sleep(min(duration, 2))
    placeholder.empty()
    return True


def show_error(message: str, icon: str = "❌"):
    """Show an error toast notification."""
    placeholder = st.empty()
    with placeholder.container():
        st.markdown(
            f"""
        <div class="opc-toast opc-toast-error">
            {icon} {message}
        </div>
        <style>
        .opc-toast-error {{
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: linear-gradient(135deg, #ef4444, #dc2626);
            color: white;
            padding: 14px 24px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 999;
            font-size: 15px;
        }}
        @media (max-width: 768px) {{
            .opc-toast-error {{
                left: 50%;
                right: auto;
                transform: translateX(-50%);
                bottom: 16px;
                width: 90%;
                max-width: 360px;
                text-align: center;
                font-size: 14px;
                padding: 12px 16px;
            }}
        }}
        </style>
        """,
            unsafe_allow_html=True,
        )
    import time as _time

    _time.sleep(2)
    placeholder.empty()


def show_info(message: str, icon: str = "ℹ️"):
    """Show an info toast notification."""
    placeholder = st.empty()
    with placeholder.container():
        st.markdown(
            f"""
        <div class="opc-toast opc-toast-info">
            {icon} {message}
        </div>
        <style>
        .opc-toast-info {{
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: linear-gradient(135deg, #3b82f6, #2563eb);
            color: white;
            padding: 14px 24px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 999;
            font-size: 15px;
        }}
        @media (max-width: 768px) {{
            .opc-toast-info {{
                left: 50%;
                right: auto;
                transform: translateX(-50%);
                bottom: 16px;
                width: 90%;
                max-width: 360px;
                text-align: center;
                font-size: 14px;
                padding: 12px 16px;
            }}
        }}
        </style>
        """,
            unsafe_allow_html=True,
        )
    import time as _time

    _time.sleep(2)
    placeholder.empty()


THEME_CONFIGS = {
    "light": {
        "backgroundColor": "#FFFFFF",
        "secondaryBackgroundColor": "#F0F2F6",
        "textColor": "#1F2937",
        "font": "sans-serif",
        "primaryColor": "#3B82F6",
    },
    "dark": {
        "backgroundColor": "#111827",
        "secondaryBackgroundColor": "#1F2937",
        "textColor": "#F9FAFB",
        "font": "sans-serif",
        "primaryColor": "#60A5FA",
    },
    "sunset": {
        "backgroundColor": "#1a1423",
        "secondaryBackgroundColor": "#261a2e",
        "textColor": "#fef3c7",
        "font": "sans-serif",
        "primaryColor": "#F59E0B",
    },
    "forest": {
        "backgroundColor": "#0d1f17",
        "secondaryBackgroundColor": "#152920",
        "textColor": "#D1FAE5",
        "font": "sans-serif",
        "primaryColor": "#34D399",
    },
    "ocean": {
        "backgroundColor": "#0c1929",
        "secondaryBackgroundColor": "#162d4a",
        "textColor": "#E0F2FE",
        "font": "sans-serif",
        "primaryColor": "#38BDF8",
    },
}


def apply_theme(theme_name: str):
    """Apply complete theme via Streamlit config."""
    config = THEME_CONFIGS.get(theme_name, THEME_CONFIGS["light"])
    import streamlit as st

    try:
        st.config.set_option("theme.primaryColor", config["primaryColor"])
        st.config.set_option("theme.backgroundColor", config["backgroundColor"])
        st.config.set_option(
            "theme.secondaryBackgroundColor", config["secondaryBackgroundColor"]
        )
        st.config.set_option("theme.textColor", config["textColor"])
        st.config.set_option("theme.font", config["font"])
        if theme_name == "dark":
            st.config.set_option("theme.base", "dark")
        elif theme_name == "light":
            st.config.set_option("theme.base", "light")
    except Exception:
        pass


def _get_theme_css(theme_name: str) -> str:
    """Return custom CSS for enhanced theme support."""
    themes = {
        "dark": """
            .stApp { background-color: #111827 !important; }
            .stMarkdown { color: #F9FAFB !important; }
            .stDataFrame { background-color: #1F2937 !important; }
            [data-testid="stMetric"] { background-color: #1F2937 !important; }
            [data-testid="stCheckbox"] label { color: #F9FAFB !important; }
            .stSelectbox > div > div { background-color: #1F2937 !important; }
            .stTextInput > div > div { background-color: #1F2937 !important; }
            """,
        "sunset": """
            .stApp { background-color: #1a1423 !important; }
            .stMarkdown { color: #fef3c7 !important; }
            [data-testid="stMetric"] { background-color: #261a2e !important; }
            """,
        "forest": """
            .stApp { background-color: #0d1f17 !important; }
            .stMarkdown { color: #D1FAE5 !important; }
            [data-testid="stMetric"] { background-color: #152920 !important; }
            """,
        "ocean": """
            .stApp { background-color: #0c1929 !important; }
            .stMarkdown { color: #E0F2FE !important; }
            [data-testid="stMetric"] { background-color: #162d4a !important; }
            """,
    }
    base_css = themes.get(theme_name, "")

    mobile_css = """
    /* 移动端响应式规则 */
    @media (max-width: 768px) {
        /* 按钮在小屏幕全宽显示 */
        .stButton > button {
            width: 100% !important;
            min-height: 44px !important;
        }
        /* 侧边栏在小屏幕自动收起 */
        [data-testid="stSidebar"] {
            width: 0px !important;
            min-width: 0px !important;
            overflow: hidden;
        }
        [data-testid="stSidebar"][aria-expanded="true"] {
            width: 280px !important;
            min-width: 280px !important;
        }
        /* Metric 卡片适配 */
        [data-testid="stMetric"] {
            padding: 8px !important;
        }
        /* 减少内边距节省空间 */
        .block-container {
            padding-top: 2rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
    }
    """
    return base_css + mobile_css


# Import DELIVERABLES_DIR from parent module (set in app.py before import)
# We'll get it from the module-level config or pass it as needed


def _get_export_bytes(content: str, fmt: str) -> tuple:
    try:
        return ErrorHandler.safe_execute(
            _do_get_export_bytes,
            content,
            fmt,
            context=_t("export_fmt_context", fmt=fmt),
        )
    except UserFriendlyError as e:
        logger.warning(
            "[frontend] %s: %s", _t("export_failed_log", fmt=fmt), e.user_message
        )
        return None, None, None


def _do_get_export_bytes(content: str, fmt: str) -> tuple:
    from opc_manager.export import ExportManager
    from opc_manager.export.models import ResultData, ExportFormat

    manager = ExportManager()
    format_enum = ExportFormat(fmt)
    data = ResultData(content=content, metadata={"title": "Export"})
    file_bytes = manager.export_sync(data, format_enum)
    mime_map = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "png": "image/png",
        "html": "text/html",
        "md": "text/markdown",
    }
    ext_map = {
        "pdf": "pdf",
        "docx": "docx",
        "xlsx": "xlsx",
        "png": "png",
        "html": "html",
        "md": "md",
    }
    return (
        file_bytes,
        mime_map.get(fmt, "application/octet-stream"),
        ext_map.get(fmt, "bin"),
    )


def _get_mime_type(filepath: str) -> str:
    """根据文件扩展名获取MIME类型"""
    ext = os.path.splitext(filepath)[1].lower()
    return {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".zip": "application/zip",
    }.get(ext, "application/octet-stream")


def _render_batch_export_section(DELIVERABLES_DIR):
    st.markdown(f"### 📤 {_t('export_batch_title')}")

    col_fmt, col_btn = st.columns([3, 1])
    with col_fmt:
        export_format = st.selectbox(
            _t("export_select_format"),
            options=[
                _t("export_pdf_pack"),
                _t("export_word_pack"),
                _t("export_excel"),
                _t("export_md_archive"),
            ],
            help=_t("export_format_help"),
        )
    with col_btn:
        if st.button(_t("export_batch_btn"), type="primary", use_container_width=True):
            _execute_batch_export(export_format, DELIVERABLES_DIR)


def _execute_batch_export(format_name: str, DELIVERABLES_DIR):
    from opc_manager.export.manager import ExportManager
    from opc_manager.export.models import ResultData, ExportFormat

    em = ExportManager()

    progress_bar = st.progress(0, text=_t("export_preparing"))

    deliverables = st.session_state.get("deliverables", [])

    if not deliverables:
        st.warning(_t("export_no_deliverables"))
        return

    fmt_map = {
        _t("export_pdf_pack"): ExportFormat.PDF,
        _t("export_word_pack"): ExportFormat.WORD,
        _t("export_excel"): ExportFormat.EXCEL,
        _t("export_md_archive"): ExportFormat.MD,
    }

    target_fmt = fmt_map.get(format_name, ExportFormat.MD)
    results = []

    for i, item in enumerate(deliverables):
        progress = int((i + 1) / len(deliverables) * 100)
        progress_bar.progress(
            progress, text=_t("export_progress", current=i + 1, total=len(deliverables))
        )

        try:
            filepath = item.get("filepath", "")
            if not filepath or not os.path.exists(filepath):
                continue

            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            rd = ResultData(
                content=content,
                metadata=item.get("metadata", item.get("meta", {})),
                attachments=item.get("attachments", []),
            )
            file_bytes = em.export_sync(rd, target_fmt)

            if file_bytes:
                ext = target_fmt.value
                output_filename = f"batch_{os.path.splitext(item.get('filename', f'item_{i}'))[0]}.{ext}"
                output_path = os.path.join(
                    DELIVERABLES_DIR, f"batch_export_{output_filename}"
                )
                with open(output_path, "wb") as f:
                    f.write(file_bytes)
                results.append(output_path)
        except Exception as e:
            st.warning(_t("export_item_failed", index=i + 1, error=e))

    progress_bar.progress(100, text=_t("export_complete"))

    if results:
        st.success(_t("export_success_count", count=len(results)))
        for fp in results:
            if os.path.exists(fp):
                with open(fp, "rb") as f:
                    st.download_button(
                        label=f"⬇️ {_t('download')} {os.path.basename(fp)}",
                        data=f,
                        file_name=os.path.basename(fp),
                        mime=_get_mime_type(fp),
                        key=f"dl_{fp}",
                    )


def _render_single_export_buttons(item: dict, item_id: str):
    col_pdf, col_word, col_excel, col_png = st.columns(4)
    with col_pdf:
        if st.button(
            "📄 PDF", key=f"pdf_{item_id}", help=_t("export_as_format", fmt="PDF")
        ):
            _export_single_with_preview(item, "pdf", item_id)
    with col_word:
        if st.button(
            "📝 Word", key=f"word_{item_id}", help=_t("export_as_format", fmt="Word")
        ):
            _export_single_with_preview(item, "word", item_id)
    with col_excel:
        if st.button(
            "📊 Excel", key=f"excel_{item_id}", help=_t("export_as_format", fmt="Excel")
        ):
            _export_single_with_preview(item, "excel", item_id)
    with col_png:
        if st.button("🖼️ 图片", key=f"png_{item_id}", help=_t("export_as_png")):
            _export_single_with_preview(item, "png", item_id)


def _render_export_preview(item_data: dict, format_type: str):
    st.subheader(_t("export_preview_title"))

    col_info, col_preview = st.columns([1, 2])
    with col_info:
        st.markdown(f"**{_t('format')}**: `{format_type.upper()}`")
        content_str = str(item_data) if not isinstance(item_data, str) else item_data
        size_kb = len(content_str.encode("utf-8")) // 1024
        st.markdown(f"**{_t('size')}**: ~{size_kb} KB ({_t('size_estimated')})")
        keys = list(item_data.keys()) if isinstance(item_data, dict) else []
        st.markdown(
            f"**{_t('included_fields')}**: {', '.join(keys[:5])}{'...' if len(keys) > 5 else ''}"
            if keys
            else f"**{_t('content_type')}**: {_t('text_type')}"
        )

        format_hints = {
            "pdf": "📄 PDF {_t('format_pdf_desc')}",
            "word": "📝 Word {_t('format_word_desc')}",
            "excel": "📊 Excel {_t('format_excel_desc')}",
            "image": "🖼️ PNG {_t('format_png_desc')}",
            "png": "🖼️ PNG {_t('format_png_desc')}",
        }
        st.caption(
            format_hints.get(
                format_type.lower(), _t("export_as_format2", fmt=format_type.upper())
            )
        )

    with col_preview:
        content_preview = str(item_data)[:500] + (
            "..." if len(str(item_data)) > 500 else ""
        )
        st.text_area(
            _t("content_preview"), value=content_preview, height=200, disabled=True
        )

    col_confirm, col_cancel = st.columns([1, 1])
    with col_confirm:
        if st.button(
            "✅ " + _t("confirm_export"),
            type="primary",
            key=f"confirm_export_{format_type}",
        ):
            return True
    with col_cancel:
        if st.button(_t("cancel"), key=f"cancel_export_{format_type}"):
            return False

    return None


def _export_single_with_preview(item: dict, fmt: str, item_id: str):
    filepath = item.get("filepath", "")
    if not filepath or not os.path.exists(filepath):
        st.error(_t("file_not_exists"))
        return

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        item_data = {
            "content": content[:2000],
            "filename": item.get("filename", ""),
            "metadata": item.get("metadata", item.get("meta", {})),
        }

        preview_result = _render_export_preview(item_data, fmt)

        if preview_result is True:
            _export_single(item, fmt)
        elif preview_result is False:
            st.info(_t("export_cancelled"))
    except Exception as e:
        st.error(_t("preview_failed", error=e))


def _export_single(item: dict, fmt: str):
    from opc_manager.export.manager import ExportManager
    from opc_manager.export.models import ResultData, ExportFormat

    filepath = item.get("filepath", "")
    if not filepath or not os.path.exists(filepath):
        st.error(_t("file_not_exists"))
        return

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        em = ExportManager()
        fmt_map = {
            "pdf": ExportFormat.PDF,
            "word": ExportFormat.WORD,
            "excel": ExportFormat.EXCEL,
            "png": ExportFormat.IMAGE,
        }
        target_fmt = fmt_map.get(fmt, ExportFormat.MD)

        rd = ResultData(
            content=content,
            metadata=item.get("metadata", item.get("meta", {})),
            attachments=item.get("attachments", []),
        )
        file_bytes = em.export_sync(rd, target_fmt)

        if file_bytes:
            ext = target_fmt.value
            filename = f"{os.path.splitext(item.get('filename', 'export'))[0]}.{ext}"
            st.download_button(
                label=f"⬇️ {_t('download')} {filename}",
                data=file_bytes,
                file_name=filename,
                mime=_get_mime_type(f".{ext}"),
                key=f"dl_single_{fmt}_{item_id}",
            )
        else:
            st.warning(_t("export_format_failed", fmt=fmt.upper()))
    except Exception as e:
        st.error(_t("export_failed", error=e))


def _event_type_label(event_type: str) -> str:
    labels = {
        "PLAN_START": _t("event_plan_start"),
        "INTENT_DETECTED": _t("event_intent_detected"),
        "CONFIRM_REQUESTED": _t("event_confirm_requested"),
        "CONFIRMED": _t("event_confirmed"),
        "STEP_START": _t("event_step_start"),
        "STEP_PROGRESS": _t("event_step_progress"),
        "STEP_COMPLETE": _t("event_step_complete"),
        "COLLAB_START": _t("event_collab_start"),
        "REFLECT_START": _t("event_reflect_start"),
        "COMPLETE": _t("event_complete"),
        "ERROR": _t("event_error"),
        "CANCELLED": _t("event_cancelled"),
        "plan_start": _t("event_plan_start"),
        "intent_detected": _t("event_intent_detected"),
        "confirm_requested": _t("event_confirm_requested"),
        "confirmed": _t("event_confirmed"),
        "step_start": _t("event_step_start"),
        "step_progress": _t("event_step_progress"),
        "step_complete": _t("event_step_complete"),
        "collab_start": _t("event_collab_start"),
        "reflect_start": _t("event_reflect_start"),
        "complete": _t("event_complete"),
        "error": _t("event_error"),
        "cancelled": _t("event_cancelled"),
    }
    return labels.get(event_type, event_type.replace("_", " ").title())


def _get_phase_from_event(event_type: str) -> tuple:
    phase_mapping = {
        "plan_start": ("🚀", _t("phase_task_start")),
        "intent_detected": ("🔍", _t("phase_intent_detected")),
        "step_start": ("⚡", _t("phase_executing")),
        "step_progress": ("⚡", _t("phase_executing")),
        "step_complete": ("✅", _t("event_step_complete")),
        "complete": ("✅", _t("phase_task_complete")),
        "error": ("❌", _t("phase_exec_error")),
    }
    event_key = event_type.lower().replace("-", "_")
    return phase_mapping.get(event_key, ("⚡", _t("phase_executing")))


def _event_emoji(event_type: str) -> str:
    """获取事件类型对应的emoji"""
    emojis = {
        "PLAN_START": "🎯",
        "INTENT_DETECTED": "🔍",
        "CONFIRM_REQUESTED": "❓",
        "CONFIRMED": "✅",
        "STEP_START": "⚙️",
        "STEP_PROGRESS": "🔄",
        "STEP_COMPLETE": "✅",
        "COLLAB_START": "🤝",
        "REFLECT_START": "💭",
        "COMPLETE": "🎉",
        "ERROR": "❌",
        "CANCELLED": "⏹️",
        "plan_start": "🎯",
        "intent_detected": "🔍",
        "confirm_requested": "❓",
        "confirmed": "✅",
        "step_start": "⚙️",
        "step_progress": "🔄",
        "step_complete": "✅",
        "collab_start": "🤝",
        "reflect_start": "💭",
        "complete": "🎉",
        "error": "❌",
        "cancelled": "⏹️",
    }
    return emojis.get(event_type, "📌")


def _render_progress_indicator(session_id: str):
    """渲染基于SSE的实时进度指示器（增强版）

    显示功能：
    - 动画进度条，通过Server-Sent Events更新
    - 阶段图标映射（PLAN_START→🚀, INTENT_DETECTED→🔍等）
    - 阶段时间线可视化
    - 错误状态特殊样式（红色高亮）
    - 如果SSE不可用则回退到静态进度显示
    """
    try:
        from opc_manager.progress_emitter import (
            ProgressEmitter,
            get_progress_emitter,
            EventType,
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

    bar_color = "error" if is_error else None
    bar = st.progress(min(progress_pct / 100.0, 1.0))

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
        st.markdown(f"**📈 {_t('execution_timeline')}**")

        _render_timeline(history)

        with st.expander("📋 操作日志详情", expanded=False):
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
        "plan_start": "🚀",
        "intent_detected": "🔍",
        "confirm_requested": "❓",
        "confirmed": "✅",
        "step_start": "⚡",
        "step_progress": "⚡",
        "step_complete": "✅",
        "complete": "✅",
        "error": "❌",
        "cancelled": "⏹️",
    }
    event_key = event_type.lower().replace("-", "_")
    return icon_mapping.get(event_key, "📌")


def _render_timeline(history: list):
    timeline_phases = [
        ("plan_start", "🚀 " + _t("timeline_plan_start")),
        ("intent_detected", "🔍 " + _t("timeline_intent_detected")),
        ("step_start", "⚡ " + _t("timeline_step_start")),
        ("step_complete", "✅ " + _t("event_step_complete")),
        ("complete", "🎉 " + _t("timeline_task_complete")),
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
        if st.button("🔄 " + _t("refresh_progress"), key="refresh_prog"):
            st.rerun()
    with col_close:
        st.caption(_t("click_refresh_hint"))


def _render_export_buttons(content: str, formats: list, key_prefix: str):
    if not formats:
        return
    FORMAT_LABELS = {
        "pdf": "📄 PDF",
        "docx": "📝 Word",
        "xlsx": "📊 Excel",
        "png": "🖼️ 图片",
        "html": "🌐 HTML",
        "md": "📑 Markdown",
    }
    st.markdown(f"**{_t('export_as_other_formats')}:**")
    btn_cols = st.columns(min(len(formats), 4))
    for i, fmt in enumerate(formats):
        label = FORMAT_LABELS.get(fmt, fmt.upper())
        with btn_cols[i % len(btn_cols)]:
            file_bytes, mime, ext = _get_export_bytes(content, fmt)
            if file_bytes:
                st.download_button(
                    label=label,
                    data=file_bytes,
                    file_name=f"export_{key_prefix}.{ext}",
                    mime=mime,
                    key=f"export_{fmt}_{key_prefix}",
                    use_container_width=True,
                )
            else:
                st.button(
                    label,
                    key=f"export_fail_{fmt}_{key_prefix}",
                    disabled=True,
                    help="导出依赖未安装",
                )


def _get_undo_manager():
    """Safe wrapper to get UndoManager instance."""
    try:
        from opc_manager.undo_manager import get_undo_manager

        return get_undo_manager()
    except ImportError:
        return None
    except Exception as e:
        logger.warning("[frontend] UndoManager init failed: %s", e)
        return None


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
                                        st.balloons()
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
            st.markdown(
                f"""
            | {_t('tips_title')} | |
            |--------|------|
            | `Enter` | {_t('shortcut_send')} |
            | `Esc` | {_t('shortcut_cancel')} |
            | `/` | {_t('tip_slash_command')} |

            {_t('tips_hint')}
            """
            )

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


def _get_current_session_id() -> str:
    """Get current session ID from session context.

    Returns:
        Session ID string or 'default' fallback
    """
    try:
        session_ctx = st.session_state.get("session_ctx")
        if session_ctx and hasattr(session_ctx, "_session_id"):
            return session_ctx._session_id
        elif session_ctx and hasattr(session_ctx, "session_id"):
            return session_ctx.session_id
    except Exception:
        pass

    return st.session_state.get("session_id", "default")


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
                            st.balloons()
                            _cached_list_undoable.clear()
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(
                                f"❌ {_t('undo_failed', error=result.get('error', _t('unknown_error')))}"
                            )

    except Exception as e:
        logger.warning("[frontend] Quick undo button error: %s", e)
