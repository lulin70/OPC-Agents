# Changelog

All notable changes to OPC-Agents will be documented in this file.

## [0.1.8] - 2026-05-14

### Added — v0.1.8 版本统一与目录清理

- 版本号统一为0.1.8（从0.1.9-delta/0.2.0回归）
- skill_marketplace_api.py / mcp_transport.py 版本号改为动态引用（from .version import __version__）
- 清理MagicMock遗留目录
- 清理运行时数据（consensus_logs/dashboard/perf_metrics）
- 更新.gitignore（运行时数据/Mock遗留/Node规则）

## [0.1.9-delta] - 2026-05-09

### Added — v0.1.9-delta 真实运行验证（V2-1到V2-7）

#### V2-1: 三贤者LLM驱动升级
- 策略脑(StrategistBrain)：LLM驱动意图理解+LLM驱动执行计划生成
  - `_understand_intent_with_llm()`: LLM语义理解意图类型+置信度+子意图+约束
  - `_plan_with_llm()`: LLM动态规划多步骤执行计划
  - 关键词匹配作为降级路径（LLM失败时自动降级）
- 反思脑(ReflectorBrain)：LLM驱动结果评估
  - `_evaluate_with_llm()`: LLM评估质量评分+偏差分析+关键发现+改进建议
  - 规则评估作为降级路径
- AgentLoop：新增`llm_service`参数，传递给策略脑和反思脑
- 前端：AgentLoop初始化时注入LLMEnhancedContentGenerator

#### V2-2: 复合意图拆解实测
- 策略脑LLM规划支持复合意图自动拆解为多步骤
- LLM返回的步骤自动映射到可用技能（search/analysis/content_generation等）

#### V2-3: 技能市场API服务化
- 新增 `skill_marketplace_api.py`: FastAPI REST服务
  - POST /api/v1/keys — 创建API Key
  - POST /api/v1/skills — 注册技能
  - PUT /api/v1/skills/{id}/approve — 审核技能
  - GET /api/v1/skills — 发现技能（支持category/keyword过滤）
  - GET /api/v1/skills/{id} — 获取技能详情
  - POST /api/v1/skills/{id}/execute — 调用技能
  - GET /api/v1/stats — 市场统计
  - CORS中间件 + API Key认证 + 权限分级

#### V2-4: MCP协议真实对接
- 新增 `mcp_transport.py`: SSE + stdio 传输层
  - SSE模式：EventSourceResponse + POST /messages
  - stdio模式：标准输入输出JSON-RPC
  - 可选启动：`uvicorn opc_manager.mcp_transport:create_sse_app` 或 `python -m opc_manager.mcp_transport --transport stdio`

#### V2-5: 插件示例+热加载
- 新增 `plugins/text_summarizer.py`: 文本摘要生成器示例
- 新增 `plugins/data_converter.py`: JSON→Markdown表格转换器示例
- 插件热加载测试通过（register→initialize→execute→shutdown）

#### V2-6: 技能编辑器Streamlit UI
- 前端侧边栏新增"技能编辑器"按钮
- 表单式技能创建（名称/描述/分类/输出格式/模板）
- 已创建技能列表展示

#### V2-7: 性能调优
- 新增 `performance_monitor.py`: 性能监控与SLA管理
  - SLA: 单次请求<30秒, 反思循环<60秒
  - LRU缓存: 相同prompt 5分钟内返回缓存（最大100条）
  - 性能指标采集: avg/max/min/p95
  - SLA违规告警

### Testing
- 新增20个delta集成测试（test_delta_integration.py）
- 全量测试：470 passed, 21 skipped

### Changed
- VERSION: 0.1.9-gamma → 0.1.9-delta
- version.py: __version__ = "0.1.9-delta"
- strategist_brain.py: 新增LLM驱动意图理解+规划
- reflector_brain.py: 新增LLM驱动结果评估
- agent_loop.py: 新增llm_service参数+性能监控集成
- frontend/app.py: LLM注入+技能编辑器UI

## [0.1.9-gamma] - 2026-05-09

### Added — v0.1.9-gamma 整改优化（G1-G9全任务）

#### G1: AgentLoop接入主流程（P0）
- 新增 `TaskEngineAdapter`：ExecutorBrain与TaskEngineV3之间的适配器层
  - IntentType→TaskType映射表（7种IntentType完整映射）
  - skill_id→TaskType映射表（7个核心技能映射）
  - sync/async桥接（`execute_skill_async`用`run_in_executor`包装）
  - TaskResult↔Dict双向转换
- 修改 `ExecutorBrain`：新增`task_engine_adapter`参数，优先使用Adapter执行
- 修改 `frontend/app.py`：新增`execute_with_agent_loop()`函数，替代原入口
  - `OPC_USE_AGENT_LOOP`环境变量控制入口选择
  - AgentLoop失败自动降级到TaskEngineV3
- 修改 `AgentLoop`：集成TaskEngineAdapter，新增总超时60秒机制

#### G2: 策略脑替代IntentClassifier（P0）
- TaskEngineAdapter中实现IntentType→TaskType完整映射
- 策略脑通过AgentLoop._phase_plan()在运行时被调用
- 保留IntentClassifier作为降级路径

#### G3: 反思脑质量把关（P0）
- AgentLoop总超时60秒（AGENT_LOOP_TIMEOUT_SECONDS）
- 超时强制返回当前结果
- 前端降级路径：AgentLoop异常→TaskEngineV3直接执行

#### G4: 共识引擎集成（P1）
- 共识引擎已在AgentLoop._consult_consensus()中集成
- 新增决策日志持久化（JSONL格式，data/consensus_logs/）

#### G5: 执行进度可视化（P1）
- 前端侧边栏新增"执行模式"开关（质量模式/快速模式）
- `OPC_SKIP_REFLECT`环境变量控制反思跳过
- 快速模式：跳过反思评估，直接执行返回

#### G6: 技能市场API（P1）
- 新增 `SkillMarketplace`：技能注册/发现/调用
  - API Key认证（SHA256哈希存储）
  - 权限分级（read/write/execute）
  - 技能审核流程（pending→approved/rejected）
  - 技能发现（按分类/关键词搜索）
  - 数据持久化（JSON格式）

#### G7: MCP协议支持（P1）
- 新增 `MCPServer`：Model Context Protocol兼容
  - MCP Server端点（initialize/tools/list/tools/call/resources/prompts）
  - 4个内置工具（execute_task/search_web/analyze_business/generate_content）
  - 3个内置资源（deliverables/knowledge-base/skills）
  - 2个内置提示词（business_analysis/content_creation）
  - JSON-RPC 2.0协议

#### G8: 插件系统（P2）
- 新增 `PluginManager`：插件生命周期管理
  - 插件注册/初始化/执行/停止/卸载
  - 依赖解析（缺失依赖拒绝注册）
- 新增 `PluginSandbox`：沙箱隔离
  - 安全红线：禁止未授权的文件系统/网络/环境变量/子进程访问
  - 受限import（仅允许json/math/re/datetime等安全模块）
  - 访问日志记录
  - 执行超时限制（30秒）

#### G9: 自定义技能编辑器（P2）
- 新增 `SkillEditor`：表单式技能配置
  - 技能创建/编辑/删除
  - 参数定义（类型/必填/默认值/枚举）
  - 模板预览（{{变量}}替换）
  - 技能测试（参数校验+预览）
  - 发布到技能市场
  - 数据持久化（JSON格式）

### Testing
- 新增42个gamma集成测试（test_gamma_integration.py）
- 全量测试：450 passed, 21 skipped

### Changed
- VERSION: 0.1.9-beta → 0.1.9-gamma
- version.py: __version__ = "0.1.9-gamma"

## [0.1.9-beta] - 2026-05-09

### Changed — Phase 3.5 公开测试版

基于v0.1.9端到端闭环版本，进行文档一致性审查、目录结构清理和版本号统一。

#### 文档一致性更新

- README.md/README-EN.md/README-JP.md: 补充三贤者架构模块到项目结构，更新关键特性（自动修正/多技能编排/任务暂停/进度可视化/长会话上下文），测试数量350+→408，补充v0.1.7-v0.1.9版本历史
- QUICK_START_BETA.md/EN/JP: 版本号v0.1.6→v0.1.9，更新日期，补充v0.1.7-v0.1.9更新日志
- .env.example: 版本号v0.1.6→v0.1.9
- install.sh: 生成的.env模板版本号v0.1.6→v0.1.9
- CONTRIBUTING.md: 测试命令补充PYTHONPATH=.和-v参数
- ROADMAP_AGENT_EVOLUTION.md: 当前状态从v0.1.6更新为v0.1.9，v0.1.9-beta状态从"规划中"→"进行中"

#### 版本号更新

- VERSION: 0.1.9 → 0.1.9-beta
- version.py: __version__ = "0.1.9-beta", __version_info__ = (0, 1, 9, "beta")

#### 验证结果

- 全量测试: 408 passed, 21 skipped ✅
- 安全扫描(bandit): No issues identified ✅
- 语法检查(py_compile): 9核心模块全部通过 ✅

## [0.1.9] - 2026-05-07

### Added — PHASE3 端到端闭环

实现从用户目标到任务完成的完整闭环，让Agent真正"能干活"。

#### REQ-3.2: 长会话上下文传递

- `AgentLoop.run` 新增 `session_id` 参数，支持多轮对话上下文保持
- `AgentContext` 新增 `session_id` 字段
- 集成 `SessionContextManager`，任务完成后自动写入对话历史
- 策略脑理解意图时注入对话历史，支持追问场景
- 自动生成 uuid4 格式 session_id

#### REQ-3.3: 结果验证与自动修正

- 新增 `CorrectionStrategy` 枚举：RETRY/SEARCH_AND_RETRY/SWITCH_SKILL/DEGRADE
- `ReflectorBrain` 新增 `suggest_correction_strategy()` 方法
- `ReflectorBrain` 新增 `_check_placeholders()` 占位符检测
- `AgentLoop._phase_reflect` 集成自动修正循环
- `AgentLoop` 新增 `_apply_correction()` 方法实现4种修正策略
- 质量评分<0.6自动触发修正，最多修正2次
- 修正后仍不达标标记需人工复核

#### REQ-3.4: 多技能编排

- `Intent` 新增 `sub_intents` 字段，支持复合意图拆解
- `StrategistBrain` 新增 `_decompose_intent()` 复合意图分解方法
- `StrategistBrain` 新增 `_detect_single_intent_type()` 单意图检测
- `_generate_steps` 重构为支持子意图编排的 `_generate_skill_steps`
- 复合意图自动拆解为多步骤执行计划（如"分析竞品并写方案"→搜索→分析→创作）

#### REQ-3.1: 任务暂停/恢复

- `AgentState` 新增 `PAUSED` 状态
- `AgentContext` 新增 `paused_at` 字段记录暂停时间
- `AgentLoop` 新增 `pause_task()` 方法
- `AgentLoop` 新增 `resume_task()` 方法，从暂停点继续执行
- 暂停超时30分钟自动取消（`PAUSE_TIMEOUT_SECONDS` 常量）

#### REQ-3.5: 执行进度可视化

- 新增 `Event` 数据类（event_type/step_id/step_name/status/timestamp/duration_ms）
- 新增 `EventEmitter` 类，基于内存队列的事件发布/订阅
- `AgentLoop` 集成 `EventEmitter`，步骤开始/完成/失败自动发事件
- 任务完成发送 `task_completed` 事件
- 支持 `subscribe()` 获取 AsyncIterator 事件流

### Changed — PHASE2启动前代码走读整改

PHASE2（核心技能开发）启动前的全面7维度代码走读，修复6个遗留问题，综合评分从92.4提升至93.1。

#### 代码质量 (92→94)

- 移除agent_loop.py中未使用的ExecutionStatus导入
- 移除tool_system.py中未使用的OrderedDict导入
- 移除skill_registry.py中未使用的延迟import IntentType

#### 架构 (93→94)

- `_execute_web_search`/`_execute_send_email`改为async，与call_tool异步框架一致

#### 性能 (92→93)

- AuditLogger添加优雅关闭机制：`shutdown_event` + drain队列 + 5秒超时

#### 可维护性 (93→94)

- BoundedDict添加`__repr__`用于调试输出

### Testing

- 新增22个PHASE3端到端闭环集成测试
- 408 tests passing, 21 skipped, 0 failures

## [0.1.8] - 2026-05-07

### Added — PHASE2 核心技能开发

完成6个核心技能从mock实现到真实能力的升级，实现搜索→分析/创作闭环和工具系统对接。

#### SKILL-006: LLM集成基础设施

- 新增 `SkillContext` 数据类，支持技能间上下文传递（用户输入、历史步骤结果、会话信息）
- `SkillRegistry` 支持依赖注入 `llm_service`/`search_processor`/`tool_system`
- `execute_skill` 方法自动传递 `_context` 参数给技能执行函数
- 所有内置技能执行函数统一添加 `_context` 可选参数

#### SKILL-003: 搜索增强技能

- 搜索技能从mock实现升级为真实搜索：集成 `WebSearchMCP`（DuckDuckGo）
- 集成 `SearchResultProcessor` 实现搜索结果重排序和知识库兜底
- 查询预处理：自动清理 `<>&"'` 等特殊字符，防止注入
- 三级搜索架构：WebSearchMCP → SearchResultProcessor → 空结果降级

#### SKILL-001: 商业分析技能

- 分析技能从mock实现升级为LLM增强分析
- 自动搜索增强：无数据时自动调用搜索技能获取背景信息
- 集成 `LLMEnhancedContentGenerator` 实现RAG混合模式分析
- SWOT分析模板 + 结果结构化解析（摘要/关键发现/SWOT/行动清单）
- 规则引擎降级：LLM不可用时自动切换到规则引擎

#### SKILL-002: 内容创作技能

- 内容创作从mock实现升级为LLM增强创作
- 智能模板选择：根据目标关键词自动选择方案/报告/通用模板
- 搜索→创作闭环：自动搜索相关资料后生成内容
- 返回质量评分和降级标记

#### SKILL-004: 文件操作技能

- 文件操作从mock实现升级为ToolSystem对接
- 支持4种操作：read_file/write_file/list_directory/search_files
- 操作名到工具ID的字典映射，易于扩展

#### SKILL-005: 消息通知技能

- 通知技能从mock实现升级为ToolSystem邮件对接
- CRLF注入防护：清理收件人中的 `\r\n` 字符

### Fixed — 代码走读修复

- 修复 `execute_skill` 内部递归调用时参数名错误（`_context` → `context`）
- 修复 `asyncio.get_event_loop()` 废弃API调用，改用 `asyncio.get_running_loop()`
- 优化 `_execute_operation` if-elif链为字典映射，提升可维护性

### Changed — 架构/性能/可维护性专项整改

针对v0.1.7七维度代码走读中架构(88)、性能(85)、可维护性(87)三项低于90的维度进行专项整改，综合评分从89.6提升至92.4。

#### 架构 (88→93)

- **REQ-ARCH-005**: AgentLoop集成ConsensusEngine — 反思阶段调用`_consult_consensus()`，质量评分<0.7时触发共识协商，VETOED→ABANDON, ESCALATED→REVIEW
- **REQ-ARCH-006**: skill_registry异步化 — `execute_skill`改为async，自动适配协程和同步函数
- BoundedDict统一 — 提取到`utils.py`共享实现，executor_brain.py/agent_loop.py统一引用
- 重试逻辑统一 — 移除executor_brain.py重复重试，由AgentLoop._execute_step_with_retry统一处理

#### 性能 (85→92)

- AuditLogger异步写入 — 实现异步队列写入(`_write_queue` + `_writer_task`)，队列满时降级同步写入
- 文件操作异步化 — `_execute_file_read/write/list`改为async，通过`run_in_executor`执行同步IO
- call_tool异步化 — `call_tool`改为async，自动检测协程函数并await，同步函数走executor
- 超时/轮次可配置 — `max_reflect_rounds`/`max_retry_per_step`作为AgentLoop构造参数
- 命令超时常量化 — `COMMAND_TIMEOUT_SECONDS=30`提取为模块级常量

#### 可维护性 (87→93)

- 魔法数字→命名常量 — 5个模块共26个命名常量（权重/阈值/超时/退避参数）
- 清理空from_dict — skill_registry.py的from_dict实现技能校验逻辑
- import规范 — fnmatch移至tool_system.py顶部
- AuditLogger日志路径常量化 — `AUDIT_LOG_FILE`

### Added

- `opc_manager/utils.py` — 公共工具模块，BoundedDict共享实现
- `opc_manager/__init__.py` — 导出BoundedDict

### Testing

- 373 tests passing, 21 skipped, 0 failures
- test_execute_skill适配async/await

## [0.1.7] - 2026-05-07

### Added — 三贤者架构 (PLAN B)

- **StrategistBrain (策略脑)** — 意图理解+任务规划，支持6种意图类型(ANALYSIS/CREATION/OPERATION/SEARCH/NOTIFICATION/COMBINED)和5种约束类型
- **ExecutorBrain (执行脑)** — 技能执行+工具调用，优先使用SkillRegistry，mock作为备选
- **ReflectorBrain (反思脑)** — 结果评估+策略调整，5级评估(EXCELLENT/GOOD/ACCEPTABLE/POOR/FAILURE)+5种后续行动(CONTINUE/RETRY/ADJUST_STRATEGY/ABANDON/REVIEW)
- **ConsensusEngine (共识引擎)** — 三贤者意见协调，支持一致同意/多数同意/折中/否决/升级5种决策类型
- **AgentLoop (执行循环)** — Plan→Act→Observe→Reflect四阶段闭环，反思驱动的重试与策略调整
- **SkillRegistry (技能注册表)** — 7个内置技能+9个场景迁移技能，关键词/分类索引
- **ToolSystem (工具调用框架)** — 6个内置工具(文件读写/列表/搜索/邮件/命令)，权限分级
- **ScenarioToSkillMigrator (场景迁移器)** — 9个现有场景无缝迁移为技能格式
- **AuditLogger (审计日志)** — 安全事件审计记录和查询，JSONL格式持久化
- **BoundedDict (有界字典)** — 自动清理超限历史记录，防止内存泄漏

### Added — 安全控制

- **REQ-SEC-001**: 命令注入防护 — `shell=False` + `shlex.split()` + 命令白名单(17个安全命令)
- **REQ-SEC-002**: 路径穿越防护 — `_validate_path()` 拒绝`..`路径 + `_ALLOWED_BASE_DIRS` 白名单目录
- **REQ-SEC-003**: 输入长度限制 — `INPUT_LENGTH_LIMITS` 4类输入上限校验
- **REQ-SEC-004**: 审计日志 — `AuditLogger.log/query` 覆盖命令执行/文件访问8个关键点

### Added — 架构改进

- **REQ-ARCH-001**: 执行脑集成SkillRegistry — 优先使用注册技能，mock仅作备选
- **REQ-ARCH-002**: 任务隔离 — `AgentContext`每任务独立状态，消除并发状态污染
- **REQ-ARCH-003**: 反思-重试闭环 — `MAX_REFLECT_ROUNDS=3`，RETRY/ADJUST_STRATEGY触发重新执行
- **REQ-ARCH-004**: 步骤级重试 — `step_retry_counts` + `MAX_RETRY_PER_STEP=3` + 指数退避 + 失败不终止(进入反思)

### Added — 质量改进

- **REQ-QUAL-002**: import规范 — 核心模块无方法内import
- **REQ-QUAL-003**: 数据结构校验 — `isinstance`类型检查+防御性处理
- **REQ-QUAL-004**: 资源生命周期 — `BoundedDict`自动清理 + `MAX_TASK_HISTORY=100` + `MAX_CONTEXT_HISTORY=100`
- **REQ-QUAL-005**: 数据不可变 — `copy.deepcopy(steps)` 防止修改输入参数
- **REQ-SIDE-001**: 模块初始化安全 — `scenario_migrator`移除自动执行，显式调用+状态标记

### Added — 文档

- `docs/internal/SECURITY_DESIGN.md` — 安全设计文档(威胁建模+安全控制+编码规范)
- `docs/internal/CODE_REVIEW_7DIM_v0.1.7.md` — 七维度代码走读报告(综合评分89.6/100)
- `docs/internal/AGENT_BRAIN_DESIGN_CONSENSUS.md` v2.0 — 架构设计(新增安全架构+任务隔离+资源管理)
- `docs/internal/TEST_PLAN_PHASE1.md` v2.0 — 测试计划(新增45个安全/架构/质量测试用例)
- `docs/product-manager/PRD_V3.md` — 新增PLAN B三贤者架构需求(15个需求+验收标准)
- `docs/product-manager/USER_STORIES.md` — 新增11个安全/架构/质量用户故事

### Changed

- `version.py`: 0.1.6 → 0.1.7
- `opc_manager/__init__.py`: 导出三贤者架构全部公开API
- `tool_system.py`: 命令执行改用`asyncio.create_subprocess_exec`，文件操作添加审计日志和长度校验
- `executor_brain.py`: `task_statuses`改用`BoundedDict`，`steps`改用`copy.deepcopy`
- `agent_loop.py`: `import uuid`移至顶部，步骤失败break而非raise
- `reflector_brain.py`: `_calculate_quality_score`添加`isinstance`类型校验

### Testing

- 373 tests passing, 21 skipped, 0 failures
- 77 security+architecture+validator专项测试全通过
- Test execution time: ~11s

## [0.1.6] - 2026-05-03

### Added
- **First-time user onboarding** — 3-step guided tour (input → wait → download), skippable, persists across sessions
- **Empty state example queries** — 3 clickable example questions when no conversation history exists
- **Quality feedback buttons** — 👍/👎 after each deliverable, feedback saved to `data/feedback/`
- **Deliverable search** — Search deliverables by keyword (prompt/filename/type) in the 📁 tab
- **Deliverable count display** — Shows total and filtered count in deliverables page

### Changed
- `version.py` is SSOT: `__version__ = "0.1.6"`, `__version_info__ = (0, 1, 6)`
- `requirements.txt` version comment updated to 0.1.6
- `VERSION` file updated to 0.1.6
- `docs/internal/` archived 5 obsolete decision records to `docs/internal/archive/`

### Fixed
- **P0 Logic**: `AsyncTaskExecutor._schedule_retry()` duplicate retry — Added RETRYING state check to prevent concurrent retry scheduling from `get_status()` timeout and worker exception
- **P0 Logic**: `AsyncTaskExecutor` zombie scan used `created_at` for RUNNING timeout — Now correctly uses `started_at` for RUNNING tasks in both `get_status()` and `_scan_zombies()`
- **P0 Security**: `secure_storage.py` hardcoded PBKDF2 salt — Salt now derived from machine fingerprint (`SHA-256(fingerprint)`) making it installation-specific
- **P0 Security**: `llm_content.py` prompt injection via XML tag escape — Fixed HTML entity escape order (`&` before `<`/`>`), added regex-based XML tag stripping for search context
- **P1 Doc**: `MANIFEST.in` referenced non-existent `config/` directory — Removed, added `*.yaml` to `opc_manager` include
- **P1 Doc**: `README-EN.md` and `README-JP.md` missing `protocols.py` and `secure_storage.py` in project structure — Added
- **P1 Doc**: `CONTRIBUTING.md` CHANGELOG path corrected to `docs/CHANGELOG.md`

### Security
- Feedback file names sanitized with `re.sub(r'[^\w-]', '', task_id)` to prevent path traversal

### Testing
- 350 tests passing, 21 skipped, 0 failures
- Test execution time: ~10s

## [0.1.5] - 2026-05-03

### Added
- **Multi-turn conversation enhancement (Sprint2 P0)** — Users can now follow up with "补充XX" or "修改XX" and the system will continue based on previous results instead of starting from scratch
- `IntentClassifier.is_follow_up()` — Detects follow-up requests vs new tasks with 40+ patterns in 3 languages (zh/en/jp)
- `IntentClassifier.NEW_TASK_PATTERNS` — Negative patterns to prevent new tasks from being misclassified as follow-ups
- Follow-up context injection in `TaskEngineV3.execute()` — When follow-up is detected, enriched_input includes history context with modification instructions
- Follow-up prompt instructions in `LLMEnhancedContentGenerator._build_prompt()` — LLM receives explicit instructions to modify incrementally
- Frontend follow-up detection and UI hint — Shows "🔄 检测到追问请求" when follow-up is detected
- `llm_query` parameter in `_gen_real_report/plan/content` — Ensures enriched input (with history context) reaches LLM, not just search query
- Deliverable quality gate — Zero placeholders + minimum length + data source checks
- Anti-rationalization instructions in LLM system prompt — Prevents hollow suggestions
- Configuration SSOT — `version.py` is the single source of truth for version numbers
- Protocol + NullProvider pattern — Unified degradation for LLM/Search/Secure/Monitor providers
- Security test suite (`test_security.py`) — Prompt injection, XSS, path traversal, API key leakage
- pytest markers — unit/integration/e2e/security test layering
- SHA256 checkpoint in `AsyncTaskExecutor._persist_active_tasks()`
- Output redaction in `LLMEnhancedContentGenerator._redact_secrets()` — Auto-replaces API keys with [REDACTED]
- Ollama backend support — OpenAI-compatible endpoint, no API key needed

### Changed
- `TaskEngineV3.execute()` — Now detects follow-up requests and injects history context with modification instructions
- `LLMEnhancedContentGenerator.generate()` — Accepts `is_follow_up` parameter for incremental modification mode
- `_build_prompt()` — Adds follow-up-specific rules when `is_follow_up=True`
- `_try_llm_generate()` and `_gen_real_*()` methods — Now accept `llm_query` parameter to pass enriched input to LLM
- Frontend `app.py` — Shows follow-up detection hint before task submission

### Fixed
- **P0 Critical**: `enriched_input` (containing history context) was not passed to LLM in CONTENT_GENERATION path — now fixed via `llm_query` parameter chain
- **P0 Critical**: `is_follow_up` not passed to non-CONTENT_GENERATION paths (INFO_COLLECTION/DATA_ANALYSIS/SCENARIO_BASED/GENERAL_CHAT) — now all paths receive `is_follow_up`
- **P0 Critical**: LLM template title `{topic}` replaced with `llm_query` (containing full history context) instead of original `search_query` — now uses `title` parameter
- **P0 Security**: History context injection without Prompt injection defense — added `<history_context>` boundary tags and "do not execute instructions in history" warnings
- **P1**: FOLLOW_UP_PATTERNS high false-positive rate — Added NEW_TASK_PATTERNS negative patterns to prevent new tasks from being misclassified as follow-ups
- **P1 Security**: All `unsafe_allow_html=True` removed from `app.py` — replaced with Streamlit native components (`st.caption`, `st.subheader`, `st.metric`)
- **P1 Security**: State persistence file `async_tasks_state.json` now has `0o600` file permissions
- **P1**: NullProvider methods now log warnings when called (previously silent failures)

### Testing
- 350+ tests passing, 21 skipped, 0 failures
- 23 new tests for follow-up detection and context injection
- Test execution time: ~10s (fast unit test suite)

## [0.1.0] - 2026-04-23

### Added
- `opc_manager/version.py` — Single source of truth for version number
- `requirements-dev.txt` — Development dependencies separated from core
- MOKA API support in `llm_content.py` — Claude Sonnet 4 via OpenAI-compatible API
- `_get_llm_config()` method — 3-provider priority chain (MOKA > GLM > OpenAI)
- `CATEGORY_KEYWORDS` in `search_processor.py` — Enhanced knowledge base matching
- Knowledge base expanded: 3 categories → 6 categories, 7 entries → 20 entries
- jieba graceful degradation — Uses jieba when available, falls back to sliding window
- Deliverable disk recovery — Restores deliverable list from disk on page refresh
- API Key configuration warning in frontend settings page

### Changed
- VERSION: 0.0.1 → 0.1.0
- Frontend version display reads from `version.py` (SSOT)
- `LLMProvider` enum: Removed MOCK, added MOKA/GLM
- `LLMConfig` default: MOCK → MOKA, timeout 10s → 60s
- `web_app/config.py`: LLM_PROVIDER default "mock" → "moka"
- `web_app/config.py`: SECRET_KEY from hardcoded → environment variable
- Frontend settings: Removed "mock" option, default to "moka (recommended)"
- `requirements.txt`: Added streamlit, duckduckgo-search, jieba; removed sqlite3
- `.env.example`: Updated with MOKA_API_KEY configuration guide
- Frontend chat: Synchronous → Async submit→poll→display flow
- Frontend progress: Simple spinner → 5-stage progress with time estimates
- Frontend homepage: 9 scenario buttons → 4 core + expandable "more"

### Removed
- `MockLLMBackend` class and `LLMProvider.MOCK` enum value
- `archive/` directory (v1/v2 legacy code)
- `opc_manager/_deprecated_openclaw_protocol/` directory
- Duplicate `README_EN.md` (kept `README-EN.md`)
- Simulated search results in `web_search.py` (now returns empty list + KB fallback)
- Hardcoded SECRET_KEY in `web_app/config.py`
- Various phase1/phase2 process documents from `docs/`
- Duplicate `docs/architecture/` and `docs/product_manager/` directories

### Fixed
- `gate_llm_real_e2e.py`: `result.id` → `result.query_id` attribute error
- `gate_llm_real_e2e.py`: Default timeout 30s → 60s for complex queries
- `gate_llm_real_e2e.py`: API Key display now masked in reports

### Testing
- 174 tests passing, 0 failures
- G-LLM-REAL-01 gate passed: 50 queries, 96% quality rate, 58% LLM RAG mode
- G-E2E-FRONTEND-01 gate passed: 18 tests covering async flow, API adapter, KB, performance
