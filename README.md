# OPC-Agents for TRAE

A multi-agent system for One Person Company (OPC), inspired by the popular GitHub project Agency-Agents, integrated with TRAE for enhanced AI capabilities.

## Overview

This project implements a virtual agency with multiple specialized AI agents that can handle various tasks. Each agent is designed with specific expertise and can be assigned tasks through the TRAE API.

## Features

- **Multi-department structure** with 35 specialized departments
- **157+ specialized agents** across different domains (from official Agency-Agents project)
- **TRAE integration** for powerful AI capabilities
- **Task assignment** system for delegating work to specific agents
- **Project management** for coordinating multiple tasks
- **Internal communication** system for agent-to-agent messaging
- **Consensus mechanism** for multi-agent decision making
- **Token usage control** for efficient resource management

## Directory Structure

```
OPC-Agents/
├── config.toml               # Main configuration file
├── opc_manager.py             # Core management script
├── communication_manager.py    # Communication management script
├── opc_skill.py               # TRAE skill implementation
├── official_agents/           # Official agents from Agency-Agents project
├── SKILL.md                   # TRAE skill definition
└── TRAE_SKILL_UPDATE.md       # TRAE skill update guide
```

## Installation

1. **Clone the repository** (or create the directory structure manually)
2. **Install dependencies**:
   ```bash
   pip install requests toml
   ```
3. **Configure TRAE API key** in `config.toml`

## Usage

### Basic Usage

```python
from opc_manager import OPCManager

# Initialize the manager
manager = OPCManager()

# Assign a task to an agent
result = manager.assign_task(
    "Design a modern UI for a task management app",
    "design",
    "UI Designer"
)
print(result)

# Run a project with multiple tasks
project_tasks = [
    {
        "department": "design",
        "agent": "UI Designer",
        "task": "Design a login page for a web application"
    },
    {
        "department": "engineering",
        "agent": "Frontend Developer",
        "task": "Implement the login page using React"
    },
    {
        "department": "marketing",
        "agent": "Digital Marketer",
        "task": "Create a marketing campaign for the new login system"
    }
]

project_results = manager.run_project("Login System Project", project_tasks)
print(project_results)

# Send message between agents
message_result = manager.send_message(
    "UI Designer",
    "Frontend Developer",
    "task_assignment",
    "Please implement the login page according to the design"
)
print(message_result)

# Start consensus process
consensus_result = manager.start_consensus(
    "Technical stack selection for the project",
    ["UI Designer", "Frontend Developer", "Backend Architect"]
)
print(consensus_result)
```

### Command Line Usage

```bash
# View all departments
python opc_skill.py 查看所有部门

# View agents in a department
python opc_skill.py 查看部门 engineering

# Assign a task
python opc_skill.py 安排任务 engineering "Design a database architecture"

# Create a project
python opc_skill.py 创建项目 "Website Development" "design:Design UI" "engineering:Implement backend"

# Send message
python opc_skill.py 发送消息 "UI Designer" "Backend Architect" "task_assignment" "Design database schema"

# Start consensus
python opc_skill.py 启动共识 "Technical选型" "UI Designer" "Backend Architect" "Frontend Developer"

# View token usage
python opc_skill.py 查看Token使用
```

## Available Departments and Agents

### Design Team
- ui_designer
- ux_researcher
- graphic_designer
- motion_designer

### Development Team
- frontend_developer
- backend_developer
- fullstack_developer
- devops_engineer
- qa_engineer

### Marketing Team
- digital_marketer
- content_marketer
- social_media_specialist
- seo_specialist
- email_marketer

### Legal Team
- contract_specialist
- compliance_officer

### HR Team
- recruiter
- onboarding_specialist

### Finance Team
- accountant
- financial_analyst

### Operations Team
- project_coordinator
- process_analyst

### Research Team
- market_researcher
- data_analyst

### Sales Team
- account_executive
- sales_development_rep

### Project Management Team
- project_manager
- scrum_master

### Customer Service Team
- support_specialist
- account_manager

### Content Team
- copywriter
- editor
- content_strategist

## Configuration

The `config.toml` file contains the following sections:

- **core**: Basic agency information
- **trae**: TRAE API configuration
- **agents**: Agent definitions by department

## Integration with TRAE

The system uses the TRAE API to power the agents. Each agent is defined with a specific role and expertise, and tasks are sent to TRAE with appropriate prompts to ensure high-quality responses.

## Extending the System

To add new agents or departments:

1. Update the `config.toml` file to include new agents
2. Create appropriate prompt templates for the new agents
3. Extend the `OPCManager` class if needed
4. Add new communication types in `communication_manager.py` for specialized messaging

## License

MIT License - feel free to use and modify this project as needed.
