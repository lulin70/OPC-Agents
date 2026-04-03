# OPC-Agents

> **You give one instruction to the Executive Office, it mobilizes all 18 specialized departments and 180+ AI employees to collaborate and get it done.**

An AI multi-agent operating system for One Person Company (OPC). You don't call AI tools one by one — just tell the Executive Office what you want like a CEO giving orders. The system automatically breaks down tasks, dispatches the right AI departments, coordinates execution, and reports results back to you.

## How It Works

```
You → Executive Office → Three Sages Decision → HR Resource Assessment → Task Decomposition → AI Departments Collaborate → Results Reported
```

**In one sentence: You are the CEO, the Executive Office is your AI Chief of Staff, and 18 specialized departments are your AI team.**

## Core Capabilities

**Intelligent Scheduling & Decision Making**
- **Executive Office**: 4-mode intent detection (chat/search/task/follow-up), proactive clarification for ambiguous requests
- **Three Sages Decision System**: Strategic/Execution/Innovation perspectives (resources/relationships/risks/strategy/action items)
- **Dynamic Task Decomposition**: Generate execution steps with dependencies/skill requirements/acceptance criteria
- **Intelligent Role Matching**: Three-layer matching (historical performance 30% + skill match 40% + keywords 30%)

**Dual-Layer Context Management**
- **Global Context (Long-term Memory)**: Knowledge base + Experience base + User profile, persistent across tasks
- **Task Context (Working Memory)**: Task definition + Thinking records + Deliverables + Injected references
- **Bidirectional Synchronization**: Inject knowledge at task start, accumulate experience at task completion
- **Self-Improving**: Every task accumulates knowledge and experience for future reuse

**Task Execution & Quality Assurance**
- **Workflow Engine**: State machine with conditional branching, ${variable} templates, pause/resume support
- **DAG Dependency Scheduling**: Manage task dependencies, cycle detection, execute in dependency order
- **TaskScheduler Abstraction**: Unified interface (schedule/cancel/pause/resume)
- **Step Auto-Retry**: Automatic retry on failure (configurable), mark failed only after exhausting retries
- **Loop Controller**: Iteration counter + max iteration limit + exit conditions + progress persistence
- **Context Passing**: Subsequent agents get actual deliverable content from previous agents
- **Auto Validation**: 4 checks (deliverable exists/non-empty/acceptance criteria/GLM quality assessment)
- **Breakpoint Recovery**: Resume from breakpoint after system crash, no progress loss
- **Handover Documents**: Standardized handover between agents

**Multi-Task Concurrent Management** (NEW)
- **Concurrent Task Manager**: Multiple agents execute different tasks simultaneously
- **Priority Scheduling**: 6-level priority (CRITICAL/URGENT/HIGH/MEDIUM/LOW/BACKGROUND)
- **Task Pause/Resume**: Pause and resume tasks at any time
- **Timeout Control**: Prevent tasks from running indefinitely
- **Auto Retry**: Failed tasks automatically retry with exponential backoff
- **Resource Monitoring**: Real-time monitoring of CPU/Memory/Process resources
- **Event Callbacks**: 7 event types (submitted/started/completed/failed/paused/resumed/timeout)
- **Progress Tracking**: Real-time task progress (0-100%) and description updates
- **Task History**: Keep last 100 completed task records

**Event Bus**
- **EventBus**: Decouple module dependencies, publish/subscribe mechanism
- **Task Events**: task_completed/task_failed events, HR module auto-responds

**Configuration Management**
- **Hot Reload**: Monitor config.toml changes, auto-reload without restart
- **Centralized Config**: All hardcoded values extracted as configurable items

**18 specialized departments** covering design, development, marketing, finance, gaming, spatial computing, etc.
**180+ specialized agents** (from Agency-Agents project + A2A protocol)
**Web Search**: DuckDuckGo free search for latest information
**MCP GitHub Integration**: Search/fetch/import external agents and skills (with security audit)
**Multi-model Support**: GLM, OpenAI, Anthropic, Google, Azure, local models
**Finance Department**: Token monitoring, cost reports, budget alerts
**System Monitoring**: CPU/memory/disk, component health, task stats, alerts
**SSE Real-time Push**: Task completion/failure events pushed to frontend in real-time
**Dark Theme**: CSS variables driven, 🌓 one-click switch, localStorage persistence
**Responsive Layout**: 768px/480px breakpoints, sidebar auto-collapse/hide

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
