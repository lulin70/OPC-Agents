# OPC-Agents for TRAE

一个为一人公司 (OPC) 设计的多代理系统，灵感来自流行的 GitHub 项目 Agency-Agents，与 TRAE 集成以增强 AI 能力。

## 概述

本项目实现了一个虚拟代理机构，包含多个专业 AI 代理，可以处理各种任务。每个代理都设计有特定的专业知识，可以通过 TRAE API 分配任务。系统增强了总裁办功能、三贤者决策系统和代理自我优化能力。

## 功能

- **多部门结构**，包含 35 个专业部门
- **157+ 专业代理**，涵盖不同领域（来自官方 Agency-Agents 项目）
- **TRAE 集成**，提供强大的 AI 能力
- **多模型支持**，包括 TRAE、OpenAI、Anthropic、Google、Azure、GLM 和本地模型
- **任务分配系统**，用于将工作委派给特定代理（现在支持实际任务分派，而不仅仅是模拟）
- **项目管理**，用于协调多个任务
- **内部通信系统**，用于代理间消息传递
- **共识机制**，用于多代理决策
- **Token 使用控制**，用于高效资源管理
- **总裁办**，用于任务分解、进度跟踪和报告
- **三贤者决策系统**，用于高维度战略决策
- **代理自我优化**，用于自动性能改进
- **自动优化调度器**，用于定期自动优化
- **Web 界面**，用于轻松管理和监控（带有代理活动状态区域）
- **综合报告**，带有智能洞察
- **任务分解**，分为短期、中期和长期目标
- **进度跟踪**，跨部门和优先级
- **资源优化**，用于高效代理利用
- **A2A（代理到代理协议）** 集成，用于标准化代理通信
- **HR 生命周期管理**，包括招聘、培训和绩效评估
- **ZeroClaw 集成**，用于增强 LLM 连接
- **HR 部门页面**，显示部门和代理列表
- **实际任务分派**，实时状态更新

## 目录结构

```
OPC-Agents/
├── config.toml               # 主要配置文件
├── config.toml.sample        # 配置文件模板
├── opc_manager.py             # 核心管理脚本
├── communication_manager.py    # 通信管理脚本
├── web_interface.py           # Web 界面实现
├── auto_optimizer.py          # 自动优化调度器
├── opc_skill.py               # TRAE 技能实现
├── a2a_protocol.py            # A2A（代理到代理）协议实现
├── a2a_integration.py         # A2A 协议与 OPC-Agents 集成
├── a2a_api.py                 # A2A 协议的 REST API 端点
├── hr_enhancement.py          # HR 生命周期管理实现
├── hr_api.py                  # HR 功能的 REST API 端点
├── OPCstart.sh                # OPC-Agents 启动脚本
├── official_agents/           # 来自 Agency-Agents 项目的官方代理
├── optimization_records/      # 优化迭代记录
├── optimization_notifications/ # 优化通知文件
├── project_management/        # 项目管理文档
│   ├── 需求范围承诺书模板.md   # 需求范围承诺书模板
│   ├── 项目管理规范.md         # 项目管理规范
│   ├── 迭代计划/             # 迭代计划和回顾
│   └── 需求文档/             # 已批准的需求文档
├── templates/                 # Web 界面模板
├── SKILL.md                   # TRAE 技能定义
├── TRAE_SKILL_UPDATE.md       # TRAE 技能更新指南
├── test_enhanced_features.py  # 增强功能测试脚本
├── test_agent_optimization.py # 代理优化测试脚本
└── test_auto_optimizer.py     # 自动优化器测试脚本
```

## 安装

1. **克隆仓库**（或手动创建目录结构）
2. **安装依赖**：
   ```bash
   pip install requests toml flask
   ```
3. **配置 API 密钥**：
   - 将 `config.toml.sample` 复制为 `config.toml`
   - 在 `config.toml` 中更新 API 密钥：
     - TRAE API 密钥
     - 其他模型 API 密钥（OpenAI、Anthropic、Google、Azure、GLM）（如果需要）
     - ZeroClaw 配置（如果使用 ZeroClaw 集成）

## 使用

### 基本使用

```python
from opc_manager import OPCManager

# 初始化管理器
manager = OPCManager()

# 向代理分配任务
result = manager.assign_task(
    "设计一个现代的任务管理应用 UI",
    "design",
    "UI Designer"
)
print(result)

# 运行包含多个任务的项目
project_tasks = [
    {
        "department": "design",
        "agent": "UI Designer",
        "task": "为 Web 应用设计登录页面"
    },
    {
        "department": "engineering",
        "agent": "Frontend Developer",
        "task": "使用 React 实现登录页面"
    },
    {
        "department": "marketing",
        "agent": "Digital Marketer",
        "task": "为新的登录系统创建营销活动"
    }
]

project_results = manager.run_project("登录系统项目", project_tasks)
print(project_results)

# 在代理之间发送消息
message_result = manager.send_message(
    "UI Designer",
    "Frontend Developer",
    "task_assignment",
    "请根据设计实现登录页面"
)
print(message_result)

# 启动共识过程
consensus_result = manager.start_consensus(
    "项目技术栈选择",
    ["UI Designer", "Frontend Developer", "Backend Architect"]
)
print(consensus_result)
```

### 总裁办使用

```python
from opc_manager import OPCManager

manager = OPCManager()

# 将任务分解为更小的任务
decomposed_tasks = manager.decompose_task(
    "帮助企业实施Agent落地项目",
    "medium"  # short, medium, long
)
print("分解的任务:")
for task in decomposed_tasks:
    print(f"- {task['task']} (部门: {task['department']}, 代理: {task['agent']}, 优先级: {task['priority']})")

# 跟踪任务进度
progress = manager.track_progress()
print("任务进度:")
print(f"总任务数: {progress['overview']['total_tasks']}")
print(f"平均进度: {progress['overview']['average_progress']:.1f}%")

# 生成报告
report = manager.generate_report("weekly")
print("报告生成完成:")
print(f"周期: {report['period']}")
print(f"平均进度: {report['task_summary']['average_progress']:.1f}%")
print("智能洞察:")
for insight in report['insights']:
    print(f"- {insight}")
```

### 三贤者决策系统使用

```python
from opc_manager import OPCManager

manager = OPCManager()

# 启动三贤者决策过程
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

### 代理自我优化使用

```python
from opc_manager import OPCManager

manager = OPCManager()

# 优化所有代理
optimization_result = manager.optimize_agents(iterations=2)
print("优化结果:")
print(f"优化的Agent数量: {len(optimization_result['summary']['optimized_agents'])}")
print("改进总结:")
for improvement in optimization_result['summary']['improvements']:
    print(f"- {improvement}")

# 优化特定代理
specific_optimization = manager.optimize_agents(
    agent_ids=["project_coordinator", "strategy_planner"],
    iterations=1
)
print("特定Agent优化结果:")
print(f"优化的Agent: {specific_optimization['summary']['optimized_agents']}")
```

### 自动优化调度器使用

```python
from auto_optimizer import AutoOptimizer

# 创建自动优化器
auto_optimizer = AutoOptimizer()

# 启动调度器
auto_optimizer.start_scheduler()
print("自动优化调度器已启动")
print(f"下次优化时间: {auto_optimizer.get_next_optimization_time().strftime('%Y-%m-%d %H:%M:%S')}")

# 获取优化统计
stats = auto_optimizer.get_optimization_statistics()
print("优化统计:")
print(f"总优化次数: {stats['total_optimizations']}")
print(f"平均改进率: {stats['average_improvement_rate']:.2f}")

# 更新配置
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

# 手动运行优化
auto_optimizer.run_optimization()
print("手动优化执行完成")
```

### A2A（代理到代理）协议使用

```python
from a2a_integration import A2AIntegration

# 初始化 A2A 集成
a2a_integration = A2AIntegration()

# 注册代理到 A2A
a2a_integration.register_agents()
print("Agents registered with A2A protocol")

# 创建工作流
workflow = a2a_integration.create_workflow(
    "Website Development Project",
    [
        {"agent": "ui_designer", "task": "Design website UI"},
        {"agent": "frontend_developer", "task": "Implement frontend"},
        {"agent": "backend_developer", "task": "Implement backend"}
    ]
)
print(f"Workflow created: {workflow['id']}")

# 使用 A2A 在代理之间发送消息
message_result = a2a_integration.send_message(
    "ui_designer",
    "frontend_developer",
    "design_specs",
    "Please implement the UI according to these specifications"
)
print(f"Message sent: {message_result['id']}")
```

### HR 生命周期管理使用

```python
from hr_enhancement import HRLifecycleManager

# 初始化 HR 管理器
hr_manager = HRLifecycleManager()

# 招聘新代理
recruitment_result = hr_manager.recruit_agents(
    department="marketing",
    skills=["digital_marketing", "social_media"],
    count=2
)
print(f"Recruited {len(recruitment_result['agents'])} new agents")

# 培训代理
training_result = hr_manager.train_agents(
    agent_ids=["digital_marketer", "social_media_specialist"],
    skills=["content_creation", "analytics"]
)
print(f"Training completed for {len(training_result['trained_agents'])} agents")

# 评估代理绩效
evaluation_result = hr_manager.evaluate_performance(
    agent_id="digital_marketer",
    period="monthly"
)
print(f"Agent performance score: {evaluation_result['score']}")

# 优化代理绩效
optimization_result = hr_manager.optimize_agent(
    agent_id="digital_marketer"
)
print(f"Agent optimization completed: {optimization_result['status']}")
```

### Web 界面使用

#### 使用 OPCstart.sh（推荐）

1. **使脚本可执行**：
   ```bash
   chmod +x OPCstart.sh
   ```

2. **运行启动脚本**：
   ```bash
   ./OPCstart.sh
   ```

3. **按照提示操作**：
   - 脚本将启动 ZeroClaw Gateway
   - 等待配对代码生成
   - 在 `config.toml` 中输入配对代码
   - 脚本将启动 Web 服务器

4. **访问 Web 界面**：`http://localhost:5007`

#### 手动启动

1. **启动 Web 服务器**：
   ```bash
   python web_interface.py
   ```

2. **访问 Web 界面**：`http://localhost:5007`

3. **Web 界面可用功能**：
   - 部门和代理管理
   - 任务创建和管理
   - 共识过程启动
   - 总裁办功能（任务分解、进度跟踪、报告）
   - 三贤者决策系统
   - 代理自我优化
   - 自动优化调度器配置
   - Token 使用监控
   - 优化统计和历史
   - 代理活动状态区域（显示哪个代理在做什么）
   - HR 部门页面，显示部门和代理列表
   - A2A 协议集成状态
   - ZeroClaw 集成状态

### 命令行使用

```bash
# 查看所有部门
python opc_skill.py 查看所有部门

# 查看部门中的代理
python opc_skill.py 查看部门 engineering

# 分配任务
python opc_skill.py 安排任务 engineering "Design a database architecture"

# 创建项目
python opc_skill.py 创建项目 "Website Development" "design:Design UI" "engineering:Implement backend"

# 发送消息
python opc_skill.py 发送消息 "UI Designer" "Backend Architect" "task_assignment" "Design database schema"

# 启动共识
python opc_skill.py 启动共识 "Technical选型" "UI Designer" "Backend Architect" "Frontend Developer"

# 查看 Token 使用
python opc_skill.py 查看Token使用
```

## 可用部门和代理

### 设计团队
- ui_designer
- ux_researcher
- graphic_designer
- motion_designer

### 开发团队
- frontend_developer
- backend_developer
- fullstack_developer
- devops_engineer
- qa_engineer

### 营销团队
- digital_marketer
- content_marketer
- social_media_specialist
- seo_specialist
- email_marketer

### 法律团队
- contract_specialist
- compliance_officer

### HR 团队
- recruiter
- onboarding_specialist

### 财务团队
- accountant
- financial_analyst

### 运营团队
- project_coordinator
- process_analyst

### 研究团队
- market_researcher
- data_analyst

### 销售团队
- account_executive
- sales_development_rep

### 项目管理团队
- project_manager
- scrum_master

### 客户服务团队
- support_specialist
- account_manager

### 内容团队
- copywriter
- editor
- content_strategist

### 总裁办团队
- chief_executive_agent
- strategy_planner
- operations_coordinator
- resource_optimizer
- risk_manager
- external_relations_officer
- report_specialist

### 三贤者团队
- astra (阿斯特拉) - 战略贤者
- terra (泰拉) - 执行贤者
- nova (诺娃) - 创新贤者

## 配置

`config.toml` 文件包含以下部分：

- **core**：基本代理机构信息
- **models**：AI 模型配置（TRAE、OpenAI、Anthropic、Google、Azure、GLM、本地）
- **agents**：按部门划分的代理定义，包括 executive_office 和 three_sages

### 示例配置

```toml
# Core Settings
[core]
name = "OPC Agency"
description = "AI-powered agency system for One Person Company"
version = "1.0.0"

# AI Model Integration
[models]
# Default model to use
default = "trae"

# TRAE Model
[models.trae]
api_key = "your_trae_api_key"
base_url = "https://api.trae.cn/v1/chat"

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
tr = ["recruiter", "onboarding_specialist"]

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

## 与 TRAE 和其他模型的集成

系统通过各自的 API 集成多个 AI 模型：

- **TRAE**：代理交互的主要 AI 引擎
- **OpenAI**：用于高级语言理解的 GPT 模型
- **Anthropic**：用于详细推理的 Claude 模型
- **Google**：用于多模态能力的 Gemini 模型
- **Azure OpenAI**：企业级 AI 解决方案
- **GLM**：中文语言优化
- **本地模型**：注重隐私的本地部署

每个代理都定义了特定的角色和专业知识，任务被发送到适当的模型，并使用定制的提示以确保高质量的响应。系统会根据任务类型和上下文自动选择最佳模型。

## 扩展系统

### 添加新代理或部门

1. **更新 `config.toml` 文件**，在适当的部门中包含新代理
2. **创建提示模板**，为新代理提供特定的专业知识和指令
3. **扩展 `OPCManager` 类**（如果需要新功能）
4. **在 `communication_manager.py` 中添加通信类型**，用于专门的消息传递

### 添加新功能

1. **总裁办扩展**：在 `opc_manager.py` 的总裁办部分添加新功能
2. **三贤者增强**：修改 `start_three_sages_decision` 函数，添加新的决策因素
3. **代理优化**：在 `optimize_agents` 函数中扩展优化逻辑
4. **自动优化**：更新 `auto_optimizer.py` 文件，添加新的调度选项
5. **Web 界面**：在 `web_interface.py` 中添加新的 API 端点和 UI 组件

### 定制选项

- **模型选择**：在 `config.toml` 文件中添加新的 AI 模型
- **优化参数**：在 auto_optimizer_config.json 文件中调整优化设置
- **通知渠道**：在 auto_optimizer.py 文件中添加新的通知方法
- **任务模板**：为特定行业创建自定义任务分解模板

## 许可证

MIT 许可证 - 请根据需要使用和修改此项目。