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

logger = logging.getLogger(__name__)


def show_success(message: str, icon: str = "✅", duration: int = 3):
    """Show a success toast notification that auto-dismisses."""
    placeholder = st.empty()
    with placeholder.container():
        st.markdown(f"""
        <div style="
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
        ">
            {icon} {message}
        </div>
        <style>
        @keyframes slideIn {{
            from {{ transform: translateX(100%); opacity: 0; }}
            to {{ transform: translateX(0); opacity: 1; }}
        }}
        </style>
        """, unsafe_allow_html=True)

    import time as _time
    _time.sleep(min(duration, 2))
    placeholder.empty()
    return True


def show_error(message: str, icon: str = "❌"):
    """Show an error toast notification."""
    placeholder = st.empty()
    with placeholder.container():
        st.markdown(f"""
        <div style="
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
        ">
            {icon} {message}
        </div>
        """, unsafe_allow_html=True)
    import time as _time
    _time.sleep(2)
    placeholder.empty()


def show_info(message: str, icon: str = "ℹ️"):
    """Show an info toast notification."""
    placeholder = st.empty()
    with placeholder.container():
        st.markdown(f"""
        <div style="
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
        ">
            {icon} {message}
        </div>
        """, unsafe_allow_html=True)
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
        st.config.set_option("theme.secondaryBackgroundColor", config["secondaryBackgroundColor"])
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
    return themes.get(theme_name, "")

# Import DELIVERABLES_DIR from parent module (set in app.py before import)
# We'll get it from the module-level config or pass it as needed


def _get_export_bytes(content: str, fmt: str) -> tuple:
    try:
        return ErrorHandler.safe_execute(
            _do_get_export_bytes, content, fmt,
            context=f"导出{fmt}格式时"
        )
    except UserFriendlyError as e:
        logger.warning("[frontend] 导出失败 (%s): %s", fmt, e.user_message)
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
        "pdf": "pdf", "docx": "docx", "xlsx": "xlsx",
        "png": "png", "html": "html", "md": "md",
    }
    return file_bytes, mime_map.get(fmt, "application/octet-stream"), ext_map.get(fmt, "bin")


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
    """在成果物Tab中渲染批量导出区域"""
    st.markdown("### 📤 批量导出")

    col_fmt, col_btn = st.columns([3, 1])
    with col_fmt:
        export_format = st.selectbox(
            "选择导出格式",
            options=["PDF文档包", "Word文档包", "Excel表格", "Markdown归档"],
            help="将所有成果物打包为选定格式"
        )
    with col_btn:
        if st.button("批量导出", type="primary", use_container_width=True):
            _execute_batch_export(export_format, DELIVERABLES_DIR)


def _execute_batch_export(format_name: str, DELIVERABLES_DIR):
    """执行批量导出所有成果物"""
    from opc_manager.export.manager import ExportManager
    from opc_manager.export.models import ResultData, ExportFormat

    em = ExportManager()

    progress_bar = st.progress(0, text="准备导出...")

    deliverables = st.session_state.get("deliverables", [])

    if not deliverables:
        st.warning("暂无成果物可导出")
        return

    fmt_map = {
        "PDF文档包": ExportFormat.PDF,
        "Word文档包": ExportFormat.WORD,
        "Excel表格": ExportFormat.EXCEL,
        "Markdown归档": ExportFormat.MD,
    }

    target_fmt = fmt_map.get(format_name, ExportFormat.MD)
    results = []

    for i, item in enumerate(deliverables):
        progress = int((i + 1) / len(deliverables) * 100)
        progress_bar.progress(progress, text=f"正在导出 ({i+1}/{len(deliverables)})...")

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
                output_path = os.path.join(DELIVERABLES_DIR, f"batch_export_{output_filename}")
                with open(output_path, "wb") as f:
                    f.write(file_bytes)
                results.append(output_path)
        except Exception as e:
            st.warning(f"导出第{i+1}项失败: {e}")

    progress_bar.progress(100, text="✅ 导出完成!")

    if results:
        st.success(f"成功导出 {len(results)} 个文件")
        for fp in results:
            if os.path.exists(fp):
                with open(fp, "rb") as f:
                    st.download_button(
                        label=f"⬇️ 下载 {os.path.basename(fp)}",
                        data=f,
                        file_name=os.path.basename(fp),
                        mime=_get_mime_type(fp),
                        key=f"dl_{fp}",
                    )


def _render_single_export_buttons(item: dict, item_id: str):
    """渲染单个成果物的4图标导出按钮组"""
    col_pdf, col_word, col_excel, col_png = st.columns(4)
    with col_pdf:
        if st.button("📄 PDF", key=f"pdf_{item_id}", help="导出为PDF"):
            _export_single_with_preview(item, "pdf", item_id)
    with col_word:
        if st.button("📝 Word", key=f"word_{item_id}", help="导出为Word"):
            _export_single_with_preview(item, "word", item_id)
    with col_excel:
        if st.button("📊 Excel", key=f"excel_{item_id}", help="导出为Excel"):
            _export_single_with_preview(item, "excel", item_id)
    with col_png:
        if st.button("🖼️ 图片", key=f"png_{item_id}", help="导出为PNG图片"):
            _export_single_with_preview(item, "png", item_id)


def _render_export_preview(item_data: dict, format_type: str):
    """Show preview of export content before actual export."""
    st.subheader("📋 导出预览")

    col_info, col_preview = st.columns([1, 2])
    with col_info:
        st.markdown(f"**格式**: `{format_type.upper()}`")
        content_str = str(item_data) if not isinstance(item_data, str) else item_data
        size_kb = len(content_str.encode("utf-8")) // 1024
        st.markdown(f"**大小**: ~{size_kb} KB (预估)")
        keys = list(item_data.keys()) if isinstance(item_data, dict) else []
        st.markdown(f"**包含字段**: {', '.join(keys[:5])}{'...' if len(keys) > 5 else ''}" if keys else "**内容类型**: 文本")

        format_hints = {
            "pdf": "📄 PDF 文档，支持中文排版",
            "word": "📝 Word 文档，可编辑格式",
            "excel": "📊 Excel 表格，含数据表",
            "image": "🖼️ PNG 图片，适合分享",
            "png": "🖼️ PNG 图片，适合分享",
        }
        st.caption(format_hints.get(format_type.lower(), f"导出为 {format_type.upper()} 格式"))

    with col_preview:
        content_preview = str(item_data)[:500] + ("..." if len(str(item_data)) > 500 else "")
        st.text_area("内容预览", value=content_preview, height=200, disabled=True)

    col_confirm, col_cancel = st.columns([1, 1])
    with col_confirm:
        if st.button("✅ 确认导出", type="primary", key=f"confirm_export_{format_type}"):
            return True
    with col_cancel:
        if st.button("取消", key=f"cancel_export_{format_type}"):
            return False

    return None


def _export_single_with_preview(item: dict, fmt: str, item_id: str):
    """Execute single export with preview step."""
    filepath = item.get("filepath", "")
    if not filepath or not os.path.exists(filepath):
        st.error("文件不存在")
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
            st.info("导出已取消")
    except Exception as e:
        st.error(f"预览失败: {e}")


def _export_single(item: dict, fmt: str):
    """执行单个成果物的格式导出"""
    from opc_manager.export.manager import ExportManager
    from opc_manager.export.models import ResultData, ExportFormat

    filepath = item.get("filepath", "")
    if not filepath or not os.path.exists(filepath):
        st.error("文件不存在")
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
                label=f"⬇️ 下载 {filename}",
                data=file_bytes,
                file_name=filename,
                mime=_get_mime_type(f".{ext}"),
                key=f"dl_single_{fmt}_{item_id}",
            )
        else:
            st.warning(f"导出{fmt.upper()}失败")
    except Exception as e:
        st.error(f"导出失败: {e}")


def _event_type_label(event_type: str) -> str:
    """将事件类型转换为中文标签"""
    labels = {
        "PLAN_START": "🎯 规划中...",
        "INTENT_DETECTED": "🔍 分析意图...",
        "CONFIRM_REQUESTED": "❓ 等待确认...",
        "CONFIRMED": "✅ 已确认",
        "STEP_START": "⚙️ 执行步骤...",
        "STEP_PROGRESS": "🔄 进行中...",
        "STEP_COMPLETE": "✅ 步骤完成",
        "COLLAB_START": "🤝 协作处理...",
        "REFLECT_START": "💭 反思评估...",
        "COMPLETE": "🎉 全部完成!",
        "ERROR": "❌ 出现错误",
        "CANCELLED": "⏹️ 已取消",
        "plan_start": "🎯 规划中...",
        "intent_detected": "🔍 分析意图...",
        "confirm_requested": "❓ 等待确认...",
        "confirmed": "✅ 已确认",
        "step_start": "⚙️ 执行步骤...",
        "step_progress": "🔄 进行中...",
        "step_complete": "✅ 步骤完成",
        "collab_start": "🤝 协作处理...",
        "reflect_start": "💭 反思评估...",
        "complete": "🎉 全部完成!",
        "error": "❌ 出现错误",
        "cancelled": "⏹️ 已取消",
    }
    return labels.get(event_type, event_type.replace("_", " ").title())


def _get_phase_from_event(event_type: str) -> tuple:
    """根据事件类型返回对应的图标和阶段名称

    Args:
        event_type: 事件类型字符串

    Returns:
        (icon, name) 元组
    """
    phase_mapping = {
        "plan_start": ("🚀", "任务启动"),
        "intent_detected": ("🔍", "意图识别"),
        "step_start": ("⚡", "执行中"),
        "step_progress": ("⚡", "执行中"),
        "step_complete": ("✅", "步骤完成"),
        "complete": ("✅", "任务完成"),
        "error": ("❌", "执行错误"),
    }
    event_key = event_type.lower().replace("-", "_")
    return phase_mapping.get(event_key, ("⚡", "执行中"))


def _event_emoji(event_type: str) -> str:
    """获取事件类型对应的emoji"""
    emojis = {
        "PLAN_START": "🎯", "INTENT_DETECTED": "🔍",
        "CONFIRM_REQUESTED": "❓", "CONFIRMED": "✅",
        "STEP_START": "⚙️", "STEP_PROGRESS": "🔄",
        "STEP_COMPLETE": "✅", "COLLAB_START": "🤝",
        "REFLECT_START": "💭", "COMPLETE": "🎉",
        "ERROR": "❌", "CANCELLED": "⏹️",
        "plan_start": "🎯", "intent_detected": "🔍",
        "confirm_requested": "❓", "confirmed": "✅",
        "step_start": "⚙️", "step_progress": "🔄",
        "step_complete": "✅", "collab_start": "🤝",
        "reflect_start": "💭", "complete": "🎉",
        "error": "❌", "cancelled": "⏹️",
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
        from opc_manager.progress_emitter import ProgressEmitter, get_progress_emitter, EventType
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
        st.markdown(f"#### {phase_icon} 当前状态: :red[{status_label}]")
    else:
        st.markdown(f"#### {phase_icon} 当前状态: {status_label}")

    bar_color = "error" if is_error else None
    bar = st.progress(min(progress_pct / 100.0, 1.0))

    cols_info = st.columns(3)
    with cols_info[0]:
        if is_error:
            st.metric("进度", f":red[{progress_pct}%]")
        else:
            st.metric("进度", f"{progress_pct}%")
    with cols_info[1]:
        stage_name = event_type.replace("_", " ").title() if event_type else "-"
        st.metric("阶段", stage_name)
    with cols_info[2]:
        display_msg = message[:50] + "..." if len(message) > 50 else (message or "-")
        if is_error:
            st.metric("消息", f":red[{display_msg}]")
        else:
            st.metric("消息", display_msg)

    if len(history) > 1:
        st.markdown("---")
        st.markdown("**📈 执行时间线**")

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
                    st.markdown(f"{emoji} `{time_str}` :red[**{etype}**] ({epct}%) - :red[{emsg}]")
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
    """渲染阶段时间线可视化

    Args:
        history: 事件历史列表
    """
    timeline_phases = [
        ("plan_start", "🚀 计划启动"),
        ("intent_detected", "🔍 意图识别"),
        ("step_start", "⚡ 步骤执行"),
        ("step_complete", "✅ 步骤完成"),
        ("complete", "🎉 任务完成"),
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
        if st.button("🔄 刷新进度", key="refresh_prog"):
            st.rerun()
    with col_close:
        st.caption("点击刷新查看最新进度")


def _render_export_buttons(content: str, formats: list, key_prefix: str):
    if not formats:
        return
    FORMAT_LABELS = {
        "pdf": "📄 PDF", "docx": "📝 Word", "xlsx": "📊 Excel",
        "png": "🖼️ 图片", "html": "🌐 HTML", "md": "📑 Markdown",
    }
    st.markdown("**导出为其他格式:**")
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
                st.button(label, key=f"export_fail_{fmt}_{key_prefix}", disabled=True, help="导出依赖未安装")


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

    if st.button("↩️ 撤销操作", use_container_width=True, help="查看和管理可撤销的操作"):
        st.session_state.show_undo = not st.session_state.get("show_undo", False)

    if st.session_state.get("show_undo", False):
        st.markdown("#### ↩️ 可撤销的操作")

        session_id = _get_current_session_id()
        if not session_id:
            st.warning("⚠️ 无法获取当前会话ID")
            return

        undoable = _cached_list_undoable(session_id)

        if not undoable:
            st.info("没有可撤销的操作")
            return

        st.caption(f"共 {len(undoable)} 个可撤销操作")

        for record in undoable[-10:]:
            op_type = record.get("operation_type", "unknown")
            created_at = record.get("created_at", "")
            op_id = record.get("operation_id", "")

            can_undo, reason = um.can_undo(session_id, op_id)

            with st.expander(f"↩️ {op_type} — {created_at}"):
                col_info, col_action = st.columns([3, 1])

                with col_info:
                    st.json({
                        "类型": op_type,
                        "时间": created_at,
                        "状态": "可撤销" if can_undo else f"不可撤: {reason}",
                        "ID": op_id[:12] if op_id else "",
                    })

                with col_action:
                    if can_undo:
                        confirmed = st.checkbox(
                            "确认撤销",
                            key=f"undo_confirm_{op_id}",
                            help="勾选此项以确认执行撤销操作"
                        )

                        if confirmed:
                            if st.button(
                                "撤销",
                                key=f"undo_{op_id}",
                                type="secondary",
                                help="此操作将执行逆操作，请谨慎"
                            ):
                                with st.spinner("正在撤销..."):
                                    result = um.undo(session_id, op_id)
                                    if result.get("success"):
                                        st.success(f"✅ 已撤销: {result.get('message', '')}")
                                        st.balloons()
                                        _cached_list_undoable.clear()
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error(f"❌ 撤销失败: {result.get('error', '未知错误')}")
                    else:
                        st.caption(f"❌ {reason}")

                        expires_at = record.get("expires_at", 0)
                        if expires_at and not can_undo:
                            remaining = max(0, expires_at - time.time())
                            if remaining > 0:
                                mins, secs = divmod(int(remaining), 60)
                                st.caption(f"⏰ 剩余时间: {mins}分{secs}秒")
                            else:
                                st.caption("⏰ 已过撤销窗口期")


def _render_theme_selector():
    """Render theme selector in sidebar."""
    themes = {
        "light": "☀️ 浅色",
        "dark": "🌙 深色",
        "sunset": "🌅 日落橙",
        "forest": "🌲 森林绿",
        "ocean": "🌊 海洋蓝",
    }

    current = st.session_state.get("theme", "light")
    selected = st.selectbox(
        "🎨 主题",
        options=list(themes.keys()),
        format_func=lambda x: themes[x],
        index=list(themes.keys()).index(current) if current in themes else 0,
        key="theme_selector"
    )

    if selected != current:
        st.session_state.theme = selected
        apply_theme(selected)


def _render_language_selector():
    """Render language selector in sidebar."""
    from opc_manager.i18n import get_i18n
    i18n = get_i18n()
    locales = i18n.get_available_locales()
    current = i18n.locale
    selected = st.selectbox(
        "🌐 Language / 语言",
        options=[l["code"] for l in locales],
        format_func=lambda x: next(l["name"] for l in locales if l["code"] == x),
        index=[l["code"] for l in locales].index(current),
        key="lang_selector"
    )
    if selected != current:
        i18n.locale = selected
        st.rerun()


def _render_shortcuts_help():
    """Render keyboard shortcuts help panel with enhanced content."""
    from opc_manager.i18n import t as _t
    with st.expander("⌨️ Keyboard Shortcuts / 快捷键"):
        shortcuts = [
            ("Enter", "发送消息 / Send message"),
            ("Esc", "取消当前操作 / Close dialog"),
            ("Ctrl+Z", "撤销上一步 / Undo last step"),
            ("/", "打开命令面板 / Command palette"),
            ("?", "显示帮助 / Show help"),
            ("Ctrl + N", "New chat / 新对话"),
            ("Ctrl + E", "Export / 导出"),
            ("Ctrl + D", "Dashboard / 仪表板"),
            ("Ctrl + S", "Settings / 设置"),
        ]
        for keys, desc in shortcuts:
            st.code(f"{keys:20s} → {desc}")
        st.caption("💡 *提示：按 `?` 随时查看此列表*")


def _maybe_show_shortcut_hints():
    """Show keyboard shortcuts hint bubble on first visit to chat page."""
    if "shortcuts_shown" not in st.session_state:
        st.session_state.shortcuts_shown = False

    if not st.session_state.shortcuts_shown:
        with st.expander("⌨️ 键盘快捷键提示 (点击收起)", expanded=True):
            st.markdown("""
            | 快捷键 | 功能 |
            |--------|------|
            | `Enter` | 发送消息 |
            | `Esc` | 取消当前操作 |
            | `Ctrl+Z` | 撤销上一步 |
            | `/` | 打开命令面板 |
            | `?` | 显示帮助 |

            💡 *提示：按 `?` 随时查看此列表*
            """)

        col_dismiss, col_later = st.columns([1, 1])
        with col_dismiss:
            if st.button("知道了，不再显示", key="dismiss_shortcuts"):
                st.session_state.shortcuts_shown = True
                st.rerun()
        with col_later:
            if st.button("下次再说", key="shortcuts_later"):
                st.session_state.shortcuts_shown = True


def _render_floating_help_button():
    """Render a small floating '?' button that re-shows shortcut hints."""
    st.markdown("""
    <div style="
        position: fixed;
        bottom: 80px;
        right: 24px;
        z-index: 998;
    >
    </div>
    """, unsafe_allow_html=True)
    if st.button("❓ 快捷键帮助", key="floating_help_btn", help="点击查看键盘快捷键"):
        st.session_state.shortcuts_shown = False
        st.rerun()


def _get_current_session_id() -> str:
    """Get current session ID from session context.

    Returns:
        Session ID string or 'default' fallback
    """
    try:
        session_ctx = st.session_state.get("session_ctx")
        if session_ctx and hasattr(session_ctx, '_session_id'):
            return session_ctx._session_id
        elif session_ctx and hasattr(session_ctx, 'session_id'):
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
            label = f"↩️ 撤销上一步 ({operation_type or last_record.get('operation_type', '操作')})"

            if st.button(label, key=f"quick_undo_{task_id}", type="secondary"):
                confirmed = st.checkbox(
                    "✅ 我确认要撤销此操作",
                    key=f"quick_undo_confirm_{task_id}",
                    help="撤销是破坏性操作，将执行逆操作恢复原始状态"
                )

                if confirmed:
                    with st.spinner("正在撤销..."):
                        result = um.undo(session_id, op_id)
                        if result.get("success"):
                            st.success(f"✅ 已撤销: {result.get('message', '')}")
                            st.balloons()
                            _cached_list_undoable.clear()
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"❌ 撤销失败: {result.get('error', '未知错误')}")

    except Exception as e:
        logger.warning("[frontend] Quick undo button error: %s", e)
