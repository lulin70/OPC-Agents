# Changelog

All notable changes to OPC-Agents will be documented in this file.

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
