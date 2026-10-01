"""Local morning-brief aggregation and scheduled draft delivery."""

from __future__ import annotations

import atexit
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from opc_manager.audit_log import AuditLog
from opc_manager.data_manager import DATA_DIR, init_db
from opc_manager.scheduler import (
    ScheduledTaskRepository,
    SchedulerService,
    TaskExecutionRepository,
)
from opc_manager.settings import MorningBriefSettings, get_settings

logger = logging.getLogger(__name__)

_WORKSPACE_DIR = os.environ.get("OPC_WORKSPACE", os.getcwd())
_DELIVERABLES_DIR = Path(_WORKSPACE_DIR) / "deliverables"
_SCHEDULER_DB_PATH = str(Path(DATA_DIR) / "schedules" / "scheduler.db")
_RUNTIME_LOCK = threading.RLock()
_RUNTIME: Optional[SchedulerService] = None
_REPOSITORIES: Optional[tuple[ScheduledTaskRepository, TaskExecutionRepository]] = None


def _empty_data() -> Dict[str, Any]:
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "finance": {"monthly": {}, "trend": []},
        "crm": {"stats": {}, "silent": {"customers": [], "count": 0}},
        "tasks": {"items": [], "by_status": {}},
        "audit_log": [],
        "errors": [],
    }


def collect_morning_brief_data(
    scope: str = "default", limit: int = 10
) -> Dict[str, Any]:
    """Collect a local-first operating brief without Streamlit dependencies."""
    del scope
    init_db()
    data = _empty_data()

    try:
        from opc_manager.finance_skill import get_monthly_report, get_trend

        data["finance"] = {
            "monthly": get_monthly_report(),
            "trend": get_trend(6),
        }
    except Exception as exc:
        data["errors"].append(f"财务数据不可用：{type(exc).__name__}")
        logger.warning("[MorningBrief] finance aggregation failed: %s", exc)

    try:
        from opc_manager.crm_skill import get_customer_stats, get_silent_customers

        data["crm"] = {
            "stats": get_customer_stats(),
            "silent": get_silent_customers(),
        }
    except Exception as exc:
        data["errors"].append(f"CRM 数据不可用：{type(exc).__name__}")
        logger.warning("[MorningBrief] CRM aggregation failed: %s", exc)

    try:
        from opc_manager.task_skill import list_tasks

        tasks = list_tasks(status="all", limit=limit).get("tasks", [])
        by_status: Dict[str, int] = {}
        for task in tasks:
            status = task.get("status", "pending")
            by_status[status] = by_status.get(status, 0) + 1
        data["tasks"] = {"items": tasks, "by_status": by_status}
    except Exception as exc:
        data["errors"].append(f"待办数据不可用：{type(exc).__name__}")
        logger.warning("[MorningBrief] task aggregation failed: %s", exc)

    try:
        data["audit_log"] = AuditLog().query(limit=20)
    except Exception as exc:
        data["errors"].append(f"审计摘要不可用：{type(exc).__name__}")
        logger.warning("[MorningBrief] audit aggregation failed: %s", exc)

    return data


def render_morning_brief_markdown(data: Dict[str, Any]) -> str:
    """Render an auditable, human-readable local brief."""
    finance = data.get("finance", {}).get("monthly", {})
    crm = data.get("crm", {})
    silent = crm.get("silent", {})
    stats = crm.get("stats", {})
    tasks = data.get("tasks", {})

    lines = [
        "# 经营早报",
        "",
        f"生成时间：{data.get('generated_at', '')}",
        "",
        "## 经营概览",
        f"- 本月收入：¥{finance.get('income', 0):,.2f}",
        f"- 本月支出：¥{finance.get('expense', 0):,.2f}",
        f"- 本月利润：¥{finance.get('profit', 0):,.2f}",
        f"- 客户总数：{stats.get('total', 0)}",
        f"- 沉默客户：{silent.get('count', 0)}",
        "",
        "## 沉默客户跟进",
    ]

    customers = silent.get("customers", [])
    if customers:
        lines.extend(
            f"- {customer.get('name', '未命名')} · "
            f"{customer.get('company', '') or '未填写公司'}"
            for customer in customers[:10]
        )
    else:
        lines.append("- 当前没有需要跟进的沉默客户")

    lines.extend(["", "## 待办摘要"])
    by_status = tasks.get("by_status", {})
    if by_status:
        lines.extend(f"- {status}：{count} 个" for status, count in by_status.items())
    else:
        lines.append("- 当前没有待办记录")

    errors: List[str] = data.get("errors", [])
    if errors:
        lines.extend(["", "## 数据源状态"])
        lines.extend(f"- {error}" for error in errors)

    return "\n".join(lines) + "\n"


def save_morning_brief_draft(markdown: str) -> str:
    """Persist a scheduled brief as a deliverable visible to the operator."""
    _DELIVERABLES_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{datetime.now():%Y%m%d_%H%M%S}_morning_brief.md"
    path = _DELIVERABLES_DIR / filename
    path.write_text(markdown, encoding="utf-8")
    return str(path)


def handle_morning_brief(parameters: Dict[str, Any]) -> str:
    """Scheduler handler: aggregate data and save a local draft only."""
    started = datetime.now()
    data = collect_morning_brief_data(
        scope=str(parameters.get("scope", "default")),
        limit=int(parameters.get("limit", 10)),
    )
    path = save_morning_brief_draft(render_morning_brief_markdown(data))
    AuditLog().log(
        session_id="scheduler",
        operation_type="morning_brief_generated",
        skill_id="morning_brief",
        input_text=str(parameters),
        output_data=path,
        duration_ms=int((datetime.now() - started).total_seconds() * 1000),
        status="success" if not data["errors"] else "degraded",
        error_msg="; ".join(data["errors"]),
    )
    return path


def get_morning_brief_scheduler() -> SchedulerService:
    """Return the process-local scheduler and register the production handler."""
    global _RUNTIME, _REPOSITORIES
    with _RUNTIME_LOCK:
        if _RUNTIME is not None:
            return _RUNTIME
        Path(_SCHEDULER_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        task_repo = ScheduledTaskRepository(_SCHEDULER_DB_PATH)
        execution_repo = TaskExecutionRepository(_SCHEDULER_DB_PATH)
        service = SchedulerService(task_repo, execution_repo)
        service.register_handler("morning_brief", handle_morning_brief)
        service.start()
        _REPOSITORIES = (task_repo, execution_repo)
        _RUNTIME = service

        def shutdown() -> None:
            service.stop()
            task_repo.close()
            execution_repo.close()

        atexit.register(shutdown)
        return service


def sync_morning_brief_task(
    settings: Optional[MorningBriefSettings] = None,
) -> Any:
    """Synchronize the unique scheduler task from structured subscription settings."""
    settings = settings or get_settings().briefing
    get_morning_brief_scheduler()
    repositories = _REPOSITORIES
    if repositories is None:
        raise RuntimeError("早报调度器未初始化")
    task_repo, _ = repositories
    tasks = [
        task for task in task_repo.list_tasks() if task.task_type == "morning_brief"
    ]
    task = tasks[0] if tasks else None
    for duplicate in tasks[1:]:
        task_repo.disable_task(duplicate.id)

    schedule_expression = f"daily {settings.schedule_time}"
    parameters = {
        "scope": settings.scope,
        "delivery": "local_draft",
        "recipient_email": settings.recipient_email,
    }
    if task is None:
        task = task_repo.create_task(
            name="每日经营早报",
            schedule_type="daily",
            schedule_expression=schedule_expression,
            task_type="morning_brief",
            parameters=parameters,
            timezone_name=settings.timezone,
        )
    else:
        task = task_repo.update_task_config(
            task.id,
            schedule_expression=schedule_expression,
            timezone_name=settings.timezone,
            parameters=parameters,
        )

    if settings.enabled and not task.enabled:
        task = task_repo.enable_task(task.id)
    elif not settings.enabled and task.enabled:
        task_repo.disable_task(task.id)
        task = task_repo.get_task(task.id)
    return task


def ensure_morning_brief_task(
    schedule_expression: str = "daily 08:00",
    timezone_name: str = "Asia/Shanghai",
) -> Any:
    """Create and enable the single local daily brief task."""
    _, schedule_time = schedule_expression.split(" ", 1)
    return sync_morning_brief_task(
        MorningBriefSettings(
            enabled=True,
            schedule_time=schedule_time,
            timezone=timezone_name,
        )
    )


def get_morning_brief_status() -> Dict[str, Any]:
    get_morning_brief_scheduler()
    if _REPOSITORIES is None:
        return {"configured": False}
    task_repo, execution_repo = _REPOSITORIES
    tasks = [
        task for task in task_repo.list_tasks() if task.task_type == "morning_brief"
    ]
    if not tasks:
        return {"configured": False, "enabled": False}
    task = tasks[0]
    return {
        "configured": True,
        "enabled": task.enabled,
        "task_id": task.id,
        "next_run_at": task.next_run_at.isoformat() if task.next_run_at else "",
        "last_run_at": task.last_run_at.isoformat() if task.last_run_at else "",
        "history": execution_repo.history_for_task(task.id, limit=3),
    }


def run_morning_brief_now() -> Dict[str, Any]:
    try:
        path = handle_morning_brief({"scope": "default", "delivery": "local_draft"})
        return {"success": True, "path": path}
    except Exception as exc:
        logger.exception("[MorningBrief] manual generation failed")
        return {"success": False, "error": str(exc)}
