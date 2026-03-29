# OPC-Agents

一个为一人公司（OPC）设计的多代理系统，灵感来自流行的GitHub项目Agency-Agents，具有增强的AI能力。

## 概述

该项目实现了一个虚拟代理机构，包含多个专业的AI代理，可以处理各种任务。每个代理都设计有特定的专业知识，可以通过各种AI模型API分配任务。系统增强了总裁办功能、三贤者决策系统和代理自我优化能力。

## 功能

- **多部门结构**，包含35个专业部门
- **157+专业代理**，覆盖不同领域（来自官方Agency-Agents项目）
- **多模型支持**，包括GLM、OpenAI、Anthropic、Google、Azure和本地模型
- **任务分配**系统，用于将工作委托给特定代理（现在支持实际任务调度，而不仅仅是模拟）
- **项目管理**，用于协调多个任务
- **内部通信**系统，用于代理间消息传递
- **共识机制**，用于多代理决策
- **Token使用控制**，用于高效的资源管理
- **总裁办**，用于任务分解、进度跟踪和报告
- **三贤者决策系统**，用于高维度战略决策
- **代理自我优化**，用于自动性能改进
- **自动优化调度器**，用于定期自动优化
- **Web界面**，用于轻松管理和监控（带有代理活动状态区域）
- **综合报告**，带有智能洞察
- **任务分解**，分为短期、中期和长期目标
- **进度跟踪**，跨部门和优先级
- **资源优化**，用于高效的代理利用
- **A2A（代理到代理协议）**集成，用于标准化代理通信
- **HR生命周期管理**，包括招聘、培训和绩效评估
- **HR部门页面**，显示部门和代理列表
- **实际任务调度**，向部门代理发送任务并提供实时状态更新

## 目录结构

```
OPC-Agents/
├── config.toml               # 主配置文件
├── config.toml.sample        # 配置文件模板
├── communication_manager.py    # 通信管理脚本
├── opc_skill.py               # 技能实现
├── OPCstart.sh                # OPC-Agents启动脚本
├── official_agents/           # 来自Agency-Agents项目的官方代理
├── optimization_records/      # 优化迭代记录
├── optimization_notifications/ # 优化通知文件
├── templates/                 # Web界面模板
├── logs/                      # 日志文件目录
├── temp-use/                  # 旧文件的临时目录
├── opc_manager/               # 核心管理模块
│   ├── __init__.py
│   ├── core.py                # 主OPCManager类
│   ├── log_config.py          # 日志配置
│   ├── config.py              # 配置管理
│   ├── agent_manager.py       # 代理管理
│   ├── task_manager.py        # 任务管理
│   ├── architecture.py        # 系统架构
│   ├── three_sages.py         # 三贤者决策系统
│   └── personal_assistant.py  # 个人助理功能
├── web_interface/             # Web界面模块
│   ├── __init__.py
│   ├── app.py                 # 主Flask应用
│   └── routes/                # API路由
│       ├── executive_office.py
│       ├── task_management.py
│       ├── department_management.py
│       ├── personal_assistant.py
│       ├── model_management.py
│       └── auto_optimizer.py
├── opc_hr/                    # HR和A2A相关模块
│   ├── a2a_api.py             # A2A协议的REST API端点
│   ├── a2a_integration.py     # A2A协议集成
│   ├── a2a_protocol.py        # A2A（代理到代理）协议实现
│   ├── auto_optimizer.py      # 自动优化调度器
│   ├── hr_api.py              # HR功能的REST API端点
│   └── hr_enhancement.py      # HR生命周期管理实现
├── test_opc_manager.py        # OPCManager测试脚本
└── zeroclaw_integration.py    # ZeroClaw集成
```

## 安装

1. **克隆仓库**（或手动创建目录结构）
2. **安装依赖**：
   ```bash
   pip install requests toml flask
   ```
3. **配置API密钥**：
   - 将 `config.toml.sample` 复制为 `config.toml`
   - 在 `config.toml` 中更新API密钥：
     - GLM API密钥
     - 其他模型API密钥（OpenAI、Anthropic、Google、Azure）（如果需要）

## 使用

### 基本使用

```python
from opc_manager import OPCManager

# 初始化管理器
manager = OPCManager()

# 向代理分配任务
result = manager.assign_task(
    "为任务管理应用设计现代UI",
    "design",
    "UI Designer"
)
print(result)

# 运行包含多个任务的项目
project_tasks = [
    {
        "department": "design",
        "agent": "UI Designer",
        "task": "为Web应用设计登录页面"
    },
    {
        "department": "engineering",
        "agent": "Frontend Developer",
        "task": "使用React实现登录页面"
    },
    {
        "department": "marketing",
        "agent": "Digital Marketer",
        "task": "为新登录系统创建营销活动"
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
from opc_hr.auto_optimizer import AutoOptimizer

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
from opc_hr.a2a_integration import OPCA2AIntegration
from opc_manager import OPCManager

# 初始化OPC管理器
opc_manager = OPCManager()

# 初始化A2A集成
a2a_integration = OPCA2AIntegration(opc_manager)

# 向A2A注册代理（在初始化时自动完成）
print("代理已注册到A2A协议")

# 创建工作流（使用工作流模块）
workflow = a2a_integration.workflow.create_workflow(
    "网站开发项目",
    [
        {"agent": "ui_designer", "task": "设计网站UI"},
        {"agent": "frontend_developer", "task": "实现前端"},
        {"agent": "backend_developer", "task": "实现后端"}
    ]
)
print(f"工作流已创建: {workflow}")

# 使用A2A在代理之间发送消息
message_result = a2a_integration.send_a2a_message(
    "ui_designer",
    "frontend_developer",
    "请根据这些规范实现UI"
)
print(f"消息已发送: {message_result.id}")
```

### HR生命周期管理使用

```python
from opc_hr.hr_enhancement import HREnhancement
from opc_manager import OPCManager

# 初始化OPC管理器
opc_manager = OPCManager()

# 初始化HR增强
hr_enhancement = HREnhancement(opc_manager)

# 获取所有代理
agents = hr_enhancement.get_all_agents()
print(f"代理总数: {len(agents)}")

# 培训代理
training_result = hr_enhancement.train_agent(
    agent_id="digital_marketer",
    skills={"content_creation": "high", "analytics": "medium"}
)
print(f"培训结果: {training_result}")

# 评估代理绩效
evaluation_result = hr_enhancement.evaluate_performance(
    agent_id="digital_marketer",
    rating=4.5,
    feedback="内容创建表现优秀"
)
print(f"评估结果: {evaluation_result}")

# 优化代理绩效
optimization_result = hr_enhancement.optimize_agent(
    agent_id="digital_marketer"
)
print(f"代理优化完成: {optimization_result['success']}")
```

### Web界面使用

#### 使用OPCstart.sh（推荐）

1. **使脚本可执行**：
   ```bash
   chmod +x OPCstart.sh
   ```

2. **运行启动脚本**：
   ```bash
   ./OPCstart.sh
   ```

3. **访问Web界面**：`http://localhost:5007`

#### 手动启动

1. **启动Web服务器**：
   ```bash
   python -m web_interface.app
   ```

2. **访问Web界面**：`http://localhost:5007`

3. **Web界面可用功能**：
   - 部门和代理管理
   - 任务创建和管理
   - 共识过程启动
   - 总裁办功能（任务分解、进度跟踪、报告）
   - 三贤者决策系统
   - 代理自我优化
   - 自动优化调度器配置
   - Token使用监控
   - 优化统计和历史
   - 代理活动状态区域（显示哪个代理在做什么）
   - HR部门页面，显示部门和代理列表
   - A2A协议集成状态

### 命令行使用

```bash
# 查看所有部门
python opc_skill.py 查看所有部门

# 查看部门中的代理
python opc_skill.py 查看部门 engineering

# 分配任务
python opc_skill.py 安排任务 engineering "设计数据库架构"

# 创建项目
python opc_skill.py 创建项目 "网站开发" "design:设计UI" "engineering:实现后端"

# 发送消息
python opc_skill.py 发送消息 "UI Designer" "Backend Architect" "task_assignment" "设计数据库架构"

# 启动共识
python opc_skill.py 启动共识 "技术选型" "UI Designer" "Backend Architect" "Frontend Developer"

# 查看Token使用
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

### HR团队
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

- **core**：基本机构信息
- **models**：AI模型配置（GLM、OpenAI、Anthropic、Google、Azure、本地）
- **agents**：按部门定义的代理，包括executive_office和three_sages

### 示例配置

```toml
# 核心设置
[core]
name = "OPC Agency"
description = "AI-powered agency system for One Person Company"
version = "1.0.0"

# AI模型集成
[models]
# 默认使用的模型
default = "glm"

# OpenAI模型
[models.openai]
api_key = "your_openai_api_key"
base_url = "https://api.openai.com/v1/chat/completions"
model = "gpt-4o"

# Anthropic模型
[models.anthropic]
api_key = "your_anthropic_api_key"
base_url = "https://api.anthropic.com/v1/messages"
model = "claude-3-opus-20240229"

# Google模型
[models.google]
api_key = "your_google_api_key"
base_url = "https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent"
model = "gemini-pro"

# Azure OpenAI
[models.azure]
api_key = "your_azure_api_key"
base_url = "https://your-resource-name.openai.azure.com/openai/deployments/your-deployment-name/chat/completions?api-version=2024-02-15-preview"
model = "gpt-4"

# 本地模型（例如，Ollama）
[models.local]
base_url = "http://localhost:11434/api/chat"
model = "llama3"

# GLM模型
[models.glm]
api_key = "your_glm_api_key"
base_url = "https://open.bigmodel.cn/api/messages"
model = "glm-4"

# 代理配置
[agents]
# 设计团队
design = ["ui_designer", "ux_researcher", "graphic_designer", "motion_designer"]

# 开发团队
development = ["frontend_developer", "backend_developer", "fullstack_developer", "devops_engineer", "qa_engineer"]

# 营销团队
marketing = ["digital_marketer", "content_marketer", "social_media_specialist", "seo_specialist", "email_marketer"]

# 法律团队
legal = ["contract_specialist", "compliance_officer"]

# HR团队
hr = ["recruiter", "onboarding_specialist"]

# 财务团队
finance = ["accountant", "financial_analyst"]

# 运营团队
operations = ["project_coordinator", "process_analyst"]

# 研究团队
research = ["market_researcher", "data_analyst"]

# 销售团队
sales = ["account_executive", "sales_development_rep"]

# 项目管理团队
project_management = ["project_manager", "scrum_master"]

# 客户服务团队
customer_service = ["support_specialist", "account_manager"]

# 内容团队
content = ["copywriter", "editor", "content_strategist"]

# 总裁办团队
[agents.executive_office]
chief_executive_agent = "chief_executive_agent"
strategy_planner = "strategy_planner"
operations_coordinator = "operations_coordinator"
resource_optimizer = "resource_optimizer"
risk_manager = "risk_manager"
external_relations_officer = "external_relations_officer"
report_specialist = "report_specialist"

# 三贤者团队
[agents.three_sages]
astra = "astra"  # 战略贤者
terra = "terra"  # 执行贤者
nova = "nova"  # 创新贤者
```

## 与AI模型集成

系统通过各自的API集成多个AI模型：

- **GLM**：中文语言优化（默认模型）
- **OpenAI**：GPT模型，用于高级语言理解
- **Anthropic**：Claude模型，用于详细推理
- **Google**：Gemini模型，用于多模态能力
- **Azure OpenAI**：企业级AI解决方案
- **本地模型**：注重隐私的本地部署

每个代理都定义有特定的角色和专业知识，任务会发送到适当的模型，并使用定制的提示来确保高质量的响应。系统会根据任务类型和上下文自动选择最佳模型。

## 扩展系统

### 添加新代理或部门

1. **更新 `config.toml` 文件**，在适当的部门中添加新代理
2. **创建提示模板**，为新代理提供特定的专业知识和指令
3. **扩展 `OPCManager` 类**，如果需要新功能
4. **在 `communication_manager.py` 中添加通信类型**，用于专门的消息传递

### 添加新功能

1. **总裁办扩展**：在 `opc_manager/core.py` 的总裁办部分添加新功能
2. **三贤者增强**：修改 `three_sages.py` 文件，添加新的决策因素
3. **代理优化**：在 `opc_hr/auto_optimizer.py` 中扩展优化逻辑
4. **Web界面**：在 `web_interface/routes/` 下的适当路由文件中添加新的API端点
5. **HR增强**：在 `opc_hr/hr_enhancement.py` 中扩展HR功能
6. **A2A协议**：在 `opc_hr/a2a_protocol.py` 中添加新功能

### 自定义选项

- **模型选择**：在 `config.toml` 文件中添加新的AI模型
- **优化参数**：在 auto_optimizer_config.json 文件中调整优化设置
- **通知渠道**：在 auto_optimizer.py 文件中添加新的通知方法
- **任务模板**：为特定行业创建自定义任务分解模板

## 许可证

Apache License 2.0 - 详见 [LICENSE](./LICENSE) 文件。

使用本项目，即表示您同意遵守Apache 2.0许可证的条款。该许可证允许您自由使用、修改和分发本项目，同时提供专利保护。