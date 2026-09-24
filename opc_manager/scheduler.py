"""Local Scheduler for OPC-Agents v1.0.0 — 复发任务调度与本地持久化.

契约来源（不得偏离）:
  - docs/architecture/TDD_V1.0.0.md §5.1 组件 / §5.2 任务状态
  - docs/architecture/TDD_V1.0.0.md §5.3 执行流程 / §5.4 安全边界 / §5.5 持久化表

安全约束（TDD §5.4）:
  - v1.0.0 自动任务默认只生成报告或草稿：task_type 白名单 + handler 注册表双门
  - 不允许 scheduler 直接调用 SMTP、财务写入等底层接口绕过 Skill/Consensus 层
  - 任务参数限制大小和允许字段，禁止任意 Python 表达式或 shell 命令
  - 关键决策点保护：guard 否决或 guard 异常一律 fail-close（BLOCKED_BY_CONSENSUS）
  - 本模块不依赖 PromiseLink：PROMISELINK_ENABLED=false 时完整可用（TDD §8 回滚）
"""

import json
import logging
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

MAX_PARAMS_JSON_BYTES = 10240
MAX_AUTO_RETRIES = 1
DEFAULT_POLL_INTERVAL_SECONDS = 30.0
DEFAULT_TIMEZONE = "Asia/Shanghai"

# TDD §5.4：v1.0.0 自动任务默认只生成报告或草稿。邮件"发送"不在白名单，
# 自动发送外部邮件默认关闭，必须显式授权且每次执行受保护。
DEFAULT_AUTO_TASK_TYPES = frozenset(
    {"report_draft", "morning_brief", "email_draft", "local_summary"}
)

# 受限调度语法允许的 schedule_type（TDD §5.4 禁止任意表达式）
ALLOWED_SCHEDULE_TYPES = frozenset({"cron", "daily", "interval"})

_DB_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


def _utcnow() -> datetime:
    """当前 UTC 时间（naive 存储，消除字符串比较中 tz 后缀的错位风险）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.strftime(_DB_DATE_FORMAT)


def _from_iso(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    return datetime.strptime(raw, _DB_DATE_FORMAT)


class TaskState(str, Enum):
    """TDD §5.2 任务状态机。"""

    DRAFT = "DRAFT"
    ENABLED = "ENABLED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    RETRYING = "RETRYING"
    FAILED = "FAILED"
    BLOCKED_BY_CONSENSUS = "BLOCKED_BY_CONSENSUS"
    PAUSED = "PAUSED"
    DISABLED = "DISABLED"


class ScheduleParseError(ValueError):
    """调度表达式无法解析（fail-closed：任务不允许被创建）。"""


class DecisionVetoError(RuntimeError):
    """关键决策点 guard 主动否决。"""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# ---------------------------------------------------------------------------
# ScheduleParser — 受限调度语法（cron 5 字段 / daily HH:MM / interval:N 分钟）
# ---------------------------------------------------------------------------

_FIELD_RANGES = {
    "minute": (0, 59),
    "hour": (0, 23),
    "dom": (1, 31),
    "month": (1, 12),
    "dow": (0, 7),
}
_FIELD_ORDER = ("minute", "hour", "dom", "month", "dow")


@dataclass(frozen=True)
class _CronFields:
    minute: frozenset
    hour: frozenset
    dom: frozenset
    month: frozenset
    dow: frozenset


def _parse_field(name: str, raw: str) -> frozenset:
    low, high = _FIELD_RANGES[name]
    values: set = set()
    for part in raw.split(","):
        part = part.strip()
        step = 1
        if "/" in part:
            part, step_raw = part.split("/", 1)
            step = int(step_raw)
            if step < 1:
                raise ScheduleParseError(f"{name} step 必须 >= 1: {raw}")
        if part == "*":
            start, end = low, high
        elif "-" in part:
            start_raw, end_raw = part.split("-", 1)
            start, end = int(start_raw), int(end_raw)
        else:
            start = end = int(part)
        if start < low or end > high or start > end:
            raise ScheduleParseError(f"{name} 字段越界: {raw}")
        values.update(range(start, end + 1, step))
    if name == "dow" and 7 in values:
        # 标准 cron：7 视作周日(0)
        values.discard(7)
        values.add(0)
    return frozenset(values)


def _parse_cron(expression: str) -> _CronFields:
    parts = expression.split()
    if len(parts) != 5:
        raise ScheduleParseError(f"cron 表达式必须为 5 字段: {expression}")
    parsed = {name: _parse_field(name, raw) for name, raw in zip(_FIELD_ORDER, parts)}
    return _CronFields(**parsed)


def _day_matches(fields: _CronFields, day: datetime) -> bool:
    if day.month not in fields.month:
        return False
    dom_restricted = fields.dom != frozenset(range(1, 32))
    dow_restricted = fields.dow != frozenset(range(0, 7))
    dom_hit = day.day in fields.dom
    dow_hit = day.isoweekday() % 7 in fields.dow
    if dom_restricted and dow_restricted:
        # 标准 cron 语义：两者均受限时取 OR
        return dom_hit or dow_hit
    if dom_restricted:
        return dom_hit
    if dow_restricted:
        return dow_hit
    return True


class ScheduleParser:
    """受限调度语法解析器：只接受 cron 5 字段 / daily HH:MM / interval:N。"""

    @staticmethod
    def next_after(expression: str, after: datetime) -> datetime:
        """计算 after 之后的下一次触发时间（含时区信息，分钟精度）。"""
        expression = expression.strip()
        if expression.startswith("interval:"):
            minutes_raw = expression[len("interval:") :]
            try:
                minutes = int(minutes_raw)
            except ValueError as exc:
                raise ScheduleParseError(f"interval 语法: interval:N，收到 {expression}") from exc
            if minutes < 1:
                raise ScheduleParseError(f"interval 分钟数必须 >= 1: {expression}")
            return after + timedelta(minutes=minutes)

        if expression.startswith("daily "):
            time_raw = expression[len("daily ") :].strip()
            try:
                hour_raw, minute_raw = time_raw.split(":")
                hour, minute = int(hour_raw), int(minute_raw)
            except ValueError as exc:
                raise ScheduleParseError(f"daily 语法: daily HH:MM，收到 {expression}") from exc
            fields = _parse_cron(f"{minute} {hour} * * *")
        else:
            fields = _parse_cron(expression)

        candidate = (after + timedelta(minutes=1)).replace(second=0, microsecond=0)
        limit = candidate + timedelta(days=366)
        while candidate < limit:
            if _day_matches(fields, candidate):
                for hour in sorted(fields.hour):
                    for minute in sorted(fields.minute):
                        attempt = candidate.replace(hour=hour, minute=minute)
                        if attempt > after:
                            return attempt
            candidate = (candidate + timedelta(days=1)).replace(hour=0, minute=0)
        raise ScheduleParseError(f"一年内无触发时间: {expression}")


# ---------------------------------------------------------------------------
# 持久化 — 表结构严格对应 TDD §5.5
# ---------------------------------------------------------------------------


@dataclass
class ScheduledTask:
    id: str
    name: str
    schedule_type: str
    schedule_expression: str
    task_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = False
    timezone: str = DEFAULT_TIMEZONE
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.strftime(_DB_DATE_FORMAT)


def _from_iso(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    return datetime.strptime(raw, _DB_DATE_FORMAT)


class ScheduledTaskRepository:
    """SQLite 持久化：scheduled_tasks 表（TDD §5.5），重启后任务不丢。"""

    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._lock = threading.RLock()
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    schedule_type TEXT NOT NULL,
                    schedule_expression TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    timezone TEXT NOT NULL,
                    next_run_at TEXT,
                    last_run_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def create_task(
        self,
        name: str,
        schedule_type: str,
        schedule_expression: str,
        task_type: str,
        parameters: Optional[Dict[str, Any]] = None,
        timezone_name: str = DEFAULT_TIMEZONE,
        allowed_task_types: frozenset = DEFAULT_AUTO_TASK_TYPES,
    ) -> ScheduledTask:
        """创建任务（DRAFT, enabled=0）。白名单/参数大小/表达式/时区全部 fail-closed。"""
        if task_type not in allowed_task_types:
            raise ValueError(f"task_type 不在自动任务白名单内: {task_type}")
        if schedule_type not in ALLOWED_SCHEDULE_TYPES:
            raise ValueError(f"schedule_type 不允许: {schedule_type}")
        ZoneInfo(timezone_name)  # 非法时区直接抛出
        params = dict(parameters or {})
        try:
            params_json = json.dumps(params, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"parameters 必须可 JSON 序列化: {exc}") from exc
        if len(params_json.encode("utf-8")) > MAX_PARAMS_JSON_BYTES:
            raise ValueError(
                f"parameters_json 超过 {MAX_PARAMS_JSON_BYTES} 字节上限"
            )
        ScheduleParser.next_after(schedule_expression, datetime.now())  # 可解析性校验

        now_text = _iso(_utcnow())
        task = ScheduledTask(
            id=uuid.uuid4().hex,
            name=name,
            schedule_type=schedule_type,
            schedule_expression=schedule_expression,
            task_type=task_type,
            parameters=params,
            timezone=timezone_name,
            created_at=_from_iso(now_text),
        )
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO scheduled_tasks
                (id, name, schedule_type, schedule_expression, task_type,
                 parameters_json, enabled, timezone, next_run_at, last_run_at,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, NULL, NULL, ?, ?)
                """,
                (
                    task.id,
                    name,
                    schedule_type,
                    schedule_expression,
                    task_type,
                    params_json,
                    timezone_name,
                    now_text,
                    now_text,
                ),
            )
            self._conn.commit()
        return task

    def _row_to_task(self, row: tuple) -> ScheduledTask:
        (
            task_id,
            name,
            schedule_type,
            schedule_expression,
            task_type,
            params_json,
            enabled,
            timezone_name,
            next_run_at,
            last_run_at,
            created_at,
            updated_at,
        ) = row
        return ScheduledTask(
            id=task_id,
            name=name,
            schedule_type=schedule_type,
            schedule_expression=schedule_expression,
            task_type=task_type,
            parameters=json.loads(params_json),
            enabled=bool(enabled),
            timezone=timezone_name,
            next_run_at=_from_iso(next_run_at),
            last_run_at=_from_iso(last_run_at),
            created_at=_from_iso(created_at),
            updated_at=_from_iso(updated_at),
        )

    _SELECT_COLUMNS = (
        "id, name, schedule_type, schedule_expression, task_type, parameters_json, "
        "enabled, timezone, next_run_at, last_run_at, created_at, updated_at"
    )

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        with self._lock:
            row = self._conn.execute(
                f"SELECT {self._SELECT_COLUMNS} FROM scheduled_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
        return self._row_to_task(row) if row else None

    def list_tasks(self, enabled_only: bool = False) -> List[ScheduledTask]:
        query = f"SELECT {self._SELECT_COLUMNS} FROM scheduled_tasks"
        if enabled_only:
            query += " WHERE enabled = 1"
        with self._lock:
            rows = self._conn.execute(query).fetchall()
        return [self._row_to_task(row) for row in rows]

    def due_tasks(self, now: datetime) -> List[ScheduledTask]:
        """取到期任务：enabled=1 且 next_run_at <= now 且 next_run_at 非空。"""
        with self._lock:
            rows = self._conn.execute(
                f"""SELECT {self._SELECT_COLUMNS} FROM scheduled_tasks
                    WHERE enabled = 1 AND next_run_at IS NOT NULL AND next_run_at <= ?
                    ORDER BY next_run_at""",
                (_iso(now),),
            ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def _update_fields(self, task_id: str, updates: Dict[str, Any]) -> None:
        sets = ", ".join(f"{column} = ?" for column in updates)
        values = list(updates.values())
        values.append(task_id)
        with self._lock:
            self._conn.execute(
                f"UPDATE scheduled_tasks SET {sets} WHERE id = ?",
                tuple(values),
            )
            self._conn.commit()

    def enable_task(self, task_id: str) -> ScheduledTask:
        """DRAFT → ENABLED：校验表达式并计算首次 next_run_at。"""
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(f"任务不存在: {task_id}")
        tz = ZoneInfo(task.timezone)
        next_run = ScheduleParser.next_after(
            task.schedule_expression, datetime.now(tz=tz)
        )
        self._update_fields(
            task_id,
            {
                "enabled": 1,
                "next_run_at": _iso(_to_utc_naive(next_run)),
                "updated_at": _iso(_utcnow()),
            },
        )
        return self.get_task(task_id)  # type: ignore[return-value]

    def disable_task(self, task_id: str) -> None:
        self._update_fields(
            task_id,
            {"enabled": 0, "updated_at": _iso(_utcnow())},
        )

    def mark_run(
        self,
        task_id: str,
        next_run_at: Optional[datetime],
        state_enabled: bool,
    ) -> None:
        """tick 后回写：last_run_at=now，next_run_at，enabled（失败停用/阻塞挂起）。"""
        self._update_fields(
            task_id,
            {
                "last_run_at": _iso(_utcnow()),
                "next_run_at": _iso(next_run_at),
                "enabled": 1 if state_enabled else 0,
                "updated_at": _iso(_utcnow()),
            },
        )

    def delete_task(self, task_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM scheduled_tasks WHERE id = ?", (task_id,)
            )
            self._conn.commit()


class TaskExecutionRepository:
    """SQLite 持久化：task_executions 表（TDD §5.5），执行历史审计。"""

    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._lock = threading.RLock()
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_executions (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    result_ref TEXT,
                    error_code TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    consensus_status TEXT,
                    trace_id TEXT NOT NULL
                )
                """
            )
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def start_execution(self, task_id: str, trace_id: str) -> str:
        execution_id = uuid.uuid4().hex
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO task_executions
                (id, task_id, started_at, finished_at, status, result_ref,
                 error_code, retry_count, consensus_status, trace_id)
                VALUES (?, ?, ?, NULL, 'RUNNING', NULL, NULL, 0, NULL, ?)
                """,
                (execution_id, task_id, _iso(_utcnow()), trace_id),
            )
            self._conn.commit()
        return execution_id

    def finish_execution(
        self,
        execution_id: str,
        status: str,
        result_ref: Optional[str] = None,
        error_code: Optional[str] = None,
        retry_count: int = 0,
        consensus_status: Optional[str] = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                UPDATE task_executions
                SET finished_at = ?, status = ?, result_ref = ?, error_code = ?,
                    retry_count = ?, consensus_status = ?
                WHERE id = ?
                """,
                (
                    _iso(_utcnow()),
                    status,
                    result_ref,
                    error_code,
                    retry_count,
                    consensus_status,
                    execution_id,
                ),
            )
            self._conn.commit()

    def history_for_task(self, task_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT id, task_id, started_at, finished_at, status, result_ref,
                          error_code, retry_count, consensus_status, trace_id
                   FROM task_executions WHERE task_id = ?
                   ORDER BY started_at DESC LIMIT ?""",
                (task_id, limit),
            ).fetchall()
        keys = (
            "id",
            "task_id",
            "started_at",
            "finished_at",
            "status",
            "result_ref",
            "error_code",
            "retry_count",
            "consensus_status",
            "trace_id",
        )
        return [dict(zip(keys, row)) for row in rows]


# ---------------------------------------------------------------------------
# 执行器与调度服务 — TDD §5.3 执行流程（决策点保护 fail-close）
# ---------------------------------------------------------------------------

GuardCallable = Callable[[ScheduledTask], None]


def default_consensus_guard(task: ScheduledTask) -> None:
    """默认 guard：白名单内放行，白名单外否决（防御纵深，create 已前置校验）。"""
    if task.task_type not in DEFAULT_AUTO_TASK_TYPES:
        raise DecisionVetoError(f"task_type 不在自动任务白名单内: {task.task_type}")


@dataclass
class ExecutionOutcome:
    task_id: str
    state: TaskState
    attempts: int
    result_ref: Optional[str] = None
    error_code: Optional[str] = None


class ScheduledTaskRunner:
    """路由任务到注册 handler 并执行保护检查（TDD §5.1 ScheduledTaskRunner）。"""

    def __init__(
        self,
        task_repo: ScheduledTaskRepository,
        exec_repo: TaskExecutionRepository,
        consensus_guard: Optional[GuardCallable] = None,
    ):
        self._task_repo = task_repo
        self._exec_repo = exec_repo
        self._guard: GuardCallable = consensus_guard or default_consensus_guard
        self._handlers: Dict[str, Callable[[Dict[str, Any]], str]] = {}

    def register_handler(
        self, task_type: str, handler: Callable[[Dict[str, Any]], str]
    ) -> None:
        """注册 task_type → handler。handler 只接收 parameters dict，返回 result_ref。"""
        self._handlers[task_type] = handler

    def run_task(self, task: ScheduledTask) -> ExecutionOutcome:
        """执行单个任务：guard → (失败自动重试 MAX_AUTO_RETRIES 次) → 状态落库。"""
        trace_id = uuid.uuid4().hex
        try:
            self._guard(task)
        except DecisionVetoError as exc:
            return self._record_blocked(task, "VETOED", str(exc), trace_id)
        except Exception as exc:  # guard 异常一律 fail-close（TDD §5.3）
            return self._record_blocked(task, "GUARD_ERROR", type(exc).__name__, trace_id)

        handler = self._handlers.get(task.task_type)
        if handler is None:
            return self._record_blocked(
                task, "NO_HANDLER", f"未注册 handler: {task.task_type}", trace_id
            )

        attempts = 0
        last_error: Optional[str] = None
        while attempts <= MAX_AUTO_RETRIES:
            attempts += 1
            execution_id = self._exec_repo.start_execution(task.id, trace_id)
            try:
                result_ref = str(handler(task.parameters))[:255]
            except Exception as exc:
                last_error = type(exc).__name__
                status = (
                    TaskState.RETRYING
                    if attempts <= MAX_AUTO_RETRIES
                    else TaskState.FAILED
                )
                self._exec_repo.finish_execution(
                    execution_id,
                    status=status.value,
                    error_code=last_error,
                    retry_count=attempts - 1,
                )
                if status is TaskState.RETRYING:
                    continue
                return ExecutionOutcome(
                    task.id, TaskState.FAILED, attempts, error_code=last_error
                )
            self._exec_repo.finish_execution(
                execution_id,
                status=TaskState.SUCCEEDED.value,
                result_ref=result_ref,
                retry_count=attempts - 1,
            )
            return ExecutionOutcome(
                task.id, TaskState.SUCCEEDED, attempts, result_ref=result_ref
            )
        return ExecutionOutcome(
            task.id, TaskState.FAILED, attempts, error_code=last_error
        )

    def _record_blocked(
        self,
        task: ScheduledTask,
        consensus_status: str,
        detail: str,
        trace_id: str,
    ) -> ExecutionOutcome:
        execution_id = self._exec_repo.start_execution(task.id, trace_id)
        self._exec_repo.finish_execution(
            execution_id,
            status=TaskState.BLOCKED_BY_CONSENSUS.value,
            error_code=detail[:255],
            consensus_status=consensus_status,
        )
        logger.warning(
            "[Scheduler] 任务被阻塞 fail-close: task=%s reason=%s",
            task.name,
            consensus_status,
        )
        return ExecutionOutcome(
            task.id, TaskState.BLOCKED_BY_CONSENSUS, 1, error_code=detail[:255]
        )


class SchedulerService:
    """调度循环与任务生命周期（TDD §5.1 SchedulerService）。

    状态全部落在 SQLite：服务重启后 due_tasks 依然成立，任务不丢。
    """

    def __init__(
        self,
        task_repo: ScheduledTaskRepository,
        exec_repo: TaskExecutionRepository,
        runner: Optional[ScheduledTaskRunner] = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ):
        self._task_repo = task_repo
        self._exec_repo = exec_repo
        self._runner = runner or ScheduledTaskRunner(task_repo, exec_repo)
        self._poll_interval = poll_interval
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def register_handler(
        self, task_type: str, handler: Callable[[Dict[str, Any]], str]
    ) -> None:
        self._runner.register_handler(task_type, handler)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="opc-scheduler")
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop_event.wait(self._poll_interval):
            try:
                self.tick()
            except Exception as exc:  # 循环永不退出，单轮异常只记录
                logger.error("[Scheduler] tick 异常: %s", exc)

    def tick(self, now: Optional[datetime] = None) -> List[ExecutionOutcome]:
        """执行一轮到期任务并回写下次触发时间。测试可直接调用（无需起线程）。"""
        now = now or _utcnow()
        outcomes: List[ExecutionOutcome] = []
        for task in self._task_repo.due_tasks(now):
            outcome = self._runner.run_task(task)
            next_run = self._compute_next_run(task, now)
            state_enabled = outcome.state in (TaskState.SUCCEEDED, TaskState.RETRYING)
            if outcome.state is TaskState.BLOCKED_BY_CONSENSUS:
                # 阻塞即挂起：next_run_at 置空，等人工处理，避免每轮空转重试
                next_run = None
                state_enabled = True
            self._task_repo.mark_run(task.id, next_run, state_enabled)
            outcomes.append(outcome)
        return outcomes

    def _compute_next_run(self, task: ScheduledTask, now: datetime) -> Optional[datetime]:
        """now 为 naive UTC；在任务时区内计算下次触发后转回 naive UTC 存储。"""
        try:
            tz = ZoneInfo(task.timezone)
            base_local = now.replace(tzinfo=timezone.utc).astimezone(tz)
            next_run = ScheduleParser.next_after(task.schedule_expression, base_local)
            return _to_utc_naive(next_run)
        except Exception as exc:
            logger.error("[Scheduler] 计算下次触发失败 task=%s: %s", task.name, exc)
            return None
