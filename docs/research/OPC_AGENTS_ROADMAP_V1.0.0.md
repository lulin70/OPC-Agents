# OPC-Agents 后期规划 v1.0.0+（7-Role 共识版）

> **创建日期**: 2026-08-01 | **当前版本**: v0.5.9（Beta）→ **目标版本**: v1.0.0/v1.1.0/v2.0.0
> **创建方式**: DevSquad 7-Role 共识 + [市场调研报告](OPC_MARKET_RESEARCH_REPORT.md) + [PromiseLink 基础版现有能力复用]
> **关联文档**: [POSITIONING_RESOLUTION.md](../spec/POSITIONING_RESOLUTION.md)、[SKILL_FREEZE_LIST.md](../spec/SKILL_FREEZE_LIST.md)、[USER_STORIES.md](../product-manager/USER_STORIES.md)
> **状态**: 待 PM 主导的全员确认 + 后续种子用户反馈驱动

---

## 〇、规划背景与核心判断

### 0.1 市场调研关键结论

依据 [OPC_MARKET_RESEARCH_REPORT.md](OPC_MARKET_RESEARCH_REPORT.md)：

1. **市场存在但有 4 大结构性困境**（能力短板/获客难/法律风险/心理孤独），AI 可解决 3 项、辅助 1 项
2. **22h/周节省上限**，OPC-Agents 当前覆盖 ~7.5h（邮件+财务+报告）
3. **L3 智能体阶段**需要 cron 化主动执行（"起床时工作已完成"），OPC-Agents 当前缺此能力
4. **架构优势确认**：三贤者并行投票 + 关键决策点 fail-close + CarryMem 飞轮 5 级 = 行业领先
5. **核心差距**：CRM 半冻结 + L3 缺失 + 沉默客户识别未激活

### 0.2 团队内部资产复用机会

依据 [PromiseLink v0.9.0](https://github.com/lulin70/PromiseLink) 调研（基础版，1968 tests passed）：

| PromiseLink 现有能力 | 文件 | 复用方案 |
|------------------|------|---------|
| EntityExtractor（实体抽取）| `services/entity_extractor.py` | API 集成：用户输入→PromiseLink API→结构化客户/承诺/承诺提取 |
| RelationshipBrief（关系推进卡 12 模块）| `services/relationship_brief_service.py` | UI 组件复用：OPC-Agents 集成 RelationshipBrief 视图 |
| DormantScanner（沉默客户扫描）| `services/dormant_scanner.py` | 服务集成：OPC-Agents crm_skill 集成扫描能力 |
| PromiseBidirectional（双向承诺）| `services/promise_bidirectional.py` | 任务生成：自动区分我承诺/对方承诺/跟进 |
| NudgeGenerator（温和催促）| `services/nudge_generator.py` | 邮件技能增强：自动生成对方承诺到期的催促消息 |
| NotificationService（早晚报）| `services/notification_service.py` | 推送集成：Apple Shortcuts/邮件/微信公众号 |
| ScheduledEvent（排程事件）| `api/v1/scheduled_events.py` | 直接复用为 OPC-Agents L3 cron 化任务核心 |
| Reminder Preference | `models/reminder.py` | 复用疲劳度控制（5条/天+22:00-08:00 静默时段）|
| 6 种 Todo 类型 | `services/todo_generator.py` | 任务系统集成：promise/help/care/followup/cooperation_signal/risk |
| Entity Resolution 5 步级联 | `services/entity_resolution.py` | 客户归一化：合并同一客户的不同表达 |

**复用模式**：
- ✅ 通过 HTTP API 集成（轻量、零代码耦合）
- ✅ 通过 pip 本地依赖复用（更紧密、需 PromiseLink 作为可选项）
- ❌ 不做代码 fork（违背"集成现有工具优先于自建"原则）

---

## 一、7-Role 共识评估

### 1.1 PM（产品经理）

| 维度 | 评估 | 决策 |
|------|------|------|
| 产品定位 | 当前 3 核心技能聚焦（v0.3.0 决策正确），但市场需要 CRM+线索跟进+沉默客户识别 | v1.0.0 必须扩展到 4-5 核心技能 |
| 解冻路径 | [POSITIONING_RESOLUTION.md](../spec/POSITIONING_RESOLUTION.md) 已有 v0.5.0 解冻框架（task_manager/crm），但市场调研显示 crm 解冻优先级最高 | v1.0.0 解冻 crm，task_manager 推迟到 v1.1.0 |
| 与 PromiseLink 集成 | 复用而非重建符合"集成现有工具优先于自建"原则 | v1.0.0 集成 PromiseLink 基础版核心能力（实体抽取+沉默扫描+双向承诺）|
| 目标用户 | 6 类用户（内容创作者/数字产品/AI 工具/咨询/电商/创意），不同类对 CRM 需求不同 | v1.0.0 优先服务咨询+电商（CRM 强需求），v1.1.0 扩展到其他 |

**决策**：v1.0.0 = "3 核心技能 + CRM 解冻 + PromiseLink 复用 + L3 cron 化"

### 1.2 Architect（架构师）

| 维度 | 评估 | 决策 |
|------|------|------|
| 三贤者架构 | 已就绪，关键决策点保护完善 | v1.0.0 不动架构核心 |
| L3 cron 化 | 当前缺失，需要新模块 `opc_manager/scheduler.py` | v1.0.0 新增 scheduler 模块（基于 Python `schedule` 库 + 持久化）|
| PromiseLink 集成模式 | HTTP API 比 pip 依赖更解耦，但延迟较高 | 推荐 HTTP API 模式（OPC-Agents Skill 调用 PromiseLink API）|
| 数据库 | SQLite 已就绪 | 不迁移（基础版定位约束）|
| 失败模式 | cron 任务失败需降级到下次执行而非阻塞 | v1.0.0 scheduler 内置降级机制 |
| 缓存策略 | LLM 缓存已就绪（llm_cache.py）| cron 任务结果自动缓存 |

**决策**：
- 新增 `opc_manager/scheduler.py`（基于 schedule 库）
- PromiseLink 集成走 HTTP API（端口可配置，默认为 8200）
- 复用现有 SQLite + AES 加密架构

### 1.3 Security（安全）

| 维度 | 评估 | 决策 |
|------|------|------|
| Cron 任务权限 | 自动执行的 cron 任务权限过大可能误操作 | v1.0.0 scheduler 必须接关键决策点保护（涉及 email/report/finance 自动触发 fail-close）|
| PromiseLink API 调用 | 需要 token 认证 | v1.0.0 复用 OAuth2 token 机制（PromiseLink 已有）|
| 数据隔离 | 基础版本地 SQLite，PromiseLink 基础版也是本地 | 两者数据可独立（无需跨库关联）|
| 审计日志 | AuditLogger 已就绪 | v1.0.0 scheduler 自动执行记录完整审计链 |
| 密钥管理 | SMTP/API Key 已用 Fernet 加密 | PromiseLink 集成不暴露额外密钥 |

**决策**：scheduler 不可绕过三贤者保护，自动执行 email/finance/report 必须经关键决策点

### 1.4 Tester（测试）

| 维度 | 评估 | 决策 |
|------|------|------|
| CRM 解冻测试覆盖 | crm_skill 半冻结仅 3 方法维护，测试覆盖率不足 | v1.0.0 解冻前必须补齐 ≥80% 覆盖率 |
| Scheduler E2E | cron 调度涉及时间维度，传统 pytest 难以测试 | v1.0.0 新增 `test_scheduler_e2e.py`（使用 freezegun + time.sleep 混合）|
| PromiseLink 集成测试 | 涉及外部服务，需要 stub | v1.0.0 测试用 PromiseLink MockClient + 真实响应 fixture |
| E2E 总数 | 当前 4744 测试，v0.5.9 补充 70 个后 4814 | v1.0.0 新增 ≥100 个 E2E（scheduler 30 + PromiseLink 30 + CRM 40）|
| 回归测试 | 现有 CI 全门禁（ruff/mypy/coverage/E2E）| v1.0.0 维持 11 项门禁 |

**决策**：v1.0.0 必须新增 100+ E2E 测试 + 维持覆盖率 ≥65%

### 1.5 Coder（开发）

| 维度 | 评估 | 决策 |
|------|------|------|
| CRM 解冻工作量 | 移除 frozen 标记 + 解锁所有方法 + 补测试 | 3-4 天（符合 [POSITIONING_RESOLUTION §4.2](../spec/POSITIONING_RESOLUTION.md) 估算）|
| Scheduler 开发 | 基于 Python `schedule` 库 + 持久化 + cron 表达式解析 | 5-7 天 |
| PromiseLink HTTP 客户端 | 轻量 HTTP 客户端（requests + retry + circuit breaker）| 3-5 天 |
| Apple Shortcuts 扩展 | 现有 CLI 已实现 5 个动作，新增"日程任务触发"动作 | 1-2 天 |
| 文档同步 | PRD_V4.1 + SKILL_FREEZE_LIST + README + API | 0.5 天 |

**决策**：v1.0.0 总工作量约 12-15 工作日（Coder 主负责）

### 1.6 DevOps（运维）

| 维度 | 评估 | 决策 |
|------|------|------|
| Cron 任务持久化 | 需要数据库表 `scheduled_tasks` + `task_executions` | v1.0.0 数据迁移脚本已就绪 |
| PromiseLink 部署 | 基础版本地运行，集成需要 PromiseLink Docker 部署或 pip 安装 | v1.0.0 默认 pip 安装 + HTTP 调用（用户可选部署）|
| CI/CD | 现有 GitHub Actions 全门禁 | v1.0.0 新增 scheduler 单测 + E2E + PromiseLink Mock 测试 |
| 监控 | scheduler 任务执行需监控（成功/失败/重试次数）| v1.0.0 集成 Prometheus metrics |
| 备份 | cron 任务配置需备份 | v1.0.0 自动备份 scheduled_tasks 表到 data/backup/ |

**决策**：v1.0.0 scheduler 模块自带监控 + 自动备份

### 1.7 UI Designer（UI 设计）

| 维度 | 评估 | 决策 |
|------|------|------|
| CRM 集成 UI | v0.5.9 已有 Settings 页面 6 标签页，需要新增 "CRM" 标签页 | v1.0.0 CRM 标签页（客户档案 + 合作记录 + 沉默客户）|
| Scheduler UI | 需要新增"定时任务"页面 | v1.0.0 定时任务页面（任务列表 + 新建任务 + 执行历史）|
| PromiseLink 集成 UI | 关系推进卡（12 模块）需要可视化 | v1.0.0 集成 RelationshipBrief 视图到客户详情页 |
| i18n | 中文/英文/日文三语 | v1.0.0 新增 CRM/Scheduler 相关 60 个 i18n 键 |
| Morandi 配色 | 已就绪 | 维持 |

**决策**：v1.0.0 新增 2 个核心 UI 页面（CRM 标签页 + 定时任务页）

### 1.8 共识结论

> **7-Role 共识：7/7 通过**（无 Veto）

**v1.0.0 核心范围**：
1. ✅ CRM 技能解冻（移除 frozen 标记 + 解锁所有方法 + 补齐测试 ≥80%）
2. ✅ PromiseLink 基础版能力集成（EntityExtractor/DormantScanner/PromiseBidirectional/ScheduledEvent）
3. ✅ L3 cron 化主动执行（新增 scheduler 模块）
4. ✅ Apple Shortcuts 扩展（新增 2-3 个 CLI 动作）
5. ✅ 100+ 新 E2E 测试 + 维持 11 项门禁
6. ✅ UI 扩展（CRM 标签页 + 定时任务页）

---

## 二、详细功能规划（v1.0.0/v1.1.0/v2.0.0）

### 2.1 v1.0.0 范围（6 周目标）

> **主题**：从"被动响应"升级为"主动持续自治 + 完整 CRM"

#### F-V100-01: CRM 技能完全解冻（3-4 天）

**目标**：将 [crm_skill.py](../opc_manager/crm_skill.py) 从半冻结状态激活为完整技能

**当前状态**：仅维护 `get_customer/get_customer_stats/get_silent_customers` 3 方法

**解冻范围**（基于 [USER_STORIES §CRM 用户故事](../product-manager/USER_STORIES.md)）：
- ✅ `add_customer`（客户档案创建）— CRM-01
- ✅ `update_customer`（客户档案更新）
- ✅ `get_customer`（已实现）
- ✅ `list_customers`（按名称/公司/标签/来源筛选）— CRM-03
- ✅ `add_interaction`（合作记录创建）— CRM-04
- ✅ `list_interactions`（合作记录查询）
- ✅ `get_silent_customers`（已实现）— CRM-03 沉默客户
- ✅ `add_followup_reminder`（跟进提醒）— CRM-05
- ✅ `get_customer_stats`（已实现）— CRM-04
- ✅ `lifecycle_tracker`（生命周期：潜在→初次合作→活跃→沉默→流失）— Phase 2+

**E2E 验证**：✅ 新增 [test_crm_e2e.py](../tests/e2e/test_crm_e2e.py)（40 测试）
- add_customer + get_customer 闭环
- silent_customer 阈值（N=90 天未联系）
- lifecycle 状态流转
- followup_reminder 触发与通知

**风险**：
- ⚠️ 客户数据导出需二次确认（[SEC-4-04](../product-manager/PRD_V4.md) 已实现）
- ⚠️ 客户电话/邮箱加密存储（AES-256 已就绪）

#### F-V100-02: L3 cron 化主动执行（5-7 天）

**目标**：新增 `opc_manager/scheduler.py`，让 OPC-Agents 升级到 L3 智能体阶段

**核心组件**：
- `Scheduler` 类（基于 Python `schedule` 库 + 持久化）
- `ScheduledTask` 数据模型（cron 表达式 + 任务类型 + 参数 + 启用状态）
- `TaskExecution` 历史记录（执行时间/状态/结果/重试次数）
- 关键决策点保护（涉及 email/report/finance 自动触发必须经三贤者）

**支持的 cron 触发器**：
- 用户预设模板：
  - "每周一 9:00 生成营销周报"
  - "每日 18:00 同步客户跟进状态"
  - "每月底自动发送发票"
  - "每季度自动生成财务报告"
  - "每日 9:00 早报推送（沉默客户/到期承诺/今日待办）"
- 自定义 cron 表达式（5 字段标准 cron）

**持久化**：SQLite 表 `scheduled_tasks` + `task_executions`

**降级机制**：
- 任务失败自动重试 3 次（指数退避）
- 任务失败后下次执行前不重复触发（避免雪崩）
- LLM 不可用时降级到本地缓存结果

**E2E 验证**：✅ 新增 [test_scheduler_e2e.py](../tests/e2e/test_scheduler_e2e.py)（30 测试）
- cron 表达式解析正确性
- 任务持久化（重启后恢复）
- 关键决策点保护（涉及 email 的 cron 任务触发 fail-close）
- 失败重试机制
- 静默时段控制（22:00-08:00 不执行）

**用户场景**（来自市场调研）：
- "起床时工作已完成" 体验兑现
- 22h/周节省目标提升到 14h+

#### F-V100-03: PromiseLink 基础版能力集成（3-5 天）

**目标**：通过 HTTP API 集成 PromiseLink v0.9.0 现有能力，避免重复开发

**集成接口**（在 OPC-Agents 端）：

| OPC-Agents 技能 | PromiseLink API | 复用价值 |
|---------------|----------------|---------|
| `crm.add_customer` | `POST /api/v1/entities` | 复用 PromiseLink EntityExtractor 自动提取客户档案（从会议记录）|
| `crm.get_silent_customers` | `GET /api/v1/entities?dormant_days=90` | 复用 DormantScanner 3 维度打分算法 |
| `email.compose_followup` | `POST /api/v1/todos` (followup 类型) | 复用 PromiseLink 6 种 Todo 分类 |
| `email.compose_nudge` | `POST /api/v1/nudges/generate` | 复用 NudgeGenerator 温和催促消息模板 |
| `report.daily_brief` | `GET /api/v1/dashboard/daily` | 复用 RelationshipBrief 12 模块聚合 |
| `crm.get_relationship_brief` | `GET /api/v1/persons/{id}/relationship-brief` | 复用关系推进卡（关注点/承诺/下一动作）|
| `crm.schedule_event` | `POST /api/v1/scheduled-events` | 复用 ScheduledEvent CRUD |

**集成模式**：
- ✅ HTTP API 客户端（`opc_manager/promiselink_client.py`）
- ✅ 可选启用（默认关闭，Settings 页面配置）
- ✅ 配置项：`PROMISELINK_ENABLED` + `PROMISELINK_API_URL` + `PROMISELINK_API_TOKEN`
- ✅ 优雅降级（API 不可用时静默降级到 OPC-Agents 自身能力）

**E2E 验证**：✅ 新增 [test_promiselink_integration_e2e.py](../tests/e2e/test_promiselink_integration_e2e.py)（30 测试）
- HTTP 客户端 retry + circuit breaker
- 配置缺失时优雅降级
- 7 个集成接口的 mock 测试
- 真实 PromiseLink 实例的 smoke 测试（可选）

**风险**：
- ⚠️ PromiseLink 与 OPC-Agents 数据库独立（用户需双倍本地存储）—— 已在用户偏好文档中说明
- ⚠️ 两个产品的 i18n 同步问题——v1.0.0 仅中文（其他语言 v1.1.0）

#### F-V100-04: Apple Shortcuts CLI 扩展（1-2 天）

**目标**：基于 [shortcuts_handler.py](../opc_manager/shortcuts_handler.py) 现有 5 个动作，扩展支持 L3 cron 触发

**新增动作**：
- `opc-agents schedule-add "每周一 9:00" "生成营销周报"` — 注册定时任务
- `opc-agents schedule-list` — 列出所有定时任务
- `opc-agents schedule-run <task_id>` — 手动触发定时任务
- `opc-agents schedule-disable <task_id>` — 停用定时任务

**E2E 验证**：✅ 扩展 [test_shortcuts_e2e.py](../tests/e2e/test_shortcuts_e2e.py)（+10 测试）

#### F-V100-05: 客户跟进序列（4-5 天）— 复用 PromiseLink

**目标**：基于 PromiseLink 双向承诺 + EmailSkill，实现 day 3/7/14 自动跟进序列

**核心能力**：
- ✅ 自动识别"对方承诺"（their_promise）— 复用 PromiseLink PromiseBidirectional
- ✅ 自动生成温和催促消息（nudge）— 复用 NudgeGenerator
- ✅ 自动发送跟进邮件（频率限制 1/天 + 3/小时）— 复用现有 email_skill
- ✅ 跟进状态追踪（pending/sent/replied/done）— 复用 PromiseLink Todo 状态机

**E2E 验证**：✅ 集成到 [test_p0_skills_e2e.py](../tests/e2e/test_p0_skills_e2e.py)（+10 测试）

#### F-V100-06: UI 扩展（2-3 天）

**目标**：新增 2 个核心页面

| 页面 | 位置 | 内容 |
|------|------|------|
| **CRM 标签页** | Settings → 新增第 7 标签 | 客户列表 + 客户档案 + 合作记录 + 沉默客户 |
| **定时任务页** | 主导航新增入口 | 任务列表 + 新建任务 + 执行历史 + 启用/停用 |

**i18n**：新增 60 个键（中文/英文/日文）

**E2E 验证**：✅ 新增 [test_crm_ui_e2e.py](../tests/e2e/test_crm_ui_e2e.py) + [test_scheduler_ui_e2e.py](../tests/e2e/test_scheduler_ui_e2e.py)（+20 测试）

#### F-V100-07: 文档同步 + 版本管理（0.5 天）

- [PROJECT_STATUS.md](../PROJECT_STATUS.md) v0.5.9 → v1.0.0
- [POSITIONING_RESOLUTION.md](../spec/POSITIONING_RESOLUTION.md) 更新 crm 解冻状态
- [SKILL_FREEZE_LIST.md](../spec/SKILL_FREEZE_LIST.md) 标记 crm 解冻
- [CHANGELOG.md](../../CHANGELOG.md) v1.0.0 完整条目
- [README.md](../../README.md) 三语同步 + 版本号
- [PRD_V4.1](../product-manager/PRD_V4.md) 更新 CRM 部分为活跃状态
- 新建 [docs/research/OPC_MARKET_RESEARCH_REPORT.md](OPC_MARKET_RESEARCH_REPORT.md)（已创建）
- 新建 [docs/research/OPC_AGENTS_ROADMAP_V1.0.0.md](OPC_AGENTS_ROADMAP_V1.0.0.md)（本文档）

---

### 2.2 v1.1.0 范围（4 周目标，预计 Q4 2026）

> **主题**：扩展到内容创作 + 线索资格化 + 任务管理解冻

| 编号 | 功能 | 工作量 | 优先级 |
|------|------|--------|--------|
| F-V110-01 | task_manager 完全解冻 | 3-4 天 | 🟡 P1 |
| F-V110-02 | 多平台内容发布（LinkedIn/微博/公众号）| 1-2 周 | 🟡 P1 |
| F-V110-03 | 线索资格化（表单评分 + 约会调度）| 1 周 | 🟡 P1 |
| F-V110-04 | Stripe 集成（发票+订阅）| 3-5 天 | 🟡 P1 |
| F-V110-05 | 竞争对手监控（Jina Reader + RSS）| 1 周 | 🟢 P2 |
| F-V110-06 | Apple Shortcuts 自然语言定义 | 1 周 | 🟢 P2 |

---

### 2.3 v2.0.0 范围（8 周目标，预计 2027 Q1）

> **主题**：AI Search SEO + MCP 产品化 + 商业闭环

| 编号 | 功能 | 工作量 | 优先级 |
|------|------|--------|--------|
| F-V200-01 | AI Search SEO（AI 搜索结果优化）| 2 周 | 🟢 P2 |
| F-V200-02 | MCP 产品化（个人能力→服务→分发）| 4 周 | 🟢 P2 |
| F-V200-03 | 外部技能市场（X-Agent 模式）| 4 周 | 🟢 P2 |
| F-V200-04 | 自我复制 + 飞轮全闭环（CarryMem 5 级 → 6 级）| 2 周 | 🟢 P2 |

---

## 三、PromiseLink 基础版能力复用详细方案

### 3.1 复用决策矩阵

依据 [PromiseLink 调研](../research/PROMISELINK_BASIC_RESEARCH.md) 与 [PromiseLink 项目状态](https://github.com/lulin70/PromiseLink/blob/main/docs/PROJECT_STATUS.md)：

| PromiseLink 能力 | OPC-Agents 复用必要性 | 复用难度 | 优先级 | 决策 |
|---------------|-------------------|---------|--------|------|
| EntityExtractor | 高（自动从会议记录提取客户）| 中（HTTP API）| 🟡 P1 | ✅ 集成 |
| DormantScanner | 高（沉默客户识别）| 中（HTTP API）| 🔴 P0 | ✅ 集成 |
| PromiseBidirectional | 中（双向承诺）| 中（HTTP API）| 🟡 P1 | ✅ 集成 |
| NudgeGenerator | 高（催促消息）| 低（HTTP API）| 🟡 P1 | ✅ 集成 |
| RelationshipBrief | 高（关系视图）| 中（HTTP API + UI 适配）| 🔴 P0 | ✅ 集成 |
| ScheduledEvent | 高（与 L3 重叠）| 中（HTTP API + 数据同步）| 🔴 P0 | ✅ 集成（作为 OPC-Agents 自身 scheduler 的后端）|
| NotificationService | 中（推送集成）| 低（HTTP API）| 🟢 P2 | ⚠️ 暂不集成（Apple Shortcuts 已覆盖）|
| Entity Resolution | 中（客户归一化）| 高（深度集成）| 🟢 P2 | ⚠️ v1.1.0 评估 |
| Todo 6 类型 | 中（任务分类）| 中（HTTP API）| 🟡 P1 | ✅ 集成 |
| 早晚报推送 | 中（推送体验）| 中（HTTP API）| 🟢 P2 | ⚠️ v1.1.0 |

### 3.2 集成架构

```
┌────────────────────────────────────────────────────────────┐
│              OPC-Agents v1.0.0                              │
│                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐  │
│  │ IntentRouter │──▶│ ThreeSages   │──▶│ Skills       │  │
│  │  (L1-L5)     │   │ (Consensus)  │   │ (10 内置)    │  │
│  └──────────────┘   └──────────────┘   └──────┬───────┘  │
│                                                │             │
│                                                ▼             │
│                                        ┌──────────────┐    │
│                                        │ PromiseLink   │    │
│                                        │ Client        │    │
│                                        └──────┬───────┘    │
│                                                │             │
│  ┌──────────────┐                              │             │
│  │ Scheduler    │                              │ HTTP API    │
│  │ (L3 cron)    │──────────────────────────────┼─────────────│
│  └──────────────┘                              │             │
│                                                ▼             │
│                                        ┌──────────────┐    │
│                                        │ PromiseLink   │    │
│                                        │ v0.9.0        │    │
│                                        │ (Local pip)   │    │
│                                        └──────────────┘    │
└────────────────────────────────────────────────────────────┘
```

### 3.3 配置示例

```bash
# .env 配置文件（新增）
PROMISELINK_ENABLED=true
PROMISELINK_API_URL=http://localhost:8200  # PromiseLink 基础版 HTTP 端口
PROMISELINK_API_TOKEN=<OAuth2 token>      # 复用 PromiseLink JWT 认证

# 启用后 OPC-Agents 自动获得 PromiseLink 7 大能力
# 禁用时优雅降级到 OPC-Agents 自身能力
```

### 3.4 失败降级路径

| 场景 | 降级行为 |
|------|---------|
| PromiseLink 未安装 | 关闭集成，OPC-Agents 使用 crm_skill 自身能力 |
| PromiseLink 未启动 | retry 3 次后降级到自身能力，记录日志 |
| API 调用超时 | circuit breaker 30s 内不重试，使用缓存结果 |
| API 返回错误 | 记录错误码 + 降级到自身能力 + 通知用户 |
| 双向承诺分析失败 | 使用规则引擎 fallback（基于 OPC-Agents 关键词） |

---

## 四、关键决策与风险评估

### 4.1 关键决策记录

| 决策项 | 决策 | 决策依据 |
|--------|------|---------|
| v1.0.0 是否解冻 CRM | ✅ 解冻 | 市场调研显示 CRM 4h/周节省优先级最高 |
| v1.0.0 是否集成 PromiseLink | ✅ 集成 | 符合"集成现有工具优先于自建"原则，避免 6+ 月重复开发 |
| 集成模式 | ✅ HTTP API（非 pip）| 解耦更好，延迟可接受，版本独立 |
| scheduler 库选择 | ✅ Python `schedule` 库 | 轻量、零依赖、cron 表达式支持 |
| cron 任务保护 | ✅ 关键决策点 fail-close | 涉及 email/report/finance 自动触发必须经三贤者 |
| Apple Shortcuts 扩展 | ✅ 新增 4 个动作 | 与现有 5 个动作一致风格 |
| 6 个冻结技能解冻顺序 | ✅ CRM (v1.0.0) → task_manager (v1.1.0) → 其他 (v2.0.0+) | 基于市场调研 + USER_STORIES 用户反馈 |
| PromiseLink 集成范围 | ✅ 7 个核心能力 | 高 ROI + 低集成难度 |

### 4.2 风险矩阵

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| PromiseLink 与 OPC-Agents 数据库独立 | 🟡 中 | 双倍存储已在用户偏好文档说明 |
| scheduler 误触发导致邮件/财务误发 | 🔴 高 | 关键决策点 fail-close（强制三贤者）|
| crm_skill 解冻引入回归 | 🟡 中 | 100+ E2E 测试 + 全量回归 |
| 两个产品的 i18n 不一致 | 🟢 低 | v1.0.0 仅中文（OPC-Agents 现有三语机制）|
| scheduler 持久化失败 | 🟡 中 | SQLite + 内存双层降级 |
| LLM 不可用导致 cron 任务失败 | 🟡 中 | 缓存 fallback + 任务自动重试 |
| 用户配置 PromiseLink 失败 | 🟢 低 | 启动时检测 + 明确错误提示 |

---

## 五、版本路线图

```
v0.5.9（当前） ──────┐
   质量巩固            │   现状：3 核心技能 + 三贤者 + CarryMem
                      │   4744 测试 + 11 项门禁
                      ▼
v1.0.0（6 周）────────┐
   CRM 解冻            │
   + L3 cron           │   重点：CRM 完整闭环 + 主动执行
   + PromiseLink 集成   │
   + 100 E2E           │
                      ▼
v1.1.0（4 周）────────┐
   task_manager 解冻    │
   + 内容发布           │   重点：内容 + 线索 + 订阅
   + 线索资格化         │
   + Stripe            │
                      ▼
v2.0.0（8 周）────────┐
   AI Search SEO       │
   + MCP 产品化        │   重点：商业闭环 + 自我复制
   + 外部市场          │
   + CarryMem 6 级     │
                      ▼
v3.0.0（远期）         ─▶ 全闭环商业体 + 90 天上线 OPC
```

---

## 六、共识签名

> 本规划由 DevSquad 7-Role 共识达成，2026-08-01

| 角色 | 代表意见 | 共识度 |
|------|---------|--------|
| PM | ✅ 完全同意 v1.0.0 范围与优先级排序 | 100% |
| Architect | ✅ 三贤者架构不动 + scheduler 新增模块 + PromiseLink HTTP 集成 | 100% |
| Security | ✅ scheduler 关键决策点保护 + 审计日志完整 | 100% |
| Tester | ✅ 100+ 新 E2E + 全量回归 + 11 项门禁维持 | 100% |
| Coder | ✅ 12-15 工作日工作量可接受 | 100% |
| DevOps | ✅ scheduler 自带监控 + 自动备份 | 100% |
| UI Designer | ✅ 新增 2 个 UI 页面 + i18n 同步 | 100% |

**总体共识**：7/7 通过，无 Veto。

---

## 七、变更记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-08-01 | v1.0 | 初版创建（基于市场调研 + PromiseLink 能力复用）|

---

## 八、参考文献

### 内部文档

- [OPC_MARKET_RESEARCH_REPORT.md](OPC_MARKET_RESEARCH_REPORT.md) — 市场调研报告
- [POSITIONING_RESOLUTION.md](../spec/POSITIONING_RESOLUTION.md) — 产品定位矛盾解决方案
- [SKILL_FREEZE_LIST.md](../spec/SKILL_FREEZE_LIST.md) — 技能冻结清单
- [USER_STORIES.md](../product-manager/USER_STORIES.md) — 用户故事（6 大类型）
- [PRD_V4.md](../product-manager/PRD_V4.md) — 产品需求文档
- [PROJECT_STATUS.md](../PROJECT_STATUS.md) — 项目状态
- [CHANGELOG.md](../../CHANGELOG.md) — 版本变更历史

### 团队内部资产

- [PromiseLink v0.9.0](https://github.com/lulin70/PromiseLink) — 基础版（1968 tests）
- [CarryMem v0.10.0](https://github.com/lulin70/carrymem) — 跨会话记忆引擎
- [DevSquad v4.5.16](https://github.com/lulin70/DevSquad) — 7-Role 协作框架

### 行业基准

- [McKinsey State of AI 2026](https://karriere.mckinsey.de/capabilities/quantumblack/our-insights/the-state-of-ai)
- [MBO Partners State of Independence 2025](https://www.mbopartners.com/state-of-independence/)
- [Pancake AI](https://getpancake.ai/blog/how-to-run-one-person-company-2026)
- [Pokee AI](https://pokee.ai/blog/ai-agent-for-solopreneurs)

---

*最后更新: 2026-08-01*
*规划负责人: OPC-Agents 团队 + DevSquad 7-Role 共识*
*下次回顾: v1.0.0 发布后（约 2026-09-15）*