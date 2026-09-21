# OPC-Agents v1.0.0 技术设计（TDD）

> **状态**: Draft — 需求已定义，进入架构设计阶段
> **日期**: 2026-08-01 | **版本**: v1.0.0
> **关联 PRD**: [PRD_V5.md](../product-manager/PRD_V5.md)
> **关联校准**: [PROMISELINK_API_CALIBRATION.md](../research/PROMISELINK_API_CALIBRATION.md)
> **评审角色**: Architect Lead，Security/Tester/Coder/DevOps/UI 协作

---

## 1. 设计原则

1. 保持三贤者、IntentRouter、CarryMem 和现有核心技能不变。
2. PromiseLink 是可选外部能力，不成为 OPC-Agents 核心可用性的单点依赖。
3. 不复制、不 fork PromiseLink 代码；使用明确的 HTTP API 客户端。
4. 不为未确认的 PromiseLink 路由编写实现。增强端点在 PromiseLink 项目组交付并验收后才接入。
5. 所有自动外部操作继续经过关键决策点和审计链。
6. 先实现最小闭环，再扩展自然语言和多平台能力。

---

## 2. 系统边界

```text
┌─────────────────────────────────────────────────────────┐
│ OPC-Agents                                               │
│                                                         │
│ IntentRouter → Three Sages → Scheduler/Skills          │
│       │                    │                            │
│       │                    ├─ email/finance/report     │
│       │                    ├─ crm                        │
│       │                    └─ PromiseLinkClient         │
│       │                                   │              │
│       └──────── CarryMem                 │ HTTP         │
└───────────────────────────────────────────┼─────────────┘
                                            ▼
┌─────────────────────────────────────────────────────────┐
│ PromiseLink v0.9.0（可选、独立部署）                      │
│ Entity / Event / Todo / Promise / Reminder / Brief       │
└─────────────────────────────────────────────────────────┘
```

### 2.1 数据所有权

- OPC-Agents 负责任务执行、邮件发送、财务数据、报告成果物和关键操作授权。
- PromiseLink 负责关系实体、事件管线、承诺、提醒、关系推进卡。
- 两个数据库独立；OPC-Agents 只保存 PromiseLink `entity_id` 等关联标识和必要摘要。
- 不复制 PromiseLink 原始 PII，除非用户主动导出或明确允许缓存。

---

## 3. PromiseLinkClient 设计

### 3.1 当前已确认路由

| 能力 | 方法与路径 | 使用策略 |
|------|-----------|---------|
| 健康检查 | `GET /api/v1/health` | 启用前探活 |
| 事件输入 | `POST /api/v1/events` | 触发完整异步管线 |
| 事件查询 | `GET /api/v1/events/{event_id}` | 轮询处理状态 |
| 客户列表 | `GET /api/v1/entities` | 搜索/过滤/分页 |
| 沉默客户 | `GET /api/v1/entities/dormant?min_days=N` | CRM 核心 |
| 客户详情 | `GET /api/v1/entities/{entity_id}` | CRM 详情 |
| 关系阶段 | `GET /api/v1/entities/{entity_id}/stage-info` | 生命周期 |
| 关系卡 | `GET /api/v1/persons/{entity_id}/relationship-brief/aggregated` | 客户详情 |
| Todo | `GET /api/v1/todos` | 跟进队列 |
| 承诺 | `GET /api/v1/promises` | 双向承诺 |
| 承诺统计 | `GET /api/v1/promises/stats` | 经营摘要 |
| 催促草稿 | `GET /api/v1/promises/{todo_id}/nudge-draft` | 仅草稿 |
| 每日提醒 | `GET /api/v1/reminders/daily` | 早报/提醒 |
| 提醒偏好 | `GET/PATCH /api/v1/reminders/preferences` | 疲劳控制 |
| 排程事件 | `POST/GET /api/v1/scheduled-events` | 单次排程 |
| 早报 | `GET /api/v1/dashboard/morning-brief` | 经营早报 |
| 关怀提醒 | `GET /api/v1/dashboard/care-reminders` | 关系维护 |

### 3.2 明确不使用的路径

以下路径在 PromiseLink v0.9.0 源码中不存在：

- `GET /api/v1/entities?dormant_days=N`
- `POST /api/v1/todos/analyze-bidirectional`
- `POST /api/v1/nudges/generate`

双向承诺分析当前只能通过 `POST /api/v1/events` 的异步管线触发；催促消息当前只能对已有 `todo_id` 调用 GET。

### 3.3 客户端职责

`PromiseLinkClient` 负责：

- URL 拼接和 API 版本约束
- Bearer Token 注入
- 超时、指数退避和 429 处理
- circuit breaker
- 响应 schema 最小校验
- trace_id 传递和调用耗时记录
- 将外部数据映射成 OPC-Agents 内部 DTO
- 失败返回显式状态，不吞掉用户可见原因

### 3.4 失败状态

```text
DISABLED       → 未启用
UNCONFIGURED   → 缺 URL/Token
AVAILABLE      → health 通过
DEGRADED       → 请求失败，使用本地能力
CIRCUIT_OPEN   → 连续失败，暂时停止请求
SCHEMA_MISMATCH→ 路由存在但响应契约不匹配，禁止继续处理
```

---

## 4. CRM 设计

### 4.1 本地领域模型

不直接复用 PromiseLink SQLAlchemy 模型。OPC-Agents 侧只定义：

- `CustomerReference(entity_id, display_name, source, last_synced_at)`
- `FollowupReference(todo_id, entity_id, status, source)`
- `RelationshipSnapshot(entity_id, payload, source, captured_at)`

### 4.2 CRM 读路径

```text
用户进入 CRM
    │
    ▼
PromiseLinkClient.is_available()
    │
    ├─ available → /entities 或 /entities/dormant
    │                → DTO 校验 → UI
    │
    └─ unavailable → OPC-Agents 本地 crm_skill
                       → UI 标明 local_fallback
```

### 4.3 写路径

v1.0.0 不在 PromiseLink 中创建独立 CRM 写入接口，优先使用已确认的事件管线：

```text
会议/名片/聊天输入
    │
    ▼
POST /api/v1/events
    │
    ▼
轮询 GET /api/v1/events/{event_id}
    │
    ▼
实体/Todo/承诺结果
    │
    ▼
用户确认低置信度结果
```

用户直接手动添加客户时，使用 OPC-Agents 本地 CRM；待 PromiseLink 提供标准 CRM 写接口后再评估双写。

---

## 5. Scheduler 设计

### 5.1 组件

- `SchedulerService`：调度循环和任务生命周期
- `ScheduleParser`：自然语言转换为受限调度结构
- `ScheduledTaskRepository`：SQLite 持久化
- `TaskExecutionRepository`：执行记录
- `ScheduledTaskRunner`：路由到技能并执行保护检查

### 5.2 任务状态

```text
DRAFT → ENABLED → RUNNING → SUCCEEDED
                   │       ├→ RETRYING → SUCCEEDED
                   │       └→ FAILED
                   ├→ BLOCKED_BY_CONSENSUS
                   ├→ PAUSED
                   └→ DISABLED
```

### 5.3 执行流程

```text
触发时间到达
   │
   ▼
加载任务 + 校验启用状态
   │
   ▼
IntentRouter 判断任务类型
   │
   ├─ email/report/finance → 三贤者/关键决策点
   │                         ├─ 通过 → 执行
   │                         └─ 超时/异常/否决 → fail-close
   │
   └─ 只读摘要/本地任务 → 直接执行
   │
   ▼
记录执行结果、耗时、重试、trace_id、审计
```

### 5.4 任务安全边界

- v1.0.0 自动任务默认只生成报告或草稿。
- 自动发送外部邮件默认关闭，必须显式授权且每次执行受保护。
- 不允许 scheduler 直接调用 SMTP、财务写入等底层接口绕过 Skill/Consensus 层。
- 任务参数限制大小和允许字段，禁止任意 Python 表达式或 shell 命令。

### 5.5 持久化表

```sql
CREATE TABLE scheduled_tasks (
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
);

CREATE TABLE task_executions (
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
);
```

### 5.6 关于 PromiseLink ScheduledEvent

PromiseLink v0.9.0 的 `/scheduled-events` 是**一次性排程事件**，不是 OPC-Agents 所需的复发 cron 任务后端。因此：

- OPC-Agents v1.0.0 自身持有复发任务调度和执行历史。
- PromiseLink ScheduledEvent 仅用于客户会议/通话等一次性关系事件。
- 不把 PromiseLink `/scheduled-events` 宣称为 cron 后端。
- 待 PromiseLink 实现 `cron_expression` 等增强接口后，再评估对接。

---

## 6. 关键数据流

### 6.1 客户输入到跟进

```text
用户粘贴会议纪要
  → POST PromiseLink /events
  → 轮询事件状态
  → 读取 entities/todos/promises
  → 用户确认低置信度项
  → CRM 关系卡展示
  → 生成 follow-up 草稿
  → 用户确认
  → email 技能 + 三贤者保护
```

### 6.2 每日早报

```text
Scheduler 触发
  → PromiseLink /dashboard/morning-brief
  → /entities/dormant
  → /promises/stats
  → /reminders/daily
  → 合并本地 finance/report 数据
  → 生成带来源的早报
  → 记录执行历史
```

---

## 7. 可观测性

每次外部调用记录：

- `trace_id`
- 服务名和路由模板（不记录 Token）
- HTTP 状态码
- 耗时
- 重试次数
- 降级原因
- schema 校验结果

Prometheus 指标建议：

- `opc_promiselink_requests_total{route,status}`
- `opc_promiselink_request_duration_seconds{route}`
- `opc_promiselink_fallback_total{reason}`
- `opc_scheduler_executions_total{task_type,status}`
- `opc_scheduler_consensus_blocked_total{task_type}`

---

## 8. 迁移与回滚

### 启用迁移

1. 新增配置但默认关闭。
2. 数据库迁移只新增 OPC-Agents 自身表。
3. 先启用只读端点：health/entities/dormant/brief/promises。
4. 再启用事件写入和跟进工作流。
5. 最后启用 scheduler；外部发送默认仍关闭。

### 回滚

- `PROMISELINK_ENABLED=false` 立即关闭外部调用。
- 保留本地 CRM、邮件、报告功能。
- scheduler 可独立暂停，不删除任务历史。
- schema mismatch 自动切换本地降级，不尝试猜测字段。

---

## 9. 未决事项

| 事项 | 负责人 | 阻塞版本 |
|------|--------|---------|
| PromiseLink 同步承诺分析接口 | PromiseLink 项目组 | v1.0.0 实时分析体验 |
| PromiseLink POST nudge 接口 | PromiseLink 项目组 | v1.0.0 无 todo 草稿 |
| PromiseLink quick entity extract | PromiseLink 项目组 | v1.0.0 实时实体提取 |
| PromiseLink recurring cron | PromiseLink 项目组 | v1.0.0 统一调度后端 |
| PromiseLink API schema/version discovery | 双方 | v1.0.0 正式集成 |

---

## 10. 设计验收

- [ ] 所有当前调用路径与 PromiseLink v0.9.0 源码一致
- [ ] 外部服务不可用时本地能力可用
- [ ] scheduler 不绕过三贤者和关键决策点
- [ ] 不复制 PromiseLink 数据库模型和代码
- [ ] 所有外部调用可观测且不泄露 Token/PII
- [ ] 真实 PromiseLink 实例通过 smoke 测试
- [ ] 数据迁移和回滚路径经过 E2E 验证

---

*文档状态：架构设计草案，不代表代码已实现。*