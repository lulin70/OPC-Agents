# 产品定位矛盾解决方案（v1.0.0 更新版）

> **版本**: v1.0.0 | **日期**: 2026-08-01 | **状态**: PM 主导，7-Role 共识
> **依据**: [OPC 市场调研](../research/OPC_MARKET_RESEARCH_REPORT.md) + [PromiseLink API 校准](../research/PROMISELINK_API_CALIBRATION.md) + [PRD_V5.md](../product-manager/PRD_V5.md)
> **上一版**: [v0.5.0 版本](POSITIONING_RESOLUTION.md)
> **目的**: 在 v1.0.0 阶段解决 PRD/技能/实际能力之间的对齐，并明确 v1.0.0 CRM 解冻和定时主动执行的实施策略

---

## 〇、问题陈述

### 0.1 v0.5.0 阶段的解决现状

| 已解决问题 | 状态 |
|----------|------|
| PRD_V4 与 SKILL_FREEZE_LIST 矛盾 | ✅ PRD_V4.1 已统一表述 |
| 解冻决策框架缺失 | ✅ v0.5.0 已建立"≥2 种子用户反馈"决策矩阵 |
| 文档可信度问题 | ✅ PRD + FreezeList + UserStories 三文档已同步 |

### 0.2 v1.0.0 阶段的新矛盾

基于市场调研和 PromiseLink API 校准，v1.0.0 阶段出现新的对齐问题：

| # | 矛盾点 | 旧表述 | v1.0.0 调整 |
|---|--------|-------|-----------|
| 1 | CRM 解冻路径 | 依赖种子用户反馈 | 基于市场调研（22h/周节省目标）主动解冻 |
| 2 | 主动执行能力 | v0.5.0 文档未涉及 | v1.0.0 新增 L3 定时主动执行 |
| 3 | PromiseLink 集成 | 未在 PRD 中提及 | v1.0.0 明确集成策略（HTTP API + 优雅降级）|
| 4 | 关键决策点保护 | 仅覆盖 email/report/finance | 扩展到 cron 触发任务 |
| 5 | 用户反馈驱动 vs 市场驱动 | 种子用户反馈 | 双向驱动：市场调研 + 种子用户 |

### 0.3 影响

- 产品方向：从"被动响应"升级为"主动运营"——这是从工具到助手的根本转变
- 技术债务：CRM 半冻结状态阻碍 22h/周节省目标的 50%（CRM 占 4h）
- 外部依赖：PromiseLink API 路径未校准时集成代码可能错误
- 风险：定时自动执行可能绕过用户掌控

---

## 一、矛盾根因分析

### 1.1 5-Why 分析

```
v1.0.0 新矛盾：产品愿景（主动运营助手）与当前能力（被动响应工具）脱节

Why 1: 为什么 v1.0.0 出现新矛盾？
→ 因为市场调研显示 v0.5.0 的 3 核心技能只能覆盖 7.5h/周（22h/周目标的 34%）

Why 2: 为什么市场调研与 v0.5.0 状态存在 14.5h/周差距？
→ 因为 CRM（4h）+ 定时主动执行（5h）+ 内容发布（5h）+ 线索资格化（3h）等能力缺失

Why 3: 为什么这些能力在 v0.5.0 之前被冻结？
→ 因为 v0.3.0 质量优先收缩导致 CRM/task_manager 半冻结，主动执行能力未设计

Why 4: 为什么半冻结状态持续到 v0.5.9？
→ 因为解冻依赖种子用户反馈，但用户必须先有可用能力才能反馈

Why 6 (根因): 
   缺少"基于市场调研主动解冻 + 种子用户验证"的解冻机制
```

### 1.2 根因总结

- **根本原因**：解冻机制设计为"用户驱动单向反馈"，但用户需先有可用能力才能反馈
- **次要原因**：
  - CRM/task_manager 半冻结状态阻碍新能力构建
  - PromiseLink 集成路径未基于源码校准
  - 定时主动执行（L3）作为全新能力需要单独设计

---

## 二、7-Role 共识评估

### 2.1 PM 角度

| 评估项 | 决策 |
|--------|------|
| 产品方向 | v1.0.0 必须从"被动响应"升级到"主动运营" |
| 解冻路径 | CRM 主动解冻（市场调研驱动），task_manager 推迟到 v1.1.0（风险更可控）|
| 用户验证 | CRM 解冻后通过种子用户验证 |
| 集成策略 | PromiseLink 通过 HTTP API 集成（不复制代码、不 fork）|

### 2.2 Architect 角度

| 评估项 | 决策 |
|--------|------|
| 架构影响 | 三贤者架构不动；新增 scheduler 模块；新增 promiselink_client 模块 |
| 技术可行性 | 基于 Python `schedule` 库 + SQLite 持久化；HTTP 客户端 + circuit breaker |
| 风险评估 | 中风险：cron 自动执行可能误操作 → 必须经关键决策点保护 |
| 依赖关系 | PromiseLink 数据独立，避免双产品耦合 |

### 2.3 Security 角度

| 评估项 | 决策 |
|--------|------|
| 自动执行权限 | cron 任务涉及 email/report/finance 必须经关键决策点 fail-close |
| 外部依赖 | PromiseLink API Token Fernet 加密存储 |
| 数据隔离 | OPC-Agents 与 PromiseLink 数据库独立 |
| 审计 | cron 任务执行必须写入审计日志 |
| 隐私 | 数据导出需明确用户确认；Token 不进入日志 |

### 2.4 Tester 角度

| 评估项 | 决策 |
|--------|------|
| 测试覆盖 | CRM 解冻需补齐 ≥80% 覆盖率 |
| 新增 E2E | scheduler 30 + PromiseLink 30 + CRM 40 = 100+ 新测试 |
| 真实验证 | 必须用真实 PromiseLink 实例做 smoke 测试（不能只用 Mock）|
| 时间维度测试 | scheduler 需要时间模拟（freezegun）|

### 2.5 Coder 角度

| 评估项 | 决策 |
|--------|------|
| CRM 解冻 | 3-4 天（移除 frozen 标记 + 补测试 + 解锁方法）|
| Scheduler 开发 | 5-7 天（基于 schedule 库 + 持久化 + 三贤者保护）|
| PromiseLink Client | 3-5 天（HTTP 客户端 + retry + circuit breaker）|
| 文档同步 | 0.5 天 |

### 2.6 DevOps 角度

| 评估项 | 决策 |
|--------|------|
| 数据持久化 | scheduler 表 scheduled_tasks + task_executions |
| 部署 | PromiseLink 集成可选，默认关闭；用户启用时检测 |
| 监控 | scheduler 任务执行监控（Prometheus metrics）|
| 备份 | scheduled_tasks 表自动备份到 data/backup/ |

### 2.7 UI Designer 角度

| 评估项 | 决策 |
|--------|------|
| 新增页面 | CRM 标签页 + 定时任务页 |
| 视图组件 | 集成 PromiseLink RelationshipBrief 12 模块视图 |
| i18n | 新增 60 个键（中文/英文/日文）|
| Morandi 配色 | 维持 |

### 2.8 共识结论

> **7-Role 共识 7/7 通过**

| 共识项 | 决策 |
|--------|------|
| v1.0.0 定位 | OPC 主动运营助手（从被动工具升级）|
| CRM 解冻 | v1.0.0 主动解冻（市场驱动），task_manager 推迟到 v1.1.0 |
| 主动执行 | 新增 scheduler 模块 + cron 化任务 |
| PromiseLink 集成 | HTTP API 模式 + 可选启用 + 优雅降级 |
| 关键决策点 | cron 任务涉及 email/report/finance 必须经三贤者保护 |

---

## 三、解决方案

### 3.1 总体策略

**"主动解冻 + L3 主动执行 + 现有工具集成"**

```
v0.5.9 (2026-07-31)        v1.0.0 (本方案)
──────────────              ──────────────
3 核心技能                   5 核心技能（含 CRM + report）
被动响应工具                 主动运营助手
单 LLM 后端                  L1-L5 路由（含 cron 化 L3）
无外部集成                   PromiseLink HTTP 集成
```

### 3.2 三层解决方案

#### Layer 1：CRM 主动解冻（v1.0.0 立即执行）

**解冻原则**：
- v0.5.0 阶段依赖"用户反馈驱动"，但 v1.0.0 市场调研已经提供明确需求
- CRM 在 v1.0.0 主动解冻，并发种子用户验证

**解冻范围**：
- 移除 `crm_skill.py` 的 frozen 标记
- 解锁所有方法（add_customer/update_customer/get_customer/list_customers/add_interaction/list_interactions/add_followup_reminder/...）
- 集成 PromiseLink DormantScanner 替换/增强 get_silent_customers
- 补齐测试覆盖率 ≥80%

**风险控制**：
- 集成默认关闭（`PROMISELINK_ENABLED=false`）
- 本地 CRM 降级能力完整保留
- 测试覆盖率门禁：未达 80% 不允许合并

#### Layer 2：L3 主动执行能力（v1.0.0 立即执行）

**新增模块**：
- `opc_manager/scheduler.py`：基于 Python `schedule` 库
- `scheduled_tasks` 表：cron 表达式 + 任务类型 + 参数 + 启用状态
- `task_executions` 表：执行历史 + 状态 + 结果

**安全保护**：
- cron 任务涉及 email/report/finance 必须经三贤者共识
- 关键决策点保护覆盖 cron 触发路径
- 失败重试 3 次（指数退避）
- 静默时段 22:00-08:00 不执行

**用户体验**：
- 自然语言创建："每周一 9:00 生成营销周报"
- 手动触发、单次触发、启停
- 执行历史可视化

#### Layer 3：PromiseLink 集成（v1.0.0 立即执行）

**集成模式**：
- HTTP API 客户端（`opc_manager/promiselink_client.py`）
- 配置：`PROMISELINK_ENABLED` + `PROMISELINK_API_URL` + `PROMISELINK_API_TOKEN`
- 默认关闭，Settings 页面配置启用

**优雅降级**：
- API 不可用 → 静默降级到 OPC-Agents 自身能力
- retry + circuit breaker（5 次失败后熔断 30 秒）
- 配置缺失时明确提示

**已校准的 API 路径**（基于 [PROMISELINK_API_CALIBRATION.md](../research/PROMISELINK_API_CALIBRATION.md)）：
- 客户管理 5 个端点（`/entities`, `/entities/dormant`, `/entities/{id}/stage-info`, `/persons/{id}/relationship-brief/aggregated`）
- 客户跟进 4 个端点（`/todos`, `/promises`, `/promises/stats`, `/promises/{todo_id}/nudge-draft`）
- 定时任务 1 个端点（`/scheduled-events` POST/GET）
- 报告/摘要 3 个端点（`/dashboard/morning-brief`, `/dashboard/care-reminders`, `/reminders/daily`）

### 3.3 解冻决策矩阵（v1.0.0 更新）

| 技能 | v0.5.0 状态 | v1.0.0 决策 | 依据 |
|------|------------|------------|------|
| email | ✅ 活跃 | ✅ 维持活跃 | 已是核心 |
| finance | ✅ 活跃 | ✅ 维持活跃 | 已是核心 |
| report | ✅ 活跃 | ✅ 维持活跃 | 已是核心 |
| crm | 🔶 半冻结 | ✅ **主动解冻** | 市场调研（4h/周节省）+ 用户硬约束 |
| task_manager | 🔶 半冻结 | ⏸️ **推迟到 v1.1.0** | 风险更高，需独立设计 |
| 其他 6 个冻结技能 | ❌ 冻结 | ❌ 维持冻结 | 待种子用户反馈 |

### 3.4 PRD 与现状同步机制

**v1.0.0 同步机制**：
- PRD_V5.md 替代 PRD_V4.1 作为 v1.0.0 文档基础
- SKILL_FREEZE_LIST 更新为 v1.0.0 版本
- USER_STORIES.md 新增 8 个核心用户故事
- 每次发布前 PM 必须检查 PRD 与现状一致性

**长期机制**：
- 每版本发布前同步更新 PRD、SKILL_FREEZE_LIST、USER_STORIES
- 活文档原则：PRD 与代码必须一致

---

## 四、v1.0.0 具体决策

### 4.1 CRM 主动解冻

**当前状态**：半冻结（仅 `get_customer/get_customer_stats/get_silent_customers` 3 方法维护）

**v1.0.0 决策**：
- ✅ 主动解冻（市场调研驱动 + 用户硬约束）
- ✅ 移除 frozen="semi" 标记
- ✅ 解锁所有方法
- ✅ 集成 PromiseLink DormantScanner（已校准 `/entities/dormant?min_days=`）
- ✅ 12 模块关系推进卡视图（已校准 `/persons/{id}/relationship-brief/aggregated`）
- ✅ 测试覆盖率 ≥80%

**v1.0.0 新增 CRM 方法**：
- `add_customer`（CRM-01 添加客户档案）
- `update_customer`（CRM-02 更新客户档案）
- `list_customers`（CRM-03 客户列表查询，支持分页/搜索/过滤）
- `add_interaction`（CRM-04 合作记录）
- `list_interactions`（合作记录查询）
- `add_followup_reminder`（CRM-05 跟进提醒）
- `lifecycle_tracker`（CRM-06 客户生命周期，集成 PromiseLink `/entities/{id}/stage-info`）

**工作量估算**：
- 解冻 + 解锁方法：0.5 天
- 补齐测试：2-3 天
- 集成 PromiseLink：1 天
- 文档同步：0.5 天
- E2E 验证：0.5 天
- **总计**：4-5 天

### 4.2 L3 主动执行能力（全新）

**当前状态**：v0.5.9 无主动执行能力

**v1.0.0 决策**：
- ✅ 新增 `opc_manager/scheduler.py` 模块
- ✅ 基于 Python `schedule` 库 + SQLite 持久化
- ✅ 关键决策点保护（email/report/finance 自动触发 fail-close）
- ✅ 失败重试 + 静默时段
- ✅ UI 新增"定时任务"页面
- ✅ Apple Shortcuts 扩展（新增 4 个动作）

**关键设计**：
- 任务存储：`scheduled_tasks` 表（id/cron_expression/task_type/params/enabled）
- 执行历史：`task_executions` 表（id/task_id/executed_at/result/retry_count）
- 调度器：单线程 scheduler + 持久化恢复
- 关键决策点：cron 任务执行器必须在调用 email/report/finance 前经过三贤者共识

**工作量估算**：
- scheduler 模块开发：3 天
- 持久化 + 监控：1 天
- 关键决策点保护：1 天
- UI 页面 + Apple Shortcuts：2 天
- 文档同步：0.5 天
- **总计**：7-8 天

### 4.3 PromiseLink 集成

**当前状态**：未集成

**v1.0.0 决策**：
- ✅ HTTP API 客户端（`opc_manager/promiselink_client.py`）
- ✅ 集成 12 个核心端点（已校准）
- ✅ 优雅降级（API 不可用时本地能力接管）
- ✅ 配置加密 + circuit breaker
- ✅ UI 集成状态显示

**已校准的 12 个核心端点**：
1. `GET /api/v1/entities` — 客户列表
2. `GET /api/v1/entities/{entity_id}` — 客户详情
3. `GET /api/v1/entities/dormant?min_days=N&limit=N` — 沉默客户
4. `GET /api/v1/entities/{entity_id}/stage-info` — 关系阶段
5. `GET /api/v1/persons/{entity_id}/relationship-brief/aggregated` — 12 模块视图
6. `GET /api/v1/todos` — 任务列表
7. `GET /api/v1/promises` — 承诺列表
8. `GET /api/v1/promises/stats` — 履约统计
9. `GET /api/v1/promises/{todo_id}/nudge-draft` — 催促消息草稿
10. `POST /api/v1/scheduled-events` — 创建排程事件
11. `GET /api/v1/dashboard/morning-brief` — 每日晨间摘要
12. `GET /api/v1/dashboard/care-reminders` — 关怀提醒

**请求 PromiseLink 项目组的增强**（10 项提案）见 [PROMISELINK_API_CALIBRATION.md §六](../research/PROMISELINK_API_CALIBRATION.md)。

**工作量估算**：
- HTTP 客户端 + retry + circuit breaker：2 天
- 12 个端点封装：1 天
- 优雅降级集成：1 天
- UI 配置页面：1 天
- 文档 + 测试：0.5 天
- **总计**：5-6 天

### 4.4 task_manager 推迟到 v1.1.0

**决策依据**：
- task_manager 解冻工作量与 CRM 相当，但风险更高
- v1.0.0 阶段已经包含 CRM + scheduler + PromiseLink 集成 3 大新增能力
- 分散风险：v1.1.0 单独解冻 task_manager

**v1.1.0 任务**：
- 移除 frozen="semi" 标记
- 解锁所有方法
- 补齐测试覆盖率 ≥80%
- 与 PromiseLink Todo 系统集成

---

## 五、PRD_V5 同步更新

### 5.1 必须更新项

| PRD_V4.1 章节 | 旧内容 | PRD_V5 更新 |
|--------------|-------|------------|
| §1.2 产品定位 | 一人公司全栈运营系统（愿景）| OPC 主动运营助手（v1.0.0 实施中）|
| §1.3 P0 技能 | 5 P0（含 task_manager 半冻结）| 6 P0（email/finance/report/crm/task_manager/scheduler），crm v1.0.0 主动解冻 |
| §1.5 当前阶段 | 用户验证 + 解冻评估 | 主动解冻 + L3 主动执行 + PromiseLink 集成 |
| §3.6 PromiseLink 集成 | 未涉及 | 新增章节（HTTP API + 优雅降级）|

### 5.2 新增章节

#### PRD_V5 §3.5 F-INTEGRATION：PromiseLink 集成

```
F-INTEGRATION 需求：
- F-INT-01 可选启用
- F-INT-02 配置加密保存
- F-INT-03 健康检查
- F-INT-04 retry + circuit breaker
- F-INT-05 本地降级
- F-INT-06 API 路由校准（基于 [PROMISELINK_API_CALIBRATION.md](../research/PROMISELINK_API_CALIBRATION.md)）
- F-INT-07 调用审计
```

#### PRD_V5 §3.3 F-SCHEDULE：主动执行

```
F-SCHEDULE 需求：
- F-SCHEDULE-01 自然语言创建
- F-SCHEDULE-02 重复任务支持
- F-SCHEDULE-03 启停/编辑/手动运行
- F-SCHEDULE-04 执行历史 + 重试
- F-SCHEDULE-05 关键技能任务进入三贤者
- F-SCHEDULE-06 静默时段 + 疲劳阈值
```

---

## 六、文档同步清单

| 文档 | 同步内容 | 状态 |
|------|---------|------|
| [PRD_V5.md](../product-manager/PRD_V5.md) | 新增 6 大功能需求 | ✅ |
| [PROMISELINK_API_CALIBRATION.md](../research/PROMISELINK_API_CALIBRATION.md) | 67 个路由逐项校准 | ✅ |
| [PROMISELINK_REUSE_PLAN.md](../research/PROMISELINK_REUSE_PLAN.md) | 路径修正 + 10 项增强提案 | ✅ |
| [SKILL_FREEZE_LIST.md](SKILL_FREEZE_LIST.md) | 标记 crm 主动解冻 | 🔄 待更新 |
| [USER_STORIES.md](../product-manager/USER_STORIES.md) | 新增 8 个核心用户故事 | 🔄 待更新 |
| [TECHNICAL_DESIGN.md](../technical/TECHNICAL_DESIGN.md) | 新增 scheduler + promiselink_client 模块设计 | 🔄 待更新 |
| [TEST_PLAN.md](../test/test_plan.md) | 新增 100+ E2E 测试计划 | 🔄 待更新 |
| [SECURITY_REVIEW.md](../security/SECURITY_REVIEW.md) | 评估 cron + PromiseLink 安全风险 | 🔄 待更新 |
| [DEPLOYMENT.md](../operations/DEPLOYMENT.md) | cron 持久化 + PromiseLink 部署 | 🔄 待更新 |

---

## 七、v1.0.0 验收标准

### 必须满足

- [ ] CRM 6 个方法可用 + 12 模块关系推进卡视图
- [ ] 定时任务可在 UI 创建/启停/编辑，执行历史完整
- [ ] email/report/finance cron 任务无法绕过共识
- [ ] PromiseLink 集成可启用可关闭，关闭时本地能力完整
- [ ] 真实 PromiseLink 实例 smoke 测试通过
- [ ] 真实浏览器用户旅程 E2E 通过
- [ ] 12 个核心端点路由与 PromiseLink 源码一致
- [ ] 现有门禁（ruff/mypy/coverage/E2E/Bandit/pip-audit/Docker）不回退
- [ ] CRM 测试覆盖率 ≥80%

### 不接受

- 用 Mock 单元测试替代真实 API/浏览器 E2E
- 用 skip 隐藏失败
- 使用未经源码确认的路由
- 自动发送未经用户确认的外部邮件
- 未经用户确认触发关键决策点保护下的自动任务

---

## 八、变更记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-07-19 | v0.5.0 | 初版（解决 PRD_V4 vs SKILL_FREEZE_LIST 矛盾）|
| 2026-08-01 | v1.0.0 | 更新版（CRM 主动解冻 + L3 主动执行 + PromiseLink 集成）|

---

## 九、参考

- [PRD_V5.md](../product-manager/PRD_V5.md) — v1.0.0 产品需求
- [OPC_MARKET_RESEARCH_REPORT.md](../research/OPC_MARKET_RESEARCH_REPORT.md) — 市场调研
- [OPC_AGENTS_ROADMAP_V1.0.0.md](../research/OPC_AGENTS_ROADMAP_V1.0.0.md) — 后期规划
- [PROMISELINK_API_CALIBRATION.md](../research/PROMISELINK_API_CALIBRATION.md) — API 校准
- [PROMISELINK_REUSE_PLAN.md](../research/PROMISELINK_REUSE_PLAN.md) — 复用方案

---

*最后更新: 2026-08-01*
*状态: 7-Role 共识，PM 主导执行*