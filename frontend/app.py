"""Streamlit 前端 - OPC-Agents (成果物交付版)

=== 产品定位 ===
"告诉系统你要什么结果，它直接做完并交付文件给你"

=== 核心设计改变（从v3.0到v3.4）===
v3.0: "屏幕上显示文字" — AI助手聊天模式
v3.4: "交付可下载的文件" — 任务执行+成果物交付模式

每次任务执行都会：
1. 调用TaskEngineV3执行真实搜索和内容生成
2. 将结果保存为.md文件到deliverables/目录
3. 在界面上显示下载按钮
4. 用户可直接下载、保存、复用

=== 页面结构（4个Tab）===
1. 💬 对话: 主交互界面，输入需求→执行→下载
2. 📁 成果物: 历史文件库，预览+重新下载
3. 📊 成长: 五维飞轮仪表盘，等级系统
4. ⚙️ 设置: 风格/路径/数据重置/高级选项

=== 会话管理策略 ===
- 使用Streamlit session_state存储所有状态
- 刷新页面会丢失历史（已知限制，后续迭代DB持久化）
- 每次页面加载时初始化默认状态（if "initialized" not in st.session_state）

=== 错误处理策略 ===
- safe_detect/safe_get_persona/safe_track_flywheel: 三层防御包装器，
  确保后端模块异常不会导致前端崩溃
- execute_task_and_deliver: 顶层try-except，失败时返回友好错误提示
- 超时检测: 通过error_msg关键词匹配判断是否为网络超时，
  给出不同的降级提示和CLI备选方案

=== 版本历史 ===
v3.0: 初始Streamlit UI
v3.1: 增加成果物下载功能
v3.2: 增加成果物库页面
v3.3: st.spinner → st.status进度反馈，超时友好提示
v3.4: 代码走读注释完善
"""

import streamlit as st
import sys
import os
import re
import html
import traceback
import time
import json
import logging
from datetime import datetime

from dotenv import load_dotenv
from pathlib import Path

_WORKSPACE_DIR = os.environ.get("OPC_WORKSPACE", os.getcwd())
load_dotenv(Path(_WORKSPACE_DIR) / ".env")

try:
    from opc_manager.secure_storage import init_secure_storage
    init_secure_storage()
except ImportError:
    pass
except Exception as e:
    import logging as _logging
    _logging.getLogger(__name__).warning("Secure storage init failed: %s", e)

from opc_manager.monitoring import init_monitoring, track_event, track_error
from opc_manager.error_handler import ErrorHandler, UserFriendlyError

logger = logging.getLogger(__name__)

init_monitoring()

DELIVERABLES_DIR = os.path.join(_WORKSPACE_DIR, "deliverables")
os.makedirs(DELIVERABLES_DIR, exist_ok=True)

for _subdir in [
    "data/knowledge", "data/notifications", "data/custom_skills",
    "data/marketplace", "data/feedback", "data/consensus_logs",
    "data/llm_cache", "data/schedules", "data/completions",
    "data/context", "data/checkpoints", "data/loop_progress",
    "data/workflows", "logs", "output",
]:
    os.makedirs(os.path.join(_WORKSPACE_DIR, _subdir), exist_ok=True)

CHAT_HISTORY_FILE = os.path.join(_WORKSPACE_DIR, "data", "chat_history.json")

# TODO(ST-01): 考虑将此文件拆分为以下模块：
# - chat_history.py: _save_chat_history, _load_chat_history
# - api_helpers.py: _has_api_key, _get_export_bytes
# - ui_components.py: _render_export_buttons
# - safe_wrappers.py: safe_detect, safe_get_persona, safe_track_flywheel
# - task_executor.py: execute_with_agent_loop, execute_task_and_deliver, _async_execute_task
# - page_tabs.py: 各个tab页面的渲染函数


def _save_chat_history():
    try:
        os.makedirs(os.path.dirname(CHAT_HISTORY_FILE), exist_ok=True)
        with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(st.session_state.messages, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Failed to save chat history: %s", e)


def _load_chat_history():
    try:
        if os.path.exists(CHAT_HISTORY_FILE):
            with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def _has_api_key():
    """检查是否配置了有效的API Key（排除空格-only值）"""
    return bool(
        (os.environ.get("MOKA_API_KEY") or "").strip()
        or (os.environ.get("GLM_API_KEY") or "").strip()
        or (os.environ.get("OPENAI_API_KEY") or "").strip()
    )


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


def _render_batch_export_section():
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
            _execute_batch_export(export_format)


def _execute_batch_export(format_name: str):
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


st.set_page_config(
    page_title="一人公司助手",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "initialized" not in st.session_state:
    """首次访问初始化所有session_state变量

    设计意图：Streamlit的session_state在页面刷新后会重置，
    此处用"initialized"标志位避免重复初始化覆盖已有数据。
    """
    st.session_state.initialized = True
    saved_messages = _load_chat_history()
    st.session_state.messages = saved_messages if saved_messages else []
    st.session_state.deliverables = []
    st.session_state.scenario_count = 0
    st.session_state.detected_type = None
    st.session_state.detected_name = None
    st.session_state.onboarding_complete = False
    st.session_state.onboarding_step = 0
    st.session_state.quality_feedback = {}
    st.session_state.flywheel_scores = {
        "内容质量": 0,
        "受众增长": 0,
        "变现能力": 0,
        "跨域推广": 0,
        "生态协同": 0,
    }
    st.session_state.flywheel_level = 1
    st.session_state.achievements = []
    from opc_manager.async_executor import AsyncTaskExecutor
    from opc_manager.session_context import SessionContextManager

    st.session_state.session_ctx = SessionContextManager(max_turns=20)
    st.session_state.async_executor = AsyncTaskExecutor(
        max_concurrent=3,
        default_timeout=120,
        save_callback=lambda *a, **kw: save_deliverable(*a, **kw),
        max_retries=2,
        retry_backoff_base=5.0,
        zombie_check_interval=30,
        persist_dir="data",
    )
    import atexit
    atexit.register(lambda: st.session_state.async_executor.shutdown() if hasattr(st.session_state, 'async_executor') else None)
    logger.debug("[frontend] AsyncTaskExecutor 初始化完成 (max_concurrent=3)")

    if os.path.exists(DELIVERABLES_DIR):
        disk_files = [f for f in os.listdir(DELIVERABLES_DIR) if f.endswith(".md")]
        existing_names = {d.get("filename", "") for d in st.session_state.deliverables}
        for f in sorted(disk_files, reverse=True):
            if f not in existing_names:
                fp = os.path.join(DELIVERABLES_DIR, f)
                size_kb = round(os.path.getsize(fp) / 1024, 1)
                parts = f.replace(".md", "").split("_", 3)
                st.session_state.deliverables.append(
                    {
                        "filename": f,
                        "filepath": fp,
                        "prompt": (
                            parts[3]
                            if len(parts) > 3
                            else (parts[2] if len(parts) > 2 else "历史任务")
                        ),
                        "task_type": (
                            parts[2]
                            if len(parts) > 3
                            else (parts[1] if len(parts) > 1 else "unknown")
                        ),
                        "created_at": (
                            f"{parts[0][:4]}-{parts[0][4:6]}-{parts[0][6:8]} {parts[1][:2]}:{parts[1][2:4]}:{parts[1][4:6]}"
                            if len(parts) > 3
                            and len(parts[0]) >= 8
                            and len(parts[1]) >= 6
                            else (
                                f"{parts[0][:4]}-{parts[0][4:6]}-{parts[0][6:8]}"
                                if len(parts) > 0 and len(parts[0]) >= 8
                                else ""
                            )
                        ),
                        "size_kb": size_kb,
                    }
                )
        if disk_files:
            logger.debug("[frontend] 从磁盘恢复了 %d 个成果物记录", len(disk_files))

# v0.2.0: Onboarding detection for first-time users
try:
    from opc_manager.onboarding import get_onboarding
    onboard = get_onboarding()
    if not onboard.is_completed:
        _show_onboarding_overlay()
except ImportError:
    pass
except Exception as e:
    logger.warning("[frontend] Onboarding check failed: %s", e)

PERSONA_MAP = {
    """业务类型 → (显示名称, 风格描述) 映射表
    
    用于侧边栏展示当前识别到的用户业务类型对应的人格名称。
    与PersonaManager.get_persona()的结果配合使用。
    """
    "content_creator": ("✍️ 内容小助理", "轻松活泼"),
    "digital_product": ("💰 产品顾问", "专业亲切"),
    "ai_tool_builder": ("🤖 技术合伙人", "技术专业"),
    "consultant": ("💼 咨询顾问", "正式严谨"),
    "ecommerce": ("🛒 电商小管家", "干练务实"),
    "creative_work": ("🎨 创意搭子", "文艺优雅"),
}

TYPE_DISPLAY = {
    """业务类型中文显示名映射 — 用于成果物页面的类型标签展示"""
    "content_creator": "内容创作者",
    "digital_product": "数字产品开发者",
    "ai_tool_builder": "AI工具开发者",
    "consultant": "咨询顾问",
    "ecommerce": "电商运营者",
    "creative_work": "创意工作者",
}

# 9个预设场景快捷按钮配置
# 每个场景点击后会在对话中插入对应的自然语言指令，
# 由TaskEngineV3的IntentClassifier识别为SCENARIO_BASED类型，
# 再由ScenarioEngineV2编排多步骤工作流执行。
# 扩展方式：在此列表中添加新条目即可自动渲染按钮。
# 场景的具体工作流定义在scenario_engine_v2.py中。

SCENARIOS_CORE = [
    {
        "id": "content_creation",
        "icon": "✍️",
        "title": "内容创作",
        "desc": "文章/报告/日历规划",
        "coverage": ["内容日历规划", "报告撰写"],
        "prompt": "帮我规划下周的内容日历和选题",
    },
    {
        "id": "product_launch",
        "icon": "🚀",
        "title": "产品发布",
        "desc": "定价/上线/推广方案",
        "coverage": ["数字产品发布", "新产品发布"],
        "prompt": "帮我制定新产品发布的完整方案",
    },
    {
        "id": "data_analysis",
        "icon": "📊",
        "title": "数据分析",
        "desc": "反馈分析/运营优化",
        "coverage": ["用户反馈分析", "电商运营优化"],
        "prompt": "帮我分析用户反馈并提炼行动项",
    },
    {
        "id": "project_mgmt",
        "icon": "📋",
        "title": "项目管理",
        "desc": "提案/交付/会议组织",
        "coverage": ["咨询提案撰写", "项目交付物整理", "会议组织"],
        "prompt": "帮我撰写一份专业咨询提案",
    },
]

SCENARIOS_MORE = [
    {
        "id": "content_calendar",
        "icon": "📅",
        "title": "内容日历规划",
        "desc": "帮你规划下周的选题和发布节奏",
        "prompt": "帮我规划下周的内容日历和选题排期",
    },
    {
        "id": "digital_product_launch",
        "icon": "🎯",
        "title": "数字产品发布",
        "desc": "从定价到上线的完整方案",
        "prompt": "帮我制定数字产品的发布方案，包括定价和推广",
    },
    {
        "id": "feedback_analysis",
        "icon": "💬",
        "title": "用户反馈分析",
        "desc": "从用户声音中提炼行动项",
        "prompt": "帮我分析用户反馈，提炼关键行动项",
    },
    {
        "id": "consulting_proposal",
        "icon": "📝",
        "title": "咨询提案撰写",
        "desc": "专业提案框架+行业洞察",
        "prompt": "帮我撰写一份专业咨询提案",
    },
    {
        "id": "ecommerce_ops",
        "icon": "🛒",
        "title": "电商运营优化",
        "desc": "GMV提升策略与执行清单",
        "prompt": "帮我优化电商运营，提升GMV",
    },
    {
        "id": "project_deliverable",
        "icon": "📦",
        "title": "项目交付物整理",
        "desc": "交付物清单+质量检查",
        "prompt": "帮我整理项目交付物并做质量检查",
    },
    {
        "id": "write_report",
        "icon": "📄",
        "title": "报告撰写",
        "desc": "结构化报告+数据支撑",
        "prompt": "帮我写一份结构化的分析报告",
    },
    {
        "id": "organize_meeting",
        "icon": "🤝",
        "title": "会议组织",
        "desc": "议程+纪要+跟进清单",
        "prompt": "帮我组织一次项目会议",
    },
]


def safe_detect(prompt_text):
    """安全包装的业务类型检测 — 防止后端异常导致前端崩溃

    设计意图：
    BusinessTypeDetectorV2.detect()可能因模型未初始化等原因抛出异常，
    如果直接调用会导致整个Streamlit回调崩溃（WebSocket断连）。
    此函数捕获所有异常并返回安全的默认值(content_creator)。

    Returns:
        (type_value, confidence, method): 业务类型枚举值/置信度/检测方法名
    """
    try:
        from opc_manager.business_type_detector_v2 import BusinessTypeDetectorV2

        if "biz_detector" not in st.session_state:
            st.session_state.biz_detector = BusinessTypeDetectorV2()
        result = st.session_state.biz_detector.detect(prompt_text)
        if result and result.business_type:
            return result.business_type.value, result.confidence, result.method
        return "content_creator", 0.5, "default"
    except Exception as e:
        logger.debug("[frontend] detect error: %s", e)
        return "content_creator", 0.5, "fallback"


def safe_get_persona(type_value):
    """安全包装的人格信息获取 — 防止get_persona返回None导致AttributeError

    v3.0历史问题：当confidence较低时get_persona()返回None，
    直接访问persona.display_name会导致AttributeError崩溃。
    此函数确保始终返回有效的(name, tone)元组。

    Fallback策略:
    1. 尝试从PersonaManager获取完整persona对象
    2. 失败则从PERSONA_MAP静态映射获取名称
    3. 最终fallback为"智能助手"
    """
    try:
        from opc_manager.persona_manager import PersonaManager
        from opc_manager.business_types import BusinessType

        if "persona_manager" not in st.session_state:
            st.session_state.persona_manager = PersonaManager()
        pm = st.session_state.persona_manager
        persona = pm.get_persona(business_type=BusinessType(type_value))
        if persona:
            return persona.display_name, persona.style_overrides.get("tone", "专业温暖")
        return "智能助手", "专业温暖"
    except Exception as e:
        logger.debug("[frontend] persona error: %s", e)
        name = PERSONA_MAP.get(type_value, ("智能助手", "专业"))[0]
        return name, "专业"


def safe_track_flywheel(type_value):
    """安全包装的成长飞轮记录 — 记录用户互动并更新飞轮分数

    功能说明：
    - 每次用户输入后调用，记录到FlywheelTracker
    - 根据业务类型增加对应维度分数（每次+8分）
    - 根据平均分数计算飞轮等级（L1探索者/L2连接者/L3生态构建者）
    - 分数上限100，等级根据阈值35/60判定

    维度映射规则：
    - content_creator/creative_work → 内容质量
    - digital_product/ecommerce → 变现能力
    - ai_tool_builder → 跨域推广
    - consultant → 受众增长
    - 其他 → 默认内容质量
    """
    try:
        from opc_manager.flywheel_tracker import FlywheelTracker
        from opc_manager.business_types import BusinessType

        if "flywheel_tracker" not in st.session_state:
            st.session_state.flywheel_tracker = FlywheelTracker()
        tracker = st.session_state.flywheel_tracker
        bt = BusinessType(type_value)
        tracker.record_scenario_completion("web_user", "chat_interaction", bt)
        st.session_state.scenario_count += 1

        scores = st.session_state.flywheel_scores
        dim_map = {
            "content_creator": "内容质量",
            "digital_product": "变现能力",
            "ai_tool_builder": "跨域推广",
            "consultant": "受众增长",
            "ecommerce": "变现能力",
            "creative_work": "内容质量",
        }
        dim_key = dim_map.get(type_value, "内容质量")
        scores[dim_key] = min(100, scores.get(dim_key, 0) + 8)

        avg = sum(scores.values()) / len(scores) if scores else 0
        st.session_state.flywheel_level = 3 if avg >= 60 else (2 if avg >= 35 else 1)
        return True
    except Exception as e:
        logger.debug("[frontend] flywheel error: %s", e)
        st.session_state.scenario_count += 1
        return False


def generate_filename(prompt: str, task_type: str) -> str:
    """生成唯一的成果物文件名

    格式: {YYYYMMDD_HHMMSS}_{task_type}_{prompt摘要30字符}.md

    安全措施：
    - prompt截取前30字符防止文件名过长
    - 替换所有文件系统非法字符为安全字符
    - 使用时间戳保证唯一性（同一秒内多次请求仍可区分）
    """
    safe_name = (
        re.sub(r'[\\/*?:"<>|\n\r\t]', "", prompt[:30])
        .replace(" ", "_")
        .replace("/", "-")
    ) or "task"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{task_type}_{safe_name}.md"


def save_deliverable(
    content: str, prompt: str, task_type: str, meta: dict = None
) -> tuple:
    """将生成的成果物内容写入文件系统并注册到session_state

    Returns:
        tuple: (filepath, deliverable_record)
    """
    filename = generate_filename(prompt, task_type)
    filepath = os.path.join(DELIVERABLES_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    deliverable_record = {
        "filename": filename,
        "filepath": filepath,
        "prompt": prompt[:50],
        "task_type": task_type,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "size_kb": round(len(content.encode("utf-8")) / 1024, 1),
        "meta": meta or {},
    }

    logger.debug("[frontend] 成果物已保存: %s (%sKB)", filepath, deliverable_record['size_kb'])
    return filepath, deliverable_record


def execute_with_agent_loop(prompt, session_ctx=None, business_type=None):
    """Execute task via AgentLoop (Three-Sage Architecture) with fallback to TaskEngineV3

    Returns:
        Same format as execute_task_and_deliver:
        (content_with_meta, success, filepath, task_type_value, deliverable_record)
    """
    import os
    import asyncio

    use_agent_loop = st.session_state.get("exec_mode", "质量模式") == "质量模式"

    if not use_agent_loop:
        return execute_task_and_deliver(prompt, session_ctx=session_ctx, business_type=business_type)

    try:
        from opc_manager.agent_loop import AgentLoop
        from opc_manager.task_engine_adapter import TaskEngineAdapter
        from opc_manager.task_engine_v3 import task_engine_v3

        if "agent_loop" not in st.session_state:
            adapter = TaskEngineAdapter(task_engine=task_engine_v3)
            from opc_manager.simple_llm_service import SimpleLLMService
            from opc_manager.skill_registry import SkillRegistry
            simple_llm = SimpleLLMService()
            skill_registry = SkillRegistry()
            st.session_state.agent_loop = AgentLoop(
                task_engine_adapter=adapter, llm_service=simple_llm, skill_registry=skill_registry
            )
        agent_loop = st.session_state.agent_loop

        loop = asyncio.new_event_loop()
        try:
            result_dict = loop.run_until_complete(
                agent_loop.run(prompt, session_id=getattr(session_ctx, '_session_id', None) if session_ctx else None)
            )
            pending = asyncio.all_tasks(loop)
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        finally:
            loop.close()

        if not result_dict.get("success"):
            logger.warning("[frontend] AgentLoop执行失败，降级到TaskEngineV3")
            return execute_task_and_deliver(prompt, session_ctx=session_ctx, business_type=business_type)

        from opc_manager.task_engine_adapter import TaskEngineAdapter as TEA
        task_result = TEA.dict_to_task_result(result_dict)

        if not task_result.content:
            results = result_dict.get("results", [])
            if results:
                last = results[-1]
                data = last.get("data", {})
                if isinstance(data, dict):
                    task_result.content = data.get("content", "")
                elif isinstance(data, str):
                    task_result.content = data

        if not task_result.content:
            logger.warning("[frontend] AgentLoop返回空内容，降级到TaskEngineV3")
            return execute_task_and_deliver(prompt, session_ctx=session_ctx, business_type=business_type)

        from opc_manager.task_engine_v3 import TaskType
        if task_result.task_type == TaskType.GENERAL_CHAT and len(task_result.content) < 300:
            return task_result.content, True, None, "general_chat", None

        meta_lines = []
        if task_result.execution_time_ms:
            meta_lines.append(f"⏱️ 执行耗时: {task_result.execution_time_ms:.0f}ms")
        type_labels = {
            TaskType.INFO_COLLECTION: "🔍 信息收集",
            TaskType.CONTENT_GENERATION: "✍️ 内容生成",
            TaskType.DATA_ANALYSIS: "📊 数据分析",
            TaskType.SCENARIO_BASED: "🎯 场景工作流",
            TaskType.GENERAL_CHAT: "💬 智能对话",
        }
        task_type_label = type_labels.get(task_result.task_type, "通用")
        meta_lines.append(f"📌 任务类型: {task_type_label}")
        meta_lines.append("🧠 三贤者架构执行")
        if task_result.sources:
            meta_lines.append(f"🔗 信息来源: {len(task_result.sources)} 条")

        meta_str = "\n".join(meta_lines)
        content_with_meta = f"{task_result.content}\n\n---\n*{meta_str}*"

        filepath, deliverable_record = save_deliverable(
            content=content_with_meta,
            prompt=prompt,
            task_type=task_result.task_type.value,
            meta={
                "sources_count": len(task_result.sources) if task_result.sources else 0,
                "execution_time_ms": task_result.execution_time_ms,
                "success": task_result.success,
                "agent_loop": True,
            },
        )

        return content_with_meta, task_result.success, filepath, task_result.task_type.value, deliverable_record

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.warning("[frontend] AgentLoop异常，降级到TaskEngineV3: %s\n%s", e, tb)
        return execute_task_and_deliver(prompt, session_ctx=session_ctx, business_type=business_type)


def execute_task_and_deliver(prompt, session_ctx=None, business_type=None):
    """Execute task pipeline — from user input to file delivery

    Args:
        prompt: User input text
        session_ctx: SessionContextManager instance (passed from main thread)
        business_type: Detected business type (passed from main thread)

    Returns:
        (content_with_meta, success, filepath, task_type_value, deliverable_record)
    """
    try:
        logger.debug("[frontend] 开始执行任务: %s", prompt[:50])
        from opc_manager.task_engine_v3 import task_engine_v3, TaskType

        engine = task_engine_v3

        result = engine.execute(
            prompt,
            session_ctx=session_ctx,
            business_type=business_type,
        )
        logger.debug(
            f"[frontend] 任务执行完成: success={result.success}, content_len={len(result.content) if result.content else 0}"
        )

        if not result.success:
            logger.debug("[frontend] 任务标记为失败: %s", result.error)
            return None, False, None, None, None

        if not result.content:
            logger.debug("[frontend] 内容为空!")
            return None, False, None, None, None

        if result.task_type == TaskType.GENERAL_CHAT and len(result.content) < 300:
            logger.debug("[frontend] 闲聊/短回复，不生成成果物文件")
            return result.content, True, None, "general_chat", None

        meta_lines = []
        if result.execution_time_ms:
            meta_lines.append(f"⏱️ 执行耗时: {result.execution_time_ms:.0f}ms")
        type_labels = {
            TaskType.INFO_COLLECTION: "🔍 信息收集",
            TaskType.CONTENT_GENERATION: "✍️ 内容生成",
            TaskType.DATA_ANALYSIS: "📊 数据分析",
            TaskType.SCENARIO_BASED: "🎯 场景工作流",
            TaskType.GENERAL_CHAT: "💬 智能对话",
        }
        task_type_label = type_labels.get(result.task_type, "通用")
        meta_lines.append(f"📌 任务类型: {task_type_label}")
        if result.sources:
            meta_lines.append(f"🔗 信息来源: {len(result.sources)} 条")
        if result.deliverable_format:
            meta_lines.append(f"📦 格式: {result.deliverable_format}")

        meta_str = "\n".join(meta_lines)

        has_api_key = _has_api_key()
        mode_tag = ""
        if not has_api_key:
            mode_tag = "\n\n> ⚠️ **当前为模板模式输出** — 配置API Key后可获得AI增强内容（质量提升5倍+）"
        else:
            from opc_manager.simple_llm_service import SimpleLLMService
            svc = SimpleLLMService()
            if svc.is_available():
                mode_tag = "\n\n> 🟢 **AI增强模式** — 三贤者架构（策略脑+执行脑+反思脑）LLM驱动"
            else:
                mode_tag = "\n\n> 🟡 **规则引擎模式** — LLM服务不可用，使用关键词匹配+规则评分"

        content_with_meta = f"{result.content}{mode_tag}\n\n---\n*{meta_str}*"

        logger.debug("[frontend] 准备保存文件...")
        filepath, deliverable_record = save_deliverable(
            content=content_with_meta,
            prompt=prompt,
            task_type=result.task_type.value,
            meta={
                "sources_count": len(result.sources) if result.sources else 0,
                "format": result.deliverable_format,
                "execution_time_ms": result.execution_time_ms,
                "success": result.success,
            },
        )
        logger.debug("[frontend] 文件已保存: %s", filepath)

        return content_with_meta, result.success, filepath, result.task_type.value, deliverable_record

    except Exception as e:
        import traceback

        tb = traceback.format_exc()
        logger.debug("[frontend] execute_task_and_deliver error: %s\n%s", e, tb)
        return None, False, None, None, None


def _async_execute_task(prompt: str, cancel_event, session_ctx=None, business_type=None) -> dict:
    """Async execution wrapper for AsyncTaskExecutor background thread

    Thread safety: session_ctx and business_type are passed from the main thread
    as arguments, avoiding st.session_state access from background threads.
    The deliverable_record is returned in the result dict for the main thread
    to register in st.session_state.deliverables.

    Args:
        prompt: User input text
        cancel_event: threading.Event for cancellation
        session_ctx: SessionContextManager (from main thread)
        business_type: Detected business type (from main thread)

    Returns:
        dict with keys: content, success, filepath, task_type, error, deliverable_record
    """
    try:
        logger.debug("[frontend-async] 开始后台执行: %s", prompt[:50])
        content, success, filepath, task_type, deliverable_record = execute_with_agent_loop(
            prompt, session_ctx=session_ctx, business_type=business_type
        )
        logger.debug(
            f"[frontend-async] 执行完成: success={success}, has_content={bool(content)}"
        )

        if content and success:
            _export_formats = []
            if task_type:
                TYPE_EXPORT_MAP = {
                    "content_generation": ["pdf", "docx", "md"],
                    "data_analysis": ["pdf", "xlsx", "md"],
                    "scenario_based": ["pdf", "docx", "xlsx", "md"],
                    "info_collection": ["pdf", "md"],
                }
                _export_formats = TYPE_EXPORT_MAP.get(task_type, ["md"])
            return {
                "content": content,
                "success": True,
                "filepath": filepath,
                "task_type": task_type,
                "error": None,
                "deliverable_record": deliverable_record,
                "_exportable_formats": _export_formats,
            }
        else:
            return {
                "content": None,
                "success": False,
                "filepath": None,
                "task_type": None,
                "error": "任务执行未返回有效结果",
                "deliverable_record": None,
            }

    except Exception as e:
        import traceback

        tb = traceback.format_exc()
        logger.debug("[frontend-async] 执行异常: %s\n%s", e, tb)
        return {
            "content": None,
            "success": False,
            "filepath": None,
            "task_type": None,
            "error": str(e),
            "deliverable_record": None,
        }


with st.sidebar:
    """侧边栏 — 导航+状态展示"""
    st.text_input("🔍 Cmd+K 搜索...", key="sidebar_global_search", label_visibility="collapsed")

    if st.session_state.get("sidebar_global_search", "").strip():
        query = st.session_state.sidebar_global_search.strip()
        if len(query) >= 2:
            with st.expander(f"🔍 搜索结果 ({query})", expanded=True):
                results = _execute_global_search(query)
                if results:
                    st.success(f"找到 {len(results)} 条结果")
                    for r in results[:8]:
                        st.markdown(f"**{r.get('title', '-')}**")
                        st.caption(r.get("summary", "")[:80])
                        st.divider()
                else:
                    st.info("未找到相关内容")

    st.markdown("### 🚀 一人公司助手")
    from opc_manager.i18n import t as _t
    page = st.radio(
        "", [_t("nav_chat"), _t("nav_deliverables"), "📈 Dashboard", _t("nav_growth"), _t("nav_marketplace"), _t("nav_settings")], label_visibility="collapsed"
    )

    if st.session_state.detected_type:
        pinfo = PERSONA_MAP.get(st.session_state.detected_type, ("助手", ""))
        st.divider()
        st.markdown(f"**当前人格**\n{pinfo[0]}")
        st.caption(f"风格：{pinfo[1]}")

    if st.session_state.deliverables:
        st.divider()
        st.markdown(f"**📦 已生成 {len(st.session_state.deliverables)} 个成果物**")

    st.divider()
    if "exec_mode" not in st.session_state:
        st.session_state.exec_mode = "质量模式"
    exec_mode = st.radio(
        "🧠 执行模式",
        ["质量模式", "快速模式"],
        index=0 if st.session_state.exec_mode == "质量模式" else 1,
        help="质量模式：三贤者架构（策略脑+执行脑+反思脑），自动修正低质量结果\n快速模式：直接执行，跳过反思评估"
    )
    st.session_state.exec_mode = exec_mode

    st.divider()
    if st.button("🔧 技能编辑器", use_container_width=True):
        st.session_state.show_skill_editor = not st.session_state.get("show_skill_editor", False)

    if st.session_state.get("show_skill_editor", False):
        st.markdown("#### 技能编辑器")
        from opc_manager.skill_editor import SkillEditor, CustomSkill, SkillParameter, ParameterType, OutputFormat
        editor = SkillEditor()
        with st.form("create_skill_form"):
            sk_name = st.text_input("技能名称", key="sk_name")
            sk_desc = st.text_input("描述", key="sk_desc")
            sk_cat = st.selectbox("分类", ["custom", "analysis", "creation", "search", "operation"], key="sk_cat")
            sk_output = st.selectbox("输出格式", ["markdown", "json", "text"], key="sk_output")
            sk_template = st.text_area("模板 (用{{变量名}}占位)", key="sk_template", height=100)
            submitted = st.form_submit_button("创建技能")
            if submitted and sk_name:
                import re
                if not re.match(r'^[\w\u4e00-\u9fff\s-]+$', sk_name) or len(sk_name) > 50:
                    st.error("技能名称只能包含字母、数字、中文、下划线、连字符，且不超过50字符")
                elif len(sk_desc) > 500:
                    st.error("描述不能超过500字符")
                else:
                    skill = CustomSkill(
                        skill_id=f"custom_{sk_name.lower().replace(' ', '_')}",
                        name=sk_name, description=sk_desc, category=sk_cat,
                        output_format=OutputFormat(sk_output), template=sk_template,
                    )
                    result = editor.create_skill(skill)
                    if result["success"]:
                        st.success(f"技能 '{sk_name}' 创建成功！")
                    else:
                        st.error(result.get("error", "创建失败"))
        skills = editor.list_skills()
        if skills:
            st.markdown(f"**已创建 {len(skills)} 个自定义技能**")
            for s in skills[:5]:
                st.markdown(f"- {s['name']} ({s['skill_id']})")

    st.divider()
    if st.button("🏪 技能市场", use_container_width=True):
        st.session_state.show_marketplace = not st.session_state.get("show_marketplace", False)

    if st.session_state.get("show_marketplace", False):
        st.markdown("#### 技能市场")
        from opc_manager.skill_marketplace import SkillMarketplace
        mp = SkillMarketplace()
        stats = mp.get_stats()
        st.caption(f"📊 共 {stats['total_skills']} 个技能 | ✅ 已审核 {stats['approved_skills']} | ⏳ 待审核 {stats['pending_skills']}")
        categories = mp.list_categories()
        if categories:
            sel_cat = st.selectbox("按分类筛选", ["全部"] + categories, key="mp_cat")
            discovered = mp.discover_skills(category=sel_cat if sel_cat != "全部" else None)
        else:
            discovered = mp.discover_skills()
        if discovered:
            for sk in discovered[:10]:
                st.markdown(f"**{sk['name']}** `v{sk['version']}` — {sk['description'][:80]}")
                st.caption(f"分类: {sk['category']} | 作者: {sk['author']}")
        else:
            st.info("暂无已审核的技能")

    st.divider()
    if st.button("📊 性能监控", use_container_width=True):
        st.session_state.show_perf = not st.session_state.get("show_perf", False)

    if st.session_state.get("show_perf", False):
        st.markdown("#### 性能监控")
        from opc_manager.performance_monitor import performance_monitor
        stats = performance_monitor.get_stats()
        sla = performance_monitor.check_sla()
        total = stats.get("total_operations", 0)
        st.metric("总操作数", total)
        sla_color = "🟢" if all(sla.values()) else "🔴"
        st.markdown(f"**SLA状态**: {sla_color} 单次请求{'✅' if sla.get('single_request') else '❌'} | 反思循环{'✅' if sla.get('reflect_loop') else '❌'}")
        cache = stats.get("cache", {})
        if cache:
            st.caption(f"LLM缓存: 命中率 {cache.get('hit_rate', 0):.0%} | 大小 {cache.get('size', 0)}/{cache.get('max_size', 0)}")
        ops = stats.get("operations", {})
        if ops:
            for op, op_stats in ops.items():
                st.caption(f"  {op}: 平均{op_stats['avg_ms']:.0f}ms | P95 {op_stats.get('p95_ms', 0):.0f}ms")

    st.divider()

    _render_undo_panel()

    st.divider()

    _render_theme_selector()
    _render_language_selector()
    _render_shortcuts_help()

    st.divider()
    from opc_manager.version import get_version

    st.caption(f"OPC-Agents v{get_version()}")


if page == "💬 对话":
    """主对话页面 — 用户交互的核心界面

    空状态: 展示欢迎语 + 9个场景快捷按钮
    有消息: 渲染历史消息（含下载按钮） + chat_input输入框
    输入后:
      ① safe_detect → 意图识别（进度标签更新）
      ② 人格设置 + 飞轮追踪
      ③ execute_task_and_deliver → 核心执行
      ④ 成功: 显示结果 + 下载按钮 + 追加到消息历史
      ⑤ 失败: 区分超时/其他错误，给出不同提示
    """
    if len(st.session_state.messages) > 0:
        st.caption(
            "💡 对话历史已自动保存 · 成果物文件可在「📁 成果物」标签页查看和下载"
        )
    if len(st.session_state.messages) == 0:
        st.markdown("## 👋 你好，一人公司创业者！")
        st.markdown(
            "我是你的**任务执行与成果交付助手**。"
            "**告诉我你要什么结果，我直接做完并交付文件给你** — 可下载、可保存、可复用。"
        )

        if not st.session_state.get("onboarding_complete", False):
            onboarding_step = st.session_state.get("onboarding_step", 0)
            with st.container():
                if onboarding_step == 0:
                    st.info("👋 **欢迎使用 OPC-Agents！** 让我用 30 秒带你快速上手")
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        if st.button("▶️ 开始快速引导", type="primary", use_container_width=True):
                            st.session_state.onboarding_step = 1
                            st.rerun()
                    with col2:
                        if st.button("⏭️ 跳过引导，直接使用"):
                            st.session_state.onboarding_complete = True
                            st.rerun()
                elif onboarding_step == 1:
                    st.success("✅ **第1步/3步：输入你的需求**\n\n在下方输入框中，用自然语言描述你要什么结果。比如：\"分析电商行业竞争格局\"")
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        if st.button("下一步 →", type="primary", use_container_width=True):
                            st.session_state.onboarding_step = 2
                            st.rerun()
                    with col2:
                        if st.button("跳过引导"):
                            st.session_state.onboarding_complete = True
                            st.rerun()
                elif onboarding_step == 2:
                    st.success("✅ **第2步/3步：等待AI执行**\n\n提交后系统会自动搜索资料、生成内容。你会看到实时进度和预估时间，也可以随时取消。")
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        if st.button("下一步 →", type="primary", use_container_width=True):
                            st.session_state.onboarding_step = 3
                            st.rerun()
                    with col2:
                        if st.button("跳过引导"):
                            st.session_state.onboarding_complete = True
                            st.rerun()
                elif onboarding_step == 3:
                    st.success("✅ **第3步/3步：下载成果物**\n\n生成完成后，你可以直接下载 .md 文件，也可以追问\"补充XX\"让AI继续完善。")
                    if st.button("🎉 完成！开始使用", type="primary", use_container_width=True):
                        st.session_state.onboarding_complete = True
                        st.rerun()

        st.markdown(
            "**使用步骤**：① 在下方输入需求或点击场景按钮 → ② 等待AI执行 → ③ 下载成果物文件"
        )

        has_api_key = _has_api_key()
        if not has_api_key:
            st.warning(
                "⚠️ **当前为模板模式** — 配置API Key后可获得AI增强内容（质量提升5倍+）"
            )
            with st.expander("📖 如何获取API Key？", expanded=True):
                st.markdown(
                    """
**3步配置，2分钟搞定：**

1. 访问 [MOKA AI](https://moka-ai.com) 注册账号并获取API Key
2. 在项目根目录创建 `.env` 文件（可从 `.env.example` 复制）
3. 填入: `MOKA_API_KEY=sk-your-key-here`

配置后重启应用即可。**不配置也能用**，只是输出为模板填充内容。
"""
                )
        else:
            st.success("✅ AI增强模式已就绪")

        st.markdown("### 🎯 我能直接帮你完成并交付：")

        st.markdown("**核心场景（最常用）**")
        core_cols = st.columns(2)
        for i, sc in enumerate(SCENARIOS_CORE):
            with core_cols[i % 2]:
                if st.button(
                    f"{sc['icon']} **{sc['title']}**\n\n📌 {sc['desc']}\n\n_涵盖: {', '.join(sc['coverage'])}_",
                    key=f"core_{sc['id']}",
                    use_container_width=True,
                ):
                    st.session_state.pending_prompt = sc.get(
                        "prompt", f"帮我执行「{sc['title']}」相关任务"
                    )
                    st.rerun()

        with st.expander("🔍 更多具体场景（8个）", expanded=False):
            st.markdown("**选择一个具体的场景模板：**")
            more_cols = st.columns(2)
            for i, sc in enumerate(SCENARIOS_MORE):
                with more_cols[i % 2]:
                    if st.button(
                        f"{sc['icon']} {sc['title']}\n_{sc['desc']}",
                        key=f"more_{sc['id']}",
                        use_container_width=True,
                    ):
                        st.session_state.pending_prompt = sc.get(
                            "prompt", f"帮我执行「{sc['title']}」场景"
                        )
                        st.rerun()

        st.divider()
        st.caption("💡 输入需求 → 执行任务 → 生成文件 → 立即下载")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("deliverable_path"):
                real_path = os.path.realpath(msg["deliverable_path"])
                if not real_path.startswith(os.path.realpath(DELIVERABLES_DIR)):
                    continue
                file_content = None
                if os.path.exists(real_path):
                    col_dl, col_info = st.columns([1, 3])
                    with col_dl:
                        with open(real_path, "r", encoding="utf-8") as f:
                            file_content = f.read()
                    st.download_button(
                        label="📥 下载文件",
                        data=file_content,
                        file_name=os.path.basename(msg["deliverable_path"]),
                        mime="text/markdown",
                        key=f"dl_{msg.get('deliverable_id', id(msg))}",
                        use_container_width=True,
                    )
                if file_content is not None:
                    with col_info:
                        size_kb = round(len(file_content.encode("utf-8")) / 1024, 1)
                        st.caption(
                            f"📄 {os.path.basename(msg['deliverable_path'])} ({size_kb}KB)"
                        )

    if len(st.session_state.messages) == 0:
        with st.container():
            st.markdown("### 💬 试试问我：")
            example_cols = st.columns(3)
            EXAMPLE_QUERIES = [
                ("📊 竞品分析", "分析电商行业竞争格局，帮我了解主要玩家和差异化策略"),
                ("📋 营销方案", "帮我制定Q2社交媒体营销方案，预算5万以内"),
                ("🔍 行业趋势", "收集2026年AI Agent行业最新趋势和投资动态"),
            ]
            for i, (title, query) in enumerate(EXAMPLE_QUERIES):
                with example_cols[i]:
                    if st.button(title, key=f"example_{i}", use_container_width=True):
                        st.session_state.pending_prompt = query
                        st.rerun()

    pending = st.session_state.pop("pending_prompt", None)
    if pending:
        prompt = pending
        st.session_state.messages.append({"role": "user", "content": prompt})
        _save_chat_history()
        with st.chat_message("user"):
            st.markdown(prompt)
    elif prompt := st.chat_input("告诉我你需要什么结果，我直接做完并交付文件..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        _save_chat_history()
        with st.chat_message("user"):
            st.markdown(prompt)
    else:
        prompt = None

    if prompt:

        executor = st.session_state.async_executor
        session_ctx = st.session_state.get("session_ctx")

        is_follow_up = False
        if session_ctx and session_ctx.get_turn_count() > 0:
            from opc_manager.task_engine_v3 import IntentClassifier
            is_follow_up = IntentClassifier.is_follow_up(prompt)
            if is_follow_up:
                st.info("🔄 检测到追问请求 — 系统将基于上次结果继续，而非从头生成")

        detected_type, confidence, method = safe_detect(prompt)
        st.session_state.detected_type = detected_type
        persona_name, persona_tone = safe_get_persona(detected_type)
        st.session_state.detected_name = persona_name
        safe_track_flywheel(detected_type)

        task_id = executor.submit(
            prompt,
            execute_func=_async_execute_task,
            session_ctx=st.session_state.get("session_ctx"),
            business_type=detected_type,
        )

        if not task_id:
            st.error("⚠️ 系统繁忙，请稍后再试（并发任务已达上限）")
            st.stop()

        logger.debug("[frontend] 任务已提交: %s (异步模式%s)", task_id, "，追问模式" if is_follow_up else "")

        with st.chat_message("assistant"):
            status_container = st.status(
                "🚀 任务已提交，正在后台执行...", expanded=True
            )

            cancel_col, _ = st.columns([1, 4])
            with cancel_col:
                if st.button(
                    "❌ 取消任务", key=f"cancel_{task_id}", use_container_width=True
                ):
                    if executor.cancel(task_id):
                        st.warning("⏹️ 任务已取消")
                        st.stop()
                    else:
                        st.error("取消失败（任务可能已完成）")

            EXECUTION_PHASES = [
                (0, 3, "🚀 任务启动", "初始化任务执行环境..."),
                (3, 8, "🔎 信息搜索", "搜索相关参考资料..."),
                (8, 25, "🤖 LLM生成", "AI正在撰写专业内容..."),
                (25, 50, "✍️ 内容润色", "优化输出质量..."),
                (50, 60, "📦 交付准备", "生成可下载文件..."),
            ]

            max_polls = 60
            poll_interval = 1.0
            start_time = time.time()
            progress_placeholder = st.empty()

            for poll_count in range(max_polls):
                task_status = executor.get_status(task_id)
                current_status = task_status.get("status", "unknown")
                elapsed = task_status.get("elapsed", 0)

                if current_status == "pending":
                    if poll_count < 3:
                        status_container.update(label="⏳ 排队中，等待执行...")
                    time.sleep(poll_interval)
                    continue

                elif current_status == "retrying":
                    retry_count = task_status.get("retry_count", 0)
                    max_retries = task_status.get("max_retries", 2)
                    status_container.update(
                        label=f"🔄 自动重试中 ({retry_count}/{max_retries})..."
                    )
                    max_polls += 10
                    time.sleep(poll_interval)
                    continue

                elif current_status == "running":
                    phase_icon, phase_name, phase_hint = "⚡", "执行中", "处理中..."
                    for phase_start, phase_end, icon, hint in EXECUTION_PHASES:
                        if phase_start <= elapsed < phase_end:
                            phase_icon, phase_name, phase_hint = (
                                icon,
                                hint.split("...")[0],
                                hint,
                            )
                            break
                    if elapsed >= 60:
                        phase_icon, phase_name, phase_hint = (
                            "🔄",
                            "深度处理",
                            "内容较长，请耐心等待...",
                        )

                    estimated_total = (
                        max(30, elapsed * 1.5)
                        if elapsed < 10
                        else max(30, elapsed / 0.7)
                    )
                    remaining = max(0, estimated_total - elapsed)
                    progress_pct = min(int((elapsed / estimated_total) * 100), 95)

                    status_container.update(
                        label=f"{phase_icon} {phase_name} ({elapsed:.0f}s / 预计还需{remaining:.0f}s)",
                        state="running",
                    )
                    progress_placeholder.progress(
                        progress_pct / 100.0,
                        text=f"预估进度 {progress_pct}% — {phase_hint} — 已耗时 {elapsed:.0f}s",
                    )

                    session_id = _get_current_session_id()
                    if session_id and session_id != "default":
                        with st.expander("📊 实时执行详情", expanded=False):
                            _render_progress_indicator(session_id)

                    time.sleep(poll_interval)
                    continue

                elif current_status == "done":
                    status_container.update(label="✅ 任务完成", state="complete")

                    track_event(
                        "task_completed",
                        {
                            "mode": "async",
                            "latency_ms": round(task_status.get("elapsed", 0) * 1000),
                        },
                    )

                    result_content = task_status.get("result_content")
                    result_filepath = task_status.get("result_filepath")
                    result_deliverable_record = task_status.get("result_deliverable_record")

                    if result_deliverable_record:
                        st.session_state.deliverables.insert(0, result_deliverable_record)

                    if result_content:
                        st.markdown(result_content)

                        _render_export_buttons(
                            result_content,
                            task_status.get("_exportable_formats", []),
                            key_prefix=f"{int(time.time()*1000)}",
                        )

                        feedback_key = f"fb_{task_id}"
                        safe_task_id = re.sub(r'[^\w-]', '', task_id)
                        if feedback_key not in st.session_state.quality_feedback:
                            fb_cols = st.columns([1, 1, 6])
                            with fb_cols[0]:
                                if st.button("👍 有用", key=f"good_{task_id}"):
                                    st.session_state.quality_feedback[feedback_key] = "good"
                                    try:
                                        os.makedirs(os.path.join(_WORKSPACE_DIR, "data", "feedback"), exist_ok=True)
                                        with open(os.path.join(_WORKSPACE_DIR, "data", "feedback", f"{safe_task_id}.json"), "w") as f:
                                            json.dump({"task_id": task_id, "feedback": "good", "timestamp": time.time()}, f)
                                    except Exception:
                                        pass
                                    st.success("感谢反馈！")
                                    st.rerun()
                            with fb_cols[1]:
                                if st.button("👎 需改进", key=f"bad_{task_id}"):
                                    st.session_state.quality_feedback[feedback_key] = "bad"
                                    try:
                                        os.makedirs(os.path.join(_WORKSPACE_DIR, "data", "feedback"), exist_ok=True)
                                        with open(os.path.join(_WORKSPACE_DIR, "data", "feedback", f"{safe_task_id}.json"), "w") as f:
                                            json.dump({"task_id": task_id, "feedback": "bad", "timestamp": time.time()}, f)
                                    except Exception:
                                        pass
                                    st.info("感谢反馈！我们会持续改进")
                                    st.rerun()
                        elif st.session_state.quality_feedback.get(feedback_key) == "good":
                            st.caption("👍 你觉得这次输出有用")
                        elif st.session_state.quality_feedback.get(feedback_key) == "bad":
                            st.caption("👎 你觉得这次输出需要改进")

                        _render_quick_undo_button(task_id, result_deliverable_record.get("task_type") if result_deliverable_record else None)

                        if result_filepath and os.path.exists(result_filepath):
                            col_dl, col_info = st.columns([1, 3])
                            with col_dl:
                                with open(result_filepath, "r", encoding="utf-8") as f:
                                    file_content = f.read()
                                st.download_button(
                                    label="📥 下载成果物",
                                    data=file_content,
                                    file_name=os.path.basename(result_filepath),
                                    mime="text/markdown",
                                    key=f"dl_async_{int(time.time()*1000)}",
                                    use_container_width=True,
                                    type="primary",
                                )
                            with col_info:
                                size_kb = round(
                                    len(file_content.encode("utf-8")) / 1024, 1
                                )
                                st.success(
                                    f"✅ 已生成: {os.path.basename(result_filepath)} ({size_kb}KB)"
                                )

                        msg_record = {
                            "role": "assistant",
                            "content": result_content,
                            "deliverable_id": f"{int(time.time()*1000)}",
                        }
                        if result_filepath and os.path.exists(result_filepath):
                            msg_record["deliverable_path"] = result_filepath
                        st.session_state.messages.append(msg_record)
                        _save_chat_history()
                    break

                elif current_status == "failed":
                    error_msg = task_status.get("error_message", "未知错误")
                    status_container.update(label="❌ 任务执行失败", state="error")

                    track_error(
                        Exception(error_msg), {"mode": "async"}
                    )

                    FRIENDLY_ERRORS = {
                        "timeout": (
                            "⏰ AI助手思考时间过长",
                            "网络或AI服务响应较慢，请稍后重试。简短的需求通常更快完成。",
                        ),
                        "connection": (
                            "🌐 网络连接中断",
                            "请检查网络连接后重试。如果问题持续，可能是AI服务暂时不可用。",
                        ),
                        "api_key": (
                            "🔑 API Key无效或已过期",
                            "请在.env文件中更新你的API Key，然后重启应用。",
                        ),
                        "incorrect api key": (
                            "🔑 API Key无效或已过期",
                            "请在.env文件中更新你的API Key，然后重启应用。",
                        ),
                        "authentication": (
                            "🔑 认证失败",
                            "API Key可能无效或已过期，请检查配置后重试。",
                        ),
                        "rate_limit": (
                            "🚦 请求过于频繁",
                            "AI服务暂时限流，请等待1-2分钟后重试。",
                        ),
                        "rate limit": (
                            "🚦 请求过于频繁",
                            "AI服务暂时限流，请等待1-2分钟后重试。",
                        ),
                        "429": (
                            "🚦 请求过于频繁",
                            "AI服务暂时限流，请等待1-2分钟后重试。",
                        ),
                        "server_error": (
                            "🔧 AI服务暂时不可用",
                            "服务端正在维护，请稍后重试。系统会自动使用模板模式作为备选。",
                        ),
                        "500": (
                            "🔧 AI服务暂时不可用",
                            "服务端正在维护，请稍后重试。",
                        ),
                        "502": (
                            "🔧 AI服务暂时不可用",
                            "服务端正在维护，请稍后重试。",
                        ),
                        "503": (
                            "🔧 AI服务暂时不可用",
                            "服务端正在维护，请稍后重试。",
                        ),
                    }

                    error_lower = error_msg.lower()
                    friendly_title = "⚠️ 任务执行遇到问题"
                    friendly_hint = "请稍后重试，或换个方式描述你的需求。"

                    for kw, (title, hint) in FRIENDLY_ERRORS.items():
                        if kw in error_lower:
                            friendly_title = title
                            friendly_hint = hint
                            break

                    prompt_short = html.escape(prompt[:40] + ("..." if len(prompt) > 40 else ""))
                    safe_error = html.escape(error_msg[:300])

                    st.error(friendly_title)
                    st.caption(f"关于「{prompt_short}」")
                    st.info(friendly_hint)
                    with st.expander("技术详情"):
                        st.code(safe_error)

                    fallback = (
                        f"{friendly_title}\n\n"
                        f"关于「**{prompt_short}**」\n\n"
                        f"{friendly_hint}\n\n"
                        f"<details><summary>技术详情</summary>\n\n`{safe_error}`\n</details>"
                    )
                    st.session_state.messages.append(
                        {"role": "assistant", "content": fallback}
                    )
                    _save_chat_history()
                    st.session_state.last_failed_prompt = prompt
                    break

                elif current_status == "cancelled":
                    status_container.update(label="⏹️ 任务已取消", state="complete")
                    st.info("任务已被用户取消")
                    break

                else:
                    time.sleep(poll_interval)
                    continue

            else:
                status_container.update(label="⏰ 任务执行超时", state="error")
                st.warning("任务执行时间过长，请查看历史记录或重新提交")

        failed_prompt = st.session_state.pop("last_failed_prompt", None)
        if failed_prompt:
            if st.button("🔄 重新执行", key=f"retry_{int(time.time()*1000)}"):
                st.session_state.pending_prompt = failed_prompt
                st.rerun()


elif page == "📁 成果物":
    """成果物库页面 — 历史文件的管理中心 + 操作日志查看

    v0.2.0 升级: 添加双Tab布局
    - Tab 1: 成果物文件（原有功能）
    - Tab 2: 操作日志（新增审计日志展示）
    """
    st.markdown("## 📁 我的成果物")

    deliverable_tabs = st.tabs(["📄 成果物文件", "📋 操作日志"])

    with deliverable_tabs[0]:
        _render_deliverables_list()

    with deliverable_tabs[1]:
        _render_audit_log_page()


elif page == "📊 成长":
    """成长飞轮页面 — 游戏化的用户激励系统

    数据来源：
    - flywheel_scores: 五维评分（内容质量/受众增长/变现能力/跨域推广/生态协同）
    - flywheel_level: 当前等级（L1探索者/L2连接者/L3生态构建者）
    - scenario_count: 累计互动次数

    等级晋升规则：
    - L1→L2: 平均分 ≥ 35
    - L2→L3: 平均分 ≥ 60
    - 每次互动对应维度 +8分（上限100）

    UI组件：
    - 等级卡片（渐变背景色随等级变化）
    - 互动次数指标
    - 五维进度条（颜色编码：绿≥60/橙≥30/灰<30）
    - 升级提示（未满级时显示下一级目标）
    """
    st.markdown("## 📊 我的成长飞轮")
    scores = st.session_state.flywheel_scores
    level = st.session_state.flywheel_level
    count = st.session_state.scenario_count

    level_info = {
        1: ("🌱 探索者", "专注单一业务类型，持续深耕", "#4CAF50"),
        2: ("🔗 连接者", "双类型组合，产生协同效应", "#FF9800"),
        3: ("🌍 生态构建者", "全生态系统，商业闭环运转", "#E91E63"),
    }
    lv_name, lv_desc, lv_color = level_info.get(level, level_info[1])

    col_level, col_count = st.columns([2, 1])
    with col_level:
        st.subheader(f"{lv_name}")
        st.caption(lv_desc)
    with col_count:
        st.metric("互动次数", count)
    if count > 0:
        st.metric("当前等级", f"Lv.{level}")

    st.divider()
    st.markdown("### 五维健康度")
    dims = [
        ("📝", "内容质量"),
        ("👥", "受众增长"),
        ("💰", "变现能力"),
        ("🔗", "跨域推广"),
        ("🌍", "生态协同"),
    ]
    for icon, dim in dims:
        score = scores.get(dim, 0)
        c1, c2, c3 = st.columns([1.5, 6, 1])
        with c1:
            st.markdown(f"{icon} **{dim}**")
        with c2:
            st.progress(score / 100)
        with c3:
            color = "#4CAF50" if score >= 60 else ("#FF9800" if score >= 30 else "#ccc")
            st.metric(label=dim, value=score)

    if count == 0:
        st.info("💡 开始与助手对话，你的成长数据会自动记录在这里！")
    elif level < 3:
        ni = level_info.get(level + 1, level_info[1])
        st.success(f"🎯 继续互动可以升级到 **{ni[0]}**！")


elif page == "🏪 技能市场":
    _render_skill_marketplace_page()


def _render_skill_marketplace_page():
    """Render the Skill Marketplace MVP page.

    Features:
    1. Browse tab: Search + category filter + skill cards grid
    2. My Skills tab: Installed skills list with status
    3. Detail view: Click card to see full info + install button
    """
    try:
        from opc_manager.skill_marketplace import SkillMarketplace, ExternalSkillMarketplace
    except ImportError:
        st.warning("技能市场模块暂未加载")
        return

    st.markdown("## 🏪 技能市场")

    marketplace = SkillMarketplace()
    external_mp = ExternalSkillMarketplace()

    sub_tab = st.tabs(["🔍 浏览发现", "📦 我的技能"])

    with sub_tab[0]:
        _render_marketplace_browse(marketplace, external_mp)

    with sub_tab[1]:
        _render_my_skills(marketplace, external_mp)


def _render_marketplace_browse(marketplace, external_mp):
    """Browse and discover skills."""
    col_search, col_cat = st.columns([3, 1])
    with col_search:
        search_query = st.text_input(
            "🔍 搜索技能...",
            placeholder="搜索名称、描述或作者...",
        )
    with col_cat:
        categories = ["全部", "分析", "创作", "搜索", "运营", "财务", "沟通"]
        cat_filter = st.selectbox("分类", categories)

    try:
        stats = marketplace.get_stats()
        total_skills = stats.get("total_skills", 0)
        approved = stats.get("approved_skills", 0)

        st.caption(f"共 {total_skills} 个技能 | 已审核 {approved} 个")

        skills = marketplace.discover_skills(
            keyword=search_query if search_query else None,
            category=cat_filter if cat_filter != "全部" else None
        )

        if not skills:
            st.info("没有找到匹配的技能")
            return

        cols = st.columns(3)
        for i, skill in enumerate(skills[:12]):
            with cols[i % 3]:
                _render_skill_card(skill, marketplace)

    except Exception as e:
        st.error(f"加载技能列表失败: {e}")


def _render_skill_card(skill: dict, marketplace):
    """Render a single skill card."""
    name = skill.get("name", "未知技能")
    version = skill.get("version", "0.0.0")
    desc = skill.get("description", "")
    author = skill.get("author", "unknown")
    category = skill.get("category", "general")
    status = skill.get("status", "pending")
    skill_id = skill.get("skill_id", "")

    trust_colors = {
        "official": "blue",
        "verified": "green",
        "community": "orange",
        "unverified": "gray",
    }
    trust_labels = {
        "official": "官方",
        "verified": "已验证",
        "community": "社区",
        "unverified": "未验证",
    }

    color = trust_colors.get("gray", "gray")
    label = trust_labels.get("unverified", "未验证")

    with st.container(border=True):
        st.markdown(f"**{label}** `{name}` v{version}")
        st.caption(desc[:80] + "..." if len(desc) > 80 else desc)
        st.markdown(f"*{category}* · {author}")

        if st.button(f"查看详情 →", key=f"skill_detail_{skill_id}_{id(skill)}", use_container_width=True):
            st.session_state[f"selected_skill"] = skill


def _render_my_skills(marketplace, external_mp):
    """Render installed/manageable skills list."""
    try:
        installed_result = external_mp.list_installed()
        installed = installed_result.get("skills", []) if isinstance(installed_result, dict) else []
    except Exception:
        installed = []

    if not installed:
        st.info("暂未安装任何额外技能")
        st.markdown("""
        前往「浏览发现」页面试试安装新技能！

        💡 **提示**: 内置21个核心技能始终可用，无需安装。
        """)
        return

    st.caption(f"已安装 {len(installed)} 个技能")

    for skill in installed:
        with st.expander(f"📦 {skill.get('name', 'Unknown')} v{skill.get('version', '?')}"):
            col_info, col_action = st.columns([3, 1])
            with col_info:
                st.json({
                    "名称": skill.get("name"),
                    "版本": skill.get("version"),
                    "状态": skill.get("status"),
                    "安装时间": skill.get("installed_at", "-"),
                })
            with col_action:
                if st.button("卸载", key=f"uninstall_{skill.get('skill_id', id(skill))}"):
                    try:
                        result = external_mp.uninstall_skill(skill.get("skill_id"))
                        if result.get("success"):
                            st.success("已卸载")
                            st.rerun()
                        else:
                            st.error(result.get("error", "卸载失败"))
                    except Exception as e:
                        st.error(f"卸载失败: {e}")


def _render_global_search():
    """Render global search across all modules.

    Searches across:
    - Chat history / conversation logs
    - Deliverables files
    - Client records (CRM data)
    - Financial records
    - Tasks
    - Audit log entries
    """
    search_query = st.text_input(
        "🔍 全局搜索...",
        value="",
        key="global_search_input",
        label_visibility="collapsed",
    )

    if not search_query or len(search_query.strip()) < 2:
        st.caption("输入至少2个字符开始搜索...")
        return

    results = _execute_global_search(search_query.strip())

    if not results:
        st.info(f"未找到与「{search_query}」相关的内容")
        return

    st.success(f"找到 {len(results)} 条结果")

    grouped = {}
    for r in results:
        rtype = r.get("type", "other")
        grouped.setdefault(rtype, []).append(r)

    for rtype, items in grouped.items():
        type_icons = {
            "chat": "💬",
            "deliverable": "📁",
            "client": "👥",
            "finance": "💰",
            "task": "✅",
            "audit": "📋",
            "skill": "🔧",
            "other": "📌",
        }
        icon = type_icons.get(rtype, "📌")

        with st.expander(f"{icon} {rtype} ({len(items)})"):
            for item in items[:10]:
                title = item.get("title", item.get("name", "-"))
                summary = item.get("summary", "")[:100]
                link = item.get("link", "")
                score = item.get("score", 0)

                col_t, col_s = st.columns([4, 1])
                with col_t:
                    if link:
                        st.markdown(f"**{title}**")
                        st.caption(summary)
                        st.link_button(
                            "查看详情",
                            url="#" if link.startswith("#") else link,
                        )
                    else:
                        st.markdown(f"**{title}**")
                        st.caption(summary)
                with col_s:
                    st.metric("匹配度", f"{int(score * 100)}%")


def _execute_global_search(query: str) -> list:
    """Execute global search across data sources."""
    results = []
    q_lower = query.lower()

    deliverables = st.session_state.get("deliverables", [])
    for d in deliverables:
        content = str(d.get("content", "")) + str(d.get("metadata", ""))
        if q_lower in content.lower():
            results.append({
                "type": "deliverable",
                "title": d.get("title", "成果物"),
                "summary": content[:150],
                "score": _simple_match_score(q_lower, content),
                "link": None,
            })

    try:
        from opc_manager.audit_log import get_audit_log
        audit = get_audit_log()
        logs = audit.query(limit=50)
        for log in logs:
            combined = f"{log.get('operation_type', '')} {log.get('input_summary', '')} {log.get('output_summary', '')}"
            if q_lower in combined.lower():
                results.append({
                    "type": "audit",
                    "title": f"[{log.get('operation_type', 'operation')}]",
                    "summary": log.get("input_summary", "")[:100],
                    "score": _simple_match_score(q_lower, combined),
                    "link": None,
                })
    except Exception:
        pass

    messages = st.session_state.get("messages", [])
    for msg in messages[-50:]:
        content = str(msg.get("content", ""))
        if q_lower in content.lower():
            results.append({
                "type": "chat",
                "title": content[:60] + "..." if len(content) > 60 else content,
                "summary": "",
                "score": _simple_match_score(q_lower, content),
                "link": None,
            })

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results[:30]


def _simple_match_score(query: str, text: str) -> float:
    """Calculate simple text match score (0.0 to 1.0)."""
    if not query or not text:
        return 0.0
    text_lower = text.lower()
    words = query.split()
    matches = sum(1 for w in words if w in text_lower)
    return min(matches / len(words), 1.0) if words else 0.0


# === Settings Page Functions (v0.2.0 Sprint 1) ===

def _create_settings_page():
    """Create the unified Settings page with 5 tabs.

    Tabs:
    1. 🧠 LLM Configuration — Provider selection, API key input, connection test
    2. 📧 SMTP Configuration — Email server setup, preset providers, test connection
    3. 🔑 API Keys — All API keys management with masking
    4. 🔒 Security — Encryption key status, regenerate option
    5. 👤 Profile — User info, company, timezone, language
    """
    try:
        from opc_manager.settings import get_settings
        settings = get_settings()
    except ImportError:
        st.error("⚠️ 设置模块未就绪，请稍后再试")
        return

    st.markdown("## ⚙️ 系统设置")

    from opc_manager.i18n import t as _t
    settings_tabs = st.tabs([_t("settings_llm"), _t("settings_smtp"), _t("settings_api_keys"), _t("settings_security"), _t("settings_profile"), _t("settings_backup")])

    with settings_tabs[0]:
        _render_llm_settings(settings)

    with settings_tabs[1]:
        _render_smtp_settings(settings)

    with settings_tabs[2]:
        _render_api_keys_settings(settings)

    with settings_tabs[3]:
        _render_security_settings(settings)

    with settings_tabs[4]:
        _render_profile_settings(settings)

    with settings_tabs[5]:
        _render_data_backup_settings()


def _render_llm_settings(settings):
    """Render LLM configuration tab"""
    from opc_manager.i18n import t as _t
    st.markdown("### 🧠 LLM 配置")

    llm_config = settings.llm.__dict__

    with st.form("llm_config_form"):
        provider = st.radio(
            _t("llm_provider"),
            ["MokaAI", "OpenAI", "智谱GLM", "Ollama"],
            index=["MokaAI", "OpenAI", "智谱GLM", "Ollama"].index(llm_config.get("provider", "MokaAI")) if llm_config.get("provider", "MokaAI") in ["MokaAI", "OpenAI", "智谱GLM", "Ollama"] else 0,
            help="选择你要使用的LLM服务提供商",
        )

        col_key, col_url = st.columns(2)
        with col_key:
            api_key = st.text_input(
                _t("llm_api_key"),
                value=llm_config.get("api_key", ""),
                type="password",
                help="输入你的API密钥",
                placeholder="sk-...",
            )
        with col_url:
            base_url = st.text_input(
                _t("llm_base_url"),
                value=llm_config.get("base_url", ""),
                help="API端点地址（可选，留空使用默认值）",
                placeholder="https://api.example.com/v1",
            )

        model = st.text_input(
            _t("llm_model"),
            value=llm_config.get("model", ""),
            help="指定使用的模型名称（可选）",
            placeholder="gpt-4 / chatglm-turbo 等",
        )

        col_tokens, col_temp = st.columns(2)
        with col_tokens:
            max_tokens = st.slider(
                "Max Tokens",
                min_value=1000,
                max_value=16000,
                value=int(llm_config.get("max_tokens", 4000)),
                step=1000,
                help="最大生成token数",
            )
        with col_temp:
            temperature = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=2.0,
                value=float(llm_config.get("temperature", 0.7)),
                step=0.1,
                help="控制输出的随机性（越高越随机）",
            )

        col_test, col_save = st.columns([1, 1])
        with col_test:
            test_clicked = st.form_submit_button("🔗 测试连接", type="secondary")
        with col_save:
            save_clicked = st.form_submit_button("💾 保存配置", type="primary")

        if test_clicked:
            if api_key and api_key.strip():
                st.success("✅ API Key 已配置（实际连接将在使用时验证）")
            else:
                st.error("❌ 请先输入有效的 API Key")

        if save_clicked:
            new_config = {
                "provider": provider,
                "api_key": api_key,
                "base_url": base_url,
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if settings.update_llm(**new_config):
                st.success("✅ LLM配置已保存")
                st.rerun()
            else:
                st.error("❌ 保存失败，请重试")


def _render_smtp_settings(settings):
    """Render SMTP configuration tab"""
    st.markdown("### 📧 SMTP 邮件配置")

    smtp_config = settings.smtp.__dict__

    SMTP_PRESETS = {
        "自定义": {},
        "QQ邮箱": {"host": "smtp.qq.com", "port": 587, "tls": True},
        "163邮箱": {"host": "smtp.163.com", "port": 465, "tls": True},
        "Gmail": {"host": "smtp.gmail.com", "port": 587, "tls": True},
        "Outlook": {"host": "smtp.office365.com", "port": 587, "tls": True},
    }

    with st.form("smtp_config_form"):
        preset = st.selectbox(
            "预设服务商",
            list(SMTP_PRESETS.keys()),
            help="选择邮件服务商后自动填充常用配置",
        )

        preset_config = SMTP_PRESETS.get(preset, {})

        host = st.text_input(
            "SMTP 服务器",
            value=preset_config.get("host", smtp_config.get("host", "")),
            help="邮件服务器地址",
            placeholder="smtp.example.com",
        )

        port = st.number_input(
            "端口",
            min_value=1,
            max_value=65535,
            value=int(preset_config.get("port", smtp_config.get("port", 587))),
            help="常用端口: 25(普通), 465(SSL), 587(TLS)",
        )

        col_user, col_pass = st.columns(2)
        with col_user:
            username = st.text_input(
                "用户名",
                value=smtp_config.get("username", ""),
                help="邮箱登录用户名",
                placeholder="your@email.com",
            )
        with col_pass:
            password = st.text_input(
                "密码/授权码",
                value=smtp_config.get("password", ""),
                type="password",
                help="邮箱密码或应用专用授权码",
                placeholder="••••••••",
            )

        tls_enabled = st.checkbox(
            "启用 TLS 加密",
            value=bool(preset_config.get("tls", smtp_config.get("tls", True))),
            help="推荐开启TLS加密保护邮件传输安全",
        )

        from_email = st.text_input(
            "发件人邮箱",
            value=smtp_config.get("from_email", ""),
            help="发送邮件时显示的发件人地址",
            placeholder="noreply@example.com",
        )

        col_test, col_save = st.columns([1, 1])
        with col_test:
            test_clicked = st.form_submit_button("🔗 测试连接", type="secondary")
        with col_save:
            save_clicked = st.form_submit_button("💾 保存配置", type="primary")

        if test_clicked:
            new_config = {
                "host": host,
                "port": port,
                "username": username,
                "password": password,
                "tls": tls_enabled,
                "from_email": from_email,
            }
            settings.update_smtp(**new_config)
            with st.spinner("正在测试SMTP连接..."):
                test_result = settings.test_smtp_connection()
                if test_result["success"]:
                    st.success(f"✅ SMTP连接成功！延迟: {test_result['latency_ms']}ms")
                    st.info(f"服务器响应: {test_result['message']}")
                else:
                    st.error(f"❌ 连接失败: {test_result['message']}")

        if save_clicked:
            new_config = {
                "host": host,
                "port": port,
                "username": username,
                "password": password,
                "tls": tls_enabled,
                "from_email": from_email,
            }
            if settings.update_smtp(**new_config):
                st.success("✅ SMTP配置已保存")
                st.rerun()
            else:
                st.error("❌ 保存失败，请重试")


def _render_api_keys_settings(settings):
    """Render API Keys management tab"""
    st.markdown("### 🔑 API 密钥管理")

    st.info("💡 当前显示已配置的服务密钥。完整的API密钥管理功能即将支持。")

    st.markdown("**已配置的密钥：**")

    llm_key = settings.llm.api_key
    smtp_pass = settings.smtp.password

    with st.expander("🧠 LLM API Key", expanded=bool(llm_key)):
        if llm_key:
            masked = "****" + llm_key[-4:] if len(llm_key) > 4 else "****"
            col_val, col_copy = st.columns([3, 1])
            with col_val:
                st.text_input("密钥值（掩码）", value=masked, disabled=True)
                st.caption(f"最后4位: `{llm_key[-4:]}`" if len(llm_key) >= 4 else "未显示")
            with col_copy:
                if st.button("📋 复制完整密钥", key="copy_llm_key"):
                    st.clipboard_text(llm_key)
                    st.success("✅ 已复制到剪贴板")
        else:
            st.warning("⚠️ 未配置 LLM API Key")
            st.caption("请前往「LLM 配置」标签页设置")

    with st.expander("📧 SMTP 密码/授权码", expanded=bool(smtp_pass)):
        if smtp_pass:
            masked = "****" + smtp_pass[-4:] if len(smtp_pass) > 4 else "****"
            col_val, col_copy = st.columns([3, 1])
            with col_val:
                st.text_input("密码值（掩码）", value=masked, disabled=True)
                st.caption(f"最后4位: `{smtp_pass[-4:]}`" if len(smtp_pass) >= 4 else "未显示")
            with col_copy:
                if st.button("📋 复制完整密码", key="copy_smtp_pass"):
                    st.clipboard_text(smtp_pass)
                    st.success("✅ 已复制到剪贴板")
        else:
            st.warning("⚠️ 未配置 SMTP 密码")
            st.caption("请前往「SMTP 邮件配置」标签页设置")

    st.divider()

    st.markdown("**➕ 添加新密钥**")
    st.info("🚧 即将支持：多API密钥管理、自动轮换、权限控制等功能")
    st.caption("当前版本请在对应的配置标签页中直接输入密钥")


def _render_security_settings(settings):
    """Render Security settings tab"""
    st.markdown("### 🔒 安全设置")

    security = settings.security

    if security.encryption_key:
        if security.auto_generated:
            status_text = "✅ 已自动生成"
            status_color = "green"
        else:
            status_text = "🔐 手动设置"
            status_color = "blue"
    else:
        status_text = "⚠️ 未设置"
        status_color = "orange"

    st.markdown("**加密密钥状态**")
    st.markdown(f"- 状态: :{status_color}[{status_text}]")
    if security.auto_generated:
        st.markdown("- 生成方式: 系统自动生成（CSPRNG安全随机数）")
    st.markdown(f"- 存储位置: `.env.local` 文件（已加入 .gitignore）")
    st.markdown("- 密钥长度: 256位（64个十六进制字符）")

    st.divider()

    st.info("💡 **安全提示：**")
    st.caption("• 加密密钥用于保护敏感配置数据（API密钥、密码等）")
    st.caption("• 密钥丢失将导致无法解密已加密的数据")
    st.caption("• 请定期备份 `.env.local` 文件到安全位置")

    st.divider()

    col_regenerate, _ = st.columns([1, 3])
    with col_regenerate:
        if st.button("🔄 重新生成密钥", type="secondary", disabled=True):
            pass
    st.caption("⚠️ 重新生成功能为高级操作，请联系管理员执行（需手动删除 .env.local 后重启系统）")


def _render_profile_settings(settings):
    """Render Profile settings tab"""
    st.markdown("### 👤 个人信息")

    profile = settings.profile.__dict__

    TIMEZONES = [
        "Asia/Shanghai",
        "Asia/Tokyo",
        "Asia/Singapore",
        "Asia/Dubai",
        "Europe/London",
        "Europe/Berlin",
        "Europe/Paris",
        "America/New_York",
        "America/Los_Angeles",
        "America/Chicago",
        "Pacific/Auckland",
        "Australia/Sydney",
    ]

    LANGUAGES = ["中文", "English"]

    with st.form("profile_form"):
        username = st.text_input(
            "用户名",
            value=profile.get("user_name", ""),
            placeholder="输入你的名字",
            help="用于个性化显示",
        )

        company = st.text_input(
            "公司名称",
            value=profile.get("company_name", ""),
            placeholder="输入公司或组织名称（可选）",
            help="用于生成文档的公司信息",
        )

        col_tz, col_lang = st.columns(2)
        with col_tz:
            timezone = st.selectbox(
                "时区",
                TIMEZONES,
                index=TIMEZONES.index(profile.get("timezone", "Asia/Shanghai")) if profile.get("timezone", "Asia/Shanghai") in TIMEZONES else 0,
                help="选择你所在的时区",
            )
        with col_lang:
            language = st.selectbox(
                "语言",
                LANGUAGES,
                index=LANGUAGES.index(profile.get("language", "zh_CN")) if profile.get("language", "zh_CN") in ["中文", "English"] else 0,
                help="界面语言设置（即将支持多语言切换）",
            )

        submitted = st.form_submit_button("💾 保存个人信息")
        if submitted:
            new_profile = {
                "user_name": username,
                "company_name": company,
                "timezone": timezone,
                "language": language,
            }
            if settings.update_profile(**new_profile):
                st.success("✅ 个人信息已保存")
                st.rerun()
            else:
                st.error("❌ 保存失败，请重试")


def _render_data_backup_settings():
    """Render Data Backup settings tab.

    Features:
    - Create backup button with progress indicator
    - List existing backups with download/delete options
    - Restore from backup with confirmation
    - Export data in JSON/CSV/ZIP formats
    """
    st.markdown("### 💾 数据备份与恢复")

    st.info("💡 **数据安全提示：** 定期备份你的数据，防止意外丢失。备份文件包含所有客户记录、财务数据和任务信息。")

    backup_tabs = st.tabs(["📦 创建备份", "📋 备份列表", "📥 导出数据", "🔄 恢复数据"])

    with backup_tabs[0]:
        _render_create_backup_tab()

    with backup_tabs[1]:
        _render_backup_list_tab()

    with backup_tabs[2]:
        _render_export_data_tab()

    with backup_tabs[3]:
        _render_restore_data_tab()


def _render_create_backup_tab():
    """Render the create backup tab."""
    st.markdown("#### 📦 创建新备份")

    include_attachments = st.checkbox(
        "包含附件文件",
        value=False,
        help="勾选后备份将包含附件（会增大备份文件大小）",
    )

    col_create, _ = st.columns([1, 2])
    with col_create:
        if st.button("🚀 立即创建备份", type="primary", use_container_width=True):
            with st.spinner("正在创建备份，请稍候..."):
                try:
                    from opc_manager.data_backup import get_backup_manager
                    manager = get_backup_manager()
                    backup_path, manifest = manager.create_backup(
                        include_attachments=include_attachments
                    )

                    st.success(f"✅ 备份创建成功！")
                    st.json({
                        "文件名": backup_path.name,
                        "大小": f"{manifest.total_size_bytes / (1024*1024):.2f} MB",
                        "文件数": manifest.total_files,
                        "版本": manifest.version,
                        "校验和": f"{manifest.checksum_sha256[:16]}...",
                        "创建时间": manifest.created_at,
                    })
                    st.balloons()
                except Exception as e:
                    logger.error("[frontend] Create backup error: %s", e)
                    st.error(f"❌ 备份创建失败: {str(e)}")


def _render_backup_list_tab():
    """Render the backup list tab."""
    st.markdown("#### 📋 已有备份")

    try:
        from opc_manager.data_backup import get_backup_manager
        manager = get_backup_manager()
        backups = manager.list_backups()

        if not backups:
            st.info("💡 暂无备份。点击「创建备份」生成第一个备份")
            return

        st.caption(f"共 {len(backups)} 个备份")

        for idx, backup in enumerate(backups):
            with st.expander(
                f"📄 {backup['filename']} — {backup['size_mb']} MB ({backup['created_at'][:10]})",
                expanded=(idx == 0)
            ):
                col_dl, col_del, _ = st.columns([1, 1, 2])

                with col_dl:
                    backup_file_path = Path(backup["path"])
                    if backup_file_path.exists():
                        with open(backup_file_path, "rb") as f:
                            zip_bytes = f.read()
                        st.download_button(
                            label="⬇️ 下载",
                            data=zip_bytes,
                            file_name=backup["filename"],
                            mime="application/zip",
                            key=f"dl_backup_{idx}",
                            use_container_width=True,
                        )

                with col_del:
                    if st.button("🗑️ 删除", key=f"del_backup_{idx}", use_container_width=True):
                        if manager.delete_backup(backup["path"]):
                            st.success("✅ 已删除")
                            st.rerun()
                        else:
                            st.error("❌ 删除失败")

                st.caption(f"完整路径: `{backup['path']}`")

    except ImportError:
        st.warning("⚠️ 备份模块未就绪")
    except Exception as e:
        logger.error("[frontend] Backup list error: %s", e)
        st.error(f"⚠️ 加载备份列表失败: {str(e)}")


def _render_export_data_tab():
    """Render the export data tab."""
    st.markdown("#### 📥 导出数据")

    st.markdown("**选择导出格式：**")

    format_col1, format_col2, format_col3 = st.columns(3)

    with format_col1:
        if st.button("📄 导出为 JSON", use_container_width=True, help="结构化JSON格式，适合程序处理"):
            with st.spinner("正在导出..."):
                try:
                    from opc_manager.data_backup import get_backup_manager
                    manager = get_backup_manager()
                    json_data = manager.export_data(format_type="json")
                    st.download_button(
                        label="⬇️ 下载 JSON 文件",
                        data=json_data,
                        file_name=f"opc_agents_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        key="dl_export_json",
                        use_container_width=True,
                    )
                    st.success("✅ JSON导出完成")
                except Exception as e:
                    logger.error("[frontend] Export JSON error: %s", e)
                    st.error(f"❌ 导出失败: {str(e)}")

    with format_col2:
        if st.button("📊 导出为 CSV", use_container_width=True, help="表格格式，适合Excel打开"):
            with st.spinner("正在导出..."):
                try:
                    from opc_manager.data_backup import get_backup_manager
                    manager = get_backup_manager()
                    csv_data = manager.export_data(format_type="csv")
                    st.download_button(
                        label="⬇️ 下载 CSV 文件",
                        data=csv_data,
                        file_name=f"opc_agents_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        key="dl_export_csv",
                        use_container_width=True,
                    )
                    st.success("✅ CSV导出完成")
                except Exception as e:
                    logger.error("[frontend] Export CSV error: %s", e)
                    st.error(f"❌ 导出失败: {str(e)}")

    with format_col3:
        if st.button("📦 导出为 ZIP", use_container_width=True, help="完整备份包（含清单文件）"):
            with st.spinner("正在导出..."):
                try:
                    from opc_manager.data_backup import get_backup_manager
                    manager = get_backup_manager()
                    zip_data = manager.export_data(format_type="zip")
                    st.download_button(
                        label="⬇️ 下载 ZIP 文件",
                        data=zip_data,
                        file_name=f"opc_agents_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                        mime="application/zip",
                        key="dl_export_zip",
                        use_container_width=True,
                    )
                    st.success("✅ ZIP导出完成")
                except Exception as e:
                    logger.error("[frontend] Export ZIP error: %s", e)
                    st.error(f"❌ 导出失败: {str(e)}")

    st.divider()
    st.caption("💡 提示：JSON格式适合数据迁移，CSV适合表格分析，ZIP是完整备份")


def _render_restore_data_tab():
    """Render the restore data tab."""
    st.markdown("#### 🔄 从备份恢复")

    st.warning("⚠️ **注意：** 恢复操作将覆盖当前所有数据，请确保已做好当前数据的备份！")

    uploaded_file = st.file_uploader(
        "选择备份文件 (ZIP格式)",
        type=["zip"],
        help="选择之前下载的 .zip 备份文件",
    )

    if uploaded_file:
        st.info(f"📄 已选择文件: {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")

        # Save uploaded file to temp location (sanitize filename)
        import re
        safe_name = re.sub(r'[^\w\-.]', '_', uploaded_file.name)[:100]
        temp_dir = Path(_WORKSPACE_DIR) / "data" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / f"restore_{safe_name}"

        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        confirm_restore = st.checkbox(
            "✅ 我确认要从此备份恢复数据（这将覆盖当前数据）",
            key="confirm_restore_checkbox",
        )

        col_restore, _ = st.columns([1, 2])
        with col_restore:
            if st.button(
                "🔄 开始恢复",
                type="primary",
                use_container_width=True,
                disabled=not confirm_restore,
                help="必须先勾选确认框才能执行恢复操作"
            ):
                with st.spinner("正在从备份恢复数据，请勿关闭页面..."):
                    try:
                        from opc_manager.data_backup import get_backup_manager
                        manager = get_backup_manager()
                        result = manager.restore_backup(str(temp_path), confirm=True)

                        if result["success"]:
                            st.success(f"✅ {result.get('message', '恢复成功')}")
                            st.json({
                                "恢复文件数": result.get("restored_files", 0),
                            })
                            st.balloons()
                            st.warning("⚠️ 建议刷新页面以确保所有数据正确加载")
                        else:
                            st.error(f"❌ 恢复失败: {result.get('error', '未知错误')}")

                        # Cleanup temp file
                        if temp_path.exists():
                            temp_path.unlink()

                    except Exception as e:
                        logger.error("[frontend] Restore error: %s", e)
                        st.error(f"❌ 恢复过程出错: {str(e)}")


# === Dashboard Page Functions (v0.2.0 Sprint 3) ===

def _render_dashboard_page():
    """Render modular Dashboard with selectable panels.

    Available panels (user can toggle on/off):
    1. 📈 Income Trend Chart (收入趋势图)
    2. 👥 Client Health Score (客户健康度)
    3. ✅ Task Completion Rate (任务完成率)
    4. 💰 Monthly Financial Summary (月度财务汇总)
    5. 📅 Recent Activity Timeline (近期活动时间线)
    6. ⏱️ Skill Usage Stats (技能使用统计)

    Default: Show Top 3 most useful panels
    """
    st.markdown("## 📈 数据仪表盘")

    # Panel selector at top
    ALL_PANELS = [
        ("income_trend", "📈 收入趋势图", "显示最近30天/按月的收入变化趋势"),
        ("client_health", "👥 客户健康度", "客户活跃度和互动频率分析"),
        ("task_completion", "✅ 任务完成率", "任务进度和完成情况统计"),
        ("financial_summary", "💰 月度财务汇总", "本月收入/支出/净利润概览"),
        ("activity_timeline", "📅 近期活动时间线", "最近20条操作记录时间线"),
        ("skill_usage", "⏱️ 技能使用统计", "各技能调用次数和使用频率"),
    ]

    DEFAULT_PANELS = ["income_trend", "client_health", "task_completion"]

    if "dashboard_selected_panels" not in st.session_state:
        st.session_state.dashboard_selected_panels = DEFAULT_PANELS

    with st.expander("⚙️ 面板设置（选择要显示的数据面板）", expanded=False):
        selected = []
        for panel_id, title, desc in ALL_PANELS:
            is_checked = st.checkbox(
                f"{title}",
                value=panel_id in st.session_state.dashboard_selected_panels,
                help=desc,
                key=f"dashboard_panel_{panel_id}",
            )
            if is_checked:
                selected.append(panel_id)

        if selected != st.session_state.dashboard_selected_panels:
            st.session_state.dashboard_selected_panels = selected
            st.rerun()

        col_select_all, col_deselect, _ = st.columns([1, 1, 2])
        with col_select_all:
            if st.button("全选", use_container_width=True):
                st.session_state.dashboard_selected_panels = [p[0] for p in ALL_PANELS]
                st.rerun()
        with col_deselect:
            if st.button("默认(Top 3)", use_container_width=True):
                st.session_state.dashboard_selected_panels = DEFAULT_PANELS
                st.rerun()

    st.divider()

    selected_panels = st.session_state.dashboard_selected_panels

    if not selected_panels:
        st.info("💡 请在上方选择至少一个数据面板")
        return

    # Render selected panels in grid layout (2-3 columns)
    panels_to_render = [(pid, title, desc) for pid, title, desc in ALL_PANELS if pid in selected_panels]

    for i in range(0, len(panels_to_render), 2):
        row_panels = panels_to_render[i:i+2]
        cols = st.columns(len(row_panels))

        for idx, (panel_id, panel_title, _) in enumerate(row_panels):
            with cols[idx]:
                try:
                    if panel_id == "income_trend":
                        _render_income_trend_panel()
                    elif panel_id == "client_health":
                        _render_client_health_panel()
                    elif panel_id == "task_completion":
                        _render_task_completion_panel()
                    elif panel_id == "financial_summary":
                        _render_financial_summary_panel()
                    elif panel_id == "activity_timeline":
                        _render_activity_timeline_panel()
                    elif panel_id == "skill_usage":
                        _render_skill_usage_panel()
                except Exception as e:
                    logger.error("[frontend] Dashboard panel %s error: %s", panel_id, e)
                    st.error(f"⚠️ 面板加载失败: {panel_title}")


def _get_dashboard_data():
    """Safe wrapper to get dashboard data from backend modules.

    Returns:
        dict with keys: finance, crm, tasks, audit_log
    """
    data = {
        "finance": {"trend": [], "monthly": {}},
        "crm": {"customers": [], "stats": {}},
        "tasks": {"list": [], "by_status": {}},
        "audit_log": [],
        "skills_usage": {},
    }

    try:
        from opc_manager.finance_skill import get_trend, get_monthly_report
        import time as _time
        year_month = _time.strftime("%Y-%m")
        data["finance"]["trend"] = get_trend(6)
        data["finance"]["monthly"] = get_monthly_report(year_month)
    except Exception as e:
        logger.debug("[frontend] Finance data error: %s", e)

    try:
        from opc_manager.crm_skill import get_customer_stats, get_silent_customers, list_customers
        data["crm"]["stats"] = get_customer_stats()
        data["crm"]["silent"] = get_silent_customers()
        try:
            data["crm"]["customers"] = list_customers(limit=10).get("customers", [])
        except Exception:
            pass
    except Exception as e:
        logger.debug("[frontend] CRM data error: %s", e)

    try:
        from opc_manager.task_skill import list_tasks
        tasks_result = list_tasks(status="all")
        data["tasks"]["list"] = tasks_result.get("tasks", [])
        by_status = {}
        for t in data["tasks"]["list"]:
            status = t.get("status", "pending")
            by_status[status] = by_status.get(status, 0) + 1
        data["tasks"]["by_status"] = by_status
    except Exception as e:
        logger.debug("[frontend] Tasks data error: %s", e)

    try:
        from opc_manager.audit_log import AuditLog
        audit = AuditLog()
        data["audit_log"] = audit.query(limit=20)
    except Exception as e:
        logger.debug("[frontend] Audit log error: %s", e)

    return data


def _render_income_trend_panel():
    """Panel 1: 收入趋势图 - Income trend chart."""
    st.markdown("### 📈 收入趋势图")

    data = _get_dashboard_data()
    trend = data.get("finance", {}).get("trend", [])

    if not trend:
        st.info("💡 暂无财务数据。开始记录收入后这里会展示趋势图")
        return

    import pandas as pd

    df = pd.DataFrame(trend)
    chart_data = pd.DataFrame({
        "月份": [t.get("year_month", "") for t in trend],
        "收入": [t.get("income", 0) for t in trend],
        "支出": [t.get("expense", 0) for t in trend],
        "利润": [t.get("profit", 0) for t in trend],
    })

    st.line_chart(chart_data.set_index("月份"), use_container_width=True)

    if len(trend) >= 2:
        latest = trend[-1].get("profit", 0)
        previous = trend[-2].get("profit", 0)
        change_pct = ((latest - previous) / abs(previous) * 100) if previous != 0 else 0
        delta_color = "normal" if change_pct >= 0 else "inverse"
        st.metric(
            "本月利润",
            f"¥{latest:,.2f}",
            f"{change_pct:+.1f}%" if change_pct != 0 else None,
            delta_color=delta_color,
        )


def _render_client_health_panel():
    """Panel 2: 客户健康度 - Client health score."""
    st.markdown("### 👥 客户健康度")

    data = _get_dashboard_data()
    customers = data.get("crm", {}).get("customers", [])
    stats = data.get("crm", {}).get("stats", {})
    silent = data.get("crm", {}).get("silent", {})

    total = stats.get("total", 0)
    active = stats.get("active", 0)
    silent_count = silent.get("count", 0)

    if total == 0 and not customers:
        st.info("💡 暂无客户数据。添加客户后这里会展示健康度分析")
        return

    col_total, col_active, col_silent = st.columns(3)
    with col_total:
        st.metric("客户总数", total)
    with col_active:
        st.metric("活跃客户", active)
    with col_silent:
        st.metric("沉默客户", silent_count, delta_color="inverse")

    if customers:
        import pandas as pd
        customer_data = []
        for c in customers[:10]:
            name = c.get("name", "Unknown")
            status = c.get("status", "unknown")
            last_contact = c.get("last_contact", "")
            interactions = c.get("interactions", 0)

            # Health score logic
            from datetime import datetime as _dt, timedelta
            now = _dt.now()
            health_status = "🟢 健康"
            if last_contact:
                try:
                    last_date = _dt.strptime(last_contact[:10], "%Y-%m-%d") if len(last_contact) >= 10 else now
                    days_since = (now - last_date).days
                    if days_since > 30:
                        health_status = "🔴 需关注"
                    elif days_since > 14:
                        health_status = "🟡 一般"
                except Exception:
                    pass

            customer_data.append({
                "客户名称": name,
                "状态": status,
                "互动次数": interactions,
                "最近联系": last_contact[:10] if last_contact else "-",
                "健康度": health_status,
            })

        if customer_data:
            df = pd.DataFrame(customer_data)
            st.dataframe(df, use_container_width=True, hide_index=True)


def _render_task_completion_panel():
    """Panel 3: 任务完成率 - Task completion rate."""
    st.markdown("### ✅ 任务完成率")

    data = _get_dashboard_data()
    tasks = data.get("tasks", {}).get("list", [])
    by_status = data.get("tasks", {}).get("by_status", {})

    total = len(tasks)
    completed = by_status.get("completed", 0)
    in_progress = by_status.get("in_progress", 0)
    pending = by_status.get("pending", 0)

    if total == 0:
        st.info("💡 暂无任务数据。创建任务后这里会展示完成率")
        return

    completion_rate = (completed / total * 100) if total > 0 else 0

    col_total, col_done, col_rate = st.columns(3)
    with col_total:
        st.metric("总任务", total)
    with col_done:
        st.metric("已完成", completed)
    with col_rate:
        st.metric("完成率", f"{completion_rate:.1f}%")

    st.progress(completion_rate / 100, text=f"完成率 {completion_rate:.1f}%")

    # Status breakdown
    if by_status:
        import pandas as pd
        status_df = pd.DataFrame([
            {"状态": "已完成", "数量": completed, "占比": f"{completed/total*100:.1f}%"},
            {"状态": "进行中", "数量": in_progress, "占比": f"{in_progress/total*100:.1f}%" if total > 0 else "0%"},
            {"状态": "待处理", "数量": pending, "占比": f"{pending/total*100:.1f}%" if total > 0 else "0%"},
        ])
        st.dataframe(status_df, use_container_width=True, hide_index=True)


def _render_financial_summary_panel():
    """Panel 4: 月度财务汇总 - Monthly financial summary."""
    st.markdown("### 💰 月度财务汇总")

    data = _get_dashboard_data()
    monthly = data.get("finance", {}).get("monthly", {})
    trend = data.get("finance", {}).get("trend", [])

    income = monthly.get("income", 0)
    expense = monthly.get("expense", 0)
    profit = monthly.get("profit", 0)

    if income == 0 and expense == 0:
        st.info("💡 暂无本月财务数据。记录收支后这里会展示汇总")
        return

    col_inc, col_exp, col_profit = st.columns(3)
    with col_inc:
        st.metric("本月收入", f"¥{income:,.2f}")
    with col_exp:
        st.metric("本月支出", f"¥{expense:,.2f}", delta_color="inverse")
    with col_profit:
        profit_delta = None
        if len(trend) >= 2:
            prev_profit = trend[-2].get("profit", 0)
            profit_delta = f"{profit - prev_profit:+,.2f}" if prev_profit != 0 else None
        st.metric("净利润", f"¥{profit:,.2f}", profit_delta)

    # Simple bar chart comparing income vs expense
    if income > 0 or expense > 0:
        import pandas as pd
        comparison = pd.DataFrame({
            "类别": ["收入", "支出"],
            "金额": [income, expense],
        })
        st.bar_chart(comparison.set_index("类别"), use_container_width=True)


def _render_activity_timeline_panel():
    """Panel 5: 近期活动时间线 - Recent activity timeline."""
    st.markdown("### 📅 近期活动时间线")

    data = _get_dashboard_data()
    logs = data.get("audit_log", [])

    if not logs:
        st.info("💡 暂无操作记录。执行任务后日志会自动记录在这里")
        return

    from datetime import datetime as _dt

    for idx, record in enumerate(logs[:20]):
        timestamp = record.get("timestamp", 0)
        op_type = record.get("operation_type", "unknown")
        skill_id = record.get("skill_id", "")
        status = record.get("status", "unknown")
        duration = record.get("duration_ms", 0)

        time_str = _dt.fromtimestamp(timestamp).strftime("%m-%d %H:%M:%S") if timestamp else ""

        status_emoji = {
            "success": "✅",
            "failed": "❌",
            "cancelled": "⚪",
        }.get(status, "📌")

        with st.expander(f"{status_emoji} **{op_type}** — {time_str} ({duration}ms)", expanded=(idx < 3)):
            col_meta, col_detail = st.columns([1, 2])
            with col_meta:
                st.caption(f"**技能**: `{skill_id}`")
                st.caption(f"**状态**: `{status}`")
                st.caption(f"**耗时**: {duration}ms")
            with col_detail:
                input_sum = record.get("input_summary", "")
                output_sum = record.get("output_summary", "")
                if input_sum:
                    st.text(input_sum[:150])
                if output_sum:
                    st.text(output_sum[:200])

    if len(logs) > 20:
        st.caption(f"显示最近20条，共{len(logs)}条记录")


def _render_skill_usage_panel():
    """Panel 6: 技能使用统计 - Skill usage statistics."""
    st.markdown("### ⏱️ 技能使用统计")

    data = _get_dashboard_data()
    logs = data.get("audit_log", [])

    if not logs:
        st.info("💡 暂无技能使用数据。使用各功能后统计会自动更新")
        return

    from collections import Counter
    skill_counts = Counter()
    for log in logs:
        skill_id = log.get("skill_id", "unknown")
        if skill_id:
            skill_counts[skill_id] += 1

    if not skill_counts:
        st.info("💡 暂无技能使用记录")
        return

    total_calls = sum(skill_counts.values())
    top_skills = skill_counts.most_common(10)

    st.metric("总调用次数", total_calls)

    import pandas as pd
    skill_data = []
    for skill_name, count in top_skills:
        pct = count / total_calls * 100 if total_calls > 0 else 0
        skill_data.append({
            "技能": skill_name,
            "调用次数": count,
            "占比": f"{pct:.1f}%",
        })

    if skill_data:
        df = pd.DataFrame(skill_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Horizontal bar chart
        chart_df = pd.DataFrame({
            "技能": [s[0] for s in top_skills],
            "调用次数": [s[1] for s in top_skills],
        })
        st.bar_chart(chart_df.set_index("技能"), use_container_width=True, horizontal=True)


def _render_deliverables_list():
    """Render the deliverables file list (original functionality)."""
    if not st.session_state.deliverables:
        st.info("💡 还没有生成任何成果物。去「对话」页面执行一个任务吧！")
    else:
        st.caption(f"共 {len(st.session_state.deliverables)} 个成果物")

        st.divider()

        _render_batch_export_section()

        st.divider()

        search_query = st.text_input("🔍 搜索成果物", placeholder="输入关键词搜索...", key="deliverable_search")

        filtered_deliverables = st.session_state.deliverables
        if search_query:
            search_lower = search_query.lower()
            filtered_deliverables = [
                d for d in st.session_state.deliverables
                if search_lower in d.get("prompt", "").lower()
                or search_lower in d.get("filename", "").lower()
                or search_lower in d.get("task_type", "").lower()
            ]

        st.caption(f"共 {len(st.session_state.deliverables)} 个成果物" + (f"，匹配 {len(filtered_deliverables)} 个" if search_query else ""))

        for i, d in enumerate(filtered_deliverables):
            with st.expander(f"📄 {d['filename']}", expanded=(i == 0)):
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.markdown(f"**任务**: `{d['prompt']}`")
                    st.markdown(f"**类型**: {d['task_type']}")
                    st.markdown(f"**时间**: {d['created_at']}")
                with col2:
                    st.metric("大小", f"{d['size_kb']} KB")
                with col3:
                    real_fp = os.path.realpath(d["filepath"])
                    if not real_fp.startswith(os.path.realpath(DELIVERABLES_DIR)):
                        continue
                    if os.path.exists(real_fp):
                        with open(real_fp, "r", encoding="utf-8") as f:
                            content = f.read()
                        st.download_button(
                            "📥 下载",
                            data=content,
                            file_name=d["filename"],
                            mime="text/markdown",
                            key=f"dl_lib_{i}",
                            use_container_width=True,
                        )
                    if os.path.exists(real_fp):
                        with open(real_fp, "r", encoding="utf-8") as f:
                            lib_content = f.read()
                        st.markdown("**快速导出:**")
                        _render_single_export_buttons(d, item_id=f"lib_{d['filename'][:12]}")
                    if st.button("🗑️ 删除", key=f"del_lib_{d['filename']}"):
                        try:
                            real_path = os.path.realpath(d["filepath"])
                            if not real_path.startswith(os.path.realpath(DELIVERABLES_DIR)):
                                st.error("非法文件路径")
                            elif os.path.exists(real_path):
                                os.remove(real_path)
                        except OSError:
                            pass
                        st.session_state.deliverables = [
                            item
                            for item in st.session_state.deliverables
                            if item.get("filename") != d["filename"]
                        ]
                        st.rerun()

                st.markdown("**预览（前500字）**:")
                if os.path.exists(d["filepath"]):
                    with open(d["filepath"], "r", encoding="utf-8") as f:
                        preview = f.read()[:500]
                    st.code(preview, language="markdown")


def _render_audit_log_page():
    """Render the Audit Log viewer page.

    Features:
    - Timeline-style display of recent operations
    - Filter by operation type / status / date range
    - Search by session_id or skill_id
    - Stats summary at top (total/success/failed rate)
    - Expandable detail view per record
    """
    try:
        from opc_manager.audit_log import AuditLog

        audit_log = AuditLog()

        st.markdown("### 📋 操作日志")

        stats = audit_log.get_stats()
        total_ops = stats.get("total", 0)
        success_rate = stats.get("success_rate", "0%")
        avg_duration = stats.get("avg_duration_ms", 0)

        col_total, col_success, col_avg = st.columns(3)
        with col_total:
            st.metric("总操作数", total_ops)
        with col_success:
            st.metric("成功率", success_rate)
        with col_avg:
            st.metric("平均耗时", f"{avg_duration}ms")

        if total_ops == 0:
            st.info("💡 暂无操作记录。执行任务后日志会自动记录在这里。")
            return

        st.divider()

        filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([2, 2, 2, 2])

        with filter_col1:
            op_types = ["全部"] + list(set(
                r.get("operation_type", "") for r in audit_log.query(limit=200) if r.get("operation_type")
            ))
            selected_type = st.selectbox(
                "操作类型",
                op_types,
                key="audit_op_type",
                help="筛选特定类型的操作"
            )

        with filter_col2:
            status_options = ["全部", "success", "failed", "cancelled"]
            selected_status = st.selectbox(
                "状态",
                status_options,
                key="audit_status",
                help="按执行状态筛选"
            )

        with filter_col3:
            session_search = st.text_input(
                "Session ID",
                placeholder="输入Session ID搜索...",
                key="audit_session_search",
                help="留空显示所有会话"
            )

        with filter_col4:
            time_range_options = ["全部", "今天", "最近7天", "最近30天"]
            selected_time_range = st.selectbox(
                "时间范围",
                time_range_options,
                key="audit_time_range",
                help="选择时间范围"
            )

        import time as _time
        since_timestamp = None
        if selected_time_range == "今天":
            since_timestamp = _time.time() - 86400
        elif selected_time_range == "最近7天":
            since_timestamp = _time.time() - 7 * 86400
        elif selected_time_range == "最近30天":
            since_timestamp = _time.time() - 30 * 86400

        query_params = {
            "limit": 50,
            "since": since_timestamp,
        }
        if selected_type != "全部":
            query_params["operation_type"] = selected_type
        if session_search.strip():
            query_params["session_id"] = session_search.strip()

        try:
            records = audit_log.query(**query_params)
        except Exception as e:
            logger.warning("[frontend] 审计日志查询失败: %s", e)
            st.error("⚠️ 日志查询失败，请稍后重试")
            return

        if selected_status != "全部":
            records = [r for r in records if r.get("status") == selected_status]

        st.caption(f"显示 {len(records)} 条记录" + (f"（已筛选）" if (selected_type != "全部" or selected_status != "全部" or session_search or selected_time_range != "全部") else ""))

        if not records:
            st.info("💡 没有匹配的操作记录。尝试调整筛选条件。")
            return

        for idx, record in enumerate(records):
            timestamp_str = datetime.fromtimestamp(record.get("timestamp", 0)).strftime("%H:%M:%S")
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
                expanded=(idx == 0)
            ):
                col_meta, col_detail = st.columns([1, 2])

                with col_meta:
                    st.markdown(f"**状态**: :{status_color}[{status.upper()}]")
                    st.markdown(f"**Session**: `{session_id}`")
                    st.markdown(f"**耗时**: {duration}ms")
                    st.markdown(f"**技能**: `{skill_id}`")

                with col_detail:
                    if input_summary:
                        st.markdown("**输入摘要**:")
                        st.text(input_summary[:200])
                    if output_summary:
                        st.markdown("**输出摘要**:")
                        st.text(output_summary[:300])

        if len(records) >= 50:
            if st.button("📄 加载更多", key="audit_load_more"):
                st.info("💡 当前最多显示50条记录。如需查看更多，请缩小时间范围。")

    except ImportError:
        st.warning("⚠️ 审计日志模块未就绪，此功能需要完整安装")
    except Exception as e:
        friendly_error = ErrorHandler.translate(e, context="加载操作日志时")
        st.error(friendly_error.user_message)
        if friendly_error.suggestion:
            st.info(friendly_error.suggestion)
        logger.error("[frontend] 操作日志页面错误: %s", friendly_error.traceback_str)


def _show_onboarding_overlay():
    """Show onboarding overlay for first-time users.

    If onboarding not completed, shows a modal/dialog overlay
    with the OnboardingManager step content.
    """
    try:
        from opc_manager.onboarding import get_onboarding, OnboardingStep
        onboard = get_onboarding()

        current = onboard.get_current_step()
        step_content = onboard.get_step_content(current)
        current_step_value = current.value
        total_steps = onboard.TOTAL_STEPS

        st.markdown("""
        <style>
        .onboarding-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.7);
            z-index: 99999;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .onboarding-card {
            background: white;
            padding: 40px;
            border-radius: 12px;
            max-width: 600px;
            width: 90%;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
        }
        </style>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(f"# {step_content.get('icon', '🎉')} {step_content.get('title', '欢迎使用')}")

        step_order = [OnboardingStep.WELCOME, OnboardingStep.LLM_CONFIG, OnboardingStep.SAMPLE_TASK]
        try:
            current_index = step_order.index(current)
            progress_dots = " ".join([
                "●" if i == current_index else "○"
                for i in range(total_steps)
            ])
        except ValueError:
            progress_dots = "●" + " ○" * (total_steps - 1)
        st.markdown(f"<center>{progress_dots}</center>", unsafe_allow_html=True)

        if step_content.get('description'):
            st.markdown(f"\n{step_content['description']}\n")

        col_prev, col_next, col_skip = st.columns([1, 1, 1])

        with col_prev:
            if current != OnboardingStep.WELCOME:
                if st.button("← 上一步"):
                    try:
                        prev_index = step_order.index(current) - 1
                        if prev_index >= 0:
                            onboard.advance_to_step(step_order[prev_index])
                            st.rerun()
                    except ValueError:
                        pass

        with col_next:
            is_last = (current == OnboardingStep.SAMPLE_TASK)
            btn_label = "🎉 完成！" if is_last else "下一步 →"
            if st.button(btn_label, type="primary", use_container_width=True):
                if is_last:
                    onboard.complete_onboarding()
                    st.success("✅ 欢迎使用 OPC-Agents！")
                    st.rerun()
                else:
                    try:
                        next_index = step_order.index(current) + 1
                        if next_index < len(step_order):
                            onboard.advance_to_step(step_order[next_index])
                            st.rerun()
                    except ValueError:
                        pass

        with col_skip:
            if st.button("跳过引导"):
                onboard.skip_onboarding()
                st.info("已跳过引导，你可以随时在设置中重新查看")
                st.rerun()

    except ImportError:
        st.warning("引导模块加载失败，请刷新页面重试")
    except Exception as e:
        logger.error("[frontend] Onboarding error: %s", e)
        st.error("引导程序出现错误")


if page == "⚙️ 设置":
    """设置页面 — 用户偏好和系统配置

    v0.2.0 升级: 完整的5Tab设置系统
    - 🧠 LLM配置: Provider/API Key/模型参数/测试连接
    - 📧 SMTP配置: 邮件服务器/预设服务商/测试连接
    - 🔑 API密钥: 统一管理所有API密钥
    - 🔒 安全设置: 加密密钥状态/重新生成
    - 👤 个人信息: 用户资料/时区/语言
    """
    _create_settings_page()


if st.query_params.get("_stcore_health") == "1":
    st.write("ok")
    st.stop()
