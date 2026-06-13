"""Intelligent Autocomplete Input Component for OPC-Agents

Provides smart completion suggestions for user input including:
- History-based completions (recent prompts)
- Skill name completions (21 built-in skills)
- Template completions (predefined high-frequency templates)
- Contact completions (from CRM module)

Design:
- Pure Streamlit implementation (no external JS)
- <100ms response time (local filtering)
- Cross-session frequency caching
- Chinese input support with pinyin matching (optional)

UI Layout:
┌─────────────────────────────────────────────┐
│ 🎯 输入你的需求...                    [发送] │
├─────────────────────────────────────────────┤
│ 💡 最近使用:                                │
│ [写一份Q2营销方案] [分析竞品数据] [记录收入] │
│                                              │
│ 🛠️ 技能快捷入口:                            │
│ [CRM客户管理] [财务记录] [报告生成] [...]     │
│                                              │
│ 📋 常用模板:                                │
│ [写报告...] [发邮件...] [新建任务...]        │
└─────────────────────────────────────────────┘
"""

import streamlit as st
import json
import time
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from pathlib import Path

from opc_manager.i18n import t as _t

logger = logging.getLogger(__name__)

CACHE_DIR = Path("data")
CACHE_FILE = CACHE_DIR / "completions_cache.json"
MAX_CACHE_SIZE_KB = 50


@dataclass
class CompletionItem:
    """Single completion suggestion item"""

    text: str
    display_text: str
    source: str  # "history" | "skill" | "template" | "contact"
    frequency: int = 0
    last_used: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CompletionItem":
        return cls(**data)


COMPLETION_TEMPLATES = [
    {
        "text": _t("ac_tmpl_write_report", topic="{topic}"),
        "display": _t("ac_tmpl_write_report_display"),
        "desc": _t("ac_tmpl_write_report_desc"),
    },
    {
        "text": _t("ac_tmpl_data_analysis", metric="{metric}"),
        "display": _t("ac_tmpl_data_analysis_display"),
        "desc": _t("ac_tmpl_data_analysis_desc"),
    },
    {
        "text": _t("ac_tmpl_record_income", amount="{amount}", project="{project}"),
        "display": _t("ac_tmpl_record_income_display"),
        "desc": _t("ac_tmpl_record_income_desc"),
    },
    {
        "text": _t("ac_tmpl_send_email", client="{client}", subject="{subject}"),
        "display": _t("ac_tmpl_send_email_display"),
        "desc": _t("ac_tmpl_send_email_desc"),
    },
    {
        "text": _t("ac_tmpl_create_task", task_title="{task_title}"),
        "display": _t("ac_tmpl_create_task_display"),
        "desc": _t("ac_tmpl_create_task_desc"),
    },
    {
        "text": _t("ac_tmpl_monthly_report"),
        "display": _t("ac_tmpl_monthly_report_display"),
        "desc": _t("ac_tmpl_monthly_report_desc"),
    },
    {
        "text": _t("ac_tmpl_search_info", keyword="{keyword}"),
        "display": _t("ac_tmpl_search_info_display"),
        "desc": _t("ac_tmpl_search_info_desc"),
    },
    {
        "text": _t("ac_tmpl_gen_plan", type="{type}"),
        "display": _t("ac_tmpl_gen_plan_display"),
        "desc": _t("ac_tmpl_gen_plan_desc"),
    },
]

SKILL_CATEGORY_ICONS = {
    "utility": "🔧",
    "search": "🔍",
    "analysis": "📊",
    "creation": "✍️",
    "operation": "⚙️",
    "notification": "🔔",
}

SMART_HINTS = [
    _t("ac_hint_1"),
    _t("ac_hint_2"),
    _t("ac_hint_3"),
    _t("ac_hint_4"),
]


def load_completion_cache() -> Dict[str, Dict]:
    """Load completion frequency cache from disk.

    Returns:
        Dictionary mapping item text to cache data (frequency, last_used)
    """
    try:
        if CACHE_FILE.exists():
            file_size_kb = CACHE_FILE.stat().st_size / 1024
            if file_size_kb > MAX_CACHE_SIZE_KB:
                logger.warning(
                    f"[autocomplete] Cache file too large ({file_size_kb:.1f}KB), resetting"
                )
                return {}

            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict):
                return data
    except Exception as e:
        logger.warning(f"[autocomplete] Failed to load cache: {e}")

    return {}


def save_completion_cache(cache: Dict[str, Dict]) -> None:
    """Save completion frequency cache to disk.

    Args:
        cache: Dictionary mapping item text to cache data
    """
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        cache_str = json.dumps(cache, ensure_ascii=False, indent=2)
        cache_size_kb = len(cache_str.encode("utf-8")) / 1024

        if cache_size_kb > MAX_CACHE_SIZE_KB:
            sorted_items = sorted(
                cache.items(),
                key=lambda x: (x[1].get("frequency", 0), x[1].get("last_used", 0)),
                reverse=True,
            )
            cache = dict(sorted_items[:100])
            logger.info("[autocomplete] Cache trimmed to top 100 items")

        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"[autocomplete] Failed to save cache: {e}")


def update_completion_frequency(item_text: str) -> None:
    """Update usage frequency for a completion item.

    Args:
        item_text: The text of the selected completion item
    """
    try:
        cache = load_completion_cache()

        if item_text in cache:
            cache[item_text]["frequency"] = cache[item_text].get("frequency", 0) + 1
        else:
            cache[item_text] = {"frequency": 1, "last_used": 0.0}

        cache[item_text]["last_used"] = time.time()

        save_completion_cache(cache)

    except Exception as e:
        logger.warning(f"[autocomplete] Failed to update frequency: {e}")


def _get_pinyin_initials(text: str) -> str:
    """Get pinyin initials for Chinese text (optional enhancement).

    Args:
        text: Input text (may contain Chinese characters)

    Returns:
        Pinyin initials string (e.g., "wbg" for "写报告")
    """
    try:
        from pypinyin import lazy_pinyin

        return "".join([word[0].upper() for word in lazy_pinyin(text) if word])
    except ImportError:
        return ""


def filter_completions(
    query: str, all_items: List[CompletionItem], max_results: int = 8
) -> List[CompletionItem]:
    """Filter and rank completion items based on user query.

    Matching algorithm:
    - Prefix match (weight 1.0)
    - Contains match (weight 0.8)
    - Pinyin initials match (weight 0.6, optional)

    Ranking formula: match_score × frequency_factor × time_decay_factor

    Args:
        query: User's current input
        all_items: All available completion items
        max_results: Maximum number of results to return

    Returns:
        Filtered and ranked list of CompletionItems
    """
    if not query or not query.strip():
        return []

    query_lower = query.lower().strip()
    query_pinyin = _get_pinyin_initials(query).lower()

    cache = load_completion_cache()
    current_time = time.time()

    scored_items = []

    for item in all_items:
        text_lower = item.text.lower()
        display_lower = item.display_text.lower()
        text_pinyin = _get_pinyin_initials(item.text).lower()

        match_score = 0.0

        if text_lower.startswith(query_lower):
            match_score = 1.0
        elif display_lower.startswith(query_lower):
            match_score = 0.95
        elif query_lower in text_lower:
            match_score = 0.8
        elif query_lower in display_lower:
            match_score = 0.75
        elif query_pinyin and text_pinyin.startswith(query_pinyin):
            match_score = 0.6
        elif query_pinyin and query_pinyin in text_pinyin:
            match_score = 0.55

        if match_score > 0:
            cache_data = cache.get(item.text, {})
            frequency = cache_data.get("frequency", item.frequency)
            last_used = cache_data.get("last_used", item.last_used)

            frequency_factor = 1.0 + min(frequency * 0.1, 2.0)

            days_since_last_used = (
                (current_time - last_used) / 86400 if last_used > 0 else 30
            )
            time_decay = max(0.3, 1.0 / (1.0 + days_since_last_used * 0.05))

            final_score = match_score * frequency_factor * time_decay

            scored_items.append((final_score, item))

    scored_items.sort(key=lambda x: x[0], reverse=True)

    return [item for _, item in scored_items[:max_results]]


def _render_history_suggestions(
    history: List[Dict], max_show: int = 5
) -> List[CompletionItem]:
    """Render history-based suggestions from chat history.

    Args:
        history: List of message dicts from chat history
        max_show: Maximum number of suggestions to show

    Returns:
        List of CompletionItems from history
    """
    items = []
    seen_texts = set()

    user_messages = [
        msg
        for msg in history
        if msg.get("role") == "user" and msg.get("content", "").strip()
    ]

    for msg in reversed(user_messages[-20:]):
        content = msg["content"].strip()
        if content not in seen_texts and len(content) <= 200:
            seen_texts.add(content)
            items.append(
                CompletionItem(
                    text=content,
                    display_text=content[:50] + ("..." if len(content) > 50 else ""),
                    source="history",
                )
            )
            if len(items) >= max_show:
                break

    return items


def _render_skill_shortcuts() -> List[CompletionItem]:
    """Render skill name shortcuts from skill registry.

    Returns:
        List of CompletionItems for all built-in skills
    """
    items = []

    try:
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry()
        skills = registry.list_all_skills()

        category_groups = {}
        for skill in skills:
            cat_name = (
                skill.category.value
                if hasattr(skill.category, "value")
                else str(skill.category)
            )
            icon = SKILL_CATEGORY_ICONS.get(cat_name, "📌")
            display_text = f"{icon} {skill.name}"

            items.append(
                CompletionItem(
                    text=_t("ac_use_skill", name=skill.name),
                    display_text=display_text,
                    source="skill",
                )
            )

            if cat_name not in category_groups:
                category_groups[cat_name] = []
            category_groups[cat_name].append(skill.name)

        logger.debug(f"[autocomplete] Loaded {len(items)} skill shortcuts")

    except Exception as e:
        logger.warning(f"[autocomplete] Failed to load skills: {e}")
        default_skills = [
            (_t("ac_default_skill_search"), "🔍"),
            (_t("ac_default_skill_analysis"), "📊"),
            (_t("ac_default_skill_content"), "✍️"),
            (_t("ac_default_skill_email"), "📧"),
            (_t("ac_default_skill_finance"), "💰"),
            (_t("ac_default_skill_crm"), "👥"),
            (_t("ac_default_skill_report"), "📝"),
            (_t("ac_default_skill_schedule"), "📅"),
            (_t("ac_default_skill_todo"), "✅"),
        ]
        for name, icon in default_skills:
            items.append(
                CompletionItem(
                    text=_t("ac_use_skill", name=name),
                    display_text=f"{icon} {name}",
                    source="skill",
                )
            )

    return items


def _render_template_suggestions() -> List[CompletionItem]:
    """Render template-based suggestions.

    Returns:
        List of CompletionItems from predefined templates
    """
    items = []

    for template in COMPLETION_TEMPLATES:
        items.append(
            CompletionItem(
                text=template["text"],
                display_text=template["display"],
                source="template",
            )
        )

    return items


def _render_contact_suggestions(query: str = "") -> List[CompletionItem]:
    """Render contact suggestions from CRM module.

    Args:
        query: Current user input (to detect contact triggers like "@" or "给 ")

    Returns:
        List of CompletionItems for contacts
    """
    items = []

    if not query or not ("@" in query or "给 " in query):
        return items

    try:
        from opc_manager.crm_skill import search_customers

        result = search_customers(limit=10)
        customers = result.get("customers", [])

        for customer in customers[:10]:
            name = customer.get("name", "")
            if name:
                items.append(
                    CompletionItem(
                        text=f"@{name}", display_text=f"👤 {name}", source="contact"
                    )
                )

    except Exception as e:
        logger.debug(f"[autocomplete] Contacts not available: {e}")

    return items


def _get_all_completion_items(
    session_history: List[Dict] = None,
) -> List[CompletionItem]:
    """Gather all available completion items from all sources.

    Args:
        session_history: Current session's chat history

    Returns:
        Combined list of all CompletionItems
    """
    all_items = []

    if session_history:
        all_items.extend(_render_history_suggestions(session_history))

    all_items.extend(_render_skill_shortcuts())
    all_items.extend(_render_template_suggestions())

    return all_items


def render_autocomplete_input(
    label: str, key: str, session_history: List[Dict] = None, **kwargs
) -> str:
    """Render an enhanced autocomplete input component.

    This is a drop-in replacement for st.chat_input() that provides:
    - Real-time filtering suggestions
    - History-based completions
    - Skill shortcuts
    - Template suggestions
    - Smart hints when input is empty
    - Mobile responsive: compact suggestions and touch-friendly areas

    UI Layout:
    ┌─────────────────────────────────────────────┐
    │ 🎯 输入你的需求...                    [发送] │
    ├─────────────────────────────────────────────┤
    │ 💡 最近使用: (if available)                 │
    │ [suggestion buttons]                        │
    │                                              │
    │ 🛠️ 技能快捷入口:                            │
    │ [skill buttons]                              │
    │                                              │
    │ 📋 常用模板:                                │
    │ [template buttons]                           │
    └─────────────────────────────────────────────┘

    Args:
        label: Input label text
        key: Unique key for this input component
        session_history: Optional list of chat messages for history suggestions
        **kwargs: Additional arguments passed to st.chat_input

    Returns:
        User input string (empty string if no input)
    """
    # 移动端响应式 CSS：紧凑建议列表和触摸友好区域
    st.markdown(
        """
    <style>
    @media (max-width: 768px) {
        /* 建议列表在小屏幕更紧凑 */
        [data-testid="stHorizontalBlock"] > div {
            flex-direction: column !important;
            width: 100% !important;
        }
        /* 按钮触摸区域增大 */
        .stButton > button {
            min-height: 44px !important;
            font-size: 14px !important;
            padding: 8px 12px !important;
        }
        /* 输入框触摸友好 */
        [data-testid="stChatInput"] textarea {
            min-height: 48px !important;
            font-size: 16px !important;
        }
        /* 建议区域间距紧凑 */
        .stMarkdown p {
            margin-bottom: 4px !important;
        }
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    state_key = f"{key}_autocomplete"

    if state_key not in st.session_state:
        st.session_state[state_key] = {
            "show_suggestions": True,
            "selected_value": None,
            "hint_index": 0,
        }

    user_input = st.chat_input(label, **kwargs)

    if user_input and user_input.strip():
        update_completion_frequency(user_input.strip())

    auto_state = st.session_state[state_key]

    if auto_state.get("selected_value"):
        result = auto_state.pop("selected_value")
        auto_state["show_suggestions"] = False
        return result

    if not user_input:
        _render_empty_state_hints(auto_state)
        _render_default_suggestions(session_history)
        return ""

    if auto_state.get("show_suggestions", True) and len(user_input.strip()) >= 1:
        _render_filtered_suggestions(user_input, session_history, key)

    return user_input or ""


def _render_empty_state_hints(auto_state: Dict) -> None:
    """Render smart hints when input is empty.

    Shows rotating helpful hints to guide users.

    Args:
        auto_state: Autocomplete state dictionary
    """
    hint_index = auto_state.get("hint_index", 0)
    hint = SMART_HINTS[hint_index % len(SMART_HINTS)]

    st.caption(f"💡 {hint}")

    auto_state["hint_index"] = hint_index + 1


def _render_default_suggestions(session_history: List[Dict] = None) -> None:
    """Render default suggestions when input is empty.

    Shows recent history, skill shortcuts, and popular templates.

    Args:
        session_history: Optional chat history for history suggestions
    """
    history_items = []
    if session_history:
        history_items = _render_history_suggestions(session_history, max_show=3)

    if history_items:
        st.markdown(_t("ac_recent_used"))
        hist_cols = st.columns(min(len(history_items), 3))
        for i, item in enumerate(history_items):
            with hist_cols[i % len(history_items)]:
                if st.button(
                    item.display_text,
                    key=f"hist_def_{item.text[:20]}_{i}",
                    use_container_width=True,
                    help=_t("ac_click_to_fill"),
                ):
                    _apply_selection(item.text)

    skill_items = _render_skill_shortcuts()
    if skill_items:
        st.markdown(_t("ac_skill_shortcuts"))
        skill_cols = st.columns(min(len(skill_items), 3))
        for i, item in enumerate(skill_items[:12]):
            with skill_cols[i % min(len(skill_items), 3)]:
                if st.button(
                    item.display_text,
                    key=f"skill_def_{item.text[:15]}_{i}",
                    use_container_width=True,
                    help=item.text,
                ):
                    _apply_selection(item.text)

    template_items = _render_template_suggestions()
    if template_items:
        with st.expander(_t("ac_common_templates"), expanded=False):
            tmpl_cols = st.columns(min(len(template_items), 2))
            for i, item in enumerate(template_items):
                with tmpl_cols[i % len(tmpl_cols)]:
                    if st.button(
                        item.display_text,
                        key=f"tmpl_def_{item.text[:15]}_{i}",
                        use_container_width=True,
                        help=item.text,
                    ):
                        _apply_selection(item.text)


def _render_filtered_suggestions(
    query: str, session_history: List[Dict], base_key: str
) -> None:
    """Render filtered suggestions based on current input.

    Shows real-time filtered results as user types.

    Args:
        query: Current user input
        session_history: Chat history for context
        base_key: Base key for generating unique button keys
    """
    all_items = _get_all_completion_items(session_history)
    all_items.extend(_render_contact_suggestions(query))

    filtered = filter_completions(query, all_items, max_results=8)

    if not filtered:
        return

    st.markdown(_t("ac_matched_suggestions"))

    sug_cols = st.columns(min(len(filtered), 2))
    for i, item in enumerate(filtered):
        with sug_cols[i % len(sug_cols)]:
            button_label = item.display_text
            if len(button_label) > 25:
                button_label = button_label[:22] + "..."

            if st.button(
                button_label,
                key=f"sug_{base_key}_{item.source}_{item.text[:15]}_{i}",
                use_container_width=True,
                help=_t("ac_source_click_fill", source=item.source),
            ):
                _apply_selection(item.text)
                update_completion_frequency(item.text)


def _apply_selection(selected_text: str) -> None:
    """Apply a selected completion item to the input.

    Sets the selected value in session state to be returned on next rerun.

    Args:
        selected_text: Text of the selected completion item
    """
    for state_key in st.session_state:
        if state_key.endswith("_autocomplete"):
            st.session_state[state_key]["selected_value"] = selected_text
            break

    st.rerun()


def get_autocomplete_stats() -> Dict[str, Any]:
    """Get statistics about the autocomplete system.

    Returns:
        Dictionary containing cache statistics
    """
    cache = load_completion_cache()

    total_items = len(cache)
    total_usage = sum(item.get("frequency", 0) for item in cache.values())

    most_used = sorted(
        cache.items(), key=lambda x: x[1].get("frequency", 0), reverse=True
    )[:5]

    return {
        "total_cached_items": total_items,
        "total_usage_count": total_usage,
        "top_completions": most_used,
        "cache_file_exists": CACHE_FILE.exists(),
        "cache_size_kb": (
            round(CACHE_FILE.stat().st_size / 1024, 1) if CACHE_FILE.exists() else 0
        ),
    }


def clear_completion_cache() -> bool:
    """Clear the completion frequency cache.

    Returns:
        True if cache was successfully cleared
    """
    try:
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
            logger.info("[autocomplete] Cache cleared successfully")
            return True
        return False
    except Exception as e:
        logger.error(f"[autocomplete] Failed to clear cache: {e}")
        return False
