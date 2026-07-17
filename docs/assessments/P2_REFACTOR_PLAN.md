# P2 重构方案文档

**创建日期**: 2026-07-05
**项目版本**: v0.3.3
**前置评估**: [ASSESSMENT_D01_MATURITY.md](ASSESSMENT_D01_MATURITY.md)
**执行原则**: 文档先行 → 达成共识 → 再动手修改 → 充分验证

**执行状态（2026-07-05 更新）**:
- ✅ P2-13 tests/ 分层（87 文件迁移 + 11 路径修复 + test_user_journey 调整）
- ✅ P2-14 虚拟分层（DIRECTORY_STRUCTURE.md 补充 P2-15 新模块 + ruff isort 软约束 + 96 个架构守护测试）
- ✅ P2-15 God Class 拆分（StrategistBrain 884→176 行，ReflectorBrain 841→222 行，10 个独立服务模块）

---

## 执行摘要

| 任务 | 风险 | 工作量 | 建议 | 理由 |
|------|------|--------|------|------|
| P2-13 tests/ 分层 | 中 | 0.5 人日 | ✅ 执行 | 机械迁移，conftest.py 保留根目录即可 |
| P2-14 opc_manager/ 子包化 | **高** | 2 人日 | ⚠️ **改为虚拟分层** | 与 v0.3.3 决策冲突，250+ 导入改动违反 Surgical Changes |
| P2-15 God Class 拆分 | 中 | 1 人日 | ✅ 执行 | Facade 模式保 API，增量拆分，测试覆盖充分 |

**核心结论**: P2-13 + P2-15 执行物理重构，P2-14 改为虚拟分层（更新 DIRECTORY_STRUCTURE.md + ruff isort 规则），避免破坏 v0.3.3 稳定状态。

---

## P2-13: tests/ 重构为 unit/integration/e2e 分层

### 现状
- 87 个 test_*.py 文件平铺在 tests/ 根
- 已有 tests/e2e/ (1 文件), tests/tools/ (gate 脚本)
- tests/integration/ **不存在**
- tests/conftest.py 含 autouse fixture `_reset_global_singletons`（清理线程/DB/i18n，P0-1 修复关键）

### 目标结构
```
tests/
├── conftest.py              # 保留根目录（autouse fixture 必需）
├── __init__.py
├── unit/                    # ~45 个文件，纯 mock，无 IO
│   ├── __init__.py
│   ├── test_brain_modules.py
│   ├── test_agent_brain.py
│   ├── test_consensus_engine.py
│   └── ... (42 个)
├── integration/             # ~28 个文件，跨模块，tmp_path/DB
│   ├── __init__.py
│   ├── test_integration_modules.py
│   ├── test_settings.py
│   └── ... (25 个)
├── e2e/                     # ~9 个文件，真实服务/浏览器
│   ├── __init__.py
│   ├── conftest.py          # Playwright fixtures
│   ├── test_ui_playwright.py
│   ├── test_e2e_real.py     # 真实 API
│   └── ... (6 个)
└── tools/                   # 保留（gate 脚本，非 pytest）
```

### 迁移清单

#### → tests/unit/ (45 个)
- Brain/Agent: test_brain_modules, test_agent_brain, test_agent_loop_components, test_confirmer, test_consensus_engine, test_executor_opinion, test_reflector_prediction
- 业务逻辑: test_business_type_detector, test_scenario_definitions, test_unified_types, test_intent_router, test_extract_json, test_validators, test_error_handler, test_version
- Skill 单元: test_p1_skills, test_p2_skills, test_skill_reviews
- LLM 单元: test_llm_cache, test_llm_content, test_simple_llm_service, test_search_processor, test_embedding_service, test_ollama_backend
- 数据单元: test_data_manager, test_audit_log, test_secure_storage, test_undo_manager, test_session_context
- i18n: test_i18n, test_multilingual
- 并发: test_async_executor, test_llm_concurrency, test_parallel_executor, test_parallel_sages
- 其他: test_no_circular_import, test_smart_suggestions, test_knowledge_semantic, test_progress_emitter, test_real_progress, test_tool_system, test_memory_optimization, test_smoke_zero_coverage
- Regression: test_regression_imports, test_regression_structure, test_regression_session_state, test_regression_smoke, test_regression_i18n

#### → tests/integration/ (29 个)
- Integration: test_architecture_integration, test_async_frontend_integration, test_delta_integration, test_gamma_integration, test_integration_modules, test_integration_v35
- UI 集成: test_confirmation_dialog, test_dashboard_config, test_input_autocomplete, test_live_log_panel, test_result_cards, test_shortcuts_handler, test_timeline_view, test_undo_panel, test_ux_polish
- 数据集成: test_data_backup, test_memory_bridge, test_settings, test_security, test_security_deep
- Skill 集成: test_email_skill_coverage, test_finance_skill_coverage, test_skill_executors, test_marketplace_v2
- 性能: test_concurrent_access, test_performance, test_performance_ext
- 业务集成: test_onboarding, test_task_engine_v3, test_user_journey (mock-based 用户旅程，无真实服务/浏览器，归 integration)

#### → tests/e2e/ (8 个)
- 已有: test_ui_playwright
- 迁入: test_e2e_real (真实 API), test_ui_e2e_apptest (AppTest), test_e2e_user_journeys, test_e2e_user_workflow, test_integration_e2e, test_docker_deployment, test_start_script

> **微调说明（2026-07-05 实施时）**: `test_user_journey.py` 原计划归 e2e，但实施时发现：(1) 该文件全量 mock（"LLM calls and Streamlit UI are mocked throughout"），仅用 `tmp_path`，不符合 e2e "真实服务/浏览器" 定义；(2) 与 `test_ui_playwright.py` 同目录跑时，Playwright `sync_playwright()` 内部 event loop 未释放，导致后续 `asyncio.run()` 报 `RuntimeError: cannot be called from a running event loop`；(3) CI 中 `--ignore=tests/e2e` 会跳过该文件，造成覆盖丢失。故改归 integration。

### 执行步骤
1. 创建 tests/unit/, tests/integration/ 目录及 __init__.py
2. 使用 `git mv` 迁移文件（保留 git history）
3. 验证 tests/conftest.py 仍在 tests/ 根（pytest 自动发现）
4. 更新 pyproject.toml 的 testpaths（如有）
5. 运行 `pytest tests/unit/ -q` + `pytest tests/integration/ -q` + `pytest tests/e2e/ -q` 分层验证
6. 运行全量 `pytest tests/ -q` 确保无回归

### 风险与缓解
- **风险**: 文件移动后 IDE 缓存失效 → 缓解: 机械迁移，无内容修改
- **风险**: conftest.py 找不到 → 缓解: 保留在 tests/ 根，pytest 自动向上发现
- **风险**: CI 路径硬编码 → 缓解: 检查 .github/workflows/ 中的 pytest 路径

---

## P2-14: opc_manager/ 引入 services/ + infrastructure/ 子包

### ⚠️ 重要：与 v0.3.3 决策冲突

**v0.3.3 决策记录**（2026-06-29）：明确决定**不进行物理目录重组**，原因：
- 全量重组需改 250+ 导入语句（74 相对 + 89 绝对 + 87 测试）
- 违反 Simplicity First / Surgical Changes 原则
- v0.3.3 已稳定，3360 测试全绿

### 现状
- 115 个 .py 文件（104 顶层 + 8 export/ + 3 i18n/）
- 已有子目录: export/, i18n/
- 导入风格混合: 相对导入 + 绝对导入并存
- `__init__.py` 显式导出 60+ 符号

### 建议方案：虚拟分层（替代物理子包化）

**不移动文件**，而是通过以下方式实现分层：

1. **更新 DIRECTORY_STRUCTURE.md** 到 v0.3.3+
   - 按 7 层（Input/Control/Output/Skills/Infra/DB/Protocol）虚拟分类
   - 每个文件标注所属层
   - 提供导航价值，无需物理移动

2. **添加 ruff isort 规则**（pyproject.toml）
   ```toml
   [tool.ruff.lint.isort]
   known-first-party = ["opc_manager"]
   section-order = ["future", "standard-library", "third-party", "opc_manager", "first-party", "local-folder"]
   ```
   通过 import 顺序强制开发者感知层次

3. **添加架构守护测试**（tests/unit/test_architecture_layers.py）
   - 断言 Brain 层不依赖 Skills 层
   - 断言 Skills 层不依赖 Brain 层
   - 断言 DB 层不依赖业务层

### 物理子包化方案（备选，不推荐）

如用户坚持物理子包化：

| 子包 | 文件数 | 内容 |
|------|--------|------|
| `infrastructure/` | ~30 | data_manager, settings*, config, audit_log, monitoring, mcp*, async_executor*, utils, unified_types |
| `services/` | ~22 | agent_loop, task_engine_v3*, scenario*, state_manager, session_context |
| 顶层保留 | ~63 | Brain 文件, consensus_engine, protocols, skills, input, output |

**代价**：250+ 导入改动，3360 测试需全量回归，2 人日工作量，高回归风险。

### 推荐：执行虚拟分层，跳过物理子包化

---

## P2-15: God Class 拆分（StrategistBrain + ReflectorBrain）

### 现状
- strategist_brain.py: 884 行, 20 方法, 4 数据类
- reflector_brain.py: 841 行, 18 方法, 2 数据类
- 测试充分: test_brain_modules.py (78), test_reflector_prediction.py (12), test_agent_brain.py (36), test_parallel_sages.py (26)

### 拆分策略：Facade + 协作服务

**核心原则**: 保留 `StrategistBrain` / `ReflectorBrain` 作为对外门面（向后兼容），内部职责拆到独立 Service 类。

### StrategistBrain 拆分（5 个新模块）

| 新模块 | 内容 | 行数 | 依赖 |
|--------|------|------|------|
| `strategist_models.py` | ConstraintType, Constraint, Intent, Step, ExecutionPlan | ~80 | 无 |
| `intent_understanding_service.py` | understand_intent + 9 个相关方法 | ~280 | intent_types, utils, llm |
| `external_skill_resolver.py` | _fallback_to_external + 缓存 | ~60 | UserProfile, Marketplace |
| `planning_service.py` | plan + 5 个规划方法 | ~280 | utils, llm, skill_registry |
| `strategist_brain.py`（Facade） | __init__, to_dict, from_dict, express_opinion + 委托 | ~120 | 上述 3 服务 |

### ReflectorBrain 拆分（5 个新模块）

| 新模块 | 内容 | 行数 | 依赖 |
|--------|------|------|------|
| `reflector_models.py` | EvaluationResult, NextActionType, CorrectionStrategy, Evaluation, NextAction + 常量 | ~100 | 无 |
| `quality_evaluator.py` | evaluate_result + 5 个评估方法 | ~260 | utils, llm |
| `next_action_decider.py` | decide_next_action + suggest_improvement + suggest_correction_strategy + _check_placeholders | ~200 | 无（纯逻辑） |
| `consequence_predictor.py` | predict_consequence + _predict_with_llm + _predict_with_rules + async | ~220 | utils, consensus_engine, llm |
| `reflector_brain.py`（Facade） | __init__, to_dict, from_dict, express_opinion + 委托 | ~80 | 上述 3 服务 |

### 执行顺序（低风险递进）

每步独立提交、独立验证（跑 test_brain_modules + test_reflector_prediction + test_agent_brain + test_parallel_sages + test_no_circular_import）：

1. **抽数据模型** → strategist_models.py / reflector_models.py（纯搬运，零逻辑变更）
2. **抽 ConsequencePredictor**（ReflectorBrain 侧，已有专属测试 test_reflector_prediction.py）
3. **抽 PlanningService 和 IntentUnderstandingService**（StrategistBrain 侧，test_brain_modules.py 覆盖充分）
4. **抽 NextActionDecider 和 QualityEvaluator**（ReflectorBrain 侧）
5. **抽 ExternalSkillResolver**（依赖 lazy import，需关注循环导入）
6. **Facade 收口**（保持公共 API 不变，agent_loop.py 等调用方零改动）

### 风险与缓解
- **风险**: express_opinion 依赖 Brain 整体状态 → 缓解: 上下文 dict 透传给服务
- **风险**: _fallback_to_external 用 time.time() 全局时钟 → 缓解: 注入可替换 clock 函数
- **风险**: 循环导入 → 缓解: test_no_circular_import.py 守门，每步验证
- **风险**: agent_loop.py 调用方破坏 → 缓解: Facade 保 API，零改动

---

## 验证计划

### 每步验证（P2-15）
```bash
# 单元测试
pytest tests/unit/test_brain_modules.py tests/unit/test_reflector_prediction.py tests/unit/test_agent_brain.py tests/unit/test_parallel_sages.py tests/unit/test_no_circular_import.py -v

# 静态分析
ruff check opc_manager/strategist_brain.py opc_manager/reflector_brain.py opc_manager/strategist_models.py opc_manager/reflector_models.py
mypy opc_manager/ --ignore-missing-imports --follow-imports=silent
```

### 全量验证（P2-13 + P2-15 完成后）
```bash
# 分层验证
pytest tests/unit/ -q --timeout=60
pytest tests/integration/ -q --timeout=60
pytest tests/e2e/ -q --timeout=180

# 全量验证
pytest tests/ -q --timeout=180

# 静态分析
ruff check .
mypy opc_manager/ --ignore-missing-imports --follow-imports=silent
```

### 发布门控
| 门控 | 目标 | 验证命令 |
|------|------|----------|
| Unit 测试全绿 | 0 失败 | `pytest tests/unit/ -q` |
| Integration 测试全绿 | 0 失败 | `pytest tests/integration/ -q` |
| E2E 测试全绿 | 0 失败 | `pytest tests/e2e/ -q` |
| ruff 0 错误 | 0 | `ruff check .` |
| mypy 0 错误 | 0 | `mypy opc_manager/ --ignore-missing-imports` |
| 无循环导入 | 通过 | `pytest tests/unit/test_no_circular_import.py` |

---

## 执行顺序总览

1. **P2-13 tests/ 分层**（0.5 人日）— 机械迁移，先执行
2. **P2-15 God Class 拆分**（1 人日）— 6 步增量，每步验证
3. **P2-14 虚拟分层**（0.3 人日）— 更新文档 + 架构守护测试
4. **全量验证** — ruff + mypy + pytest 三层
5. **更新 ASSESSMENT_D01_MATURITY.md** — 标记已修复项
6. **Git commit + push**

**预计总工作量**: 1.8 人日

---

## 附录：调查数据来源

- tests/ 调查: 87 文件 / 3234 测试函数 / conftest.py 分析
- opc_manager/ 调查: 115 文件 / 7 层分类 / 依赖图
- God Class 调查: 38 方法 / 6 数据类 / 152 测试用例
