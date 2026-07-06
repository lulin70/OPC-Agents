# OPC-Agents 目录结构 — IOC 分层映射

> 生成于 v0.3.2 Phase 4，更新于 v0.3.3（轻量分层方案：仅文档，不移动文件）
>
> 决策原因：全量目录重组需改 250+ 导入语句（74 相对导入 + 89 绝对导入 + 87 测试导入），
> 违反 Simplicity First / Surgical Changes 原则。本文档提供导航价值，零代码风险。
>
> v0.3.3 更新：实测 opc_manager/ 顶层 99 个 .py（含子目录 110），tests/ 顶层 87 个 .py（含子目录 90）。
>
> P2-15 更新（2026-07-05）：StrategistBrain + ReflectorBrain God Class 拆分完成，
> 新增 10 个独立服务模块（Facade 模式，向后兼容）。文件数 99→109。

## 分层总览

```
opc_manager/   (109 文件，P2-15 后)
├── I  — Input        (6 文件)   用户输入 → 意图识别 → 校验
├── C  — Control     (32 文件)   业务逻辑、引擎编排、状态管理（含 P2-15 拆出的 10 个 Brain 服务）
├── O  — Output      (21 文件)   内容生成、搜索、进度、检测
├── S  — Skills      (24 文件)   可插拔技能模块 + 技能市场
└── F  — Infra       (26 文件)   数据、配置、安全、监控、协议

tests/          (90 文件，P2-13 后分层)
├── unit/          (49 文件)   纯 mock，无 IO
├── integration/   (29 文件)   跨模块 DB/文件系统
├── e2e/           (8 文件)    真实服务/浏览器
├── tools/         (3 文件)    gate 脚本（非 pytest）
└── conftest.py              autouse fixture 必需保留根目录
```

---

## I — Input Layer（输入层）

用户输入处理、意图识别、输入校验。数据从外部进入系统的入口。

| 文件 | 职责 |
|---|---|
| `cli.py` | CLI 入口，6 个生命周期快捷命令 (spec/plan/build/test/review/ship) |
| `intent_classifier.py` | 意图分类器，将用户输入映射到 TaskType |
| `intent_types.py` | 意图类型定义 |
| `shortcuts_handler.py` | 快捷指令处理 (/help, /clear 等) |
| `validators.py` | 输入校验 (TaskRequest, sanitize) |
| `onboarding.py` | 新用户引导流程 |

---

## C — Control Layer（控制层）

三贤者架构核心：策略脑 → 执行脑 → 反思脑 + 共识引擎 + 任务引擎。

> **P2-15 拆分说明**：StrategistBrain（884→176 行）和 ReflectorBrain（841→222 行）
> 已重构为 Facade，公共 API 完全向后兼容；具体职责拆到 10 个独立服务模块。
> 调用方（agent_loop.py 等）零改动。

| 文件 | 职责 |
|---|---|
| `agent_loop.py` | Agent 执行循环（主入口） |
| `agent_context.py` | Agent 上下文与状态机 |
| `agent_error_handler.py` | Agent 错误处理 |
| `agent_utils.py` | Agent 工具函数 |
| `strategist_brain.py` | **策略脑 Facade**（P2-15 后 176 行）：意图分解、执行计划生成，委托给下方 3 个服务 |
| `strategist_models.py` | [P2-15] 策略脑数据模型（ConstraintType/Constraint/Intent/Step/ExecutionPlan） |
| `intent_understanding_service.py` | [P2-15] 意图理解服务（understand_intent + 9 个相关方法） |
| `planning_service.py` | [P2-15] 任务规划服务（plan + 5 个规划方法） |
| `external_skill_resolver.py` | [P2-15] 外部技能解析（用户偏好 + 技能市场降级查找） |
| `executor_brain.py` | **执行脑**：步骤执行、结果收集 |
| `reflector_brain.py` | **反思脑 Facade**（P2-15 后 222 行）：质量评估、纠偏策略，委托给下方 3 个服务 |
| `reflector_models.py` | [P2-15] 反思脑数据模型（Evaluation/NextAction + 常量） |
| `quality_evaluator.py` | [P2-15] 质量评估服务（evaluate_result + 5 个评估方法 + 权重常量） |
| `next_action_decider.py` | [P2-15] 行动决策服务（decide_next_action + 改进/修正策略 + 占位符检测） |
| `consequence_predictor.py` | [P2-15] 后果预判服务（predict_consequence + LLM/规则/异步版本） |
| `consensus_engine.py` | **共识引擎**：三贤者并行投票决策 |
| `confirmer.py` | 确认器（关键操作前用户确认） |
| `correction_manager.py` | 纠偏管理 |
| `task_engine_v3.py` | 任务引擎 facade（1853→499 行，Phase 3 拆分） |
| `task_engine_v3_search.py` | 任务搜索 mixin |
| `task_engine_v3_executors.py` | 任务执行器 mixin（8 种执行策略） |
| `task_engine_v3_parallel.py` | 并行执行 mixin |
| `task_orchestrator.py` | 任务编排器 |
| `task_lifecycle.py` | 任务生命周期管理 |
| `task_content_generators.py` | 内容生成 mixin（ContentGenerationMixin） |
| `task_types.py` | 任务类型定义 (TaskType, TaskResult) |
| `scenario_engine_v2.py` | 场景引擎 v2 |
| `scenario_definitions.py` | 场景定义（9 种场景配置） |
| `state_manager.py` | 全局状态管理 |
| `session_context.py` | 会话上下文（多轮对话） |

---

## O — Output Layer（输出层）

内容生成、搜索检索、进度反馈、业务类型检测。

| 文件 | 职责 |
|---|---|
| `llm_content.py` | LLM 增强内容生成 facade（1060→419 行，Phase 3 拆分） |
| `llm_content_prompt.py` | LLM 提示构建 mixin |
| `llm_content_generation.py` | LLM API 调用 + 质量门 mixin |
| `llm_service.py` | LLM 服务封装 |
| `llm_cache.py` | LLM 响应缓存（TTL + LRU） |
| `simple_llm_service.py` | 简易 LLM 服务（无 RAG） |
| `business_type_detector_v2.py` | 业务类型检测 facade（1197→362 行，Phase 3 拆分） |
| `business_type_detector_v2_database.py` | 检测关键词/模式数据库 mixin |
| `business_type_detector_v2_scoring.py` | 检测评分 + 否定检测 mixin |
| `business_type_detector_v2_strategies.py` | 检测策略 mixin |
| `business_types.py` | 业务类型枚举定义 |
| `search_processor.py` | 搜索结果处理 |
| `search_cache.py` | 搜索缓存 |
| `result_builder.py` | 结果构建器 |
| `progress_emitter.py` | 进度事件发射器 |
| `progress_tracker.py` | 进度追踪 |
| `undo_manager.py` | 撤销管理 |
| `dashboard_config.py` | 仪表盘配置 |
| `flywheel_tracker.py` | 飞轮追踪 |
| `user_profile.py` | 用户画像 |
| `persona_manager.py` | 人设管理 |

### export/ 子目录（文档导出，Output 层）

| 文件 | 职责 |
|---|---|
| `export/__init__.py` | 导出系统包入口 |
| `export/manager.py` | 导出管理器 |
| `export/models.py` | 导出数据模型 |
| `export/exporters/excel_exporter.py` | Excel 导出器 |
| `export/exporters/pdf_exporter.py` | PDF 导出器 |
| `export/exporters/word_exporter.py` | Word 导出器 |
| `export/exporters/image_exporter.py` | 图片导出器 |

---

## S — Skills Layer（技能层）

可插拔技能模块 + 技能市场 + 技能注册。

### 业务技能（14 个）

| 文件 | 职责 |
|---|---|
| `calendar_skill.py` | 日历管理 |
| `competitor_skill.py` | 竞品分析 |
| `crm_skill.py` | 客户关系管理 |
| `dashboard_skill.py` | 仪表盘 |
| `email_skill.py` | 邮件发送（覆盖率 100%） |
| `finance_skill.py` | 财务管理（覆盖率 100%） |
| `invoice_skill.py` | 发票管理 |
| `knowledge_skill.py` | 知识库 |
| `pricing_skill.py` | 定价策略 |
| `proposal_skill.py` | 方案撰写 |
| `report_skill.py` | 报告生成 |
| `social_skill.py` | 社交媒体 |
| `task_skill.py` | 任务管理 |
| `tax_reminder_skill.py` | 税务提醒 |

### 技能基础设施（10 个）

| 文件 | 职责 |
|---|---|
| `skill_registry.py` | 技能注册表 |
| `skill_builtin.py` | 内置技能 |
| `skill_editor.py` | 技能编辑器 |
| `skill_executors.py` | 技能执行器 |
| `skill_models.py` | 技能数据模型 |
| `skill_reviews.py` | 技能评价 |
| `skill_marketplace.py` | 技能市场 facade（1073→468 行，Phase 3 拆分） |
| `skill_marketplace_api.py` | 技能市场 API |
| `skill_marketplace_constants.py` | 技能市场共享常量 |
| `skill_marketplace_external.py` | 外部技能市场（搜索/安装/MCP） |

---

## F — Infra Layer（基础设施层）

数据持久化、配置、安全、监控、协议、工具。

### 数据与配置

| 文件 | 职责 |
|---|---|
| `config.py` | 配置管理（env + YAML） |
| `constants.py` | 全局常量 |
| `data_manager.py` | 数据管理（SQLite + 加密） |
| `data_backup.py` | 数据备份 |
| `settings.py` | 设置管理 facade（1067→470 行，Phase 3 拆分） |
| `settings_encryption.py` | 设置加密 mixin |
| `settings_persistence.py` | 设置持久化 mixin |
| `settings_operations.py` | 设置操作 mixin |

### 安全与监控

| 文件 | 职责 |
|---|---|
| `secure_storage.py` | 安全存储（Fernet 加密） |
| `audit_log.py` | 审计日志 |
| `monitoring.py` | 系统监控 |
| `performance_monitor.py` | 性能监控（P95/P99） |
| `error_handler.py` | 错误处理 |

### 协议与集成

| 文件 | 职责 |
|---|---|
| `protocols.py` | Protocol 接口（BrainProtocol 等） |
| `mcp_protocol.py` | MCP 协议 |
| `mcp_transport.py` | MCP 传输层 |
| `embedding_service.py` | 嵌入服务 |
| `memory_bridge.py` | 记忆桥接（CarryMem 集成） |
| `knowledge_bridge.py` | 知识桥接 |

### 工具

| 文件 | 职责 |
|---|---|
| `utils.py` | 通用工具（BoundedDict, EventEmitter） |
| `version.py` | 版本管理 |
| `unified_types.py` | 统一类型定义 |
| `tool_system.py` | 工具调用框架 |
| `async_executor.py` | 异步执行器 |
| `parallel_executor.py` | 并行执行器 |

### i18n/ 子目录（国际化，Infra 层）

| 文件 | 职责 |
|---|---|
| `i18n/__init__.py` | i18n 包入口 |
| `i18n/loader.py` | 翻译加载器 |
| `i18n/manager.py` | i18n 管理器 |
| `i18n/locales/zh_CN.json` | 中文翻译（1242 键） |
| `i18n/locales/en_US.json` | 英文翻译 |
| `i18n/locales/ja_JP.json` | 日文翻译 |

---

## tests/ 目录结构（顶层 87 + tools/ 3 = 90 文件）

| 类别 | 命名模式 | 数量 | 说明 |
|---|---|---|---|
| 单元测试 | `test_<module>.py` | ~55 | 按被测模块命名，1:1 对应 |
| 集成测试 | `test_integration_*.py` | ~8 | 跨模块集成验证 |
| E2E 测试 | `test_e2e_*.py`, `test_user_journey.py` | ~6 | 端到端用户流程 |
| 安全测试 | `test_security*.py` | ~4 | 安全扫描 + 注入检测 |
| 内存测试 | `test_memory_optimization.py` | 1 | 内存泄漏检测 |
| 覆盖率测试 | `test_*_coverage.py` | ~3 | 覆盖率补充 |
| 工具脚本 | `tools/` | 3 | 测试辅助工具（gate_e2e_frontend, gate_llm_real_e2e, __init__） |

---

## 依赖方向（IOC 原则）

```
外部输入 → I (Input)
              ↓
         C (Control) ←→ S (Skills)
              ↓           ↓
         O (Output)    F (Infra) ← 被所有层依赖
              ↓
          交付给用户
```

**规则**：
- F (Infra) 可被任何层依赖，不依赖其他层
- C (Control) 依赖 I (Input) + O (Output) + S (Skills) + F (Infra)
- S (Skills) 依赖 F (Infra)，不依赖 C (Control)
- O (Output) 依赖 F (Infra)，被 C (Control) 调用
- I (Input) 依赖 F (Infra)，被 C (Control) 调用

**禁止**：
- F (Infra) 依赖 C (Control) — 会导致循环依赖
- S (Skills) 依赖 C (Control) — 技能不应引用引擎
