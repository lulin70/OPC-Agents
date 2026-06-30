import logging
import os
import time
from typing import Any, Dict

from opc_manager.data_manager import init_db, DATA_DIR
from opc_manager.finance_skill import get_monthly_report, get_trend
from opc_manager.crm_skill import get_customer_stats, get_silent_customers
from opc_manager.task_skill import list_tasks

logger = logging.getLogger(__name__)

REPORT_DIR = os.path.join(DATA_DIR, "reports")


def generate_weekly_report(week_note: str = "") -> Dict[str, Any]:
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    today = time.strftime("%Y-%m-%d")

    pending_result = list_tasks()
    done_result = list_tasks(status="done")
    done_tasks = done_result.get("tasks", [])
    pending_tasks = pending_result.get("tasks", [])

    crm_stats = get_customer_stats()
    silent = get_silent_customers()

    md = f"# 周报 {today}\n\n"
    md += "## 本周完成\n\n"
    if done_tasks:
        for t in done_tasks:
            md += f"- [x] {t['title']} [{t.get('priority_label', '')}]\n"
    else:
        md += "- （暂无已完成任务）\n"

    md += "\n## 待办事项\n\n"
    if pending_tasks:
        for t in pending_tasks:
            md += f"- [ ] {t['title']} [{t.get('priority_label', '')}]"
            if t.get("due_date"):
                md += f" — 截止 {t['due_date']}"
            md += "\n"
    else:
        md += "- （暂无待办）\n"

    md += "\n## 客户动态\n\n"
    md += f"- 客户总数: {crm_stats.get('total', 0)}\n"
    md += f"- 活跃客户: {crm_stats.get('active', 0)}\n"
    md += f"- 沉默客户: {silent.get('count', 0)}（超过30天未联系）\n"

    if week_note:
        md += f"\n## 备注\n\n{week_note}\n"

    md += f"\n---\n*由OPC-Agents自动生成 · {now[:10]}*\n"

    return _save_report("weekly", today, md)


def generate_monthly_report(year_month: str = "") -> Dict[str, Any]:
    if not year_month:
        year_month = time.strftime("%Y-%m")

    finance = get_monthly_report(year_month)
    crm_stats = get_customer_stats()
    silent = get_silent_customers()
    trend = get_trend(3)

    md = f"# 月度经营报告 {year_month}\n\n"
    md += "## 财务概况\n\n"
    if finance.get("success"):
        md += "| 指标 | 金额 | 环比变化 |\n"
        md += "|------|------|--------|\n"
        md += f"| 收入 | ¥{finance['income']:.2f} | {finance.get('income_change', 'N/A')} |\n"
        md += f"| 支出 | ¥{finance['expense']:.2f} | {finance.get('expense_change', 'N/A')} |\n"
        md += f"| 利润 | ¥{finance['profit']:.2f} | — |\n\n"

        if finance.get("income_by_category"):
            md += "### 收入构成\n\n"
            for cat, amt in finance["income_by_category"].items():
                md += f"- {cat}: ¥{amt:.2f}\n"
            md += "\n"

        if finance.get("expense_by_category"):
            md += "### 支出构成\n\n"
            for cat, amt in finance["expense_by_category"].items():
                md += f"- {cat}: ¥{amt:.2f}\n"
            md += "\n"

    md += "## 客户概况\n\n"
    md += f"- 客户总数: {crm_stats.get('total', 0)}\n"
    md += (
        f"- 活跃: {crm_stats.get('active', 0)} | "
        f"潜在: {crm_stats.get('potential', 0)} | "
        f"沉默: {crm_stats.get('silent', 0)}\n"
    )
    md += f"- 需跟进: {silent.get('count', 0)}个客户超过30天未联系\n\n"

    md += "## 近3月趋势\n\n"
    md += "| 月份 | 收入 | 支出 | 利润 |\n"
    md += "|------|------|------|------|\n"
    for t in trend:
        md += (
            f"| {t.get('year_month', '')} | ¥{t.get('income', 0):.2f} | "
            f"¥{t.get('expense', 0):.2f} | ¥{t.get('profit', 0):.2f} |\n"
        )

    pending_tasks = list_tasks()
    done_tasks = list_tasks(status="done")
    pending_count = pending_tasks.get("count", 0)
    done_count = done_tasks.get("count", 0)
    overdue_tasks = [
        t
        for t in pending_tasks.get("tasks", [])
        if t.get("due_date") and t["due_date"] < time.strftime("%Y-%m-%d")
    ]
    overdue_count = len(overdue_tasks)

    md += "\n## 任务概况\n\n"
    md += f"- 待办数: {pending_count}\n"
    md += f"- 完成数: {done_count}\n"
    md += f"- 逾期数: {overdue_count}\n\n"

    md += f"\n---\n*由OPC-Agents自动生成 · {time.strftime('%Y-%m-%d')}*\n"

    return _save_report("monthly", year_month, md)


def generate_annual_report(year: str = "") -> Dict[str, Any]:
    if not year:
        year = time.strftime("%Y")

    from opc_manager.data_manager import execute_query

    rows = execute_query(
        "SELECT substr(date,1,7) as ym, type, SUM(amount) as total "
        "FROM finance_records WHERE date LIKE ? GROUP BY ym, type ORDER BY ym",
        (f"{year}%",),
    )
    monthly_data = {}
    for r in rows:
        ym = r["ym"]
        if ym not in monthly_data:
            monthly_data[ym] = {
                "year_month": ym,
                "income": 0.0,
                "expense": 0.0,
                "profit": 0.0,
            }
        if r["type"] == "income":
            monthly_data[ym]["income"] = round(r["total"], 2)
        else:
            monthly_data[ym]["expense"] = round(r["total"], 2)
    for ym in monthly_data:
        m = monthly_data[ym]
        m["profit"] = round(m["income"] - m["expense"], 2)

    monthly_list = sorted(monthly_data.values(), key=lambda x: x["year_month"])
    annual_income = sum(m["income"] for m in monthly_list)
    annual_expense = sum(m["expense"] for m in monthly_list)
    annual_profit = annual_income - annual_expense
    crm_stats = get_customer_stats()

    md = f"# 年度经营报告 {year}\n\n"
    md += "## 年度财务\n\n"
    md += f"- 年度收入: ¥{annual_income:.2f}\n"
    md += f"- 年度支出: ¥{annual_expense:.2f}\n"
    md += f"- 年度利润: ¥{annual_profit:.2f}\n"
    md += f"- 利润率: {(annual_profit/annual_income*100) if annual_income else 0:.1f}%\n\n"

    if monthly_list:
        md += "### 月度趋势\n\n"
        md += "| 月份 | 收入 | 支出 | 利润 |\n"
        md += "|------|------|------|------|\n"
        for t in monthly_list:
            md += f"| {t['year_month']} | ¥{t['income']:.2f} | ¥{t['expense']:.2f} | ¥{t['profit']:.2f} |\n"
        md += "\n"

    md += "## 客户概况\n\n"
    md += f"- 客户总数: {crm_stats.get('total', 0)}\n"
    md += f"- 活跃: {crm_stats.get('active', 0)} | 流失: {crm_stats.get('lost', 0)}\n\n"

    deal_rows = execute_query(
        "SELECT COUNT(*) as cnt, COALESCE(SUM(amount),0) as total_amount "
        "FROM deals WHERE status='closed_won' AND date LIKE ?",
        (f"{year}%",),
    )
    deal_count = deal_rows[0]["cnt"] if deal_rows else 0
    deal_total = deal_rows[0]["total_amount"] if deal_rows else 0
    deal_customer_rows = execute_query(
        "SELECT COUNT(DISTINCT customer_id) as cnt FROM deals WHERE status='closed_won' AND date LIKE ?",
        (f"{year}%",),
    )
    deal_customer_count = deal_customer_rows[0]["cnt"] if deal_customer_rows else 0

    md += "## 成交概况\n\n"
    md += f"- 总成交额: ¥{deal_total:.2f}\n"
    md += f"- 成交客户数: {deal_customer_count}\n"
    md += f"- 成交笔数: {deal_count}\n\n"

    md += f"---\n*由OPC-Agents自动生成 · {time.strftime('%Y-%m-%d')}*\n"

    return _save_report("annual", year, md)


def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]:
    init_db()
    if any(kw in goal for kw in ["年报", "年度", "年总结", "年报告"]):
        return generate_annual_report()
    if any(
        kw in goal
        for kw in [
            "月报",
            "月度",
            "月总结",
            "月报告",
            "经营报告",
            "经营分析",
            "经营状况",
            "业务报告",
        ]
    ):
        return generate_monthly_report()
    return generate_weekly_report()


def _save_report(report_type: str, period: str, content: str) -> Dict[str, Any]:
    os.makedirs(REPORT_DIR, exist_ok=True)
    filename = f"{report_type}_{period.replace('-', '')}.md"
    filepath = os.path.join(REPORT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return {
        "success": True,
        "report_type": report_type,
        "period": period,
        "filepath": filepath,
        "markdown": content,
        "message": f"{report_type}报告已生成: {filepath}",
    }
