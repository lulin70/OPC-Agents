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
from dataclasses import dataclass
from typing import List
from collections import Counter

from opc_manager.i18n import t as _t

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
            title=_t("ss_export_pdf"),
            description=_t("ss_export_pdf_desc"),
            icon="",
            action_type="quick_task",
            action_payload={"prompt": _t("ss_export_pdf_prompt")},
            confidence=0.9,
            category="follow_up",
        ),
        Suggestion(
            id="gen_related_doc",
            title=_t("ss_gen_related_doc"),
            description=_t("ss_gen_related_doc_desc"),
            icon="",
            action_type="quick_task",
            action_payload={"prompt": _t("ss_gen_related_doc_prompt")},
            confidence=0.75,
            category="follow_up",
        ),
        Suggestion(
            id="share_content",
            title=_t("ss_share_content"),
            description=_t("ss_share_content_desc"),
            icon="",
            action_type="quick_task",
            action_payload={"prompt": _t("ss_share_content_prompt")},
            confidence=0.65,
            category="follow_up",
        ),
    ],
    "data_analysis": [
        Suggestion(
            id="deep_dive_metric",
            title=_t("ss_deep_dive_metric"),
            description=_t("ss_deep_dive_metric_desc"),
            icon="",
            action_type="quick_task",
            action_payload={"prompt": _t("ss_deep_dive_metric_prompt")},
            confidence=0.88,
            category="follow_up",
        ),
        Suggestion(
            id="compare_history",
            title=_t("ss_compare_history"),
            description=_t("ss_compare_history_desc"),
            icon="",
            action_type="quick_task",
            action_payload={"prompt": _t("ss_compare_history_prompt")},
            confidence=0.82,
            category="follow_up",
        ),
        Suggestion(
            id="generate_report",
            title=_t("ss_generate_report"),
            description=_t("ss_generate_report_desc"),
            icon="",
            action_type="quick_task",
            action_payload={"prompt": _t("ss_generate_report_prompt")},
            confidence=0.85,
            category="follow_up",
        ),
    ],
    "info_collection": [
        Suggestion(
            id="gen_plan_from_info",
            title=_t("ss_gen_plan_from_info"),
            description=_t("ss_gen_plan_from_info_desc"),
            icon="",
            action_type="quick_task",
            action_payload={"prompt": _t("ss_gen_plan_from_info_prompt")},
            confidence=0.87,
            category="follow_up",
        ),
        Suggestion(
            id="save_as_template",
            title=_t("ss_save_as_template"),
            description=_t("ss_save_as_template_desc"),
            icon="",
            action_type="quick_task",
            action_payload={"prompt": _t("ss_save_as_template_prompt")},
            confidence=0.7,
            category="follow_up",
        ),
        Suggestion(
            id="set_reminder",
            title=_t("ss_set_reminder"),
            description=_t("ss_set_reminder_desc"),
            icon="",
            action_type="quick_task",
            action_payload={"prompt": _t("ss_set_reminder_prompt")},
            confidence=0.72,
            category="follow_up",
        ),
    ],
    "business_operation": [
        Suggestion(
            id="view_monthly_report",
            title=_t("ss_view_monthly_report"),
            description=_t("ss_view_monthly_report_desc"),
            icon="",
            action_type="navigate_tab",
            action_payload={"target_tab": " Dashboard"},
            confidence=0.9,
            category="follow_up",
        ),
        Suggestion(
            id="record_expense",
            title=_t("ss_record_expense"),
            description=_t("ss_record_expense_desc"),
            icon="",
            action_type="quick_task",
            action_payload={"prompt": _t("ss_record_expense_prompt")},
            confidence=0.78,
            category="follow_up",
        ),
        Suggestion(
            id="client_followup",
            title=_t("ss_client_followup"),
            description=_t("ss_client_followup_desc"),
            icon="",
            action_type="quick_task",
            action_payload={"prompt": _t("ss_client_followup_prompt")},
            confidence=0.8,
            category="follow_up",
        ),
    ],
    "scenario_based": [
        Suggestion(
            id="review_steps",
            title=_t("ss_review_steps"),
            description=_t("ss_review_steps_desc"),
            icon="",
            action_type="quick_task",
            action_payload={"prompt": _t("ss_review_steps_prompt")},
            confidence=0.85,
            category="follow_up",
        ),
        Suggestion(
            id="adjust_rerun",
            title=_t("ss_adjust_rerun"),
            description=_t("ss_adjust_rerun_desc"),
            icon="",
            action_type="quick_task",
            action_payload={"prompt": _t("ss_adjust_rerun_prompt")},
            confidence=0.82,
            category="follow_up",
        ),
    ],
    "general_chat": [
        Suggestion(
            id="start_task",
            title=_t("ss_start_task"),
            description=_t("ss_start_task_desc"),
            icon="",
            action_type="quick_task",
            action_payload={"prompt": _t("ss_start_task_prompt")},
            confidence=0.75,
            category="follow_up",
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
    "content_generation": _t("ss_task_type_content_gen"),
    "data_analysis": _t("ss_task_type_data_analysis"),
    "info_collection": _t("ss_task_type_info_collection"),
    "business_operation": _t("ss_task_type_business_op"),
    "scenario_based": _t("ss_task_type_scenario"),
    "general_chat": _t("ss_task_type_general_chat"),
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

    recent_types = [
        h.get("task_type", "") for h in user_history[:5] if h.get("task_type")
    ]
    type_counter = Counter(recent_types)

    complementary = COMPLEMENTARY_TASKS.get(last_task_type, [])
    suggestions = []

    for comp_type in complementary:
        if comp_type in type_counter:
            count = type_counter[comp_type]
            confidence = min(0.6 + (count * 0.08), 0.9)

            if comp_type == "data_analysis":
                suggestions.append(
                    Suggestion(
                        id=f"rel_analysis_{comp_type}",
                        title=_t("ss_rel_financial_analysis"),
                        description=_t("ss_rel_financial_analysis_desc"),
                        icon="",
                        action_type="quick_task",
                        action_payload={
                            "prompt": _t("ss_rel_financial_analysis_prompt")
                        },
                        confidence=confidence,
                        category="related",
                    )
                )
            elif comp_type == "content_generation":
                suggestions.append(
                    Suggestion(
                        id=f"rel_content_{comp_type}",
                        title=_t("ss_rel_weekly_report"),
                        description=_t("ss_rel_weekly_report_desc"),
                        icon="",
                        action_type="quick_task",
                        action_payload={"prompt": _t("ss_rel_weekly_report_prompt")},
                        confidence=confidence,
                        category="related",
                    )
                )
            elif comp_type == "info_collection":
                suggestions.append(
                    Suggestion(
                        id=f"rel_info_{comp_type}",
                        title=_t("ss_rel_market_research"),
                        description=_t("ss_rel_market_research_desc"),
                        icon="",
                        action_type="quick_task",
                        action_payload={"prompt": _t("ss_rel_market_research_prompt")},
                        confidence=confidence,
                        category="related",
                    )
                )

    return suggestions


def _generate_improvement_suggestions(context: dict) -> List[Suggestion]:
    """Generate improvement suggestions based on result quality"""
    suggestions = []
    last_result = context.get("last_result", {})
    feedback_history = context.get("feedback_history", [])

    exec_time = last_result.get("execution_time_ms", 0)
    sources_count = last_result.get("sources_count", 0)

    if exec_time > 10000:
        suggestions.append(
            Suggestion(
                id="imp_speed",
                title=_t("ss_imp_simplify_request"),
                description=_t("ss_imp_simplify_request_desc"),
                icon="",
                action_type="quick_task",
                action_payload={"prompt": ""},
                confidence=0.75,
                category="improvement",
            )
        )

    if sources_count == 0:
        suggestions.append(
            Suggestion(
                id="imp_search",
                title=_t("ss_imp_optimize_search"),
                description=_t("ss_imp_optimize_search_desc"),
                icon="",
                action_type="quick_task",
                action_payload={"prompt": ""},
                confidence=0.7,
                category="improvement",
            )
        )

    negative_feedback = [f for f in feedback_history if f.get("feedback") == "bad"]
    if negative_feedback:
        suggestions.append(
            Suggestion(
                id="imp_feedback",
                title=_t("ss_imp_try_different"),
                description=_t("ss_imp_try_different_desc"),
                icon="",
                action_type="quick_task",
                action_payload={"prompt": ""},
                confidence=0.8,
                category="improvement",
            )
        )

    return suggestions


def _generate_exploration_suggestions(context: dict) -> List[Suggestion]:
    """Generate exploration suggestions for unused features"""
    suggestions = []
    user_features_used = context.get("features_used", set())

    all_features = {"dashboard", "marketplace", "shortcuts"}
    unused = all_features - user_features_used

    if "dashboard" in unused:
        suggestions.append(
            Suggestion(
                id="exp_dashboard",
                title=_t("ss_exp_dashboard"),
                description=_t("ss_exp_dashboard_desc"),
                icon="",
                action_type="navigate_tab",
                action_payload={"target_tab": " Dashboard"},
                confidence=0.72,
                category="exploration",
            )
        )

    if "marketplace" in unused:
        suggestions.append(
            Suggestion(
                id="exp_marketplace",
                title=_t("ss_exp_marketplace"),
                description=_t("ss_exp_marketplace_desc"),
                icon="",
                action_type="navigate_tab",
                action_payload={"target_tab": _t("ss_skill_market_tab")},
                confidence=0.68,
                category="exploration",
            )
        )

    if "shortcuts" in unused:
        suggestions.append(
            Suggestion(
                id="exp_shortcuts",
                title=_t("ss_exp_shortcuts"),
                description=_t("ss_exp_shortcuts_desc"),
                icon="",
                action_type="open_settings",
                action_payload={"section": "shortcuts"},
                confidence=0.65,
                category="exploration",
            )
        )

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
        )
        from frontend.components.session_utils import _get_current_session_id

        session_id = context.get("session_id", "") or _get_current_session_id()

        if check_has_active_undo_records(session_id):
            record_info = get_latest_undo_record_info(session_id)

            if record_info:
                record_info.get("operation_type", "unknown")
                op_label = record_info.get("label", _t("ss_undo_last_op"))
                op_icon = record_info.get("icon", "")
                remaining = record_info.get("remaining_seconds", 0)

                if remaining < 60:
                    time_urgency = _t("ss_only_seconds_left", seconds=remaining)
                elif remaining < 300:
                    time_urgency = _t("ss_minutes_left", minutes=remaining // 60)
                else:
                    time_urgency = ""

                suggestions.append(
                    Suggestion(
                        id="undo_last_operation",
                        title=_t("ss_undo_last_op"),
                        description=_t(
                            "ss_undo_last_op_desc",
                            icon=op_icon,
                            label=op_label,
                            urgency=time_urgency,
                        ),
                        icon="",
                        action_type="quick_task",
                        action_payload={
                            "prompt": "",
                            "undo_action": True,
                            "operation_id": record_info.get("operation_id", ""),
                        },
                        confidence=0.85,
                        category="follow_up",
                    )
                )

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

    sorted_suggestions = sorted(
        unique_suggestions, key=lambda x: x.confidence, reverse=True
    )
    return sorted_suggestions[:10]


def _render_suggestion_card(suggestion: Suggestion) -> None:
    """Render a single suggestion card with icon, title, description, and action button"""
    confidence_pct = int(suggestion.confidence * 100)

    st.markdown(
        f"""
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
    """,
        unsafe_allow_html=True,
    )

    col_btn, col_space = st.columns([1, 2])
    with col_btn:
        if st.button(
            _t("ss_one_click_exec"),
            key=f"sug_exec_{suggestion.id}",
            type="primary",
            use_container_width=True,
            help=_t("ss_confidence_label", pct=confidence_pct),
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

    st.markdown(
        """
    <div style="
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        border-left: 4px solid #f59e0b;
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 16px;
    ">
        <span style="font-size: 18px; margin-right: 8px;"></span>
        <strong style="color: #92400e;">{_t("ss_next_steps")}</strong>
    </div>
    """,
        unsafe_allow_html=True,
    )

    visible = suggestions[:max_show]
    hidden = suggestions[max_show:]

    for suggestion in visible:
        _render_suggestion_card(suggestion)

    if hidden:
        with st.expander(_t("ss_view_more_suggestions", count=len(hidden))):
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
                st.success(_t("ss_ready_to_exec", title=suggestion.title))
                st.toast("建议已执行", icon="")
                st.rerun()
            else:
                st.info(_t("ss_suggestion_tip", desc=suggestion.description))

        elif suggestion.action_type == "navigate_tab":
            target_tab = suggestion.action_payload.get("target_tab", "")
            tab_key_map = {
                " Dashboard": "dashboard",
                "Dashboard": "dashboard",
                " 仪表盘": "dashboard",
            }
            nav_key = tab_key_map.get(target_tab, target_tab)
            if nav_key:
                st.session_state.main_page_navigation = nav_key
                st.success(_t("ss_navigating_to", tab=target_tab))
                st.rerun()
            else:
                st.warning(_t("ss_no_target_page"))

        elif suggestion.action_type == "open_settings":
            section = suggestion.action_payload.get("section", "")
            st.session_state.main_page_navigation = "settings"
            if section:
                st.session_state.settings_section = section
            st.success(_t("ss_open_settings", section=section or _t("ss_general")))
            st.rerun()

        else:
            st.warning(_t("ss_unknown_action_type", type=suggestion.action_type))

    except Exception as e:
        logger.error("[smart_suggestions] 执行建议失败: %s", e)
        st.error(_t("ss_exec_failed", error=str(e)))


def build_context_from_session(
    last_task_type: str = "",
    last_result: dict = None,
    deliverables: list = None,
    feedback_history: list = None,
) -> dict:
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
        user_history = [
            {
                "task_type": d.get("task_type", ""),
                "created_at": d.get("created_at", ""),
            }
            for d in deliverables[-5:]
        ]

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
