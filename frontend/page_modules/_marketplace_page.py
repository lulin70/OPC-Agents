"""Marketplace page module for OPC-Agents frontend.

Contains all skill marketplace-related UI rendering functions:
- Main marketplace page with browse/my skills tabs (MVP)
- Skill card rendering with version pinning (V2)
- Category filter + search enhancement (V2)
- Detail view panel (V2)
- Global search functionality
"""

import streamlit as st
import logging
import hashlib
from opc_manager.i18n import t as _t

logger = logging.getLogger(__name__)

ALL_CATEGORIES = [
    "CRM",
    "Finance",
    "Email",
    "Calendar",
    "Social",
    "Knowledge",
    "Report",
    "Task",
    "Proposal",
    "Tax",
    "Dashboard",
    "Competitor",
    "Pricing",
    "Invoice",
    "Security",
    "Monitoring",
]

SORT_OPTIONS = {
    "name_asc": "mp_sort_name_asc",
    "name_desc": "mp_sort_name_desc",
    "popular": "mp_sort_popular",
    "rating_desc": "mp_sort_highest_rated",
}


def _render_skill_marketplace_page():
    """Render the Skill Marketplace V2 page.

    Features:
    1. Browse tab: Search + category filter + sort + skill cards grid
    2. My Skills tab: Installed skills list with version pinning
    3. Detail view: Click card to see full info + install/uninstall button
    """
    try:
        from opc_manager.skill_marketplace import (
            SkillMarketplace,
            ExternalSkillMarketplace,
        )
    except ImportError:
        st.warning(_t("mp_not_loaded"))
        return

    st.markdown(_t("mp_title"))

    marketplace = SkillMarketplace()
    external_mp = ExternalSkillMarketplace()

    sub_tab = st.tabs([_t("mp_tab_browse"), _t("mp_tab_my_skills")])

    with sub_tab[0]:
        _render_marketplace_browse_v2(marketplace, external_mp)

    with sub_tab[1]:
        _render_my_skills_v2(marketplace, external_mp)


def _render_marketplace_browse_v2(marketplace, external_mp):
    """Browse and discover skills with V2 enhanced filters."""
    selected_skill = st.session_state.get("selected_skill")

    if selected_skill:
        _render_skill_detail(selected_skill, marketplace, external_mp)
        return

    search_query, selected_cats, sort_by = _render_marketplace_filters_v2()

    try:
        stats = marketplace.get_stats()
        total_skills = stats.get("total_skills", 0)
        approved = stats.get("approved_skills", 0)

        all_skills = marketplace.discover_skills(
            keyword=search_query if search_query else None,
            category=None,
        )

        filtered_skills = _filter_and_sort_skills(
            all_skills, search_query, selected_cats, sort_by
        )

        st.caption(
            _t(
                "mp_stats",
                total=total_skills,
                approved=approved,
                show=len(filtered_skills),
            )
        )

        if not filtered_skills:
            st.info(_t("mp_no_results"))
            return

        installed_versions = _load_installed_versions(external_mp)

        from opc_manager.skill_reviews import get_review_manager

        review_mgr = get_review_manager()
        batch_ratings = {}
        if review_mgr:
            skill_ids = [
                s.get("skill_id", "") for s in filtered_skills[:12] if s.get("skill_id")
            ]
            batch_ratings = review_mgr.get_average_ratings(skill_ids)

        cols = st.columns(3)
        for i, skill in enumerate(filtered_skills[:12]):
            with cols[i % 3]:
                _render_skill_card_v2(
                    skill, marketplace, external_mp, installed_versions, batch_ratings
                )

    except Exception as e:
        st.error(_t("mp_load_error", error=e))


def _render_marketplace_filters_v2():
    """Render search + category filter + sort controls (V2)."""
    search = st.text_input(
        _t("mp_search"),
        placeholder=_t("mp_search_placeholder"),
        key="mp_search_v2",
    )

    col_cat, col_sort = st.columns([3, 1])
    with col_cat:
        selected_cats = st.multiselect(
            _t("mp_category_filter"),
            options=ALL_CATEGORIES,
            default=[],
            key="mp_category_filter_v2",
        )
    with col_sort:
        sort_by = st.selectbox(
            _t("mp_sort"),
            options=list(SORT_OPTIONS.keys()),
            format_func=lambda x: _t(SORT_OPTIONS.get(x, x)),
            key="mp_sort_v2",
        )

    return search, selected_cats, sort_by


def _filter_and_sort_skills(skills, search_text, categories, sort_by):
    """Apply search + category + sort to skill list.

    Args:
        skills: List of skill dicts from marketplace.discover_skills()
        search_text: Search query string
        categories: List of category strings to filter by (AND logic)
        sort_by: One of 'name_asc', 'name_desc', 'popular'

    Returns:
        Filtered and sorted list of skill dicts.
    """
    filtered = list(skills)

    if search_text:
        q = search_text.lower()
        filtered = [
            s
            for s in filtered
            if q in s.get("name", "").lower() or q in s.get("description", "").lower()
        ]

    if categories:
        filtered = [s for s in filtered if s.get("category", "") in categories]

    if sort_by == "name_asc":
        filtered = sorted(filtered, key=lambda s: s.get("name", ""))
    elif sort_by == "name_desc":
        filtered = sorted(filtered, key=lambda s: s.get("name", ""), reverse=True)
    elif sort_by == "popular":
        filtered.sort(
            key=lambda s: _simulate_install_count(s.get("skill_id", "")), reverse=True
        )
    elif sort_by == "rating_desc":
        from opc_manager.skill_reviews import get_review_manager

        _rm = get_review_manager()
        if _rm:
            skill_ids = [s.get("skill_id", "") for s in filtered if s.get("skill_id")]
            batch_ratings = _rm.get_average_ratings(skill_ids)
            filtered.sort(
                key=lambda s: batch_ratings.get(s.get("skill_id", ""), 0.0),
                reverse=True,
            )

    return filtered


def _simulate_install_count(skill_id: str) -> int:
    """Generate deterministic simulated install count for demo purposes.

    # TODO(v0.3.0): Replace with real install count from database when analytics are implemented.
    """
    import hashlib

    hash_val = int(hashlib.sha256(skill_id.encode()).hexdigest()[:8], 16)
    return (hash_val % 900) + 100  # 100-999 range


def _render_skill_card_v2(
    skill, marketplace, external_mp, installed_versions=None, batch_ratings=None
):
    """Render a single skill card with version pinning (V2)."""
    if installed_versions is None:
        installed_versions = {}
    if batch_ratings is None:
        batch_ratings = {}

    name = skill.get("name", _t("mp_unknown_skill"))
    version = skill.get("version", "1.0.0")
    desc = skill.get("description", "")
    author = skill.get("author", "unknown")
    category = skill.get("category", "general")
    skill_id = skill.get("skill_id", "")

    trust_colors = {
        "official": "blue",
        "verified": "green",
        "community": "orange",
        "unverified": "gray",
    }
    trust_labels = {
        "official": _t("mp_trust_official"),
        "verified": _t("mp_trust_verified"),
        "community": _t("mp_trust_community"),
        "unverified": _t("mp_trust_unverified"),
    }

    is_installed = skill_id in installed_versions
    installed_ver = installed_versions.get(skill_id, "")
    update_available = is_installed and installed_ver and installed_ver != version

    status_text = ""
    if is_installed:
        if update_available:
            status_text = _t("mp_status_update_avail", ver=installed_ver)
        else:
            status_text = _t("mp_status_installed", ver=installed_ver)
    else:
        status_text = _t("mp_status_available", ver=version)

    with st.container(border=True):
        st.markdown(f"**{name}**{status_text}")
        st.caption(desc[:80] + "..." if len(desc) > 80 else desc)
        st.markdown(f"*{category}* · {author}")

        avg_rating = batch_ratings.get(skill_id, 0.0)
        if avg_rating > 0:
            stars = "★" * int(avg_rating) + "☆" * (5 - int(avg_rating))
            st.markdown(
                f'<span style="font-size:0.85em">{stars} {avg_rating}</span>',
                unsafe_allow_html=True,
            )

        if update_available:
            st.markdown(_t("mp_update_available_notice"), unsafe_allow_html=True)

        if st.button(
            _t("mp_btn_view_detail"),
            key=f"skill_detail_{skill_id}_{hash(skill.get('name', ''))}",
            use_container_width=True,
        ):
            st.session_state["selected_skill"] = skill


def _render_skill_detail(skill, marketplace, external_mp):
    """Render detailed skill information panel (V2)."""
    name = skill.get("name", _t("mp_unknown_skill"))
    version = skill.get("version", "1.0.0")
    desc = skill.get("description", "")
    author = skill.get("author", "OPC-Agents Team")
    category = skill.get("category", "general")
    skill_id = skill.get("skill_id", "")
    tags = skill.get("tags", [])

    installed_versions = _load_installed_versions(external_mp)
    is_installed = skill_id in installed_versions
    installed_ver = installed_versions.get(skill_id, "")
    update_available = is_installed and installed_ver and installed_ver != version

    st.markdown(f"### {name}")
    if update_available:
        st.markdown(_t("mp_update_avail_detail", old=installed_ver, new=version))

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"{_t('mp_detail_desc')}: {desc}")
        st.markdown(f"{_t('mp_detail_category')}: {category}")
        st.markdown(f"{_t('mp_detail_version')}: {version}")
        st.markdown(f"{_t('mp_detail_author')}: {author}")
        st.markdown(
            f"{_t('mp_detail_installs')}: {_t('mp_install_count_fmt', count=_simulate_install_count(skill_id))}"
        )
        st.markdown(f"{_t('mp_detail_compat')}: {_t('mp_compat_version')}")

        if tags:
            tag_str = " ".join(f"`{t}`" for t in tags)
            st.markdown(f"{_t('mp_detail_tags')}: {tag_str}")

    with col2:
        if is_installed:
            if st.button(
                _t("mp_btn_uninstall"),
                key=f"uninstall_detail_{skill_id}",
                type="secondary",
            ):
                try:
                    result = external_mp.uninstall_skill(skill_id)
                    if result.get("success"):
                        st.success(_t("mp_uninstall_success"))
                        _remove_installed_version(skill_id)
                        st.session_state.pop("selected_skill", None)
                        st.rerun()
                    else:
                        st.error(result.get("error", _t("mp_uninstall_failed")))
                except Exception as e:
                    st.error(_t("mp_uninstall_failed") + f": {e}")
            if update_available:
                if st.button(
                    _t("mp_btn_update"), key=f"update_detail_{skill_id}", type="primary"
                ):
                    try:
                        result = external_mp.install_skill(skill_id, confirmed=True)
                        if result.get("success"):
                            _save_installed_version(skill_id, version)
                            st.success(
                                _t("mp_update_success", old=installed_ver, new=version)
                            )
                            st.rerun()
                        else:
                            st.error(result.get("error", _t("mp_update_failed")))
                    except Exception as e:
                        st.error(_t("mp_update_failed") + f": {e}")
        else:
            if st.button(
                _t("mp_btn_install"), key=f"install_detail_{skill_id}", type="primary"
            ):
                try:
                    result = external_mp.install_skill(skill_id, confirmed=True)
                    if result.get("success"):
                        _save_installed_version(skill_id, version)
                        st.success(_t("mp_install_success"))
                        st.rerun()
                    elif result.get("requires_confirmation"):
                        st.warning(_t("mp_install_needs_confirm"))
                    else:
                        st.error(result.get("error", _t("mp_install_failed")))
                except Exception as e:
                    st.error(_t("mp_install_failed") + f": {e}")

    st.divider()

    if st.button(_t("mp_btn_back_grid"), key="back_to_grid"):
        st.session_state.pop("selected_skill", None)
        st.rerun()


def _render_my_skills_v2(marketplace, external_mp):
    """Render installed/manageable skills list with version pinning (V2)."""
    try:
        installed_result = external_mp.list_installed()
        installed = (
            installed_result.get("skills", [])
            if isinstance(installed_result, dict)
            else []
        )
    except Exception as e:
        logger.warning("[marketplace] list_installed failed: %s", e)
        installed = []

    if not installed:
        st.info(_t("mp_no_installed"))
        st.markdown(_t("mp_no_installed_hint") + "\n\n" + _t("mp_no_installed_tip"))
        return

    installed_versions = _load_installed_versions(external_mp)
    st.caption(_t("mp_installed_count", count=len(installed)))

    for skill in installed:
        skill_id = skill.get("skill_id", "")
        skill_name = skill.get("name", _t("mp_unknown_skill"))
        skill_version = skill.get("version", "?")
        pinned_version = installed_versions.get(skill_id, skill_version)

        with st.expander(f"📦 {skill_name} v{pinned_version or skill_version}"):
            col_info, col_action = st.columns([3, 1])
            with col_info:
                st.json(
                    {
                        _t("mp_json_name"): skill.get("name"),
                        _t("mp_json_version"): pinned_version or skill.get("version"),
                        _t("mp_json_source"): skill.get("source", "-"),
                        _t("mp_json_status"): skill.get("status"),
                        _t("mp_json_trust"): skill.get("trust_level", "-"),
                        _t("mp_json_installed_at"): skill.get("installed_at", "-"),
                    }
                )
            with col_action:
                if st.button(
                    _t("mp_btn_uninstall"), key=f"uninstall_{skill_id or id(skill)}"
                ):
                    try:
                        result = external_mp.uninstall_skill(skill_id)
                        if result.get("success"):
                            _remove_installed_version(skill_id)
                            st.success(_t("mp_uninstall_success"))
                            st.rerun()
                        else:
                            st.error(result.get("error", _t("mp_uninstall_failed")))
                    except Exception as e:
                        st.error(_t("mp_uninstall_failed") + f": {e}")


def _get_installed_versions_file():
    """Get path to installed versions tracking file."""
    import os

    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "installed_skills.json")


def _load_installed_versions(external_mp):
    """Load installed skill versions from tracking file."""
    import json
    import os

    filepath = _get_installed_versions_file()
    versions = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                versions = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    try:
        installed_result = external_mp.list_installed()
        installed_list = (
            installed_result.get("skills", [])
            if isinstance(installed_result, dict)
            else []
        )
        for s in installed_list:
            sid = s.get("skill_id", "")
            if sid and sid not in versions:
                versions[sid] = s.get("version", "1.0.0")
    except Exception as e:
        logger.warning("[marketplace] load_installed_versions merge failed: %s", e)
    return versions


def _save_installed_version(skill_id, version):
    """Save an installed skill's version pin."""
    import json

    versions = _load_installed_versions_for_write()
    versions[skill_id] = version
    filepath = _get_installed_versions_file()
    try:
        with open(filepath, "w") as f:
            json.dump(versions, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.warning("保存版本信息失败: %s", e)


def _remove_installed_version(skill_id):
    """Remove a skill's version pin record."""
    import json

    versions = _load_installed_versions_for_write()
    versions.pop(skill_id, None)
    filepath = _get_installed_versions_file()
    try:
        with open(filepath, "w") as f:
            json.dump(versions, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.warning("删除版本信息失败: %s", e)


def _load_installed_versions_for_write():
    """Load versions without merging external (for write operations)."""
    import json
    import os

    filepath = _get_installed_versions_file()
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


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
            results.append(
                {
                    "type": "deliverable",
                    "title": d.get("title", "成果物"),
                    "summary": content[:150],
                    "score": _simple_match_score(q_lower, content),
                    "link": None,
                }
            )

    try:
        from opc_manager.audit_log import get_audit_log

        audit = get_audit_log()
        logs = audit.query(limit=50)
        for log in logs:
            combined = f"{log.get('operation_type', '')} {log.get('input_summary', '')} {log.get('output_summary', '')}"
            if q_lower in combined.lower():
                results.append(
                    {
                        "type": "audit",
                        "title": f"[{log.get('operation_type', 'operation')}]",
                        "summary": log.get("input_summary", "")[:100],
                        "score": _simple_match_score(q_lower, combined),
                        "link": None,
                    }
                )
    except Exception as e:
        logger.warning("[marketplace] global_search audit_log query failed: %s", e)

    messages = st.session_state.get("messages", [])
    for msg in messages[-50:]:
        content = str(msg.get("content", ""))
        if q_lower in content.lower():
            results.append(
                {
                    "type": "chat",
                    "title": content[:60] + "..." if len(content) > 60 else content,
                    "summary": "",
                    "score": _simple_match_score(q_lower, content),
                    "link": None,
                }
            )

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
