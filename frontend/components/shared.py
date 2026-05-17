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
            _export_single(item, "pdf")
    with col_word:
        if st.button("📝 Word", key=f"word_{item_id}", help="导出为Word"):
            _export_single(item, "word")
    with col_excel:
        if st.button("📊 Excel", key=f"excel_{item_id}", help="导出为Excel"):
            _export_single(item, "excel")
    with col_png:
        if st.button("🖼️ 图片", key=f"png_{item_id}", help="导出为PNG图片"):
            _export_single(item, "png")


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
    """渲染基于SSE的实时进度指示器

    显示一个动画进度条，通过Server-Sent Events更新。
    如果SSE不可用则回退到静态进度显示。
    """
    try:
        from opc_manager.progress_emitter import ProgressEmitter, get_progress_emitter
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

    st.markdown(f"#### ⚡ 当前状态: {_event_type_label(event_type)}")

    bar = st.progress(min(progress_pct / 100.0, 1.0))

    cols_info = st.columns(3)
    with cols_info[0]:
        st.metric("进度", f"{progress_pct}%")
    with cols_info[1]:
        st.metric("阶段", event_type.replace("_", " ").title() if event_type else "-")
    with cols_info[2]:
        display_msg = message[:50] + "..." if len(message) > 50 else (message or "-")
        st.metric("消息", display_msg)

    if len(history) > 1:
        with st.expander("📋 操作日志详情", expanded=False):
            for evt in reversed(history[-10:]):
                etype = evt.get("event", evt.get("event_type", "UNKNOWN"))
                epct = evt.get("progress", evt.get("progress_pct", 0))
                emsg = evt.get("message", "")
                etime = evt.get("timestamp", "")
                emoji = _event_emoji(etype)

                if etime:
                    try:
                        time_str = datetime.fromtimestamp(etime).strftime("%H:%M:%S")
                    except (TypeError, ValueError):
                        time_str = str(etime)
                else:
                    time_str = ""

                st.markdown(f"{emoji} `{time_str}` **{etype}** ({epct}%) - {emsg}")


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
        if selected == "dark":
            st.config.set_option("theme.base", "dark")
        elif selected == "light":
            st.config.set_option("theme.base", "light")
        elif selected == "sunset":
            st.config.set_option("theme.primaryColor", "#FF6B35")
            st.config.set_option("theme.backgroundColor", "#1E1E1E")
            st.config.set_option("theme.secondaryBackgroundColor", "#2D2D2D")
        elif selected == "forest":
            st.config.set_option("theme.primaryColor", "#2E7D32")
            st.config.set_option("theme.backgroundColor", "#1B3A1B")
            st.config.set_option("theme.secondaryBackgroundColor", "#263D26")
        elif selected == "ocean":
            st.config.set_option("theme.primaryColor", "#1976D2")
            st.config.set_option("theme.backgroundColor", "#0D1F2C")
            st.config.set_option("theme.secondaryBackgroundColor", "#152938")


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
    """Render keyboard shortcuts help panel."""
    from opc_manager.i18n import t as _t
    with st.expander("⌨️ Keyboard Shortcuts / 快捷键"):
        shortcuts = [
            ("Ctrl + Enter", _t("Send message") if 't' in dir() else "发送消息"),
            ("Ctrl + N", "New chat / 新对话"),
            ("Ctrl + E", "Export / 导出"),
            ("Ctrl + D", "Dashboard / 仪表板"),
            ("Ctrl + S", "Settings / 设置"),
            ("?", "Show help / 显示帮助"),
            ("Esc", "Close dialog / 关闭对话框"),
        ]
        for keys, desc in shortcuts:
            st.code(f"{keys:20s} → {desc}")


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
