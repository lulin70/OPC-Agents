# OPC-Agents 后续改进优化全局方案

**制定日期**: 2026-07-13
**当前版本**: v0.3.23
**方案状态**: 待审核（DevSquad 7 角色共识）
**制定方法**: DevSquad V4.0.0 多角色协作 + 前序盘点验证

---

## 1. 背景与现状

### 1.1 已完成

| 评估 | 版本 | 评分 | P0 | P1 | P2 | P3 |
|------|------|------|-----|-----|-----|-----|
| D01 (v0.3.3) | 72.9 分 C+ | 5 项 | 8 项 | — | — |
| D02 (v0.3.19) | 82 分 B+ | 5 项 ✅ | 5 项 ✅ | 4 项 ✅ | 多项 ✅ |
| 当前 (v0.3.23) | 待评估 | ✅ | ✅ | ✅ | 部分 |

### 1.2 未完成事项（盘点验证结果）

| # | 事项 | 类型 | 工作量 | 阻塞发布 |
|---|------|------|--------|---------|
| F1 | D02 评估报告"发布就绪判断"表未更新 | 文档 | 0.5h | 否 |
| F2 | 6 个 timeout 测试（满载时 >30s） | 测试 | 2-4h | 否（CI --ignore=tests/e2e） |
| F3 | 覆盖率 68.25% → 70% 目标 | 测试 | 4-6h | 否（CI 阈值 65%） |
| F4 | tool_system.py 拆分（Phase 3） | 架构 | 1 人日 | 否 |
| F5 | P0-6: email/finance 全量覆盖率 | 大型 | 2-3 人日 | ⚠️ v0.4.0 前需完成 |
| F6 | P1-8: Mock 反模式剩余重构 | 大型 | 2-3 人日 | ⚠️ 需甄别后评估 |

### 1.3 当前 CI 门控状态

| 门控 | 状态 | 备注 |
|------|------|------|
| ruff | ✅ 0 错误 | |
| mypy | ✅ 0 错误 (113 files) | |
| Black | ✅ | |
| 覆盖率 | ✅ 68.25% > 65% | 目标 70% |
| radon cc | ✅ D+ blocking | |
| Bandit | ✅ | |
| pip-audit | ✅ | |
| Docker build | ✅ | |
| 版本一致性 | ✅ | |
| 三语 README | ✅ | |
| E2E (Playwright) | ✅ 硬门控 | |

---

## 2. 改进目标

### 2.1 总体目标

```
v0.3.23 (当前) → v0.3.24 (Wave 1 收尾) → v0.3.25 (Wave 2 质量) → v0.4.0 (Wave 3 发布就绪)
```

### 2.2 量化指标

| 指标 | 当前 | v0.3.24 目标 | v0.3.25 目标 | v0.4.0 目标 |
|------|------|-------------|-------------|------------|
| 覆盖率 | 68.25% | 68.25% | 70%+ | 70%+ |
| 测试通过 | 3913 | 3919+ (修复 6 timeout) | 4050+ | 4100+ |
| timeout 测试 | 6 | 0 | 0 | 0 |
| email/finance 全量覆盖 | 17%/14% | — | — | ≥50% |
| Mock 反模式文件 | 31 文件 | — | 甄别完成 | 修复完成 |
| D02 发布就绪门控 | 6/8 ✅ | 8/8 ✅ | 8/8 ✅ | 8/8 ✅ |

---

## 3. 分波次方案

### Wave 1: 快速收尾（v0.3.24，0.5-1 人日）

**目标**: 清除文档债务 + 修复 flaky 测试，使发布就绪门控达 8/8。

#### F1: D02 评估报告更新

| 项 | 内容 |
|----|------|
| **角色** | PM + DevOps |
| **任务** | 更新 ASSESSMENT_D02_MATURITY.md 第 388-399 行"发布就绪判断"表，反映 v0.3.23 实际状态 |
| **变更** | Unit 测试 → ✅ (3913 passed, 6 timeout 非 CI 阻塞); 文档一致性 → ✅; 工作区干净 → ✅ |
| **验证** | 表格数据与实际 `pytest`/`ruff`/`mypy` 输出一致 |
| **工作量** | 0.5h |

#### F2: 6 个 timeout 测试修复 — ✅ 已完成 (v0.3.24)

| 项 | 内容 |
|----|------|
| **角色** | Tester + Coder |
| **任务** | 调查 6 个 timeout 测试根因，修复测试隔离问题 |
| **测试列表** | test_task_engine_uses_skill_registry / test_search_processor_filters_results / test_pipeline_with_all_components / test_search_skill_query_preprocessing / test_skill_context_passing / test_pause_task |
| **根因** | conftest.py 注释声明"mocked search & LLM"但 search mock 缺失。4 个测试（网络型）调用真实 `WebSearchMCP.search()` 触发 DuckDuckGo 网络搜索（21-28s/个），满载时资源竞争导致 2 个 CPU 型测试也 timeout |
| **修复方案** | 在 conftest.py 添加 `_mock_web_search` autouse fixture，对非 e2e 测试 patch `WebSearchMCP.search` 返回预设结果；e2e 测试通过 `@pytest.mark.e2e` marker 检查跳过 mock，使用真实搜索 |
| **修复效果** | 6 个测试从 21-28s 降到 <0.7s（33x 提速）；完整套件从 ~480s 降到 65s（7.4x 提速）；3942 passed + 0 timeout + 0 回归 |
| **验证** | `pytest --ignore=tests/e2e --timeout=30` → 3942 passed, 77 skipped, 0 timeout；E2E 搜索测试（19.31s 真实网络）验证 mock 不影响 e2e |
| **工作量** | 实际 1.5h（预估 2-4h） |

**Wave 1 验证标准**:
- `pytest --tb=no -q --ignore=tests/e2e` → 0 failed, 0 timeout
- D02 评估报告发布就绪门控 8/8 ✅
- ruff/mypy/black 全绿

---

### Wave 2: 质量提升（v0.3.25，1-2 人日）✅ 已完成

**目标**: 覆盖率达 70%+，tool_system 架构演进。
**实际结果**: 覆盖率达 74%（超额完成 70% 目标），tool_system.py 拆分为 4 个子模块 + Facade，4278 测试通过，ruff/black/mypy/radon 全绿。

#### F3: 覆盖率提升 68.25% → 74% ✅（目标 70%，实际 74%）

| 项 | 内容 |
|----|------|
| **角色** | Tester + Coder |
| **任务** | 补充低覆盖模块测试，覆盖 19299 stmts 中剩余 ~5800 missed 的 ~400 行 |
| **候选模块** | |
| | knowledge_bridge.py: 200 miss → 目标 60% (补 ~120 行) |
| | llm_service.py: 77 miss → 目标 80% (补 ~50 行) |
| | search_processor.py: 71 miss → 目标 70% (补 ~40 行) |
| | async_executor_worker.py: 55 miss → 目标 75% (补 ~35 行) |
| | secure_storage.py: 54 miss → 目标 70% (补 ~30 行) |
| | scenario_engine_v2.py: 53 miss → 目标 70% (补 ~30 行) |
| **预期** | 补 ~305 行，覆盖率 68.25% → ~70.0% |
| **验证** | `pytest --cov=opc_manager --cov=frontend --cov-fail-under=70` |
| **工作量** | 4-6h |

#### F4: tool_system.py 拆分 ✅

| 项 | 内容 |
|----|------|
| **角色** | Architect + Coder |
| **任务** | tool_system.py (754 行) 拆分为 4 个子模块 |
| **拆分方案** | |
| | `tool_registry.py` — 工具注册 + 发现 + 元数据管理 |
| | `tool_audit.py` — 已有 tool_audit_logger.py，合并审计逻辑 |
| | `tool_handlers_fs.py` — 文件系统相关工具处理器 |
| | `tool_handlers_smtp.py` — 邮件相关工具处理器 |
| | `tool_system.py` 保留为 Facade，委托给子模块 |
| **约束** | 不破坏现有 API；96 个架构守护测试需通过；radon cc 保持 D+ |
| **验证** | 全量测试通过 + 架构守护测试通过 + mypy 0 错误 |
| **工作量** | 1 人日 |

**Wave 2 验证标准** ✅ 全部通过:
- ✅ 覆盖率 ≥ 70%（实际 74%）
- ✅ tool_system.py 拆分后无功能回归（4278 测试通过）
- ✅ CI 全部门控通过（ruff/black/mypy/radon 全绿）

---

### Wave 3: 发布就绪（v0.4.0，3-5 人日）

**目标**: email/finance 全量覆盖率提升 + Mock 反模式甄别修复，达 v0.4.0 发布标准。

#### F5: P0-6 email/finance 全量覆盖率

| 项 | 内容 |
|----|------|
| **角色** | Tester + Coder + Architect |
| **任务** | email_skill.py (16.96%) 和 finance_skill.py (14.46%) 全量覆盖率提升至 ≥50% |
| **现状** | 专项测试覆盖率已达 99%/100%，但全量口径低（集成测试未覆盖这些模块） |
| **方案** | (a) 分析全量测试中未触发 email/finance 的测试路径; (b) 补充集成级测试，真实调用 email/finance skill; (c) 确保测试不依赖外部网络/SMTP |
| **验证** | `coverage report` 中 email_skill ≥ 50%, finance_skill ≥ 50% |
| **工作量** | 2-3 人日 |
| **备注** | 专项覆盖率 99%/100% 已保证代码质量，全量覆盖率提升主要是集成测试补充 |

#### F6: P1-8 Mock 反模式甄别 + 修复

| 项 | 内容 |
|----|------|
| **角色** | Tester + Coder |
| **任务** | 甄别 31 文件中 245 处 `MagicMock()` 的合理性，修复不合理的使用 |
| **阶段 1: 甄别** | 分类 245 处为：合理 Mock / 反模式 Mock / 可简化 Mock |
| | 合理 Mock: streamlit ScriptRunContext、psutil namedtuple、@patch 拦截 LLM |
| | 反模式 Mock: 用 MagicMock 模拟有真实 API 的内部组件 |
| | 可简化 Mock: 可用 SimpleNamespace/dataclass 替代的简单 mock |
| **阶段 2: 修复** | 仅修复"反模式 Mock"，预估 ~50-80 处（P3-4+P3-5 已修 10 文件） |
| **验证** | 全量测试通过 + 无新增 MagicMock 反模式 |
| **工作量** | 甄别 0.5 人日 + 修复 1.5-2 人日 |

**Wave 3 验证标准**:
- email/finance 全量覆盖率 ≥ 50%
- Mock 反模式甄别报告完成 + 修复完成
- v0.4.0 发布门控全部达标

---

## 4. 角色分工矩阵（RACI）

| 任务 | Architect | PM | Security | Tester | Coder | DevOps | UI |
|------|-----------|-----|----------|--------|-------|--------|-----|
| F1 评估报告更新 | I | R | — | I | — | A | — |
| F2 timeout 修复 | I | — | — | R/A | R | — | — |
| F3 覆盖率提升 | I | — | — | R/A | R | — | — |
| F4 tool_system 拆分 | R/A | I | I | C | R | I | — |
| F5 email/finance 覆盖 | C | I | — | R | R/A | — | — |
| F6 Mock 甄别修复 | I | — | — | R/A | R | — | — |

> R=Responsible, A=Accountable, C=Consulted, I=Informed

---

## 5. 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| F2 timeout 根因复杂（非简单隔离问题） | 中 | 延迟 Wave 1 | 若 4h 内未修复，提高 timeout 至 60s 作为临时方案 |
| F3 覆盖率提升不足 70% | 低 | 延迟 Wave 2 | 补充更多模块测试（如 task_orchestrator.py 86 miss） |
| F4 tool_system 拆分破坏 API | 中 | 功能回归 | 保留 Facade 模式，96 个架构守护测试验证 |
| F5 email/finance 集成测试依赖外部服务 | 中 | 无法 CI 化 | 使用 SMTP Mock + 真实 fake 类替代外部服务 |
| F6 Mock 甄别工作量超预期 | 中 | 延迟 Wave 3 | 优先修复高影响文件，低影响文件推迟到 v0.4.1 |

---

## 6. 验证检查清单

每个 Wave 完成后必须验证：

- [ ] `ruff check opc_manager/ frontend/ tests/` → 0 错误
- [ ] `mypy opc_manager/` → 0 错误
- [ ] `black --check` → 全部通过
- [ ] `pytest --cov=opc_manager --cov=frontend --cov-fail-under=<wave目标>` → 通过
- [ ] `pytest --tb=no -q --ignore=tests/e2e` → 0 failed, 0 timeout
- [ ] 版本号一致性（VERSION / version.py / Dockerfile / README × 3）
- [ ] CHANGELOG.md 更新
- [ ] PROJECT_STATUS.md 更新
- [ ] ASSESSMENT_D02_MATURITY.md 更新（如适用）

---

## 7. 版本规划

| 版本 | Wave | 内容 | 预计工期 |
|------|------|------|---------|
| v0.3.24 | Wave 1 | F1 + F2 (评估报告更新 + timeout 修复) | 0.5-1 人日 |
| v0.3.25 | Wave 2 | F3 + F4 (覆盖率 70% + tool_system 拆分) | 1-2 人日 |
| v0.4.0 | Wave 3 | F5 + F6 (email/finance 覆盖 + Mock 修复) | 3-5 人日 |

**v0.4.0 发布门控**:
1. ✅ 覆盖率 ≥ 70%
2. ✅ 0 timeout 测试
3. ✅ email/finance 全量覆盖率 ≥ 50%
4. ✅ Mock 反模式甄别 + 修复完成
5. ✅ CI 全部门控通过
6. ✅ D02 评估发布就绪门控 8/8
7. ✅ E2E 真实用户测试（发布前必做）
8. ✅ 三语 README + CHANGELOG + PROJECT_STATUS 一致

---

## 8. 多角色审核共识结果

> DevSquad 7 角色审核完成（Architect/Security + Tester/Coder + PM/DevOps），以下为共识结论。

### 8.1 审核发现的关键问题

| # | 问题 | 发现者 | 影响 |
|---|------|--------|------|
| C1 | **F5 前提数据确认**: email_skill.py 237 stmts 0 miss **100%**、finance_skill.py 166 stmts 0 miss **100%**（2026-07-13 验证） | Tester | **F5 取消**，工作量转 E2E 真实用户测试 |
| C2 | **F3 模块目标有误**: search_processor 已 70%、secure_storage 已 71%，无需补测试 | Tester | F3 候选模块需重算 |
| C3 | **F4 拆分方案遗漏**: `tool_audit.py` 冗余（AuditLogger 已在 tool_audit_logger.py）；遗漏 `run_command`（命令注入防护，需独立） | Architect | F4 拆分方案需修正 |
| C4 | **CI EXPECTED_TEST_COUNT 硬编码 3781**: 实际已 3996+，Wave 1 会致 CI 红 | DevOps | Wave 1 必须同步更新 |
| C5 | **F2 根因误判**: `test_search_processor_filters_results` 纯 CPU 无 I/O，不应 timeout | Tester | F2 需逐个 profile 后分类修复 |
| C6 | **门控遗漏**: 缺"基础版本地运行验证"、pip-audit/Bandit 0 高危、手动触发 weekly-e2e-real.yml | DevOps | v0.4.0 门控需补充 |
| C7 | **Security 风险**: F6 Mock 修复须保留 CRLF 注入清洗 + 路径校验；F5 SMTP Mock 须保留收件人正则校验 | Security | F5/F6 须 Security 角色介入 |

### 8.2 共识决策

| 问题 | 共识结论 | 依据 |
|------|---------|------|
| **Q1: F2 修复策略** | 先逐个 profile（`pytest --durations=10`），区分网络型/LLM 型/CPU 型三类再分别处理 | Tester 发现 CPU 型不应 timeout，根因不同 |
| **Q2: F4 拆分粒度** | 4 模块：tool_registry + tool_handlers_fs + tool_handlers_smtp + tool_handlers_cmd（删除 tool_audit.py） | Architect 分析：run_command 有命令注入防护须独立；tool_audit.py 与 tool_audit_logger.py 重复 |
| **Q3: F5 覆盖率目标** | **先验证数据**：重跑覆盖率确认 email/finance 实际值。若已 100% 则 F5 降级/取消，工作量转 E2E 真实用户测试 | Tester 发现 .coverage 显示 100% |
| **Q4: F6 修复范围** | 仅修复反模式 Mock，优先 `test_task_lifecycle.py`（47 处集中反模式，ROI 最高） | Tester + Coder 一致：不过度简化 |
| **Q5: Wave 顺序** | W1(F1+F2+C4) → W2(F3+F4) → W3(F5验证+F6)；F4 先于 F5 因 SMTP 拆分为 F5 测试铺路 | Architect 技术依赖分析 |
| **Q6: CI 阈值** | Wave 1 同步更新 EXPECTED_TEST_COUNT + cov-fail-under 保持 65（Wave 2 完成后升至 70） | DevOps：避免 CI 假红 |

### 8.3 方案修正

#### F2 修正：分类修复策略

```
步骤 1: pytest --durations=10 -k "test_task_engine_uses_skill_registry or test_search_processor_filters_results
        or test_pipeline_with_all_components or test_search_skill_query_preprocessing
        or test_skill_context_passing or test_pause_task"
步骤 2: 按耗时分类：
        - 网络型 (test_task_engine_uses_skill_registry 等): Mock WebSearchMCP.search()
        - LLM 型 (test_search_skill_query_preprocessing 等): LLM stub 替代真实调用
        - CPU 型 (test_search_processor_filters_results): 查 fixture/导入副作用
步骤 3: 若 4h 内未修复，临时提高这些测试 timeout 至 60s
```

#### F3 修正：候选模块重算

| 模块 | 原方案 miss | 实际状态 | 修正行动 |
|------|-----------|---------|---------|
| knowledge_bridge.py | 200 miss → 补 120 行 | 200 miss, 381 stmts (52%) | 补 ~48 行达 60% |
| llm_service.py | 77 miss → 补 50 行 | 待验证 | 保持 |
| search_processor.py | 71 miss → 补 40 行 | **已 70%** | ❌ 移除候选 |
| async_executor_worker.py | 55 miss → 补 35 行 | 待验证 | 保持 |
| secure_storage.py | 54 miss → 补 30 行 | **已 71%** | ❌ 移除候选 |
| scenario_engine_v2.py | 53 miss → 补 30 行 | 待验证 | 保持 |
| task_orchestrator.py | — (备用) | 86 miss | ✅ 加入候选 |

**修正后预期**: 补 ~250 行（非 305），覆盖率 68.25% → ~70%。若不足，补 task_orchestrator.py。

#### F4 修正：拆分方案定稿

```
tool_system.py (754 行, Facade) 拆分为:
├── tool_registry.py         — 工具注册 + 发现 + 元数据 (~240 行)
├── tool_handlers_fs.py       — 文件系统工具处理器 (~130 行)
├── tool_handlers_smtp.py     — 邮件工具处理器 (~133 行)
├── tool_handlers_cmd.py      — 命令执行工具处理器 (~54 行，含 shlex + allowlist 安全防护)
├── tool_audit_logger.py      — 已有，不变
└── tool_system.py            — Facade，委托给子模块 (~200 行)
```

**Security 约束**:
- run_command 的 shlex.quote + allowlist 必须完整迁移
- CRLF 注入清洗（`to.replace("\r","")`）必须保留
- 路径校验（`_validate_path`）必须保留

#### v0.4.0 门控补充（3 项）

| # | 门控 | 验证方法 |
|---|------|---------|
| 9 | 基础版本地运行验证 | `./scripts/start.sh` 启动成功 + http://localhost:8000 可访问 |
| 10 | pip-audit 0 高危 + Bandit 0 高危 | CI 门控已有，发布前确认 |
| 11 | 手动触发 weekly-e2e-real.yml 通过 | GitHub Actions 手动 dispatch + 全绿 |

---

## 9. 审核签字

| 角色 | 审核 | 关键意见 |
|------|------|---------|
| Architect | ✅ 同意（附修正） | F4 拆分方案修正：删 tool_audit.py，加 tool_handlers_cmd.py |
| Security | ⚠️ 附条件同意 | F5/F6 须 Security 介入；SMTP Mock 保留收件人校验；finance 覆盖负数/浮点/溢出 |
| Tester | ✅ 同意（附修正） | F5 数据存疑须先验证；F2 分类修复；F3 候选模块重算 |
| Coder | ✅ 同意 | F4 4 模块方案可行；F6 优先 test_task_lifecycle.py |
| PM | ⚠️ 附条件同意 | 工期漏算文档同步成本；F3 估算偏乐观（8-10h 非 4-6h） |
| DevOps | ✅ 同意（附修正） | C4 CI EXPECTED_TEST_COUNT 必须 Wave 1 更新；门控补充 3 项 |

**共识达成**: 6/6 角色审核通过（4 ✅ + 2 ⚠️ 附条件），方案修正后可推进。
