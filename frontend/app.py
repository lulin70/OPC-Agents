"""Streamlit 前端 - OPC-Agents (成果物交付版) — Thin Dispatcher

=== 架构说明（v0.3.3 重构后）===
本文件仅负责：
1. 导入所有依赖模块
2. 页面配置（st.set_page_config）
3. Session State 初始化
4. 侧边栏导航渲染
5. 路由分发（PageKey → 对应 router）

页面逻辑已提取到:
- frontend/routers/     — 6个页面路由器
- frontend/renderers/   — 3个渲染器组件
- frontend/routers/base_router.py — 共享工具函数和常量
"""

import streamlit as st
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

from opc_manager.monitoring import init_monitoring

logger = logging.getLogger(__name__)

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

init_monitoring()

from frontend.routers.base_router import (
    DELIVERABLES_DIR,
    is_demo_mode,
    _load_chat_history,
    PERSONA_MAP,
    save_deliverable,
    init_session_state,
)

os.makedirs(DELIVERABLES_DIR, exist_ok=True)

for _subdir in [
    "data/knowledge",
    "data/notifications",
    "data/custom_skills",
    "data/marketplace",
    "data/feedback",
    "data/consensus_logs",
    "data/llm_cache",
    "data/schedules",
    "data/completions",
    "data/context",
    "data/checkpoints",
    "data/loop_progress",
    "data/workflows",
    "logs",
    "output",
]:
    os.makedirs(os.path.join(_WORKSPACE_DIR, _subdir), exist_ok=True)

from frontend.components.shared import (
    _render_theme_selector,
    _render_language_selector,
    _render_shortcuts_help,
    _get_current_session_id,
)

from frontend.components.undo_panel import (
    render_undo_panel,
    render_batch_undo,
    check_has_active_undo_records,
)


from frontend.page_modules._marketplace_page import (
    _execute_global_search,
)


from opc_manager.i18n import t as _t
from frontend.routers import PageKey, get_page_label, navigate
from frontend.renderers.onboarding_renderer import _show_onboarding_overlay

st.set_page_config(
    page_title=_t("app_title"),
    page_icon="",
    layout="wide",
    initial_sidebar_state="auto",
)

if is_demo_mode():
    st.markdown(
        f"""
    <div style="
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        text-align: center;
        margin-bottom: 16px;
        font-size: 15px;
    ">
         <strong>{_t('demo_banner_title')}</strong> — {_t('demo_banner_hint')} &nbsp;|&nbsp;
        {_t('demo_banner_action')}
    </div>
    """,
        unsafe_allow_html=True,
    )

if "initialized" not in st.session_state:
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
        "content_quality": 0,
        "audience_growth": 0,
        "monetization": 0,
        "cross_promotion": 0,
        "ecosystem_synergy": 0,
    }
    st.session_state.flywheel_level = 1
    st.session_state.achievements = []
    from opc_manager.async_executor import AsyncTaskExecutor
    from opc_manager.session_context import SessionContextManager

    st.session_state.session_ctx = SessionContextManager(max_turns=20)
    _async_executor = AsyncTaskExecutor(
        max_concurrent=3,
        default_timeout=120,
        save_callback=lambda *a, **kw: save_deliverable(*a, **kw),
        max_retries=2,
        retry_backoff_base=5.0,
        zombie_check_interval=30,
        persist_dir="data",
    )
    st.session_state.async_executor = _async_executor
    import atexit

    # Capture executor in closure so atexit does not need to access
    # st.session_state, which is only valid inside a Streamlit script run context.
    atexit.register(lambda executor=_async_executor: executor.shutdown())
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
                            else (
                                parts[2]
                                if len(parts) > 2
                                else _t("deliverable_prompt_fallback")
                            )
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

init_session_state()

onboarding_container = st.empty()

with st.sidebar:
    from opc_manager.i18n import t as _t

    st.text_input(
        _t("search_placeholder"),
        key="sidebar_global_search",
        label_visibility="collapsed",
    )

    if st.session_state.get("sidebar_global_search", "").strip():
        query = st.session_state.sidebar_global_search.strip()
        if len(query) >= 2:
            with st.expander(f" {query}", expanded=True):
                results = _execute_global_search(query)
                if results:
                    st.success(_t("search_found", count=len(results)))
                    for r in results[:8]:
                        st.markdown(f"**{r.get('title', '-')}**")
                        st.caption(r.get("summary", "")[:80])
                        st.divider()
                else:
                    st.info(_t("search_no_result"))

    st.markdown(_t("sidebar_title"))

    page_key_map = {
        "chat": PageKey.CHAT,
        "deliverables": PageKey.DELIVERABLES,
        "dashboard": PageKey.DASHBOARD,
        "growth": PageKey.GROWTH,
        "marketplace": PageKey.MARKETPLACE,
        "settings": PageKey.SETTINGS,
    }
    selected = st.radio(
        "Navigation",
        options=list(page_key_map.keys()),
        format_func=lambda k: get_page_label(page_key_map[k], _t),
        label_visibility="collapsed",
        key="main_page_navigation",
    )

    if st.session_state.detected_type:
        pinfo = PERSONA_MAP.get(
            st.session_state.detected_type, (_t("persona_default_name"), "")
        )
        st.divider()
        st.markdown(
            f"{_t('current_persona')}\n{_t(pinfo[0]) if pinfo else _t('persona_default_name')}"
        )
        st.caption(
            f"{_t('style_label')}{_t(pinfo[1]) if pinfo and len(pinfo) > 1 else ''}"
        )

    if st.session_state.deliverables:
        st.divider()
        st.markdown(_t("deliverables_count", count=len(st.session_state.deliverables)))

    # 记忆状态指示器
    try:
        from opc_manager.memory_bridge import get_memory_bridge

        _mb = get_memory_bridge()
        status = _mb.get_status()
        if status["enabled"]:
            st.divider()
            mem_info = _t("sidebar_memory_info", count=status["memory_count"])
            if status.get("rule_count", 0) > 0:
                mem_info += _t("sidebar_memory_rules", count=status["rule_count"])
            if status.get("pending_lessons", 0) > 0:
                mem_info += _t(
                    "sidebar_memory_pending", count=status["pending_lessons"]
                )
            st.markdown(mem_info)
        elif status["available"]:
            st.divider()
            st.caption(_t("sidebar_memory_disabled"))
    except Exception as e:
        logger.warning("[App] Memory sidebar init failed: %s", e)

    # 知识库状态指示器
    try:
        from opc_manager.knowledge_bridge import get_knowledge_bridge

        _kb = get_knowledge_bridge()
        kb_status = _kb.get_status()
        if kb_status["enabled"]:
            kb_type = kb_status.get("type", "")
            source_count = kb_status.get("source_count", kb_status.get("file_count", 0))
            st.markdown(_t("sidebar_knowledge_info", type=kb_type, count=source_count))
    except Exception as e:
        logger.warning("[App] Knowledge base sidebar init failed: %s", e)

    st.divider()
    st.markdown(_t("tools_section"))
    if st.button(_t("skill_editor"), use_container_width=True):
        st.session_state.show_skill_editor = not st.session_state.get(
            "show_skill_editor", False
        )

    if st.session_state.get("show_skill_editor", False):
        st.markdown(_t("skill_editor_title"))
        from opc_manager.skill_editor import (
            SkillEditor,
            CustomSkill,
            OutputFormat,
        )

        editor = SkillEditor()
        with st.form("create_skill_form"):
            sk_name = st.text_input(_t("skill_name_label"), key="sk_name")
            sk_desc = st.text_input(_t("skill_desc_label"), key="sk_desc")
            sk_cat = st.selectbox(
                _t("skill_cat_label"),
                ["custom", "analysis", "creation", "search", "operation"],
                key="sk_cat",
            )
            sk_output = st.selectbox(
                _t("skill_output_label"), ["markdown", "json", "text"], key="sk_output"
            )
            sk_template = st.text_area(
                _t("skill_template_placeholder"), key="sk_template", height=100
            )
            submitted = st.form_submit_button(_t("skill_create_btn"))
            if submitted and sk_name:
                import re

                if (
                    not re.match(r"^[\w\u4e00-\u9fff\s-]+$", sk_name)
                    or len(sk_name) > 50
                ):
                    st.error(_t("skill_name_validation_error"))
                elif len(sk_desc) > 500:
                    st.error(_t("skill_desc_validation_error"))
                else:
                    skill = CustomSkill(
                        skill_id=f"custom_{sk_name.lower().replace(' ', '_')}",
                        name=sk_name,
                        description=sk_desc,
                        category=sk_cat,
                        output_format=OutputFormat(sk_output),
                        template=sk_template,
                    )
                    result = editor.create_skill(skill)
                    if result["success"]:
                        st.success(_t("skill_created_success", name=sk_name))
                    else:
                        st.error(result.get("error", _t("skill_create_failed")))
        skills = editor.list_skills()
        if skills:
            st.markdown(_t("custom_skills_count", count=len(skills)))
            for s in skills[:5]:
                st.markdown(f"- {s['name']} ({s['skill_id']})")

    if st.button(_t("marketplace_btn"), use_container_width=True):
        st.session_state.show_marketplace = not st.session_state.get(
            "show_marketplace", False
        )

    if st.session_state.get("show_marketplace", False):
        st.markdown(_t("marketplace_panel_title"))
        from opc_manager.skill_marketplace import SkillMarketplace

        mp = SkillMarketplace()
        stats = mp.get_stats()
        st.caption(
            _t(
                "marketplace_stats_caption",
                total=stats["total_skills"],
                approved=stats["approved_skills"],
                pending=stats["pending_skills"],
            )
        )
        categories = mp.list_categories()
        if categories:
            sel_cat = st.selectbox(
                _t("filter_by_category"),
                [_t("category_all")] + categories,
                key="mp_cat",
            )
            discovered = mp.discover_skills(
                category=sel_cat if sel_cat != _t("category_all") else None
            )
        else:
            discovered = mp.discover_skills()
        if discovered:
            for sk in discovered[:10]:
                st.markdown(
                    f"**{sk['name']}** `v{sk['version']}` — {sk['description'][:80]}"
                )
                st.caption(
                    _t(
                        "skill_card_category_author",
                        category=sk["category"],
                        author=sk["author"],
                    )
                )
        else:
            st.info(_t("no_approved_skills"))

    if st.button(_t("perf_monitor"), use_container_width=True):
        st.session_state.show_perf = not st.session_state.get("show_perf", False)

    if st.session_state.get("show_perf", False):
        st.markdown(_t("perf_monitor_title"))
        from opc_manager.performance_monitor import performance_monitor

        stats = performance_monitor.get_stats()
        sla = performance_monitor.check_sla()
        total = stats.get("total_operations", 0)
        st.metric(_t("total_ops"), total)
        sla_color = "" if all(sla.values()) else ""
        st.markdown(
            f"{_t('sla_status_label')}: {sla_color} {_t('sla_single_request')}{'' if sla.get('single_request') else ''} | {_t('sla_reflect_loop')}{'' if sla.get('reflect_loop') else ''}"
        )
        cache = stats.get("cache", {})
        if cache:
            st.caption(
                _t(
                    "cache_llm",
                    hit_rate=cache.get("hit_rate", 0),
                    size=cache.get("size", 0),
                    max_size=cache.get("max_size", 0),
                )
            )
        ops = stats.get("operations", {})
        if ops:
            for op, op_stats in ops.items():
                st.caption(
                    _t(
                        "op_stats_fmt",
                        op=op,
                        avg_ms=op_stats["avg_ms"],
                        p95_ms=op_stats.get("p95_ms", 0),
                    )
                )

    with st.container():
        if st.button(
            _t("undo_history_btn"), use_container_width=True, help=_t("undo_mgmt")
        ):
            st.session_state.show_undo_panel = not st.session_state.get(
                "show_undo_panel", False
            )

        if st.session_state.get("show_undo_panel", False):
            session_id = _get_current_session_id()
            with st.expander(_t("undo_detail_title"), expanded=True):
                render_undo_panel(session_id, expand=True)

                if check_has_active_undo_records(session_id):
                    with st.expander(_t("batch_undo_title"), expanded=False):
                        render_batch_undo(session_id)

    with st.container():
        if st.button(_t("live_log_btn"), use_container_width=True, help=_t("live_log")):
            st.session_state.show_log_panel = not st.session_state.get(
                "show_log_panel", False
            )

        if st.session_state.get("show_log_panel", False):
            with st.expander(_t("live_log_panel_title"), expanded=True):
                from frontend.components.live_log_panel import render_live_log_panel

                render_live_log_panel(auto_refresh=True, refresh_interval=2)

    _render_theme_selector()
    _render_language_selector()
    _render_shortcuts_help()

    from opc_manager.version import get_version

    st.caption(f"OPC-Agents v{get_version()}")

navigate(page_key_map[selected])

try:
    from opc_manager.onboarding import get_onboarding

    onboard = get_onboarding()
    if not onboard.is_completed and not st.session_state.get(
        "onboarding_complete", False
    ):
        with onboarding_container:
            _show_onboarding_overlay()
    else:
        onboarding_container.empty()
        if not st.session_state.get("onboarding_complete", False):
            st.session_state.onboarding_complete = True
except ImportError:
    onboarding_container.empty()
except Exception as e:
    logger.warning("[frontend] Onboarding check failed: %s", e)
    onboarding_container.empty()

if st.query_params.get("_stcore_health") == "1":
    st.write("ok")
    st.stop()
