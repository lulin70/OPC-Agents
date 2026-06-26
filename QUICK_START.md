# OPC-Agents Quick Start Guide

## 5 Steps to Get Running

### Step 1: Get an LLM API Key

OPC-Agents requires an LLM backend to function. Choose **one** of the following:

| Provider | Get API Key | Model | Cost |
|----------|------------|-------|------|
| MOKA (Claude) | https://moka-ai.com | claude-sonnet-4 | Pay-per-use |
| Zhipu GLM-4 | https://open.bigmodel.cn | glm-4 | Free tier available |
| OpenAI | https://platform.openai.com | gpt-4o | Pay-per-use |
| Ollama (local) | https://ollama.com | llama3/qwen2 | Free, no API key needed |

### Step 2: Install & Configure

**Option A: Docker (Recommended)**

```bash
# Clone the repo
git clone https://github.com/lulin70/OPC-Agents.git
cd OPC-Agents

# Create config from template
cp .env.example .env

# Edit .env — add your API key (only ONE is needed)
# For MOKA:  uncomment and set MOKA_API_KEY=your-key
# For GLM:   uncomment and set GLM_API_KEY=your-key
# For Ollama: uncomment OLLAMA_ENABLED=true and OLLAMA_BASE_URL=http://localhost:11434
#   (Docker 场景需用 http://host.docker.internal:11434)
nano .env

# Start!
docker compose up -d

# Open in browser
open http://localhost:8501
```

**Option B: Local Python**

```bash
# Clone and enter the repo
git clone https://github.com/lulin70/OPC-Agents.git
cd OPC-Agents

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create config from template
cp .env.example .env

# Edit .env — add your API key
nano .env

# Start!
streamlit run frontend/app.py

# Open in browser
open http://localhost:8501
```

### Step 3: First Task

Once the app loads, type in the chat box:

```
帮我写一封客户跟进邮件
```

Or try any of these:

- `分析一下AI行业趋势` — Market analysis
- `记录一笔收入5000元来自张三` — Finance tracking
- `帮我制定Q2营销方案` — Marketing plan

### Step 4: Explore Features

| Page | What it does |
|------|-------------|
| **Chat** | Main interaction — type tasks, get results |
| **Deliverables** | View and export generated documents |
| **Dashboard** | Business metrics and analytics |
| **Growth** | Flywheel scoring and improvement suggestions |
| **Marketplace** | Browse and install additional skills |
| **Settings** | API keys, language, theme configuration |

### Step 5: Secure Your Setup

- **API Keys**: Go to Settings → store keys in encrypted storage (never in .env plaintext)
- **Language**: Settings → switch between Chinese / English / Japanese
- **Backup**: Data is stored in `data/` — back it up regularly
- **MCP**: If using MCP integration, set `MCP_API_KEY` in .env

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No LLM provider available" | Set at least one API key in .env |
| Connection timeout | Check network, try `OLLAMA_BASE_URL=http://localhost:11434` (Docker 场景用 `host.docker.internal:11434`) |
| Port 8501 already in use | Change port: `streamlit run frontend/app.py --server.port 8502` |
| Data not persisting (Docker) | Verify `opc-data` volume exists: `docker volume ls` |

## Architecture

```
User Input
    │
    ▼
AgentLoop (lightweight coordinator, ~460 lines)
    │
    ▼
IntentRouter.classify_route(user_input)
    ├─► GREETING  ──────────────────────────────► 模板响应（0 LLM 成本）
    ├─► SIMPLE    ──────────────────────────────► 单步快速执行
    └─► COMPLEX   ──────────────────────────────► 三贤者并行投票（1×RTT）
                                                        │
        ┌───────────────────────────────────────────────┼───────────────────────────────────────────────┐
        ▼                                               ▼                                               ▼
StrategistBrain (Plan)                        ExecutorBrain (Act)                          ReflectorBrain (predict)
express_opinion()                             express_opinion()                            predict_consequence()
        │                                               │                                               │
        └───────────────────────────────────────────────┼───────────────────────────────────────────────┘
                                                        ▼
                                              ConsensusEngine.collect_opinions_async()
                                                        │
                    ┌───────────────────────────────────┴───────────────────────────────────┐
                    ▼                                       ▼                                 ▼
              approved=True                            approved=False                  timeout / error
                    │                                       │                                 │
                    ▼                                       ▼                                 ▼
            SkillRegistry.execute_skill()         返回替代方案 / 跳过步骤             fail-close 跳过步骤
                    │
                    ▼
                 Result
```

AgentLoop delegates to 5 dedicated components (StateManager, AgentErrorHandler,
ProgressTracker, ResultBuilder, TaskOrchestrator). Shared constants live in
`constants.py` and shared helpers in `agent_utils.py` (eliminates the previous
circular dependency).

### Key Design Points

- **Parallel Sages**: StrategistBrain, ExecutorBrain, and ReflectorBrain vote in parallel via `asyncio.gather`-style scheduling, reducing latency from 3×RTT (serial) to 1×RTT (worst case).
- **Three-Way Routing**: `IntentRouter` classifies input into `GREETING`, `SIMPLE`, or `COMPLEX`; simple tasks bypass the sage system to save cost and latency.
- **Consensus Gate**: Critical skills (`email`, `report`, `finance`) must pass a pre-execution consensus vote. On timeout or exception, the gate **fails closed** — the step is skipped rather than executed.
- **Skill Freeze**: 9 non-core skills are fully frozen in v0.3.0 (see `docs/spec/SKILL_FREEZE_LIST.md`).

## Support

- GitHub Issues: https://github.com/lulin70/OPC-Agents/issues
- Docs: See `docs/` directory
