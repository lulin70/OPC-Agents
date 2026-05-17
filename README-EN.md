# 🚀 OPC-Agents — Intelligent Task Execution System for One-Person Companies

> **Version**: v0.2.0 | **Status**: Beta | **License**: MIT

[![Beta](https://img.shields.io/badge/status-beta-blue)](https://github.com/lulin70/OPC-Agents)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI](https://img.shields.io/pypi/v/opc-agents)](https://pypi.org/project/opc-agents/)

---

**Languages**: [中文](README.md) | **English** | [日本語](README-JP.md)

---

## What Is This

OPC-Agents (One-Person Company Agents) is an **intelligent task execution system designed for solo entrepreneurs, freelancers, and independent creators**.

**Core Philosophy: Tell the system what result you want, and it completes the work and delivers the file to you.**

Not a chatbot. Not an advice engine. It's a **doer that gets things done**.

## What It Can Do

| You Say | System Delivers |
|---------|----------------|
| "Collect OPC company trends" | 🔍 **Research Report** (real search results + source links + structured organization) |
| "Write a Q2 marketing plan" | ✍️ **Complete Plan Document** (SMART goals + roadmap + resources/risks/acceptance criteria) |
| "Analyze competitor A" | 📊 **Analysis Report** (SWOT + action items + priority ranking) |
| "Create a product launch plan" | 🚀 **Launch Plan** (pricing strategy + promotion channels + timeline) |

### Key Features

- ✅ **Three-Sage Architecture** — Strategist Brain (intent understanding) + Executor Brain (skill execution) + Reflector Brain (result evaluation) closed-loop collaboration
- ✅ **Skill Context Passing** — SkillContext enables data flow between skills, search→analysis→creation closed loop
- ✅ **LLM-Enhanced Content Generation** — Powered by Claude Sonnet 4, high-quality output
- ✅ **Real Web Search** — DuckDuckGo live search, no fabricated data
- ✅ **Zero-Placeholder Guarantee** — Every output has specific, actionable content
- ✅ **Auto-Correction** — Automatically triggers correction strategies when quality is substandard (retry/search-and-retry/switch-skill/degrade)
- ✅ **Multi-Skill Orchestration** — Composite intents auto-decomposed into multi-step execution plans (e.g., "analyze competitors and write plan" → search → analysis → creation)
- ✅ **Task Pause/Resume** — Pause running tasks and resume from breakpoint later
- ✅ **Execution Progress Visualization** — Event-driven real-time progress tracking with SSE support
- ✅ **Long Session Context** — Multi-turn conversation maintains context, follow-up "add XX" continues from previous results
- ✅ **Async Execution** — Submit and return, background processing with progress indication
- ✅ **Quality Gate** — Auto-check deliverables for zero placeholders + minimum length + data sources; flag if substandard
- ✅ **Output Redaction** — Auto-detect and replace API keys/GitHub tokens in generated content
- ✅ **Knowledge Base Fallback** — 6 categories, 20 professional knowledge entries, auto-fallback when search fails
- ✅ **File Delivery** — Auto-generates `.md` files with download button
- ✅ **Security Protection** — Command whitelist + path validation + input length limit + audit log + input validation + Prompt injection defense + URL safety + error sanitization + encrypted API key storage
- ✅ **Test Coverage** — 1126 test cases, 100% pass rate, CI auto-verification (covers settings/onboarding/backup/i18n/dashboard/shortcuts/marketplace_v2/error_handler and all new modules)
- ✅ **Skill Marketplace API** — External skill registration/discovery/invocation, API Key auth + permission levels
- ✅ **MCP Protocol Compatible** — Compatible with Microsoft Model Context Protocol standard, supports tools/resources/prompts
- ✅ **Plugin System** — Community plugin hot-loading + sandbox isolation + lifecycle management
- ✅ **Custom Skill Editor** — Form-based skill creation/testing/preview/publishing
- ✅ **Quality/Fast Mode** — User-selectable three-sage full closed loop or skip-reflection fast execution
- ✅ **📋 Unified Settings Management** — 5-tab settings center (LLM/SMTP/API Keys/Security/Profile), SettingsManager singleton
- ✅ **🚶 First-Run Onboarding** — 3-step onboarding wizard (Welcome → API Key Config → Feature Intro)
- ✅ **💾 Data Backup & Restore** — ZIP/JSON/CSV export, SHA256 verification, Zip Slip protection, DataBackupManager
- ✅ **🛡️ User-Friendly Error Handling** — 9 exception types → Chinese-friendly messages, ErrorHandler unified exception translation
- ✅ **💬 WeChat E2E Integration** — WeChatAgent + WeChatGateway for WeChat-based task interaction
- ✅ **📊 Modular Dashboard** — DashboardConfig (3 layouts × 3 densities × 6 panels), template system supports 9 combinations
- ✅ **🌐 Tri-Lingual i18n** — I18nManager supports zh_CN/en_US/ja_JP, 58+ translation keys
- ✅ **🛒 Skill Marketplace V2** — Detail panel + 16-category filter + version pinning,全新 UI experience
- ✅ **🔍 Global Search** — Cross-module unified search for skills/customers/articles/tasks in one place
- ✅ **⌨️ Apple Shortcuts Integration** — 5 shortcut actions (quick_task/query_status/create_deliverable/record_income/daily_report)
- ✅ **🔐 API Key Encryption at Rest** — Fernet symmetric encryption, auto-generated key (.env.local), enhanced secure_storage
- ✅ **🧩 Code Modularization Refactor** — Frontend split from 3834-line monolithic into 8 modules; backend extracted skill_models/skill_builtin/skill_executors/task_types/task_content_generators/scenario_definitions as independent modules

## Quick Start

### Prerequisites

- Python 3.9+
- At least one LLM API Key (recommended: [MOKA](https://moka-ai.com))

### Option 1: pip Install

```bash
# 1. Install
pip install opc-agents

# 2. Create workspace and configure API Key
mkdir my-opc-workspace && cd my-opc-workspace
echo "MOKA_API_KEY=your-key-here" > .env

# (Optional) Use encrypted storage instead of plaintext .env
# python -m opc_manager.secure_storage set MOKA_API_KEY your-key-here

# 3. Launch
opc-agents
```

> After pip install, `.env`, deliverables, and logs are stored in the current working directory.

### Option 2: Source Install (Recommended for Developers)

```bash
git clone https://github.com/lulin70/OPC-Agents.git
cd OPC-Agents
chmod +x install.sh start.sh
./install.sh

# Configure API Key
cp .env.example .env
# Edit .env and fill in your MOKA API Key

# Launch
./start.sh
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

### About API Keys

> ⚠️ **OPC-Agents does NOT provide LLM services.** Choose your own LLM provider and obtain your own API key. The project does not store any API keys or sensitive information.

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
| Wrong Python version | Requires Python 3.9+, run `python3 --version` to check |
| Dependency install fails | Try `pip install --upgrade pip` and retry |

## Project Structure

```
OPC-Agents/
├── frontend/              # Streamlit frontend (modularized)
│   ├── app.py             # Main UI router (1687 lines, routing only)
│   ├── components/        # Shared components
│   │   └── shared.py      # 16 UI helper functions (639 lines)
│   └── pages/             # Page modules
│       ├── dashboard_page.py   # Dashboard page (578 lines + templates)
│       ├── marketplace_page.py # Skill Marketplace V2 (547 lines)
│       └── settings_page.py    # Settings management (666 lines)
├── opc_manager/           # Core business logic (84 .py modules)
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
│   ├── error_handler.py   # 🛡️ ErrorHandler (9 exception types → friendly messages)
│   ├── data_backup.py     # 💾 DataBackupManager (ZIP/JSON/CSV export, SHA256, Zip Slip protection)
│   ├── i18n.py            # 🌐 I18nManager (zh_CN/en_US/ja_JP, 58+ keys)
│   ├── dashboard_config.py# 📊 DashboardConfig (3 layouts × 3 densities × 6 panels = 9 combos)
│   ├── shortcuts_handler.py# ⌨️ Apple Shortcuts integration (5 CLI actions)
│   ├── wechat_agent.py    # 💬 WeChat E2E agent
│   ├── wechat_gateway.py  # 💬 WeChat gateway
│   │
│   ├── # === v0.2.0 Modular Extraction ===
│   ├── task_types.py              # Task type definitions extracted from task_engine_v3
│   ├── task_content_generators.py # Content generators extracted from task_engine_v3
│   ├── skill_models.py            # Skill models extracted from skill_registry
│   ├── skill_builtin.py           # 21 built-in skill definitions (standalone module)
│   ├── skill_executors.py         # SkillExecutorMixin (20 execute methods)
│   ├── scenario_definitions.py    # 9 scenario definitions + dataclasses
│   │
│   ├── scenario_migrator.py# Scenario Migrator (9 scenarios → skill mapping)
│   ├── task_engine_adapter.py# TaskEngine adapter (Three-Sage ↔ TaskEngineV3 bridge)
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
├── opc_manager/api/        # API events module
│   └── events.py          # Event definitions
├── opc_manager/export/     # Export module
│   ├── manager.py          # Export manager
│   ├── models.py           # Export models
│   └── exporters/          # Format exporters
│       ├── excel_exporter.py
│       ├── pdf_exporter.py
│       ├── word_exporter.py
│       └── image_exporter.py
├── opc_hr/                # Search & knowledge base
│   └── web_search.py      # DuckDuckGo web search
├── plugins/               # Community plugins
│   ├── plugin_config.json
│   ├── data_converter.py
│   └── text_summarizer.py
├── tests/                 # Test suite (39 test files, 1126 tests, 100% pass)
├── docs/                  # Project documentation
│   ├── API.md             # API documentation
│   └── guides/            # Quick start guides (zh/en/jp)
├── requirements.txt       # Core dependencies
├── requirements-dev.txt   # Dev dependencies (black/flake8/pytest)
├── .env.example           # Environment variable template
├── .env.local             # Auto-generated encryption key (gitignore protected)
├── install.sh             # One-click install script
├── start.sh               # One-click launch script
└── VERSION                # Version file
```

## Testing

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run all tests (1126 test cases)
PYTHONPATH=. pytest tests/ -v

# Run with coverage report
PYTHONPATH=. pytest tests/ --cov=opc_manager --cov-report=term-missing

# Run specific module tests
PYTHONPATH=. pytest tests/test_settings.py tests/test_onboarding.py tests/test_i18n.py -v
```

> **Test Coverage**: All 84 opc_manager modules + 8 frontend modules + new modules (settings/onboarding/backup/i18n/dashboard/shortcuts/marketplace_v2/error_handler/wechat, etc.)

## Version History

| Version | Date | Milestone |
|---------|------|-----------|
| **0.2.0** | **2026-05-17** | **FINAL** — Product Release: Unified settings + onboarding + data backup/restore + error handling + WeChat E2E + modular dashboard + i18n tri-lingual + Skill Marketplace V2 + global search + Apple Shortcuts + API Key encryption (Fernet) + code modularization refactor (84 modules / 39 test files / 1126 tests) |
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
