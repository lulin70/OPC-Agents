# Changelog

All notable changes to OPC-Agents will be documented in this file.

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
