# OPC-Agents

A multi-agent system for One Person Company (OPC), inspired by the popular GitHub project Agency-Agents, with enhanced AI capabilities.

## Overview

This project implements a virtual agency with multiple specialized AI agents that can handle various tasks. Each agent is designed with specific expertise and can be assigned tasks through various AI model APIs. The system is enhanced with executive office functionality, three sages decision system, and agent self-optimization capabilities.

## Features

- **Multi-department structure** with 35 specialized departments
- **157+ specialized agents** across different domains (from official Agency-Agents project)
- **Multi-model support** including GLM, OpenAI, Anthropic, Google, Azure, and local models
- **Task assignment** system for delegating work to specific agents (now with actual task dispatching, not just simulation)
- **Project management** for coordinating multiple tasks
- **Internal communication** system for agent-to-agent messaging
- **Consensus mechanism** for multi-agent decision making
- **Token usage control** for efficient resource management
- **Executive Office** (总裁办) for task decomposition, progress tracking, and reporting
- **Three Sages Decision System** (三贤者决策系统) for high-dimensional strategic decision making
- **Agent Self-Optimization** for automatic performance improvement
- **Auto-Optimization Scheduler** for regular automated optimization
- **Web Interface** for easy management and monitoring (with Agent activity status area)
- **Comprehensive reporting** with intelligent insights
- **Task decomposition** into short, medium, and long-term goals
- **Progress tracking** across departments and priorities
- **Resource optimization** for efficient agent utilization
- **A2A (Agent-to-Agent Protocol)** integration for standardized agent communication
- **HR Lifecycle Management** including recruitment, training, and performance evaluation
- **ZeroClaw integration** for enhanced LLM connectivity
- **HR Department Page** showing department and agent lists
- **Actual task dispatching** to department agents with real-time status updates

## Directory Structure

```
OPC-Agents/
├── config.toml               # Main configuration file
├── config.toml.sample        # Configuration file template
├── communication_manager.py    # Communication management script
├── opc_skill.py               # Skill implementation
├── OPCstart.sh                # Startup script for OPC-Agents
├── official_agents/           # Official agents from Agency-Agents project
├── optimization_records/      # Optimization iteration records
├── optimization_notifications/ # Optimization notification files
├── templates/                 # Web interface templates
├── logs/                      # Log files directory
├── temp-use/                  # Temporary directory for old files
├── opc_manager/               # Core management modules
│   ├── __init__.py
│   ├── core.py                # Main OPCManager class
│   ├── log_config.py          # Logging configuration
│   ├── config.py              # Configuration management
│   ├── agent_manager.py       # Agent management
│   ├── task_manager.py        # Task management
│   ├── architecture.py        # System architecture
│   ├── three_sages.py         # Three sages decision system
│   └── personal_assistant.py  # Personal assistant functionality
├── web_interface/             # Web interface modules
│   ├── __init__.py
│   ├── app.py                 # Main Flask application
│   └── routes/                # API routes
│       ├── executive_office.py
│       ├── task_management.py
│       ├── department_management.py
│       ├── personal_assistant.py
│       ├── model_management.py
│       └── auto_optimizer.py
├── opc_hr/                    # HR and A2A related modules
│   ├── a2a_api.py             # REST API endpoints for A2A protocol
│   ├── a2a_integration.py     # A2A protocol integration
│   ├── a2a_protocol.py        # A2A (Agent-to-Agent) Protocol implementation
│   ├── auto_optimizer.py      # Auto-optimization scheduler
│   ├── hr_api.py              # REST API endpoints for HR functionality
│   └── hr_enhancement.py      # HR lifecycle management implementation
├── test_opc_manager.py        # Test script for OPCManager
└── zeroclaw_integration.py    # ZeroClaw integration
```

## Installation

1. **Clone the repository** (or create the directory structure manually)
2. **Install dependencies**:
   ```bash
   pip install requests toml flask
   ```
3. **Configure API keys**:
   - Copy `config.toml.sample` to `config.toml`
   - Update API keys in `config.toml`:
     - GLM API key
     - Other model API keys (OpenAI, Anthropic, Google, Azure) if needed
     - ZeroClaw configuration if using ZeroClaw integration

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

### Executive Office Usage

```python
from opc_manager import OPCManager

manager = OPCManager()

# Decompose task into smaller tasks
decomposed_tasks = manager.decompose_task(
    "帮助企业实施Agent落地项目",
    "medium"  # short, medium, long
)
print("分解的任务:")
for task in decomposed_tasks:
    print(f"- {task['task']} (部门: {task['department']}, 代理: {task['agent']}, 优先级: {task['priority']})")

# Track progress of tasks
progress = manager.track_progress()
print("任务进度:")
print(f"总任务数: {progress['overview']['total_tasks']}")
print(f"平均进度: {progress['overview']['average_progress']:.1f}%")

# Generate report
report = manager.generate_report("weekly")
print("报告生成完成:")
print(f"周期: {report['period']}")
print(f"平均进度: {report['task_summary']['average_progress']:.1f}%")
print("智能洞察:")
for insight in report['insights']:
    print(f"- {insight}")
```

### Three Sages Decision System Usage

```python
from opc_manager import OPCManager

manager = OPCManager()

# Start three sages decision process
decision_result = manager.start_three_sages_decision(
    "是否应该投资开发新的AI代理产品"
)
print("三贤者决策结果:")
print(f"决策: {decision_result['decision']}")
print(f"综合得分: {decision_result['total_score']:.2f}/1.0")
print("贤者意见:")
for sage in decision_result['sages']:
    print(f"- {sage['name']} ({sage['title']}): {sage['opinion'][:100]}...")
```

### Agent Self-Optimization Usage

```python
from opc_manager import OPCManager

manager = OPCManager()

# Optimize all agents
optimization_result = manager.optimize_agents(iterations=2)
print("优化结果:")
print(f"优化的Agent数量: {len(optimization_result['summary']['optimized_agents'])}")
print("改进总结:")
for improvement in optimization_result['summary']['improvements']:
    print(f"- {improvement}")

# Optimize specific agents
specific_optimization = manager.optimize_agents(
    agent_ids=["project_coordinator", "strategy_planner"],
    iterations=1
)
print("特定Agent优化结果:")
print(f"优化的Agent: {specific_optimization['summary']['optimized_agents']}")
```

### Auto-Optimization Scheduler Usage

```python
from opc_hr.auto_optimizer import AutoOptimizer

# Create auto optimizer
auto_optimizer = AutoOptimizer()

# Start scheduler
auto_optimizer.start_scheduler()
print("自动优化调度器已启动")
print(f"下次优化时间: {auto_optimizer.get_next_optimization_time().strftime('%Y-%m-%d %H:%M:%S')}")

# Get optimization statistics
stats = auto_optimizer.get_optimization_statistics()
print("优化统计:")
print(f"总优化次数: {stats['total_optimizations']}")
print(f"平均改进率: {stats['average_improvement_rate']:.2f}")

# Update configuration
new_config = {
    "schedule": {
        "type": "daily",
        "hour": 3,
        "minute": 0
    },
    "optimization": {
        "iterations": 2
    }
}
auto_optimizer.update_config(new_config)
print("配置已更新")

# Manually run optimization
auto_optimizer.run_optimization()
print("手动优化执行完成")
```

### A2A (Agent-to-Agent) Protocol Usage

```python
from opc_hr.a2a_integration import OPCA2AIntegration
from opc_manager import OPCManager

# Initialize OPC Manager
opc_manager = OPCManager()

# Initialize A2A integration
a2a_integration = OPCA2AIntegration(opc_manager)

# Register agents with A2A (automatically done in initialization)
print("Agents registered with A2A protocol")

# Create a workflow (using workflow module)
workflow = a2a_integration.workflow.create_workflow(
    "Website Development Project",
    [
        {"agent": "ui_designer", "task": "Design website UI"},
        {"agent": "frontend_developer", "task": "Implement frontend"},
        {"agent": "backend_developer", "task": "Implement backend"}
    ]
)
print(f"Workflow created: {workflow}")

# Send message between agents using A2A
message_result = a2a_integration.send_a2a_message(
    "ui_designer",
    "frontend_developer",
    "Please implement the UI according to these specifications"
)
print(f"Message sent: {message_result.id}")
```

### HR Lifecycle Management Usage

```python
from opc_hr.hr_enhancement import HREnhancement
from opc_manager import OPCManager

# Initialize OPC Manager
opc_manager = OPCManager()

# Initialize HR enhancement
hr_enhancement = HREnhancement(opc_manager)

# Get all agents
agents = hr_enhancement.get_all_agents()
print(f"Total agents: {len(agents)}")

# Train agents
training_result = hr_enhancement.train_agent(
    agent_id="digital_marketer",
    skills={"content_creation": "high", "analytics": "medium"}
)
print(f"Training result: {training_result}")

# Evaluate agent performance
evaluation_result = hr_enhancement.evaluate_performance(
    agent_id="digital_marketer",
    rating=4.5,
    feedback="Excellent performance in content creation"
)
print(f"Evaluation result: {evaluation_result}")

# Optimize agent performance
optimization_result = hr_enhancement.optimize_agent(
    agent_id="digital_marketer"
)
print(f"Agent optimization completed: {optimization_result['success']}")
```

### Web Interface Usage

#### Using OPCstart.sh (Recommended)

1. **Make the script executable**:
   ```bash
   chmod +x OPCstart.sh
   ```

2. **Run the start script**:
   ```bash
   ./OPCstart.sh
   ```

3. **Follow the prompts**:
   - The script will start ZeroClaw Gateway
   - Wait for the pairing code to be generated
   - Enter the pairing code in `config.toml`
   - The script will start the web server

4. **Access the web interface** at `http://localhost:5007`

#### Manual Start

1. **Start the web server**:
   ```bash
   python -m web_interface.app
   ```

2. **Access the web interface** at `http://localhost:5007`

3. **Features available in the web interface**:
   - Department and agent management
   - Task creation and management
   - Consensus process initiation
   - Executive office functions (task decomposition, progress tracking, reporting)
   - Three sages decision system
   - Agent self-optimization
   - Auto-optimization scheduler configuration
   - Token usage monitoring
   - Optimization statistics and history
   - Agent activity status area (showing which agent is doing what)
   - HR Department page with department and agent lists
   - A2A protocol integration status
   - ZeroClaw integration status

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

### Executive Office Team
- chief_executive_agent
- strategy_planner
- operations_coordinator
- resource_optimizer
- risk_manager
- external_relations_officer
- report_specialist

### Three Sages Team
- astra (阿斯特拉) - 战略贤者
- terra (泰拉) - 执行贤者
- nova (诺娃) - 创新贤者

## Configuration

The `config.toml` file contains the following sections:

- **core**: Basic agency information
- **models**: AI model configurations (GLM, OpenAI, Anthropic, Google, Azure, local)
- **agents**: Agent definitions by department, including executive_office and three_sages

### Example Configuration

```toml
# Core Settings
[core]
name = "OPC Agency"
description = "AI-powered agency system for One Person Company"
version = "1.0.0"

# AI Model Integration
[models]
# Default model to use
default = "glm"

# OpenAI Model
[models.openai]
api_key = "your_openai_api_key"
base_url = "https://api.openai.com/v1/chat/completions"
model = "gpt-4o"

# Anthropic Model
[models.anthropic]
api_key = "your_anthropic_api_key"
base_url = "https://api.anthropic.com/v1/messages"
model = "claude-3-opus-20240229"

# Google Model
[models.google]
api_key = "your_google_api_key"
base_url = "https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent"
model = "gemini-pro"

# Azure OpenAI
[models.azure]
api_key = "your_azure_api_key"
base_url = "https://your-resource-name.openai.azure.com/openai/deployments/your-deployment-name/chat/completions?api-version=2024-02-15-preview"
model = "gpt-4"

# Local Model (e.g., Ollama)
[models.local]
base_url = "http://localhost:11434/api/chat"
model = "llama3"

# GLM Model
[models.glm]
api_key = "your_glm_api_key"
base_url = "https://open.bigmodel.cn/api/messages"
model = "glm-4"

# Agent Configuration
[agents]
# Design Team
design = ["ui_designer", "ux_researcher", "graphic_designer", "motion_designer"]

# Development Team
development = ["frontend_developer", "backend_developer", "fullstack_developer", "devops_engineer", "qa_engineer"]

# Marketing Team
marketing = ["digital_marketer", "content_marketer", "social_media_specialist", "seo_specialist", "email_marketer"]

# Legal Team
legal = ["contract_specialist", "compliance_officer"]

# HR Team
hr = ["recruiter", "onboarding_specialist"]

# Finance Team
finance = ["accountant", "financial_analyst"]

# Operations Team
operations = ["project_coordinator", "process_analyst"]

# Research Team
research = ["market_researcher", "data_analyst"]

# Sales Team
sales = ["account_executive", "sales_development_rep"]

# Project Management Team
project_management = ["project_manager", "scrum_master"]

# Customer Service Team
customer_service = ["support_specialist", "account_manager"]

# Content Team
content = ["copywriter", "editor", "content_strategist"]

# Executive Office Team
[agents.executive_office]
chief_executive_agent = "chief_executive_agent"
strategy_planner = "strategy_planner"
operations_coordinator = "operations_coordinator"
resource_optimizer = "resource_optimizer"
risk_manager = "risk_manager"
external_relations_officer = "external_relations_officer"
report_specialist = "report_specialist"

# Three Sages Team
[agents.three_sages]
astra = "astra"  # 战略贤者
terra = "terra"  # 执行贤者
nova = "nova"  # 创新贤者
```

## Integration with AI Models

The system integrates with multiple AI models through their respective APIs:

- **GLM**: Chinese language optimization (default model)
- **OpenAI**: GPT models for advanced language understanding
- **Anthropic**: Claude models for detailed reasoning
- **Google**: Gemini models for multimodal capabilities
- **Azure OpenAI**: Enterprise-grade AI solutions
- **Local models**: Privacy-focused local deployment

Each agent is defined with a specific role and expertise, and tasks are sent to the appropriate model with tailored prompts to ensure high-quality responses. The system automatically selects the best model based on the task type and context.

## Extending the System

### Adding New Agents or Departments

1. **Update the `config.toml` file** to include new agents in the appropriate department
2. **Create prompt templates** for the new agents with specific expertise and instructions
3. **Extend the `OPCManager` class** if new functionality is needed
4. **Add communication types** in `communication_manager.py` for specialized messaging

### Adding New Features

1. **Executive Office Extensions**: Add new functions in `opc_manager/core.py` under the executive office section
2. **Three Sages Enhancements**: Modify the `three_sages.py` file to add new decision factors
3. **Agent Optimization**: Extend the optimization logic in `opc_hr/auto_optimizer.py`
4. **Web Interface**: Add new API endpoints in the appropriate route files under `web_interface/routes/`
5. **HR Enhancements**: Extend HR functionality in `opc_hr/hr_enhancement.py`
6. **A2A Protocol**: Add new features in `opc_hr/a2a_protocol.py`

### Customization Options

- **Model Selection**: Add new AI models in the `config.toml` file
- **Optimization Parameters**: Adjust optimization settings in the auto_optimizer_config.json file
- **Notification Channels**: Add new notification methods in the auto_optimizer.py file
- **Task Templates**: Create custom task decomposition templates for specific industries

## License

Apache License 2.0 - See [LICENSE](./LICENSE) file for details.

By using this project, you agree to comply with the terms of the Apache 2.0 License. This license allows you to freely use, modify, and distribute this project while providing patent protection.
