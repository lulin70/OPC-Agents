# 🚀 OPC-Agents — Intelligent Task Execution System for One-Person Companies

> **Version**: v0.3.6 | **Status**: Beta | **License**: MIT

[![Beta](https://img.shields.io/badge/status-beta-blue)](https://github.com/lulin70/OPC-Agents)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI](https://img.shields.io/pypi/v/opc-agents)](https://pypi.org/project/opc-agents/)

---

**Languages**: [中文](README.md) | **English** | [日本語](README-JP.md)

---

## 30 Seconds to Understand OPC-Agents

**🎯 One-liner**: An AI execution team for one-person companies — you state the requirement, it delivers the result.

**⚡ Core Flow**:
```
You state requirement → AI analyzes + searches + generates → You get deliverable (report/plan/copy/email...)
```

**🚀 3-Step Quickstart**:
```bash
pip install opc-agents          # 1. Install
opc-agents                      # 2. Launch
# 3. Type "write a weekly report for me" → get deliverable
```

---

## 🆕 v0.3.5 Highlights

> Full changes see [CHANGELOG.md](CHANGELOG.md), architecture design see [docs/architecture/PARALLEL_SAGES_DESIGN.md](docs/architecture/PARALLEL_SAGES_DESIGN.md).

- **⚡ Three Sages Parallel Voting Architecture Returns**: Switched from serial pipeline (3×RTT) to parallel voting (1×RTT), 3x latency reduction. Inspired by EVA MAGI three-sage synchronous voting + minority report mechanism, key decision points protected by upfront consensus.
- **🎯 Focus on 3 Core Skills**: Email / Finance / Report. 9 non-core skills frozen (see [docs/spec/SKILL_FREEZE_LIST.md](docs/spec/SKILL_FREEZE_LIST.md)), making each core skill genuinely great.
- **🧠 IntentRouter 3-Way Smart Routing**: SIMPLE / COMPLEX / GREETING three-way classification. Simple tasks bypass the three sages directly — fast and cost-effective; complex tasks enter parallel voting for quality assurance.
- **🛡 Key Decision Point Upfront Consensus Protection**: ConsensusEngine shifts from "post-hoc remedy" to "upfront gatekeeping", ExecutorBrain gives real opinions (fake opinion rules removed), ReflectorBrain upfront prediction + minority report.
- **📊 Significant Quality Improvement**: Total coverage 62.87%, core skill targeted test coverage email_skill 99% / finance_skill 100% (targeted `pytest --cov` scope; under full test suite email_skill 17.0% / finance_skill 14.5%, see `coverage.json`; Sprint 2 improved targeted coverage from 16.96%/14.46% baseline); added 7 real LLM E2E tests (CI auto-runs every Monday).
- **🌐 i18n Refactor**: 3857 lines → 133 lines logic layer + JSON-ification, backward compatible, drastically reduced maintenance cost.

> 🧪 Want to try it? Read [docs/guides/USER_TRIAL_GUIDE.md](docs/guides/USER_TRIAL_GUIDE.md) (3-minute setup), demo scripts at [docs/guides/DEMO_SCRIPTS.md](docs/guides/DEMO_SCRIPTS.md), feedback form at [docs/guides/FEEDBACK_FORM.md](docs/guides/FEEDBACK_FORM.md).

---

## What Is This

OPC-Agents (One-Person Company Agents) is an **intelligent task execution system designed for solo entrepreneurs, freelancers, and independent creators**.

**Core Philosophy: Tell the system what result you want, and it completes the work and delivers the file to you.**

Not a chatbot. Not an advice engine. It's a **doer that gets things done**.

## What It Can Do for You

| You Say | It Delivers |
|---------|-------------|
| "Collect OPC company trends" | 🔍 Research Report (real search + source links + structured organization) |
| "Write a Q2 marketing plan" | ✍ Complete Plan (SMART goals + roadmap + risks + acceptance criteria) |
| "Analyze competitor A" | 📊 Analysis Report (SWOT + action items + priority ranking) |
| "Send an email to a client" | 📧 Email Sending (template rendering + SMTP sending + rate limiting) |
| "Record an income entry" | 💰 Finance Record (auto-categorization + monthly report + trend analysis) |
| "Add customer info" | 👥 Customer Profile (encrypted storage + silence alert + collaboration tracking) |

---

## Core Capabilities

**Three Sages Parallel Voting Architecture** — Three AI roles vote synchronously in a closed-loop collaboration, with key decisions protected by upfront consensus (v0.3.0 upgrade, see [docs/architecture/PARALLEL_SAGES_DESIGN.md](docs/architecture/PARALLEL_SAGES_DESIGN.md)):
- 🧠 **StrategistBrain**: Understands your intent, plans execution steps
- ⚡ **ExecutorBrain**: Invokes skills and tools, generates deliverables (v0.3.0 onwards gives "real opinions", no more fake opinion rules)
- 🔍 **ReflectorBrain**: Evaluates result quality, upfront prediction + minority report, auto-corrects when substandard
- 🛡 **ConsensusEngine**: Three sages parallel voting (1×RTT, 3x faster than serial 3×RTT), key decision point upfront protection

**IntentRouter 3-Way Smart Routing** — Routes by task complexity, saving time and money:
- 🟢 **SIMPLE**: Simple tasks execute directly, bypassing the three sages
- 🟡 **COMPLEX**: Complex tasks enter parallel voting, quality assured
- 👋 **GREETING**: Greetings/small talk responded directly

**3 Core Skills** — v0.3.0 focused polish, covering the most frequent one-person company scenarios (other skills frozen, see [docs/spec/SKILL_FREEZE_LIST.md](docs/spec/SKILL_FREEZE_LIST.md)):
- 📧 **Email**: SMTP sending + template rendering + rate limiting
- 💰 **Finance**: Income/expense records + monthly report + trend analysis
- 📊 **Report**: Weekly/monthly/annual report auto-generation

**Real Search** — DuckDuckGo live search integration, no fabricated data, every conclusion has a source.

---

## Accelerators

These features make the core workflow **better, faster, and stronger over time**:

| Accelerator | How It Helps You Get Results Faster |
|-------------|-------------------------------------|
| 🧠 **Cross-Session Memory** | Remembers your preferences and context, no need to repeat every time (requires [CarryMem](https://github.com/lulin70/carrymem), `pip install opc-agents[memory]`) |
| 🔄 **Flywheel Growth** | The more you use it, the higher your level (🌱Novice→👑Legend), output quality auto-improves |
| 🏪 **Skill Marketplace** | Search and install third-party skills, expand capabilities on demand |
| 📚 **External Knowledge Base** | Connect Obsidian/Yuque/Feishu/Notion/Siyuan Notes, AI references your private materials |
| 📜 **Rule Engine** | Failed experiences auto-extracted as rules, same errors never repeated |
| ↩ **Undo Mechanism** | Operations are reversible, use boldly with confidence |
| 🌐 **Tri-Lingual Switch** | Chinese/English/Japanese UI one-click switch |
| 🧊 **LLM Cache** | Same questions don't trigger duplicate API calls, saves time and money |

## Ecosystem Tools

Encounter specific scenarios? Use these together for better results:

| Scenario | Recommended Tool | Description |
|----------|-----------------|-------------|
| Want AI to remember your preferences | [CarryMem](https://github.com/lulin70/carrymem) | Cross-session persistent memory engine, `pip install opc-agents[memory]` to enable |
| Have dev tasks needing multi-role collaboration | [DevSquad](https://github.com/lulin70/DevSquad) | 7-role AI team (Architect/PM/Security/Tester/Coder/DevOps/UI), complex dev task decomposition and collaboration |

## Architecture Overview

> v0.3.0 upgraded to Three Sages Parallel Voting architecture, full design see [docs/architecture/PARALLEL_SAGES_DESIGN.md](docs/architecture/PARALLEL_SAGES_DESIGN.md), latency comparison see [docs/internal/PARALLEL_LATENCY_REPORT.md](docs/internal/PARALLEL_LATENCY_REPORT.md).

```
┌─────────────────────────────────────────────────────┐
│                    OPC-Agents v0.3.0                 │
├─────────────────────────────────────────────────────┤
│  User Input                                          │
│       ↓                                              │
│  IntentRouter 3-Way Smart Routing                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ SIMPLE   │  │ COMPLEX  │  │ GREETING │          │
│  │ Direct   │  │ Enter    │  │ Direct   │          │
│  │ Execute  │  │ Voting   │  │ Respond  │          │
│  └────┬─────┘  └────┬─────┘  └──────────┘          │
│       ↓              ↓                              │
│  ┌─────────────────────────────────────────┐        │
│  │ Three Sages Parallel Voting (1×RTT)     │        │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ │        │
│  │  │Strategist│ │Executor  │ │Reflector │ │        │
│  │  │Brain     │ │Brain     │ │Brain     │ │        │
│  │  │(real op) │ │(real op) │ │(upfront) │ │        │
│  │  └─────┬────┘ └─────┬────┘ └─────┬────┘ │        │
│  │        └──────┬─────┴──────┬──────┘     │        │
│  │               ↓            ↓            │        │
│  │     ConsensusEngine (key decision       │        │
│  │     upfront protection)                 │        │
│  │     · Parallel voting · Minority report │        │
│  │     · Conflict resolution               │        │
│  └────────────────────┬────────────────────┘        │
│                       ↓                             │
├─────────────────────────────────────────────────────┤
│  3 Core Skills (v0.3.0 focus)                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐│
│  │ 📧 email     │ │ 💰 finance   │ │ 📊 report    ││
│  │ SMTP+tpl+lim │ │ inc/exp+rpt  │ │ wk/mo/yr rpt ││
│  └──────────────┘ └──────────────┘ └──────────────┘│
│  (Other 9 non-core skills frozen, see SKILL_FREEZE)│
├─────────────────────────────────────────────────────┤
│  External Extensions                                 │
│  ┌──────────────┐  ┌──────────────┐                │
│  │ 🔌 Skill     │  │ 🔗 MCP       │                │
│  │   Marketplace│  │   Service    │                │
│  └──────────────┘  └──────────────┘                │
│  ┌──────────────┐  ┌──────────────┐                │
│  │ 👤 User      │  │ 🔒 Data      │                │
│  │   Profile    │  │   Security   │                │
│  └──────────────┘  └──────────────┘                │
├─────────────────────────────────────────────────────┤
│  SQLite Unified Storage (AES encryption + 0600 perm) │
└─────────────────────────────────────────────────────┘
```

## Quick Start

> 🆕 **v0.3.0 Trial Users**: Non-technical users please read [docs/guides/USER_TRIAL_GUIDE.md](docs/guides/USER_TRIAL_GUIDE.md) directly (illustrated version, 3-minute setup, includes API Key acquisition links and no-API-Key experience mode). This section is a quick reference for developers.

### Prerequisites

- Python 3.10+
- At least one LLM API Key (recommended: [MOKA](https://moka-ai.com))

### Option 1: pip Install

```bash
# 1. Install
pip install opc-agents==0.3.6

# 2. Install encryption dependency (recommended, for email passwords and other sensitive field encryption)
pip install cryptography

# 3. Create workspace and configure API Key
mkdir my-opc-workspace && cd my-opc-workspace
echo "MOKA_API_KEY=your-key-here" > .env

# (Optional) Use encrypted storage instead of plaintext .env
# python -m opc_manager.secure_storage set MOKA_API_KEY your-key-here

# First launch will auto-generate .env.local (contains encryption key, protected by gitignore)
# To manually set encryption key:
# echo "OPC_ENCRYPTION_KEY=$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" >> .env.local

# 4. Launch
opc-agents
```

> After pip install, `.env`, deliverables, and logs are stored in the current working directory.

### Option 2: Source Install (Recommended for Developers)

```bash
git clone https://github.com/lulin70/OPC-Agents.git
cd OPC-Agents
chmod +x scripts/install.sh scripts/start.sh
./scripts/install.sh

# Install encryption dependency
pip install cryptography

# Configure API Key
cp .env.example .env
# Edit .env and fill in your MOKA API Key

# Launch
./scripts/start.sh
```

### Option 3: Docker Deployment

```bash
docker compose up -d
```

| Port | Service | Description |
|------|---------|-------------|
| 8501 | Main App (Streamlit) | Web UI |
| 8900 | Skill Marketplace API (FastAPI) | REST API |
| 8901 | MCP SSE Endpoint | Model Context Protocol |

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPC_DATA_DIR` | Data storage directory | `data/` under project root |
| `OPC_ENCRYPTION_KEY` | AES encryption key (**must be set**, otherwise encryption operations throw RuntimeError) | None (encryption refused when unset) |
| `MOKA_API_KEY` | MOKA LLM API key | — |
| `GLM_API_KEY` | Zhipu GLM API key | — |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `OLLAMA_BASE_URL` | Ollama local model address | — |
| `OPC_SKIP_REFLECT` | Skip reflection phase (fast mode) | `false` |
| `CARRYMEM_ENABLED` | Enable cross-session persistent memory | `false` |
| `CARRYMEM_DB_PATH` | CarryMem database path | `~/.opc-agents/memory.db` |
| `OPC_KB_ENABLED` | Enable external knowledge base | `false` |
| `OPC_KB_TYPE` | Knowledge base type | `local` |
| `OPC_KB_PATH` | Knowledge base path (Obsidian/local) | `~/knowledge` |

> ⚠ **Security Note**: `OPC_ENCRYPTION_KEY` is required. When unset, `encrypt_field()` will throw `RuntimeError`, causing email passwords, customer sensitive fields, and other encryption operations to fail. Make sure to set a strong random key in `.env`.

### About API Keys

> ⚠ **OPC-Agents does NOT provide LLM services.** Choose your own LLM provider and obtain your own API key. The project does not store any API keys or sensitive information.

| Backend | Model | Config Variable | Quality | Get Key |
|---------|-------|-----------------|---------|---------|
| MOKA | Claude Sonnet 4 | `MOKA_API_KEY` | ⭐⭐⭐⭐⭐ | [moka-ai.com](https://moka-ai.com) |
| Zhipu GLM | GLM-4 | `GLM_API_KEY` | ⭐⭐⭐⭐ | [open.bigmodel.cn](https://open.bigmodel.cn) |
| OpenAI | GPT-4o | `OPENAI_API_KEY` | ⭐⭐⭐⭐ | [platform.openai.com](https://platform.openai.com) |
| Ollama | Local models | `OLLAMA_BASE_URL` / `OLLAMA_ENABLED` / `OLLAMA_MODEL` | ⭐⭐⭐ | [ollama.com](https://ollama.com) |

> Works without an API Key (template mode), but content quality is limited. **Strongly recommended to configure at least one API Key.**

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Page shows "Template Mode" | Check if API Key is filled in `.env` |
| Port in use | `opc-agents -- --server.port 8502` |
| Wrong Python version | Requires Python 3.10+, run `python3 --version` to check |
| Dependency install fails | Try `pip install --upgrade pip` and retry |
| Encryption not available | Run `pip install cryptography` to install encryption dependency |

## Project Structure

```
OPC-Agents/
├── frontend/              # Streamlit frontend (modularized)
│   ├── app.py             # Main UI router (579 lines, routing only)
│   ├── components/        # Shared components
│   │   ├── shared.py      # 16 UI helper functions (384 lines)
│   │   ├── session_utils.py      # Session utility functions
│   │   ├── export_helpers.py     # Export helper functions
│   │   ├── progress_indicator.py # Progress indicator component
│   │   ├── toast_notifications.py # Toast notification component
│   │   ├── theme_manager.py      # Theme manager
│   │   ├── timeline_data.py      # Timeline data processing
│   │   ├── timeline_export.py    # Timeline export
│   │   ├── timeline_filters.py   # Timeline filters
│   │   ├── undo_display.py       # Undo operation display
│   │   ├── undo_export.py        # Undo operation export
│   │   └── undo_actions.py       # Undo operation actions
│   ├── page_modules/      # Page modules
│   │   ├── dashboard_page.py   # Dashboard page (578 lines + templates)
│   │   ├── marketplace_page.py # Skill Marketplace V2 (547 lines)
│   │   └── settings_page.py    # Settings management (666 lines)
│   ├── routers/            # Router modules
│   └── renderers/          # Renderer modules
├── opc_manager/           # Core business logic (99 .py modules)
│   ├── cli.py             # CLI entry point (opc-agents command after pip install)
│   ├── agent_loop.py      # Execution loop (Plan→Act→Observe→Reflect 4-phase closed loop)
│   ├── strategist_brain.py# Strategist Brain (intent understanding + task planning + composite intent decomposition)
│   ├── executor_brain.py  # Executor Brain (skill execution + tool invocation + resource management)
│   ├── reflector_brain.py # Reflector Brain (result evaluation + auto-correction strategy)
│   ├── consensus_engine.py# Consensus Engine (three-sage opinion coordination + conflict resolution)
│   ├── skill_registry.py  # Skill Registry (21 built-in skills + scenario migration + DI)
│   ├── tool_system.py     # Tool Framework (permission control + security protection + audit log)
│   ├── utils.py           # Utilities (BoundedDict + EventEmitter)
│   │
│   ├── # === v0.2.0 New Core Modules ===
│   ├── settings.py        # 📋 SettingsManager singleton (5 tabs: LLM/SMTP/API Keys/Security/Profile)
│   ├── onboarding.py      # 🚶 OnboardingManager (3-step first-run wizard)
│   ├── error_handler.py   # 🛡 ErrorHandler (9 exception types → friendly messages)
│   ├── data_backup.py     # 💾 DataBackupManager (ZIP/JSON/CSV export, SHA256, Zip Slip protection)
│   ├── i18n.py            # 🌐 I18nManager (zh_CN/en_US/ja_JP, 1242 keys)
│   ├── dashboard_config.py# 📊 DashboardConfig (3 layouts × 3 densities × 6 panels = 9 combos)
│   ├── shortcuts_handler.py# ⌨ Apple Shortcuts integration (5 CLI actions)
│   │
│   ├── # === v0.2.5 New: CarryMem + Knowledge Base + Flywheel ===
│   ├── memory_bridge.py   # 🧠 MemoryBridge (CarryMem adapter, persistent memory + rule engine + flywheel)
│   ├── knowledge_bridge.py# 📚 KnowledgeBridge (6 KB adapters: Obsidian/Yuque/Feishu/Notion/Siyuan/Local)
│   ├── search_cache.py    # 🔍 Search cache (SQLite cache + TTL + hit tracking)
│   ├── intent_classifier.py # 🎯 Intent classifier (lightweight intent routing)
│   ├── correction_manager.py # 🔧 Correction manager (auto-correction strategy coordination)
│   ├── embedding_service.py # 📐 Embedding service (vector embedding + similarity computation)
│   ├── llm_cache.py       # 🧊 LLM cache (SQLite cache + SHA256 key + 7-day TTL + thread-safe)
│   ├── skill_reviews.py   # ⭐ Skill reviews (1-5 stars + text reviews + aggregated average)
│   │
│   ├── # === v0.2.0 Modular Extraction ===
│   ├── task_types.py              # Task type definitions extracted from task_engine_v3
│   ├── task_content_generators.py # Content generators extracted from task_engine_v3
│   ├── skill_models.py            # Skill models extracted from skill_registry
│   ├── skill_builtin.py           # 21 built-in skill definitions (standalone module)
│   ├── skill_executors.py         # SkillExecutorMixin (20 execute methods)
│   ├── scenario_definitions.py    # 9 scenario definitions + dataclasses
│   │
│   ├── skill_marketplace.py # Skill Marketplace V2 (search/install/detail/filter/version pinning + MCP discovery)
│   ├── skill_marketplace_api.py # Skill Marketplace API server (FastAPI server)
│   ├── mcp_protocol.py      # MCP protocol support (Model Context Protocol compatible)
│   ├── mcp_transport.py     # MCP transport layer (SSE + stdio)
│   ├── plugin_system.py     # Plugin system (sandbox isolation + lifecycle management)
│   ├── skill_editor.py      # Skill editor (custom skill creation/testing/publishing)
│   ├── performance_monitor.py# Performance monitoring (SLA management + LLM cache + metrics)
│   ├── task_engine_v3.py  # Task execution engine
│   ├── llm_content.py     # LLM-enhanced content generation (RAG hybrid mode)
│   ├── llm_service.py     # LLM service layer (MOKA/GLM/OpenAI/Ollama)
│   ├── search_processor.py# Search result post-processing (TF-IDF + KB fallback)
│   ├── async_executor.py  # Async task executor
│   ├── session_context.py # Multi-turn conversation context management
│   ├── validators.py      # Input validation layer (Pydantic models)
│   ├── business_type_detector_v2.py  # Business type detection
│   ├── business_types.py             # Business type enum definitions
│   ├── scenario_engine_v2.py         # Scenario matching engine
│   ├── flywheel_tracker.py           # Growth flywheel tracker
│   ├── persona_manager.py            # Persona management
│   ├── persona_variants.yaml         # 6 business type persona configs
│   ├── monitoring.py                 # Monitoring & logging
│   ├── config.py                     # Configuration management
│   ├── protocols.py                  # Protocol interface + NullProvider degradation
│   ├── secure_storage.py             # Encrypted API key storage (Fernet)
│   ├── undo_manager.py               # Undo manager
│   ├── audit_log.py                  # Audit log
│   ├── confirmer.py                  # Confirmation mechanism
│   ├── progress_emitter.py           # Progress event emitter
│   └── version.py         # Version management (SSOT)
├── opc_manager/export/     # Export module
│   ├── manager.py          # Export manager
│   ├── models.py           # Export models
│   └── exporters/          # Format exporters
│       ├── excel_exporter.py
│       ├── pdf_exporter.py
│       ├── word_exporter.py
│       └── image_exporter.py
├── tests/                 # Test suite (89 test files, 3396 tests, 100% pass)
├── docs/                  # Project documentation
│   ├── API.md             # API documentation
│   └── guides/            # Quick start guides (zh/en/jp)
├── scripts/               # Deployment & ops scripts
│   ├── install.sh         # One-click install script
│   └── start.sh           # One-click launch script
├── requirements.txt       # Core dependencies
├── requirements-dev.txt   # Dev dependencies (black/flake8/pytest)
├── .env.example           # Environment variable template
├── .env.local             # Auto-generated encryption key (gitignore protected)
└── VERSION                # Version file
```

## Testing

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run all tests (3396 test cases)
PYTHONPATH=. pytest tests/ -v

# Run with coverage report
PYTHONPATH=. pytest tests/ --cov=opc_manager --cov-report=term-missing

# Run specific module tests
PYTHONPATH=. pytest tests/integration/test_settings.py tests/integration/test_onboarding.py tests/unit/test_i18n.py -v
```

> **Test Coverage**: All 99 opc_manager modules + 38 frontend modules + new modules (settings/onboarding/backup/i18n/dashboard/shortcuts/marketplace_v2/error_handler/wechat, etc.)

## Version History

| Version | Date | Milestone |
|---------|------|-----------|
| **0.3.6** | **2026-07-10** | **Tech Debt Cleanup P2-P3** — install.bat removal (pip install cross-platform) + task_skill SQL parameterization (IN/NOT IN placeholders) + web_search.py migration from opc_hr/ to opc_manager/ (eliminate fake layering) + fix 2 failing tests + CI coverage threshold 59%→65% |
| **0.3.5** | **2026-07-09** | **Maturity Fixes + God Class Split** — DevSquad 7-dimension assessment 18 P0+P1+P2 fixes (ruff 43→0 / trilingual README / ghost function cleanup / pre-commit hooks) + tests/ layering unit/integration/e2e (87 files migrated) + StrategistBrain/ReflectorBrain Facade split (884→176 / 841→222 lines) + virtual layering architecture guard (96 tests) + Dockerfile version sync |
| **0.3.4** | **2026-07-07** | **Frozen Skills Removal + Release Pipeline Fix** — Deleted tax_reminder/calendar/proposal 3 frozen skills + 90 i18n orphan keys cleaned + release.yml E2E isolation fix + first release.yml pipeline trigger |
| **0.3.3** | **2026-06-28** | **Tech Debt Cleanup** — TD-065 mypy 516→0 errors (CI blocking) + TD-066 settings_encryption fail-open→fail-closed + flake8 E501 cleared + 3174 passed |
| **0.3.2** | **2026-06-27** | **Project Tidy Assessment Fix** — DevSquad 7-dim assessment 72→79 (B+) + 17 version sync + check_prompt_injection ghost function integrated + mypy CI integration + 3167 passed |
| **0.3.1** | **2026-06-26** | **Ghost Feature Removal** — Deleted api/events + experimental/wechat + plugin_system + plugins/ (~2196 lines dead code) + flake8 F401/F841 348 items cleared + 3165 passed |
| **0.3.0** | **2026-06-19** | **Three Sages Parallel Voting Architecture Returns** — Parallel voting (1×RTT, 3x latency reduction) + ConsensusEngine upfront + ExecutorBrain real opinions + ReflectorBrain upfront prediction + IntentRouter 3-way routing + focus on 3 core skills (email/finance/report) + 9 non-core skills frozen + i18n refactor (3857→133 lines) + coverage 62.87% + real LLM E2E tests |
| **0.2.5** | **2026-06-07** | **Architecture Unification + Security Hardening** — Architecture unification refactor + LLM concurrency control + security hardening + 3305 tests / 76 files |
| **0.2.4** | **2026-05-24** | **Memory + Knowledge Enhancement** — CarryMem deep integration + knowledge search optimization + notification system + extended tests |
| **0.2.3** | **2026-05-24** | **CarryMem Integration** — Cross-session persistent memory (MemoryBridge) + rule engine + flywheel mechanism + LLM cache + skill scoring |
| **0.2.2** | **2026-05-21** | **CarryMem + Knowledge Base + Flywheel** — Cross-session persistent memory + rule engine + 6 KB adapters + flywheel mechanism + LLM cache + skill reviews + frontend modularization + E2E tests (1952 tests / 56 files) |
| **0.2.2** | **2026-05-20** | **Quality Fix** — i18n 315+ hardcoded cleanup + backup AES encryption + export sanitization + MCP default localhost + Onboarding merge + mobile responsive + keyboard shortcuts fix + CI security scan |
| 0.2.1 | 2026-05-18 | 8 OPC skills integrated + tech debt cleanup (32 bare except + i18n 97 keys) |
| **0.2.0** | **2026-05-17** | **FINAL** — Product Release: Unified settings + onboarding + data backup/restore + error handling + WeChat E2E + modular dashboard + i18n tri-lingual + Skill Marketplace V2 + global search + Apple Shortcuts + API Key encryption (Fernet) + code modularization refactor (87 modules / 56 test files / 1860 tests) |
| 0.1.8 | 2026-05-14 | 21 built-in skills + external skill marketplace + MCP service discovery + user profile + data security + SQLite unified storage |
| 0.1.9-delta | 2026-05-09 | Real-run verification: Three-Sage LLM-driven + Skill Marketplace FastAPI + MCP transport + Plugin examples + Editor UI + Performance monitoring |
| 0.1.9-gamma | 2026-05-09 | Refactoring: Three-Sage integration + Skill Marketplace API + MCP protocol + Plugin system + Skill editor |
| 0.1.9 | 2026-05-09 | End-to-end closed loop: auto-correction + multi-skill orchestration + task pause/resume + progress visualization + long session context |
| 0.1.8 | 2026-05-08 | Core skill development: 6 skills upgraded from mock to real + search enhancement + LLM integration |
| 0.1.7 | 2026-05-07 | Three-Sage Architecture: Strategist Brain + Executor Brain + Reflector Brain + Consensus Engine + Skill Registry + Tool Framework |
| 0.1.6 | 2026-05-03 | User onboarding + Quality feedback + Deliverable search + Empty state examples + 3D code review fixes |
| 0.1.5 | 2026-05-03 | Multi-turn follow-up + Quality gate + Security tests + Protocol degradation + Output redaction + Ollama support |
| 0.1.2 | 2026-04-28 | Security hardening + Performance optimization: XSS fixes, Prompt injection defense, singleton pattern, thread safety |
| 0.1.1-beta | 2026-04-27 | Bug fixes: LLM init / search deps / scenario path / context pollution / placeholder replacement |
| 0.1.0-beta | 2026-04-24 | Beta release: Install flow fixes, security hardening, CI passing |
| 0.1.0 | 2026-04-23 | "Trustworthy & Usable": Version unification, Mock removal, MOKA API integration, async execution |

## License

[MIT License](LICENSE)
