# OPC-Agents v1.0.0 推进计划（执行基线）

> **状态**: Approved — DevSquad 五角色共识通过
> **日期**: 2026-09-21 | **版本**: v1.0.0
> **主项目铁律**: 当前主项目 = OPC-Agents；PromiseLink/DevSquad 仅为依赖或协作仓库，不主动修改（2026-09-21 用户确认）
> **上游文档**: [PRD_V5](PRD_V5.md) · [TDD_V1.0.0](../architecture/TDD_V1.0.0.md) · [TEST_PLAN_V1.0.0](../test/TEST_PLAN_V1.0.0.md) · [SECURITY_REVIEW_V1.0.0](../security/SECURITY_REVIEW_V1.0.0.md) · [DEPLOYMENT_V1.0.0](../operations/DEPLOYMENT_V1.0.0.md) · [SKILL_FREEZE_LIST_V1.0.0](../spec/SKILL_FREEZE_LIST_V1.0.0.md) · [PROMISELINK_API_CALIBRATION](../research/PROMISELINK_API_CALIBRATION.md)

---

## 1. 目标

完成 OPC-Agents v1.0.0 的全部交付项：CRM 解冻、PromiseLink 集成客户端、Scheduler 主动执行引擎、UI 更新，通过全部门禁后发版。

## 2. 现状事实（2026-09-21 核查）

| 项 | 事实 |
|---|---|
| 代码基座 | v0.5.9 已有代码：`opc_manager/`（数十模块）+ `frontend/app.py` + 144 个测试文件 |
| 规划文档 | 9 份全链完成（PRD/TDD/TEST/SEC/DEP/POS/FREEZE/US48-59/CALIBRATION），**已提交推送** |
| v1.0.0 新模块 | promiselink_client / scheduler / CRM 解冻：**未启动** |
| 外部依赖 | ENH-PL-01~10 已送 PromiseLink 团队，未回；仅阻塞双向承诺分析等少数功能 |
| 协作基座 | DevSquad PR #9 已合并（09-14），无遗留 open 项 |
| 周榜借鉴 | 仅采纳信号 4（Skill 输出结构化+可校验，已写入 SKILL_FREEZE_LIST §九）；信号 5 入 P2 backlog |

## 3. 批次计划

### 批次 0 — 文档留痕闭环（已完成 2026-09-21）
| 项 | 内容 | 校验方法 |
|---|---|---|
| 0.1 | 信号 4 增补 SKILL_FREEZE_LIST §九 | 文档含"结构化+可校验"约束条目 |
| 0.2 | 提交推送 9 份文档 + USER_STORIES | `git status` 干净，CI 绿 |

### 批次 1 — 无外部依赖开发（三项独立，client 最优先）
前置动作：跑通现有 144 测试文件回归，锁定绿色基线；动工后创建 `feature/v1.0.0-batch1` 分支。

| 项 | 内容 | 验收标准 | 校验方法 |
|---|---|---|---|
| 1.1 | `opc_manager/promiselink_client.py`：TDD §3 的 17 条已确认路由 + 六态失败状态（DISABLED/UNCONFIGURED/AVAILABLE/DEGRADED/CIRCUIT_OPEN/SCHEMA_MISMATCH）+ 指数退避/429 处理 + trace_id | 单测全绿；认证失败 fail-closed；日志无 token | `pytest tests/test_promiselink_client.py -v` |
| 1.2 | `opc_manager/scheduler.py`：cron 触发 + 本地持久化 + 关键决策点保护；`PROMISELINK_ENABLED=false` 默认 | 单测全绿；重启后任务不丢 | `pytest tests/test_scheduler.py -v` |
| 1.3 | CRM 解冻：按 SKILL_FREEZE_LIST §5 清单（移除 FROZEN 标记、解锁 10 方法、lifecycle_tracker、DormantScanner 集成） | 覆盖率 ≥80%；`tests/e2e/test_crm_e2e.py` 40 测试通过；集成可开关，关闭时本地 CRM 完整可用 | `pytest --cov=opc_manager.crm_skill` + E2E |
| 1.4 | 批次回归：全量测试 + CI 门禁不回退（现有 11 项） | 0 regression | 全量 pytest + CI 绿后合并 main |

### 批次 2 — 事件驱动（ENH-PL 反馈到达后）
反馈 → 共识决策（改 TDD 或不改）→ **先更文档再动码** → 实现被阻塞功能（ENH-PL-01 双向承诺分析等）。

### 批次 3 — 集成验证与发布门禁
UI（技能市场 6 技能、CRM 标签页、关系推进卡、Onboarding）→ 真实 PromiseLink 实例 smoke → Streamlit+Playwright 模拟真实用户 E2E（发布硬门禁）→ 对照 SECURITY_REVIEW / DEPLOYMENT 收尾 → 发版。

## 4. 明确不做（防插队）
- DevSquad backlog（16 大文件拆分、bandit MEDIUM、Prometheus exporter）→ v1.0.0 后
- 周榜信号 2（安全垂直开源）/ 信号 5（跨模型路由，P2 backlog）→ 不进 v1.0.0
- task_manager 解冻 → v1.1.0 评估

## 5. 角色共识记录（DevSquad，2026-09-21）

| 角色 | 结论 | 关键输入 |
|---|---|---|
| PM | ✅ 同意 | 每批次带验收标准对齐 US48-59；文档先行闭环为前置 |
| Architect | ✅ 同意 | client 六态契约按 TDD §3.4 严格执行；不复制 PromiseLink 代码；DTO 最小映射 |
| Tester | ✅ 同意 | 动工前回归基线锁定；真实组件优先于 Mock；E2E 为发布硬门禁 |
| Security | ✅ 同意 | fail-closed + 日志禁泄 token + Fernet 按 SECURITY_REVIEW 前置于批次 1 |
| DevOps | ✅ 同意 | 批次 0 文档直推 main；批次 1 走 feature 分支，CI 绿后合并 |

**共识结论**：全体通过，无阻塞异议。批次 0 立即执行，批次 1 按依赖顺序推进。

## 6. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-09-21 | 初版；DevSquad 五角色共识通过；批次 0 完成闭环 |

---

*维护者: DevSquad 协作产出，PM 归档*
