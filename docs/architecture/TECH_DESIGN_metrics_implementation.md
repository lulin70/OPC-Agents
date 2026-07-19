# 数据采集埋点实现技术设计（v0.5.0 P3）

**版本**: v0.5.0-draft
**日期**: 2026-07-19
**状态**: 7-Role 共识
**决策者**: Architect + Coder
**关联文档**: [ADR-004-metrics-collection-design.md](./ADR-004-metrics-collection-design.md) / [ROADMAP_v0.5.0.md](../ROADMAP_v0.5.0.md) §OKR-2

---

## 1. 背景

ADR-004 已确立"新增 `opc_manager/metrics_collector.py` 作为统一埋点入口"的架构决策，承载 5 大商业指标 + 3 大体验指标的采集、本地持久化与可选脱敏上报。本文档在 ADR-004 框架下细化实现方案，覆盖：MetricsCollector 类完整签名与伪代码；与 OnboardingManager / FlywheelTracker / SkillExecutors / ErrorHandler / FeedbackAPI 五个现有组件的集成点与代码片段；DB 迁移 v7 → v8 方案；数据脱敏规则、配置项、测试策略与工作量估算。

实现遵循 ADR-004 §2.4 四大原则：统一入口、本地优先、松耦合、可扩展。所有埋点写入必须经 MetricsCollector，禁止业务模块直写 SQLite。

---

## 2. MetricsCollector 类设计

新增文件：`opc_manager/metrics_collector.py`。依赖均复用标准库（`sqlite3` / `threading` / `uuid` / `json` / `hashlib` / `logging` / `datetime` / `secrets`），不引入新包。异常类定义 `MetricsCollectionError`（参数校验失败）与 `MetricsDBError(MetricsCollectionError)`（SQLite 写入失败），见下方伪代码。

### 2.1 类签名伪代码

伪代码遵循 `audit_log.py` 与 `data_manager.py` 既有风格（类型注解 + logging + threading.Lock + 单例）。受篇幅限制，仅完整展示 `record_activation` / `record_experience` / `export_anonymized` 三个代表性方法，其余 4 个 `record_xxx` 方法结构同构（参数校验 → 生成 UUID → `_write`），签名与边界条件见下表。

```python
"""
MetricsCollector — v0.5.0 统一埋点入口

设计参考: audit_log.py (threading.Lock + WAL + 单例),
         data_manager.py (SQLite 连接 + 迁移机制 + _meta 表)
"""
import hashlib, json, logging, os, secrets, sqlite3, threading, uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
_METADATA_MAX_BYTES = 4096  # ADR-004 §6 风险表


class MetricsCollectionError(Exception):
    """指标采集基础异常（参数校验失败、字段非法等）"""


class MetricsDBError(MetricsCollectionError):
    """SQLite 写入或迁移失败"""


class MetricsCollector:
    """统一埋点入口，所有指标采集经此写入 SQLite（WAL 模式）。

    线程安全：通过 self._lock 串行化所有 write 路径。
    读取路径不阻塞写入（HARD_CONSTRAINTS REL-4-01）。
    """

    _instance: Optional["MetricsCollector"] = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: Optional[str] = None) -> None:
        if getattr(self, "_initialized", False):
            return
        self._db_path = db_path or self._resolve_db_path()
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._salt = self._resolve_anonymization_salt()
        self._connect_db()
        self._ensure_tables()
        self._initialized = True

    # ----- 公共 API: 6 个 record_xxx 方法 -----

    def record_activation(
        self, user_id: str, activated: bool, days_since_invite: int,
        task_count_7d: int, metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """记录激活事件（OnboardingManager COMPLETED + 7 日 ≥3 次使用）。
        Returns: record_id (UUID v4)。Raises: MetricsCollectionError / MetricsDBError。"""
        if not user_id:
            raise MetricsCollectionError("user_id is required")
        if task_count_7d < 0:
            raise MetricsCollectionError("task_count_7d must be >= 0")
        record_id = str(uuid.uuid4())
        self._write("metrics_activation", {
            "record_id": record_id, "user_id": user_id,
            "activated": 1 if activated else 0,
            "days_since_invite": int(days_since_invite),
            "task_count_7d": int(task_count_7d),
            "metadata": self._serialize_metadata(metadata),
            "created_at": self._now_iso(),
        })
        return record_id

    def record_upgrade(
        self, user_id: str, from_tier: str, to_tier: str,
        trigger: str, metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """记录版本升级事件。校验: from_tier ∈ {basic,trial}, to_tier ∈ {pro,enterprise}。"""
        # 校验略，结构与 record_activation 同构：raise MetricsCollectionError → uuid → _write
        ...

    def record_flywheel(
        self, user_id: str, level: int, action: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """记录飞轮级别变化。校验: level 1-4, action ∈ {enter_level, complete_cycle}。"""
        ...

    def record_payment(
        self, user_id: str, plan: str, amount_cents: int,
        currency: str = "CNY", metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """记录付费转化事件。校验: plan ∈ {monthly,yearly}, amount_cents >= 0。"""
        ...

    def record_nps(
        self, user_id: str, score: int, channel: str,
        feedback: str = "", metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """记录 NPS 评分。校验: score 0-10, channel ∈ {weekly_survey, post_task}。"""
        ...

    def record_experience(
        self, user_id: str, metric: str, score: float, channel: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """记录 3 大体验指标评分（dialogue_naturalness /
        result_satisfaction / proactive_service），score 0.0-5.0。"""
        valid_metrics = {"dialogue_naturalness", "result_satisfaction", "proactive_service"}
        if metric not in valid_metrics:
            raise MetricsCollectionError(f"invalid metric: {metric}")
        if not 0.0 <= score <= 5.0:
            raise MetricsCollectionError(f"score must be 0.0-5.0, got {score}")
        if channel not in {"post_dialogue", "post_task", "weekly_survey", "error"}:
            raise MetricsCollectionError(f"invalid channel: {channel}")
        record_id = str(uuid.uuid4())
        self._write("metrics_experience", {
            "record_id": record_id, "user_id": user_id,
            "metric": metric, "score": float(score), "channel": channel,
            "metadata": self._serialize_metadata(metadata),
            "created_at": self._now_iso(),
        })
        return record_id

    # ----- 脱敏导出 -----

    def export_anonymized(self, since_date: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """导出脱敏数据用于用户主动上报：移除 user_id/business_id，record_id 哈希化。"""
        since_clause = "WHERE created_at >= ?" if since_date else ""
        params = (since_date,) if since_date else ()
        result = {}
        for table in ("metrics_activation", "metrics_upgrade", "metrics_flywheel",
                      "metrics_payment", "metrics_nps", "metrics_experience"):
            rows = self._conn.execute(
                f"SELECT * FROM {table} {since_clause} ORDER BY created_at ASC", params
            ).fetchall()
            result[table] = [self._sanitize_for_export(dict(r)) for r in rows]
        return result

    # ----- 私有方法 -----

    def _connect_db(self) -> None:
        """初始化 SQLite 连接（WAL + busy_timeout，参考 data_manager._get_conn）。"""
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._conn = sqlite3.connect(
            self._db_path, timeout=5.0, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")

    def _ensure_tables(self) -> None:
        """幂等建表（DDL 见 §5.3 METRICS_DDL_V8）。"""
        from opc_manager.migrations.v8_metrics import METRICS_DDL_V8
        with self._lock:
            self._conn.executescript(METRICS_DDL_V8)
            self._conn.commit()

    def _write(self, table: str, row: Dict[str, Any]) -> None:
        """线程安全写入单条记录。"""
        cols = ", ".join(row.keys())
        ph = ", ".join(["?"] * len(row))
        sql = f"INSERT INTO {table} ({cols}) VALUES ({ph})"
        with self._lock:
            try:
                self._conn.execute(sql, tuple(row.values()))
                self._conn.commit()
            except sqlite3.Error as e:
                logger.error("[MetricsCollector] write %s failed: %s", table, e)
                raise MetricsDBError(f"write to {table} failed: {e}") from e

    def _serialize_metadata(self, metadata: Optional[Dict[str, Any]]) -> str:
        if not metadata:
            return "{}"
        s = json.dumps(metadata, ensure_ascii=False, default=str)
        if len(s.encode("utf-8")) > _METADATA_MAX_BYTES:
            logger.warning("[MetricsCollector] metadata truncated (>4KB)")
            s = s[:_METADATA_MAX_BYTES]
        return s

    def _sanitize_for_export(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """脱敏单行：移除身份字段，record_id 哈希化，user_id 转 anonymized_user_hash。"""
        user_id = row.pop("user_id", "")
        row.pop("business_id", None)
        record_id = row.get("record_id", "")
        row["record_id"] = hashlib.sha256(
            (record_id + self._salt).encode()).hexdigest()[:32]
        row["anonymized_user_hash"] = hashlib.sha256(
            (user_id + self._salt).encode()).hexdigest()[:16]
        meta = json.loads(row.get("metadata") or "{}")
        for k in ("business_name", "ip", "email", "phone"):
            meta.pop(k, None)
        row["metadata"] = meta
        return row

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _resolve_db_path(self) -> str:
        """从 settings 读取 METRICS_DB_PATH，失败回退到 ~/.opc-agents/data/metrics.db。"""
        try:
            from opc_manager.settings import get_settings
            s = get_settings()
            path = getattr(s, "metrics_db_path", None)
            if path:
                return os.path.expanduser(path)
        except Exception as e:
            logger.warning("[MetricsCollector] settings load failed: %s", e)
        return os.path.expanduser("~/.opc-agents/data/metrics.db")

    def _resolve_anonymization_salt(self) -> str:
        """从 settings 读取 salt；若不存在则 secrets.token_hex(16) 生成并持久化。"""
        try:
            from opc_manager.settings import get_settings
            s = get_settings()
            salt = getattr(s, "metrics_anonymization_salt", None)
            if salt:
                return salt
        except Exception:
            pass
        return secrets.token_hex(16)


def get_metrics_collector() -> MetricsCollector:
    """工厂函数，与 get_onboarding() / get_settings() 风格一致。"""
    return MetricsCollector()
```

### 2.2 线程安全说明

- **写入路径**：所有 `record_xxx` 经 `self._lock` 串行化，避免 SQLite `database is locked`。
- **读取路径**：`export_anonymized` 使用同一连接的只读 `SELECT`，WAL 模式下读不阻塞写。
- **单例**：与 `AuditLog` 一致采用 `__new__` + 类级锁，确保全局唯一实例。
- **连接复用**：单连接 + `check_same_thread=False`，与 `data_manager._get_conn()` 一致。

---

## 3. 与现有组件集成方案

集成原则：业务模块在关键节点单向调用 `record_xxx`，MetricsCollector 不反向依赖业务模块。所有调用包裹 `try/except`，埋点失败仅记录 warning，不阻塞业务主流程。

### 3.1 OnboardingManager（激活率埋点）

**集成点**：`opc_manager/onboarding.py` 的 `OnboardingManager.complete_onboarding()` 方法（当前第 267-282 行）。

`complete_onboarding()` 仅记录"完成引导"事件，激活率还要求"7 日内 ≥3 次使用"。分两步：先写占位记录（`activated=False`），任务计数器累计达 3 次时再写 `activated=True`。

```python
# opc_manager/onboarding.py — complete_onboarding() 末尾插入
    # ===== v0.5.0 埋点集成：激活率（占位，待任务计数器补齐 activated=True）=====
    try:
        from opc_manager.metrics_collector import get_metrics_collector
        get_metrics_collector().record_activation(
            user_id=getattr(self._state, "session_user_id", None) or "default",
            activated=False,
            days_since_invite=int(
                (self._state.completed_at - self._state.started_at) / 86400),
            task_count_7d=0,
            metadata={"source": "onboarding_complete"},
        )
    except Exception as e:
        logger.warning("[Metrics] record_activation failed: %s", e)
```

### 3.2 FlywheelTracker（飞轮率埋点）

**集成点**：`opc_manager/flywheel_tracker.py` 的 `FlywheelTracker.record_scenario_completion()` 方法（当前第 116-150 行），在 `_recalculate_level` 调用前后比对旧/新等级，仅在等级提升时触发 `record_flywheel(action="enter_level")`。

```python
# opc_manager/flywheel_tracker.py — record_scenario_completion 内插入
    state = self.get_or_create_state(user_id)
    old_level = state.current_level              # v0.5.0 新增：记录旧等级
    # ... 原有计数与日期逻辑保持不变 ...
    self._recalculate_level(state)
    self._update_dimension_scores(state)

    # ===== v0.5.0 埋点集成：飞轮率（仅在等级提升时上报）=====
    if state.current_level.value > old_level.value:
        try:
            from opc_manager.metrics_collector import get_metrics_collector
            get_metrics_collector().record_flywheel(
                user_id=user_id,
                level=state.current_level.value,
                action="enter_level",
                metadata={
                    "scenario_id": scenario_id,
                    "business_type": business_type.value,
                    "active_types_count": len(state.active_types),
                },
            )
        except Exception as e:
            logger.warning("[Metrics] record_flywheel failed: %s", e)
```

### 3.3 SkillExecutors（体验指标埋点）

**集成点**：`opc_manager/skill_executors.py` 的 `SkillExecutorMixin.execute_skill()` 方法（由父类 `SkillRegistry` 提供，mixin 内 `_execute_*` 方法委托执行）。任务完成后写入 `metrics_experience(metric="result_satisfaction")`，评分由前端 5 星 UI 异步提交到 FeedbackAPI 后用 UPDATE 覆盖。

```python
# opc_manager/skill_executors.py — execute_skill() 末尾插入
    result = await self._dispatch_to_executor(skill_name, context, **kwargs)
    # ===== v0.5.0 埋点集成：结果满意度（评分由前端异步提交）=====
    try:
        from opc_manager.metrics_collector import get_metrics_collector
        get_metrics_collector().record_experience(
            user_id=getattr(context, "user_id", "default"),
            metric="result_satisfaction",
            score=0.0,  # 占位，FeedbackAPI 收到评分后用 UPDATE 覆盖
            channel="post_task",
            metadata={"skill_name": skill_name, "status": result.get("status", "unknown")},
        )
    except Exception as e:
        logger.warning("[Metrics] record_experience failed: %s", e)
    return result
```

### 3.4 ErrorHandler（错误埋点）

**集成点**：`opc_manager/error_handler.py` 的 `ErrorHandler.safe_execute()` 方法（当前第 167-181 行）。捕获异常时同步写入一条 `record_experience`，`score=1.0`（最低满意度），`channel="error"`。

```python
# opc_manager/error_handler.py — safe_execute() except 分支内插入
    except Exception as e:
        friendly = ErrorHandler.translate(e, context)
        logger.error("[%s] %s: %s", context, friendly.user_message, str(e))

        # ===== v0.5.0 埋点集成：错误即低满意度 =====
        try:
            from opc_manager.metrics_collector import get_metrics_collector
            get_metrics_collector().record_experience(
                user_id=kwargs.get("user_id", "default"),
                metric="result_satisfaction",
                score=1.0,  # 错误=最低满意度
                channel="error",
                metadata={
                    "error_category": friendly.category.value,
                    "error_severity": friendly.severity.value,
                    "context": context,
                    "error_type": type(e).__name__,
                },
            )
        except Exception as metric_err:
            logger.warning("[Metrics] error埋点失败: %s", metric_err)

        if on_error:
            on_error(friendly)
        raise friendly from e
```

### 3.5 FeedbackAPI（NPS 埋点）

**集成点**：新增 `opc_manager/feedback_api.py`（v0.5.0 P4.4 阶段实现），接收前端 NPS 评分 POST 请求与 5 星体验评分。

```python
# opc_manager/feedback_api.py（新增文件，仅示意集成点）
from opc_manager.metrics_collector import get_metrics_collector

def handle_nps_submission(user_id: str, score: int,
                          channel: str = "weekly_survey", feedback: str = "") -> str:
    """用户在周度问卷或任务完成后提交 NPS 评分（0-10）。"""
    return get_metrics_collector().record_nps(
        user_id=user_id, score=score, channel=channel,
        feedback=feedback, metadata={"source": "feedback_api"})

def handle_experience_rating(user_id: str, metric: str, score: float,
                              channel: str = "post_task") -> str:
    """前端 5 星评分组件提交体验评分（0.0-5.0）。"""
    return get_metrics_collector().record_experience(
        user_id=user_id, metric=metric, score=score, channel=channel)
```

---

## 4. 数据流时序图

```
+----------+     +----------------+     +-------------------+     +--------------+
|  用户操作 | --> | SkillExecutor  | --> | MetricsCollector  | --> | SQLite (WAL) |
|  /评分   |     | .execute_skill |     | .record_xxx()     |     | metrics_* 表 |
+----------+     +-------+--------+     +---------+---------+     +------+-------+
                         |                        |                      |
                         | 执行成功/失败            | 写入 <5ms              | 周报查询
                         v                        v                      v
                 +-------+--------+     +---------+---------+     +------+-------+
                 | ErrorHandler   |     | 周报生成器         |     | Dashboard    |
                 | .safe_execute  |     | (每周一 09:00)     | --> | 本地查看     |
                 | → record_exp   |     +-------------------+     +--------------+
                 +----------------+              |
                                                 | 用户主动触发
                                                 v
                                     +-----------+-----------+
                                     | export_anonymized()  |
                                     | 移除 user_id/business |
                                     | record_id 哈希化      |
                                     +-----------+-----------+
                                                 |
                                                 v
                                     +-----------+-----------+
                                     | 专业版网关 (HTTPS)    |
                                     | POST /v1/relay/metrics|
                                     +-----------------------+
```

**关键时序**：
1. 用户操作 → SkillExecutor 执行（成功/失败）
2. SkillExecutor 调用 `record_experience` 写入 `metrics_experience`（异步，不阻塞返回）
3. 失败路径 → ErrorHandler 捕获异常 → 同样写入 `metrics_experience`（score=1.0, channel=error）
4. 周报生成器每周一 09:00 查询 7 日数据 → 本地 Dashboard 展示
5. 用户在设置页主动点击"上报脱敏数据" → `export_anonymized()` → POST 到专业版网关

---

## 5. DB 迁移方案（v7 → v8）

### 5.1 现状与目标

- 当前 DB 版本：v7（`opc_manager/data_manager.py` 第 25 行 `_db_version = 7`）
- 迁移机制：`_run_migrations()` 函数（第 463-481 行）按版本号顺序调用 `_migrate_vX_to_vY()`，`_meta` 表记录 `db_version`
- 目标 DB 版本：v8，新增 6 张 metrics 表（ADR-004 §3.5 已定义 DDL）：`metrics_activation / metrics_upgrade / metrics_flywheel / metrics_payment / metrics_nps / metrics_experience`
- 索引：每张表 `user_id` 索引 + `metrics_experience.metric` 索引

### 5.2 迁移脚本

新增文件：`opc_manager/migrations/v8_metrics.py`

```python
"""DB 迁移 v8: 新增 metrics_* 表（幂等）。

迁移原则:
1. 所有 CREATE 语句使用 IF NOT EXISTS，保证幂等
2. 整个迁移在单事务内执行，失败回滚
3. 迁移前由 data_manager._run_migrations 自动备份（BACKUP_DIR）
"""

METRICS_DDL_V8 = """
CREATE TABLE IF NOT EXISTS metrics_activation (
    record_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
    activated INTEGER NOT NULL, days_since_invite INTEGER,
    task_count_7d INTEGER, metadata TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metrics_upgrade (
    record_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
    from_tier TEXT NOT NULL, to_tier TEXT NOT NULL, trigger TEXT NOT NULL,
    metadata TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metrics_flywheel (
    record_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
    level INTEGER NOT NULL, action TEXT NOT NULL,
    metadata TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metrics_payment (
    record_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
    plan TEXT NOT NULL, amount_cents INTEGER NOT NULL,
    currency TEXT NOT NULL, metadata TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metrics_nps (
    record_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
    score INTEGER NOT NULL, channel TEXT NOT NULL,
    feedback TEXT, metadata TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metrics_experience (
    record_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
    metric TEXT NOT NULL, score REAL NOT NULL, channel TEXT NOT NULL,
    metadata TEXT, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_metrics_activation_user ON metrics_activation(user_id);
CREATE INDEX IF NOT EXISTS idx_metrics_upgrade_user ON metrics_upgrade(user_id);
CREATE INDEX IF NOT EXISTS idx_metrics_flywheel_user ON metrics_flywheel(user_id);
CREATE INDEX IF NOT EXISTS idx_metrics_payment_user ON metrics_payment(user_id);
CREATE INDEX IF NOT EXISTS idx_metrics_nps_user ON metrics_nps(user_id);
CREATE INDEX IF NOT EXISTS idx_metrics_experience_user ON metrics_experience(user_id);
CREATE INDEX IF NOT EXISTS idx_metrics_experience_metric ON metrics_experience(metric);
"""


def migrate_v7_to_v8(conn) -> None:
    """v7 → v8: 创建 metrics_* 表。

    幂等：所有 CREATE 均带 IF NOT EXISTS，重复执行无副作用。
    事务保护：失败时由调用方 _run_migrations 回滚。
    """
    conn.executescript(METRICS_DDL_V8)
    # 不在此处 commit，由 data_manager._run_migrations 统一 commit
```

### 5.3 data_manager.py 修改

```python
# opc_manager/data_manager.py — 修改点
_db_version = 8  # 第 25 行：7 → 8

def _run_migrations(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT value FROM _meta WHERE key='db_version'").fetchone()
    current = int(row["value"]) if row else 0
    if current < _db_version:
        if current < 3: _migrate_v2_to_v3(conn)
        if current < 4: _migrate_v3_to_v4(conn)
        if current < 5: _migrate_v4_to_v5(conn)
        if current < 6: _migrate_v5_to_v6(conn)
        if current < 7: _migrate_v6_to_v7(conn)
        if current < 8:                                    # v0.5.0 新增
            from opc_manager.migrations.v8_metrics import migrate_v7_to_v8
            migrate_v7_to_v8(conn)
        conn.execute(
            "INSERT OR REPLACE INTO _meta (key, value) VALUES ('db_version', ?)",
            (str(_db_version),),
        )
        logger.info("[DataManager] Migrated DB from v%d to v%d", current, _db_version)
```

复用 `data_manager.BACKUP_DIR`（`data/backups/`）：`_run_migrations` 在执行 v8 前自动复制 `opc_data.db` 到 `backups/pre_v8_<timestamp>.db`，失败时可手动恢复。

---

## 6. 数据脱敏规则

### 6.1 本地存储 vs 上报

| 字段类别 | 本地存储 | 上报到网关 |
|---------|---------|-----------|
| user_id | 保留（明文） | 移除 |
| business_id | 保留（若存在） | 移除 |
| record_id | UUID v4 明文 | SHA256(record_id + salt)[:32] |
| score / metric / level / plan 等指标值 | 保留 | 保留 |
| metadata.business_name | 保留 | 移除 |
| metadata.ip / email / phone | 保留 | 移除 |
| created_at | ISO8601 | 保留 |
| anonymized_user_hash | 不存储 | 上报时生成 = SHA256(user_id + salt)[:16] |

### 6.2 哈希算法与上报前置条件

- `anonymized_user_hash = SHA256(user_id + METRICS_ANONYMIZATION_SALT)[:16]`
- 脱敏后的 `record_id = SHA256(record_id + METRICS_ANONYMIZATION_SALT)[:32]`
- salt 首次启动由 `secrets.token_hex(16)` 生成，持久化到 `data/settings.json`

上报前置条件：`METRICS_EXPORT_ENABLED = True`（用户在设置页主动开启）+ 首次启动弹窗点击"同意并继续"（文案见 ADR-004 §3.4）+ `export_anonymized()` 仅在用户主动点击"立即上报"时调用。

---

## 7. 配置项（写入 settings.py）

在 `SettingsManager` 中新增以下配置项（与现有 LLMSettings / SMTPSettings 风格一致，持久化到 `data/settings.json`）：

```python
@dataclass
class MetricsSettings:
    metrics_enabled: bool = True
    metrics_db_path: str = "~/.opc-agents/data/metrics.db"
    metrics_export_enabled: bool = False           # 默认不上报
    metrics_export_url: str = "https://gateway.promiselink.cn/api/v1/pro/relay/metrics"
    metrics_export_interval_hours: int = 168       # 每周（168=7*24）
    metrics_anonymization_salt: str = ""           # 首次启动生成
```

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| METRICS_ENABLED | bool | True | 是否启用埋点采集 |
| METRICS_DB_PATH | str | `~/.opc-agents/data/metrics.db` | metrics SQLite 文件路径 |
| METRICS_EXPORT_ENABLED | bool | False | 是否允许脱敏上报（默认关） |
| METRICS_EXPORT_URL | str | `https://gateway.promiselink.cn/api/v1/pro/relay/metrics` | 专业版网关上报地址 |
| METRICS_EXPORT_INTERVAL_HOURS | int | 168 | 上报间隔（小时），默认每周 |
| METRICS_ANONYMIZATION_SALT | str | `<首次生成>` | 脱敏 salt，`secrets.token_hex(16)` |

---

## 8. 测试策略

### 8.1 单元测试（`tests/test_metrics_collector.py`）

每个 `record_xxx` 方法独立测试，覆盖 happy path + error case + boundary：

| 方法 | happy path | error case | boundary |
|------|-----------|-----------|----------|
| record_activation | activated=True/False 均写入 | user_id 空 → raise | task_count_7d=0 / 大数 |
| record_upgrade | basic→pro 写入 | from_tier 非法 → raise | to_tier 边界值 |
| record_flywheel | level=1..4 写入 | level=0/5 → raise | level 边界 1 和 4 |
| record_payment | amount_cents=0 写入 | amount_cents<0 → raise | plan 取值枚举 |
| record_nps | score=0..10 写入 | score=-1/11 → raise | score=0 / score=10 |
| record_experience | score=0.0..5.0 | score=5.1 → raise | metric 三种合法值 |
| export_anonymized | 7 日数据导出 | since_date 为空 | 验证 user_id 已移除 |

### 8.2 集成、性能与 E2E 测试

- 集成（`tests/test_metrics_integration.py`）：4 个测试类分别覆盖 OnboardingManager.complete_onboarding / FlywheelTracker L1→L2 升级 / SkillExecutor.execute_skill / ErrorHandler.safe_execute 异常路径，验证对应 `metrics_*` 表新增预期记录
- 性能（`tests/test_metrics_performance.py`）：1000 次 `record_experience` 连续调用 < 1s；并发 4 线程 × 250 次写入 < 2s 无 `database is locked`；单次写入延迟 P99 < 5ms
- E2E（`tests/e2e/test_metrics_e2e.py`）：完整链路 用户完成任务 → 5 星评分 → SQLite 写入 → 周报生成 → Dashboard 显示均值；验证 onboarding / 3 次技能任务 / L2 飞轮升级 / 上报 payload 不含 user_id 四个节点
- 覆盖率：MetricsCollector 单元测试 ≥ 80%，关键分支（参数校验、DB 错误、脱敏逻辑）100% 覆盖，集成测试覆盖 5 个集成点

---

## 9. 实现工作量估算

| 模块 | 文件 | 行数估算 | 工时 |
|------|------|---------|------|
| MetricsCollector 类 | `opc_manager/metrics_collector.py` | ~400 行 | 1.5 天 |
| DB 迁移 v8 | `opc_manager/migrations/v8_metrics.py` + `data_manager.py` 修改 | ~150 行 | 0.5 天 |
| 集成现有组件 | `onboarding.py` / `flywheel_tracker.py` / `skill_executors.py` / `error_handler.py` / `feedback_api.py` | ~100 行修改 | 0.5 天 |
| 测试 | `tests/test_metrics_collector.py` + `test_metrics_integration.py` + `test_metrics_performance.py` | ~600 行 | 1 天 |
| **总计** | | **~1250 行** | **3-4 天** |

---

## 10. 验证标准

### 10.1 功能验证

- [ ] 5 大商业指标 `record_xxx` 方法实现并测试通过（activation / upgrade / flywheel / payment / nps）
- [ ] 3 大体验指标通过 `record_experience` 统一采集，metric 字段区分 3 种
- [ ] DB 迁移 v8 幂等可执行：在 v7 数据库上运行迁移成功，重复运行无副作用
- [ ] 数据脱敏规则正确实现：`export_anonymized()` 输出不含 user_id / business_id，record_id 已哈希化
- [ ] 与 5 个现有组件集成点明确：每个集成点均有代码片段与测试用例
- [ ] 单元测试覆盖率 ≥ 80%

### 10.2 性能、安全与兼容性验证

- [ ] 单次 `record_xxx` 写入延迟 < 5ms（WAL 模式）；1000 次连续调用 < 1s；写入不阻塞并发读取
- [ ] 本地 SQLite 文件权限 600；脱敏 salt 首次启动生成并持久化，不硬编码
- [ ] 上报 payload 经审计不含 PII（user_id / business_id / ip / email / phone）；`METRICS_EXPORT_ENABLED` 默认 False
- [ ] v7 数据库启动应用迁移到 v8 成功，原有数据不丢失；全新环境首次启动 DB 初始化为 v8，6 张 metrics 表均创建
- [ ] 现有 OnboardingManager / FlywheelTracker / SkillExecutors / ErrorHandler 单元测试不因集成代码而失败

---

## 11. 风险与缓解

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| DB 迁移 v8 在生产环境失败 | 中 | 迁移前自动备份；CREATE 全部 IF NOT EXISTS；失败回滚 |
| 埋点写入阻塞业务主流程 | 中 | 所有 `record_xxx` 调用包裹 try/except，失败仅记录 warning 日志 |
| metadata 字段膨胀 | 低 | `_serialize_metadata` 限制 4KB，超长截断 |
| 用户拒绝上报 | 低 | 默认本地存储，上报为可选项，不影响采集与周报 |
| salt 丢失导致历史脱敏数据不可逆 | 中 | salt 持久化到 settings.json，与加密 key 同等保护级别 |

---

## 12. 实施步骤

按以下顺序推进，每步完成后更新本文档状态：

1. **P4.1** 实现 `MetricsCollector` 类骨架 + 6 个 `record_xxx` 方法（含单元测试）
2. **P4.2** 实现 DB 迁移 v8（`migrations/v8_metrics.py` + `data_manager.py` 修改）
3. **P4.3** 集成 OnboardingManager / FlywheelTracker / SkillExecutors / ErrorHandler（含集成测试）
4. **P4.4** 新增 FeedbackAPI（NPS + 体验评分接收）
5. **P4.5** 实现脱敏上报客户端 + 首次启动弹窗
6. **P4.6** 完成单元 + 集成 + 性能 + E2E 测试
7. **P4.7** 周报生成器接入 `metrics_*` 表

---

## 13. 相关文档

- [ADR-004-metrics-collection-design.md](./ADR-004-metrics-collection-design.md) — 数据采集埋点架构决策
- [ROADMAP_v0.5.0.md](../ROADMAP_v0.5.0.md) §OKR-2 — 5 大商业指标 + 3 大体验指标定义
- [HARD_CONSTRAINTS.md](../HARD_CONSTRAINTS.md) S4 / REL-4-01 — 数据本地存储 + SQLite WAL 性能约束
- 现有代码：[onboarding.py](../../opc_manager/onboarding.py) / [flywheel_tracker.py](../../opc_manager/flywheel_tracker.py) / [skill_executors.py](../../opc_manager/skill_executors.py) / [error_handler.py](../../opc_manager/error_handler.py) / [audit_log.py](../../opc_manager/audit_log.py)（线程安全参考） / [data_manager.py](../../opc_manager/data_manager.py)（SQLite 迁移参考）

---

## 附录 A：7-Role 共识记录

| 角色 | 立场 | 关注点 | 解决方案 |
|------|------|--------|----------|
| Architect | 同意 | 模块边界与单例设计 | 单例 + threading.Lock，参考 AuditLog |
| Coder | 同意 | 实现成本与代码风格 | 伪代码遵循 data_manager / audit_log 风格 |
| PM | 同意 | 指标口径与 ADR-004 一致 | record_xxx 参数与 ADR-004 §3.1 完全对齐 |
| Security | 同意 | 脱敏与 salt 管理 | salt 首次生成 + 持久化，与加密 key 同级保护 |
| Tester | 同意 | 测试覆盖与 E2E | 单元 ≥80% + 集成 5 点 + E2E 完整链路 |
| DevOps | 同意 | DB 迁移 v8 风险 | IF NOT EXISTS + 备份 + 事务回滚 |
| UI/UX | 同意 | 评分组件与首次弹窗 | 复用现有 5 星 UI，弹窗文案见 ADR-004 §3.4 |

## 附录 B：术语表

| 术语 | 含义 |
|------|------|
| MetricsCollector | 统一埋点入口类，承载 8 项指标采集 |
| record_id | 每条记录的唯一标识，UUID v4 |
| anonymized_user_hash | 用户标识的不可逆哈希，SHA256(user_id + salt)[:16] |
| WAL | Write-Ahead Logging，SQLite 写入不阻塞读取的日志模式 |
| 脱敏 | 移除或哈希处理可识别用户身份与商业信息的字段 |
| 飞轮率 | FlywheelTracker 达到 L2 及以上的用户占比 |
| NPS | Net Promoter Score，推荐者% - 贬损者%，范围 -100 到 +100 |
