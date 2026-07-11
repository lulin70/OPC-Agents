# OPC-Agents 项目状态

> **最后更新**: 2026-07-11（DevSquad 共识推进 P3-3 Batch 1 完成，v0.3.12 发布） | **版本**: v0.3.12 (Beta) | **许可**: MIT
>
> 本文档为项目当前状态的单一事实来源（Single Source of Truth），与 [README.md](../README.md) / [CHANGELOG.md](../CHANGELOG.md) / [PROJECT_MATURITY_ASSESSMENT_v0.3.3_20260629.md](internal/PROJECT_MATURITY_ASSESSMENT_v0.3.3_20260629.md) 配套使用。

---

## 1. 当前版本

| 项目 | 值 |
|------|-----|
| 版本号 | `0.3.12`（见 [VERSION](../VERSION)） |
| 状态 | Beta |
| Python 要求 | ≥ 3.10 |
| 许可证 | MIT |
| PyPI 包名 | `opc-agents` |
| 仓库 | [lulin70/OPC-Agents](https://github.com/lulin70/OPC-Agents) |

---

## 2. 模块清单

### 核心包：`opc_manager/`（99 个 `.py` 文件）

| 类别 | 关键模块 | 职责 |
|------|----------|------|
| **三贤者引擎** | `consensus_engine.py`, `executor_brain.py`, `reflector_brain.py`, `strategist_brain.py` | 并行投票架构（asyncio.gather），关键决策点前置共识 |
| **任务调度** | `task_engine_v3_parallel.py`, `parallel_executor.py`, `intent_classifier.py`, `intent_types.py` | IntentRouter 三路智能路由（SIMPLE/COMPLEX/GREETING） |
| **核心技能** | `email_skill.py`, `finance_skill.py`, `llm_content.py` | 邮件 / 财务 / 报告生成（v0.3.0 聚焦的 3 个核心 skill） |
| **内容生成** | `llm_content.py` (facade) + `llm_content_prompt.py` + `llm_content_generation.py` | RAG 混合模式（模板骨架 + LLM 填充），优雅降级到 v3.4 模板 |
| **数据层** | `data_manager.py`, `settings.py`, `settings_encryption.py`, `secure_storage.py` | SQLite + Fernet 加密 + PBKDF2 密钥派生 |
| **安全** | `validators.py`, `skill_marketplace.py`, `audit_log.py` | 输入校验 / prompt injection 阻断 / 时序攻击防护 |
| **技能市场** | `skill_marketplace.py` | 技能发布 / 安装 / HMAC 恒定时间比较 |
| **i18n** | `i18n/` | 3857 行 → 133 行逻辑层 + JSON 化（中/英/日） |
| **API** | `api_server.py` | FastAPI REST API（OpenAPI/Swagger） |
| **导出** | `export/` | 数据导出（CSV/JSON/Markdown） |

### 冻结技能（v0.3.0 冻结，11 个）

详见 [docs/spec/SKILL_FREEZE_LIST.md](spec/SKILL_FREEZE_LIST.md)。聚焦邮件/财务/报告 3 个核心技能，把每个做到真正好用。

---

## 3. 测试摘要

> **口径说明**: 本节数据来自 `pytest --co -q` 实测，覆盖率来自 `coverage.json` 实测值。专项测试覆盖率（`pytest --cov` 单模块）与全量测试套件覆盖率口径不同，详见 [README.md](../README.md) 第 42 行注释。

| 指标 | 值 | 来源 |
|------|-----|------|
| 测试用例总数 | 3781 collected | `pytest --co -q --ignore=tests/e2e`（unit+integration） |
| 全量覆盖率 | 66% | `coverage.json` totals.percent_covered_display（v0.3.10 crm_skill 64 tests + 3 bug 修复后提升，CI 阈值 65%） |
| `email_skill.py` 覆盖率（全量口径） | 16.96% | `coverage.json` |
| `finance_skill.py` 覆盖率（全量口径） | 14.46% | `coverage.json` |
| `email_skill` 专项测试覆盖率 | 99% | `pytest --cov=opc_manager.email_skill` |
| `finance_skill` 专项测试覆盖率 | 100% | `pytest --cov=opc_manager.finance_skill` |
| mypy 错误数 | 0 | `MYPYPATH=src mypy -p opc_manager`（v0.3.3 已清理 516→0） |
| flake8 违规 | 0 | `flake8 opc_manager/ tests/` = 0（Phase 2 P0 清零：opc_manager 143→0 + tests 119→0） |

### 测试维度现状（v0.3.3 评估）

- **Happy Path**: 充分（≥50%）
- **Error Case**: 充分（≥15%）
- **Boundary**: 不足（<10%，Phase 2 补充）
- **Performance**: 达标（5.53%，硬约束要求 ≥5%，Phase 1 Task #3 已完成）
- **Configuration**: 充分
- **Integration**: 充分（24 个 E2E 测试）
- **Security**: 充分（prompt injection 阻断 + 时序攻击防护 + PBKDF2）

---

## 4. 已知问题

### 🔴 P0 阻塞发布（v0.4.0 发布前必做）

| # | 问题 | 状态 |
|---|------|------|
| P0-1 | CHANGELOG/README 覆盖率口径混淆（17% vs 99%） | ✅ 已修复（2026-06-29，README 措辞澄清） |
| P0-2 | Perf 测试维度 0.83% 违反 ≥5% 硬约束 | ✅ 已修复（2026-07-01，新增 165 个 Perf 测试，5.53%） |
| P0-3 | 无 v0.3.3 git tag，release.yml 从未触发 | ✅ 已修复（2026-07-07，v0.3.4 发布成功：PyPI + GHCR + GitHub Release 三端齐全） |
| P0-4 | requirements.lock SSH 私有仓库依赖不可复现 | ✅ 已修复（2026-06-29，carrymem==0.4.0，移除本地路径） |
| P0-5 | release.yml 缺 PyPI twine upload 步骤 | ✅ 已修复（2026-06-29，新增 publish-pypi job） |
| P0-6 | email/finance 覆盖率全量口径仅 17%/14.5% | ⏳ 待办（大型任务，专项测试覆盖率已达 99%/100%） |

### 🟠 P1 重要问题（影响生产就绪）

| # | 问题 | 状态 |
|---|------|------|
| P1-1 | 裸 SHA-256 违反硬约束 | ✅ 已修复（2026-06-29，PBKDF2-HMAC-SHA256 + salt） |
| P1-2 | prompt injection 仅检测不阻断 | ✅ 已修复（2026-06-29，阻断式模板降级） |
| P1-3 | PROJECT_STATUS.md 缺失 | ✅ 已修复（本文档） |
| P1-4 | parallel_executor.py 幽灵功能 | ✅ 已修复（2026-06-29，文档化三贤者实际路径） |
| P1-5 | skill_marketplace.py 时序攻击（`==` 比较哈希） | ✅ 已修复（2026-06-29，`hmac.compare_digest`） |
| P1-6 | opc_manager 99 文件平铺无子包 | ✅ 已修复（2026-07-05，P2-14 虚拟分层：DIRECTORY_STRUCTURE.md 7 层映射 + ruff isort 软约束 + 96 个架构守护测试） |
| P1-7 | async 函数注解率仅 23% | ✅ 已修复（2026-06-29，AST 实测 87.5%，84/96） |
| P1-8 | 715 处 Mock 违反"优先真实组件"铁律 | ⏳ 待办（Phase 1 Task #14，大型任务） |

---

## 5. Phase 1 修复进度

> 完整任务清单见 [PROJECT_MATURITY_ASSESSMENT_v0.3.3_20260629.md](internal/PROJECT_MATURITY_ASSESSMENT_v0.3.3_20260629.md) 第四节。

| 评估任务 # | 任务 | 状态 | 完成时间 |
|------------|------|------|----------|
| #1 | 覆盖率口径混淆修复 | ✅ 完成 | 2026-06-29 |
| #2 | email/finance 补真实组件测试 ≥80% | ⏳ 待办（大型任务） | — |
| #3 | Perf 维度扩充至 ≥5%（≥162 测试） | ✅ 完成（165 个 Perf 测试，5.53%） | 2026-07-01 |
| #4 | 三语 README 安装命令统一 0.3.3 | ✅ 完成 | 2026-06-29 |
| #5 | 打 v0.3.4 git tag | ✅ 完成（v0.3.4 发布成功：PyPI + GHCR + GitHub Release） | 2026-07-07 |
| #6 | requirements.lock 移除 SSH 依赖 | ✅ 完成 | 2026-06-29 |
| #7 | release.yml 补 PyPI twine upload | ✅ 完成 | 2026-06-29 |
| #8 | PBKDF2 替换裸 SHA-256 | ✅ 完成 | 2026-06-29 |
| #9 | prompt injection 阻断式升级 | ✅ 完成 | 2026-06-29 |
| #10 | 新建 PROJECT_STATUS.md | ✅ 完成 | 2026-06-29 |
| #11 | parallel_executor 三贤者路径文档化 | ✅ 完成 | 2026-06-29 |
| #12 | opc_manager 拆子包 | ✅ 完成（2026-07-05，P2-14 虚拟分层替代物理子包化） | 2026-07-05 |
| #13 | async 函数补类型注解 ≥80% | ✅ 完成（87.5%，AST 实测 84/96） | 2026-06-29 |
| #14 | test_email_skill mock→真实组件重构 | ⏳ 待办（大型任务） | — |
| #15 | skill_marketplace hmac.compare_digest | ✅ 完成 | 2026-06-29 |

**进度**: 13/15 完成（87%），2 项待办（大型任务）。

---

## 6. 改进路线图

### Phase 1：v0.4.0 发布前必做（P0+P1）

见上方第 5 节。当前进度 13/15（87%）。

### Phase 2：v0.4.1 跟进（P2）

#### 已完成（2026-06-30）

- ✅ flake8 opc_manager/ 清零（143→0，28 文件）
- ✅ flake8 tests/ 清零（119→0，28 文件，E402 合理忽略）
- ✅ DIRECTORY_STRUCTURE.md 更新到 v0.3.3
- ✅ PROJECT_STATUS.md 同步真实进度
- ✅ data_manager.py 补索引（finance_records.date/type + tasks.status/created_at）
- ✅ 16 处 `assertTrue(len())` → `assertGreater` 批量替换
- ✅ async_executor.py God file 拆分（913→448 行，facade + 3 mixin）
- ✅ mypy 15 errors 修复（async_executor_worker.py mixin 属性类型声明）
- ✅ skill_marketplace API key 哈希改 PBKDF2（裸 SHA-256 → PBKDF2-HMAC-SHA256 + salt）
- ✅ 三语 README 数据校正（模块数 90→99，测试数 3341→3299）+ 一致性校验 CI
- ✅ 审计日志链式哈希（prev_hash/current_hash + verify_chain() + DB 迁移 v6→v7 + writer drain bug 修复）
- ✅ Skill 生态借鉴分析文档（docs/research/SKILL_ECOSYSTEM_RESEARCH.md，研究 design.md / Anthropic-Cybersecurity-Skills / Ponytail）
- ✅ scenario_definitions.py God file 拆分（890→225 行 facade + 776 行 builtin，PEP 562 懒加载 re-export）
- ✅ tool_system.py 拆分 — 提取 AuditLogger 到 tool_audit_logger.py（887→754 行 + 158 行，关注点分离）
- ✅ 硬约束文档化 — docs/HARD_CONSTRAINTS.md（Ponytail 风格"永不削减"清单 + rationale + 执行机制，研究 P0 应用）

#### 已完成（2026-07-05）

- ✅ strategist_brain.py 拆分（884→176 行 Facade + 4 个独立服务：strategist_models / intent_understanding_service / planning_service / external_skill_resolver）
- ✅ reflector_brain.py 拆分（841→222 行 Facade + 4 个独立服务：reflector_models / quality_evaluator / next_action_decider / consequence_predictor）
- ✅ tests/ 分层为 unit(49)/integration(29)/e2e(8)，87 文件迁移
- ✅ 虚拟分层 — DIRECTORY_STRUCTURE.md 7 层映射 + ruff isort 软约束 + 96 个架构守护测试
- ✅ P0+P1 成熟度问题修复（18 项：版本号同步/幽灵函数清理/pre-commit/ruff 43 错误清零/三语 README/E2E 门控等）

#### 待办（大型任务）

- email/finance 全量覆盖率提升（专项已达 99%/100%，全量口径仅 17%/14.5%）
- 715 处 Mock → 真实组件重构（P1-8）

### Phase 3：v0.5.0 长期（P3 + 架构演进）

- `tool_system.py` 拆为 tool_registry/tool_audit/tool_handlers_fs/tool_handlers_smtp
- ~~`opc_hr` 充实或并入 opc_manager/hr/ 子包~~ ✅ 已解决 (2026-07-10): web_search.py 迁移到 opc_manager/web_search.py，消除 opc_hr 假分层目录
- ~~CI coverage 阈值 62% (含 frontend 总覆盖率 ~64%, opc_manager 单独 ~74%) → 目标 65%~~ ✅ 已完成 (2026-07-11, v0.3.10): `--cov-fail-under=65`（实际 66%），crm_skill 64 tests + 3 bug 修复
- ~~mypy 配置升级为 `disallow_untyped_defs = True`~~ ⏳ 进行中 (2026-07-11, v0.3.12 Batch 1): 全局启用，Batch 1 已移除 46 模块从 per-module overrides（83→37），返回类型+参数类型注解补全（`__init__`/`__post_init__`/`execute_goal`/`undo_*`/`**kwargs: Any` 等），mypy `disallow_untyped_defs = true` 全局生效。剩余 37 模块待 Batch 2（25 模块，3-5 untyped）+ Batch 3（12 模块，6+ untyped）渐进式移除
- ~~引入 `radon cc` 圈复杂度门禁~~ ✅ 已完成 (2026-07-11, v0.3.8): CI non-blocking 报告 → ✅ v0.3.11 转 D+ blocking
- ~~高复杂度函数降级（TD-066 核心）~~ ✅ 已完成 (2026-07-11, v0.3.9+v0.3.11): v0.3.9 降级 4 个 D/E 级函数 + v0.3.11 降级 6 个 D/E 级函数（`_parse_analysis_result` E(36)→A(2) / `finance_skill.execute_goal` D(30)→A(4) / `_extract_keywords` D(29)→A(2) / `_calculate_quality_score` D(28)→B(6) / `_parallel_data_analysis` D(22)→A(4) / `_execute_collaborative` D(21)→A(4)），radon cc D+ blocking 门禁已生效
- ~~补 IntentRouter/ToolSystem/TaskEngineV3 的 ADR~~ ✅ 已完成 (2026-07-11): [ADR-001](architecture/ADR-001-IntentRouter-design.md) / [ADR-002](architecture/ADR-002-ToolSystem-design.md) / [ADR-003](architecture/ADR-003-TaskEngineV3-design.md)

---

## 7. 关键约束（硬约束清单）

以下约束来自项目级 `project_memory.md`，违反即阻塞发布：

1. 密码存储必须使用带 salt 的 PBKDF2-HMAC-SHA256，禁止裸 SHA-256 ✅
2. 项目必须包含依赖锁文件以确保构建可复现 ✅
3. CI mypy 检查必须为阻塞状态 ✅
4. 发布前必须完成模拟真实用户使用的测试 ✅（Playwright E2E 21 用例 + 用户旅程 24 用例）
5. 项目必须包含 `scripts/start.sh` 一键启动脚本 ✅
6. ConsensusEngine 必须作为核心决策机制前置介入所有关键决策点 ✅
7. 三贤者系统必须采用并行投票架构（asyncio.gather）而非串行流水线 ✅
8. 共识门在关键决策失败时必须安全降级，禁止 fail-open ✅
9. 版本号必须在所有位置（VERSION/README/代码注释）保持一致 ✅

---

## 8. 文档索引

| 文档 | 路径 | 用途 |
|------|------|------|
| 项目 README（中） | [README.md](../README.md) | 用户入口 |
| 项目 README（英） | [README-EN.md](../README-EN.md) | 英文用户入口 |
| 项目 README（日） | [README-JP.md](../README-JP.md) | 日文用户入口 |
| 变更日志 | [CHANGELOG.md](../CHANGELOG.md) | 版本变更记录 |
| 成熟度评估 | [internal/PROJECT_MATURITY_ASSESSMENT_v0.3.3_20260629.md](internal/PROJECT_MATURITY_ASSESSMENT_v0.3.3_20260629.md) | 7 维度评估 + Phase 1 任务清单 |
| 架构设计 | [architecture/PARALLEL_SAGES_DESIGN.md](architecture/PARALLEL_SAGES_DESIGN.md) | 三贤者并行投票架构 |
| API 文档 | [API.md](API.md) | REST API 接口 |
| 用户试用指南 | [guides/USER_TRIAL_GUIDE.md](guides/USER_TRIAL_GUIDE.md) | 3 分钟配置 |
| 硬约束清单 | [HARD_CONSTRAINTS.md](HARD_CONSTRAINTS.md) | Ponytail 风格"永不削减"清单 |
| Skill 生态研究 | [research/SKILL_ECOSYSTEM_RESEARCH.md](research/SKILL_ECOSYSTEM_RESEARCH.md) | design.md / Anthropic / Ponytail 借鉴分析 |
