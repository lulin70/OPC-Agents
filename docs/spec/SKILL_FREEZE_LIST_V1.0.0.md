# 技能冻结清单（v1.0.0 更新版）

> **版本**: v1.0.0 | **日期**: 2026-08-01
> **状态**: PM 主导执行
> **上一版**: [v0.3.4](SKILL_FREEZE_LIST.md)
> **依据**: [POSITIONING_RESOLUTION_V1.0.0.md](POSITIONING_RESOLUTION_V1.0.0.md) + [OPC 市场调研](../research/OPC_MARKET_RESEARCH_REPORT.md) + [PRD_V5.md](../product-manager/PRD_V5.md)

---

## v1.0.0 更新说明

v1.0.0 阶段对 v0.3.4 冻结清单做出以下调整：

| 技能 | v0.3.4 状态 | v1.0.0 状态 | 决策依据 |
|------|------------|------------|---------|
| **crm** | 🔶 半冻结 | ✅ **主动解冻** | 市场调研 4h/周节省需求 + 用户硬约束 |
| **task_manager** | 🔶 半冻结 | ⏸️ **推迟到 v1.1.0** | 风险更高，独立评估 |
| 其余冻结技能 | ❌ 冻结 | ❌ 维持冻结 | 无市场调研或用户反馈需求 |

### v1.0.0 CRM 主动解冻

**当前状态**：半冻结（仅 `get_customer/get_customer_stats/get_silent_customers` 3 方法维护）

**v1.0.0 决策**：
- ✅ 移除 frozen="semi" 标记
- ✅ 解锁所有方法（`add_customer/update_customer/list_customers/add_interaction/list_interactions/add_followup_reminder/lifecycle_tracker`）
- ✅ 集成 PromiseLink DormantScanner（已校准 `/entities/dormant?min_days=`）
- ✅ 12 模块关系推进卡视图（已校准 `/persons/{id}/relationship-brief/aggregated`）
- ✅ 测试覆盖率 ≥80%

**v1.1.0 task_manager 解冻（待评估）**：
- 移除 frozen="semi" 标记
- 解锁所有方法
- 集成 PromiseLink Todo 系统

---

## v0.3.4 冻结技能彻底移除（历史记录）

> **决策时间**: 2026-07-06
> **触发任务**: P0-2（成熟度审核 — 彻底移除冻结技能残留）
> **决策依据**: v0.3.0 冻结后无任何用户反馈需要复活这 3 个技能；保留冻结代码持续带来 i18n / 前端 / 文档 / 测试的孤儿引用维护成本。

### 移除清单

| 技能 | 文件 | 移除原因 | 复活路径 |
|------|------|---------|---------|
| calendar | `opc_manager/calendar_skill.py` | 无用户反馈；前端 `ADD_EVENT` 撤销分支、i18n `timeline_op_add_event` 等孤儿引用持续累积 | 如需复活，从 v0.3.3 tag 拉回，重新接入 skill_builtin / skill_executors / undo_manager |
| proposal | `opc_manager/proposal_skill.py` | 无用户反馈；`CREATE_PROPOSAL` 撤销分支、`timeline_proposal_created` 事件配置等孤儿引用持续累积 | 同上 |
| tax_reminder | `opc_manager/tax_reminder_skill.py` | 无用户反馈；`invoice_skill` 对其依赖已降级为 try/except lazy import | 如需复活，需同步恢复 invoice_skill 的 TAX_CALENDAR 强依赖 |

### 影响范围与处理方式

| 层 | 处理方式 |
|----|---------|
| 后端代码 | 3 个 skill 文件物理删除；`skill_builtin.py` 移除 3 个 Skill() 注册与 `_FULLY_FROZEN` 集合条目；`skill_executors.py` 移除 3 个 `_execute_*` 方法；`undo_manager.py` 移除 `ADD_EVENT` / `CREATE_PROPOSAL` 枚举值与对应映射 |
| 前端代码 | `undo_display.py` 移除 ADD_EVENT / CREATE_PROPOSAL 的 OPERATION_TYPE_CONFIG 与描述生成分支；`timeline_data.py` 移除 proposal_created 事件配置与 audit_log 操作映射；`base_router.py` 移除 tax_reminder 场景按钮 |
| i18n | 3 个语种文件（zh_CN / en_US / ja_JP）各移除 10 个孤儿键，共 30 键 |
| 测试 | `test_p1_skills.py` / `test_p2_skills.py` / `test_undo_manager.py` / `test_skill_executors.py` / `test_timeline_view.py` / `test_undo_panel.py` 同步更新断言 |
| 文档 | SKILL_FREEZE_LIST / API / README / DIRECTORY_STRUCTURE / COVERAGE_BASELINE 同步更新 |
| 隐藏依赖 | `invoice_skill.py` 顶部 `from opc_manager.tax_reminder_skill import ...` 改为 try/except lazy import，`get_tax_calendar=None` 时返回降级提示；`task_skill.py` 对 `calendar_skill` 的 import 已在 try/except 中，安全 |

### 验收

- [x] 3 个 skill 文件物理删除
- [x] skill_builtin / skill_executors / undo_manager 同步清理
- [x] 前端 undo_display / timeline_data / base_router 同步清理
- [x] i18n 30 个孤儿键清除（grep 零命中）
- [x] 测试同步更新（含 6 个 "removed" 断言测试）
- [x] 文档同步更新
- [x] 全量回归通过（1537 通过 + 86 skip，0 regression）

---

## 〇、冻结原则

1. **不删除代码**: 冻结技能代码保留，仅标记 `[FROZEN v0.3.0]`
2. **不主动维护**: 冻结技能不接受新功能、不优化性能
3. **UI隐藏**: 技能市场不显示冻结技能
4. **保留可活性**: 满足复活条件时可解冻
5. **依赖安全**: 冻结前确认无核心技能依赖被破坏

---

## 一、核心技能（v1.0.0 共 6 个）

| 技能 | 文件 | 状态 | 说明 |
|------|------|------|------|
| email | `email_skill.py` | ✅ 活跃 | "说一句话发邮件" |
| finance | `finance_skill.py` | ✅ 活跃 | "说一句话记账" |
| report | `report_skill.py` | ✅ 活跃 | "说一句话生成报告" |
| **crm** | `crm_skill.py` | ✅ **v1.0.0 主动解冻** | 客户管理 + 关系推进卡（基于 PromiseLink 集成）|
| task_manager | `task_skill.py` | ⏸️ 推迟到 v1.1.0 解冻 | 任务管理 |
| scheduler | `scheduler.py` | 🆕 v1.0.0 新增 | 主动执行引擎 |

---

## 二、半冻结技能（v1.0.0 状态变化）

### 2.1 CRM 主动解冻

**v0.3.4 状态**：半冻结（`get_customer/get_customer_stats/get_silent_customers` 3 方法维护）

**v1.0.0 状态**：✅ 完全解冻

**解冻清单**：

> **方法名映射（2026-09-24 校正）**：本表"规划名义"与代码实际实现名不一致（规划时命名未与代码对齐）。
> 处置为**保留代码现有实现名**（`email_skill`/`report_skill` 与既有单测均按现名引用，重命名属破坏性改动），
> 本表补"实际实现名"列以消除歧义。

| 规划名义 | **实际实现名** | v0.3.4 状态 | v1.0.0 状态 | 说明 |
|------|------------|------------|------------|------|
| `get_customer` | `get_customer` | ✅ 维护 | ✅ 维持 | 客户详情 |
| `get_customer_stats` | `get_customer_stats` | ✅ 维护 | ✅ 维持 | 客户统计 |
| `get_silent_customers` | `get_silent_customers` | ✅ 维护 | ✅ 增强 | 集成 PromiseLink `list_dormant_entities`（DormantScanner 为 PromiseLink 侧服务）|
| `add_customer` | `add_customer` | 🔶 半冻结 | ✅ **解冻** | 添加客户档案 |
| `update_customer` | `update_customer_status` | 🔶 半冻结 | ✅ **解冻** | 更新客户状态 |
| `list_customers` | `search_customers` | 🔶 半冻结 | ✅ **解冻** | 客户列表（搜索/过滤）|
| `add_interaction` | `add_deal` | 🔶 半冻结 | ✅ **解冻** | 合作记录 |
| `list_interactions` | `get_customer`（含 `deals`）| 🔶 半冻结 | ✅ **解冻** | 合作记录查询随客户详情返回 |
| `add_followup_reminder` | `add_follow_up` | 🔶 半冻结 | ✅ **解冻** | 跟进记录 |
| （未列入） | `get_follow_ups` | — | ✅ **解冻** | 跟进记录查询 |
| `lifecycle_tracker` | `lifecycle_tracker` | 🔶 半冻结 | ✅ **解冻** | 客户生命周期（本地视图 + 可选 PromiseLink `stage-info`）|

### 2.2 task_manager 维持半冻结（v1.1.0 解冻）

| 技能 | 文件 | 依赖方 | 被引用方法 | 状态 |
|------|------|--------|-----------|------|
| task_manager | `task_skill.py` | report_skill | `list_tasks` | ⏸️ v1.1.0 解冻 |

---

## 三、完全冻结技能（6 个）

| # | 技能 | 文件 | 当前功能 | 冻结理由 | 复活条件 |
|---|------|------|---------|---------|---------|
| 1 | competitor_watch | `competitor_skill.py` | 竞品分析 | 非高频，价值未验证 | 用户反馈需要竞品监控 |
| 2 | dashboard | `dashboard_skill.py` | 仪表盘 | 依赖crm/task，但本身非核心 | 用户反馈需要可视化 |
| 3 | invoice | `invoice_skill.py` | 发票管理 | 依赖tax_reminder（v0.3.4 已降级为 lazy import），低频 | 用户反馈需要开票 |
| 4 | knowledge_mgmt | `knowledge_skill.py` | 知识库 | 非高频，MemoryBridge已覆盖核心 | 用户反馈需要知识管理 |
| 5 | pricing | `pricing_skill.py` | 定价策略 | 非高频，价值未验证 | 用户反馈需要定价建议 |
| 6 | social_publish | `social_skill.py` | 社交媒体 | 非一人公司核心需求 | 用户反馈需要社媒管理 |

### 冻结技能间的依赖链

```
invoice_skill → tax_reminder_skill (两者都冻结，依赖链内部自洽)
dashboard_skill → crm_skill + task_skill (dashboard冻结，依赖不影响)
```

---

## 四、依赖关系图（v1.0.0 更新）

```
核心技能（活跃）:
  email_skill ──→ crm_skill.get_customer (✅ v1.0.0 解冻)
  report_skill ──→ crm_skill.get_customer_stats, get_silent_customers (✅ v1.0.0 解冻)
  report_skill ──→ task_skill.list_tasks (⏸️ 半冻结，v1.1.0 解冻)
  report_skill ──→ finance_skill.get_monthly_report, get_trend (✅ 核心)

新增能力（v1.0.0）:
  scheduler ──→ email_skill, report_skill, finance_skill (cron 触发受关键决策点保护)
  scheduler ──→ promiselink_client (可选集成)
  crm_skill ──→ promiselink_client (可选集成，默认本地降级)

冻结技能（内部依赖自洽）:
  invoice_skill → tax_reminder_skill (都冻结)
  dashboard_skill → crm_skill + task_skill (dashboard冻结，依赖不影响)
```

---

## 五、CRM 解冻执行清单

### 5.1 代码层

> **2026-09-24 校正**：原第 1、2 条描述与代码事实不符——`crm_skill.py` 内**不存在** per-method `# [FROZEN v0.3.0]` 注释，只有文件头 `"""[SEMI-FROZEN v0.3.0] ..."""` 模块 docstring。两行已合并为一条。

- [x] 改写 `crm_skill.py` 模块 docstring（移除 `[SEMI-FROZEN v0.3.0]` 标记）
- [x] 新增 `lifecycle_tracker` 方法（本地生命周期视图 + 可选 PromiseLink `/entities/{id}/stage-info`）
- [x] 增强 `get_silent_customers`：集成 PromiseLink `PromiseLinkClient.list_dormant_entities(min_days)`（`DormantScanner` 为 PromiseLink 侧服务，OPC-Agents 侧集成点为既有客户端）
- [x] `PROMISELINK_ENABLED=false` 默认配置（**已在批次 1.1 落地于 `promiselink_client.py`**；crm_skill 仅新增模块级 `_get_client()` 工厂复用，不重复定义配置）

> 施工完成：2026-09-24（T7）。集成不可用/失败时统一以 `promiselink_state` 显式给出六态之一，本地结果键语义不变。

### 5.2 测试层

> **2026-09-24 校正**：原描述「当前约 40%」与实测不符。实测 `pytest tests/unit/test_crm_skill.py --cov=opc_manager.crm_skill` = **249 stmts / 24 miss / 90%**（64 passed）→ 存量覆盖率**已达标**，不存在"需补充 ~40 个测试"的缺口。本批次只为**新增代码**补测。

- [x] 覆盖率维持 ≥80%（实测：`93 passed`，`crm_skill.py 317 stmts / 24 miss / 92%`）
- [x] 新增 `tests/e2e/test_crm_e2e.py`：模拟真实用户走完 **录入 → 查询 → 合作 → 跟进 → 沉默客户 → 统计 → 生命周期** 完整链路（实测 `43 passed`）
- [x] 验证 PromiseLink 集成两路径：**关闭/不可用（本地降级）** 与 **可用/降级（`DEGRADED`）**，均用 `httpx.MockTransport` 而非打真实网络（另覆盖 `SCHEMA_MISMATCH` / `CIRCUIT_OPEN` / `UNCONFIGURED`）

### 5.3 文档层

> 归属批次 3（与 UI 同步收口），非 T7 范围。PRD_V5 已含 F-CRM-01~06 与 US-CRM-01/02、USER_STORIES 已含 US49-51 映射（现状核对，非本批次产出）。

- [ ] [PRD_V5.md](../product-manager/PRD_V5.md) 标注 CRM 活跃
- [ ] [USER_STORIES.md](../product-manager/USER_STORIES.md) 新增 8 个 CRM 用户故事
- [ ] [API.md](../api/API.md) 记录 CRM API 变更
- [ ] [README.md](../../README.md) 三语同步

### 5.4 UI 层

- [ ] 技能市场重新显示 crm
- [ ] Settings 新增 CRM 标签页
- [ ] 主导航新增"客户管理"入口
- [ ] 集成 PromiseLink 12 模块关系推进卡视图
- [ ] Onboarding 更新（4 核心技能 → 6 核心技能）

---

## 六、v1.0.0 验收

### CRM 解冻验收

- [x] `crm_skill.py` 不含 `[SEMI-FROZEN v0.3.0]` 标记（模块 docstring 已改写）
- [x] 所有方法可调用且有测试
- [x] 测试覆盖率 ≥80%（实测 92%，口径见 §5.2）
- [x] `tests/e2e/test_crm_e2e.py` 通过（43 passed，模拟真实用户全链路）
- [x] PromiseLink 集成可启用可关闭
- [x] 集成关闭时本地 CRM 能力完整可用
- [x] 集成可用/降级两条路径均有测试且失败不静默（输出含显式 `promiselink_state`）

### 整体解冻验收

- [ ] PRD_V5 / SKILL_FREEZE_LIST / USER_STORIES 三文档一致（批次 3）
- [ ] 技能市场显示 6 核心技能（email/finance/report/crm/task_manager/scheduler）（批次 3）
- [ ] 6 个冻结技能在技能市场隐藏（批次 3）
- [x] 现有 11 项 CI 门禁不回退（本地五门禁 + 三语 README 一致性脚本复跑全绿）

---

## 七、变更记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-06-19 | v0.3.0 | 初版（13 → 3 核心技能）|
| 2026-07-06 | v0.3.4 | 移除 3 个冻结技能残留（calendar/proposal/tax_reminder）|
| 2026-08-01 | v1.0.0 | CRM 主动解冻 + 新增 scheduler 核心技能 |
| 2026-09-21 | v1.0.0 | 新增 §八 Skill 输出结构化约束（周榜信号 4，DevSquad 共识采纳）|
| 2026-09-24 | v1.0.0 | §5 施工前事实校正：① 无 per-method `[FROZEN]` 注释（仅模块 docstring）；② §2.1 补"规划名义→实际实现名"映射（保留代码现名，不重命名）；③ 覆盖率实测 90%（非"约 40%"）；④ 集成点校正为 `PromiseLinkClient.list_dormant_entities` / `get_entity_stage_info`（`DormantScanner` 属 PromiseLink 侧）；⑤ `PROMISELINK_ENABLED=false` 已在批次 1.1 落地 |
| 2026-09-24 | v1.0.0 | §5.1/§5.2/§六 CRM 解冻验收施工完成（T7）：docstring 去冻结标记、`lifecycle_tracker` 新增、`get_silent_customers` 集成增强（六态显式 `promiselink_state`）；单测 64→93、覆盖率 92%、新增 `test_crm_e2e.py` 43 项；§5.3/§5.4 与"整体解冻验收"前三条标注归属批次 3 |

---

## 八、Skill 输出结构化约束（v1.0.0 新增，2026-09-21）

> 来源：GitHub 周榜借鉴信号 4（参考 cloudflare/security-audit-skill 模式），经 DevSquad 五角色共识采纳。

v1.0.0 起，所有核心技能（email/finance/report/crm/scheduler）与新增模块的对外输出必须满足：

1. **结构化**：机器可读格式（dict/JSON schema 定义），禁止纯文本自由格式作为唯一输出
2. **可校验**：输出附带可编程验证的字段（状态码、数据 schema、trace_id），失败时返回 TDD §3.4 显式失败状态而非静默降级
3. **适用范围**：新增 `promiselink_client.py` / `scheduler.py` / CRM 解冻方法一律遵循；存量活跃技能渐进改造，不阻塞 v1.0.0

---

## 九、参考

- [POSITIONING_RESOLUTION_V1.0.0.md](POSITIONING_RESOLUTION_V1.0.0.md) — 产品定位矛盾解决方案
- [PRD_V5.md](../product-manager/PRD_V5.md) — v1.0.0 PRD
- [OPC_MARKET_RESEARCH_REPORT.md](../research/OPC_MARKET_RESEARCH_REPORT.md) — 市场调研
- [PROMISELINK_API_CALIBRATION.md](../research/PROMISELINK_API_CALIBRATION.md) — PromiseLink API 校准

---

*最后更新: 2026-09-21*
*状态: PM 主导执行中*