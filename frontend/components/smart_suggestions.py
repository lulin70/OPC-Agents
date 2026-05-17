"""Smart Suggestions System for OPC-Agents

Context-aware next-step recommendations after task completion.
Uses heuristic rule engine (no LLM dependency) for <100ms response time.

Design:
- 4 suggestion categories: follow_up, related, improvement, exploration
- Confidence-based ranking (0-1)
- Max 3 visible, expandable to 10
- One-click execution via st.session_state triggers
"""

import streamlit as st
import logging
import uuid
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from collections import Counter

logger = logging.getLogger(__name__)


@dataclass
class Suggestion:
    """Single smart suggestion item"""
    id: str
    title: str
    description: str
    icon: str
    action_type: str  # "quick_task" | "navigate_tab" | "open_settings"
    action_payload: dict
    confidence: float  # 0-1
    category: str  # "follow_up" | "related" | "improvement" | "exploration"


TASK_TYPE_FOLLOW_UP_MAP = {
    "content_generation": [
        Suggestion(
            id="export_pdf",
            title="导出为PDF",
            description="将当前成果导出为专业PDF文档",
            icon="📄",
            action_type="quick_task",
            action_payload={"prompt": "将刚才的内容导出为PDF格式"},
            confidence=0.9,
            category="follow_up"
        ),
        Suggestion(
            id="gen_related_doc",
            title="生成相关文档",
            description="基于当前内容生成配套文档（如PPT、大纲）",
            icon="📝",
            action_type="quick_task",
            action_payload={"prompt": "基于刚才的内容，生成相关的配套文档"},
            confidence=0.75,
            category="follow_up"
        ),
        Suggestion(
            id="share_content",
            title="分享到...",
            description="生成适合社交媒体分享的摘要版本",
            icon="📤",
            action_type="quick_task",
            action_payload={"prompt": "将刚才的内容改写为适合分享的简短版本"},
            confidence=0.65,
            category="follow_up"
        ),
    ],
    "data_analysis": [
        Suggestion(
            id="deep_dive_metric",
            title="深入分析某指标",
            description="选择关键指标进行更深入的趋势分析",
            icon="🔍",
            action_type="quick_task",
            action_payload={"prompt": "对刚才分析结果中的核心指标进行深入分析"},
            confidence=0.88,
            category="follow_up"
        ),
        Suggestion(
            id="compare_history",
            title="对比历史数据",
            description="与历史同期数据进行对比分析",
            icon="📊",
            action_type="quick_task",
            action_payload={"prompt": "将刚才的数据与历史同期进行对比分析"},
            confidence=0.82,
            category="follow_up"
        ),
        Suggestion(
            id="generate_report",
            title="生成报告",
            description="基于分析结果自动生成完整报告",
            icon="📋",
            action_type="quick_task",
            action_payload={"prompt": "基于刚才的分析结果，生成一份完整的分析报告"},
            confidence=0.85,
            category="follow_up"
        ),
    ],
    "info_collection": [
        Suggestion(
            id="gen_plan_from_info",
            title="基于信息生成方案",
            description="利用收集到的信息制定行动方案",
            icon="💡",
            action_type="quick_task",
            action_payload={"prompt": "基于刚才收集的信息，制定一个详细的执行方案"},
            confidence=0.87,
            category="follow_up"
        ),
        Suggestion(
            id="save_as_template",
            title="保存为模板",
            description="将本次搜索模式保存为可复用模板",
            icon="📌",
            action_type="quick_task",
            action_payload={"prompt": "将刚才的搜索过程总结为可复用的模板"},
            confidence=0.7,
            category="follow_up"
        ),
        Suggestion(
            id="set_reminder",
            title="设置提醒",
            description="为重要信息设置后续跟进提醒",
            icon="⏰",
            action_type="quick_task",
            action_payload={"prompt": "基于刚才收集的重要信息，设置后续跟进提醒"},
            confidence=0.72,
            category="follow_up"
        ),
    ],
    "business_operation": [
        Suggestion(
            id="view_monthly_report",
            title="查看月度报表",
            description="汇总本月所有业务操作的财务报表",
            icon="📈",
            action_type="navigate_tab",
            action_payload={"target_tab": "📈 Dashboard"},
            confidence=0.9,
            category="follow_up"
        ),
        Suggestion(
            id="record_expense",
            title="记录支出",
            description="记录相关的业务支出项",
            icon="💰",
            action_type="quick_task",
            action_payload={"prompt": "帮我记录一笔业务支出"},
            confidence=0.78,
            category="follow_up"
        ),
        Suggestion(
            id="client_followup",
            title="客户跟进提醒",
            description="为关联客户设置跟进任务",
            icon="👥",
            action_type="quick_task",
            action_payload={"prompt": "为相关客户设置跟进提醒和任务"},
            confidence=0.8,
            category="follow_up"
        ),
    ],
    "scenario_based": [
        Suggestion(
            id="review_steps",
            title="回顾执行步骤",
            description="查看工作流的详细执行过程和决策点",
            icon="🔄",
            action_type="quick_task",
            action_payload={"prompt": "回顾刚才场景工作流的所有执行步骤"},
            confidence=0.85,
            category="follow_up"
        ),
        Suggestion(
            id="adjust_rerun",
            title="调整参数重跑",
            description="修改部分参数后重新执行工作流",
            icon="⚙️",
            action_type="quick_task",
            action_payload={"prompt": "调整刚才工作流的参数并重新执行"},
            confidence=0.82,
            category="follow_up"
        ),
    ],
    "general_chat": [
        Suggestion(
            id="start_task",
            title="开始具体任务",
            description="将对话转化为具体的可执行任务",
            icon="🎯",
            action_type="quick_task",
            action_payload={"prompt": "基于刚才的讨论，帮我开始执行具体任务"},
            confidence=0.75,
            category="follow_up"
        ),
    ],
}

COMPLEMENTARY_TASKS = {
    "content_generation": ["data_analysis", "business_operation"],
    "data_analysis": ["content_generation", "info_collection"],
    "info_collection": ["content_generation", "scenario_based"],
    "business_operation": ["data_analysis", "info_collection"],
    "scenario_based": ["content_generation", "data_analysis"],
    "general_chat": ["content_generation", "info_collection"],
}

TASK_TYPE_LABELS = {
    "content_generation": "✍️ 内容生成",
    "data_analysis": "📊 数据分析",
    "info_collection": "🔍 信息收集",
    "business_operation": "🏢 业务操作",
    "scenario_based": "🎯 场景工作流",
    "general_chat": "💬 智能对话",
}


def _generate_follow_up_suggestions(context: dict) -> List[Suggestion]:
    """Generate follow-up suggestions based on completed task type"""
    task_type = context.get("last_task_type", "")
    suggestions = TASK_TYPE_FOLLOW_UP_MAP.get(task_type, [])
    return [s for s in suggestions if s.category == "follow_up"]


def _generate_related_suggestions(context: dict) -> List[Suggestion]:
    """Generate related suggestions based on user history"""
    user_history = context.get("user_history", [])
    last_task_type = context.get("last_task_type", "")

    if not user_history:
        return []

    recent_types = [h.get("task_type", "") for h in user_history[:5] if h.get("task_type")]
    type_counter = Counter(recent_types)

    complementary = COMPLEMENTARY_TASKS.get(last_task_type, [])
    suggestions = []

    for comp_type in complementary:
        if comp_type in type_counter:
            count = type_counter[comp_type]
            confidence = min(0.6 + (count * 0.08), 0.9)

            if comp_type == "data_analysis":
                suggestions.append(Suggestion(
                    id=f"rel_analysis_{comp_type}",
                    title="财务数据分析",
                    description="对近期业务数据进行深度分析",
                    icon="📊",
                    action_type="quick_task",
                    action_payload={"prompt": "对我最近的业务数据进行综合分析"},
                    confidence=confidence,
                    category="related"
                ))
            elif comp_type == "content_generation":
                suggestions.append(Suggestion(
                    id=f"rel_content_{comp_type}",
                    title="生成项目周报",
                    description="基于本周活动自动生成项目周报",
                    icon="📝",
                    action_type="quick_task",
                    action_payload={"prompt": "生成本周的项目周报"},
                    confidence=confidence,
                    category="related"
                ))
            elif comp_type == "info_collection":
                suggestions.append(Suggestion(
                    id=f"rel_info_{comp_type}",
                    title="市场调研",
                    description="收集行业最新动态和竞品信息",
                    icon="🔎",
                    action_type="quick_task",
                    action_payload={"prompt": "帮我调研一下最新的行业动态"},
                    confidence=confidence,
                    category="related"
                ))

    return suggestions


def _generate_improvement_suggestions(context: dict) -> List[Suggestion]:
    """Generate improvement suggestions based on result quality"""
    suggestions = []
    last_result = context.get("last_result", {})
    feedback_history = context.get("feedback_history", [])

    exec_time = last_result.get("execution_time_ms", 0)
    sources_count = last_result.get("sources_count", 0)

    if exec_time > 10000:
        suggestions.append(Suggestion(
            id="imp_speed",
            title="简化需求以加快响应",
            description="检测到上次执行较慢，尝试更简洁的需求描述",
            icon="⚡",
            action_type="quick_task",
            action_payload={"prompt": ""},
            confidence=0.75,
            category="improvement"
        ))

    if sources_count == 0:
        suggestions.append(Suggestion(
            id="imp_search",
            title="优化搜索描述",
            description="上次未找到参考来源，尝试更具体的关键词",
            icon="🔍",
            action_type="quick_task",
            action_payload={"prompt": ""},
            confidence=0.7,
            category="improvement"
        ))

    negative_feedback = [f for f in feedback_history if f.get("feedback") == "bad"]
    if negative_feedback:
        suggestions.append(Suggestion(
            id="imp_feedback",
            title="需要改进？换个方式试试",
            description="检测到之前的负面反馈，建议换种方式描述需求",
            icon="💭",
            action_type="quick_task",
            action_payload={"prompt": ""},
            confidence=0.8,
            category="improvement"
        ))

    return suggestions


def _generate_exploration_suggestions(context: dict) -> List[Suggestion]:
    """Generate exploration suggestions for unused features"""
    suggestions = []
    user_features_used = context.get("features_used", set())

    all_features = {"dashboard", "marketplace", "shortcuts"}
    unused = all_features - user_features_used

    if "dashboard" in unused:
        suggestions.append(Suggestion(
            id="exp_dashboard",
            title="试试仪表盘查看成长轨迹",
            description="可视化展示你的使用统计和成果趋势",
            icon="📈",
            action_type="navigate_tab",
            action_payload={"target_tab": "📈 Dashboard"},
            confidence=0.72,
            category="exploration"
        ))

    if "marketplace" in unused:
        suggestions.append(Suggestion(
            id="exp_marketplace",
            title="浏览技能市场发现新能力",
            description="探索可安装的外部技能扩展系统功能",
            icon="🛒",
            action_type="navigate_tab",
            action_payload={"target_tab": "技能市场"},
            confidence=0.68,
            category="exploration"
        ))

    if "shortcuts" in unused:
        suggestions.append(Suggestion(
            id="exp_shortcuts",
            title="学习快捷键提升效率",
            description="掌握键盘快捷键可以大幅提升操作效率",
            icon="⌨️",
            action_type="open_settings",
            action_payload={"section": "shortcuts"},
            confidence=0.65,
            category="exploration"
        ))

    return suggestions


def _generate_undo_suggestions(context: dict) -> List[Suggestion]:
    """Generate undo-related suggestions based on active undo records.

    If there are recent active undo records, suggest undoing the last operation.
    High confidence (0.85) as this is often what users want after a mistake.

    Args:
        context: Dict containing session and task information

    Returns:
        List of Suggestion objects for undo operations
    """
    suggestions = []

    try:
        from frontend.components.undo_panel import (
            check_has_active_undo_records,
            get_latest_undo_record_info,
            _get_current_session_id,
        )

        session_id = context.get("session_id", "") or _get_current_session_id()

        if check_has_active_undo_records(session_id):
            record_info = get_latest_undo_record_info(session_id)

            if record_info:
                op_type = record_info.get("operation_type", "unknown")
                op_label = record_info.get("label", "操作")
                op_icon = record_info.get("icon", "📝")
                remaining = record_info.get("remaining_seconds", 0)

                if remaining < 60:
                    time_urgency = f"（仅剩{remaining}秒）"
                elif remaining < 300:
                    time_urgency = f"（还剩{remaining // 60}分钟）"
                else:
                    time_urgency = ""

                suggestions.append(Suggestion(
                    id="undo_last_operation",
                    title=f"撤销上一步操作",
                    description=f"{op_icon} 撤销最近的「{op_label}」操作 {time_urgency}",
                    icon="↩️",
                    action_type="quick_task",
                    action_payload={
                        "prompt": "",
                        "undo_action": True,
                        "operation_id": record_info.get("operation_id", ""),
                    },
                    confidence=0.85,
                    category="follow_up"
                ))

    except ImportError:
        logger.debug("[smart_suggestions] Undo panel not available for suggestions")
    except Exception as e:
        logger.warning("[smart_suggestions] Undo suggestion generation error: %s", e)

    return suggestions


def generate_suggestions(context: dict) -> List[Suggestion]:
    """Main rule engine: generate and rank all suggestions

    Args:
        context: Dict containing:
            - last_task_type: str (e.g., "content_generation")
            - last_result: dict with execution_time_ms, sources_count
            - user_history: list of recent deliverable records
            - deliverables_count: int
            - feedback_history: list of feedback records
            - features_used: set of used feature names
            - session_id: str (optional, for undo suggestions)

    Returns:
        Sorted list of Suggestion by confidence descending
    """
    all_suggestions = []

    all_suggestions.extend(_generate_follow_up_suggestions(context))
    all_suggestions.extend(_generate_related_suggestions(context))
    all_suggestions.extend(_generate_improvement_suggestions(context))
    all_suggestions.extend(_generate_exploration_suggestions(context))
    all_suggestions.extend(_generate_undo_suggestions(context))

    seen_ids = set()
    unique_suggestions = []
    for s in all_suggestions:
        if s.id not in seen_ids:
            seen_ids.add(s.id)
            unique_suggestions.append(s)

    sorted_suggestions = sorted(unique_suggestions, key=lambda x: x.confidence, reverse=True)
    return sorted_suggestions[:10]


def _render_suggestion_card(suggestion: Suggestion) -> None:
    """Render a single suggestion card with icon, title, description, and action button"""
    confidence_pct = int(suggestion.confidence * 100)

    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
        transition: all 0.2s ease;
    ">
        <div style="display: flex; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 24px; margin-right: 10px;">{suggestion.icon}</span>
            <div>
                <div style="font-weight: 600; font-size: 15px; color: #1e293b;">{suggestion.title}</div>
                <div style="font-size: 12px; color: #64748b; margin-top: 2px;">{suggestion.description}</div>
            </div>
        </div>
        <div style="
            background: #e2e8f0;
            border-radius: 4px;
            height: 6px;
            width: 100%;
            margin: 10px 0;
        ">
            <div style="
                background: linear-gradient(90deg, #3b82f6, #8b5cf6);
                border-radius: 4px;
                height: 100%;
                width: {confidence_pct}%;
            "></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_btn, col_space = st.columns([1, 2])
    with col_btn:
        if st.button(
            f"一键执行",
            key=f"sug_exec_{suggestion.id}",
            type="primary",
            use_container_width=True,
            help=f"置信度: {confidence_pct}%"
        ):
            execute_suggestion(suggestion)


def render_suggestion_panel(suggestions: List[Suggestion], max_show: int = 3) -> None:
    """Render the main suggestion panel with collapsible UI

    Args:
        suggestions: List of Suggestion objects (should be pre-sorted by confidence)
        max_show: Maximum number of suggestions to show initially (default 3)
    """
    if not suggestions:
        return

    st.divider()

    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        border-left: 4px solid #f59e0b;
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 16px;
    ">
        <span style="font-size: 18px; margin-right: 8px;">💡</span>
        <strong style="color: #92400e;">接下来可以...</strong>
    </div>
    """, unsafe_allow_html=True)

    visible = suggestions[:max_show]
    hidden = suggestions[max_show:]

    for suggestion in visible:
        _render_suggestion_card(suggestion)

    if hidden:
        with st.expander(f"查看更多建议 ({len(hidden)}个) ▼"):
            for suggestion in hidden:
                _render_suggestion_card(suggestion)


def execute_suggestion(suggestion: Suggestion) -> None:
    """Execute a suggestion action based on its type

    Action types:
    - quick_task: Auto-fill prompt input and submit
    - navigate_tab: Switch to target tab via session state
    - open_settings: Navigate to settings page with specific section
    """
    try:
        if suggestion.action_type == "quick_task":
            prompt = suggestion.action_payload.get("prompt", "")
            if prompt:
                st.session_state.user_input = prompt
                st.session_state.auto_submit = True
                st.success(f"✅ 已准备执行: {suggestion.title}")
                st.balloons()
                st.rerun()
            else:
                st.info(f"💡 建议: {suggestion.description}")

        elif suggestion.action_type == "navigate_tab":
            target_tab = suggestion.action_payload.get("target_tab", "")
            if target_tab:
                st.session_state.current_page = target_tab
                st.success(f"📂 正在跳转到: {target_tab}")
                st.rerun()
            else:
                st.warning("⚠️ 未指定目标页面")

        elif suggestion.action_type == "open_settings":
            section = suggestion.action_payload.get("section", "")
            st.session_state.current_page = "设置"
            if section:
                st.session_state.settings_section = section
            st.success(f"⚙️ 打开设置: {section or '通用'}")
            st.rerun()

        else:
            st.warning(f"❓ 未知的操作类型: {suggestion.action_type}")

    except Exception as e:
        logger.error("[smart_suggestions] 执行建议失败: %s", e)
        st.error(f"❌ 执行失败: {str(e)}")


def build_context_from_session(last_task_type: str = "",
                                last_result: dict = None,
                                deliverables: list = None,
                                feedback_history: list = None) -> dict:
    """Build suggestion context from current Streamlit session state

    Convenience function to gather all needed context from session.
    Can be called from app.py after task completion.

    Args:
        last_task_type: Task type of just-completed task
        last_result: Result metadata (execution_time_ms, sources_count, etc.)
        deliverables: List of deliverable records from session
        feedback_history: List of user feedback records

    Returns:
        Context dict ready for generate_suggestions()
    """
    user_history = []
    if deliverables:
        user_history = [{
            "task_type": d.get("task_type", ""),
            "created_at": d.get("created_at", ""),
        } for d in deliverables[-5:]]

    features_used = set()
    if st.session_state.get("has_visited_dashboard"):
        features_used.add("dashboard")
    if st.session_state.get("has_visited_marketplace"):
        features_used.add("marketplace")
    if st.session_state.get("shortcuts_shown"):
        features_used.add("shortcuts")

    return {
        "last_task_type": last_task_type,
        "last_result": last_result or {},
        "user_history": user_history,
        "deliverables_count": len(deliverables) if deliverables else 0,
        "feedback_history": feedback_history or [],
        "features_used": features_used,
    }
