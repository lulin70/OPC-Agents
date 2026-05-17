# OPC-Agents v0.3.0 Roadmap

**Created**: 2026-05-16
**Based on**: v0.2.0 post-release evaluation (813 tests, 17 features)
**Status**: Planning

---

## 📊 Current State (v0.2.0)

| Metric | Value |
|--------|-------|
| Version | 0.2.0 (released 2026-05-16) |
| Tests | 813 passed, 21 skipped, 0 failed |
| Source files | 74 .py in opc_manager/, 29 test files |
| Total LOC | ~12,000+ lines |
| Security | 3 P0 fixed in post-release patch |
| Maturity | Product-ready Beta |

## ✅ v0.2.0 Completed (17 features)

- SettingsManager (5-tab unified settings)
- OnboardingManager (3-step first-run guide)
- DataBackupManager (ZIP/JSON/CSV export, SHA256)
- ErrorHandler (9 exception types → Chinese messages)
- WeChat E2E testing (37 new tests)
- Dashboard (6 modular panels)
- i18n Manager (zh_CN/en_US, JP extension point)
- Skill Marketplace MVP (browse + install)
- Global Search (cross-module)
- +8 additional features

---

## 🎯 v0.3.0 Vision: "Production Hardening + Experience Polish"

**Theme**: From "usable" to "delightful" — focus on stability, performance, and user delight

### Priority Framework

| Priority | Criteria | Budget |
|----------|----------|--------|
| **P0 - Must Have** | Affects data safety / security / core usability | 40% |
| **P1 - Should Have** | Significantly improves UX or reliability | 35% |
| **P2 - Nice to Have** | Delight features, polish, edge cases | 25% |

---

## 📋 v0.3.0 Feature Backlog

### P0 — Must Have (Production Readiness)

#### P0-1: Test Coverage Expansion
**Problem**: 4 core modules lack independent unit tests; ~25 modules have no dedicated test file
**Scope**:
- `test_confirmer.py` — Confirmer class (confirmation workflow)
- `test_undo_manager.py` — UndoManager (undo/redo stack)
- `test_audit_log.py` — AuditLog (event logging/trail)
- `test_progress_emitter.py` — ProgressEmitter (SSE progress)
- `test_data_manager.py` — DataManager (core data layer)
**Target**: +80 new tests, coverage gap <5%
**Effort**: Sprint 1

#### P0-2: Frontend Code Split
**Problem**: `frontend/app.py` is ~3832 lines with 20+ functions — unmaintainable
**Scope**:
- Extract `_render_settings_page()` → `frontend/pages/settings_page.py`
- Extract `_render_dashboard_page()` → `frontend/pages/dashboard_page.py`
- Extract `_render_skill_marketplace_page()` → `frontend/pages/marketplace_page.py`
- Extract helper functions → `frontend/components/shared.py`
- Keep `app.py` as router/navigation only (<300 lines)
**Target**: app.py <400 lines, each page module <500 lines
**Effort**: Sprint 1-2

#### P0-3: API Key Encryption at Rest
**Problem**: API keys stored in plaintext in settings.json
**Scope**:
- Encrypt API keys before writing to settings.json
- Decrypt on read using existing encryption key (from .env.local)
- Migration path for existing plaintext keys
- Add `settings.json` to backup skip list (already done partially)
**Target**: No plaintext secrets in any persistent storage
**Effort**: Sprint 1

#### P0-4: Large Module Refactoring
**Problem**: 3 modules exceed maintainability threshold (>500 lines)
| Module | Lines | Risk | Action |
|--------|-------|------|--------|
| task_engine_v3.py | ~727 | High | Split into EngineCore + StrategyLayer |
| skill_registry.py | ~449 | Medium | Extract loading logic to SkillLoader |
| scenario_engine_v2.py | ~400 | Medium | Separate definition from execution |
**Target**: All modules <400 lines
**Effort**: Sprint 2

### P1 — Should Have (UX & Reliability)

#### P1-1: Dashboard Template System
**User Request**: "收入趋势图、客户健康度、任务完成率可以做模板，让用户可选"
**Scope**:
- Define panel templates (compact/detailed/minimal)
- User-selectable layout presets (1-col/2-col/3-col grid)
- Panel enable/disable toggles per user preference
- Save dashboard config to profile
**Target**: 3 layouts × 3 density levels = 9 combinations
**Effort**: Sprint 2

#### P1-2: Apple Shortcuts Integration
**User Request**: "shortcuts可做"
**Scope**:
- Register OPC-Agents as Shortcuts action target
- Expose key operations: quick-task, query-status, create-deliverable
- Parameterized shortcuts (pass task text as input)
- Return result to Shortcuts app
**Target**: 5-8 pre-configured shortcuts
**Effort**: Sprint 2

#### P1-3: Skill Marketplace Enhancement
**Current State**: MVP browse-grid + My Skills tab only
**Missing Features**:
- Skill detail page (description, version, author, screenshots)
- Search/filter by category
- Install version pinning
- Auto-update check notification
- Rating/review system (basic)
**Target**: Full marketplace experience
**Effort**: Sprint 2-3

#### P1-4: Performance Optimization
**Identified Issues**:
- user_profile.py: 9 scattered lazy imports → cache imports
- ZIP full read into memory → streaming for large backups
- Frontend re-render optimization (st.cache_data for heavy panels)
- LLM response caching (identical prompt deduplication)
**Target**: Page load <2s, backup export memory O(1) scaling
**Effort**: Sprint 3

#### P1-5: i18n Japanese Support
**User Note**: "将来再考虑日语" (Japanese later)
**Scope**:
- Complete ja_JP locale file (50+ keys)
- Date/number formatting for Japanese locale
- Font fallback for CJK characters
- RTL not needed (Japanese is LTR)
**Target**: Full zh_CN/en_US/ja_JP tri-lingual support
**Effort**: Sprint 3

### P2 — Nice to Have (Delight)

#### P2-1: Plugin System Enhancement
- Hot-reload plugin without restart
- Plugin dependency management
- Plugin sandboxing (resource limits)
- Plugin marketplace integration

#### P2-2: Advanced Export Formats
- PowerPoint (.pptx) export template
- PDF with custom branding/logo
- Batch export scheduling (auto weekly/monthly)

#### P2-3: Collaboration Features (Future)
- Multi-device sync (cloud storage backend)
- Team mode (shared workspace)
- Activity feed / notifications

#### P2-4: AI Enhancements
- Conversation context summary (long session compression)
- Suggested actions based on usage patterns
- Voice input support (Whisper integration)

---

## 🗓️ Sprint Plan (v0.3.0)

### Sprint 1: "Hardening Foundation" (Week 1-2)
**Focus**: Test coverage, security, code organization

| Task ID | Task | Owner | Est. |
|---------|------|-------|------|
| 3.1.1 | Create test_confirmer.py (+20 tests) | Coder | 2h |
| 3.1.2 | Create test_undo_manager.py (+15 tests) | Coder | 2h |
| 3.1.3 | Create test_audit_log.py (+20 tests) | Coder | 2h |
| 3.1.4 | Create test_progress_emitter.py (+15 tests) | Coder | 2h |
| 3.1.5 | Create test_data_manager.py (+20 tests) | Coder | 3h |
| 3.1.6 | Implement API Key encryption at rest | Security | 4h |
| 3.1.7 | Extract settings_page.py from app.py | Coder | 3h |
| 3.1.8 | Extract shared components module | Coder | 2h |
| 3.1.9 | Optimize user_profile.py lazy imports | Coder | 1h |
| **Total** | | | **21h** |

**Exit Criteria**: +92 tests, 0 plaintext secrets, app.py <2500 lines

### Sprint 2: "Experience Polish" (Week 3-4)
**Focus**: Dashboard, marketplace, large module refactor

| Task ID | Task | Owner | Est. |
|---------|------|-------|------|
| 3.2.1 | Dashboard template system (3 layouts) | UI Designer | 6h |
| 3.2.2 | Dashboard panel toggle + persistence | Coder | 3h |
| 3.2.3 | Refactor task_engine_v3.py (split) | Architect | 5h |
| 3.2.4 | Refactor skill_registry.py (extract loader) | Coder | 3h |
| 3.2.5 | Skill marketplace detail page | UI Designer | 4h |
| 3.2.6 | Skill search/filter by category | Coder | 3h |
| 3.2.7 | Apple Shortcuts integration (5 actions) | DevOps | 6h |
| 3.2.8 | Extract dashboard_page.py from app.py | Coder | 3h |
| 3.2.9 | Extract marketplace_page.py from app.py | Coder | 2h |
| **Total** | | | **35h** |

**Exit Criteria**: app.py <800 lines, 3 dashboard layouts, marketplace V2, Shortcuts working

### Sprint 3: "Global Reach" (Week 5-6)
**Focus**: i18n-JP, performance, final polish

| Task ID | Task | Owner | Est. |
|---------|------|-------|------|
| 3.3.1 | Complete ja_JP locale (50+ keys) | Translator | 3h |
| 3.3.2 | Japanese date/number formatting | Coder | 2h |
| 3.3.3 | ZIP streaming export (memory opt) | Coder | 3h |
| 3.3.4 | Frontend st.cache_data optimization | Coder | 3h |
| 3.3.5 | LLM response caching layer | Architect | 4h |
| 3.3.6 | Scenario engine V2 refactor | Coder | 3h |
| 3.3.7 | Final code cleanup + documentation sync | PM | 2h |
| 3.3.8 | Full regression test suite run | Tester | 2h |
| **Total** | | | **22h**

**Exit Criteria**: 3 languages, <2s page load, 900+ tests, zero tech debt

---

## 📈 Success Metrics

| Metric | v0.2.0 (current) | v0.3.0 (target) | Delta |
|--------|------------------|-----------------|-------|
| Test count | 813 | 900+ | +10%+ |
| Max module size | 727 lines | <400 lines | -45% |
| app.py size | 3832 lines | <800 lines | -79% |
| Plaintext secrets | In settings.json | Zero | -100% |
| Supported languages | 2 (zh/en) | 3 (+ja) | +1 |
| Dashboard layouts | 1 (fixed) | 9 (3×3) | +8 |
| Load time target | N/A | <2s | New |
| Security issues | 0 open | 0 open | Maintain |

---

## 🚫 Explicitly Deferred to v0.4.0+

| Feature | Reason | Earliest Version |
|---------|--------|------------------|
| Multi-user/team mode | Requires auth backend | v0.5.0 |
| Cloud sync | Requires infrastructure | v0.5.0 |
| Mobile native app | Requires React Native | v0.6.0 |
| Plugin marketplace (public) | Legal/compliance | v0.4.0 |
| Voice input (Whisper) | Niche use case | v0.4.0 |
| OpenAI Assistants API migration | Dependency risk | v0.4.0 |

---

## ⚠️ Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Frontend split breaks navigation | Medium | High | Incremental extraction, test after each |
| API Key encryption breaks existing users | Low | Critical | Auto-migration on first launch |
| Large module refactor introduces regressions | Medium | High | Keep original as branch, feature-flag |
| i18n-JP translation quality | Medium | Low | Use professional translator for UI strings |
| Apple Shortcuts API changes | Low | Medium | Abstract action interface |

---

*Document generated as part of v0.2.0 post-release evaluation cycle*
*Next review: After Sprint 1 completion*
