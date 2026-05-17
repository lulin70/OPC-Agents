"""Marketplace page module for OPC-Agents frontend.

Contains all skill marketplace-related UI rendering functions:
- Main marketplace page with browse/my skills tabs
- Skill card rendering
- Global search functionality
"""

import streamlit as st
import logging

logger = logging.getLogger(__name__)


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
