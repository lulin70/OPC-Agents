import logging
import time
from typing import Any, Dict, List, Optional

from opc_manager.data_manager import execute_query, execute_write, gen_id, init_db
from opc_manager.tool_system import AuditLogger

logger = logging.getLogger(__name__)

_DEFAULT_TAX_CALENDAR = [
    {"month": 1, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 2, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 3, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 4, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 4, "deadline": 30, "task": "企业所得税汇算清缴", "type": "企业所得税"},
    {"month": 5, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 6, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 7, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 8, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 9, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 10, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 10, "deadline": 31, "task": "个人所得税汇算清缴", "type": "个人所得税"},
    {"month": 11, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 12, "deadline": 15, "task": "增值税申报", "type": "增值税"},
]

try:
    from opc_manager.utils import load_json_data

    TAX_CALENDAR = load_json_data("data/knowledge/tax_calendar.json")
except Exception as e:
    logger.debug("[TaxReminderSkill] Load tax calendar failed: %s", e)
    TAX_CALENDAR = _DEFAULT_TAX_CALENDAR


def get_tax_calendar(month: int = 0) -> Dict[str, Any]:
    if month == 0:
        month = int(time.strftime("%m"))
    entries = [e for e in TAX_CALENDAR if e["month"] == month]
    upcoming = []
    for e in entries:
        deadline_str = f"{time.strftime('%Y')}-{month:02d}-{e['deadline']:02d}"
        remaining = (
            time.strptime(deadline_str, "%Y-%m-%d").tm_yday - time.localtime().tm_yday
        )
        upcoming.append(
            {**e, "deadline_date": deadline_str, "days_remaining": remaining}
        )

    next_month = month + 1 if month < 12 else 1
    next_entries = [e for e in TAX_CALENDAR if e["month"] == next_month]

    return {
        "success": True,
        "current_month": month,
        "this_month": upcoming,
        "next_month": next_entries,
    }


def check_upcoming_deadlines(days_ahead: int = 30) -> Dict[str, Any]:
    now = time.strftime("%Y-%m-%d")
    current_month = int(time.strftime("%m"))
    current_day = int(time.strftime("%d"))
    current_year = int(time.strftime("%Y"))

    upcoming = []
    for entry in TAX_CALENDAR:
        month = entry["month"]
        deadline_day = entry["deadline"]
        deadline_date = f"{current_year}-{month:02d}-{deadline_day:02d}"

        try:
            deadline_ts = time.mktime(time.strptime(deadline_date, "%Y-%m-%d"))
            now_ts = time.mktime(time.strptime(now, "%Y-%m-%d"))
            days_remaining = int((deadline_ts - now_ts) / 86400)
        except Exception as e:
            logger.debug("[TaxReminderSkill] Date parse failed: %s", e)
            continue

        if 0 <= days_remaining <= days_ahead:
            upcoming.append(
                {
                    **entry,
                    "deadline_date": deadline_date,
                    "days_remaining": days_remaining,
                    "urgency": _urgency_level(days_remaining),
                }
            )

    upcoming.sort(key=lambda x: x["days_remaining"])

    return {
        "success": True,
        "check_date": now,
        "days_ahead": days_ahead,
        "upcoming": upcoming,
        "count": len(upcoming),
    }


def create_reminder(
    task: str, deadline: str, tax_type: str = "增值税", amount_estimate: float = 0
) -> Dict[str, Any]:
    if not task.strip():
        return {"success": False, "error": "提醒任务不能为空"}
    if not _validate_date(deadline):
        return {"success": False, "error": f"日期格式无效: {deadline}"}

    reminder_id = gen_id()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    try:
        execute_write(
            "INSERT INTO tax_reminders (id,task,deadline,tax_type,amount_estimate,status,created_at) VALUES (?,?,?,?,?,?,?)",
            (reminder_id, task, deadline, tax_type, amount_estimate, "pending", now),
        )
    except Exception as e:
        logger.warning("tax_reminder_skill.create_reminder write failed: %s", e)
        return {"success": False, "error": f"保存失败: {e}"}

    AuditLogger.log("tax_reminder_created", {"id": reminder_id, "deadline": deadline})

    return {
        "success": True,
        "id": reminder_id,
        "message": f"税务提醒已创建: {task}，截止 {deadline}",
    }


def complete_reminder(reminder_id: str) -> Dict[str, Any]:
    rows = execute_query("SELECT * FROM tax_reminders WHERE id=?", (reminder_id,))
    if not rows:
        return {"success": False, "error": f"未找到提醒: {reminder_id}"}

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        execute_write(
            "UPDATE tax_reminders SET status='completed', completed_at=? WHERE id=?",
            (now, reminder_id),
        )
    except Exception as e:
        logger.warning("tax_reminder_skill.complete_reminder update failed: %s", e)
        return {"success": False, "error": f"更新失败: {e}"}

    record = dict(rows[0])
    AuditLogger.log("tax_reminder_completed", {"id": reminder_id})
    return {"success": True, "message": f"税务提醒已完成: {record['task']}"}


def list_reminders(status: str = "") -> Dict[str, Any]:
    try:
        if status:
            rows = execute_query(
                "SELECT * FROM tax_reminders WHERE status=? ORDER BY created_at DESC",
                (status,),
            )
        else:
            rows = execute_query("SELECT * FROM tax_reminders ORDER BY created_at DESC")
    except Exception as e:
        logger.warning("tax_reminder_skill.list_reminders query failed: %s", e)
        return {"success": True, "reminders": [], "count": 0}

    reminders = [dict(row) for row in rows]
    return {"success": True, "reminders": reminders, "count": len(reminders)}


def get_tax_checklist(month: int = 0) -> Dict[str, Any]:
    if month == 0:
        month = int(time.strftime("%m"))

    calendar_result = get_tax_calendar(month)
    deadlines = calendar_result.get("this_month", [])

    checklist = []
    for d in deadlines:
        checklist.append(
            {
                "task": d["task"],
                "deadline": d.get("deadline_date", f"每月{d['deadline']}日"),
                "type": d.get("type", ""),
                "status": "pending",
            }
        )

    existing = list_reminders(status="completed")
    completed_tasks = {r["task"] for r in existing.get("reminders", [])}
    for item in checklist:
        if item["task"] in completed_tasks:
            item["status"] = "completed"

    return {
        "success": True,
        "month": month,
        "checklist": checklist,
        "total": len(checklist),
        "completed": sum(1 for c in checklist if c["status"] == "completed"),
    }


def _urgency_level(days: int) -> str:
    if days <= 3:
        return "紧急"
    elif days <= 7:
        return "重要"
    elif days <= 15:
        return "关注"
    return "提前准备"


def _validate_date(date_str: str) -> bool:
    try:
        time.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]:
    init_db()
    if any(kw in goal for kw in ["即将到期", "快到期", "还有什么没报"]):
        return check_upcoming_deadlines()

    if any(kw in goal for kw in ["清单", "检查", "本月税务"]):
        return get_tax_checklist()

    if any(kw in goal for kw in ["完成", "已报", "已申报"]):
        return {"success": False, "error": "请提供提醒ID来标记完成"}

    if any(kw in goal for kw in ["列表", "查看"]):
        return list_reminders()

    return check_upcoming_deadlines()
