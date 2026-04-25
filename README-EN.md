# 🚀 OPC-Agents — Intelligent Task Execution for One-Person Companies

> **Version**: v0.1.0-beta | **Status**: Beta Testing | **License**: MIT

---

## 🎉 Beta Testing Open!

OPC-Agents v0.1.0-beta is now available for testing!

**How to participate:**
1. One-click install: `git clone https://github.com/lulin70/OPC-Agents.git && cd OPC-Agents && ./install.sh`
2. Share your feedback at [Issue #1](https://github.com/lulin70/OPC-Agents/issues/1)
3. Found a bug? Create an Issue with the `bug` label

---

## What Is This

OPC-Agents (One-Person Company Agents) is an **intelligent task execution system for solo entrepreneurs, freelancers, and indie makers**.

**Core idea: Tell it what result you need, and it delivers a file directly.**

Not a chatbot. Not a suggestion engine. It's an **executor that gets things done**.

## What It Can Do

| You Say | It Delivers |
|---------|-------------|
| "Help me research OPC company trends" | 🔍 **Research report** (real search results + source links + structured summary) |
| "Write a Q2 marketing plan" | ✍️ **Complete plan** (SMART goals + roadmap + resources/risks/acceptance criteria) |
| "Analyze competitor A" | 📊 **Analysis report** (SWOT + action items + priority ranking) |
| "Create a product launch plan" | 🚀 **Launch plan** (pricing strategy + promotion channels + timeline) |

### Key Features

- ✅ **LLM-Enhanced Content Generation** — Powered by Claude Sonnet 4, 91.2% Chinese capability
- ✅ **Real Web Search** — DuckDuckGo live search, no fabricated data
- ✅ **Zero Placeholder Guarantee** — Every output has specific, actionable content
- ✅ **Async Execution** — Submit and return immediately, background processing with progress indication
- ✅ **Knowledge Base Fallback** — 6 categories, 20 entries, automatic fallback when search fails
- ✅ **File Delivery** — Auto-generates `.md` files with download buttons
- ✅ **Multi-turn Dialogue** — Context-aware iterative optimization
- ✅ **Security Protection** — Input validation + Prompt injection defense + URL safety + Error sanitization
- ✅ **Test Coverage** — 229 test cases, 100% pass rate, CI auto-verification

## Quick Start

### Option 1: One-Click Install (Recommended)

```bash
git clone https://github.com/lulin70/OPC-Agents.git
cd OPC-Agents
chmod +x install.sh start.sh
./install.sh
```

### Option 2: Manual Install

```bash
git clone https://github.com/lulin70/OPC-Agents.git
cd OPC-Agents
pip install -r requirements.txt
```

### Configure LLM API (Recommended)

```bash
cp .env.example .env
# Edit .env and add your MOKA API Key:
# MOKA_API_KEY=sk-your-key-here
```

> Works without API Key (template mode), but LLM-enhanced content quality is significantly higher.

### Launch

```bash
./start.sh
# Or manually:
streamlit run frontend/app.py
```

Open http://localhost:8501 in your browser.

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Page shows "template mode" | Check `MOKA_API_KEY` in `.env` file |
| Port in use | `streamlit run frontend/app.py --server.port 8502` |
| Python version issue | Requires Python 3.9+, run `python3 --version` to check |
| Dependency install fails | Try `pip install --upgrade pip` then retry |

## Project Structure

```
OPC-Agents/
├── frontend/              # Streamlit frontend
│   └── app.py             # Main UI (async execution + progress + deliverable management)
├── opc_manager/           # Core business logic
│   ├── task_engine_v3.py  # Task execution engine
│   ├── llm_content.py     # LLM-enhanced content generation (RAG hybrid mode)
│   ├── llm_service.py     # LLM service layer (MOKA/GLM/OpenAI/Ollama)
│   ├── search_processor.py# Search result post-processing (TF-IDF + KB fallback)
│   ├── async_executor.py  # Async task executor
│   ├── session_context.py # Multi-turn dialogue context management
│   ├── validators.py      # Input validation layer (Pydantic models)
│   ├── business_type_detector_v2.py  # Business type detection
│   ├── scenario_engine_v2.py         # Scenario matching engine
│   ├── flywheel_tracker.py           # Growth flywheel tracking
│   ├── persona_manager.py            # Persona management
│   ├── monitoring.py                 # Monitoring & logging
│   ├── config.py                     # Configuration management
│   └── version.py         # Version management (SSOT)
├── tests/                 # Test suite (229 tests, 100% pass)
├── docs/                  # Project documentation
├── requirements.txt       # Core dependencies
├── requirements-dev.txt   # Dev dependencies (black/flake8/pytest)
├── .env.example           # Environment variable template
├── install.sh             # One-click install script
├── start.sh               # One-click launch script
└── VERSION                # Version file
```

## Supported LLM Backends

| Backend | Model | Config Variable | Quality |
|---------|-------|----------------|---------|
| **MOKA (Recommended)** | Claude Sonnet 4 | `MOKA_API_KEY` | ⭐⭐⭐⭐⭐ |
| Zhipu GLM | GLM-4 | `GLM_API_KEY` | ⭐⭐⭐⭐ |
| OpenAI | GPT-4 | `OPENAI_API_KEY` | ⭐⭐⭐⭐ |
| Ollama | Local models | `OLLAMA_BASE_URL` | ⭐⭐⭐ |

Priority: MOKA > GLM > OpenAI > Ollama

## Testing

```bash
pip install -r requirements-dev.txt
PYTHONPATH=. pytest tests/ -v
PYTHONPATH=. pytest tests/ --cov=opc_manager --cov-report=term-missing
```

## Version History

| Version | Date | Milestone |
|---------|------|-----------|
| 0.1.0-beta | 2026-04-25 | Beta release: critical bug fixes, security hardening, CI passing |
| 0.1.0 | 2026-04-23 | "Trustworthy & Usable": version unification, mock removal, MOKA API, async execution |

## License

[MIT License](LICENSE)
