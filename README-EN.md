# OPC-Agents

A multi-agent system for One Person Company (OPC), inspired by the GitHub project Agency-Agents, with enhanced AI capabilities.

## Overview

A virtual agency with 180+ specialized AI agents across 36 departments. Features include executive office task processing chain, three sages decision system, web search (DuckDuckGo), MCP GitHub integration, and financial monitoring.

## Features

- **36 departments** covering design, development, marketing, finance, operations, etc.
- **180+ specialized agents** (from Agency-Agents + A2A protocol)
- **Multi-model support**: GLM, OpenAI, Anthropic, Google, Azure, local models
- **Executive Office**: chat/search/task three-mode intent detection
- **Three Sages Decision System**: strategic/execution/innovation perspectives
- **Web Search**: DuckDuckGo free search for decision support
- **MCP GitHub Integration**: search/fetch/import external agents and skills
- **Task Management**: create/rename/delete with auto work directory
- **Task Workspaces**: `YYYYMMDD_HHMM_taskname` naming, Finder integration
- **Finance Department**: Token monitoring, cost reports, budget alerts
- **System Monitoring**: CPU/memory/disk, component health, task stats, alerts
- **HR Lifecycle**: recruitment, training, performance evaluation
- **A2A Protocol**: standardized agent-to-agent communication
- **Web Interface**: unified top nav, 5 pages (port 5009)

## Quick Start

```bash
pip3 install requests toml flask ddgs
cp config.toml.sample config.toml  # Edit: add GLM API key
chmod +x OPCstart.sh && ./OPCstart.sh
```

Open **http://localhost:5009**

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/chat/<id>/message` | Executive office chat |
| `POST/GET /api/tasks` | Create/list tasks |
| `PUT /api/tasks/<id>/rename` | Rename task |
| `DELETE /api/tasks/<id>` | Delete task + workspace |
| `GET /api/tasks/<id>/workdir` | Get work directory |
| `POST /api/tasks/<id>/open_workdir` | Open in Finder |
| `GET /api/departments` | Department list |
| `GET /api/agents/` | Agent list |
| `GET /api/finance/dashboard` | Finance dashboard |
| `GET /api/health/` | Health check |
| `GET /api/mcp/web/search?q=xxx` | Web search |
| `GET /api/mcp/agents/search?q=xxx` | GitHub agent search |
| `GET /api/progress/stream` | SSE progress stream |

## Directory Structure

```
OPC-Agents/
├── opc_manager/          # Core manager (system brain)
├── model_integration/    # AI model integration
├── opc_hr/               # HR department (agents/skills/MCP/web search)
├── opc_finance/          # Finance department
├── monitoring/           # System monitoring
├── message_queue/        # Message queue
├── data_storage/         # SQLite storage
├── web_interface/        # Flask web interface (port 5009)
├── templates/            # HTML templates
├── official_agents/      # Official agent profiles
└── task_workspaces/      # Task work directories (auto-created)
```

See [CODE_MAP.md](./CODE_MAP.md) for detailed architecture documentation.

## License

Apache License 2.0
