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
v0.2.0: 模块化重构 - 拆分为 pages/ 和 components/ 子模块
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


def _is_demo_mode():
    """判断是否处于演示模式（无API Key配置）"""
    return not _has_api_key()


def _get_demo_dashboard_data():
    """Return sample dashboard data for demo/no-LLM mode."""
    return {
        "income_trend": {
            "labels": ["1月", "2月", "3月", "4月", "5月"],
            "values": [12000, 15000, 13500, 18000, 22000],
            "total": 80500,
            "growth": "+63%"
        },
        "client_health": [
            {"name": "张三科技", "score": 92, "trend": "up", "projects": 3},
            {"name": "李四咨询", "score": 78, "trend": "stable", "projects": 2},
            {"name": "王五集团", "score": 85, "trend": "up", "projects": 1},
        ],
        "task_completion": {"total": 24, "done": 18, "rate": "75%"},
        "financial_summary": {"income": 80500, "expenses": 12500, "profit": 68000},
        "timeline": [
            {"time": "09:00", "event": "完成周报", "type": "deliverable"},
            {"time": "11:00", "event": "收入记录 ¥5000", "type": "finance"},
            {"time": "14:00", "event": "客户会议", "type": "meeting"},
            {"time": "16:00", "event": "方案提交", "type": "proposal"},
        ],
        "skill_usage": [
            {"name": "CRM技能", "count": 45},
            {"name": "财务技能", "count": 32},
            {"name": "报告生成", "count": 28},
        ]
    }


def _show_success_toast(message: str):
    """Display a visible success confirmation after user actions."""
    st.success(f"✅ {message}")


# Import shared components and page modules
from frontend.components.shared import (
    _get_export_bytes, _get_mime_type, _render_batch_export_section,
    _execute_batch_export, _render_single_export_buttons, _event_type_label,
    _event_emoji, _render_progress_indicator, _auto_refresh_progress,
    _render_export_buttons, _get_undo_manager, _cached_list_undoable,
    _render_theme_selector, _render_language_selector,
    _render_shortcuts_help, _get_current_session_id,
    show_success, show_error, show_info,
    _maybe_show_shortcut_hints, _render_floating_help_button,
)

from frontend.components.undo_panel import (
    render_undo_panel,
    render_mini_undo_hint,
    render_batch_undo,
    check_has_active_undo_records,
)

from frontend.pages.settings_page import (
    _create_settings_page,
)

from frontend.pages.dashboard_page import (
    _render_dashboard_page,
)

from frontend.pages.marketplace_page import (
    _render_skill_marketplace_page, _render_global_search, _execute_global_search,
)

from frontend.components.confirmation_dialog import (
    build_confirm_callback,
    check_pending_confirmation,
    render_confirmation_dialog,
    clear_pending_confirmation,
)

from frontend.components.input_autocomplete import (
    render_autocomplete_input,
)


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
    {"id": "content_calendar", "icon": "📅", "title": "内容日历规划", "desc": "帮你规划下周的选题和发布节奏", "prompt": "帮我规划下周的内容日历和选题排期"},
    {"id": "digital_product_launch", "icon": "🎯", "title": "数字产品发布", "desc": "从定价到上线的完整方案", "prompt": "帮我制定数字产品的发布方案，包括定价和推广"},
    {"id": "feedback_analysis", "icon": "💬", "title": "用户反馈分析", "desc": "从用户声音中提炼行动项", "prompt": "帮我分析用户反馈，提炼关键行动项"},
    {"id": "consulting_proposal", "icon": "📝", "title": "咨询提案撰写", "desc": "专业提案框架+行业洞察", "prompt": "帮我撰写一份专业咨询提案"},
    {"id": "ecommerce_ops", "icon": "🛒", "title": "电商运营优化", "desc": "GMV提升策略与执行清单", "prompt": "帮我优化电商运营，提升GMV"},
    {"id": "project_deliverable", "icon": "📦", "title": "项目交付物整理", "desc": "交付物清单+质量检查", "prompt": "帮我整理项目交付物并做质量检查"},
    {"id": "write_report", "icon": "📄", "title": "报告撰写", "desc": "结构化报告+数据支撑", "prompt": "帮我写一份结构化的分析报告"},
    {"id": "organize_meeting", "icon": "🤝", "title": "会议组织", "desc": "议程+纪要+跟进清单", "prompt": "帮我组织一次项目会议"},
]


def safe_detect(prompt_text):
    """安全包装的业务类型检测 — 防止后端异常导致前端崩溃"""
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
    """安全包装的人格信息获取 — 防止get_persona返回None导致AttributeError"""
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
    """安全包装的成长飞轮记录 — 记录用户互动并更新飞轮分数"""
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
    """生成唯一的成果物文件名"""
    safe_name = (
        re.sub(r'[\\/*?:"<>|\n\r\t]', "", prompt[:30])
        .replace(" ", "_")
        .replace("/", "-")
    ) or "task"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{task_type}_{safe_name}.md"


def save_deliverable(content: str, prompt: str, task_type: str, meta: dict = None) -> tuple:
    """将生成的成果物内容写入文件系统并注册到session_state"""
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
    """Execute task via AgentLoop (Three-Sage Architecture) with fallback to TaskEngineV3"""
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
    """Execute task pipeline — from user input to file delivery"""
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


async def _async_execute_task(prompt: str, cancel_event, session_ctx=None, business_type=None) -> dict:
    """Async execution wrapper for AsyncTaskExecutor background thread

    Integrated with Confirmer system for risk operation confirmation:
    - Builds confirm_callback for high-risk operations
    - Checks confirmation before execution
    - Emits ProgressEmitter events for tracking
    """
    try:
        logger.debug("[frontend-async] 开始后台执行: %s", prompt[:50])

        session_id = getattr(session_ctx, '_session_id', None) if session_ctx else None
        if not session_id:
            from frontend.components.shared import _get_current_session_id
            session_id = _get_current_session_id()

        detected_intent = business_type or "GENERAL_CHAT"
        ai_confidence = 0.75

        try:
            from opc_manager.confirmer import Confirmer
            from frontend.components.confirmation_dialog import build_confirm_callback

            confirmer = Confirmer()

            if session_id and session_id != "default":
                confirm_cb = build_confirm_callback(session_id)

                confirmation_result = await confirmer.check_confirmation(
                    session_id=session_id,
                    intent_type=detected_intent,
                    goal=prompt,
                    confidence=ai_confidence,
                    params={"prompt": prompt[:100]},
                    confirm_callback=confirm_cb,
                )

                if not confirmation_result.confirmed:
                    logger.info("[frontend-async] 操作被用户取消: %s", prompt[:50])
                    return {
                        "content": None,
                        "success": False,
                        "filepath": None,
                        "task_type": None,
                        "error": "操作已被用户取消",
                        "deliverable_record": None,
                        "_cancelled_by_user": True,
                    }

                if confirmation_result.method == "skipped":
                    logger.info("[frontend-async] 用户选择跳过并信任: %s", prompt[:50])
        except ImportError:
            logger.debug("[frontend-async] Confirmer不可用，跳过确认步骤")
        except Exception as e:
            logger.warning("[frontend-async] 确认检查失败（继续执行）: %s", e)

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


# === Page Configuration & Initialization ===

st.set_page_config(
    page_title="一人公司助手",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEMO_MODE = _is_demo_mode()
if DEMO_MODE:
    st.markdown("""
    <div style="
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        text-align: center;
        margin-bottom: 16px;
        font-size: 15px;
    ">
        🎮 <strong>演示模式</strong> — 配置 AI Key 后解锁完整功能 &nbsp;|&nbsp;
        前往 ⚙️ 设置 → LLM配置 填入 API Key 开始使用
    </div>
    """, unsafe_allow_html=True)

if "initialized" not in st.session_state:
    """首次访问初始化所有session_state变量"""
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


# === Sidebar Navigation ===

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

    with st.container():
        if st.button("↩️ 撤销历史", use_container_width=True, help="查看和管理可撤销的操作"):
            st.session_state.show_undo_panel = not st.session_state.get("show_undo_panel", False)

        if st.session_state.get("show_undo_panel", False):
            session_id = _get_current_session_id()
            with st.expander("撤销历史详情", expanded=True):
                render_undo_panel(session_id, expand=True)

                if check_has_active_undo_records(session_id):
                    with st.expander("📦 批量撤销（高级）", expanded=False):
                        render_batch_undo(session_id)

    st.divider()

    with st.container():
        if st.button("📡 实时日志", use_container_width=True, help="查看实时系统日志和任务执行详情"):
            st.session_state.show_log_panel = not st.session_state.get("show_log_panel", False)

        if st.session_state.get("show_log_panel", False):
            with st.expander("📡 实时日志监控面板", expanded=True):
                from frontend.components.live_log_panel import render_live_log_panel
                render_live_log_panel(auto_refresh=True, refresh_interval=2)

    st.divider()

    _render_theme_selector()
    _render_language_selector()
    _render_shortcuts_help()

    st.divider()
    from opc_manager.version import get_version

    st.caption(f"OPC-Agents v{get_version()}")


# === Main Chat Page ===

if page == "💬 对话":
    """主对话页面 — 用户交互的核心界面"""
    _maybe_show_shortcut_hints()
    if DEMO_MODE:
        st.markdown("## 🎮 演示模式")
        st.info("""
**当前为演示模式** — 以下功能在演示模式下受限：

| 功能 | 状态 |
|------|------|
| 📈 Dashboard 查看 | ✅ 可用（示例数据） |
| ⚙️ 设置页面 | ✅ 可用（可配置 API Key） |
| 🏪 技能市场浏览 | ✅ 可用 |
| 💬 AI 对话 / 任务执行 | 🔒 需要配置 API Key |

👉 **前往 ⚙️ 设置 → LLM配置 填入 API Key 即可解锁完整功能**
""")
        st.markdown("### 📊 演示数据预览")
        demo = _get_demo_dashboard_data()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("本月收入", f"¥{demo['financial_summary']['income']:,}")
        with col2:
            st.metric("任务完成率", demo['task_completion']['rate'])
        with col3:
            st.metric("收入增长", demo['income_trend']['growth'])
        st.markdown("---")
        st.caption("💡 配置 API Key 后，所有 AI 功能将立即解锁。请前往「⚙️ 设置」页面进行配置。")
        st.stop()
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
    elif prompt := render_autocomplete_input(
        label="告诉我你需要什么结果，我直接做完并交付文件...",
        key="user_input_main",
        session_history=st.session_state.get("messages", []),
    ):
        st.session_state.messages.append({"role": "user", "content": prompt})
        _save_chat_history()
        with st.chat_message("user"):
            st.markdown(prompt)
    else:
        prompt = None

    if prompt:

        pending_confirm = check_pending_confirmation()
        if pending_confirm:
            with st.container():
                st.warning("⚠️ 检测到待确认的高风险操作")
                confirmed = render_confirmation_dialog(pending_confirm)

                if not confirmed:
                    clear_pending_confirmation()
                    st.stop()

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
                    session_id = _get_current_session_id()

                    real_progress = None
                    real_message = None
                    real_event_type = None

                    if session_id and session_id != "default":
                        try:
                            from opc_manager.progress_emitter import ProgressEmitter
                            emitter = ProgressEmitter()
                            history = emitter.get_history(session_id)
                            if history:
                                latest = history[-1]
                                real_progress = latest.get("progress", latest.get("progress_pct"))
                                real_message = latest.get("message", "")
                                real_event_type = latest.get("event", latest.get("event_type", ""))
                        except Exception as e:
                            logger.debug("[frontend] 读取真实进度失败，回退到估算: %s", e)

                    if real_progress is not None:
                        progress_pct = min(real_progress, 100)
                        phase_hint = real_message or phase_hint
                        if real_event_type:
                            phase_icon, phase_name = _get_phase_from_event(real_event_type)
                    else:
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
                        label=f"{phase_icon} {phase_name} ({elapsed:.0f}s / 预计还需{remaining:.0f}s)" if real_progress is None else f"{phase_icon} {phase_name}",
                        state="running",
                    )
                    progress_placeholder.progress(
                        progress_pct / 100.0,
                        text=f"{'真实' if real_progress is not None else '预估'}进度 {progress_pct}% — {phase_hint} — 已耗时 {elapsed:.0f}s",
                    )

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
                        from frontend.components.result_cards import render_result_card

                        render_result_card(
                            content=result_content,
                            task_type=task_status.get("task_type"),
                            deliverable_record=result_deliverable_record,
                            filepath=result_filepath,
                        )
                        show_success(f"成果物已创建: {os.path.basename(result_filepath) if result_filepath else '任务完成'}")

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

                        session_id = _get_current_session_id()
                        render_mini_undo_hint(session_id, task_id=task_id)

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
                                show_success(f"成果物已生成: {os.path.basename(result_filepath)}")

                        msg_record = {
                            "role": "assistant",
                            "content": result_content,
                            "deliverable_id": f"{int(time.time()*1000)}",
                        }
                        if result_filepath and os.path.exists(result_filepath):
                            msg_record["deliverable_path"] = result_filepath
                        st.session_state.messages.append(msg_record)
                        _save_chat_history()

                        from frontend.components.smart_suggestions import (
                            build_context_from_session,
                            generate_suggestions,
                            render_suggestion_panel,
                        )
                        suggestion_context = build_context_from_session(
                            last_task_type=task_type or result_deliverable_record.get("task_type", ""),
                            last_result={
                                "execution_time_ms": result_deliverable_record.get("execution_time_ms", 0) if result_deliverable_record else 0,
                                "sources_count": result_deliverable_record.get("sources_count", 0) if result_deliverable_record else 0,
                            },
                            deliverables=st.session_state.get("deliverables", []),
                            feedback_history=list(st.session_state.get("quality_feedback", {}).items()),
                        )

                        suggestion_context["session_id"] = session_id

                        suggestions = generate_suggestions(suggestion_context)
                        if suggestions:
                            render_suggestion_panel(suggestions, max_show=3)
                    break

                elif current_status == "failed":
                    error_msg = task_status.get("error_message", "未知错误")

                    if task_status.get("_cancelled_by_user"):
                        status_container.update(label="⏹️ 操作已取消", state="complete")
                        st.info("操作已被用户取消")
                        clear_pending_confirmation()
                        break

                    status_container.update(label="❌ 任务执行失败", state="error")

                    track_error(
                        Exception(error_msg), {"mode": "async"}
                    )

                    FRIENDLY_ERRORS = {
                        "timeout": ("⏰ AI助手思考时间过长", "网络或AI服务响应较慢，请稍后重试。简短的需求通常更快完成。"),
                        "connection": ("🌐 网络连接中断", "请检查网络连接后重试。如果问题持续，可能是AI服务暂时不可用。"),
                        "api_key": ("🔑 API Key无效或已过期", "请在.env文件中更新你的API Key，然后重启应用。"),
                        "incorrect api key": ("🔑 API Key无效或已过期", "请在.env文件中更新你的API Key，然后重启应用。"),
                        "authentication": ("🔑 认证失败", "API Key可能无效或已过期，请检查配置后重试。"),
                        "rate_limit": ("🚦 请求过于频繁", "AI服务暂时限流，请等待1-2分钟后重试。"),
                        "rate limit": ("🚦 请求过于频繁", "AI服务暂时限流，请等待1-2分钟后重试。"),
                        "429": ("🚦 请求过于频繁", "AI服务暂时限流，请等待1-2分钟后重试。"),
                        "server_error": ("🔧 AI服务暂时不可用", "服务端正在维护，请稍后重试。系统会自动使用模板模式作为备选。"),
                        "500": ("🔧 AI服务暂时不可用", "服务端正在维护，请稍后重试。"),
                        "502": ("🔧 AI服务暂时不可用", "服务端正在维护，请稍后重试。"),
                        "503": ("🔧 AI服务暂时不可用", "服务端正在维护，请稍后重试。"),
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
                    show_error(f"操作失败: {friendly_title}")
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


# === Deliverables Page ===

elif page == "📁 成果物":
    """成果物库页面 — 历史文件的管理中心 + 操作日志查看"""
    st.markdown("## 📁 我的成果物")

    deliverable_tabs = st.tabs(["📄 成果物文件", "📋 操作日志"])

    with deliverable_tabs[0]:
        _render_deliverables_list()

    with deliverable_tabs[1]:
        _render_audit_log_page()


# === Growth/Flywheel Page ===

elif page == "📊 成长":
    """成长飞轮页面 — 游戏化的用户激励系统"""
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


# === Marketplace Page ===

elif page == "🏪 技能市场":
    _render_skill_marketplace_page()


# === Dashboard Page ===

elif page == "📈 Dashboard":
    _render_dashboard_page(demo_mode=DEMO_MODE)


# === Settings Page ===

elif page == "⚙️ 设置":
    """设置页面 — 用户偏好和系统配置"""
    _create_settings_page()


# === Health Check Endpoint ===

if st.query_params.get("_stcore_health") == "1":
    st.write("ok")
    st.stop()


# === Deliverables List Renderer (stays in app.py) ===

def _render_deliverables_list():
    """Render the deliverables file list (original functionality)."""
    if not st.session_state.deliverables:
        st.info("💡 还没有生成任何成果物。去「对话」页面执行一个任务吧！")
    else:
        st.caption(f"共 {len(st.session_state.deliverables)} 个成果物")

        st.divider()

        _render_batch_export_section(DELIVERABLES_DIR)

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


# === Audit Log Page Renderer (stays in app.py) ===

def _render_audit_log_page():
    """Render the Audit Log viewer page."""
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


# === Onboarding Overlay (stays in app.py) ===

def _show_onboarding_overlay():
    """Show onboarding overlay for first-time users."""
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
