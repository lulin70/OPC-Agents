import logging
import re
import time
from typing import Any, Dict, List, Optional

from opc_manager.data_manager import execute_query, execute_write, gen_id, init_db
from opc_manager.tool_system import AuditLogger
from opc_manager.utils import parse_date_from_text

logger = logging.getLogger(__name__)


def add_event(title: str, date: str, time_str: str = "",
              duration_min: int = 60, description: str = "",
              reminder_min: int = 15, repeat: str = "") -> Dict[str, Any]:
    if not title.strip():
        return {"success": False, "error": "日程标题不能为空"}
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        return {"success": False, "error": f"日期格式无效: {date}，请用YYYY-MM-DD"}

    event_id = gen_id()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    try:
        execute_write(
            "INSERT INTO calendar_events (id,title,event_date,event_time,duration_min,description,repeat,reminder_min,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (event_id, title, date, time_str, duration_min, description, repeat, reminder_min, "active", now),
        )
    except Exception as e:
        logger.warning("calendar_skill.add_event write failed: %s", e)
        return {"success": False, "error": f"保存失败: {e}"}

    AuditLogger.log("calendar_event_created", {"id": event_id, "title": title, "date": date})

    return {
        "success": True,
        "id": event_id,
        "message": f"日程已创建: {title} ({date} {time_str})".strip(),
        "reminder": f"将在事件前{reminder_min}分钟提醒" if reminder_min > 0 else None,
    }


def get_day_schedule(date: str = "") -> Dict[str, Any]:
    if not date:
        date = time.strftime("%Y-%m-%d")

    try:
        rows = execute_query(
            "SELECT * FROM calendar_events WHERE event_date=? AND status!='cancelled' ORDER BY event_time",
            (date,),
        )
    except Exception as e:
        logger.warning("calendar_skill.get_day_schedule query failed: %s", e)
        return {"success": True, "date": date, "events": [], "count": 0}

    events = []
    for row in rows:
        e = dict(row)
        e["date"] = e["event_date"]
        e["time"] = e["event_time"]
        e["duration_min"] = e.get("duration_min", 60)
        e["description"] = e.get("description", "")
        e["repeat"] = e.get("repeat", "")
        e["status"] = e.get("status", "active")
        events.append(e)

    return {"success": True, "date": date, "events": events, "count": len(events)}


def get_week_schedule(start_date: str = "") -> Dict[str, Any]:
    from datetime import datetime, timedelta

    if not start_date:
        d = datetime.now()
        start_date = (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = (start + timedelta(days=6)).strftime("%Y-%m-%d")

    try:
        all_rows = execute_query(
            "SELECT * FROM calendar_events WHERE event_date BETWEEN ? AND ? AND status!='cancelled' ORDER BY event_date, event_time",
            (start_date, end),
        )
    except Exception as e:
        logger.warning("calendar_skill.get_week_schedule query failed: %s", e)
        return {"success": True, "start_date": start_date, "days": []}

    rows_by_date: Dict[str, list] = {}
    for row in all_rows:
        d_key = row["event_date"]
        rows_by_date.setdefault(d_key, []).append(row)

    days = []
    for i in range(7):
        day_str = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        day_rows = rows_by_date.get(day_str, [])
        events = []
        for row in day_rows:
            e = dict(row)
            e["date"] = e["event_date"]
            e["time"] = e["event_time"]
            e["duration_min"] = e.get("duration_min", 60)
            e["description"] = e.get("description", "")
            e["repeat"] = e.get("repeat", "")
            e["status"] = e.get("status", "active")
            events.append(e)
        days.append({"success": True, "date": day_str, "events": events, "count": len(events)})

    return {"success": True, "start_date": start_date, "days": days}


def get_month_schedule(year_month: str = "") -> Dict[str, Any]:
    from datetime import datetime, timedelta

    if not year_month:
        year_month = time.strftime("%Y-%m")

    try:
        start = datetime.strptime(year_month, "%Y-%m")
    except ValueError:
        return {"success": False, "error": f"月份格式无效: {year_month}，请用YYYY-MM"}

    if start.month == 12:
        end = datetime(start.year + 1, 1, 1)
    else:
        end = datetime(start.year, start.month + 1, 1)

    start_str = start.strftime("%Y-%m-%d")
    end_str = (end - timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        all_rows = execute_query(
            "SELECT * FROM calendar_events WHERE event_date BETWEEN ? AND ? AND status!='cancelled' ORDER BY event_date, event_time",
            (start_str, end_str),
        )
    except Exception as e:
        logger.warning("calendar_skill.get_month_schedule query failed: %s", e)
        return {"success": True, "year_month": year_month, "days": []}

    rows_by_date: Dict[str, list] = {}
    for row in all_rows:
        d_key = row["event_date"]
        rows_by_date.setdefault(d_key, []).append(row)

    days = []
    current = start
    while current < end:
        day_str = current.strftime("%Y-%m-%d")
        day_rows = rows_by_date.get(day_str, [])
        events = []
        for row in day_rows:
            e = dict(row)
            e["date"] = e["event_date"]
            e["time"] = e["event_time"]
            e["duration_min"] = e.get("duration_min", 60)
            e["description"] = e.get("description", "")
            e["repeat"] = e.get("repeat", "")
            e["status"] = e.get("status", "active")
            events.append(e)
        days.append({"date": day_str, "events": events, "count": len(events)})
        current += timedelta(days=1)

    return {"success": True, "year_month": year_month, "days": days, "total_events": len(all_rows)}


def cancel_event(event_id: str) -> Dict[str, Any]:
    rows = execute_query("SELECT * FROM calendar_events WHERE id=?", (event_id,))
    if not rows:
        return {"success": False, "error": f"未找到日程: {event_id}"}

    try:
        execute_write(
            "UPDATE calendar_events SET status='cancelled' WHERE id=?",
            (event_id,),
        )
    except Exception as e:
        logger.warning("calendar_skill.cancel_event update failed: %s", e)
        return {"success": False, "error": f"取消失败: {e}"}

    record = dict(rows[0])
    return {"success": True, "message": f"日程已取消: {record.get('title', event_id)}"}


def get_upcoming_reminders(minutes_ahead: int = 60) -> Dict[str, Any]:
    today = time.strftime("%Y-%m-%d")
    current_time = time.strftime("%H:%M")

    try:
        rows = execute_query(
            "SELECT * FROM calendar_events WHERE event_date=? AND event_time!='' AND status!='cancelled'",
            (today,),
        )
    except Exception as e:
        logger.warning("calendar_skill.get_upcoming_reminders query failed: %s", e)
        return {"success": True, "reminders": [], "count": 0}

    reminders = []
    for row in rows:
        e = dict(row)
        event_time = e.get("event_time", "")
        reminder_min = e.get("reminder_min", 15)
        try:
            h, m = map(int, event_time.split(":"))
            event_minutes = h * 60 + m
            now_h, now_m = map(int, current_time.split(":"))
            now_minutes = now_h * 60 + now_m
            diff = event_minutes - now_minutes
            if 0 <= diff <= minutes_ahead + reminder_min:
                e["date"] = e["event_date"]
                e["time"] = e["event_time"]
                e["duration_min"] = e.get("duration_min", 60)
                e["description"] = e.get("description", "")
                e["repeat"] = e.get("repeat", "")
                reminders.append({**e, "minutes_until": diff})
        except (ValueError, AttributeError):
            continue

    reminders.sort(key=lambda x: x.get("minutes_until", 9999))
    return {"success": True, "reminders": reminders, "count": len(reminders)}


def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]:
    init_db()
    if any(kw in goal for kw in ["今天", "今日", "有什么安排"]):
        return get_day_schedule()

    if any(kw in goal for kw in ["本周", "这周", "周安排"]):
        return get_week_schedule()

    if any(kw in goal for kw in ["本月", "这个月", "月安排", "月视图"]):
        return get_month_schedule()

    if any(kw in goal for kw in ["取消", "删除"]):
        return {"success": False, "error": "请提供日程ID来取消"}

    from opc_manager.utils import parse_date_from_text
    date = parse_date_from_text(goal)
    time_str = ""
    m = re.search(r'(\d{1,2})[：:点](\d{1,2})?分?', goal)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            time_str = f"{hour:02d}:{minute:02d}"
    if not time_str:
        m = re.search(r'(上午|下午|晚上|早上|中午)(\d{1,2})点?', goal)
        if m:
            hour = int(m.group(2))
            if m.group(1) in ("下午", "晚上") and hour < 12:
                hour += 12
            if 0 <= hour <= 23:
                time_str = f"{hour:02d}:00"
    title = goal
    for kw in ["帮我安排", "帮我加", "日程", "提醒我", "安排", "今天", "明天", "后天", "下周",
                "上午", "下午", "晚上", "早上", "中午"]:
        title = title.replace(kw, "")
    title = re.sub(r'\d{1,2}[：:点]\d{0,2}分?', '', title)
    title = title.strip().strip("，。、的") or goal

    return add_event(title, date, time_str=time_str)


def undo_add_event(event_id=None, **kwargs):
    init_db()
    rows = execute_query("SELECT * FROM calendar_events WHERE id=? AND status='active'", (event_id,)) if event_id else \
           execute_query("SELECT * FROM calendar_events WHERE status='active' ORDER BY created_at DESC LIMIT 1")
    if not rows:
        return {"success": False, "error": "未找到可撤销的日程"}
    target_id = event_id or rows[0]["id"]
    execute_write("UPDATE calendar_events SET status='cancelled' WHERE id=?", (target_id,))
    return {"success": True, "message": f"日程已撤销: {rows[0].get('title', target_id)}"}
