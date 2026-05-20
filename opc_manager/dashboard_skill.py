import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from opc_manager.data_manager import execute_query, init_db, DATA_DIR
from opc_manager.finance_skill import get_monthly_report, get_trend
from opc_manager.crm_skill import get_customer_stats, get_silent_customers
from opc_manager.task_skill import list_tasks
from opc_manager.tool_system import AuditLogger

logger = logging.getLogger(__name__)

DASHBOARD_DIR = os.path.join(DATA_DIR, "dashboard")


def get_overview() -> Dict[str, Any]:
    init_db()
    now = time.strftime("%Y-%m-%d")
    year_month = time.strftime("%Y-%m")

    finance = get_monthly_report(year_month)
    crm_stats = get_customer_stats()
    silent = get_silent_customers()
    tasks_result = list_tasks(status="all")

    pending_tasks = [
        t
        for t in tasks_result.get("tasks", [])
        if t.get("status") in ("pending", "in_progress")
    ]
    overdue_tasks = [
        t for t in pending_tasks if t.get("due_date") and t["due_date"] < now
    ]

    return {
        "success": True,
        "date": now,
        "finance": {
            "month_income": finance.get("income", 0),
            "month_expense": finance.get("expense", 0),
            "month_profit": finance.get("profit", 0),
        },
        "crm": {
            "total_customers": crm_stats.get("total", 0),
            "active_customers": crm_stats.get("active", 0),
            "silent_customers": silent.get("count", 0),
        },
        "tasks": {
            "pending": len(pending_tasks),
            "overdue": len(overdue_tasks),
        },
    }


def get_finance_dashboard(months: int = 6) -> Dict[str, Any]:
    init_db()
    trend = get_trend(months)

    total_income = sum(t.get("income", 0) for t in trend)
    total_expense = sum(t.get("expense", 0) for t in trend)
    avg_monthly_income = total_income / max(months, 1)
    avg_monthly_expense = total_expense / max(months, 1)

    best_month = max(trend, key=lambda x: x.get("profit", -999999)) if trend else None
    worst_month = min(trend, key=lambda x: x.get("profit", 999999)) if trend else None

    return {
        "success": True,
        "period": f"近{months}个月",
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "total_profit": round(total_income - total_expense, 2),
        "avg_monthly_income": round(avg_monthly_income, 2),
        "avg_monthly_expense": round(avg_monthly_expense, 2),
        "best_month": best_month,
        "worst_month": worst_month,
        "trend": trend,
    }


def get_crm_dashboard() -> Dict[str, Any]:
    init_db()
    stats = get_customer_stats()
    silent = get_silent_customers()

    return {
        "success": True,
        "total": stats.get("total", 0),
        "by_status": {
            "potential": stats.get("potential", 0),
            "first_deal": stats.get("first_deal", 0),
            "active": stats.get("active", 0),
            "silent": stats.get("silent", 0),
            "lost": stats.get("lost", 0),
        },
        "silent_customers": silent.get("count", 0),
        "silent_list": silent.get("customers", [])[:5],
    }


def get_task_dashboard() -> Dict[str, Any]:
    init_db()
    tasks_result = list_tasks(status="all")
    now = time.strftime("%Y-%m-%d")

    all_tasks = tasks_result.get("tasks", [])
    by_status = {}
    by_priority = {}
    overdue = []

    for t in all_tasks:
        status = t.get("status", "pending")
        by_status[status] = by_status.get(status, 0) + 1
        priority = t.get("priority", 2)
        by_priority[f"P{priority}"] = by_priority.get(f"P{priority}", 0) + 1
        if (
            status in ("pending", "in_progress")
            and t.get("due_date")
            and t["due_date"] < now
        ):
            overdue.append(t)

    return {
        "success": True,
        "total": len(all_tasks),
        "by_status": by_status,
        "by_priority": by_priority,
        "overdue_count": len(overdue),
        "overdue_tasks": overdue[:5],
    }


def generate_dashboard_report() -> Dict[str, Any]:
    overview = get_overview()
    finance = get_finance_dashboard(6)
    crm = get_crm_dashboard()
    tasks = get_task_dashboard()

    md = "# 经营数据看板\n\n"
    md += f"**日期**: {time.strftime('%Y-%m-%d')}\n\n"

    md += "## 概览\n\n"
    f_data = overview.get("finance", {})
    c_data = overview.get("crm", {})
    t_data = overview.get("tasks", {})
    md += f"| 指标 | 数值 |\n|------|------|\n"
    md += f"| 本月收入 | ¥{f_data.get('month_income', 0):.2f} |\n"
    md += f"| 本月支出 | ¥{f_data.get('month_expense', 0):.2f} |\n"
    md += f"| 本月利润 | ¥{f_data.get('month_profit', 0):.2f} |\n"
    md += f"| 客户总数 | {c_data.get('total_customers', 0)} |\n"
    md += f"| 活跃客户 | {c_data.get('active_customers', 0)} |\n"
    md += f"| 沉默客户 | {c_data.get('silent_customers', 0)} |\n"
    md += f"| 待办任务 | {t_data.get('pending', 0)} |\n"
    md += f"| 逾期任务 | {t_data.get('overdue', 0)} |\n\n"

    md += "## 财务趋势\n\n"
    md += "| 月份 | 收入 | 支出 | 利润 |\n|------|------|------|------|\n"
    for t in finance.get("trend", []):
        md += f"| {t.get('year_month', '')} | ¥{t.get('income', 0):.2f} | ¥{t.get('expense', 0):.2f} | ¥{t.get('profit', 0):.2f} |\n"

    if tasks.get("overdue_count", 0) > 0:
        md += "\n## ⚠️ 逾期任务\n\n"
        for t in tasks.get("overdue_tasks", []):
            md += f"- {t['title']} (截止 {t.get('due_date', '')})\n"

    md += f"\n---\n*由OPC-Agents自动生成 · {time.strftime('%Y-%m-%d')}*\n"

    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    filepath = os.path.join(DASHBOARD_DIR, f"dashboard_{time.strftime('%Y%m%d')}.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)

    AuditLogger.log("dashboard_generated", {"filepath": filepath})

    return {
        "success": True,
        "filepath": filepath,
        "markdown": md,
        "message": "数据看板已生成",
    }


def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]:
    init_db()
    if any(kw in goal for kw in ["财务", "收入", "支出", "利润"]):
        return get_finance_dashboard()

    if any(kw in goal for kw in ["客户", "CRM"]):
        return get_crm_dashboard()

    if any(kw in goal for kw in ["任务", "待办"]):
        return get_task_dashboard()

    if any(kw in goal for kw in ["报告", "生成", "导出"]):
        return generate_dashboard_report()

    return get_overview()
