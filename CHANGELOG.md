# Changelog

All notable changes to OPC-Agents will be documented in this file.

## [0.3.0] - 2026-05-20

### Architecture & Feature Sprint

#### P0-5: Frontend Modularization (11 new modules)
- **shared.py**: 1195 → ~200 lines (83% reduction)
  - Extracted `session_utils.py` (shared utility functions)
  - Extracted `export_helpers.py` (~300 lines, export workflow)
  - Extracted `progress_indicator.py` (~245 lines, progress UI)
  - Extracted `toast_notifications.py` (~160 lines, notification system)
  - Extracted `theme_manager.py` (~120 lines, theme configuration)
- **timeline_view.py**: 1345 → ~260 lines (81% reduction)
  - Extracted `timeline_data.py` (~400 lines, data building layer)
  - Extracted `timeline_export.py` (~283 lines, export functionality)
  - Extracted `timeline_filters.py` (~205 lines, filter & grouping)
- **undo_panel.py**: 1228 → ~500 lines (59% reduction)
  - Extracted `undo_display.py` (~195 lines, data model & conversion)
  - Extracted `undo_export.py` (~113 lines, export functionality)
  - Extracted `undo_actions.py` (~220 lines, business actions)
- All original files maintain backward-compatible re-exports via `from .new_module import *`

#### P0-6: Integration Test Suite (26 E2E tests)
- User Onboarding Flow (3 tests)
- Task Execution Workflow (4 tests: simple task, undo, export, 5-task sequence)
- Knowledge Bridge Workflow (2 tests: local folder, search)
- Skill Marketplace Workflow (3 tests: browse, install, rate)
- Data Management Workflow (3 tests: backup/restore, export sanitization, audit log)
- LLM Cache Workflow (3 tests: cache hit, miss, expiry)
- i18n Workflow (3 tests: English, Japanese, fallback)
- Security Workflow (5 tests: MCP localhost, API key redaction, XSS, URL validation, audit sanitization)

#### P1-6: LLM Response Cache Layer
- New `opc_manager/llm_cache.py` — SQLite-backed cache with TTL & hit tracking
- Cache key: SHA256(model + temperature + max_tokens + system_prompt + user_prompt)
- Default TTL: 7 days, configurable via `OPC_LLM_CACHE_TTL` env var
- Skips caching for temperature > 0.7 (high variance responses)
- Integrated into `SimpleLLMService.complete()` and `LLMEnhancedContentGenerator._call_llm_api()`
- Thread-safe via `threading.RLock`
- 12 unit tests

#### P1-7: Skill Marketplace Rating System
- New `opc_manager/skill_reviews.py` — `SkillReviewManager` with SQLite persistence
- Rating schema: 1-5 stars + text review + helpful count + status
- `skill_reviews` table with indexes on skill_id, user_id
- Auto-updates `external_skills.rating` column (aggregated average)
- Frontend: star rating display (★☆) in skill cards, `rating_desc` sort option
- 17 unit tests

#### Test Coverage
- **1913 tests** total (up from 1860 in v0.2.2)
- 26 new E2E integration tests
- 29 new feature tests (12 LLM cache + 17 skill reviews)

#### 7-Dimension Code Review Fixes (Critical + High)
- **[Critical] XSS**: Added `html.escape()` to toast_notifications.py message/icon rendering
- **[Critical] Cache threshold**: Changed LLM cache skip threshold from `> 0.7` to `>= 0.7`
- **[High] Thread safety**: Added `threading.RLock` to `SkillReviewManager`
- **[High] N+1 query**: Added `get_average_ratings()` batch method, pre-compute ratings in marketplace
- **[High] UI blocking**: Removed `time.sleep()` from toast notifications
- **[High] Input validation**: Added skill_id/user_id length checks, HTML escape on review text
- **[High] Error logging**: Changed silent exception swallowing to `logger.warning()`

#### Version Consistency (9 files updated)
- README.md, Dockerfile, start.sh, install.sh → v0.3.0
- i18n.py, mcp_protocol.py → v0.3.0
- requirements.txt → v0.3.0
- pyproject.toml → carrymem upper bound widened to `<0.4.0`
- Test assertions updated to match

## [0.2.2] - 2026-05-20

### Quality Fix Sprint — All Blockers Resolved + Mobile + i18n + Security + CI/CD

#### CI/CD Pipeline Fixes
- **Fixed**: Consolidated duplicate CI workflows (`ci.yml` + `python-ci.yml` → single `python-ci.yml`)
- **Fixed**: Python matrix updated to 3.10/3.11/3.12 (matches `requires-python>=3.10`)
- **Fixed**: Added `pip install -r requirements.txt` step (was missing, caused test failures)
- **Fixed**: Added version consistency verification step
- **Fixed**: Flake8 F824 — removed unused `global _log_cache_instance` in `test_live_log_panel.py`
- **Fixed**: SyntaxWarning — invalid escape sequence in `search_processor.py` regex
- **Fixed**: Black 25.x formatting for `audit_log.py`, `search_processor.py`
- **Fixed**: Bandit B413 — replaced `pyCrypto` with `cryptography` in `wechat_gateway.py`
- **Fixed**: Bandit B314 — replaced `xml.etree.ElementTree` with `defusedxml` in `wechat_gateway.py`
- **Fixed**: Bandit B310 — added `# nosec` for controlled `urllib.request.urlopen` calls
- **Fixed**: Bandit B324 — added `# nosec` for WeChat API-required `hashlib.sha1`
- **Added**: `defusedxml>=0.7.0` to `requirements.txt`
- **Result**: CI/CD Pipeline Run #125 — all 3 Python versions pass (Black + Flake8 + Bandit + pytest)

#### B1: i18n Hardcoded Chinese Cleanup (315+ strings)
- **Fixed**: `input_autocomplete.py` — 45 hardcoded Chinese strings → i18n keys
- **Fixed**: `smart_suggestions.py` — 60+ hardcoded Chinese strings → i18n keys
- **Fixed**: `result_cards.py` — 30+ hardcoded Chinese strings → i18n keys
- **Fixed**: `timeline_view.py` — 75+ hardcoded Chinese strings → i18n keys
- **Fixed**: `confirmation_dialog.py` — 20+ hardcoded Chinese strings → i18n keys
- **Fixed**: `live_log_panel.py` — 30+ hardcoded Chinese strings → i18n keys
- **Added**: 315+ new i18n keys in zh_CN/en_US/ja_JP dictionaries

#### B2: Backup Encryption + Export Sanitization
- **Added**: AES-256 ZIP encryption via pyzipper (fallback to unencrypted with WARNING)
- **Added**: `BackupManifest.encrypted` field
- **Added**: `SENSITIVE_FIELDS` auto-redaction in JSON/CSV export (api_key, password, token, etc.)
- **Added**: `_meta.sanitized: true` marker in exported data

#### B3: MCP Default Localhost
- **Fixed**: Default host changed from `0.0.0.0` to `127.0.0.1`
- **Added**: Security check — non-localhost without MCP_API_KEY refuses to start
- **Added**: WARNING log when binding to non-localhost

#### B4: Onboarding Merge
- **Fixed**: Removed duplicate Chat inline onboarding (steps 0-3)
- **Kept**: Overlay onboarding (WELCOME → LLM_CONFIG → SAMPLE_TASK)

#### I1: Mobile Responsiveness
- **Added**: `.streamlit/config.toml` with theme and server config
- **Fixed**: `initial_sidebar_state` changed from "expanded" to "auto"
- **Added**: Mobile CSS for sidebar, toast notifications, buttons, dashboard, chat, input
- **Fixed**: Column counts adapted for small screens (6→3, 4→2, 3→2, 2→1)

#### I3: Keyboard Shortcuts Cleanup
- **Fixed**: Removed 6 unimplementable shortcuts (Ctrl+N/E/D/S, Ctrl+Z, ?)
- **Kept**: 3 working tips (Enter, Esc, /)
- **Changed**: Title from "Keyboard Shortcuts" to "操作提示"

#### I5: .gitignore
- **Added**: `.env.encrypted` to gitignore

#### I6: CI Security Audit
- **Added**: `pip-audit` step in python-ci.yml

#### I2: Dependency Lock
- **Added**: `requirements.lock` for reproducible builds

#### Other Fixes
- **Fixed**: Flywheel level calculation `int()` → `round()`
- **Fixed**: `memory_count` property cached to avoid DB query per access
- **Fixed**: SiYuanAdapter `_available` validates connection at init
- **Fixed**: `SKILL_CATEGORY_ICONS` keys lowercase to match `SkillCategory.value`
- **Fixed**: `test_marketplace_v2` import path `frontend.pages` → `frontend.page_modules`
- **Fixed**: `test_p1_skills`/`test_p2_skills` SQLite state isolation with tearDownClass
- **Fixed**: `test_ux_polish` i18n key assertions
- **Fixed**: `test_input_autocomplete` category case assertions
- **Updated**: README test count 1126 → 1859
- **Updated**: Version unified to 0.2.2 across all files

## [0.2.1] - 2026-05-18

### User Experience Enhancement
- **8 new OPC skills integrated** from tohnee/opc-skills (MIT License):
  - 💡 Creative Planning (Naval's Specific Knowledge)
  - 🔍 Market Research (Dan Koe + The Mom Test)
  - 🚀 Growth Hacker (Justin Welsh Content OS)
  - 👂 Social Listening (Reddit/X/HN pain point mining)
  - ⚖️ Legal Advisor (contract review + IP protection)
  - 🔬 Proposal Review (inversion thinking)
  - 📋 PRD Generation (structured product requirements)
  - 🎨 Domain & Brand (Paul Graham naming)
- **Total visible scenarios**: 25 (4 core + 21 more), up from 12 in v0.2.0
- **5 previously hidden skills** now exposed as scenario buttons
- **Feature**: Knowledge context injection before task execution
- **Feature**: Sidebar knowledge base status indicator (📚 知识库(type) N篇)
- **Config**: `OPC_KB_ENABLED=true`, `OPC_KB_TYPE=obsidian|local|yuque|feishu|notion|siyuan`
- **Feature**: Flywheel level assessment (🌱新手→🌿熟悉→🌳精通→🏔️专家→🧙大师→👑传奇)
- **Feature**: Memory-driven skill recommendation (`suggest_skills()`)
- **Feature**: Stale memory cleanup (`cleanup_stale_memories()`)
- **Feature**: User data export for portability (`export_user_data()`)

### Tech Debt Cleanup (from v0.2.0 post-release)
- 32 bare except fixes across 17 files with proper logging
- shared.py: ~120 hardcoded CJK strings → _t() i18n (97 new keys ×3 langs)
- Growth role names: hardcoded → i18n keys (11 new keys ×3 langs)
- Settings placeholder: hardcoded → _t('llm_model_placeholder')

### Bug Fixes (7-dimension code review)
- Fixed: `urllib.parse` not imported in knowledge_bridge.py (runtime crash for Yuque/Feishu)
- Fixed: `_mb` variable scope issue in base_router.py (NameError when CarryMem not installed)
- Fixed: Original prompt extraction error in base_router.py (data loss on multi-paragraph input)
- Fixed: Silent exceptions in agent_loop.py now log at debug level
- Fixed: `deviation_analysis` defensive null check in failure recording
- Fixed: Flywheel level calculation uses `round()` instead of `int()` to avoid 4.9→4 truncation
- Fixed: `memory_count` property cached to avoid DB query on every access
- Fixed: SiYuanAdapter `_available` now validates connection at init instead of defaulting to True
- NameError: `task_type` not defined in chat_router.py — fixed variable scope
- Settings save feedback: st.toast() added on all 3 save buttons

### Quality
- Regression tests: 49/49 passed (0 failures, 1 xfailed)
- 7-dimension maturity score: 60/70 (85.7%), up from 55/70 (78.6%)

## [0.2.0] - 2026-05-16 to 2026-05-18

### Final Stabilization (2026-05-18 — Frontend Architecture Reorganization)

#### 🏗️ Architecture Refactor
- **app.py**: 1913→405 lines (-79%), extracted to Router/Renderer architecture
- **13 new files** created:
  - `frontend/routers/` — 6 routers (base, chat, dashboard, deliverables, marketplace, settings)
  - `frontend/renderers/` — 3 renderers (deliverables, audit_log, onboarding)
  - `frontend/components/` — shared utilities (input_autocomplete, confirmation_dialog, undo_panel, etc.)
  - `frontend/page_modules/` — 6 page modules (chat, dashboard, settings, marketplace, growth, deliverables)
- **PageKey enum** + `navigate()` dispatcher for stable navigation

#### 🔧 Critical Bug Fixes (14 bugs fixed)

**P0 — Navigation & Runtime:**
1. **st.radio key fix** — Added `key="main_page_navigation"` to prevent 70% page-jump rate on rerun
2. **NameError: `_t` not defined** (Settings) — Added defensive import inside `_create_settings_page()` function body
3. **NameError: `task_type` not defined** (Chat) — Fixed bare variable reference to `task_status.get("task_type", "")`
4. **Coroutine leak to UI** — Created `_sync_execute_task()` wrapper; cleaned 3 corrupted chat_history.json entries

**P1 — Display & Data:**
5. **Dashboard `ash_` prefix** — Fixed 142+ occurrences (`ash_` → `dash_`) including nested `_t()` calls
6. **Growth page tuple display** — Hardcoded level name/desc to bypass `_t()` returning tuple issue
7. **Chat router imports** — Fixed 4 wrong import sources (autocomplete, confirmation, undo from correct modules)
8. **deliverables_renderer missing `_read_file`** — Added local file reader function
9. **base_router.py `_t` import** — Fixed `from opc_manager.i18n import _t` → `import t as _t`
10. **app.py init_session_state path** — Fixed import source from base_router

**P2 — UX Polish:**
11. **Settings save feedback** — Added `st.toast()` on all 3 save buttons (LLM/SMTP/Profile)
12. **Shortcut buttons i18n** — Added 4 new i18n keys (dismiss/later/floating_help) × 3 locales
13. **Settings error message i18n** — Added `settings_module_not_ready` key × 3 locales
14. **dim_map flywheel keys** — Changed CJK dimension keys to English identifiers

#### 🌐 i18n Hardening
- 58 hardcoded CJK strings → 0 in core user paths
- 101 new translation keys added (total: ~696 keys × 3 languages: zh_CN/en_US/ja_JP)

#### 🧪 Quality Assurance
- **49 regression tests**: All passing ✅ (0 failures, 1 expected failure)
- **Business flow E2E validation**: 5 flows tested
  | Flow | Score | Status |
  |------|-------|--------|
  | Chat complete journey | 6/6 (100%) | ✅ |
  | Settings → save → back | 5/6 (83%) | ✅ |
  | Language switch × 6 pages | Core framework ✅ | ✅ |
  | Skill create → market | 4/5 (80%) | ✅ |
  | Dashboard config | Static ✅ / Interactive manual | ⚠️ |

#### Known Residuals (P2, non-blocking)
- Dashboard interactive features (panel toggle, layout switch) — needs manual browser testing
- Auxiliary module i18n (export UI ~50 strings, audit log event labels) — logged for future sprint
- Mock data in dashboard (Chinese sample names) — demo data only

---

### Initial Release (commit 0b43f32)
- 17 features: Settings Manager, Onboarding, Data Backup, Error Handler,
  WeChat E2E, Dashboard, i18n, Skill Marketplace MVP, Global Search...

### Post-Release Security Patch (commit 849efc4)
- P0: Zip Slip path traversal fix
- P0: Upload filename sanitization
- P0: Encryption key absolute path
- P1: ERROR_MAP dead code fix
- Doc sync: README 470→813 tests, Python 3.9→3.10+

### Iteration 1: Test Coverage + Frontend Split (commit 678d7a9)
- +187 tests (5 new test files: confirmer, undo_manager, audit_log, progress_emitter, data_manager)
- Frontend: app.py 3834→1687 lines (-56%)
- 7 new module files (pages×3 + components/shared + __init__×3)
- AuditLog bugfix (_db_connection + _stop_event)

### Iteration 2: Security + Refactor (commit 9b4bbd3)
- API Key Fernet encryption at rest (+8 tests)
- task_engine_v3.py: 1857→1311 lines (-29%), extracted task_types + content_generators
- skill_registry.py: 1105→376 lines (-66%), extracted models + builtin + executors

### Iteration 3: UX + Performance (commit fd2b68d)
- Dashboard Template System: 3 layouts × 3 densities × 6 panel toggles (+30 tests)
- scenario_engine_v2.py: 1150→275 lines (-76%), extracted definitions
- Performance: user_profile lazy import cache, ZIP streaming checksum (64KB peak), 50MB cap

### Iteration 4: Final Features (commit 641c6ab)
- Apple Shortcuts: 5 CLI actions (+35 tests)
- i18n ja_JP: 58 translation keys (+11 tests)
- Skill Marketplace V2: detail panel, 16-category filter, version pinning (+42 tests)

### Iteration 5: Core Workflow Revolution (2026-05-17)

#### 🎯 本次迭代: 核心用户体验升级
完成10项核心工作流改进，全面提升产品体验从"能用"到"好用"。

**新增组件 (9个):**
- ✅ `frontend/components/result_cards.py` — 结果结构化卡片展示系统 (420行)
- ✅ `frontend/components/smart_suggestions.py` — 智能下一步建议引擎 (340行)
- ✅ `frontend/components/confirmation_dialog.py` — 风险操作确认对话框 (280行)
- ✅ `opc_manager/parallel_executor.py` — LLM并行执行引擎 (430行)
- ✅ `frontend/components/undo_panel.py` — 撤销历史可视化面板 (650行)
- ✅ `opc_manager/unified_types.py` — 统一类型系统 (450行)
- ✅ `frontend/components/input_autocomplete.py` — 输入智能补全 (480行)
- ✅ `frontend/components/live_log_panel.py` — 实时日志监控面板 (580行)
- ✅ `frontend/components/timeline_view.py` — 操作时间线视图 (680行)

**核心改进 (10项):**

**P0 级别 (3项):**
1. **P0-1 真实进度接通** — 前端主进度条从fake time-based估算改为ProgressEmitter真实事件驱动
   - 新增40个测试
   - 支持5阶段时间线可视化+错误状态红色高亮

2. **P0-2 Confirmer确认流程UI** — 高风险操作强制用户确认
   - 新增50个测试
   - 两阶段模式解决Streamlit异步限制
   - 信任度系统：连续确认降低阈值

3. **P0-3 引擎统一重构** — IntentType(22) ↔ TaskType(6) 双系统统一为13种UnifiedTaskCategory
   - 新增126个测试
   - 完整双向映射+i18n支持

**P1 级别 (4项):**
4. **P1-4 LLM调用并行化** — 平均提速61.9%（最高66.5%）
   - 新增47个测试+性能基准验证
   - Semaphore并发控制(≤3)+错误隔离

5. **P1-5 结果结构化卡片** — 替换纯文本为5种任务类型富卡片布局
   - 新增39个测试
   - 蓝紫/绿青/橙黄/粉紫渐变色系

6. **P1-6 智能下一步建议** — 4类启发式规则引擎（跟进/相关/改进/探索）
   - 新增41个测试
   - 一键执行(<50ms响应)

7. **P1-7 撤销面板可视化** — UndoManager完整UI+批量操作+导出
   - 新增52个测试
   - 双轨集成(侧边栏+迷你提示)+倒计时

**P2 级别 (3项):**
8. **P2-8 输入智能补全** — 历史+技能+模板+联系人4源补全
   - 新增69个测试
   - 混合排序算法+跨会话记忆

9. **P2-9 实时日志面板** — 5源聚合日志查看器
   - 新增70个测试
   - 颜色编码+敏感信息脱敏+TXT/JSON/CSV导出

10. **P2-10 操作时间线** — 10事件类型垂直时间轴视图
    - 新增53个测试
    - 多数据源融合+统计摘要+导出

**统计:**
- 新增代码: ~4,280行 (组件+测试)
- 新增测试: 596个 (全部通过 ✅)
- 回归测试: 1678 passed, 0 failed
- 总测试数: 1,822+

**Bug修复:**
- 🔧 修复 app.py:584 async语法错误（await在非async函数中）
- 🔧 创建缺失的 data/.gitkeep 文件
- 🔧 修复 install.sh 版本号 (0.1.8 → 0.2.0)
- 🔧 修复 version.py docstring示例版本 (v0.1.7 → v0.2.0)

**用户体验变化:**
```
之前: 用户输入 → fake进度条 → 纯文本结果 → 结束
现在: 用户输入(智能补全💡) → 真实进度(事件驱动📊) 
     → [高风险确认🔐] → 结构化结果卡片(渐变色🎨) 
     → 智能建议(一键执行⚡) → 撤销历史(可追溯↩️) 
     → 实时日志(可调试📡) → 操作时间线(全局视角🕐)
```

### Summary
- Total: 1822+ tests (from 813, +124%)
- 20+ new source modules
- Frontend fully modularized
- All large modules refactored to <400 lines
- Zero security issues open
- Core workflow revolution: 10 UX improvements with 596 new tests

---

### 重大变更：从"技术demo"升级为"真正可用的产品"

#### Sprint 1: 零配置启动 (P0×3 + P1×1)
- **SettingsManager** — 统一设置中心(5Tab): LLM/SMTP/API密钥/安全/个人信息
- **加密Key自动生成** — secrets.token_hex(32)→.env.local，首次启动零配置
- **SMTP配置UI** — 预设服务商(QQ/163/Gmail/Outlook)+5秒超时测试+错误分类
- **Onboarding新手引导** — 3步引导(欢迎→LLM配置→示例任务)+进度指示器
- 新增文件: settings.py, onboarding.py, test_settings.py(49), test_onboarding.py(44)

#### Sprint 2: 企业微信 + 体验升级 (P0×1 + P1×2 + P2×1)
- **企业微信全链路可用** — 37个E2E测试覆盖Gateway/Bridge/集成/全链路
  - Bug修复: 错误信息泄露→友好提示 / 委托模式实现 / 冗余代码清理
- **ErrorHandler统一错误中间件** — 9种异常分类+5级严重度+上下文感知翻译
- **操作日志前端展示** — 成果物双Tab(文件|日志)+统计栏+4维筛选+时间线
- **Undo撤销前端入口** — 侧边栏面板(最近10条+二次确认)+对话区快捷按钮
- 新增文件: error_handler.py, test_error_handler.py(29), test_wechat_e2e.py(37)

#### Sprint 3: 数据价值可视化 (P1×2 + P2×2)
- **DataBackupManager** — ZIP备份/JSON导出/CSV导出/SHA256校验/安全恢复
- **Dashboard模板化(6面板)** — 收入趋势图📈/客户健康度👥/任务完成率✅/月度财务💰/活动时间线📅/技能统计⏱️
- **批量导出入口优化** — 4格式选择+进度条+4图标按钮替代下拉框
- **SSE实时进度条增强** — 状态标签+进度条+指标卡+事件日志详情
- 新增文件: data_backup.py, test_data_backup.py(16)

#### Sprint 4: 打磨 + 国际化 (P2×5)
- **暗色模式/主题切换** — 5主题(浅色/深色/日落橙/森林绿/海洋蓝)
- **i18n中英文切换** — 轻量国际化系统(zh_CN/en_US) 50+翻译键+预留日语接口
- **Keyboard Shortcuts** — 7个快捷键(Ctrl+Enter/N/E/D/S/?/Esc)
- **技能市场前端MVP** — 浏览发现(搜索+筛选+卡片网格)+我的技能(列表+卸载)+5个新API端点
- **全局搜索** — 跨成果物/审计日志/聊天记录搜索+匹配度评分
- 新增文件: i18n.py, test_i18n.py(26)

### 测试统计
- **1822+ passed (+696 from v0.1.9, +124% within v0.2.0 iterations)**, 21 skipped, 0 failed
- 新增测试文件: test_settings, test_onboarding, test_error_handler, test_data_backup, test_i18n, test_wechat_e2e, test_confirmer, test_undo_manager, test_audit_log, test_progress_emitter, test_data_manager, test_dashboard_config, test_marketplace_v2, test_shortcuts_handler, test_multilingual, test_validators, test_search_processor, test_result_cards, test_smart_suggestions, test_confirmation_dialog, test_parallel_executor, test_undo_panel, test_unified_types, test_input_autocomplete, test_live_log_panel, test_timeline_view
- 安全测试: 19/19通过 (注入/XSS/路径穿越/APIKey/输出脱敏) + API Key Fernet加密测试(8/8)
- 迭代覆盖: Iteration1(+187), Iteration2(+38), Iteration3(+30), Iteration4(+88), Iteration5(+596)

### 文档
- DevSquad 7角色协作PRD+架构设计报告 (2144行)
- Sprint Plan (62任务/4阶段)
- 版本同步: 所有活跃文档更新到v0.2.0

---

## [0.1.9] - 2026-05-14

### P0: 核心体验升级（5项）

#### Confirmer — 置信度确认机制
- 4级风险分级：LOW(>70%直接执行) / MEDIUM(>85%) / HIGH(>95%) / CRITICAL(100%)
- 信任累积：连续确认同类操作降低阈值2%，最低60%
- 确认卡片生成：`get_confirmation_card()` 返回结构化确认信息
- 集成到AgentLoop：`_phase_plan`后插入确认环节，新增`CONFIRMATION_NEEDED`状态
- 11种IntentType→RiskLevel映射，覆盖全部业务技能

#### ExportManager — 多格式成果物导出
- MD作为中间输出保留，支持一键导出PDF/Word/Excel/Image
- ExportManager单例 + 插件式Exporter注册机制
- PDFExporter：weasyprint + Jinja2模板 + 中文CSS + markdown降级
- ExcelExporter：openpyxl + Markdown表格自动解析 + 样式渲染
- WordExporter：python-docx + 标题/列表/表格结构化
- ImageExporter：Pillow + 中文字体 + 社交媒体尺寸适配
- SKILL_EXPORT_CAPABILITIES：8个技能的格式能力注册表
- 前端集成：结果区动态显示导出按钮(PDF/Word/Excel/PNG)

#### ProgressEmitter — 过程透明化
- 14种EventType：PLAN_START→INTENT_DETECTED→STEP_START→STEP_PROGRESS→STEP_COMPLETE→REFLECT_START→COMPLETE/ERROR/CANCELLED
- ProgressEmitter单例：发布/订阅/历史回放
- SSE端点 `/api/events?session_id=xxx`：心跳15s + 断线清理 + 历史回放
- AgentLoop 8个关键节点发射事件，进度百分比0-100%
- 前端EventSource消费，实时更新进度条和状态文本

#### UndoManager — 撤销机制
- 9种可撤销操作类型：email_send/record_income/record_expense/add_event/add_deal/create_proposal/create_invoice/add_customer/add_follow_up/social_publish
- 分级撤销窗口：邮件5min / 记账30min / 日程1h / 报价单1h / 发帖1min
- 每用户最多50条撤销记录，过期自动清理
- 11个skill模块新增undo_*函数（soft_delete标记或实际删除）
- `list_undoable(session_id)` 查看可撤销操作列表

#### AuditLog — 审计日志系统
- 异步批量写入（Queue+BackgroundThread，每10条一批）
- 内存deque(max=1000) + SQLite audit_log表持久化(v6迁移)
- 12字段记录：id/session_id/user_id/timestamp/operation_type/skill_id/input_hash/input_summary/output_summary/duration_ms/status/error_msg
- query() 支持按session/operation_type/time过滤
- get_stats() 统计成功率/平均耗时
- 90天自动清理策略

### P1: 企业微信接入（1项）

#### WeChatGateway — 企业微信消息网关
- SHA1签名验证（token+timestamp+nonce）
- AES-CBC消息解密（PKCS7，EncodingAESKey）
- XML消息解析：text/image/voice/event → WeChatMessage数据类
- handle_callback() 完整流程：验签→解密→解析→路由→响应
- build_confirmation_card() 企微确认卡片文本生成
- WeChatAgentBridge桥接层：企微消息↔AgentLoop.run()
- Confirmer.confirm_callback注入为企微卡片生成函数
- 语音消息占位（Whisper预留接口）、图片消息占位（OCR预留接口）
- 关注/取关事件处理
- 9个单元测试全部通过

### 新增文件清单（19个）

**新模块（6个）：**
- opc_manager/confirmer.py
- opc_manager/undo_manager.py  
- opc_manager/audit_log.py
- opc_manager/progress_emitter.py
- opc_manager/wechat_gateway.py
- opc_manager/wechat_agent.py

**Export子系统（8个）：**
- opc_manager/export/__init__.py
- opc_manager/export/models.py
- opc_manager/export/manager.py
- opc_manager/export/exporters/__init__.py
- opc_manager/export/exporters/pdf_exporter.py
- opc_manager/export/exporters/excel_exporter.py
- opc_manager/export/exporters/word_exporter.py
- opc_manager/export/exporters/image_exporter.py

**API层（2个）：**
- opc_manager/api/__init__.py
- opc_manager/api/events.py

**测试（1个）：**
- tests/test_wechat_gateway.py

### 修改文件清单（18个）

| 文件 | 主要改动 |
|------|---------|
| version.py | 0.1.8→0.1.9 |
| data_manager.py | _db_version 5→6, audit_log表, execute_write(many=True) |
| agent_loop.py | Confirmer初始化+确认检查, ProgressEmitter 8节点事件发射 |
| skill_registry.py | _exportable_formats字段, export_result()方法 |
| async_executor.py | result_exportable_formats透传 |
| frontend/app.py | 导出按钮渲染+下载逻辑 |
| requirements.txt | +weasyprint/openpyxl/python-docx/Pillow/Jinja2/markdown |
| finance_skill.py | +undo_record_income, undo_record_expense |
| crm_skill.py | +undo_add_customer, undo_add_deal, undo_add_follow_up |
| email_skill.py | +undo_send_email |
| calendar_skill.py | +undo_add_event |
| proposal_skill.py | +undo_create_proposal |
| invoice_skill.py | +undo_create_invoice |
| social_skill.py | +undo_publish_content |
| task_skill.py | +undo_complete_task |

### 7维代码走读修复（v0.1.9技术债清零）

#### 🔒 P1-Security（16项修复）
- **Confirmer**: S-01回调注入防护(callable校验), S-02信任分上限(MAX_TRUST_SCORE=10), S-03目标脱敏(12种敏感词过滤)
- **UndoManager**: S-04会话隔离(256字符限制), S-05函数白名单(ALLOWED_FUNC_NAMES×11), S-06None崩溃明确报错
- **AuditLog**: S-07完整64位hash+14种敏感字段脱敏, S-08 None输入防护, S-09优雅退出(_stop_event)+DB连接复用
- **WeChatGateway**: S-10空token拒绝验证, S-11 AES key容错解码, S-12 XML CDATA转义(]]>→]]&gt;)
- **Export**: S-14 Jinja2沙箱环境(SandboxedEnvironment), S-15路径穿越防护(os.path.basename)
- **SSE**: S-18 session_id格式校验(UUID 32-128字符), S-20连接数限制(MAX=100, 超限503)

#### 🏗️ P1-Architecture（4项修复）
- **A-02 单例竞态**: 5个单例类(progress_emitter/export_manager/audit_log/confirmer/undo)初始化逻辑全部移入__new__锁内
- **A-04 延迟导入**: UndoManager._resolve_inverse改为lazy import+异常隔离，单模块失败不影响其他undo
- **A-05 DB复用**: AuditLog在__new__中一次性init_db()，writer线程复用连接
- **A-06 组合模式**: WechatAgentBridge改用wrapper委托，不再monkey-patch Confirmer方法

#### 📝 P2-CodeQuality（8项修复）
- Magic Numbers常量化: MAX_GOAL_DISPLAY_CHARS=100, AUDIT_MAX_MEMORY_LOGS=1000等15个命名常量
- 类型注解补全: confirmer.py Dict[str, ConfirmationRequest], wechat_agent.py完整注解
- frontend/app.py: 18处f-string logger → %s格式化
- 异常细化: bare except → (KeyError, TypeError)/(IOError, OSError)/Exception三级
- 错误消息增强: 包含操作ID和上下文信息
- 字体回退列表: image_exporter.py支持多平台字体路径

#### ⚙️ P2-Infrastructure（3项修复）
- .gitignore: +data/templates/, +data/reports/
- pyproject.toml: 新增export可选依赖组(weasyprint/openpyxl/python-docx/Pillow/Jinja2/markdown)
- Git清理: 移除5个runtime数据文件跟踪(knowledge/*.json, perf_metrics.json)

#### 🎨 P3-Style（9项修复）
- 边界检查增强: confidence[0,1], session_id非空, limit[1,1000], progress_pct[0,100]
- Google-style Docstring: 4个核心模块(confirmer/undo/audit_log/progress_emitter)完整文档
- Import顺序规范化: stdlib→third-party→local
- 常量定义统一: 类级→模块级UPPER_CASE
- app.py拆分TODO标记: 未来可拆为7个独立模块

### 测试结果
- **612 passed, 21 skipped, 0 failed** (从603增至612，+9个WeChatGateway测试)
- 安全测试19/19通过(注入/XSS/路径穿越/APIKey泄露/输出脱敏/安全存储)
- WeChatGateway测试更新: test_verify_no_token_always_true → test_verify_no_token_rejected(符合新安全行为)

---

## [0.1.8] - 2026-05-14

### Added

- 21个内置业务技能（P0: email/finance/task/crm, P1: social/proposal/invoice/report/calendar, P2: competitor/pricing/tax_reminder/dashboard/knowledge）
- 外部技能市场（SkillMarketplace）：搜索、安装、管理第三方技能
- MCP服务发现：搜索和连接MCP协议服务器
- 用户画像（UserProfile）：偏好记录、使用模式分析、技能推荐
- 技能间协作机制：CRM→Email、Finance→Tax、Deal→Income、Deal→Email、Report→Calendar、Proposal→Email
- AES加密：邮件密码、客户敏感字段加密存储
- SQLite统一存储：所有数据迁移到SQLite，消除JSON双轨制
- 数据库迁移机制：版本管理(v0→v5)，安全升级
- 事务支持：execute_transaction() 原子操作
- 用户偏好持久化：user_preferences表
- 交互日志：interaction_log表
- CRM跟进记录：follow_ups表，add_follow_up/get_follow_ups函数
- 发票状态管理：update_invoice_status函数（issued/paid/cancelled）
- 日历月视图：get_month_schedule函数
- 任务完成率统计：execute_goal"完成率"分支
- 任务到期日自动同步日历：create_task时due_date非空自动创建日程
- 报价→发票自动转换：proposal accepted时自动创建invoice
- 共识决策持久化：consensus_decisions表，决策日志写入SQLite
- LLM Provider熔断降级：主provider失败自动切换备选provider，3次连续失败熔断
- MCP路径接入SkillRegistry：MCP客户端可使用21个业务技能

### Security

- 加密自动降级：`OPC_ENCRYPTION_KEY` 未设置时自动生成会话密钥并输出CRITICAL警告（而非崩溃）
- CRM敏感字段加密：phone/email字段调用encrypt_field/decrypt_field
- 外部技能沙箱隔离：UNVERIFIED信任等级技能禁止安装
- 网络白名单：外部技能网络请求仅允许 `registry.opc-agents.dev`、`api.github.com`、`mcphub.io` 及其子域
- SQL参数化：所有数据库操作使用参数化查询，防止SQL注入
- STARTTLS强制：SMTP非SSL连接强制要求STARTTLS，不支持则拒绝发送
- SQLite文件权限0600
- MCP连接强制HTTPS
- MCP空API_KEY安全警告
- 信任等级体系（official/verified/community/unverified）
- 否决权置信度阈值：VETO_MIN_CONFIDENCE=0.5，低置信度反对不再一票否决

### Architecture

- intent_types.py独立模块：`IntentType`枚举、`INTENT_KEYWORDS`、`INTENT_STEP_MAP`、`SKILL_INTENT_MAP` 提取为SSOT
- SkillRegistry单例模式：双重检查锁定，线程安全
- execute_goal委托：14个技能模块统一提供 `execute_goal(goal, _context, **kwargs)` 入口
- BUSINESS_OPERATION TaskType：新增业务操作任务类型，TaskEngineV3路由到SkillRegistry
- ExecutorBrain持有SkillRegistry：三贤者架构与21业务技能打通，skill_registry失败降级到task_engine_adapter
- 协作数据管道：_execute_collaborative 维护 context_data 字典，下游技能获得上游结果
- TaskEngineAdapter传递task_type_hint：映射后的task_type不再被忽略
- data_manager线程安全：_db_init_lock保护初始化，threading.local()每线程独立连接
- performance_monitor持久化：_load_metrics启动时加载，模块级变量导出

### Performance

- get_trend()：精确月份计算，逐月聚合查询
- get_week_schedule()：单查询BETWEEN替代7次逐日查询
- generate_annual_report()：聚合查询 `GROUP BY ym, type` 替代逐月循环
- send_email_async()：异步邮件发送，`run_in_executor` 非阻塞
- AGENT_LOOP_TIMEOUT_SECONDS: 60→120秒，给搜索+LLM调用留足够时间
- LLM总超时上限：LLM_TOTAL_TIMEOUT=90秒
- LLM连接/读取超时分离：timeout=(10, timeout)元组形式

### Changed

- gen_id()改用uuid.uuid4().hex[:16]，信息密度更高
- 日志统一 `%s` 格式（loguru兼容）
- 社媒平台配置外置为 `data/knowledge/social_platforms.json`
- 定价基准外置为 `data/knowledge/pricing_benchmarks.json`
- DATA_DIR统一由 `OPC_DATA_DIR` 环境变量控制，所有模块引用同一常量
- backup_db保留数量从OPC_BACKUP_COUNT环境变量读取（默认7）
- 税务日历数据从invoice_skill移到tax_reminder_skill（职责分离）
- 价值定价法公式改为perceived_value * value_multiplier
- 发票号格式改为OPC{YYYYMMDD}{4位序号}
- datetime.utcnow()→datetime.now(timezone.utc)
- SKILL_FALLBACK_MAP从3条扩展到19条
- 反思脑TIMELY权重从0.1改为0.0（不再偏向快速低质量结果）

### Fixed — 7维代码审查修复（58项）

- social_skill不再写入email_history表（数据混淆）
- competitor_skill不再写入customers表（数据污染）
- 邮件同一收件人1小时频率限制
- 邮件正文50KB大小限制

### Fixed — 业务逻辑端到端审查修复（12项）

- BL-1: CRM添加客户正确解析姓名/电话/邮箱/公司（不再把整句当名字）
- BL-2/5: Email支持"给xxx发邮件"模式，自动从CRM查找邮箱
- BL-3: output_result步骤不再因缺data参数而TypeError
- BL-4: INTENT_KEYWORDS补充"成交/跟进/记一笔/合同/朋友圈"等缺失关键词
- BL-5: 协作链双向打通（Email→CRM查找，不再仅CRM→Email单向）
- BL-7: 报价单SERVICE_TEMPLATES增加参考价格（咨询2000/培训5000/设计8000等）
- BL-8: 日历日程提取时间（支持"14:30"/"下午3点"等格式）
- BL-9: 知识库创建不再生成占位内容，改为引导用户输入
- BL-10: 社交发布未指定平台时给出可用平台列表和示例
- BL-11: Dashboard与Report关键词冲突解决（"经营状况"归Report）
- BL-12: 财务报表支持指定月份（"3月报表"/"2025年6月报表"）
- AgentLoop._enrich_step_parameters自动注入前序步骤data到output_result

### Fixed — 技术债清零修复（66项）

P0修复（12项）：
- finance_skill"记账"区分收入/支出，parse_amount排除"3月/2024年"等非金额数字
- task_skill complete_task剥离噪音关键词再匹配
- report_skill周报/月报/年报正确获取done状态任务
- calendar_events表添加duration_min/description/repeat列（DB v4迁移）
- TaskEngineV3添加BUSINESS_OPERATION路由分支
- reflector_brain中文关键词提取替代空格分词
- consensus_engine否决权添加最低置信度阈值0.5
- agent_loop重试保留成功步骤结果，skip_reflect添加质量检查
- SkillRegistry单例双重检查锁定，data_manager加密字段实际调用
- MCP路径接入SkillRegistry，frontend AgentLoop传入skill_registry
- performance_monitor _load_metrics启动加载+模块级变量导出
- LLM Provider熔断降级机制

P1修复（34项）：
- task→calendar到期日自动同步，list_tasks支持status过滤，完成率统计
- proposal accepted→自动创建invoice，invoice添加proposal_id字段
- CRM跟进记录功能（follow_ups表），report月报添加任务统计/年报添加成交统计
- email模板渲染、body剥离指令性文字
- agent_loop超时120秒、SKILL_FALLBACK_MAP扩展19条、降级标志处理、resume_task传递deadline
- strategist_brain关键词长优先匹配、约束类型自动推断
- executor_brain skill_registry失败降级到adapter
- task_engine_adapter传递task_type_hint
- data_manager线程安全（init锁+thread local连接）
- LLM总超时+连接/读取超时分离
- consensus决策日志持久化到SQLite
- frontend atexit shutdown、save异常日志、file_content安全检查、轮询时间缩短
- MCP空API_KEY警告、async_executor取消改进/重试并发检查/状态文件安全删除
- competitor按名称查找、价值定价公式修正、税务日历职责分离、dashboard统计完整

P2修复（20项）：
- 删除死代码常量、共识日志改SQLite、_extract_goal处理后缀语气词和复杂句式
- UserProfile/Marketplace缓存、from_dict安全getattr、execute_step超时控制
- TIMELY权重中性、协作链扩展7条、register_skill允许版本升级覆盖
- backup_db环境变量配置、gen_id改hex、task_engine_v3日志%s格式
- datetime.utcnow弃用修复、competitor SQL简化、knowledge搜索词空回退
- 发票号4位序号、发票状态更新、social fallback模板改进+发布标记自然语言
- 日历月视图

## [0.1.9-delta] - 2026-05-09

### Added — v0.1.9-delta 真实运行验证（V2-1到V2-7）

#### V2-1: 三贤者LLM驱动升级
- 策略脑(StrategistBrain)：LLM驱动意图理解+LLM驱动执行计划生成
- 反思脑(ReflectorBrain)：LLM驱动结果评估
- AgentLoop：新增`llm_service`参数，传递给策略脑和反思脑
- 前端：AgentLoop初始化时注入LLMEnhancedContentGenerator

#### V2-3: 技能市场API服务化
- 新增 `skill_marketplace_api.py`: FastAPI REST服务

#### V2-4: MCP协议真实对接
- 新增 `mcp_transport.py`: SSE + stdio 传输层

#### V2-5: 插件示例+热加载
- 新增 `plugins/text_summarizer.py`: 文本摘要生成器示例
- 新增 `plugins/data_converter.py`: JSON→Markdown表格转换器示例

#### V2-6: 技能编辑器Streamlit UI
- 前端侧边栏新增"技能编辑器"按钮

#### V2-7: 性能调优
- 新增 `performance_monitor.py`: 性能监控与SLA管理

### Testing
- 新增20个delta集成测试
- 全量测试：470 passed, 21 skipped

## [0.1.9-gamma] - 2026-05-09

### Added — v0.1.9-gamma 整改优化（G1-G9全任务）

- AgentLoop接入主流程（TaskEngineAdapter适配器层）
- 策略脑替代IntentClassifier
- 反思脑质量把关（总超时60秒）
- 共识引擎集成（决策日志持久化）
- 执行进度可视化（质量/快速模式切换）
- 技能市场API（SkillMarketplace：注册/发现/调用）
- MCP协议支持（MCPServer：工具/资源/提示词）
- 插件系统（PluginManager+PluginSandbox沙箱隔离）
- 自定义技能编辑器（SkillEditor：表单式技能配置）

### Testing
- 新增42个gamma集成测试
- 全量测试：450 passed, 21 skipped

## [0.1.9] - 2026-05-09

### Added — PHASE3 端到端闭环

- 长会话上下文传递（session_id参数+SessionContextManager集成）
- 结果验证与自动修正（CorrectionStrategy+ReflectorBrain+最多2次修正）
- 多技能编排（复合意图拆解+子意图编排）
- 任务暂停/恢复（PAUSED状态+30分钟超时自动取消）
- 执行进度可视化（EventEmitter+事件流）

### Testing
- 新增22个PHASE3端到端闭环集成测试
- 408 tests passing, 21 skipped, 0 failures

## [0.1.8] - 2026-05-08

### Added — PHASE2 核心技能开发

- SkillContext数据类（技能间上下文传递）
- 搜索增强技能（WebSearchMCP+SearchResultProcessor）
- 商业分析技能（LLM增强+SWOT模板+规则引擎降级）
- 内容创作技能（智能模板选择+搜索→创作闭环）
- 文件操作技能（4种操作+ToolSystem对接）
- 消息通知技能（CRLF注入防护）

### Changed — 架构/性能/可维护性专项整改
- 综合评分从89.6提升至92.4

### Testing
- 373 tests passing, 21 skipped, 0 failures

## [0.1.7] - 2026-05-07

### Added — 三贤者架构 (PLAN B)

- StrategistBrain（策略脑）、ExecutorBrain（执行脑）、ReflectorBrain（反思脑）
- ConsensusEngine（共识引擎）、AgentLoop（执行循环）
- SkillRegistry（技能注册表）、ToolSystem（工具调用框架）
- 安全控制（命令注入/路径穿越/输入长度/审计日志）

### Testing
- 373 tests passing, 21 skipped, 0 failures

## [0.1.6] - 2026-05-03

### Added
- 首次用户引导、空状态示例、质量反馈、成果物搜索

### Fixed
- AsyncTaskExecutor重复重试、zombie扫描时间基准、PBKDF2盐值硬编码、XML标签注入

### Testing
- 350 tests passing, 21 skipped, 0 failures

## [0.1.5] - 2026-05-03

### Added
- 多轮对话增强、质量门禁、安全测试套件、Ollama后端支持

### Fixed
- enriched_input未传递到LLM、is_follow_up未传递、XSS修复

### Testing
- 350+ tests passing, 21 skipped, 0 failures

## [0.1.0] - 2026-04-23

### Added
- MOKA API支持、知识库扩展、异步执行、交付物磁盘恢复

### Changed
- 移除MockLLMBackend、前端同步→异步、5阶段进度

### Testing
- 174 tests passing, 0 failures
