# OPC-Agents v0.3.2 高成本技术债消除计划

**制定日期**：2026-06-26
**前置文档**：`PROJECT_TIDY_ASSESSMENT_v0.3.0-beta_20260626.md`（v0.3.1 复评 72/B-）
**目标**：逐一消除 v0.3.1 遗留的 4 项高成本技术债，综合分 72 → ≥78（B+ 下限）

## 调研发现（2026-06-26）

### 重大发现：P0-3 修复方向错误（循环验证漏检）

**原 P0-3 修复**：把三语 README 第42行从 `email_skill 99%/finance_skill 100%` 改为 `email 16.96%/finance 14.46%（已记入 v0.3.1 技术债）`，依据是 TECH_DEBT P2-2 的"email 16.96%, finance 14.46%"。

**实际真相**（实测命令）：
```
$ pytest tests/test_email_skill_coverage.py --cov=opc_manager.email_skill --cov-report=term
opc_manager/email_skill.py    230    3    99%   207, 263-264

$ pytest tests/test_finance_skill_coverage.py --cov=opc_manager.finance_skill --cov-report=term
opc_manager/finance_skill.py   166    0   100%
```

**16.96%/14.46% 的真实含义**：`COVERAGE_BASELINE.md:65-66` 记录的 **Sprint 2 之前的历史基线**（email 39/230 行、finance 24/166 行）。`V030_REMEDIATION_PLAN.md:64` 显示 Sprint 2 已完成提升至 99%/100%。

**错误根因**：评估者未跑实际测试，仅"两文档对照"得出"README 措辞误导"的错误结论，把正确的当前数据改成历史基线。这正是 project_memory.md 已记录的"覆盖率口径混淆"教训的再次发作。

### 调研数据汇总

| 项 | 实测数据 |
|---|---|
| flake8 F401（未用导入） | 279 项 |
| flake8 F841（未用变量） | 69 项 |
| God Class 行数 | task_engine_v3.py 1853 / business_type_detector_v2.py 1197 / skill_marketplace.py 1073 / settings.py 1067 / llm_content.py 1060 |
| God Class 结构 | task_engine_v3.py 19 个 class+def / business_type_detector_v2.py 19 / skill_marketplace.py 43 / settings.py 44 / llm_content.py 24 |
| opc_manager/ 文件数 | 86 个 .py |
| tests/ 文件数 | 87 个 .py |
| email_skill.py 覆盖率 | 99%（3 行未覆盖：207, 263-264） |
| finance_skill.py 覆盖率 | 100% |

## 5 阶段计划

### Phase 0: 纠正 P0-3 错误修复（紧急，P0 级文档错误）

**范围**：三语 README 第42行覆盖率措辞纠正。

**修改**：
- `README.md:42` / `README-EN.md:42` / `README-JP.md:42`
- 改回 `email_skill 99% / finance_skill 100%`
- 补充标注 `（Sprint 2 已从 16.96%/14.46% 基线提升）` 澄清口径

**验证**：
- `grep -n "99%" README.md README-EN.md README-JP.md` → 3 处一致
- `grep -n "16.96" README.md README-EN.md README-JP.md` → 仅在标注语境出现，不再作为当前数据
- `pytest tests/test_email_skill_coverage.py tests/test_finance_skill_coverage.py --cov=opc_manager.email_skill --cov=opc_manager.finance_skill` → 99%/100%

### Phase 1: flake8 F401+F841 修复（348 项）

**范围**：删除 279 项未用导入 + 69 项未用变量。零行为变更。

**Top 5 文件**（占 109/348 = 31%）：
1. `tests/test_skill_executors.py` 25 项
2. `tests/test_integration_modules.py` 24 项
3. `opc_manager/agent_loop.py` 24 项
4. `tests/test_agent_brain.py` 13 项
5. `frontend/components/undo_panel.py` 13 项

**策略**：
- F401：直接删除未用 import 行
- F841：删除未用变量赋值，或改用 `_` 占位
- 不修改任何函数体逻辑

**验证**：
- `flake8 opc_manager/ frontend/ tests/ --select=F401,F841` → 0 项
- `PYTHONPATH=. pytest --tb=short -q` → 3165 passed / 0 failed（与基线一致）

### Phase 2: 补 email 未覆盖 3 行（瘦身版）

**范围**：`email_skill.py` 第 207, 263-264 行。finance 已 100%。

**策略**：
- 读源码确认 3 行对应的分支
- 补充边界条件测试，触发这些分支
- 遵循 DevSquad 测试铁律：失败要报告，绝不改断言；维度完整（happy/error/boundary）

**验证**：
- `pytest tests/test_email_skill_coverage.py --cov=opc_manager.email_skill` → 100%
- 全量测试 0 failed

### Phase 3: 5 个 God Class 保守提取 + facade

**范围**：5 个文件共 6250 行，按职责提取子模块，原文件保留作 facade。

**策略**（保守提取）：
1. 分析每个 God Class 的职责分组（class/def 聚类）
2. 提取职责内聚的子模块到新文件（如 `task_engine_v3_planner.py`、`task_engine_v3_executor.py`）
3. 原文件保留作 facade：`from .task_engine_v3_planner import *`
4. **不修改任何公开 API**，保持向后兼容
5. 逐个文件处理，每个独立测试+提交

**目标**：每个原文件 ≤500 行（facade 仅做 re-export）

**验证**：
- 原文件公开 API 不变（`grep -r "from opc_manager.task_engine_v3 import"` 引用方不变）
- 全量测试 0 failed
- 每个原文件 ≤500 行（`wc -l opc_manager/task_engine_v3.py` 等）

### Phase 4: 目录按 IOC 分层重组

**范围**：opc_manager/ 86 文件 + tests/ 87 文件按 input/output/control 分层。

**策略**：
- **input/**：数据接收层（intent_classifier、validators、task_types、input_autocomplete 等）
- **output/**：响应输出层（error_handler、agent_error_handler、result_cards、live_log_panel 等）
- **control/**：业务控制层（agent_loop、task_engine、consensus_engine、executor_brain 等）
- 原顶层保留 `__init__.py` re-export 子目录内容，保持向后兼容
- tests/ 镜像 opc_manager/ 结构

**风险**：影响面最大（所有 import 路径）。最后做。

**验证**：
- 所有 import 路径更新
- 全量测试 0 failed
- 目录结构文档同步（README、PROJECT_STATUS）

## 推进规则

1. **逐项推进 + 逐项提交**：每个 Phase 独立测试 + commit + push
2. **每个 Phase 前后跑全量测试**：确保零回归
3. **每个 Phase 完成后更新本文档**：标注完成状态 + 实测数据
4. **遵循 DevSquad Delivery Workflow**：Implement → Test → Walkthrough → Annotate → Docs → Cleanup → Push
5. **遵循用户原则**：Simplicity First / Surgical Changes / Goal-Driven Execution

## 进度跟踪

| Phase | 状态 | Commit | 测试 | 备注 |
|---|---|---|---|---|
| Phase 0 | 待开始 | — | — | 纠正 P0-3 错误 |
| Phase 1 | 待开始 | — | — | flake8 348 项 |
| Phase 2 | 待开始 | — | — | email 3 行 |
| Phase 3 | 待开始 | — | — | 5 God Class |
| Phase 4 | 待开始 | — | — | IOC 分层 |

## 教训记录（本计划制定过程中发现）

**循环验证漏检（再次发作）**：P0-3 评估者未跑实际测试，仅"两文档对照"得出错误结论。这与 project_memory.md 已记录的"版本一致性验证教训"和"Marker覆盖率验证教训"同类。**已确认 project_memory.md 中"覆盖率口径混淆"教训需要强化：必须以 `pytest --cov` 实测命令输出为唯一权威数据源，不得以文档间对照作为覆盖率结论依据。**
