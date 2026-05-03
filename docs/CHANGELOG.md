# Changelog

All notable changes to OPC-Agents will be documented in this file.

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
