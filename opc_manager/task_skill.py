import logging
import re
import time
from typing import Any, Dict, List, Optional

from opc_manager.data_manager import execute_query, execute_write, gen_id, init_db
from opc_manager.tool_system import AuditLogger
from opc_manager.utils import parse_date_from_text

logger = logging.getLogger(__name__)

PRIORITY_MAP = {"紧急": 0, "重要": 1, "普通": 2, "低": 3, "urgent": 0, "important": 1, "normal": 2, "low": 3}
PRIORITY_LABELS = {0: "P0紧急", 1: "P1重要", 2: "P2普通", 3: "P3低"}


def create_task(title: str, description: str = "", priority: int = 2,
                due_date: str = "", tags: str = "") -> Dict[str, Any]:
    if not title.strip():
        return {"success": False, "error": "待办标题不能为空"}
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    task_id = gen_id()
    try:
        execute_write(
            "INSERT INTO tasks (id,title,description,priority,status,due_date,tags,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (task_id, title, description, priority, "pending", due_date, tags, now),
        )
        AuditLogger.log("task_created", {"id": task_id, "title": title[:50]})
        if due_date:
            try:
                from opc_manager.calendar_skill import add_event
                add_event(title=f"任务截止: {title}", date=due_date, time_str="09:00")
            except Exception as e:
                logger.warning("auto sync calendar failed: %s", e)
        return {
            "success": True,
            "id": task_id,
            "message": f"待办已创建: {title} [{PRIORITY_LABELS.get(priority, 'P2普通')}]",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def complete_task(task_id: str = "", title_keyword: str = "") -> Dict[str, Any]:
    if not task_id and not title_keyword:
        return {"success": False, "error": "请提供待办ID或标题关键词"}
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        if task_id:
            rows = execute_query("SELECT id, title FROM tasks WHERE id=? AND status='pending'", (task_id,))
        else:
            rows = execute_query(
                "SELECT id, title FROM tasks WHERE title LIKE ? AND status='pending'",
                (f"%{title_keyword}%",),
            )
        if not rows:
            return {"success": False, "error": "未找到匹配的待办"}
        if len(rows) > 1:
            return {"success": False, "error": f"匹配到{len(rows)}个待办，请更精确指定", "matches": rows}
        r = rows[0]
        execute_write(
            "UPDATE tasks SET status='done', completed_at=? WHERE id=?",
            (now, r["id"]),
        )
        AuditLogger.log("task_completed", {"id": r["id"], "title": r["title"][:50]})
        return {"success": True, "message": f"待办已完成: {r['title']}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


_TASK_WHERE_COLUMNS = {"status", "due_date", "priority"}


def list_tasks(status: str = None, due_date: str = "", priority_max: int = -1,
               limit: int = 50) -> Dict[str, Any]:
    conditions = []
    params: list = []
    if status == "all":
        pass
    elif status == "done":
        conditions.append(("status", "=", "done"))
    elif status:
        conditions.append(("status", "=", status))
    else:
        conditions.append(("status", "NOT IN", "('done')"))
    if due_date:
        conditions.append(("due_date", "<=", due_date))
    if priority_max >= 0:
        conditions.append(("priority", "<=", priority_max))

    where_parts = []
    for col, op, val in conditions:
        if col not in _TASK_WHERE_COLUMNS:
            continue
        if op in ("IN", "NOT IN"):
            where_parts.append(f"{col} {op} {val}")
        else:
            where_parts.append(f"{col}{op}?")
            params.append(val)
    where = " AND ".join(where_parts)
    params.append(limit)
    rows = execute_query(
        f"SELECT * FROM tasks WHERE {where} ORDER BY priority ASC, due_date ASC LIMIT ?",
        tuple(params),
    )
    for r in rows:
        r["priority_label"] = PRIORITY_LABELS.get(r["priority"], "P2普通")
    return {"success": True, "tasks": rows, "count": len(rows)}


def get_today_tasks() -> Dict[str, Any]:
    today = time.strftime("%Y-%m-%d")
    rows = execute_query(
        "SELECT * FROM tasks WHERE status IN ('pending','in_progress') AND (due_date<=? OR due_date='') ORDER BY priority ASC",
        (today,),
    )
    for r in rows:
        r["priority_label"] = PRIORITY_LABELS.get(r["priority"], "P2普通")
    return {"success": True, "tasks": rows, "count": len(rows)}


def parse_priority_from_text(text: str) -> int:
    text_lower = text.lower()
    for keyword, level in PRIORITY_MAP.items():
        if keyword in text_lower:
            return level
    return 2


def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]:
    init_db()
    if any(kw in goal for kw in ["完成", "做了", "搞定了", "交了"]):
        keyword = goal
        for kw in ["完成", "搞定了", "做完了", "帮我完成", "标记完成", "做了", "交了", "帮我", "的"]:
            keyword = keyword.replace(kw, "")
        keyword = keyword.strip().strip("，。、的") or goal
        return complete_task(title_keyword=keyword)

    if any(kw in goal for kw in ["完成率", "统计", "任务统计"]):
        all_result = list_tasks(status="all")
        done_result = list_tasks(status="done")
        total = all_result.get("count", 0)
        done_count = done_result.get("count", 0)
        rate = round(done_count / total * 100, 1) if total > 0 else 0
        overdue_rows = execute_query(
            "SELECT COUNT(*) as cnt FROM tasks WHERE status NOT IN ('done','cancelled') AND due_date < ? AND due_date != ''",
            (time.strftime("%Y-%m-%d"),),
        )
        overdue_count = overdue_rows[0]["cnt"] if overdue_rows else 0
        return {
            "success": True,
            "total": total,
            "done": done_count,
            "overdue": overdue_count,
            "completion_rate": rate,
            "message": f"任务完成率: {done_count}/{total} ({rate}%)，逾期{overdue_count}项",
        }

    if any(kw in goal for kw in ["今天", "今日", "待办列表", "要做什么", "还没做"]):
        return get_today_tasks()

    if any(kw in goal for kw in ["查看", "列出", "有哪些"]):
        return list_tasks()

    priority = parse_priority_from_text(goal)
    due_date = parse_date_from_text(goal, default="")
    title = goal
    for kw in ["帮我记一下", "帮我创建", "帮我添加", "待办", "任务", "提醒我"]:
        title = title.replace(kw, "")
    title = title.strip().strip("，。、的") or goal
    return create_task(title, priority=priority, due_date=due_date)
