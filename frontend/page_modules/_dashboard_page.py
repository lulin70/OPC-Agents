"""Dashboard page module for OPC-Agents frontend.

Contains all dashboard-related UI rendering functions:
- Template-based layout system (Compact / Focused / Minimal)
- Density levels (Detailed / Standard / Compact)
- Per-panel enable/disable toggles with persistence
- 6 dashboard panels (income, client health, tasks, finance, timeline, skills)
"""

import streamlit as st
import logging
import time
import pandas as pd
from datetime import datetime
from collections import Counter

from opc_manager.dashboard_config import (
    DashboardConfig,
    LayoutType,
    DensityLevel,
    PanelConfig,
    ALL_PANEL_IDS,
)
from opc_manager.i18n import t as _t

logger = logging.getLogger(__name__)

_DEMO_DATA = {
    "income_months": ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05"],
    "income_values": [28000, 32000, 29500, 38000, 45000],
    "clients": [
        {
            "name": "字节跳动",
            "contact": "张总",
            "projects": 3,
            "revenue": 85000,
            "health": 95,
            "last_contact": "2天前",
        },
        {
            "name": "美团点评",
            "contact": "李经理",
            "projects": 2,
            "revenue": 52000,
            "health": 88,
            "last_contact": "5天前",
        },
        {
            "name": "京东零售",
            "contact": "王总监",
            "projects": 1,
            "revenue": 35000,
            "health": 72,
            "last_contact": "1周前",
        },
        {
            "name": "滴滴出行",
            "contact": "陈PM",
            "projects": 2,
            "revenue": 48000,
            "health": 82,
            "last_contact": "3天前",
        },
        {
            "name": "网易游戏",
            "contact": "刘制作人",
            "projects": 1,
            "revenue": 28000,
            "health": 90,
            "last_contact": "4天前",
        },
    ],
    "tasks": {"total": 28, "done": 22, "in_progress": 4, "blocked": 2},
    "finance": {
        "income": 172500,
        "expense": 28600,
        "tax_estimate": 25875,
        "net_profit": 118025,
    },
    "timeline": [
        {
            "time": "09:15",
            "icon": "📄",
            "text": "完成《Q1咨询项目总结报告》",
            "tag": "成果物",
            "color": "green",
        },
        {
            "time": "10:30",
            "icon": "💰",
            "text": "记录收入 ¥35,000（字节跳动-Phase2）",
            "tag": "财务",
            "color": "blue",
        },
        {
            "time": "13:00",
            "icon": "🤝",
            "text": "客户会议：美团点评 Q2规划讨论",
            "tag": "会议",
            "color": "purple",
        },
        {
            "time": "15:30",
            "icon": "📊",
            "text": "Dashboard 数据分析完成",
            "tag": "系统",
            "color": "gray",
        },
        {
            "time": "16:45",
            "icon": "📝",
            "text": "提交《数字化转型方案》初稿",
            "tag": "提案",
            "color": "orange",
        },
        {
            "time": "17:30",
            "icon": "✅",
            "text": "完成日报自动生成",
            "tag": "任务",
            "color": "green",
        },
    ],
    "skills": [
        {"name": "CRM 客户管理", "usage": 56, "trend": "↑ 12%"},
        {"name": "智能报告生成", "usage": 43, "trend": "↑ 8%"},
        {"name": "财务记账", "usage": 38, "trend": "↑ 15%"},
        {"name": "邮件助手", "usage": 27, "trend": "-3%"},
        {"name": "日历管理", "usage": 21, "trend": "↑ 5%"},
        {"name": "竞品分析", "usage": 18, "trend": "↑ 22%"},
    ],
}

ALL_PANELS_META = [
    ("income_trend", _t("dashboard_income_trend"), _t("dash_panel_income_desc")),
    ("client_health", _t("dashboard_client_health"), _t("dash_panel_clients_desc")),
    ("task_completion", _t("dashboard_task_completion"), _t("dash_panel_tasks_desc")),
    (
        "financial_summary",
        _t("dashboard_monthly_finance"),
        _t("dash_panel_finance_desc"),
    ),
    (
        "activity_timeline",
        _t("dashboard_activity_timeline"),
        _t("dash_panel_timeline_desc"),
    ),
    ("skill_usage", _t("dashboard_skill_stats"), _t("dash_panel_skills_desc")),
]

LAYOUT_LABELS = {
    LayoutType.COMPACT: _t("dash_layout_compact"),
    LayoutType.FOCUSED: _t("dash_layout_focused"),
    LayoutType.MINIMAL: _t("dash_layout_minimal"),
}

DENSITY_LABELS = {
    DensityLevel.COMPACT: _t("dash_density_compact"),
    DensityLevel.STANDARD: _t("dash_density_standard"),
    DensityLevel.DETAILED: _t("dash_density_detailed"),
}


def _is_demo_mode() -> bool:
    """Check if dashboard should show demo data.

    Uses the demo_mode parameter already available in the render context
    rather than making expensive backend calls.
    """
    return st.session_state.get("_dashboard_demo_mode", False)


def _render_demo_badge():
    st.markdown(
        """
    <div style="
        display: inline-block;
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        opacity: 0.85;
        margin-bottom: 8px;
    ">🎮 {_t('demo_badge_text')}</div>
    """,
        unsafe_allow_html=True,
    )


def _render_dashboard_page(demo_mode: bool = False):
    """Render modular Dashboard with template-based layout system.

    Features:
    - 3 layout presets: Compact(2-col), Focused(main+side), Minimal(1-col)
    - 3 density levels: Compact, Standard, Detailed
    - Per-panel enable/disable toggles
    - Persistence via DashboardConfig JSON file
    - Demo mode with sample data when no API key configured
    - Mobile responsive: auto-switches to Minimal layout on small screens
    """
    st.markdown(f"## {_t('dash_title')}")

    # Persist demo_mode so _is_demo_mode() can use it without backend calls
    st.session_state._dashboard_demo_mode = demo_mode

    # 移动端响应式 CSS 已由 theme_manager 统一注入

    if demo_mode:
        st.info(f"📊 {_t('dash_demo_info')}")
        _render_demo_dashboard()
        return

    config = _load_or_init_config()

    _render_template_controls(config)

    st.divider()

    enabled_panels = config.get_enabled_panels()
    if not enabled_panels:
        st.info(f"💡 {_t('dash_no_panels')}")
        return

    _CACHE_TTL = 60  # seconds
    _cache_key = "_dashboard_data"
    _cache_ts_key = "_dashboard_data_ts"

    with st.spinner(_t("dash_loading") if "_t" in dir() else "Loading dashboard..."):
        if _cache_key not in st.session_state or \
           time.time() - st.session_state.get(_cache_ts_key, 0) > _CACHE_TTL:
            st.session_state[_cache_key] = _get_dashboard_data()
            st.session_state[_cache_ts_key] = time.time()

    data = st.session_state[_cache_key]

    _render_layout(config, enabled_panels, data)


def _load_or_init_config() -> DashboardConfig:
    if "dashboard_config" not in st.session_state:
        st.session_state.dashboard_config = DashboardConfig.load()
    return st.session_state.dashboard_config


def _render_template_controls(config: DashboardConfig):
    with st.expander(_t("dash_settings_title"), expanded=False):
        col_layout, col_density = st.columns(2)
        with col_layout:
            layout_key = "dashboard_layout_sel"
            current_layout = st.session_state.get(layout_key, config.layout)
            selected_layout_label = st.selectbox(
                _t("dash_layout_label"),
                options=list(LAYOUT_LABELS.keys()),
                format_func=lambda x: LAYOUT_LABELS.get(x, x.value),
                index=(
                    list(LAYOUT_LABELS.keys()).index(current_layout)
                    if current_layout in LAYOUT_LABELS
                    else 1
                ),
                key=layout_key,
                help=_t("dash_layout_help"),
            )
        with col_density:
            density_key = "dashboard_density_sel"
            current_density = st.session_state.get(density_key, config.density)
            selected_density_label = st.selectbox(
                _t("dash_density_label"),
                options=list(DENSITY_LABELS.keys()),
                format_func=lambda x: DENSITY_LABELS.get(x, x.value),
                index=(
                    list(DENSITY_LABELS.keys()).index(current_density)
                    if current_density in DENSITY_LABELS
                    else 1
                ),
                key=density_key,
                help=_t("dash_density_help"),
            )

        st.markdown(_t("dash_panel_toggles"))
        panel_toggles_cols = st.columns(2)
        toggle_states = {}
        for idx, (panel_id, title, desc) in enumerate(ALL_PANELS_META):
            with panel_toggles_cols[idx % 2]:
                is_checked = st.checkbox(
                    f"{title}",
                    value=(
                        config.panels[panel_id].enabled
                        if panel_id in config.panels
                        else True
                    ),
                    help=desc,
                    key=f"dashboard_toggle_{panel_id}",
                )
                toggle_states[panel_id] = is_checked

        col_apply, col_reset, _ = st.columns([1, 1, 2])
        with col_apply:
            if st.button(
                _t("dash_btn_apply"), type="primary", use_container_width=True
            ):
                _apply_settings(
                    config, selected_layout_label, selected_density_label, toggle_states
                )
        with col_reset:
            if st.button(_t("dash_btn_reset"), use_container_width=True):
                st.session_state.dashboard_config = DashboardConfig()
                st.rerun()


def _apply_settings(
    config: DashboardConfig,
    layout: LayoutType,
    density: DensityLevel,
    toggle_states: dict,
):
    config.layout = layout
    config.density = density
    for panel_id, enabled in toggle_states.items():
        config.set_panel_enabled(panel_id, enabled)
    config.save()
    st.session_state.dashboard_config = config
    st.success(f"✅ {_t('dash_settings_saved')}")
    st.rerun()


def _render_layout(config: DashboardConfig, enabled_panels: list, data: dict):
    density = config.density
    renderers = {
        "income_trend": lambda **kw: _render_income_trend_panel(density=density, data=data, **kw),
        "client_health": lambda **kw: _render_client_health_panel(
            density=density, data=data, **kw
        ),
        "task_completion": lambda **kw: _render_task_completion_panel(
            density=density, data=data, **kw
        ),
        "financial_summary": lambda **kw: _render_financial_summary_panel(
            density=density, data=data, **kw
        ),
        "activity_timeline": lambda **kw: _render_activity_timeline_panel(
            density=density, data=data, **kw
        ),
        "skill_usage": lambda **kw: _render_skill_usage_panel(density=density, data=data, **kw),
    }

    if config.layout == LayoutType.COMPACT:
        _render_compact_layout(enabled_panels, renderers, density)
    elif config.layout == LayoutType.FOCUSED:
        _render_focused_layout(enabled_panels, renderers, density)
    else:
        _render_minimal_layout(enabled_panels, renderers, density)


def _render_compact_layout(enabled: list, renderers: dict, density: DensityLevel):
    for i in range(0, len(enabled), 2):
        row = enabled[i : i + 2]
        cols = st.columns(len(row))
        for idx, panel_id in enumerate(row):
            with cols[idx]:
                try:
                    renderers[panel_id]()
                except Exception as e:
                    logger.error("[dashboard] Panel %s error: %s", panel_id, e)
                    st.error(f"{_t('dash_panel_error').format(panel=panel_id)}")


def _render_focused_layout(enabled: list, renderers: dict, density: DensityLevel):
    if not enabled:
        return
    try:
        renderers[enabled[0]](full_width=True)
    except Exception as e:
        logger.error("[dashboard] Panel %s error: %s", enabled[0], e)
        st.error(f"{_t('dash_panel_error').format(panel=enabled[0])}")
    remaining = enabled[1:]
    for i in range(0, len(remaining), 2):
        row = remaining[i : i + 2]
        cols = st.columns(len(row))
        for idx, panel_id in enumerate(row):
            with cols[idx]:
                try:
                    renderers[panel_id]()
                except Exception as e:
                    logger.error("[dashboard] Panel %s error: %s", panel_id, e)
                    st.error(f"{_t('dash_panel_error').format(panel=panel_id)}")
    if len(enabled) > 3:
        last_full = (
            enabled[-1] if (len(enabled) - 1) % 2 == 0 and len(enabled) > 1 else None
        )
        if last_full:
            try:
                renderers[last_full](full_width=True)
            except Exception as e:
                logger.error("[dashboard] Panel %s error: %s", last_full, e)
                st.error(f"{_t('dash_panel_error').format(panel=last_full)}")


def _render_minimal_layout(enabled: list, renderers: dict, density: DensityLevel):
    for panel_id in enabled:
        try:
            renderers[panel_id](full_width=True)
        except Exception as e:
            logger.error("[dashboard] Panel %s error: %s", panel_id, e)
            st.error(f"{_t('dash_panel_error').format(panel=panel_id)}")


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
        from opc_manager.crm_skill import (
            get_customer_stats,
            get_silent_customers,
            list_customers,
        )

        data["crm"]["stats"] = get_customer_stats()
        data["crm"]["silent"] = get_silent_customers()
        try:
            data["crm"]["customers"] = list_customers(limit=10).get("customers", [])
        except Exception as e:
            logger.warning("[Dashboard] CRM customer list failed: %s", e)
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


def _render_demo_dashboard():
    """Render dashboard with sample/demo data for no-LLM mode."""
    from frontend.routers.base_router import _get_demo_dashboard_data

    demo = _get_demo_dashboard_data()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"### {_t('dash_demo_income_title')}")
        trend = demo["income_trend"]
        st.metric(
            _t("dash_cumulative_income"), f"¥{trend['total']:,}", delta=trend["growth"]
        )
        labels = trend["labels"]
        values = trend["values"]
        df = pd.DataFrame({_t("dash_month_col"): labels, _t("dash_income_col"): values})
        st.line_chart(df.set_index(_t("dash_month_col")), use_container_width=True)

    with col2:
        st.markdown(f"### {_t('dash_demo_finance_title')}")
        fs = demo["financial_summary"]
        fin_col1, fin_col2, fin_col3 = st.columns(3)
        with fin_col1:
            st.metric(_t("dash_income_metric"), f"¥{fs['income']:,}")
        with fin_col2:
            st.metric(
                _t("dash_expense_metric"), f"¥{fs['expenses']:,}", delta_color="inverse"
            )
        with fin_col3:
            st.metric(_t("dash_profit_metric"), f"¥{fs['profit']:,}")

    st.divider()

    col3, col4 = st.columns(2)
    with col3:
        st.markdown(f"### {_t('dash_demo_clients_title')}")
        for client in demo["client_health"]:
            arrow = "📈" if client["trend"] == "up" else "➡️"
            st.markdown(
                f"**{client['name']}** — {arrow} {_t('dash_score')} {client['score']} | {_t('dash_projects')} {client['projects']}"
            )

    with col4:
        st.markdown(f"### {_t('dash_demo_tasks_title')}")
        tc = demo["task_completion"]
        st.metric(_t("dash_completion_rate"), tc["rate"], f"{tc['done']}/{tc['total']}")
        done_pct = int(tc["rate"].replace("%", "")) / 100
        st.progress(done_pct)

    st.divider()

    col5, col6 = st.columns(2)
    with col5:
        st.markdown(f"### {_t('dash_demo_timeline_title')}")
        for event in demo["timeline"]:
            type_emoji = {
                "deliverable": "📄",
                "finance": "💰",
                "meeting": "🤝",
                "proposal": "📝",
            }.get(event["type"], "📌")
            st.markdown(f"{type_emoji} **{event['time']}** — {event['event']}")

    with col6:
        st.markdown(f"### {_t('dash_demo_skills_title')}")
        for skill in demo["skill_usage"]:
            st.markdown(
                f"**{skill['name']}** — {_t('dash_calls')} {skill['count']} {_t('dash_calls')}"
            )


def _render_income_trend_panel(
    density: DensityLevel = DensityLevel.STANDARD, full_width: bool = False, data: dict = None
):
    """Panel 1: 收入趋势图 - Income trend chart."""
    st.markdown(f"### {_t('dashboard_income_trend')}")

    if data is None:
        data = _get_dashboard_data()
    trend = data.get("finance", {}).get("trend", [])

    if _is_demo_mode():
        _render_demo_badge()

        demo_months = _DEMO_DATA["income_months"]
        demo_values = _DEMO_DATA["income_values"]
        expense_vals = [int(v * (0.12 + (i * 0.02))) for i, v in enumerate(demo_values)]
        profit_vals = [
            demo_values[i] - expense_vals[i] for i in range(len(demo_values))
        ]
        chart_data = pd.DataFrame(
            {
                _t("dash_month_col"): demo_months,
                _t("dash_income_col"): demo_values,
                _t("dash_expense_col"): expense_vals,
                _t("dash_profit_col"): profit_vals,
            }
        )
        st.line_chart(
            chart_data.set_index(_t("dash_month_col")), use_container_width=True
        )
        latest_profit = profit_vals[-1]
        prev_profit = profit_vals[-2]
        change_pct = (
            ((latest_profit - prev_profit) / abs(prev_profit) * 100)
            if prev_profit != 0
            else 0
        )
        delta_color = "normal" if change_pct >= 0 else "inverse"
        st.metric(
            _t("dash_monthly_profit_demo"),
            f"¥{latest_profit:,.0f}",
            f"{change_pct:+.1f}%" if change_pct != 0 else None,
            delta_color=delta_color,
        )
        return

    if not trend:
        st.info(f"💡 {_t('dash_no_finance_data')}")
        return

    df = pd.DataFrame(trend)
    chart_data = pd.DataFrame(
        {
            _t("dash_month_col"): [t.get("year_month", "") for t in trend],
            _t("dash_income_col"): [t.get("income", 0) for t in trend],
            _t("dash_expense_col"): [t.get("expense", 0) for t in trend],
            _t("dash_profit_col"): [t.get("profit", 0) for t in trend],
        }
    )

    if density == DensityLevel.DETAILED:
        st.line_chart(
            chart_data.set_index(_t("dash_month_col")), use_container_width=True
        )
    elif density == DensityLevel.STANDARD:
        st.line_chart(
            chart_data.set_index(_t("dash_month_col")), use_container_width=True
        )
    else:
        latest = trend[-1].get("profit", 0) if trend else 0
        prev = trend[-2].get("profit", 0) if len(trend) >= 2 else 0
        change = ((latest - prev) / abs(prev) * 100) if prev != 0 else 0
        arrow = "📈" if change >= 0 else "📉"
        st.markdown(
            f"**{arrow} {_t('dash_monthly_profit_label').format(val=latest, pct=change)}**"
        )

    if density != DensityLevel.COMPACT and len(trend) >= 2:
        latest = trend[-1].get("profit", 0)
        previous = trend[-2].get("profit", 0)
        change_pct = ((latest - previous) / abs(previous) * 100) if previous != 0 else 0
        delta_color = "normal" if change_pct >= 0 else "inverse"
        st.metric(
            _t("dash_this_month_profit"),
            f"¥{latest:,.2f}",
            f"{change_pct:+.1f}%" if change_pct != 0 else None,
            delta_color=delta_color,
        )


def _render_client_health_panel(
    density: DensityLevel = DensityLevel.STANDARD, full_width: bool = False, data: dict = None
):
    """Panel 2: 客户健康度 - Client health score."""
    st.markdown(f"### {_t('dashboard_client_health')}")

    if data is None:
        data = _get_dashboard_data()
    customers = data.get("crm", {}).get("customers", [])
    stats = data.get("crm", {}).get("stats", {})
    silent = data.get("crm", {}).get("silent", {})

    if _is_demo_mode():
        _render_demo_badge()
        demo_clients = _DEMO_DATA["clients"]
        col_total, col_active, col_silent = st.columns(3)
        with col_total:
            st.metric(_t("dash_total_clients_demo"), len(demo_clients))
        with col_active:
            active_count = sum(1 for c in demo_clients if c.get("health", 0) >= 80)
            st.metric(_t("dash_active_clients"), active_count)
        with col_silent:
            silent_count = sum(1 for c in demo_clients if c.get("health", 0) < 75)
            st.metric(_t("dash_need_attention"), silent_count, delta_color="inverse")

        client_data = []
        for c in demo_clients:
            health_emoji = (
                "🟢"
                if c.get("health", 0) >= 85
                else ("🟡" if c.get("health", 0) >= 70 else "🔴")
            )
            client_data.append(
                {
                    _t("dash_client_name"): c["name"],
                    _t("dash_contact"): c["contact"],
                    _t("dash_projects_col"): c["projects"],
                    _t("dash_revenue"): f"¥{c['revenue']:,}",
                    _t("dash_health"): f"{health_emoji} {c['health']}%",
                    _t("dash_last_contact"): c["last_contact"],
                }
            )
        df = pd.DataFrame(client_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        return

    total = stats.get("total", 0)
    active = stats.get("active", 0)
    silent_count = silent.get("count", 0)

    if total == 0 and not customers:
        st.info(f"💡 {_t('dash_no_client_data')}")
        return

    if density == DensityLevel.COMPACT:
        st.markdown(
            f"**{_t('dash_total_summary').format(t=total, a=active, s=silent_count)}**"
        )
        return

    col_total, col_active, col_silent = st.columns(3)
    with col_total:
        st.metric(_t("dash_total_clients_metric"), total)
    with col_active:
        st.metric(_t("dash_active_clients"), active)
    with col_silent:
        st.metric(_t("dash_silent_clients"), silent_count, delta_color="inverse")

    if density == DensityLevel.DETAILED and customers:

        customer_data = []
        for c in customers[:10]:
            name = c.get("name", "Unknown")
            status = c.get("status", "unknown")
            last_contact = c.get("last_contact", "")
            interactions = c.get("interactions", 0)

            from datetime import datetime as _dt, timedelta

            now = _dt.now()
            health_status = _t("dash_health_healthy")
            if last_contact:
                try:
                    last_date = (
                        _dt.strptime(last_contact[:10], "%Y-%m-%d")
                        if len(last_contact) >= 10
                        else now
                    )
                    days_since = (now - last_date).days
                    if days_since > 30:
                        health_status = _t("dash_health_attention")
                    elif days_since > 14:
                        health_status = _t("dash_health_normal")
                except Exception as e:
                    logger.warning("[Dashboard] Health check failed: %s", e)

            customer_data.append(
                {
                    _t("dash_client_name"): name,
                    _t("dash_status"): status,
                    _t("dash_interactions"): interactions,
                    _t("dash_last_contact"): last_contact[:10] if last_contact else "-",
                    _t("dash_health"): health_status,
                }
            )

        if customer_data:
            df = pd.DataFrame(customer_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
    elif density == DensityLevel.STANDARD and customers:

        customer_data = []
        for c in customers[:5]:
            name = c.get("name", "Unknown")
            interactions = c.get("interactions", 0)
            customer_data.append(
                {_t("dash_client_name"): name, _t("dash_interactions"): interactions}
            )
        if customer_data:
            df = pd.DataFrame(customer_data)
            st.dataframe(df, use_container_width=True, hide_index=True)


def _render_task_completion_panel(
    density: DensityLevel = DensityLevel.STANDARD, full_width: bool = False, data: dict = None
):
    """Panel 3: 任务完成率 - Task completion rate."""
    st.markdown(f"### {_t('dashboard_task_completion')}")

    if data is None:
        data = _get_dashboard_data()
    tasks = data.get("tasks", {}).get("list", [])
    by_status = data.get("tasks", {}).get("by_status", {})

    if _is_demo_mode():
        _render_demo_badge()
        demo_tasks = _DEMO_DATA["tasks"]
        total = demo_tasks["total"]
        done = demo_tasks["done"]
        in_progress = demo_tasks["in_progress"]
        blocked = demo_tasks["blocked"]
        completion_rate = (done / total * 100) if total > 0 else 0
        emoji = (
            "🟢" if completion_rate >= 70 else ("🟡" if completion_rate >= 40 else "🔴")
        )
        if density == DensityLevel.COMPACT:
            st.markdown(
                f"**{emoji} {_t('dash_completion_rate')} {completion_rate:.1f}%（Demo）** ({done}/{total})"
            )
            return
        col_total, col_done, col_rate = st.columns(3)
        with col_total:
            st.metric(_t("dash_total_tasks_demo"), total)
        with col_done:
            st.metric(_t("dash_completed"), done)
        with col_rate:
            st.metric(_t("dash_completion_rate_metric"), f"{completion_rate:.1f}%")
        st.progress(
            completion_rate / 100,
            text=_t("dash_progress_demo").format(rate=completion_rate),
        )

        status_df = pd.DataFrame(
            [
                {
                    _t("dash_status"): _t("dash_status_done"),
                    _t("dash_count_col"): done,
                    _t("dash_percentage_col2"): f"{done/total*100:.1f}%",
                    "color": "green",
                },
                {
                    _t("dash_status"): _t("dash_status_progress"),
                    _t("dash_count_col"): in_progress,
                    _t("dash_percentage_col2"): f"{in_progress/total*100:.1f}%",
                    "color": "orange",
                },
                {
                    _t("dash_status"): _t("dash_status_blocked"),
                    _t("dash_count_col"): blocked,
                    _t("dash_percentage_col2"): f"{blocked/total*100:.1f}%",
                    "color": "red",
                },
            ]
        )
        st.dataframe(status_df, use_container_width=True, hide_index=True)
        return

    total = len(tasks)
    completed = by_status.get("completed", 0)
    in_progress = by_status.get("in_progress", 0)
    pending = by_status.get("pending", 0)

    if total == 0:
        st.info(f"💡 {_t('dash_no_task_data')}")
        return

    completion_rate = (completed / total * 100) if total > 0 else 0

    if density == DensityLevel.COMPACT:
        emoji = (
            "🟢" if completion_rate >= 70 else ("🟡" if completion_rate >= 40 else "🔴")
        )
        st.markdown(
            f"**{emoji} {_t('dash_completion_rate')} {completion_rate:.1f}%** ({completed}/{total})"
        )
        return

    col_total, col_done, col_rate = st.columns(3)
    with col_total:
        st.metric(_t("dash_total_tasks"), total)
    with col_done:
        st.metric(_t("dash_completed"), completed)
    with col_rate:
        st.metric(_t("dash_completion_rate_metric"), f"{completion_rate:.1f}%")

    st.progress(
        completion_rate / 100,
        text=_t("dash_progress_text").format(rate=completion_rate),
    )

    if density == DensityLevel.DETAILED and by_status:

        status_df = pd.DataFrame(
            [
                {
                    _t("dash_status"): _t("dash_status_done"),
                    _t("dash_count_col"): completed,
                    _t("dash_percentage_col2"): f"{completed/total*100:.1f}%",
                },
                {
                    _t("dash_status"): _t("dash_status_progress"),
                    _t("dash_count_col"): in_progress,
                    _t("dash_percentage_col2"): (
                        f"{in_progress/total*100:.1f}%" if total > 0 else "0%"
                    ),
                },
                {
                    _t("dash_status"): _t("dash_status_pending"),
                    _t("dash_count_col"): pending,
                    _t("dash_percentage_col2"): (
                        f"{pending/total*100:.1f}%" if total > 0 else "0%"
                    ),
                },
            ]
        )
        st.dataframe(status_df, use_container_width=True, hide_index=True)


def _render_financial_summary_panel(
    density: DensityLevel = DensityLevel.STANDARD, full_width: bool = False, data: dict = None
):
    """Panel 4: 月度财务汇总 - Monthly financial summary."""
    st.markdown(f"### {_t('dash_finance_panel_title')}")

    if data is None:
        data = _get_dashboard_data()
    monthly = data.get("finance", {}).get("monthly", {})
    trend = data.get("finance", {}).get("trend", [])

    if _is_demo_mode():
        _render_demo_badge()
        demo_finance = _DEMO_DATA["finance"]
        income = demo_finance["income"]
        expense = demo_finance["expense"]
        net_profit = demo_finance["net_profit"]
        tax_est = demo_finance["tax_estimate"]
        if density == DensityLevel.COMPACT:
            st.markdown(
                f"**{_t('dash_income_expense_profit_demo').format(inc=income, exp=expense, net=net_profit)}**"
            )
            return
        col_inc, col_exp, col_profit = st.columns(3)
        with col_inc:
            st.metric(_t("dash_cumulative_income_demo"), f"¥{income:,}")
        with col_exp:
            st.metric(
                _t("dash_total_expense_demo"), f"¥{expense:,}", delta_color="inverse"
            )
        with col_profit:
            st.metric(
                _t("dash_net_profit_demo"),
                f"¥{net_profit:,}",
                delta=f"¥+{(net_profit - income * 0.75):,}",
            )
        if density != DensityLevel.COMPACT:
            st.caption(
                _t("dash_estimated_tax").format(
                    tax=tax_est, margin=(net_profit / income * 100)
                )
            )

            comparison = pd.DataFrame(
                {
                    _t("dash_category"): [
                        _t("dash_income_metric"),
                        _t("dash_expense_metric"),
                        _t("dash_profit_metric"),
                    ],
                    _t("dash_amount_col"): [income, expense, net_profit],
                }
            )
            st.bar_chart(
                comparison.set_index(_t("dash_category")), use_container_width=True
            )
        return

    income = monthly.get("income", 0)
    expense = monthly.get("expense", 0)
    profit = monthly.get("profit", 0)

    if income == 0 and expense == 0:
        st.info(f"💡 {_t('dash_no_monthly_finance')}")
        return

    if density == DensityLevel.COMPACT:
        st.markdown(
            f"**{_t('dash_income_expense_profit').format(inc=income, exp=expense, profit=profit)}**"
        )
        return

    col_inc, col_exp, col_profit = st.columns(3)
    with col_inc:
        st.metric(_t("dash_monthly_income"), f"¥{income:,.2f}")
    with col_exp:
        st.metric(_t("dash_monthly_expense"), f"¥{expense:,.2f}", delta_color="inverse")
    with col_profit:
        profit_delta = None
        if len(trend) >= 2:
            prev_profit = trend[-2].get("profit", 0)
            profit_delta = f"{profit - prev_profit:+,.2f}" if prev_profit != 0 else None
        st.metric(_t("dash_net_profit_metric"), f"¥{profit:,.2f}", profit_delta)

    if density == DensityLevel.DETAILED and (income > 0 or expense > 0):

        comparison = pd.DataFrame(
            {
                _t("dash_category"): [
                    _t("dash_income_metric"),
                    _t("dash_expense_metric"),
                ],
                _t("dash_amount_col"): [income, expense],
            }
        )
        st.bar_chart(
            comparison.set_index(_t("dash_category")), use_container_width=True
        )


def _render_activity_timeline_panel(
    density: DensityLevel = DensityLevel.STANDARD, full_width: bool = False, data: dict = None
):
    """Panel 5: 近期活动时间线 - Recent activity timeline."""
    st.markdown(f"### {_t('dash_timeline_panel_title')}")

    if data is None:
        data = _get_dashboard_data()
    logs = data.get("audit_log", [])

    if _is_demo_mode():
        _render_demo_badge()
        demo_events = _DEMO_DATA["timeline"]
        display_limit = len(demo_events)
        for idx, event in enumerate(demo_events):
            tag_color_map = {
                "green": "🟢",
                "blue": "🔵",
                "purple": "🟣",
                "gray": "⚪",
                "orange": "🟠",
                "red": "🔴",
            }
            color_dot = tag_color_map.get(event.get("color", "gray"), "⚪")
            if density == DensityLevel.COMPACT:
                st.markdown(
                    f"{event['icon']} `{event['time']}` — **{event['text'][:30]}** `[{event['tag']}]`"
                )
            else:
                st.markdown(
                    f"**{color_dot} {event['time']}** `{event['tag']}`  "
                    f"{event['text']}"
                )
        return

    if not logs:
        st.info(f"💡 {_t('dash_no_activity_records')}")
        return

    display_limit = (
        20
        if density == DensityLevel.DETAILED
        else (10 if density == DensityLevel.STANDARD else 5)
    )
    expanded_count = (
        5
        if density == DensityLevel.DETAILED
        else (3 if density == DensityLevel.STANDARD else 1)
    )

    from datetime import datetime as _dt

    for idx, record in enumerate(logs[:display_limit]):
        timestamp = record.get("timestamp", 0)
        op_type = record.get("operation_type", "unknown")
        skill_id = record.get("skill_id", "")
        status = record.get("status", "unknown")
        duration = record.get("duration_ms", 0)

        time_str = (
            _dt.fromtimestamp(timestamp).strftime("%m-%d %H:%M:%S") if timestamp else ""
        )

        status_emoji = {
            "success": "✅",
            "failed": "❌",
            "cancelled": "⚪",
        }.get(status, "📌")

        if density == DensityLevel.COMPACT:
            st.markdown(f"{status_emoji} `{op_type}` — {time_str} ({duration}ms)")
        else:
            with st.expander(
                f"{status_emoji} **{op_type}** — {time_str} ({duration}ms)",
                expanded=(idx < expanded_count),
            ):
                col_meta, col_detail = st.columns([1, 2])
                with col_meta:
                    st.caption(f"**{_t('dash_skill_label')}**: `{skill_id}`")
                    st.caption(f"**{_t('dash_status_label2')}**: `{status}`")
                    st.caption(f"**{_t('dash_duration_label')}**: {duration}ms")
                with col_detail:
                    input_sum = record.get("input_summary", "")
                    output_sum = record.get("output_summary", "")
                    if input_sum:
                        st.text(input_sum[:150])
                    if output_sum:
                        st.text(output_sum[:200])

    if len(logs) > display_limit:
        st.caption(_t("dash_showing_records").format(n=display_limit, total=len(logs)))


def _render_skill_usage_panel(
    density: DensityLevel = DensityLevel.STANDARD, full_width: bool = False, data: dict = None
):
    """Panel 6: 技能使用统计 - Skill usage statistics."""
    st.markdown(f"### {_t('dash_skills_panel_title')}")

    if data is None:
        data = _get_dashboard_data()
    logs = data.get("audit_log", [])

    if _is_demo_mode():
        _render_demo_badge()
        demo_skills = _DEMO_DATA["skills"]
        total_calls = sum(s["usage"] for s in demo_skills)
        if density == DensityLevel.COMPACT:
            top_skill = max(demo_skills, key=lambda x: x["usage"])
            st.markdown(
                f"**{_t('dash_total_calls_demo_fmt').format(n=total_calls, name=top_skill['name'], pct=top_skill['usage']/total_calls*100)}**"
            )
            return
        st.metric(_t("dash_total_calls_demo"), total_calls)

        skill_data = []
        for sk in demo_skills:
            pct = sk["usage"] / total_calls * 100 if total_calls > 0 else 0
            trend_emoji = (
                "📈" if "↑" in sk["trend"] else ("📉" if "↓" in sk["trend"] else "➡️")
            )
            skill_data.append(
                {
                    _t("dash_skill_col"): sk["name"],
                    _t("dash_call_count_col"): sk["usage"],
                    _t("dash_percentage_col"): f"{pct:.1f}%",
                    _t("dash_trend_col"): f"{trend_emoji} {sk['trend']}",
                }
            )
        df = pd.DataFrame(skill_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        if density == DensityLevel.DETAILED:
            chart_df = pd.DataFrame(
                {
                    _t("dash_skill_col"): [s["name"] for s in demo_skills],
                    _t("dash_call_count_col"): [s["usage"] for s in demo_skills],
                }
            )
            st.bar_chart(
                chart_df.set_index(_t("dash_skill_col")),
                use_container_width=True,
                horizontal=True,
            )
        return

    if not logs:
        st.info(f"💡 {_t('dash_no_skill_data')}")
        return

    skill_counts = Counter()
    for log in logs:
        skill_id = log.get("skill_id", "unknown")
        if skill_id:
            skill_counts[skill_id] += 1

    if not skill_counts:
        st.info(f"💡 {_t('dash_no_skill_records')}")
        return

    total_calls = sum(skill_counts.values())
    top_skills = skill_counts.most_common(10 if density == DensityLevel.DETAILED else 5)

    if density == DensityLevel.COMPACT:
        top_name, top_count = top_skills[0] if top_skills else ("-", 0)
        pct = top_count / total_calls * 100 if total_calls > 0 else 0
        st.markdown(
            f"**{_t('dash_total_calls_fmt').format(n=total_calls, name=top_name, pct=pct)}**"
        )
        return

    st.metric(_t("dash_total_calls_metric"), total_calls)

    skill_data = []
    for skill_name, count in top_skills:
        pct = count / total_calls * 100 if total_calls > 0 else 0
        skill_data.append(
            {
                _t("dash_skill_col"): skill_name,
                _t("dash_call_count_col"): count,
                _t("dash_percentage_col"): f"{pct:.1f}%",
            }
        )

    if skill_data:
        df = pd.DataFrame(skill_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        if density == DensityLevel.DETAILED:
            chart_df = pd.DataFrame(
                {
                    _t("dash_skill_col"): [s[0] for s in top_skills],
                    _t("dash_call_count_col"): [s[1] for s in top_skills],
                }
            )
            st.bar_chart(
                chart_df.set_index(_t("dash_skill_col")),
                use_container_width=True,
                horizontal=True,
            )
