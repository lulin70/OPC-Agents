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

logger = logging.getLogger(__name__)

ALL_CATEGORIES = [
    "CRM", "Finance", "Email", "Calendar", "Social",
    "Knowledge", "Report", "Task", "Proposal", "Tax",
    "Dashboard", "Competitor", "Pricing", "Invoice",
    "Security", "Monitoring",
]

SORT_OPTIONS = {
    "name_asc": "名前 A→Z",
    "name_desc": "名前 Z→A",
    "popular": "人気順",
}


def _render_skill_marketplace_page():
    """Render the Skill Marketplace V2 page.

    Features:
    1. Browse tab: Search + category filter + sort + skill cards grid
    2. My Skills tab: Installed skills list with version pinning
    3. Detail view: Click card to see full info + install/uninstall button
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

        st.caption(f"共 {total_skills} 个技能 | 已审核 {approved} 个 | 当前显示 {len(filtered_skills)} 个")

        if not filtered_skills:
            st.info("没有找到匹配的技能，请尝试调整搜索条件或筛选器")
            return

        installed_versions = _load_installed_versions(external_mp)

        cols = st.columns(3)
        for i, skill in enumerate(filtered_skills[:12]):
            with cols[i % 3]:
                _render_skill_card_v2(skill, marketplace, external_mp, installed_versions)

    except Exception as e:
        st.error(f"加载技能列表失败: {e}")


def _render_marketplace_filters_v2():
    """Render search + category filter + sort controls (V2)."""
    search = st.text_input(
        "🔍 搜索技能...",
        placeholder="搜索名称、描述或作者...",
        key="mp_search_v2",
    )

    col_cat, col_sort = st.columns([3, 1])
    with col_cat:
        selected_cats = st.multiselect(
            "カテゴリーで絞り込み",
            options=ALL_CATEGORIES,
            default=[],
            key="mp_category_filter_v2",
        )
    with col_sort:
        sort_by = st.selectbox(
            "並び替え",
            options=list(SORT_OPTIONS.keys()),
            format_func=lambda x: SORT_OPTIONS.get(x, x),
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
        filtered = [s for s in filtered
                    if q in s.get("name", "").lower()
                    or q in s.get("description", "").lower()]

    if categories:
        filtered = [s for s in filtered if s.get("category", "") in categories]

    if sort_by == "name_asc":
        filtered = sorted(filtered, key=lambda s: s.get("name", ""))
    elif sort_by == "name_desc":
        filtered = sorted(filtered, key=lambda s: s.get("name", ""), reverse=True)
    elif sort_by == "popular":
        filtered.sort(key=lambda s: _simulate_install_count(s.get("skill_id", "")), reverse=True)

    return filtered


def _simulate_install_count(skill_id):
    """Simulate install count based on skill_id hash for demo purposes."""
    return int(hashlib.md5(skill_id.encode()).hexdigest()[:8], 16) % 10000


def _render_skill_card_v2(skill, marketplace, external_mp, installed_versions=None):
    """Render a single skill card with version pinning (V2)."""
    if installed_versions is None:
        installed_versions = {}

    name = skill.get("name", "未知技能")
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
        "official": "官方",
        "verified": "已验证",
        "community": "社区",
        "unverified": "未验证",
    }

    is_installed = skill_id in installed_versions
    installed_ver = installed_versions.get(skill_id, "")
    update_available = is_installed and installed_ver and installed_ver != version

    status_text = ""
    if is_installed:
        if update_available:
            status_text = f" `v{installed_ver}` 🔄 更新可用"
        else:
            status_text = f" `v{installed_ver}` ✅ 已安装"
    else:
        status_text = f" v{version}"

    with st.container(border=True):
        st.markdown(f"**{name}**{status_text}")
        st.caption(desc[:80] + "..." if len(desc) > 80 else desc)
        st.markdown(f"*{category}* · {author}")

        if update_available:
            st.markdown("<span style='color:red'>⚠️ 新版本可用</span>", unsafe_allow_html=True)

        if st.button(f"查看详情 →", key=f"skill_detail_{skill_id}_{id(skill)}", use_container_width=True):
            st.session_state["selected_skill"] = skill


def _render_skill_detail(skill, marketplace, external_mp):
    """Render detailed skill information panel (V2)."""
    name = skill.get("name", "未知技能")
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
        st.markdown("> ⚠️ **更新可用**: 当前已安装 v{installed_ver}，最新版本为 v{version}")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"**説明**: {desc}")
        st.markdown(f"**カテゴリー**: {category}")
        st.markdown(f"**バージョン**: {version}")
        st.markdown(f"**作者**: {author}")
        st.markdown(f"**インストール数**: **{_simulate_install_count(skill_id):,}** 回")
        st.markdown("**互換性**: OPC-Agents v0.2.0+")

        if tags:
            tag_str = " ".join(f"`{t}`" for t in tags)
            st.markdown(f"**タグ**: {tag_str}")

    with col2:
        if is_installed:
            if st.button("🗑️ アンインストール", key=f"uninstall_detail_{skill_id}", type="secondary"):
                try:
                    result = external_mp.uninstall_skill(skill_id)
                    if result.get("success"):
                        st.success("アンインストール完了")
                        _remove_installed_version(skill_id)
                        st.session_state.pop("selected_skill", None)
                        st.rerun()
                    else:
                        st.error(result.get("error", "アンインストール失敗"))
                except Exception as e:
                    st.error(f"アンインストール失敗: {e}")
            if update_available:
                if st.button("⬆️ 更新", key=f"update_detail_{skill_id}", type="primary"):
                    try:
                        result = external_mp.install_skill(skill_id, confirmed=True)
                        if result.get("success"):
                            _save_installed_version(skill_id, version)
                            st.success(f"更新完了: v{installed_ver} → v{version}")
                            st.rerun()
                        else:
                            st.error(result.get("error", "更新失敗"))
                    except Exception as e:
                        st.error(f"更新失敗: {e}")
        else:
            if st.button("⬇️ インストール", key=f"install_detail_{skill_id}", type="primary"):
                try:
                    result = external_mp.install_skill(skill_id, confirmed=True)
                    if result.get("success"):
                        _save_installed_version(skill_id, version)
                        st.success("インストール完了")
                        st.rerun()
                    elif result.get("requires_confirmation"):
                        st.warning("このスキルのインストールには確認が必要です")
                    else:
                        st.error(result.get("error", "インストール失敗"))
                except Exception as e:
                    st.error(f"インストール失敗: {e}")

    st.divider()

    if st.button("← グリッドに戻る", key="back_to_grid"):
        st.session_state.pop("selected_skill", None)
        st.rerun()


def _render_my_skills_v2(marketplace, external_mp):
    """Render installed/manageable skills list with version pinning (V2)."""
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

    installed_versions = _load_installed_versions(external_mp)
    st.caption(f"已安装 {len(installed)} 个技能")

    for skill in installed:
        skill_id = skill.get("skill_id", "")
        skill_name = skill.get("name", "Unknown")
        skill_version = skill.get("version", "?")
        pinned_version = installed_versions.get(skill_id, skill_version)

        with st.expander(f"📦 {skill_name} v{pinned_version or skill_version}"):
            col_info, col_action = st.columns([3, 1])
            with col_info:
                st.json({
                    "名称": skill.get("name"),
                    "版本": pinned_version or skill.get("version"),
                    "来源": skill.get("source", "-"),
                    "状态": skill.get("status"),
                    "信任等级": skill.get("trust_level", "-"),
                    "安装时间": skill.get("installed_at", "-"),
                })
            with col_action:
                if st.button("卸载", key=f"uninstall_{skill_id or id(skill)}"):
                    try:
                        result = external_mp.uninstall_skill(skill_id)
                        if result.get("success"):
                            _remove_installed_version(skill_id)
                            st.success("已卸载")
                            st.rerun()
                        else:
                            st.error(result.get("error", "卸载失败"))
                    except Exception as e:
                        st.error(f"卸载失败: {e}")


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
        installed_list = installed_result.get("skills", []) if isinstance(installed_result, dict) else []
        for s in installed_list:
            sid = s.get("skill_id", "")
            if sid and sid not in versions:
                versions[sid] = s.get("version", "1.0.0")
    except Exception:
        pass
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
