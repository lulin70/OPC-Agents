# 🚀 OPC-Agents — Intelligent Task Execution for One-Person Companies

> **Version**: v0.1.0 | **Status**: Usable | **License**: MIT

---

## What Is This

OPC-Agents (One-Person Company Agents) is an **intelligent task execution system for solo entrepreneurs, freelancers, and independent creators**.

**Core idea: Tell the system what result you want, and it delivers a file to you.**

Not a chatbot. Not an advice engine. A **doer**.

## What It Can Do

| You Say | It Delivers |
|---------|-------------|
| "Research OPC company trends" | 🔍 **Research report** (real search results + sources + structured summary) |
| "Write a Q2 marketing plan" | ✍️ **Complete plan** (SMART goals + roadmap + risks + acceptance criteria) |
| "Analyze competitor A" | 📊 **Analysis report** (SWOT + action items + priority ranking) |
| "Create a product launch plan" | 🚀 **Launch plan** (pricing strategy + channels + timeline) |

### Key Features

- ✅ **LLM-Enhanced Content** — Powered by Claude Sonnet 4, 96% quality pass rate
- ✅ **Real Web Search** — DuckDuckGo live search, no fabricated data
- ✅ **Zero Placeholder Guarantee** — Every output has concrete, actionable content
- ✅ **Async Execution** — Instant submit, background processing, 5-stage progress
- ✅ **Knowledge Base Fallback** — 6 categories, 20 entries, auto-fallback when search fails
- ✅ **File Delivery** — Auto-generates `.md` files with download buttons
- ✅ **Multi-turn Dialogue** — Context-aware iterative refinement

## Quick Start

### Prerequisites

- Python 3.9+
- pip

### Install

```bash
git clone https://github.com/your-username/OPC-Agents.git
cd OPC-Agents
pip install -r requirements.txt
```

### Configure LLM API (Recommended)

```bash
cp .env.example .env
# Edit .env and add your MOKA API Key:
# MOKA_API_KEY=sk-your-key-here
```

> Works without an API Key (template mode), but LLM-enhanced content is significantly better.

### Run

```bash
streamlit run frontend/app.py
```

Open http://localhost:8501 in your browser.

## Project Structure

```
OPC-Agents/
├── frontend/              # Streamlit frontend
│   └── app.py             # Main UI (async execution + progress + deliverables)
├── opc_manager/           # Core business logic
│   ├── task_engine_v3.py  # Task execution engine
│   ├── llm_content.py     # LLM-enhanced content generation (RAG hybrid)
│   ├── llm_service.py     # LLM service layer (MOKA/GLM/OpenAI/Ollama)
│   ├── search_processor.py# Search result post-processing (TF-IDF + KB fallback)
│   ├── async_executor.py  # Async task executor
│   ├── session_context.py # Multi-turn dialogue context manager
│   └── version.py         # Version number (SSOT)
├── opc_hr/                # HR/search module
│   └── web_search.py      # DuckDuckGo search wrapper
├── tests/                 # Test suite (174 tests)
├── docs/                  # Documentation
│   ├── architect/         # Architecture design
│   ├── product-manager/   # Product requirements
│   ├── solo-coder/        # Roadmap
│   ├── test-expert/       # Test plan
│   ├── user_guides/       # User guides
│   └── reviews/           # Review records
├── requirements.txt       # Core dependencies
├── requirements-dev.txt   # Dev dependencies
├── .env.example           # Environment variable template
└── VERSION                # Version number
```

## Supported LLM Backends

| Backend | Model | Env Variable | Quality |
|---------|-------|-------------|---------|
| **MOKA (Recommended)** | Claude Sonnet 4 | `MOKA_API_KEY` | ⭐⭐⭐⭐⭐ |
| Zhipu GLM | GLM-4 | `GLM_API_KEY` | ⭐⭐⭐⭐ |
| OpenAI | GPT-4 | `OPENAI_API_KEY` | ⭐⭐⭐⭐ |
| Ollama | Local models | `OLLAMA_BASE_URL` | ⭐⭐⭐ |

Priority: MOKA > GLM > OpenAI > Ollama

## Testing

```bash
# Run all tests
pip install -r requirements-dev.txt
pytest tests/ -v

# Run LLM E2E gate (requires API Key)
MOKA_API_KEY=sk-xxx python tests/gate_llm_real_e2e.py --quick

# Run frontend E2E gate
pytest tests/gate_e2e_frontend.py -v
```

## Version History

| Version | Date | Milestone |
|---------|------|-----------|
| 0.1.0 | 2026-04-23 | "Trustworthy & Usable": Version unification, Mock removal, MOKA API, async execution, simplified UI |
| — | 2026-04-22 | v3.6: Real LLM E2E validation passed (96% quality), async frontend, KB expansion |
| — | 2026-04-20 | v3.5: Four-role consensus, 4 P0 components (SearchProcessor/LLMContent/AsyncExecutor/SessionContext) |

## Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT License](LICENSE)
