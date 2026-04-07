# OPC-Agents

**Version**: 0.0.1

> **Give one command to the President's Office, and it mobilizes 18 professional departments and 180+ AI employees across the company to complete the task.**

An AI multi-agent operating system designed for One-Person Companies (OPC). You don't need to call AI tools one by one—just tell the President's Office what you want to do like giving instructions to a CEO, and the system will automatically decompose tasks, schedule suitable AI departments, coordinate completion, and report results back to you.

## How It Works

```
User → President's Office (Intent Detection) → Dual-Layer Context Injection → Three Sages Structured Decision → Dynamic Task Decomposition
→ Intelligent Role Matching → User Plan Confirmation → DAG Dependency Scheduling → Agent Collaborative Execution (Context Passing)
→ Completion Verification → Experience Learning → Result Reporting
```

**In one sentence: You are the CEO, the President's Office is your AI Chief of Staff, and 18 professional departments are your AI team. The system gets smarter the more you use it.**

## Core Capabilities

**Intelligent Scheduling & Decision Making**
- **President's Office Scheduling**: 4 intent types (chat/search/task/follow-up), proactively asks for clarification on ambiguous requirements
- **Three Sages Decision System**: Strategic/Executive/Innovation three-perspective structured assessment (resources/relationships/risks/strategy/action items), decoupled as independent module
- **Dynamic Task Decomposition**: Dynamically generates execution steps based on Three Sages assessment (with dependencies/skill requirements/acceptance criteria)
- **Intelligent Role Matching**: Three-layer matching strategy (historical performance 30% + skill matching 40% + keywords 30%), automatically finds the best Agent

**Dual-Layer Context Management** (referencing TraeMultiAgentSkill + Memory Classification Engine, integrated into main workflow)
- **Global Context (Long-term Memory)**: Knowledge base + Experience base (6 types) + User profile, cross-task persistence
- **Task Context (Working Memory)**: Task definition + Thinking records + Outputs + Injection references
- **Bidirectional Sync**: Inject relevant knowledge at task start (sync_global_to_task), learn experience at task completion (sync_task_to_global)
- **Experience Classification**: 6 types (user_preference/correction/decision/task_pattern/agent_optimization/skill_usage)
- **Weight Calculation**: 4 dimensions (confidence 40% + timeliness 30% + usage frequency 20% + source reliability 10%)
- **Conflict Detection**: Automatically identifies contradictory experiences, intelligent handling (weight comparison/mark as outdated/pending user confirmation)
- **Forgetting Mechanism**: Based on time decay + usage frequency, low-weight experiences automatically phase out
- **Gets Smarter**: Every task accumulates knowledge and experience, subsequent tasks automatically reuse high-value experiences

**Task Execution & Quality Assurance**
- **Workflow Engine**: WorkflowDefinition→Instance→Step state machine, supports conditional branches, ${variable} templates, pause/resume
- **DAG Dependency Scheduling**: Task dependency management, cycle detection, execution in dependency order
- **TaskScheduler Abstraction**: Unified scheduling interface (schedule/cancel/pause/resume), supports multiple scheduling strategies
- **Step Auto-Retry**: Automatic retry on failure (configurable), marked failed only after retry exhaustion
- **Loop Controller**: Iteration counter + max iteration limit + exit condition + progress persistence
- **Context Passing**: Subsequent Agents get actual deliverable content from previous Agents (not path strings)
- **Completion Auto-Check**: Deliverable existence/non-empty/acceptance criteria/GLM quality assessment, 4 checks
- **Breakpoint Recovery**: Can resume from breakpoint after system crash, no progress loss
- **Handoff Documentation**: Standardized handoff between Agents (completed work/current state/next steps/notes)

**Intelligent Improvements (Phase 1-3 Completed)**
- **Error Classification & Handling**: 4 error types (auto-retry/recommend retry/stop/high-risk), 50+ error pattern recognition
- **Notification Grading System**: P0-P3 four levels, multi-channel (in-app/email/WeChat), do-not-disturb hours (22:00-08:00)
- **Scheduling Transparency**: Thinking process visualization (like Trae/DeepSeek), HTML/Markdown/JSON output, collapsible display
- **Priority Intelligent Recommendation**: 3-dimension scoring (deadline 40% + dependencies 30% + business value 30%), automatic priority recommendation
- **Resource Optimization Suggestions**: Real-time CPU/memory/disk monitoring, health score (0-100), auto-pause low-priority tasks when CPU>95%
- **Task History Enhancement**: Full-text search (task name/description/result), automatic archiving (>100 tasks or >7 days), JSON/CSV export
- **Scenario-based Modes**: Simple mode (default, high automation) / Advanced mode (full control), runtime switching

**Multi-Task Concurrent Management**
- **Concurrent Execution**: Different Agents can execute tasks simultaneously, same Agent executes serially (avoid resource conflicts)
- **6 Priority Levels**: CRITICAL(10)/URGENT(8)/HIGH(6)/MEDIUM(4)/LOW(2)/BACKGROUND(0)
- **Priority Scheduling**: High priority first, same priority by submission time (FIFO), supports runtime adjustment
- **Resource Isolation**: Tasks don't affect each other, independent working directories
- **Real-time Monitoring**: CPU/memory/disk usage, task progress, Agent status (idle/busy/paused/error)

**Conversation & Notification System (Phase 1 New)**
- **Conversation Management**: Independent conversation center, supports multi-conversation switching, history search, task card embedding
- **Message Types**: Text/Task card/Plan confirmation/Search results/Chart visualization
- **Notification Center**: Global notification bell, 5 types (task/confirmation/system/finance/hr), 4 priority levels
- **Real-time Push**: SSE/WebSocket dual mode, browser desktop notifications, do-not-disturb hours
- **Conversation-Task Integration**: Display task progress in conversation, click card to view details, status real-time sync

**Event Bus**
- **EventBus**: Decouples module dependencies, supports publish/subscribe mechanism
- **Task Events**: task_completed/task_failed events, HR module automatically responds

**Configuration Management**
- **Hot Configuration Updates**: Monitors config.toml changes, automatically reloads configuration, no service restart required
- **Centralized Configuration**: All hardcoded values extracted as configuration items, easy to tune

**18 Professional Departments**, covering design/development/marketing/finance/operations/game/spatial computing and more
**180+ Professional AI Employees** (from official Agency-Agents project + A2A protocol)
**Web Search**: DuckDuckGo free search, get latest information to assist decision-making
**MCP GitHub Integration**: Search/get/import external Agents and Skills (with code security review)
**Multi-Model Support**: GLM, OpenAI, Anthropic, Google, Azure, local models
**Finance Department**: Token monitoring, spending reports, budget alerts
**System Monitoring**: CPU/memory/disk, component health, task statistics, alarms
**SSE Real-time Push**: Task completion/failure events pushed to frontend in real-time
**Dark Theme**: CSS variables driven, 🌓 one-click switch, localStorage persistence
**Responsive Layout**: 768px/480px breakpoints, sidebar auto-collapse/hide

## Directory Structure

```
OPC-Agents/
├── config.toml.sample        # Configuration template
├── OPCstart.sh               # One-click startup script
├── CODE_MAP.md               # Code map (architecture/modules/API)
├── ARCHITECTURE.md           # System architecture design
├── official_agents/          # Official Agent profiles (JSON definitions)
├── task_workspaces/          # Task working directories (auto-created)
├── templates/                # HTML page templates
├── temp-use/                 # Archived old modules
├── opc_manager/              # Core managers
│   ├── core.py               # OPCManager (system brain)
│   ├── communication_manager.py # Inter-agent communication
│   ├── task_manager.py       # Task management (CRUD/working directories)
│   ├── task_executor.py      # Async task execution
│   ├── agent_manager.py      # Official Agent query
│   ├── three_sages.py        # Three Sages decision
│   ├── context_manager.py    # Dual-layer context (knowledge + experience + user profile)
│   ├── completion_checker.py # Task completion auto-check
│   ├── dag_scheduler.py      # DAG dependency scheduling
│   ├── scheduler.py          # TaskScheduler abstraction
│   ├── event_bus.py          # Event bus
│   ├── checkpoint_manager.py # Breakpoint recovery + handoff docs
│   ├── workflow_engine.py    # Workflow engine (state machine + conditional branches + variable templates)
│   ├── loop_controller.py    # Long-running task loop controller
│   ├── personal_assistant.py # Personal assistant
│   ├── architecture.py       # Three-layer architecture
│   ├── config.py             # Configuration management (hot updates)
│   ├── conversation_manager.py # Conversation management (Phase 1 new)
│   └── notification_manager.py # Notification management (Phase 1 new)
├── model_integration/        # AI model integration
│   ├── model_manager.py      # Multi-model management
│   └── model_adapters.py     # GLM/OpenAI/Anthropic/Google adapters
├── opc_hr/                   # HR Department
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
├── opc_finance/              # Finance Department
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
    ├── README.md             # Documentation navigation
    ├── system_design.md      # System design doc (conversation/notification/architecture)
    ├── ui_enhancement_plan.md # UI enhancement plan
    ├── product_review_meeting.md # Product review minutes
    ├── phase1_implementation_plan.md # Phase 1 implementation plan
    └── ...                   # Other docs
```

## Installation

### Method 1: One-Click Installation (Recommended)

```bash
# 1. Clone repository
git clone https://github.com/your-org/OPC-Agents.git
cd OPC-Agents

# 2. Run one-click install script
chmod +x install.sh
./install.sh

# 3. Configure API keys
vim config.toml

# 4. Start service
./OPCstart.sh
```

**Detailed Installation Guide**: [INSTALL.md](INSTALL.md)

---

### Method 2: Manual Installation

```bash
# 1. Install dependencies
pip3 install requests toml flask ddgs

# 2. Create configuration
cp config.toml.sample config.toml

# 3. Configure API keys (required)
vim config.toml

# 4. Start service
python3 web_interface/app.py
```

---

### Configure API Keys (Required)

**Configure at least one model**, Zhipu AI GLM recommended (available in China):

```toml
[models.glm]
api_key = "sk.xxxxxxxxxxxxxxxxxxxxxxxx"  # ← Replace with your key
model = "glm-4.7"
```

**Get GLM API Key**:
1. Visit https://open.bigmodel.cn/
2. Register/Login
3. Go to Console → API Key Management
4. Create API key
5. Copy key to configuration file

**More Configuration Options**: [INSTALL.md](INSTALL.md#configuration-details)

## Usage

### One-Click Startup

```bash
chmod +x OPCstart.sh
./OPCstart.sh
```

Access **http://localhost:5009**

### Web Interface Features

| Page | URL | Features |
|------|-----|----------|
| President's Office | `/` | Conversation (chat/search/task), task management, HR recommendations |
| Finance | `/finance` | Spending reports, budget settings, alerts |
| System Monitoring | `/monitoring` | CPU/memory/disk, component status, task statistics |
| Agent Management | `/agent_management` | Agent list, create/edit/delete |
| Department Details | `/department/<name>` | Department task list, complete/fail operations |

### Task Management

- **Create**: "New Task" button in top right of President's Office page
- **Rename**: Hover task card → ✏️ button (inline edit, Enter to confirm)
- **Delete**: Hover task card → 🗑️ button (delete task + working directory)
- **Open Working Directory**: Hover task card → 📁 button (open in Finder)

### President's Office Conversation Modes

```
User Message → GLM Intent Detection
├── Chat → Direct friendly reply
├── Search → DuckDuckGo search → GLM answers based on search results
└── Task → Search assistance → Three Sages decision → Task decomposition → Dispatch execution
```

## API

| Endpoint | Description |
|----------|-------------|
| `POST /api/chat/<id>/message` | President's Office conversation |
| `POST/GET /api/tasks` | Task create/list |
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

`config.toml` main configuration items:

```toml
[models.glm]
api_key = "your_glm_api_key"    # Required
model = "glm-4.7"

[mcp]
github_token = ""                # Optional, increase GitHub API rate

[finance]
monthly_budget = 100             # Monthly budget (CNY)
```

## Extending the System

### Add New Agent
1. Add JSON profile in `official_agents/`
2. System auto-loads, no code changes needed

### Add New Features
1. **President's Office Extension**: `opc_manager/core.py`
2. **New API Routes**: Create Blueprint under `web_interface/routes/`
3. **New MCP Capabilities**: Create module under `opc_hr/`, integrate in core.py

## Testing

```bash
python3 -m pytest tests/ -v
```

**Test Coverage**:
- **Core Workflow**: 12 integration tests (100% pass)
- **Conversation & Notification**: 14 unit tests (ConversationManager/NotificationManager)
- **Intelligent Improvements**: 52 tests (error handling/notification system/priority recommendation, etc.)
- **Skill System**: 20 tests (web search/document processing/content summarization, etc.)
- **Workflow Engine**: 10 tests
- **API Regression**: 6 tests
- **Total**: 253 tests passed, 4 skipped, 0 failed

**Test Reports**: `reports/test_report_summary.md`

## License

Apache License 2.0
