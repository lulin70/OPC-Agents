"""Dashboard page module for OPC-Agents frontend.

Contains all dashboard-related UI rendering functions:
- Main dashboard page with panel selector
- Data aggregation from backend modules
- 6 dashboard panels (income, client health, tasks, finance, timeline, skills)
"""

import streamlit as st
import logging
from datetime import datetime
from collections import Counter

logger = logging.getLogger(__name__)


def _render_dashboard_page():
    """Render modular Dashboard with selectable panels.

    Available panels (user can toggle on/off):
    1. 📈 Income Trend Chart (收入趋势图)
    2. 👥 Client Health Score (客户健康度)
    3. ✅ Task Completion Rate (任务完成率)
    4. 💰 Monthly Financial Summary (月度财务汇总)
    5. 📅 Recent Activity Timeline (近期活动时间线)
    6. ⏱️ Skill Usage Stats (技能使用统计)

    Default: Show Top 3 most useful panels
    """
    st.markdown("## 📈 数据仪表盘")

    # Panel selector at top
    ALL_PANELS = [
        ("income_trend", "📈 收入趋势图", "显示最近30天/按月的收入变化趋势"),
        ("client_health", "👥 客户健康度", "客户活跃度和互动频率分析"),
        ("task_completion", "✅ 任务完成率", "任务进度和完成情况统计"),
        ("financial_summary", "💰 月度财务汇总", "本月收入/支出/净利润概览"),
        ("activity_timeline", "📅 近期活动时间线", "最近20条操作记录时间线"),
        ("skill_usage", "⏱️ 技能使用统计", "各技能调用次数和使用频率"),
    ]

    DEFAULT_PANELS = ["income_trend", "client_health", "task_completion"]

    if "dashboard_selected_panels" not in st.session_state:
        st.session_state.dashboard_selected_panels = DEFAULT_PANELS

    with st.expander("⚙️ 面板设置（选择要显示的数据面板）", expanded=False):
        selected = []
        for panel_id, title, desc in ALL_PANELS:
            is_checked = st.checkbox(
                f"{title}",
                value=panel_id in st.session_state.dashboard_selected_panels,
                help=desc,
                key=f"dashboard_panel_{panel_id}",
            )
            if is_checked:
                selected.append(panel_id)

        if selected != st.session_state.dashboard_selected_panels:
            st.session_state.dashboard_selected_panels = selected
            st.rerun()

        col_select_all, col_deselect, _ = st.columns([1, 1, 2])
        with col_select_all:
            if st.button("全选", use_container_width=True):
                st.session_state.dashboard_selected_panels = [p[0] for p in ALL_PANELS]
                st.rerun()
        with col_deselect:
            if st.button("默认(Top 3)", use_container_width=True):
                st.session_state.dashboard_selected_panels = DEFAULT_PANELS
                st.rerun()

    st.divider()

    selected_panels = st.session_state.dashboard_selected_panels

    if not selected_panels:
        st.info("💡 请在上方选择至少一个数据面板")
        return

    # Render selected panels in grid layout (2-3 columns)
    panels_to_render = [(pid, title, desc) for pid, title, desc in ALL_PANELS if pid in selected_panels]

    for i in range(0, len(panels_to_render), 2):
        row_panels = panels_to_render[i:i+2]
        cols = st.columns(len(row_panels))

        for idx, (panel_id, panel_title, _) in enumerate(row_panels):
            with cols[idx]:
                try:
                    if panel_id == "income_trend":
                        _render_income_trend_panel()
                    elif panel_id == "client_health":
                        _render_client_health_panel()
                    elif panel_id == "task_completion":
                        _render_task_completion_panel()
                    elif panel_id == "financial_summary":
                        _render_financial_summary_panel()
                    elif panel_id == "activity_timeline":
                        _render_activity_timeline_panel()
                    elif panel_id == "skill_usage":
                        _render_skill_usage_panel()
                except Exception as e:
                    logger.error("[frontend] Dashboard panel %s error: %s", panel_id, e)
                    st.error(f"⚠️ 面板加载失败: {panel_title}")


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
        from opc_manager.crm_skill import get_customer_stats, get_silent_customers, list_customers
        data["crm"]["stats"] = get_customer_stats()
        data["crm"]["silent"] = get_silent_customers()
        try:
            data["crm"]["customers"] = list_customers(limit=10).get("customers", [])
        except Exception:
            pass
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


def _render_income_trend_panel():
    """Panel 1: 收入趋势图 - Income trend chart."""
    st.markdown("### 📈 收入趋势图")

    data = _get_dashboard_data()
    trend = data.get("finance", {}).get("trend", [])

    if not trend:
        st.info("💡 暂无财务数据。开始记录收入后这里会展示趋势图")
        return

    import pandas as pd

    df = pd.DataFrame(trend)
    chart_data = pd.DataFrame({
        "月份": [t.get("year_month", "") for t in trend],
        "收入": [t.get("income", 0) for t in trend],
        "支出": [t.get("expense", 0) for t in trend],
        "利润": [t.get("profit", 0) for t in trend],
    })

    st.line_chart(chart_data.set_index("月份"), use_container_width=True)

    if len(trend) >= 2:
        latest = trend[-1].get("profit", 0)
        previous = trend[-2].get("profit", 0)
        change_pct = ((latest - previous) / abs(previous) * 100) if previous != 0 else 0
        delta_color = "normal" if change_pct >= 0 else "inverse"
        st.metric(
            "本月利润",
            f"¥{latest:,.2f}",
            f"{change_pct:+.1f}%" if change_pct != 0 else None,
            delta_color=delta_color,
        )


def _render_client_health_panel():
    """Panel 2: 客户健康度 - Client health score."""
    st.markdown("### 👥 客户健康度")

    data = _get_dashboard_data()
    customers = data.get("crm", {}).get("customers", [])
    stats = data.get("crm", {}).get("stats", {})
    silent = data.get("crm", {}).get("silent", {})

    total = stats.get("total", 0)
    active = stats.get("active", 0)
    silent_count = silent.get("count", 0)

    if total == 0 and not customers:
        st.info("💡 暂无客户数据。添加客户后这里会展示健康度分析")
        return

    col_total, col_active, col_silent = st.columns(3)
    with col_total:
        st.metric("客户总数", total)
    with col_active:
        st.metric("活跃客户", active)
    with col_silent:
        st.metric("沉默客户", silent_count, delta_color="inverse")

    if customers:
        import pandas as pd
        customer_data = []
        for c in customers[:10]:
            name = c.get("name", "Unknown")
            status = c.get("status", "unknown")
            last_contact = c.get("last_contact", "")
            interactions = c.get("interactions", 0)

            # Health score logic
            from datetime import datetime as _dt, timedelta
            now = _dt.now()
            health_status = "🟢 健康"
            if last_contact:
                try:
                    last_date = _dt.strptime(last_contact[:10], "%Y-%m-%d") if len(last_contact) >= 10 else now
                    days_since = (now - last_date).days
                    if days_since > 30:
                        health_status = "🔴 需关注"
                    elif days_since > 14:
                        health_status = "🟡 一般"
                except Exception:
                    pass

            customer_data.append({
                "客户名称": name,
                "状态": status,
                "互动次数": interactions,
                "最近联系": last_contact[:10] if last_contact else "-",
                "健康度": health_status,
            })

        if customer_data:
            df = pd.DataFrame(customer_data)
            st.dataframe(df, use_container_width=True, hide_index=True)


def _render_task_completion_panel():
    """Panel 3: 任务完成率 - Task completion rate."""
    st.markdown("### ✅ 任务完成率")

    data = _get_dashboard_data()
    tasks = data.get("tasks", {}).get("list", [])
    by_status = data.get("tasks", {}).get("by_status", {})

    total = len(tasks)
    completed = by_status.get("completed", 0)
    in_progress = by_status.get("in_progress", 0)
    pending = by_status.get("pending", 0)

    if total == 0:
        st.info("💡 暂无任务数据。创建任务后这里会展示完成率")
        return

    completion_rate = (completed / total * 100) if total > 0 else 0

    col_total, col_done, col_rate = st.columns(3)
    with col_total:
        st.metric("总任务", total)
    with col_done:
        st.metric("已完成", completed)
    with col_rate:
        st.metric("完成率", f"{completion_rate:.1f}%")

    st.progress(completion_rate / 100, text=f"完成率 {completion_rate:.1f}%")

    # Status breakdown
    if by_status:
        import pandas as pd
        status_df = pd.DataFrame([
            {"状态": "已完成", "数量": completed, "占比": f"{completed/total*100:.1f}%"},
            {"状态": "进行中", "数量": in_progress, "占比": f"{in_progress/total*100:.1f}%" if total > 0 else "0%"},
            {"状态": "待处理", "数量": pending, "占比": f"{pending/total*100:.1f}%" if total > 0 else "0%"},
        ])
        st.dataframe(status_df, use_container_width=True, hide_index=True)


def _render_financial_summary_panel():
    """Panel 4: 月度财务汇总 - Monthly financial summary."""
    st.markdown("### 💰 月度财务汇总")

    data = _get_dashboard_data()
    monthly = data.get("finance", {}).get("monthly", {})
    trend = data.get("finance", {}).get("trend", [])

    income = monthly.get("income", 0)
    expense = monthly.get("expense", 0)
    profit = monthly.get("profit", 0)

    if income == 0 and expense == 0:
        st.info("💡 暂无本月财务数据。记录收支后这里会展示汇总")
        return

    col_inc, col_exp, col_profit = st.columns(3)
    with col_inc:
        st.metric("本月收入", f"¥{income:,.2f}")
    with col_exp:
        st.metric("本月支出", f"¥{expense:,.2f}", delta_color="inverse")
    with col_profit:
        profit_delta = None
        if len(trend) >= 2:
            prev_profit = trend[-2].get("profit", 0)
            profit_delta = f"{profit - prev_profit:+,.2f}" if prev_profit != 0 else None
        st.metric("净利润", f"¥{profit:,.2f}", profit_delta)

    # Simple bar chart comparing income vs expense
    if income > 0 or expense > 0:
        import pandas as pd
        comparison = pd.DataFrame({
            "类别": ["收入", "支出"],
            "金额": [income, expense],
        })
        st.bar_chart(comparison.set_index("类别"), use_container_width=True)


def _render_activity_timeline_panel():
    """Panel 5: 近期活动时间线 - Recent activity timeline."""
    st.markdown("### 📅 近期活动时间线")

    data = _get_dashboard_data()
    logs = data.get("audit_log", [])

    if not logs:
        st.info("💡 暂无操作记录。执行任务后日志会自动记录在这里")
        return

    from datetime import datetime as _dt

    for idx, record in enumerate(logs[:20]):
        timestamp = record.get("timestamp", 0)
        op_type = record.get("operation_type", "unknown")
        skill_id = record.get("skill_id", "")
        status = record.get("status", "unknown")
        duration = record.get("duration_ms", 0)

        time_str = _dt.fromtimestamp(timestamp).strftime("%m-%d %H:%M:%S") if timestamp else ""

        status_emoji = {
            "success": "✅",
            "failed": "❌",
            "cancelled": "⚪",
        }.get(status, "📌")

        with st.expander(f"{status_emoji} **{op_type}** — {time_str} ({duration}ms)", expanded=(idx < 3)):
            col_meta, col_detail = st.columns([1, 2])
            with col_meta:
                st.caption(f"**技能**: `{skill_id}`")
                st.caption(f"**状态**: `{status}`")
                st.caption(f"**耗时**: {duration}ms")
            with col_detail:
                input_sum = record.get("input_summary", "")
                output_sum = record.get("output_summary", "")
                if input_sum:
                    st.text(input_sum[:150])
                if output_sum:
                    st.text(output_sum[:200])

    if len(logs) > 20:
        st.caption(f"显示最近20条，共{len(logs)}条记录")


def _render_skill_usage_panel():
    """Panel 6: 技能使用统计 - Skill usage statistics."""
    st.markdown("### ⏱️ 技能使用统计")

    data = _get_dashboard_data()
    logs = data.get("audit_log", [])

    if not logs:
        st.info("💡 暂无技能使用数据。使用各功能后统计会自动更新")
        return

    skill_counts = Counter()
    for log in logs:
        skill_id = log.get("skill_id", "unknown")
        if skill_id:
            skill_counts[skill_id] += 1

    if not skill_counts:
        st.info("💡 暂无技能使用记录")
        return

    total_calls = sum(skill_counts.values())
    top_skills = skill_counts.most_common(10)

    st.metric("总调用次数", total_calls)

    import pandas as pd
    skill_data = []
    for skill_name, count in top_skills:
        pct = count / total_calls * 100 if total_calls > 0 else 0
        skill_data.append({
            "技能": skill_name,
            "调用次数": count,
            "占比": f"{pct:.1f}%",
        })

    if skill_data:
        df = pd.DataFrame(skill_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Horizontal bar chart
        chart_df = pd.DataFrame({
            "技能": [s[0] for s in top_skills],
            "调用次数": [s[1] for s in top_skills],
        })
        st.bar_chart(chart_df.set_index("技能"), use_container_width=True, horizontal=True)
