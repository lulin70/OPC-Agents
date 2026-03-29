# OPC-Agents 项目设计文档

## 1. 系统架构

OPC-Agents 采用模块化、分层的架构设计，主要分为以下几个核心层次：

### 1.1 核心管理层
- **OPCManager**：系统的核心管理类，负责协调各个模块的工作
- **AgentManager**：负责代理的管理和调度
- **TaskManager**：负责任务的管理和分配
- **CommunicationManager**：负责代理间的通信

### 1.2 功能模块层
- **ExecutiveOffice**：总裁办功能，包括任务分解、进度跟踪和报告生成
- **ThreeSages**：三贤者决策系统，用于高维度战略决策
- **AgentOptimizer**：代理优化功能，用于自动性能改进
- **AutoOptimizer**：自动优化调度器，用于定期自动优化
- **HREnhancement**：HR生命周期管理，包括招聘、培训和绩效评估
- **A2AIntegration**：A2A协议集成，用于标准化代理通信

### 1.3 接口层
- **WebInterface**：Web界面，提供可视化管理功能
- **CommandLineInterface**：命令行接口，提供命令行操作功能
- **APILayer**：API层，提供RESTful API接口

### 1.4 外部集成层
- **ModelIntegration**：AI模型集成，支持多种AI模型
- **ZeroClawIntegration**：ZeroClaw集成，增强LLM连接性

## 2. 模块设计

### 2.1 OPCManager

**职责**：作为系统的核心管理类，协调各个模块的工作，提供统一的接口给用户。

**设计决策**：
- 采用单例模式，确保系统中只有一个OPCManager实例
- 提供统一的接口，封装底层模块的复杂性
- 负责初始化和管理各个子模块

**关键方法**：
- `assign_task()`：分配任务给指定代理
- `run_project()`：运行包含多个任务的项目
- `send_message()`：在代理之间发送消息
- `start_consensus()`：启动共识过程
- `decompose_task()`：分解任务为更小的子任务
- `track_progress()`：跟踪任务进度
- `generate_report()`：生成综合报告
- `start_three_sages_decision()`：启动三贤者决策过程
- `optimize_agents()`：优化代理性能

### 2.2 AgentManager

**职责**：负责代理的管理和调度，包括代理的注册、查询和分配。

**设计决策**：
- 采用配置驱动的方式，从配置文件中加载代理定义
- 支持按部门组织代理，便于管理和查询
- 提供代理的查询和筛选功能

**关键方法**：
- `get_agent()`：获取指定代理
- `get_agents_by_department()`：获取指定部门的所有代理
- `get_all_agents()`：获取所有代理
- `register_agent()`：注册新代理

### 2.3 TaskManager

**职责**：负责任务的管理和分配，包括任务的创建、分配、跟踪和完成。

**设计决策**：
- 采用状态机模式，跟踪任务的不同状态
- 支持任务的优先级和截止时间
- 提供任务的查询和筛选功能

**关键方法**：
- `create_task()`：创建新任务
- `assign_task()`：分配任务给指定代理
- `update_task_status()`：更新任务状态
- `get_task()`：获取指定任务
- `get_tasks_by_status()`：获取指定状态的任务
- `get_tasks_by_agent()`：获取指定代理的任务

### 2.4 CommunicationManager

**职责**：负责代理间的通信，包括消息的发送、接收和处理。

**设计决策**：
- 支持多种通信类型，如任务分配、信息共享、请求帮助等
- 提供消息的持久化存储，便于后续查询
- 支持消息的优先级和紧急程度

**关键方法**：
- `send_message()`：发送消息
- `receive_message()`：接收消息
- `process_message()`：处理消息
- `get_messages()`：获取消息历史

### 2.5 ExecutiveOffice

**职责**：实现总裁办功能，包括任务分解、进度跟踪和报告生成。

**设计决策**：
- 采用分层分解策略，将复杂任务分解为短期、中期和长期目标
- 支持多级任务分解，便于管理复杂项目
- 提供可视化的进度跟踪和报告生成

**关键方法**：
- `decompose_task()`：分解任务为更小的子任务
- `track_progress()`：跟踪任务进度
- `generate_report()`：生成综合报告
- `analyze_performance()`：分析代理和部门的绩效

### 2.6 ThreeSages

**职责**：实现三贤者决策系统，用于高维度战略决策。

**设计决策**：
- 采用三个不同角度的贤者（战略、执行、创新），提供全面的决策视角
- 基于多维度评估模型，综合考虑各种因素
- 支持决策过程的可视化和可追溯性

**关键方法**：
- `start_decision()`：启动决策过程
- `collect_opinions()`：收集贤者意见
- `analyze_opinions()`：分析贤者意见
- `generate_decision()`：生成最终决策

### 2.7 AgentOptimizer

**职责**：实现代理自我优化功能，用于自动性能改进。

**设计决策**：
- 基于反馈机制，不断改进代理的性能
- 支持多维度的优化，如专业知识、沟通能力、执行效率等
- 提供优化过程的可视化和可追溯性

**关键方法**：
- `optimize_agent()`：优化指定代理
- `optimize_all_agents()`：优化所有代理
- `analyze_performance()`：分析代理性能
- `generate_improvement_plan()`：生成改进计划

### 2.8 AutoOptimizer

**职责**：实现自动优化调度器，用于定期自动优化。

**设计决策**：
- 采用调度器模式，支持定期自动运行优化过程
- 支持配置优化频率和范围
- 提供优化统计和历史记录

**关键方法**：
- `start_scheduler()`：启动调度器
- `stop_scheduler()`：停止调度器
- `run_optimization()`：运行优化过程
- `get_optimization_statistics()`：获取优化统计
- `get_next_optimization_time()`：获取下次优化时间

### 2.9 HREnhancement

**职责**：实现HR生命周期管理，包括招聘、培训和绩效评估。

**设计决策**：
- 支持代理的全生命周期管理
- 提供培训和绩效评估机制
- 支持代理的技能发展和职业规划

**关键方法**：
- `train_agent()`：培训代理
- `evaluate_performance()`：评估代理绩效
- `optimize_agent()`：优化代理性能
- `get_agent_skills()`：获取代理技能
- `update_agent_skills()`：更新代理技能

### 2.10 A2AIntegration

**职责**：实现A2A协议集成，用于标准化代理通信。

**设计决策**：
- 采用标准化的通信协议，确保代理间的互操作性
- 支持工作流的创建和管理
- 提供消息的标准化格式和处理机制

**关键方法**：
- `register_agents()`：注册代理到A2A协议
- `send_a2a_message()`：使用A2A协议发送消息
- `create_workflow()`：创建工作流
- `execute_workflow()`：执行工作流

### 2.11 WebInterface

**职责**：提供Web界面，用于可视化管理和监控。

**设计决策**：
- 采用Flask框架，提供RESTful API
- 支持响应式设计，适配不同设备
- 提供实时状态更新和通知

**关键组件**：
- `app.py`：主Flask应用
- `routes/`：API路由，包括executive_office.py、task_management.py、department_management.py等
- `templates/`：Web界面模板

### 2.12 ModelIntegration

**职责**：实现AI模型集成，支持多种AI模型。

**设计决策**：
- 采用适配器模式，统一不同AI模型的接口
- 支持模型的动态切换和负载均衡
- 提供模型性能的监控和评估

**关键方法**：
- `get_model()`：获取指定模型
- `set_default_model()`：设置默认模型
- `switch_model()`：切换模型
- `evaluate_model_performance()`：评估模型性能

### 2.13 ZeroClawIntegration

**职责**：实现ZeroClaw集成，增强LLM连接性。

**设计决策**：
- 采用插件式架构，便于集成和扩展
- 提供ZeroClaw Gateway的管理和监控
- 支持多个LLM的连接和管理

**关键方法**：
- `start_gateway()`：启动ZeroClaw Gateway
- `stop_gateway()`：停止ZeroClaw Gateway
- `get_gateway_status()`：获取Gateway状态
- `connect_to_llm()`：连接到LLM

## 3. 数据结构

### 3.1 配置数据

**配置文件**：`config.toml`

**结构**：
- **core**：基本机构信息，如名称、描述、版本等
- **models**：AI模型配置，包括GLM、OpenAI、Anthropic、Google、Azure、本地模型等
- **agents**：按部门划分的代理定义，包括executive_office和three_sages

### 3.2 任务数据

**结构**：
```python
Task {
    id: str,              # 任务ID
    description: str,     # 任务描述
    department: str,      # 部门
    agent: str,           # 分配的代理
    status: str,          # 任务状态（待处理、进行中、已完成、已失败）
    priority: str,        # 优先级（低、中、高）
    created_at: datetime, # 创建时间
    updated_at: datetime, # 更新时间
    deadline: datetime,   # 截止时间
    result: str,          # 任务结果
    error: str            # 错误信息（如果有）
}
```

### 3.3 项目数据

**结构**：
```python
Project {
    id: str,              # 项目ID
    name: str,            # 项目名称
    description: str,     # 项目描述
    tasks: List[Task],    # 项目包含的任务
    status: str,          # 项目状态（待启动、进行中、已完成、已失败）
    created_at: datetime, # 创建时间
    updated_at: datetime, # 更新时间
    deadline: datetime,   # 截止时间
    progress: float       # 项目进度（0-100%）
}
```

### 3.4 消息数据

**结构**：
```python
Message {
    id: str,              # 消息ID
    sender: str,          # 发送者
    receiver: str,        # 接收者
    type: str,            # 消息类型（任务分配、信息共享、请求帮助等）
    content: str,         # 消息内容
    priority: str,        # 优先级（低、中、高）
    created_at: datetime, # 创建时间
    read: bool            # 是否已读
}
```

### 3.5 优化数据

**结构**：
```python
OptimizationRecord {
    id: str,              # 优化记录ID
    agent_id: str,        # 代理ID
    iterations: int,      # 优化迭代次数
    improvements: List[str], # 改进项
    before_score: float,  # 优化前得分
    after_score: float,   # 优化后得分
    created_at: datetime  # 创建时间
}
```

### 3.6 日志数据

**结构**：
```python
Log {
    id: str,              # 日志ID
    level: str,           # 日志级别（DEBUG、INFO、WARNING、ERROR、CRITICAL）
    message: str,         # 日志消息
    module: str,          # 模块名称
    created_at: datetime  # 创建时间
}
```

## 4. 接口设计

### 4.1 Web API 接口

#### 4.1.1 部门和代理管理
- `GET /api/departments`：获取所有部门
- `GET /api/departments/{department}`：获取指定部门的代理
- `POST /api/agents`：创建新代理
- `PUT /api/agents/{agent_id}`：更新代理信息
- `DELETE /api/agents/{agent_id}`：删除代理

#### 4.1.2 任务管理
- `GET /api/tasks`：获取所有任务
- `GET /api/tasks/{task_id}`：获取指定任务
- `POST /api/tasks`：创建新任务
- `PUT /api/tasks/{task_id}`：更新任务信息
- `DELETE /api/tasks/{task_id}`：删除任务
- `POST /api/tasks/{task_id}/assign`：分配任务
- `POST /api/tasks/{task_id}/complete`：完成任务

#### 4.1.3 项目管理
- `GET /api/projects`：获取所有项目
- `GET /api/projects/{project_id}`：获取指定项目
- `POST /api/projects`：创建新项目
- `PUT /api/projects/{project_id}`：更新项目信息
- `DELETE /api/projects/{project_id}`：删除项目
- `POST /api/projects/{project_id}/tasks`：向项目添加任务

#### 4.1.4 总裁办功能
- `POST /api/executive-office/decompose`：分解任务
- `GET /api/executive-office/progress`：获取进度
- `GET /api/executive-office/report`：生成报告

#### 4.1.5 三贤者决策系统
- `POST /api/three-sages/decision`：启动决策过程
- `GET /api/three-sages/decisions`：获取决策历史

#### 4.1.6 代理优化
- `POST /api/optimization/agents`：优化代理
- `POST /api/optimization/all`：优化所有代理
- `GET /api/optimization/statistics`：获取优化统计

#### 4.1.7 自动优化调度器
- `POST /api/auto-optimizer/start`：启动调度器
- `POST /api/auto-optimizer/stop`：停止调度器
- `GET /api/auto-optimizer/status`：获取调度器状态
- `PUT /api/auto-optimizer/config`：更新配置

#### 4.1.8 HR功能
- `POST /api/hr/train`：培训代理
- `POST /api/hr/evaluate`：评估代理绩效
- `GET /api/hr/agents`：获取所有代理
- `GET /api/hr/agent/{agent_id}`：获取指定代理信息

#### 4.1.9 A2A协议
- `POST /api/a2a/message`：发送A2A消息
- `POST /api/a2a/workflow`：创建工作流
- `GET /api/a2a/agents`：获取注册的代理

### 4.2 命令行接口

- `python opc_skill.py 查看所有部门`：查看所有部门
- `python opc_skill.py 查看部门 {department}`：查看部门中的代理
- `python opc_skill.py 安排任务 {department} {task}`：分配任务
- `python opc_skill.py 创建项目 {project_name} {tasks}`：创建项目
- `python opc_skill.py 发送消息 {sender} {receiver} {type} {content}`：发送消息
- `python opc_skill.py 启动共识 {topic} {agents}`：启动共识过程
- `python opc_skill.py 查看Token使用`：查看Token使用情况

## 5. 技术栈

### 5.1 核心技术
- **Python**：主要开发语言
- **Flask**：Web框架
- **TOML**：配置文件格式
- **Requests**：HTTP客户端库

### 5.2 AI模型集成
- **GLM**：中文语言优化（默认模型）
- **OpenAI**：GPT模型
- **Anthropic**：Claude模型
- **Google**：Gemini模型
- **Azure OpenAI**：企业级AI解决方案
- **本地模型**：如Ollama

### 5.3 工具和库
- **Ripgrep**：代码搜索
- **Git**：版本控制
- **ZeroClaw**：LLM连接增强

## 6. 部署与集成

### 6.1 部署方式
- **本地部署**：直接在本地运行
- **Docker部署**：使用Docker容器化部署
- **云部署**：部署到云服务器

### 6.2 集成方式
- **API集成**：通过RESTful API与其他系统集成
- **SDK集成**：提供Python SDK供其他应用使用
- **命令行集成**：通过命令行工具与其他系统集成

## 7. 监控与维护

### 7.1 监控
- **日志监控**：记录系统运行日志
- **性能监控**：监控系统性能指标
- **错误监控**：监控系统错误和异常
- **Token使用监控**：监控AI模型Token使用情况

### 7.2 维护
- **定期优化**：定期运行代理优化过程
- **模型更新**：定期更新AI模型配置
- **依赖更新**：定期更新系统依赖
- **备份**：定期备份配置和数据

## 8. 扩展性设计

### 8.1 模块扩展
- **新代理添加**：通过配置文件添加新代理
- **新部门添加**：通过配置文件添加新部门
- **新功能添加**：通过扩展现有模块或添加新模块

### 8.2 模型扩展
- **新AI模型集成**：通过添加新的模型适配器
- **模型配置更新**：通过修改配置文件更新模型配置

### 8.3 接口扩展
- **新API端点**：通过添加新的路由文件
- **新命令行命令**：通过扩展命令行工具

## 9. 安全性设计

### 9.1 API密钥管理
- **安全存储**：API密钥存储在配置文件中，不暴露在代码或日志中
- **权限控制**：限制API密钥的访问权限
- **定期轮换**：定期轮换API密钥

### 9.2 数据安全
- **数据加密**：敏感数据加密存储
- **访问控制**：限制数据访问权限
- **数据备份**：定期备份数据

### 9.3 网络安全
- **HTTPS**：使用HTTPS协议
- **防火墙**：配置防火墙规则
- **入侵检测**：监控异常访问

## 10. 结论

OPC-Agents 项目采用模块化、分层的架构设计，具有良好的可扩展性、可靠性和易用性。系统通过整合多个专业 AI 代理，为用户提供全方位的业务支持，能够帮助用户高效完成各种任务，做出更明智的商业决策。

系统的设计注重模块化和可扩展性，能够轻松添加新的代理和部门，处理各种异常情况，提供直观的用户界面。通过合理的技术选型和架构设计，确保系统能够按时、高质量地完成开发和部署。