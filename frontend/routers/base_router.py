"""Base router with shared initialization, constants, and utility functions."""
import streamlit as st
import os
import re
import html
import time
import json
import logging
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from opc_manager.i18n import t as _t

logger = logging.getLogger(__name__)

_WORKSPACE_DIR = os.environ.get("OPC_WORKSPACE", os.getcwd())
load_dotenv(Path(_WORKSPACE_DIR) / ".env")

DELIVERABLES_DIR = os.path.join(_WORKSPACE_DIR, "deliverables")
CHAT_HISTORY_FILE = os.path.join(_WORKSPACE_DIR, "data", "chat_history.json")


def _has_api_key():
    """Check if a valid API Key is configured (excluding whitespace-only values)."""
    return bool(
        (os.environ.get("MOKA_API_KEY") or "").strip()
        or (os.environ.get("GLM_API_KEY") or "").strip()
        or (os.environ.get("OPENAI_API_KEY") or "").strip()
    )


def _is_demo_mode():
    """Determine if running in demo mode (no API Key configured)."""
    return not _has_api_key()


DEMO_MODE = _is_demo_mode()

PERSONA_MAP = {
    "content_creator": ("persona_content_name", "persona_content_style"),
    "digital_product": ("persona_product_name", "persona_product_style"),
    "ai_tool_builder": ("persona_tech_name", "persona_tech_style"),
    "consultant": ("persona_consultant_name", "persona_consultant_style"),
    "ecommerce": ("persona_ecommerce_name", "persona_ecommerce_style"),
    "creative_work": ("persona_creative_name", "persona_creative_style"),
}

TYPE_DISPLAY = {
    "content_creator": "type_content_creator",
    "digital_product": "type_digital_product",
    "ai_tool_builder": "type_ai_tool_builder",
    "consultant": "type_consultant",
    "ecommerce": "type_ecommerce",
    "creative_work": "type_creative_work",
}

SCENARIOS_CORE = [
    {
        "id": "content_creation",
        "icon": "✍️",
        "title": "scenario_core_content_title",
        "desc": "scenario_core_content_desc",
        "coverage": ["scenario_core_content_coverage_1", "scenario_core_content_coverage_2"],
        "prompt": "帮我规划下周的内容日历和选题",
    },
    {
        "id": "product_launch",
        "icon": "🚀",
        "title": "scenario_core_product_title",
        "desc": "scenario_core_product_desc",
        "coverage": ["scenario_core_product_coverage_1", "scenario_core_product_coverage_2"],
        "prompt": "帮我制定新产品发布的完整方案",
    },
    {
        "id": "data_analysis",
        "icon": "📊",
        "title": "scenario_core_data_title",
        "desc": "scenario_core_data_desc",
        "coverage": ["scenario_core_data_coverage_1", "scenario_core_data_coverage_2"],
        "prompt": "帮我分析用户反馈并提炼行动项",
    },
    {
        "id": "project_mgmt",
        "icon": "📋",
        "title": "scenario_core_project_title",
        "desc": "scenario_core_project_desc",
        "coverage": ["scenario_core_project_coverage_1", "scenario_core_project_coverage_2", "scenario_core_project_coverage_3"],
        "prompt": "帮我撰写一份专业咨询提案",
    },
]

SCENARIOS_MORE = [
    {"id": "content_calendar", "icon": "📅", "title": "scenario_more_calendar_title", "desc": "scenario_more_calendar_desc", "prompt": "帮我规划下周的内容日历和选题排期"},
    {"id": "digital_product_launch", "icon": "🎯", "title": "scenario_more_digital_title", "desc": "scenario_more_digital_desc", "prompt": "帮我制定数字产品的发布方案，包括定价和推广"},
    {"id": "feedback_analysis", "icon": "💬", "title": "scenario_more_feedback_title", "desc": "scenario_more_feedback_desc", "prompt": "帮我分析用户反馈，提炼关键行动项"},
    {"id": "consulting_proposal", "icon": "📝", "title": "scenario_more_proposal_title", "desc": "scenario_more_proposal_desc", "prompt": "帮我撰写一份专业咨询提案"},
    {"id": "ecommerce_ops", "icon": "🛒", "title": "scenario_more_ecommerce_title", "desc": "scenario_more_ecommerce_desc", "prompt": "帮我优化电商运营，提升GMV"},
    {"id": "project_deliverable", "icon": "📦", "title": "scenario_more_deliverable_title", "desc": "scenario_more_deliverable_desc", "prompt": "帮我整理项目交付物并做质量检查"},
    {"id": "write_report", "icon": "📄", "title": "scenario_more_report_title", "desc": "scenario_more_report_desc", "prompt": "帮我写一份结构化的分析报告"},
    {"id": "organize_meeting", "icon": "🤝", "title": "scenario_more_meeting_title", "desc": "scenario_more_meeting_desc", "prompt": "帮我组织一次项目会议"},
    {"id": "social_publish", "icon": "📢", "title": "scenario_social_publish_title", "desc": "scenario_social_publish_desc", "prompt": "帮我在多个社交平台发布内容并管理互动"},
    {"id": "generate_invoice", "icon": "🧾", "title": "scenario_invoice_title", "desc": "scenario_invoice_desc", "prompt": "帮我生成一张专业的发票或账单"},
    {"id": "competitor_watch", "icon": "🔭", "title": "scenario_competitor_title", "desc": "scenario_competitor_desc", "prompt": "帮我监控竞品动态和市场趋势变化"},
    {"id": "pricing_strategy", "icon": "💎", "title": "scenario_pricing_title", "desc": "scenario_pricing_desc", "prompt": "帮我制定产品或服务的最优定价策略"},
    {"id": "tax_reminder", "icon": "🏛️", "title": "scenario_tax_reminder_title", "desc": "scenario_tax_reminder_desc", "prompt": "提醒我即将到期的税务申报和合规事项"},
    {"id": "opc_creative_planning", "icon": "💡", "title": "scenario_opc_creative_planning_title", "desc": "scenario_opc_creative_planning_desc", "prompt": "帮我想一些创业创意方向，我想利用我的特殊知识建立一人公司"},
    {"id": "opc_market_research", "icon": "🔍", "title": "scenario_opc_market_research_title", "desc": "scenario_opc_market_research_desc", "prompt": "帮我验证这个创意的市场需求，看看是否有真实的用户痛点"},
    {"id": "opc_growth_hacker", "icon": "🚀", "title": "scenario_opc_growth_hacker_title", "desc": "scenario_opc_growth_hacker_desc", "prompt": "帮我设计一个0预算的增长策略，快速获取前100个种子用户"},
    {"id": "opc_social_listening", "icon": "👂", "title": "scenario_opc_social_listening_title", "desc": "scenario_opc_social_listening_desc", "prompt": "帮我从Reddit和Twitter上挖掘用户对这个话题的真实抱怨和痛点"},
    {"id": "opc_legal_advisor", "icon": "⚖️", "title": "scenario_opc_legal_advisor_title", "desc": "scenario_opc_legal_advisor_desc", "prompt": "帮我审查这份合同条款，看看有没有对我不利的霸王条款"},
    {"id": "opc_proposal_review", "icon": "🔬", "title": "scenario_opc_proposal_review_title", "desc": "scenario_opc_proposal_review_desc", "prompt": "帮我评估这个项目的可行性，用逆向思维分析可能失败的原因"},
    {"id": "opc_prd_generation", "icon": "📋", "title": "scenario_opc_prd_generation_title", "desc": "scenario_opc_prd_generation_desc", "prompt": "帮我把这个方案转化成详细的PRD文档，定义清楚功能需求和验收标准"},
    {"id": "opc_domain_brand", "icon": "🎨", "title": "scenario_opc_domain_brand_title", "desc": "scenario_opc_domain_brand_desc", "prompt": "帮我为这个产品起个好名字，检查域名可用性，并提供Logo设计灵感"},
]

_TASK_TYPE_LABELS = {
    "INFO_COLLECTION": "task_type_info_collection",
    "CONTENT_GENERATION": "task_type_content_generation",
    "DATA_ANALYSIS": "task_type_data_analysis",
    "SCENARIO_BASED": "task_type_scenario_based",
    "GENERAL_CHAT": "task_type_general_chat",
}
_TASK_TYPE_GENERIC = "task_type_generic"


def init_session_state():
    """Initialize all required session_state keys with safe defaults."""
    defaults = {
        "messages": [],
        "pending_prompt": None,
        "current_task_id": None,
        "task_status": {},
        "deliverables": [],
        "flywheel_scores": {
            "content_quality": 0,
            "audience_growth": 0,
            "monetization": 0,
            "cross_promotion": 0,
            "ecosystem_synergy": 0,
        },
        "flywheel_level": 1,
        "scenario_count": 0,
        "undo_enabled": True,
        "quality_mode": True,
        "shortcuts_shown": False,
        "last_failed_prompt": None,
        "onboarding_complete": False,
        "onboarding_step": 0,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


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


def safe_detect(prompt_text):
    """Safe wrapper for business type detection — prevents backend crashes."""
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
    """Safe wrapper for persona info retrieval — prevents AttributeError."""
    try:
        from opc_manager.persona_manager import PersonaManager
        from opc_manager.business_types import BusinessType

        if "persona_manager" not in st.session_state:
            st.session_state.persona_manager = PersonaManager()
        pm = st.session_state.persona_manager
        persona = pm.get_persona(business_type=BusinessType(type_value))
        if persona:
            return persona.display_name, persona.style_overrides.get("tone", _t("persona_fallback_style"))
        return _t("persona_fallback_name"), _t("persona_fallback_style")
    except Exception as e:
        logger.debug("[frontend] persona error: %s", e)
        name = _t(PERSONA_MAP.get(type_value, ("persona_fallback_name", "persona_fallback_style_alt"))[0])
        return name, _t("persona_fallback_style_alt")


def safe_track_flywheel(type_value):
    """Safe wrapper for flywheel tracking — records interaction and updates scores."""
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
            "content_creator": "dim_content_quality",
            "digital_product": "dim_monetization",
            "ai_tool_builder": "dim_cross_promotion",
            "consultant": "dim_audience_growth",
            "ecommerce": "dim_monetization",
            "creative_work": "dim_content_quality",
        }
        dim_key = _t(dim_map.get(type_value, "dim_content_quality"))
        scores[dim_key] = min(100, scores.get(dim_key, 0) + 8)

        avg = sum(scores.values()) / len(scores) if scores else 0
        st.session_state.flywheel_level = 3 if avg >= 60 else (2 if avg >= 35 else 1)
        return True
    except Exception as e:
        logger.debug("[frontend] flywheel error: %s", e)
        st.session_state.scenario_count += 1
        return False


def generate_filename(prompt: str, task_type: str) -> str:
    """Generate a unique deliverable filename."""
    safe_name = (
        re.sub(r'[\\/*?:"<>|\n\r\t]', "", prompt[:30])
        .replace(" ", "_")
        .replace("/", "-")
    ) or "task"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{task_type}_{safe_name}.md"


def save_deliverable(content: str, prompt: str, task_type: str, meta: dict = None) -> tuple:
    """Save deliverable content to filesystem and register in session_state."""
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
    import os as _os
    import asyncio

    use_agent_loop = st.session_state.get("exec_mode", _t("mode_quality")) == _t("mode_quality")

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
        task_type_label = _t(_TASK_TYPE_LABELS.get(task_result.task_type.name, _TASK_TYPE_GENERIC))
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
        task_type_label = _t(_TASK_TYPE_LABELS.get(result.task_type.name, _TASK_TYPE_GENERIC))
        meta_lines.append(f"📌 任务类型: {task_type_label}")
        if result.sources:
            meta_lines.append(f"🔗 信息来源: {len(result.sources)} 条")
        if result.deliverable_format:
            meta_lines.append(f"📦 格式: {result.deliverable_format}")

        meta_str = "\n".join(meta_lines)

        has_api_key = _has_api_key()
        mode_tag = ""
        if not has_api_key:
            mode_tag = f"\n\n> {_t('mode_template')}"
        else:
            from opc_manager.simple_llm_service import SimpleLLMService
            svc = SimpleLLMService()
            if svc.is_available():
                mode_tag = f"\n\n> {_t('mode_ai')}"
            else:
                mode_tag = f"\n\n> {_t('mode_rule')}"

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
    """Async execution wrapper for AsyncTaskExecutor background thread.

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
                        "error": _t("error_cancelled_by_user"),
                        "deliverable_record": None,
                        "_cancelled_by_user": True,
                    }

                if confirmation_result.method == "skipped":
                    logger.info("[frontend-async] 用户选择跳过并信任: %s", prompt[:50])
        except ImportError:
            logger.debug("[frontend-async] Confirmer不可用，跳过确认步骤")
        except Exception as e:
            logger.warning("[frontend-async] 确认检查失败（继续执行）: %s", e)

        # MemoryBridge: 任务前注入记忆上下文
        memory_context = ""
        _mb = None
        original_prompt = prompt  # 保存原始用户输入，用于后续记忆存储
        try:
            from opc_manager.memory_bridge import get_memory_bridge
            _mb = get_memory_bridge()
            if _mb.enabled:
                memory_context = _mb.build_context(prompt)
                if memory_context:
                    prompt = f"{memory_context}\n\n{prompt}"
                    logger.debug("[frontend-async] 记忆上下文已注入")
        except Exception as e:
            logger.debug("[frontend-async] 记忆注入跳过: %s", e)

        # KnowledgeBridge: 任务前注入知识库参考
        knowledge_context = ""
        try:
            from opc_manager.knowledge_bridge import get_knowledge_bridge
            _kb = get_knowledge_bridge()
            if _kb.enabled:
                knowledge_context = _kb.build_knowledge_prompt(original_prompt[:200])
                if knowledge_context:
                    prompt = f"{knowledge_context}\n\n{prompt}"
                    logger.debug("[frontend-async] 知识库上下文已注入")
        except Exception as e:
            logger.debug("[frontend-async] 知识库注入跳过: %s", e)

        content, success, filepath, task_type, deliverable_record = execute_with_agent_loop(
            prompt, session_ctx=session_ctx, business_type=business_type
        )
        logger.debug(
            f"[frontend-async] 执行完成: success={success}, has_content={bool(content)}"
        )

        # MemoryBridge: 任务后存储记忆
        try:
            if _mb is not None and _mb.enabled and content:
                _mb.remember(
                    user_input=original_prompt,
                    result=content[:500],
                    evaluation={"success": success},
                )
        except Exception as e:
            logger.debug("[frontend-async] 记忆存储跳过: %s", e)

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
                "error": _t("error_task_no_result"),
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


def _sync_execute_task(prompt: str, cancel_event, session_ctx=None, business_type=None) -> dict:
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                _async_execute_task(prompt, cancel_event, session_ctx=session_ctx, business_type=business_type)
            )
        finally:
            loop.close()
    except RuntimeError:
        try:
            return asyncio.get_event_loop().run_until_complete(
                _async_execute_task(prompt, cancel_event, session_ctx=session_ctx, business_type=business_type)
            )
        except Exception as e2:
            logger.warning("[frontend-async] fallback event loop failed: %s", e2)
            return {
                "content": None, "success": False, "filepath": None,
                "task_type": None, "error": str(e2), "deliverable_record": None,
            }
