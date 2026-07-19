# ADR-004: 数据采集埋点架构设计

**版本**: v0.5.0-draft
**日期**: 2026-07-19
**状态**: 7-Role 共识
**决策者**: Architect Lead
**关联**: [ROADMAP_v0.5.0.md](../ROADMAP_v0.5.0.md) §OKR-2 / [SEED_USER_VALIDATION_PLAN.md](../spec/SEED_USER_VALIDATION_PLAN.md) §7 / [HARD_CONSTRAINTS.md](../HARD_CONSTRAINTS.md) S4

---

## 1. 背景（Context）

### 1.1 问题陈述

OPC-Agents v0.4.0 评估显示，路线图要求的 5 大商业指标与 3 大体验指标均处于 0 数据状态：

| 类别 | 指标 | v0.5.0 目标 | v0.4.0 现状 |
|------|------|-------------|-------------|
| 商业 | 激活率 | >60% | 0 数据 |
| 商业 | 升级率 | >30% | 0 数据 |
| 商业 | 飞轮率 | >15% | 0 数据 |
| 商业 | 付费率 | >10% | 0 数据 |
| 商业 | NPS | >50 | 0 数据 |
| 体验 | 对话自然度 | >4.5/5 | 0 数据 |
| 体验 | 结果满意度 | >4.5/5 | 0 数据 |
| 体验 | 主动服务度 | >4.5/5 | 0 数据 |

v0.5.0 必须完成上述 8 项指标的埋点采集，否则种子用户验证阶段无法用数据驱动产品迭代决策。

### 1.2 现有代码基础

经代码调研，已有以下可复用的采集入口，但缺乏统一的指标埋点框架：

| 模块 | 文件 | 已采集内容 | 缺口 |
|------|------|------------|------|
| OnboardingManager | `opc_manager/onboarding.py` | 状态机事件（INVITED→STARTED→COMPLETED） | 未关联"7 日内 3 次使用"激活定义 |
| SkillExecutors | `opc_manager/skill_executors.py` | 技能执行起点/终点 | 未采集任务结果满意度评分 |
| FlywheelTracker | `opc_manager/flywheel_tracker.py` | 4 级飞轮 + FlywheelTrackerDB 持久化 | 已采集但未对齐"飞轮率"统计口径 |
| ErrorHandler | `opc_manager/error_handler.py` | 错误类型与频率 | 仅用于错误监控，非指标采集 |
| AuditLog | `opc_manager/audit_log.py` | 链式哈希（SHA256）+ DB 迁移 v7 | 安全合规用途，非产品指标 |
| SQLite DB | `data/` 目录 | 本地存储已就绪 | 缺指标专用表 |

### 1.3 约束

- **数据本地存储**：HARD_CONSTRAINTS S4 规定数据从不出家门，埋点数据必须存本地 SQLite
- **性能不阻塞**：HARD_CONSTRAINTS REL-4-01 要求写入不阻塞读取，须使用 WAL 模式
- **YAGNI 原则**：v0.5.0 不引入 OpenTelemetry 等外部依赖，延后到 v0.6.0
- **用户同意**：脱敏数据上报须用户首次启动时主动同意（弹窗确认）
- **松耦合**：埋点逻辑不能污染现有业务模块的核心职责

## 2. 决策（Decision）

**新增 `opc_manager/metrics_collector.py` 模块作为统一埋点入口，承载 5 大商业指标 + 3 大体验指标的采集、本地持久化与可选脱敏上报。**

### 2.1 架构总览

```
+-----------------------------------------------------------------------+
|                       OPC-Agents 业务层                                |
|                                                                       |
|  +----------------+ +----------------+ +----------------+            |
|  | OnboardingMgr  | | FlywheelTracker| | SkillExecutors |            |
|  +-------+--------+ +-------+--------+ +-------+--------+            |
|          |                  |                  |                     |
|          | record_activation| record_flywheel  | record_experience   |
|          v                  v                  v                     |
|  +-------+------------------+------------------+--------+            |
|  |          MetricsCollector (统一埋点入口)               |            |
|  |  record_activation / record_upgrade / record_flywheel |            |
|  |  record_payment  / record_nps     / record_experience |            |
|  +-------+------------------+------------------+--------+            |
|          |                  |                  |                     |
|          v                  v                  v                     |
|  +-------+------------------+------------------+--------+            |
|  |                SQLite (WAL 模式)                       |            |
|  |  metrics_activation / metrics_upgrade / metrics_flywheel           |
|  |  metrics_payment   / metrics_nps     / metrics_experience         |
|  +-------------------+-------------------+----------------+          |
|                      |                   |                            |
|                      v                   v                            |
|              +-------+-----+     +-------+------+                    |
|              | 周报生成器  |     | 脱敏上报网关  |                    |
|              | (本地查看)  |     | (用户主动触发)|                    |
|              +-------------+     +--------------+                    |
+-----------------------------------------------------------------------+
```

### 2.2 5 大商业指标埋点

| 指标 | 触发事件 | 写入表 | 数据来源 |
|------|----------|--------|----------|
| 激活率 | OnboardingManager COMPLETED + 7 日内 ≥3 次使用 | `metrics_activation` | OnboardingManager + 任务计数器 |
| 升级率 | 基础版 → 专业版转化（基础版 relay_client 触发） | `metrics_upgrade` | relay_client 网关回调 |
| 飞轮率 | FlywheelTracker 达到 L2 及以上 | `metrics_flywheel` | FlywheelTracker（已有） |
| 付费率 | 试用 → 付费转化（专业版网关上报） | `metrics_payment` | 专业版网关 webhook |
| NPS | 每周问卷 + 任务完成后评分 | `metrics_nps` | Feedback API + UI 评分组件 |

### 2.3 3 大体验指标埋点

| 指标 | 触发事件 | 写入表 | 数据来源 |
|------|----------|--------|----------|
| 对话自然度 | 每次对话后 5 星评分 UI | `metrics_experience` | 前端评分组件 |
| 结果满意度 | 任务完成后 5 星评分 UI | `metrics_experience` | SkillExecutors 完成钩子 + 评分 UI |
| 主动服务度 | 周度问卷 + FlywheelTracker 主动建议接受率 | `metrics_experience` | FlywheelTracker 建议接受/拒绝事件 |

### 2.4 核心设计原则

1. **统一入口**：所有指标写入必须经 MetricsCollector，禁止业务模块直写 SQLite
2. **本地优先**：默认仅本地存储，上报须用户主动同意且脱敏
3. **松耦合**：MetricsCollector 不依赖 OnboardingManager 等业务模块的反向调用
4. **可扩展**：新增指标仅需添加 `record_xxx` 方法 + 对应表，不动核心框架

## 3. 方案细节

### 3.1 MetricsCollector API 设计

```python
class MetricsCollector:
    """统一埋点入口，所有指标采集经此写入 SQLite"""

    def __init__(self, db_path: str = None):
        """初始化 SQLite 连接（WAL 模式），创建缺失表"""

    def record_activation(
        self,
        user_id: str,
        activated: bool,
        days_since_invite: int,
        task_count_7d: int,
        metadata: dict = None,
    ) -> str:
        """记录激活事件，返回 record_id"""

    def record_upgrade(
        self,
        user_id: str,
        from_tier: str,  # "basic" / "trial"
        to_tier: str,    # "pro" / "enterprise"
        trigger: str,    # "relay_client" / "manual"
        metadata: dict = None,
    ) -> str:
        """记录版本升级事件"""

    def record_flywheel(
        self,
        user_id: str,
        level: int,      # 1-4
        action: str,     # "enter_level" / "complete_cycle"
        metadata: dict = None,
    ) -> str:
        """记录飞轮级别变化（与 FlywheelTracker 集成）"""

    def record_payment(
        self,
        user_id: str,
        plan: str,       # "monthly" / "yearly"
        amount_cents: int,
        currency: str = "CNY",
        metadata: dict = None,
    ) -> str:
        """记录付费转化事件"""

    def record_nps(
        self,
        user_id: str,
        score: int,      # 0-10
        channel: str,    # "weekly_survey" / "post_task"
        feedback: str = "",
        metadata: dict = None,
    ) -> str:
        """记录 NPS 评分"""

    def record_experience(
        self,
        user_id: str,
        metric: str,     # "dialogue_naturalness" / "result_satisfaction" / "proactive_service"
        score: float,    # 0.0-5.0
        channel: str,    # "post_dialogue" / "post_task" / "weekly_survey"
        metadata: dict = None,
    ) -> str:
        """记录 3 大体验指标评分"""

    def export_anonymized(self, since_date: str = None) -> dict:
        """导出脱敏数据（去除 user_id/business），用于用户主动上报"""
```

### 3.2 数据流

```
[业务事件发生]
      |
      v
[业务模块调用]  OnboardingManager.complete() ──> collector.record_activation(...)
      |         FlywheelTracker.enter_level() ──> collector.record_flywheel(...)
      |         SkillExecutors.complete()     ──> collector.record_experience(...)
      |         Feedback API (NPS 评分)       ──> collector.record_nps(...)
      |         relay_client 网关回调         ──> collector.record_upgrade(...)
      |         专业版网关 webhook             ──> collector.record_payment(...)
      v
[MetricsCollector.record_xxx()]
      |   - 参数校验 + 字段标准化
      |   - 生成 record_id (UUID v4)
      |   - 写入 SQLite (WAL 模式, 非阻塞)
      v
[SQLite metrics_xxx 表]
      |
      +─────> [周报生成器] 每周日 02:00 本地汇总 → 用户在 Dashboard 查看
      |
      +─────> [脱敏上报] 用户在设置页主动触发 → 去除 user_id/business →
                                       POST /v1/metrics (专业版网关, HTTPS)
```

### 3.3 与现有组件集成

| 现有组件 | 集成点 | 调用方式 |
|----------|--------|----------|
| OnboardingManager | `_transition_to(COMPLETED)` 之后 | `metrics_collector.record_activation(user_id, activated=True, ...)` |
| FlywheelTracker | `enter_level(level)` 内部 | `metrics_collector.record_flywheel(user_id, level=level, action="enter_level")` |
| SkillExecutors | `complete_task()` 末尾 | `metrics_collector.record_experience(user_id, metric="result_satisfaction", ...)` |
| 前端评分组件 | 用户点击 5 星后 | `Feedback API POST /v1/feedback` → 后端调 `record_experience` / `record_nps` |
| relay_client | 基础版升级触发 | 网关回调 `POST /v1/upgrade` → 后端调 `record_upgrade` |

集成遵循"调用方负责触发，MetricsCollector 负责写入"的单一职责原则。

### 3.4 数据脱敏

用户主动上报时执行以下脱敏处理：

| 字段 | 处理方式 |
|------|----------|
| `user_id` | 移除 |
| `business` | 移除 |
| `metadata.business_name` | 移除 |
| `metadata.ip` | 移除 |
| `score` / `metric` / `level` 等指标值 | 保留 |
| `record_id` | 替换为不可逆哈希（SHA256 + 项目 salt） |

首次启动时弹窗：

```
是否允许匿名上报指标数据用于产品改进？

数据将去除用户身份与商业信息，仅包含评分和指标值。
您可随时在设置页关闭或重新打开。

[同意并继续]  [暂不开启]
```

### 3.5 SQLite 表结构（DDL 草案，P4 阶段细化）

```sql
-- metrics_activation
CREATE TABLE IF NOT EXISTS metrics_activation (
    record_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    activated INTEGER NOT NULL,        -- 0/1
    days_since_invite INTEGER,
    task_count_7d INTEGER,
    metadata TEXT,                     -- JSON
    created_at TEXT NOT NULL           -- ISO8601
);

-- metrics_upgrade
CREATE TABLE IF NOT EXISTS metrics_upgrade (
    record_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    from_tier TEXT NOT NULL,
    to_tier TEXT NOT NULL,
    trigger TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT NOT NULL
);

-- metrics_flywheel
CREATE TABLE IF NOT EXISTS metrics_flywheel (
    record_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    level INTEGER NOT NULL,
    action TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT NOT NULL
);

-- metrics_payment
CREATE TABLE IF NOT EXISTS metrics_payment (
    record_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    plan TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    currency TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT NOT NULL
);

-- metrics_nps
CREATE TABLE IF NOT EXISTS metrics_nps (
    record_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    score INTEGER NOT NULL,            -- 0-10
    channel TEXT NOT NULL,
    feedback TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL
);

-- metrics_experience
CREATE TABLE IF NOT EXISTS metrics_experience (
    record_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    metric TEXT NOT NULL,              -- dialogue_naturalness / result_satisfaction / proactive_service
    score REAL NOT NULL,               -- 0.0-5.0
    channel TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_metrics_activation_user ON metrics_activation(user_id);
CREATE INDEX IF NOT EXISTS idx_metrics_upgrade_user ON metrics_upgrade(user_id);
CREATE INDEX IF NOT EXISTS idx_metrics_flywheel_user ON metrics_flywheel(user_id);
CREATE INDEX IF NOT EXISTS idx_metrics_payment_user ON metrics_payment(user_id);
CREATE INDEX IF NOT EXISTS idx_metrics_nps_user ON metrics_nps(user_id);
CREATE INDEX IF NOT EXISTS idx_metrics_experience_user ON metrics_experience(user_id);
CREATE INDEX IF NOT EXISTS idx_metrics_experience_metric ON metrics_experience(metric);
```

DDL 在 P4 阶段与 `FlywheelTrackerDB` 迁移逻辑合并，统一在 DB 迁移 v8 中执行。

## 4. 替代方案（Alternatives）

### 方案 A：复用 AuditLog 采集指标

**拒绝**。AuditLog 是安全合规用途（链式哈希、不可篡改、DB 迁移 v7 已固化），与产品指标混用会污染语义：
- 审计日志要求不可变，指标数据需要周期性聚合查询
- 审计日志每次写入都计算 SHA256，指标高频写入会有性能开销
- 审计日志字段（actor/action/resource）与指标字段（score/metric/level）结构不匹配

### 方案 B：使用 OpenTelemetry SDK

**拒绝**。v0.5.0 遵循 YAGNI 原则：
- OpenTelemetry 引入 opentelemetry-api / opentelemetry-sdk / opentelemetry-exporter 等多个依赖
- 现有 SQLite + WAL 已满足本地存储需求
- 分布式追踪场景在单机本地产品中无收益
- 延后到 v0.6.0 评估导出层兼容 OpenTelemetry 格式

### 方案 C：独立 metrics_collector 模块（采纳）

**采纳**。理由：
- 单一职责：MetricsCollector 仅负责指标采集，不承担审计或错误处理
- 松耦合：通过 `record_xxx` API 与现有组件集成，不修改现有组件核心逻辑
- 可演进：v0.6.0 可在 MetricsCollector 之上增加 OpenTelemetry 导出器，不影响业务层

## 5. 后果（Consequences）

### 5.1 正面影响

- **统一埋点入口**：8 项指标采集逻辑收敛到单一模块，便于维护与测试
- **松耦合**：OnboardingManager / FlywheelTracker / SkillExecutors 仅调用 `record_xxx`，不感知存储细节
- **本地存储合规**：满足 HARD_CONSTRAINTS S4 "数据从不出家门"约束
- **可扩展**：新增指标仅需添加方法与表，不动核心框架
- **数据驱动**：周报生成器可基于 `metrics_xxx` 表生成 v0.5.0 验证报告

### 5.2 负面影响

- **新增模块**：增加 `opc_manager/metrics_collector.py`（预计 400-600 行）
- **新增 5 张 SQLite 表**：DB 迁移 v8 需同步推进，FlywheelTrackerDB 现有数据需迁移到 `metrics_flywheel`
- **新增 6 个 record_xxx 方法**：每个方法需独立单元测试，测试代码量增加
- **业务模块需插入调用点**：OnboardingManager / FlywheelTracker / SkillExecutors 等需在关键节点插入 `record_xxx` 调用

### 5.3 中性影响

- **MetricsCollector v0.6.0 演进**：需在 v0.6.0 支持指标导出（OpenTelemetry 兼容格式），届时 API 保持不变，新增 export 层
- **上报网关协议**：脱敏上报接口由专业版网关定义，本架构仅负责生成脱敏 payload，不约束网关实现

## 6. 风险与缓解

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 数据隐私泄露 | 高 | 本地存储 + 用户首次启动弹窗同意 + 脱敏上报（去除 user_id/business） |
| 性能影响（写入阻塞读取） | 中 | SQLite WAL 模式，写入不阻塞读取（HARD_CONSTRAINTS REL-4-01） |
| 埋点准确性 | 中 | 单元测试覆盖每个 record_xxx 方法，覆盖率 ≥80% |
| 业务模块耦合度上升 | 中 | MetricsCollector 仅暴露 record_xxx API，业务模块单向调用 |
| DB 迁移失败 | 中 | 迁移 v8 在 FlywheelTrackerDB 现有迁移逻辑上扩展，单元测试覆盖升级路径 |
| 用户拒绝上报 | 低 | 默认本地存储，上报为可选项，不影响采集与周报生成 |
| metadata 字段膨胀 | 低 | metadata 仅存 JSON 字符串，单条上限 4KB，超长截断并记录警告 |

## 7. 验证标准

### 7.1 功能验证

- [ ] 5 大商业指标各有对应 `record_xxx` 方法（activation / upgrade / flywheel / payment / nps）
- [ ] 3 大体验指标通过 `record_experience` 统一采集，metric 字段区分 3 种
- [ ] 数据本地存储到 SQLite，不上传到任何外部服务
- [ ] 用户可在设置页主动触发脱敏上报
- [ ] 脱敏上报的 payload 不含 user_id / business 字段
- [ ] 首次启动弹窗询问用户是否同意匿名上报
- [ ] 与 OnboardingManager / FlywheelTracker / SkillExecutors 集成调用链可工作

### 7.2 质量验证

- [ ] 单元测试覆盖率 ≥80%（每个 record_xxx 方法独立测试）
- [ ] 集成测试覆盖 MetricsCollector 与 OnboardingManager / FlywheelTracker / SkillExecutors 的调用链
- [ ] E2E 测试覆盖"用户完成任务 → 评分 → 数据写入 SQLite → 周报显示"完整链路
- [ ] DB 迁移 v8 在已有 v7 数据库上可平滑升级

### 7.3 性能验证

- [ ] 单次 record_xxx 写入延迟 <5ms（WAL 模式）
- [ ] 写入时不阻塞并发读取
- [ ] 周报生成查询 7 日数据 <200ms

## 8. 实施计划（P4 阶段细化）

| 阶段 | 任务 | 产出 |
|------|------|------|
| P4.1 | 实现 MetricsCollector 类骨架 + 6 个 record_xxx 方法 | `opc_manager/metrics_collector.py` |
| P4.2 | DB 迁移 v8：新增 5 张 metrics 表 + FlywheelTracker 数据迁移 | 迁移脚本 |
| P4.3 | 集成 OnboardingManager / FlywheelTracker / SkillExecutors | 集成调用点 |
| P4.4 | 前端评分组件 + Feedback API | UI + API |
| P4.5 | 脱敏上报网关客户端 + 首次启动弹窗 | 上报流程 |
| P4.6 | 单元测试 + 集成测试 + E2E 测试 | 测试用例 |
| P4.7 | 周报生成器 + Dashboard 展示 | 周报功能 |

## 9. 相关文档

- [ROADMAP_v0.5.0.md](../ROADMAP_v0.5.0.md) §OKR-2 — 5 大商业指标 + 3 大体验指标定义与目标
- [SEED_USER_VALIDATION_PLAN.md](../spec/SEED_USER_VALIDATION_PLAN.md) §7 数据采集机制 — 种子用户验证阶段的数据采集要求
- [HARD_CONSTRAINTS.md](../HARD_CONSTRAINTS.md) S4 数据本地存储 — 数据从不出家门约束
- [HARD_CONSTRAINTS.md](../HARD_CONSTRAINTS.md) REL-4-01 — SQLite WAL 模式性能约束
- 现有代码：
  - [onboarding.py](../../opc_manager/onboarding.py) — OnboardingManager 状态机
  - [flywheel_tracker.py](../../opc_manager/flywheel_tracker.py) — FlywheelTracker 4 级 + DB
  - [skill_executors.py](../../opc_manager/skill_executors.py) — 技能执行起点终点
  - [audit_log.py](../../opc_manager/audit_log.py) — 审计日志（拒绝复用的对比对象）
  - [error_handler.py](../../opc_manager/error_handler.py) — 错误处理
- 相关 ADR：
  - [ADR-001](ADR-001-IntentRouter-design.md) — IntentRouter 设计
  - [ADR-002](ADR-002-ToolSystem-design.md) — ToolSystem 设计
  - [ADR-003](ADR-003-TaskEngineV3-design.md) — TaskEngineV3 Mixin 设计

---

## 附录 A：指标定义对齐表

| 指标 | 路线图定义 | 埋点实现口径 |
|------|------------|--------------|
| 激活率 | 完成引导 + 7 日内 ≥3 次使用 | `metrics_activation.activated=1` 且 `task_count_7d>=3` |
| 升级率 | 基础版 → 专业版转化 | `metrics_upgrade.from_tier='basic' AND to_tier='pro'` |
| 飞轮率 | 达到飞轮 L2 及以上 | `metrics_flywheel.level>=2 AND action='enter_level'` |
| 付费率 | 试用 → 付费转化 | `metrics_payment` 表中存在记录的用户占比 |
| NPS | 推荐者% - 贬损者% | `metrics_nps.score>=9` 占比 减 `score<=6` 占比 |
| 对话自然度 | 5 星评分 | `metrics_experience.metric='dialogue_naturalness'` 均值 |
| 结果满意度 | 5 星评分 | `metrics_experience.metric='result_satisfaction'` 均值 |
| 主动服务度 | 周度问卷 + 建议接受率 | `metrics_experience.metric='proactive_service'` 均值 |

## 附录 B：7-Role 共识记录

| 角色 | 立场 | 关注点 | 解决方案 |
|------|------|--------|----------|
| Architect | 同意 | 模块边界清晰 | MetricsCollector 单一职责 |
| PM | 同意 | 指标口径对齐路线图 | 附录 A 对齐表 |
| Security | 同意 | 数据隐私合规 | 本地存储 + 脱敏上报 + 弹窗同意 |
| Tester | 同意 | 测试覆盖 | 单元测试 ≥80% + E2E 链路覆盖 |
| Coder | 同意 | 实现成本 | P4 阶段分 7 步推进 |
| DevOps | 同意 | DB 迁移风险 | 迁移 v8 在 v7 基础上扩展 |
| UI/UX | 同意 | 评分组件体验 | 5 星 UI + 首次启动弹窗 |

## 附录 C：术语表

| 术语 | 含义 |
|------|------|
| 埋点 | 在代码关键节点插入数据采集调用，记录用户行为与业务事件 |
| 激活 | 用户完成 Onboarding 且 7 日内至少 3 次使用 |
| 飞轮 | FlywheelTracker 4 级循环（L1→L4），L2 及以上视为飞轮启动 |
| NPS | Net Promoter Score，推荐者% 减 贬损者%，范围 -100 到 +100 |
| WAL | Write-Ahead Logging，SQLite 写入不阻塞读取的日志模式 |
| 脱敏 | 移除或哈希处理可识别用户身份与商业信息的字段 |
