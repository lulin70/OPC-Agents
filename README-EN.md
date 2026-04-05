# OPC-Agents

> **You give one instruction to the Executive Office, it mobilizes all 18 specialized departments and 180+ AI employees to collaborate and get it done.**

An AI multi-agent operating system for One Person Company (OPC). You don't call AI tools one by one — just tell the Executive Office what you want like a CEO giving orders. The system automatically breaks down tasks, dispatches the right AI departments, coordinates execution, and reports results back to you.

## How It Works

```
You → Executive Office (Intent Detection) → Dual-Layer Context Injection → Three Sages Decision → Dynamic Task Decomposition
→ Intelligent Role Matching → User Confirms Plan → DAG Dependency Scheduling → Agent Collaborative Execution
→ Completion Validation → Experience Accumulation → Results Reported
```

**In one sentence: You are the CEO, the Executive Office is your AI Chief of Staff, 18 specialized departments are your AI team, and the system gets smarter over time.**

## Core Capabilities

**Intelligent Scheduling & Decision Making**
- **Executive Office**: 4-mode intent detection (chat/search/task/follow-up), proactive clarification for ambiguous requests
- **Three Sages Decision System**: Strategic/Execution/Innovation perspectives (resources/relationships/risks/strategy/action items)
- **Dynamic Task Decomposition**: Generate execution steps with dependencies/skill requirements/acceptance criteria
- **Intelligent Role Matching**: Three-layer matching (historical performance 30% + skill match 40% + keywords 30%)

**Dual-Layer Context Management**
- **Global Context (Long-term Memory)**: Knowledge base + Experience base + User profile, persistent across tasks
- **Task Context (Working Memory)**: Task definition + Thinking records + Deliverables + Injected references
- **Bidirectional Synchronization**: Inject knowledge at task start (sync_global_to_task), accumulate experience at task completion (sync_task_to_global)
- **Self-Improving**: Every task accumulates knowledge and experience for future reuse

**Task Execution & Quality Assurance**
- **Workflow Engine**: WorkflowDefinition→Instance→Step state machine with conditional branching, ${variable} templates, pause/resume support
- **DAG Dependency Scheduling**: Manage task dependencies, cycle detection, execute in dependency order
- **TaskScheduler Abstraction**: Unified interface (schedule/cancel/pause/resume)
- **Step Auto-Retry**: Automatic retry on failure (configurable), mark failed only after exhausting retries
- **Loop Controller**: Iteration counter + max iteration limit + exit conditions + progress persistence
- **Context Passing**: Subsequent agents get actual deliverable content from previous agents (not path strings)
- **Auto Validation**: 4 checks (deliverable exists/non-empty/acceptance criteria/GLM quality assessment)
- **Breakpoint Recovery**: Resume from breakpoint after system crash, no progress loss
- **Handover Documents**: Standardized handover between agents (completed work/current status/next steps/notes)

**Intelligent Improvements (Phase 1-3 Completed)**
- **Error Classification & Handling**: 4 error categories (auto-retry/advised-retry/stop/high-risk), 50+ error pattern recognition
- **Notification Grading**: P0-P3 four-level notifications, multi-channel (in-app/email/WeChat), quiet hours support (22:00-08:00)
- **Transparent Scheduling**: Thinking process visualization (like Trae/DeepSeek), HTML/Markdown/JSON output, collapsible display
- **Priority Recommendation**: 3-dimension scoring (deadline 40% + dependency 30% + business value 30%), automatic priority recommendation
- **Resource Optimization**: CPU/Memory/Disk real-time monitoring, health score (0-100), auto-pause low-priority tasks when CPU>95%
- **Task History Enhancement**: Full-text search (name/description/result), auto-archive (>100 tasks or >7 days), JSON/CSV export
- **Scenario Modes**: Simple mode (default, high automation) / Advanced mode (full control), runtime switching

**Multi-Task Concurrent Management**
- **Concurrent Execution**: Different agents execute tasks simultaneously, same agent executes serially (avoid resource conflicts)
- **6-Level Priority**: CRITICAL(10)/URGENT(8)/HIGH(6)/MEDIUM(4)/LOW(2)/BACKGROUND(0)
- **Priority Scheduling**: High priority first, FIFO for same priority, runtime adjustment support
- **Resource Isolation**: Tasks don't affect each other, independent working directories
- **Real-time Monitoring**: CPU/Memory/Disk usage, task progress, agent status (idle/busy/paused/error)

**Event Bus**
- **EventBus**: Decouple module dependencies, support publish/subscribe mechanism
- **Task Events**: task_completed/task_failed events, HR module auto-responds

**Configuration Management**
- **Hot Reload**: Monitor config.toml changes, auto-reload without restart
- **Centralized Config**: All hardcoded values extracted as config items

**18 Specialized Departments**, covering design/development/marketing/finance/operations/games/spatial computing
**180+ Professional AI Employees** (from official Agency-Agents project + A2A protocol)
**Web Search**: DuckDuckGo free search for latest information
**MCP GitHub Integration**: Search/get/import external Agents and Skills (with code security review)
**Multi-Model Support**: GLM, OpenAI, Anthropic, Google, Azure, local models
**Finance Department**: Token monitoring, spending reports, budget alerts
**System Monitoring**: CPU/Memory/Disk, component health, task statistics, alerts
**SSE Real-time Push**: Task completion/failure events pushed to frontend
**Dark Theme**: CSS variables, one-click toggle, localStorage persistence
**Responsive Layout**: 768px/480px breakpoints, sidebar auto-collapse/hide

## Directory Structure

```
OPC-Agents/
├── config.toml.sample        # Configuration template
├── OPCstart.sh               # One-click startup script
├── CODE_MAP.md               # Code map (architecture/modules/API)
├── ARCHITECTURE.md           # System architecture design
├── official_agents/          # Official Agent profiles (JSON)
├── task_workspaces/          # Task working directories (auto-created)
├── templates/                # HTML page templates
├── temp-use/                 # Archived old modules
├── opc_manager/              # Core manager
│   ├── core.py               # OPCManager (system brain)
│   ├── communication_manager.py # Inter-agent communication
│   ├── task_manager.py       # Task management (CRUD/working directories)
│   ├── task_executor.py      # Async task execution
│   ├── agent_manager.py      # Official Agent query
│   ├── three_sages.py        # Three Sages decision
│   ├── context_manager.py    # Dual-layer context
│   ├── completion_checker.py # Task completion validation
│   ├── dag_scheduler.py      # DAG dependency scheduling
│   ├── scheduler.py          # TaskScheduler abstraction
│   ├── event_bus.py          # Event bus
│   ├── checkpoint_manager.py # Breakpoint recovery + handover docs
│   ├── workflow_engine.py    # Workflow engine
│   ├── loop_controller.py    # Long-running task loop controller
│   ├── personal_assistant.py # Personal assistant
│   ├── architecture.py       # Three-layer architecture
│   └── config.py             # Configuration management (hot reload)
├── model_integration/        # AI model integration
│   ├── model_manager.py      # Multi-model management
│   └── model_adapters.py     # GLM/OpenAI/Anthropic/Google adapters
├── opc_hr/                   # HR department
│   ├── hr_enhancement.py     # HR core (Agent management/skill matching)
│   ├── role_matcher.py       # Intelligent role matching
│   ├── skill_manager.py      # Skill management
│   ├── department_manager.py # Department management
│   ├── mcp_integration.py    # MCP GitHub integration
│   ├── installation_manager.py # Installation management
│   ├── web_search.py         # Web search (DuckDuckGo)
│   ├── a2a_api.py            # A2A API
│   ├── a2a_protocol.py       # A2A protocol
│   └── a2a_integration.py    # A2A integration
├── opc_finance/              # Finance department
│   ├── finance_manager.py    # Token monitoring/spending reports/budget alerts
│   └── finance_routes.py     # Finance API routes
├── monitoring/               # System monitoring
│   ├── monitor.py            # Monitor
│   ├── health_check.py       # Health check
│   ├── metrics.py            # Metrics collection
│   └── alerts.py             # Alert management
├── message_queue/            # Message queue
├── data_storage/             # Data storage (SQLite)
├── task_deliverables/        # Task deliverables
├── web_interface/            # Web interface (Flask, port 5009)
│   ├── app.py                # Main application
│   └── routes/               # 11 route modules
└── docs/                     # Documentation
```

## Installation

1. **Clone repository**
2. **Install dependencies**:
   ```bash
   pip3 install requests toml flask ddgs
   ```
3. **Configure API keys**:
   ```bash
   cp config.toml.sample config.toml
   # Edit config.toml, fill in GLM API key (required)
   ```

## Usage

### One-Click Startup

```bash
chmod +x OPCstart.sh
./OPCstart.sh
```

Visit **http://localhost:5009**

### Web Interface Features

| Page | URL | Features |
|------|-----|----------|
| Executive Office | `/` | Chat (chat/search/task), task management, HR recommendations |
| Finance | `/finance` | Spending reports, budget settings, alerts |
| System Monitoring | `/monitoring` | CPU/Memory/Disk, component status, task statistics |
| Agent Management | `/agent_management` | Agent list, create/edit/delete |
| Department Details | `/department/<name>` | Department task list, complete/fail operations |

### Task Management

- **Create**: "New Task" button in top-right of Executive Office page
- **Rename**: Hover task card → ✏️ button (inline edit, Enter to confirm)
- **Delete**: Hover task card → 🗑️ button (delete task + working directory)
- **Open Working Directory**: Hover task card → 📁 button (open in Finder)

### Executive Office Chat Modes

```
User Message → GLM Intent Detection
├── Chat → Direct friendly reply
├── Search → DuckDuckGo search → GLM answers based on search results
└── Task → Search assistance → Three Sages decision → Task decomposition → Dispatch execution
```

## API

| Endpoint | Description |
|----------|-------------|
| `POST /api/chat/<id>/message` | Executive Office chat |
| `POST/GET /api/tasks` | Task creation/list |
| `PUT /api/tasks/<id>/rename` | Rename task |
| `DELETE /api/tasks/<id>` | Delete task |
| `GET /api/tasks/<id>/workdir` | Get working directory |
| `POST /api/tasks/<id>/open_workdir` | Open working directory |
| `GET /api/departments` | Department list |
| `GET /api/agents/` | Agent list |
| `GET /api/finance/dashboard` | Finance dashboard |
| `GET /api/finance/report?period=daily` | Spending report |
| `GET /api/health/` | Health check |
| `GET /api/mcp/web/search?q=xxx` | Web search |
| `GET /api/mcp/agents/search?q=xxx` | GitHub Agent search |
| `GET /api/progress/stream` | SSE real-time progress |

## Configuration

`config.toml` main config items:

```toml
[models.glm]
api_key = "your_glm_api_key"    # Required
model = "glm-4.7"

[mcp]
github_token = ""                # Optional, increases GitHub API rate limit
[finance]
monthly_budget = 100             # Monthly budget (CNY)
```

## Extending the System

### Adding New Agents
1. Add JSON profile in `official_agents/`
2. System auto-loads, no code changes needed

### Adding New Features
1. **Executive Office extension**: `opc_manager/core.py`
2. **New API routes**: Create Blueprint under `web_interface/routes/`
3. **New MCP capabilities**: Create module under `opc_hr/`, integrate in core.py

## Testing

```bash
python3 -m pytest tests/ -v
```

**Test Coverage**:
- Core workflow: 14 tests
- Intelligent improvements: 52 tests (error handling/notification system/priority recommendation, etc.)
- Skill system: 20 tests (web search/document processing/content summarization, etc.)
- Workflow engine: 10 tests
- API regression: 6 tests
- **Total**: 225 tests passed, 4 skipped, 0 failed

## License

Apache License 2.0
