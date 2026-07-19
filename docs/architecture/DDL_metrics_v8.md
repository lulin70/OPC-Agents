# 指标采集数据库 DDL 与迁移脚本 v8（v0.5.0 P4）

**版本**: v0.5.0-draft
**日期**: 2026-07-19
**状态**: 7-Role 共识
**决策者**: Architect + Coder
**关联**: [ADR-004-metrics-collection-design.md](ADR-004-metrics-collection-design.md) §3.5 / §4 / [ROADMAP_v0.5.0.md](../ROADMAP_v0.5.0.md) §OKR-2 / [HARD_CONSTRAINTS.md](../HARD_CONSTRAINTS.md) S4 / REL-4-01

---

## 1. 背景

ADR-004 §3.5 给出了指标采集 5 张表的 DDL 草案，但仅是字段骨架，未包含触发器、索引细节、汇总视图、脱敏视图、迁移脚本。本文档作为 ADR-004 §3.5 的 P4 阶段细化，提供**可直接执行的 DDL + 索引 + 触发器 + 视图**和**完整的迁移脚本 Python 伪代码**，供 Coder 在 P4.2 阶段直接落地。

### 1.1 与 ADR-004 草案的差异

| 维度 | ADR-004 §3.5 草案 | 本文档（P4 细化） |
|------|-------------------|--------------------|
| 表数量 | 6 张（含独立 `metrics_nps`） | 5 张（NPS 并入 `metrics_experience`，通过 `metric_type='nps'` 区分） |
| 主键命名 | `record_id` | `id`（与现有 `audit_log` / `finance_records` 等表保持一致） |
| `updated_at` 字段 | 无 | `metrics_activation` 增补，由触发器维护 |
| 触发器 / 视图 | 无 | `trg_activation_updated_at` + 6 个汇总视图 + 5 个脱敏视图 |
| 迁移入口 | 未规定 | `opc_manager/migrations/v8_metrics.py::migrate_v8(conn)` |

### 1.2 现有迁移机制回顾

`opc_manager/data_manager.py` 中迁移机制（v1 → v7）：常量 `_db_version` + `_meta` 表存储版本号 + `_run_migrations(conn)` 顺序调用 `_migrate_vN_to_vN+1(conn)` 函数，每个迁移函数使用 `CREATE TABLE IF NOT EXISTS` / `_add_column_if_not_exists` 保证幂等。v6 → v7 为 `audit_log` 补 `prev_hash` / `current_hash` 列（链式哈希）。WAL 模式 + `PRAGMA synchronous=NORMAL` 已在 `_get_conn()` 配置。

本文档的 v8 迁移脚本沿用此风格，但作为独立模块 `opc_manager/migrations/v8_metrics.py`，由 `_run_migrations` 在 `current < 8` 时委托调用，便于后续按指标域拆分迁移文件。

---

## 2. DB 版本历史

| 版本 | 内容 | 时间 |
|------|------|------|
| v1 | 初始 schema（finance_records / customers / tasks 等业务表） | 2026-04 |
| v2 | external_skills / interaction_log 字段扩展 | 2026-04 |
| v3 | calendar_events 字段扩展 | 2026-05 |
| v4 | follow_ups 表 + invoices.proposal_id | 2026-05 |
| v5 | audit_log 表 + 业务索引 | 2026-06 |
| v6 | audit_log 表索引补全 | 2026-06 |
| v7 | audit_log 链式哈希列（prev_hash / current_hash） | 2026-07 |
| **v8** | **metrics 5 张表 + 索引 + 触发器 + 视图（本文档）** | **2026-07-19** |

---

## 3. 5 张表完整 DDL

### 3.1 metrics_activation（激活率）

```sql
-- 用途: 记录用户激活事件（完成 Onboarding + 7 日内 ≥3 次使用）
-- 写入时机: OnboardingManager._transition_to(COMPLETED) 之后
CREATE TABLE IF NOT EXISTS metrics_activation (
    id                        TEXT PRIMARY KEY,
    user_id                   TEXT NOT NULL,
    onboarding_completed_at   TEXT NOT NULL,           -- ISO8601
    first_use_at              TEXT NOT NULL,          -- ISO8601, 首次任务执行时间
    activation_criteria_met   INTEGER DEFAULT 0,      -- 0/1, 是否满足激活定义
    activation_met_at         TEXT,                    -- ISO8601, 满足激活条件的时间(可空)
    days_to_activate          INTEGER,                -- 从 onboarding 到激活的天数(可空)
    metadata                  TEXT,                   -- JSON, 附加字段(单条上限 4KB)
    created_at                TEXT NOT NULL,          -- ISO8601
    updated_at                TEXT NOT NULL            -- ISO8601, 由触发器维护
);

CREATE INDEX IF NOT EXISTS idx_activation_user_id    ON metrics_activation(user_id);
CREATE INDEX IF NOT EXISTS idx_activation_created_at ON metrics_activation(created_at);
CREATE INDEX IF NOT EXISTS idx_activation_user_created ON metrics_activation(user_id, created_at DESC);

CREATE TRIGGER IF NOT EXISTS trg_activation_updated_at
    AFTER UPDATE ON metrics_activation
    FOR EACH ROW
    WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE metrics_activation
    SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    WHERE id = NEW.id;
END;
```

### 3.2 metrics_upgrade（升级率）

```sql
-- 用途: 记录版本升级事件（basic/pro_trial → pro_activated）
-- 写入时机: relay_client 网关回调 / 手动激活
-- license_key 字段已脱敏: SHA256(license_key + salt)[:16]
CREATE TABLE IF NOT EXISTS metrics_upgrade (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    from_version TEXT,                                -- 'basic' / 'pro_trial' (可空)
    to_version   TEXT NOT NULL,                       -- 'pro_activated'
    upgrade_at   TEXT NOT NULL,                       -- ISO8601
    license_key  TEXT,                                -- 脱敏哈希, 16 字符
    metadata     TEXT,                                -- JSON
    created_at   TEXT NOT NULL                        -- ISO8601
);

CREATE INDEX IF NOT EXISTS idx_upgrade_user_id   ON metrics_upgrade(user_id);
CREATE INDEX IF NOT EXISTS idx_upgrade_upgrade_at ON metrics_upgrade(upgrade_at);
CREATE INDEX IF NOT EXISTS idx_upgrade_from_to   ON metrics_upgrade(from_version, to_version);
```

### 3.3 metrics_flywheel（飞轮率）

```sql
-- 用途: 记录飞轮级别变化（FlywheelTracker L0-L4）
-- 写入时机: FlywheelTracker.enter_level(level) 内部
-- 说明: 本表无 updated_at 字段, 飞轮事件为不可变记录,
--       故不创建 trg_flywheel_updated_at 触发器 (通用模板见 §4.3)
CREATE TABLE IF NOT EXISTS metrics_flywheel (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    flywheel_level  INTEGER NOT NULL,                 -- 0-4
    previous_level  INTEGER,                          -- 可空, 首次进入为 NULL
    level_up_at     TEXT NOT NULL,                    -- ISO8601
    skills_used     TEXT,                             -- JSON 数组, e.g. ["email","calendar"]
    metadata        TEXT,                             -- JSON
    created_at      TEXT NOT NULL                     -- ISO8601
);

CREATE INDEX IF NOT EXISTS idx_flywheel_user_id        ON metrics_flywheel(user_id);
CREATE INDEX IF NOT EXISTS idx_flywheel_level          ON metrics_flywheel(flywheel_level);
CREATE INDEX IF NOT EXISTS idx_flywheel_level_up_at   ON metrics_flywheel(level_up_at);
CREATE INDEX IF NOT EXISTS idx_flywheel_user_level_time ON metrics_flywheel(user_id, flywheel_level, level_up_at DESC);
```

### 3.4 metrics_payment（付费率）

```sql
-- 用途: 记录付费转化事件（trial → paid → cancelled → refunded）
-- 写入时机: 专业版网关 webhook
CREATE TABLE IF NOT EXISTS metrics_payment (
    id             TEXT PRIMARY KEY,
    user_id        TEXT NOT NULL,
    payment_status TEXT NOT NULL,                     -- 'trial' / 'paid' / 'cancelled' / 'refunded'
    amount         REAL,                              -- 金额(可空, trial 时为 NULL)
    currency       TEXT DEFAULT 'CNY',                -- ISO 4217 货币代码
    paid_at        TEXT,                               -- ISO8601, 实际支付时间(可空)
    metadata       TEXT,                               -- JSON
    created_at     TEXT NOT NULL                       -- ISO8601
);

CREATE INDEX IF NOT EXISTS idx_payment_user_id       ON metrics_payment(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_status        ON metrics_payment(payment_status);
CREATE INDEX IF NOT EXISTS idx_payment_paid_at      ON metrics_payment(paid_at);
CREATE INDEX IF NOT EXISTS idx_payment_status_paid_at ON metrics_payment(payment_status, paid_at);
```

### 3.5 metrics_experience（体验指标 + NPS）

```sql
-- 用途: 统一存储 3 大体验指标 + NPS 评分
-- 写入时机:
--   dialogue_naturalness: 每次对话后 5 星评分 UI
--   result_satisfaction:  SkillExecutors.complete_task() 后 5 星评分
--   proactive_service:    FlywheelTracker 建议接受率 + 周度问卷
--   nps:                   每周问卷 + 任务完成后评分
CREATE TABLE IF NOT EXISTS metrics_experience (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    metric_type  TEXT NOT NULL,                       -- 'dialogue_naturalness' / 'result_satisfaction' / 'proactive_service' / 'nps'
    score        REAL NOT NULL,                       -- 1.0-5.0 (体验指标) 或 0-10 (NPS)
    skill_id     TEXT,                                -- 关联技能(可空, NPS 时为 NULL)
    session_id   TEXT,                                -- 关联会话(可空)
    comment      TEXT,                                 -- 用户反馈文字(可空, 单条上限 4KB)
    timestamp    TEXT NOT NULL,                       -- ISO8601, 评分发生时间
    metadata     TEXT,                                 -- JSON, 渠道等附加字段
    created_at   TEXT NOT NULL                         -- ISO8601
);

CREATE INDEX IF NOT EXISTS idx_experience_user_id      ON metrics_experience(user_id);
CREATE INDEX IF NOT EXISTS idx_experience_metric_type  ON metrics_experience(metric_type);
CREATE INDEX IF NOT EXISTS idx_experience_timestamp    ON metrics_experience(timestamp);
CREATE INDEX IF NOT EXISTS idx_experience_skill_id     ON metrics_experience(skill_id);
CREATE INDEX IF NOT EXISTS idx_experience_type_time    ON metrics_experience(metric_type, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_experience_user_type    ON metrics_experience(user_id, metric_type);
```

---

## 4. 触发器

### 4.1 trg_activation_updated_at

已在 §3.1 中声明。当 `metrics_activation` 任意字段被 UPDATE 且 `updated_at` 未显式赋值时，触发器自动写入当前 UTC 时间。

- `AFTER UPDATE`: 业务字段更新后执行
- `WHEN NEW.updated_at = OLD.updated_at`: 仅当 `updated_at` 未被业务层显式赋值时触发（避免覆盖业务层显式写入）
- `FOR EACH ROW`: 行级触发

### 4.2 trg_flywheel_updated_at（不创建）

根据 §3.3 表结构定义，`metrics_flywheel` **不包含 `updated_at` 字段**（飞轮事件为不可变记录，仅追加不修改），故本触发器**不创建**。若未来需增加 `updated_at` 字段，应通过 v9 迁移脚本添加列并复用 §4.3 通用模板。

### 4.3 通用触发器模板

```sql
-- 通用 updated_at 触发器模板 (供 v9+ 迁移脚本复用)
-- 使用方法: 将 {TABLE_NAME} 替换为目标表名
CREATE TRIGGER IF NOT EXISTS trg_{TABLE_NAME}_updated_at
    AFTER UPDATE ON {TABLE_NAME}
    FOR EACH ROW
    WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE {TABLE_NAME}
    SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    WHERE id = NEW.id;
END;
```

**递归避免**: 触发器内部 UPDATE `updated_at` 字段后，再次触发时 `NEW.updated_at != OLD.updated_at`，`WHEN` 条件不满足，递归终止。

---

## 5. 视图（汇总查询）

### 5.1 view_activation_rate（激活率）

```sql
-- 定义: activated_users / total_onboarded_users
-- 激活定义: activation_criteria_met = 1
CREATE VIEW IF NOT EXISTS view_activation_rate AS
SELECT
    COUNT(DISTINCT user_id) AS total_onboarded,
    COUNT(DISTINCT CASE WHEN activation_criteria_met = 1 THEN user_id END) AS activated_users,
    ROUND(
        CAST(COUNT(DISTINCT CASE WHEN activation_criteria_met = 1 THEN user_id END) AS REAL)
        / MAX(COUNT(DISTINCT user_id), 1) * 100, 2
    ) AS activation_rate_pct,
    ROUND(AVG(days_to_activate), 2) AS avg_days_to_activate
FROM metrics_activation;
```

### 5.2 view_upgrade_rate（升级率）

```sql
-- 定义: 升级用户数 / 激活用户数
CREATE VIEW IF NOT EXISTS view_upgrade_rate AS
SELECT
    (SELECT COUNT(DISTINCT user_id) FROM metrics_activation WHERE activation_criteria_met = 1)
        AS activated_users,
    COUNT(DISTINCT u.user_id) AS upgraded_users,
    ROUND(
        CAST(COUNT(DISTINCT u.user_id) AS REAL)
        / MAX((SELECT COUNT(DISTINCT user_id) FROM metrics_activation WHERE activation_criteria_met = 1), 1)
        * 100, 2
    ) AS upgrade_rate_pct,
    COUNT(DISTINCT CASE WHEN u.from_version = 'basic' THEN u.user_id END) AS from_basic_count,
    COUNT(DISTINCT CASE WHEN u.from_version = 'pro_trial' THEN u.user_id END) AS from_trial_count
FROM metrics_upgrade u;
```

### 5.3 view_flywheel_rate（飞轮率）

```sql
-- 定义: 达到 level ≥2 的用户数 / 激活用户数
-- 每用户取最新飞轮级别(MAX level_up_at)
CREATE VIEW IF NOT EXISTS view_flywheel_rate AS
WITH latest_flywheel AS (
    SELECT user_id, flywheel_level
    FROM (
        SELECT user_id, flywheel_level, level_up_at,
               ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY level_up_at DESC) AS rn
        FROM metrics_flywheel
    )
    WHERE rn = 1
)
SELECT
    (SELECT COUNT(DISTINCT user_id) FROM metrics_activation WHERE activation_criteria_met = 1)
        AS activated_users,
    COUNT(DISTINCT CASE WHEN flywheel_level >= 2 THEN user_id END) AS flywheel_users,
    ROUND(
        CAST(COUNT(DISTINCT CASE WHEN flywheel_level >= 2 THEN user_id END) AS REAL)
        / MAX((SELECT COUNT(DISTINCT user_id) FROM metrics_activation WHERE activation_criteria_met = 1), 1)
        * 100, 2
    ) AS flywheel_rate_pct,
    COUNT(DISTINCT CASE WHEN flywheel_level = 1 THEN user_id END) AS level_1_count,
    COUNT(DISTINCT CASE WHEN flywheel_level = 2 THEN user_id END) AS level_2_count,
    COUNT(DISTINCT CASE WHEN flywheel_level = 3 THEN user_id END) AS level_3_count,
    COUNT(DISTINCT CASE WHEN flywheel_level = 4 THEN user_id END) AS level_4_count
FROM latest_flywheel;
```

### 5.4 view_payment_rate（付费率）

```sql
-- 定义: 付费用户数(payment_status='paid') / 激活用户数
CREATE VIEW IF NOT EXISTS view_payment_rate AS
SELECT
    (SELECT COUNT(DISTINCT user_id) FROM metrics_activation WHERE activation_criteria_met = 1)
        AS activated_users,
    COUNT(DISTINCT CASE WHEN payment_status = 'paid' THEN user_id END) AS paid_users,
    ROUND(
        CAST(COUNT(DISTINCT CASE WHEN payment_status = 'paid' THEN user_id END) AS REAL)
        / MAX((SELECT COUNT(DISTINCT user_id) FROM metrics_activation WHERE activation_criteria_met = 1), 1)
        * 100, 2
    ) AS payment_rate_pct,
    COUNT(DISTINCT CASE WHEN payment_status = 'trial' THEN user_id END) AS trial_count,
    COUNT(DISTINCT CASE WHEN payment_status = 'cancelled' THEN user_id END) AS cancelled_count,
    COUNT(DISTINCT CASE WHEN payment_status = 'refunded' THEN user_id END) AS refunded_count,
    ROUND(SUM(CASE WHEN payment_status = 'paid' THEN amount ELSE 0 END), 2) AS total_paid_amount
FROM metrics_payment;
```

### 5.5 view_nps_score（NPS 分值）

```sql
-- 定义: 推荐者(9-10)% - 贬损者(0-6)%, 范围 -100 到 +100
CREATE VIEW IF NOT EXISTS view_nps_score AS
SELECT
    COUNT(*) AS total_responses,
    SUM(CASE WHEN score >= 9 THEN 1 ELSE 0 END) AS promoters,
    SUM(CASE WHEN score BETWEEN 7 AND 8 THEN 1 ELSE 0 END) AS passives,
    SUM(CASE WHEN score <= 6 THEN 1 ELSE 0 END) AS detractors,
    ROUND(CAST(SUM(CASE WHEN score >= 9 THEN 1 ELSE 0 END) AS REAL) / MAX(COUNT(*), 1) * 100, 2) AS promoter_pct,
    ROUND(CAST(SUM(CASE WHEN score <= 6 THEN 1 ELSE 0 END) AS REAL) / MAX(COUNT(*), 1) * 100, 2) AS detractor_pct,
    ROUND(
        (CAST(SUM(CASE WHEN score >= 9 THEN 1 ELSE 0 END) AS REAL)
         - CAST(SUM(CASE WHEN score <= 6 THEN 1 ELSE 0 END) AS REAL))
        / MAX(COUNT(*), 1) * 100, 2
    ) AS nps_score
FROM metrics_experience WHERE metric_type = 'nps';
```

### 5.6 view_experience_avg（3 大体验指标均分）

```sql
-- 定义: 按 metric_type 分组计算均分, 范围 0.0-5.0
CREATE VIEW IF NOT EXISTS view_experience_avg AS
SELECT
    metric_type,
    ROUND(AVG(score), 2) AS avg_score,
    COUNT(*) AS response_count,
    ROUND(SUM(CASE WHEN score >= 4 THEN 1 ELSE 0 END) * 100.0 / MAX(COUNT(*), 1), 2) AS satisfied_pct,
    ROUND(MIN(score), 2) AS min_score,
    ROUND(MAX(score), 2) AS max_score
FROM metrics_experience
WHERE metric_type IN ('dialogue_naturalness', 'result_satisfaction', 'proactive_service')
GROUP BY metric_type;
```

---

## 6. 迁移脚本设计

### 6.1 文件路径与函数签名

```
opc_manager/migrations/__init__.py        # 空文件, 标记为 Python 包
opc_manager/migrations/v8_metrics.py      # v8 迁移脚本
```

```python
def migrate_v8(conn: sqlite3.Connection) -> None:
    """v7 → v8: 创建 metrics 5 张表 + 索引 + 触发器 + 视图
    幂等性: 所有 CREATE 语句使用 IF NOT EXISTS, 重复执行不报错
    失败回滚: 任何步骤失败执行 ROLLBACK + 恢复备份
    Raises: RuntimeError — 迁移失败, 已回滚并恢复备份
    """
```

### 6.2 迁移步骤

1. **检查当前版本**: 从 `_meta` 表读取 `db_version`，必须为 7
2. **备份数据库**: `cp data/opc_data.db data/backups/opc_data.db.v7.bak.{timestamp}`
3. **开启事务**: `conn.execute("BEGIN")`
4. **创建 5 张表 + 14 个索引 + 1 个触发器**: `CREATE ... IF NOT EXISTS`（SQL 见 §3）
5. **创建 11 个视图**: 6 个汇总视图（§5）+ 5 个脱敏视图（§7）
6. **创建 schema_version 表**: 记录迁移历史
7. **更新版本号**: `_meta.db_version=8` + `schema_version` 新增 `(8, 'metrics', '2026-07-19')`
8. **提交事务**: `conn.commit()`
9. **失败回滚**: 任意步骤抛异常 → `conn.rollback()` → 恢复备份

### 6.3 迁移脚本 Python 伪代码

```python
"""v8 迁移脚本: 创建 metrics 5 张表 + 索引 + 触发器 + 视图

执行入口: opc_manager.data_manager._run_migrations() 在 current < 8 时调用
幂等性: 所有 CREATE 语句使用 IF NOT EXISTS, 可重复执行
回滚: 失败时恢复 v7 备份
"""

import logging, os, shutil, sqlite3
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
V8_VERSION, V8_DESCRIPTION, V8_APPLIED_AT = 8, "metrics", "2026-07-19"

# SQL 语句集中管理, 便于审计与回滚审查
# _DDL_TABLES / _DDL_INDEXES / _DDL_TRIGGERS / _DDL_VIEWS / _DDL_EXPORT_VIEWS
# 内容直接对应本文档 §3 / §4 / §5 / §7 的 SQL 语句, 实际脚本中应将上述各节
# 的 CREATE 语句完整粘贴为 Python 多行字符串常量


def migrate_v8(conn: sqlite3.Connection) -> None:
    """v7 → v8 迁移主函数 (见 §6.1 函数签名说明)"""
    # 步骤 1: 检查当前版本 (必须为 7)
    row = conn.execute("SELECT value FROM _meta WHERE key='db_version'").fetchone()
    if not row:
        raise RuntimeError("[migrate_v8] _meta.db_version not found, cannot migrate")
    current = int(row[0])
    if current != 7:
        raise RuntimeError(
            f"[migrate_v8] expected db_version=7, got v{current}. Run prior migrations first."
        )
    logger.info("[migrate_v8] Current version: v%d, target: v%d", current, V8_VERSION)

    # 步骤 2: 备份数据库到 data/backups/opc_data.db.v7.bak.{timestamp}
    db_path = conn.execute("PRAGMA database_list").fetchone()[2]
    backup_dir = os.path.join(os.path.dirname(db_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = os.path.join(backup_dir, f"opc_data.db.v7.bak.{ts}")
    shutil.copy2(db_path, backup_path)
    logger.info("[migrate_v8] Backup created: %s", backup_path)

    try:
        conn.execute("BEGIN")  # 步骤 3: 开启事务

        # 步骤 4-5: 创建 5 张表 + 14 个索引 (SQL 内容见 §3)
        conn.executescript(_DDL_TABLES)
        conn.executescript(_DDL_INDEXES)
        # 步骤 6: 创建触发器 (SQL 内容见 §3.1 / §4)
        conn.executescript(_DDL_TRIGGERS)
        # 步骤 7-8: 创建 6 个汇总视图 + 5 个脱敏视图 (SQL 内容见 §5 / §7)
        conn.executescript(_DDL_VIEWS)
        conn.executescript(_DDL_EXPORT_VIEWS)
        logger.info("[migrate_v8] Tables/indexes/triggers/views created")

        # 步骤 9: 创建 schema_version 表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY, description TEXT NOT NULL, applied_at TEXT NOT NULL
            )
        """)

        # 步骤 10: 更新版本号 (_meta + schema_version)
        conn.execute(
            "INSERT OR REPLACE INTO _meta (key, value) VALUES ('db_version', ?)",
            (str(V8_VERSION),),
        )
        conn.execute(
            "INSERT OR REPLACE INTO schema_version "
            "(version, description, applied_at) VALUES (?, ?, ?)",
            (V8_VERSION, V8_DESCRIPTION, V8_APPLIED_AT),
        )

        conn.commit()  # 步骤 11: 提交事务
        logger.info("[migrate_v8] Migration v%d → v%d completed", current, V8_VERSION)

    except Exception as e:
        # 步骤 12: 失败回滚
        logger.error("[migrate_v8] Migration failed: %s. Rolling back...", e)
        try:
            conn.rollback()
        except Exception as rollback_err:
            logger.error("[migrate_v8] Rollback failed: %s", rollback_err)
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, db_path)  # 恢复备份
        raise RuntimeError(f"migrate_v8 failed and rolled back: {e}") from e
```

### 6.4 与 data_manager.py 集成

在 `opc_manager/data_manager.py` 中修改两处：

```python
# 1. 修改常量: _db_version = 8  (原: 7)

# 2. 在 _run_migrations 中 current < 8 时委托调用:
if current < 8:
    from opc_manager.migrations.v8_metrics import migrate_v8
    migrate_v8(conn)  # 委托给独立模块, 不污染 data_manager.py
```

---

## 7. 数据脱敏视图（用于上报）

用户主动触发上报时，使用以下 5 个脱敏视图生成 payload。所有视图**去除 `user_id`**，仅保留 `anonymized_user_hash`（SHA256 + 项目 salt 的前 16 字符）。

> **重要说明**: SQLite 标准构建不内置 SHA256 函数。脱敏视图的 `anonymized_user_hash` 字段在视图层用 `NULL` 占位，真实脱敏由 `MetricsCollector.export_anonymized()` 在 Python 层执行 `hashlib.sha256((user_id + SALT).encode()).hexdigest()[:16]` 后构造 payload。视图仅用于声明字段集合。

### 7.1-7.5 5 个脱敏视图

```sql
-- view_export_activation (去除 user_id, 保留 anonymized_user_hash + 指标值)
CREATE VIEW IF NOT EXISTS view_export_activation AS
SELECT NULL AS anonymized_user_hash, onboarding_completed_at, first_use_at,
       activation_criteria_met, activation_met_at, days_to_activate, created_at
FROM metrics_activation;

-- view_export_upgrade
CREATE VIEW IF NOT EXISTS view_export_upgrade AS
SELECT NULL AS anonymized_user_hash, from_version, to_version, upgrade_at,
       license_key, created_at
FROM metrics_upgrade;

-- view_export_flywheel
CREATE VIEW IF NOT EXISTS view_export_flywheel AS
SELECT NULL AS anonymized_user_hash, flywheel_level, previous_level, level_up_at,
       skills_used, created_at
FROM metrics_flywheel;

-- view_export_payment
CREATE VIEW IF NOT EXISTS view_export_payment AS
SELECT NULL AS anonymized_user_hash, payment_status, amount, currency, paid_at, created_at
FROM metrics_payment;

-- view_export_experience
CREATE VIEW IF NOT EXISTS view_export_experience AS
SELECT NULL AS anonymized_user_hash, metric_type, score, skill_id, session_id,
       comment, timestamp, created_at
FROM metrics_experience;
```

### 7.6 Python 层脱敏实现

```python
import hashlib
from datetime import datetime, timezone

_EXPORT_SALT = "opc-agents-metrics-export-v0.5.0"  # 项目级 salt

def _anonymize_user_id(user_id: str) -> str:
    """生成匿名用户哈希: SHA256(user_id + salt)[:16]"""
    return hashlib.sha256(f"{user_id}{_EXPORT_SALT}".encode()).hexdigest()[:16]

def export_anonymized(conn, since_date: str = None) -> dict:
    """导出脱敏数据用于上报 (用户主动触发)"""
    payload = {"generated_at": datetime.now(timezone.utc).isoformat()}
    for table_name in ["metrics_activation", "metrics_upgrade", "metrics_flywheel",
                       "metrics_payment", "metrics_experience"]:
        rows = conn.execute(
            f"SELECT * FROM {table_name}" + (f" WHERE created_at >= ?" if since_date else ""),
            (since_date,) if since_date else ()
        ).fetchall()
        anonymized = []
        for row in rows:
            row_dict = dict(row)
            user_id = row_dict.pop("user_id", None)
            row_dict["anonymized_user_hash"] = _anonymize_user_id(user_id)
            row_dict.pop("license_key", None)
            anonymized.append(row_dict)
        payload[table_name] = anonymized
    return payload
```

---

## 8. 数据保留策略

| 表 | 保留期 | 清理机制 | 理由 |
|----|--------|----------|------|
| metrics_activation | 永久保留 | 无 | 激活事件为产品核心 KPI，需长期追踪 |
| metrics_upgrade | 永久保留 | 无 | 升级转化数据用于长期商业分析 |
| metrics_flywheel | 永久保留 | 无 | 飞轮轨迹用于用户成长分析 |
| metrics_payment | 永久保留 | 无 | 付费记录涉及财务，需长期留存 |
| metrics_experience | 1 年 | `cleanup_old_metrics.py` 定时任务 | 高频写入，1 年前数据已聚合到周报，原始数据可清理 |

### 8.1 清理脚本伪代码（cleanup_old_metrics.py）

```python
"""定期清理 metrics_experience 表中超过 1 年的记录
调度: 每周日 02:00 由 cron / launchd 触发, 保留最近 365 天数据"""
import sqlite3
from datetime import datetime, timedelta, timezone

def cleanup_old_metrics(db_path: str, retention_days: int = 365) -> int:
    """清理超过保留期的 metrics_experience 记录, 返回删除行数"""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("DELETE FROM metrics_experience WHERE created_at < ?", (cutoff,))
    deleted = cursor.rowcount
    conn.commit(); conn.close()
    return deleted
```

---

## 9. 性能优化

### 9.1 WAL 模式 + 索引覆盖

`opc_manager/data_manager.py::_get_conn()` 已配置 `PRAGMA journal_mode=WAL` 与 `PRAGMA synchronous=NORMAL`，v8 迁移脚本无需重复设置。WAL 模式确保写入不阻塞读取（满足 HARD_CONSTRAINTS REL-4-01）。每个表均提供单字段索引（`user_id` / `created_at` / `timestamp` / `status`）+ 组合索引（`(user_id, created_at DESC)` / `(metric_type, timestamp DESC)` 等周报核心查询路径），周报生成查询仅需索引字段即可返回，避免回表。

### 9.2 分页查询

周报生成器与 Dashboard 使用 `LIMIT + OFFSET` 分页，示例：

```python
def query_experience_paged(conn, metric_type, page=1, page_size=50):
    offset = (page - 1) * page_size
    return conn.execute(
        "SELECT * FROM metrics_experience WHERE metric_type = ? "
        "ORDER BY timestamp DESC LIMIT ? OFFSET ?",
        (metric_type, page_size, offset)).fetchall()
```

### 9.3 性能基准

| 查询场景 | 数据量 | 目标耗时 | 验证方式 |
|----------|--------|----------|----------|
| 单次 record_xxx 写入 | 0 行 | <5ms | 单元测试计时 |
| 按用户查询激活记录 | 1000 行 | <50ms | EXPLAIN QUERY PLAN |
| 周报 7 日数据聚合 | 1000 行 | <100ms | 集成测试计时 |
| 视图查询激活率 | 1000 行 | <100ms | 性能测试脚本 |
| 分页查询体验指标 | 1000 行 | <50ms | 分页测试 |

---

## 10. 验证标准

### 10.1 DDL 可执行性

- [ ] 5 张表 `CREATE TABLE` 可执行，幂等（重复执行不报错）
- [ ] 14 个索引 `CREATE INDEX` 创建成功（含 5 个组合索引）
- [ ] 1 个触发器 `trg_activation_updated_at` 创建成功
- [ ] 6 个汇总视图 + 5 个脱敏视图 `CREATE VIEW` 创建成功

### 10.2 视图查询正确性

- [ ] `view_activation_rate` / `view_upgrade_rate` 返回总数 + 转化数 + 百分比三列
- [ ] `view_flywheel_rate` 仅统计每用户最新飞轮级别（`ROW_NUMBER() OVER` 取最新）
- [ ] `view_payment_rate` 正确计算付费率与总金额
- [ ] `view_nps_score` 正确计算推荐者% - 贬损者%
- [ ] `view_experience_avg` 按 `metric_type` 分组返回均分

### 10.3 脱敏视图正确性

- [ ] 5 个脱敏视图均不含 `user_id` 字段
- [ ] `view_export_activation` / `view_export_payment` 不含 `metadata` 中可能泄漏的业务字段
- [ ] Python 层 `_anonymize_user_id()` 输出 16 字符 hex 串，且同一 `user_id` 多次调用输出一致

### 10.4 迁移脚本验证

- [ ] v7 → v8 迁移成功：`_meta.db_version` 更新为 8，`schema_version` 新增 `(8, 'metrics', '2026-07-19')` 记录，备份文件生成在 `data/backups/opc_data.db.v7.bak.{timestamp}` 路径
- [ ] 迁移失败时事务回滚，数据库恢复到 v7 状态
- [ ] 迁移脚本幂等：在已迁移的 v8 数据库上重复执行不报错

### 10.5 性能验证

- [ ] 1000 行数据查询 <100ms（见 §9.3 性能基准）；写入时不阻塞并发读取（WAL 模式）；视图查询使用索引而非全表扫描（`EXPLAIN QUERY PLAN` 验证）

### 10.6 E2E 验证（用户规则 3 要求，模拟真实用户使用）

- [ ] 完成引导 → 执行 3 次任务 → `metrics_activation` 出现 `activation_criteria_met=1` 记录
- [ ] 升级专业版 / 进入飞轮 L2 / 付费 → 对应 `metrics_upgrade` / `metrics_flywheel` / `metrics_payment` 出现记录，且对应视图数值更新
- [ ] 对话后评分 5 星 / 填写 NPS 9 分 → `metrics_experience` 出现对应 `metric_type` 记录，`view_nps_score` / `view_experience_avg` 计算正确
- [ ] 主动触发上报 → payload 不含 `user_id`，仅含 `anonymized_user_hash`

---

## 11. 风险与缓解

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 迁移失败导致数据丢失 | 高 | 步骤 2 强制备份 + 步骤 9 失败回滚恢复备份 |
| 视图性能不达标 / 触发器递归 | 中 | 组合索引覆盖查询路径（§9.1）；`WHEN NEW.updated_at = OLD.updated_at` 避免递归 |
| SQLite 无 SHA256 内置函数 | 中 | 脱敏逻辑由 Python 层 `hashlib` 实现，视图仅作字段集参考 |
| `metrics_experience` 数据膨胀 | 中 | 1 年保留期 + `cleanup_old_metrics.py` 定时清理 |
| v7 → v8 跳跃迁移风险 | 低 | 仅在 v7 基础上执行，`_check_current_version` 强制校验 |

---

## 12. 后续演进

| 版本 | 内容 | 关联 |
|------|------|------|
| v9 | metrics 表字段扩展（如 `metadata` 拆分为独立列） | 视实际使用反馈 |
| v10 | OpenTelemetry 导出层兼容（ADR-004 §2.4 / §5.3） | v0.6.0 路线图 |
| v11 | 跨设备指标同步（relay_client 已支持） | v0.7.0 评估 |

---

## 13. 相关文档

- [ADR-004-metrics-collection-design.md](ADR-004-metrics-collection-design.md) — 数据采集埋点架构设计（本文档为其 §3.5 的 P4 细化）
- [HARD_CONSTRAINTS.md](../HARD_CONSTRAINTS.md) S4 数据本地存储 / REL-4-01 WAL 模式
- [ROADMAP_v0.5.0.md](../ROADMAP_v0.5.0.md) §OKR-2 — 5 大商业指标 + 3 大体验指标定义
- 现有代码: `opc_manager/data_manager.py`（迁移机制）/ `opc_manager/audit_log.py`（v7 迁移风格参考）/ `opc_manager/onboarding.py`（激活率数据源）/ `opc_manager/flywheel_tracker.py`（飞轮率数据源）

---

## 附录: 7-Role 共识记录

| 角色 | 立场 | 关注点 | 解决方案 |
|------|------|--------|----------|
| Architect | 同意 | DDL 完整性 + 迁移幂等性 | §3 完整 DDL + §6 迁移脚本 |
| PM | 同意 | 指标口径对齐路线图 | §5 视图定义与 ADR-004 附录 A 对齐表一致 |
| Security | 同意 | 数据脱敏 + 备份回滚 | §7 脱敏视图 + §6.3 步骤 2/12 |
| Tester | 同意 | E2E 覆盖 + 性能基准 | §10.6 E2E 验证 + §9.4 性能基准 |
| Coder | 同意 | 脚本可执行 + 与现有机制集成 | §6.3 Python 伪代码 + §6.4 集成方式 |
| DevOps | 同意 | 备份策略 + 迁移失败处理 | §6.3 步骤 2 备份 + 步骤 12 回滚 |
| UI/UX | 同意 | 视图支持 Dashboard 展示 | §5 视图返回字段覆盖周报需求 |

> 术语定义见 ADR-004 附录 C，本文档不重复。
