# OPC-Agents 代码地图

## 系统架构

OPC-Agents 是一个多代理系统，用于 One Person Company，具有三层架构：

1. **Executive Office**：总裁办，负责整体战略规划和决策
2. **Departments**：各个部门，负责具体业务领域
3. **Agents**：各个部门的具体代理，负责执行具体任务

## 核心模块

### 1. 模型集成 (model_integration/)
- **model_manager.py**：模型管理器，负责管理多种AI模型的集成和切换
- **model_adapters.py**：模型适配器，为不同的AI模型提供统一的接口（GLM/OpenAI/Anthropic/Google/本地）
- **model_evaluator.py**：模型评估器，用于评估模型性能

### 2. 通信管理 (communication_manager.py)
- 负责代理之间的通信，包括消息传递、上下文共享和共识构建
- 直接使用ModelManager调用后台大模型（GLM）进行对话

### 3. 消息队列 (message_queue/)
- **queue_manager.py**：队列管理器，负责管理消息队列
- **message_processor.py**：消息处理器，使用ModelManager处理消息
- **fallback_handler.py**：降级处理器，提供多级降级策略和重试机制
- **models.py**：消息模型，定义消息的结构
- **progress_streamer.py**：进度流式传输器，用于实时传输任务进度

### 4. OPC管理器 (opc_manager/)
- **core.py**：核心管理器，负责整个系统的初始化和协调（集成ModelManager、HREnhancement、FinanceManager、MCPIntegration）
- **task_manager.py**：任务管理器，负责任务的创建、分配和跟踪
- **task_executor.py**：任务执行器，负责执行任务
- **agent_manager.py**：代理管理器，负责管理代理
- **three_sages.py**：三贤者决策系统，用于复杂决策（调用GLM模型）
- **personal_assistant.py**：个人助理，提供待办/天气/出行管理（调用真实天气API）
- **architecture.py**：系统架构管理，负责三层架构的初始化
- **config.py**：配置管理器，负责加载和管理配置

### 5. 人事部 (opc_hr/)
- **hr_enhancement.py**：人事部增强模块，Agent档案管理、技能匹配、招聘、优化（通过MCP GitHub搜索外部资源）
- **agent_manager.py**：代理管理器，负责管理代理
- **skill_manager.py**：技能管理器，负责管理代理技能
- **mcp_integration.py**：MCP GitHub集成，搜索/获取/导入Agent和Skill（GitHub API真实调用）
- **a2a_integration.py**：A2A集成，负责与A2A协议的集成
- **a2a_protocol.py**：A2A协议定义，包含MCPIntegration类
- **a2a_api.py**：A2A API接口，提供Agent间通信
- **hr_api.py**：HR API，提供HR相关的API接口

### 6. 财务部 (opc_finance/)
- **finance_manager.py**：财务部核心模块，Token使用监控、消费成本计算、日/周/月报告、预算告警
- **finance_routes.py**：财务部Web API路由

### 7. 监控系统 (monitoring/)
- **monitor.py**：系统监控器，负责监控系统整体状态
- **health_check.py**：健康检查器，负责检查系统各组件的健康状态
- **metrics.py**：指标收集器，负责收集系统指标
- **alerts.py**：告警管理器，负责管理系统告警

### 8. Web界面 (web_interface/)
- **app.py**：Web应用主文件，负责启动Flask服务（端口5009）
- **routes/**：路由模块，包含各种API路由
  - **executive_office.py**：总裁办路由（智能任务处理链：三贤者→人事部评估→任务分解→分发→执行）
  - **task_management.py**：任务管理路由
  - **department_management.py**：部门管理路由
  - **agent_management.py**：代理管理路由
  - **model_management.py**：模型管理路由
  - **auto_optimizer.py**：自动优化路由
  - **personal_assistant.py**：个人助理路由
  - **progress_routes.py**：进度路由
  - **health_routes.py**：健康检查路由
  - **mcp_management.py**：MCP管理路由（GitHub搜索/导入Agent和Skill）
  - **settings.py**：系统设置路由（模型/MCP/预算配置）

### 9. 数据存储 (data_storage/)
- **dao.py**：数据访问对象，负责与数据库交互
- **models.py**：数据模型，定义数据结构
- **conversation_manager.py**：对话管理器，负责管理对话历史

### 10. 知识库 (knowledge/)
- **knowledge_base.py**：知识库，存储系统知识
- **experience_store.py**：经验存储，存储代理经验
- **knowledge_retriever.py**：知识检索器，负责检索知识
- **solution_library.py**：解决方案库，存储解决方案

### 11. 任务报告 (task_reporting/)
- **report_generator.py**：报告生成器，负责生成任务报告
- **progress_tracker.py**：进度跟踪器，负责跟踪任务进度

### 12. 任务交付物 (task_deliverables/)
- **deliverable_generator.py**：交付物生成器，负责生成任务交付物
- **deliverable_manager.py**：交付物管理器，负责管理任务交付物

### 13. 工作流 (workflow/)
- **engine.py**：工作流引擎，通过CommunicationManager调用真实模型
- **executor.py**：工作流执行器，通过CommunicationManager调用真实模型
- **definitions.py**：工作流定义，定义工作流的结构

### 14. API层 (api_layer/)
- **api_manager.py**：API管理器，负责管理API接口
- **api_documentation.py**：API文档，提供API文档
- **api_security.py**：API安全，负责API安全

### 15. 命令行界面 (cli/)
- **cli.py**：命令行界面，提供命令行交互

## 核心业务流程

### 1. 用户任务处理完整流程

```
用户发消息给总裁办
    ↓
① GLM判断意图（闲聊 / 任务）
    ├── 闲聊 → 总裁办直接友好回复
    └── 任务 → 启动完整处理链 ↓

② 三贤者决策分析（战略贤者/执行贤者/创新贤者）
    ↓

③ 人事部评估本地Agent资源
    ├── 有合适Agent → 分配给本地Agent
    └── 无合适Agent → MCP GitHub搜索外部Agent/Skill
         ↓ 报告总裁办，建议引入

④ 任务分解（按部门拆分子任务）
    ↓

⑤ 创建主任务 + 子任务
    ↓

⑥ 分发子任务到各部门Agent
    ↓

⑦ 触发TaskExecutor异步执行
    ↓

⑧ 综合回复用户（决策建议 + 资源评估 + 分派清单）

⑨ 财务部实时记录Token消耗，超预算告警

⑩ 任务完成后：
    ├── 成功 → 人事部评估并优化本地Agent
    └── 失败 → MCP GitHub搜寻替代资源 → 报告用户确认 → 导入
```

### 2. 人事部资源管理流程

```
任务分发前：
  总裁办 → hr_enhancement.create_job_requirement()
  人事部 → find_matching_agents()（本地匹配）
  ├── 有本地Agent → 分配执行
  └── 无本地Agent → MCP GitHub搜索外部资源
       → 报告总裁办（含候选列表）

任务结束后：
  ├── 成功 → hr_enhancement.optimize_agent()
  └── 失败 → MCP GitHub搜索替代 → 用户确认 → import_agent/import_skill
```

### 3. 财务部监控流程

```
每次模型调用 → finance_manager.record_usage()
    ↓
累计消费达预算80% → warning告警
    ↓
累计消费超预算 → critical告警
    ↓
用户查看日/周/月消费报告
```

## 主要API

### 1. 总裁办API
- **POST /api/chat/<chat_id>/message**：发送消息（智能任务处理链）
- **POST /api/task/<task_id>/complete**：任务完成处理（成功优化/失败搜寻）
- **POST /api/hr/import**：用户确认引入外部Agent/Skill
- **GET /api/chat/history**：获取对话历史
- **GET /api/chat/<chat_id>**：获取对话详情
- **GET /api/agents/activity**：获取Agent活动状态
- **POST /api/chat**：新建对话
- **POST /api/three_sages_decision**：三贤者决策

### 2. 任务管理API
- **POST /api/tasks**：创建任务
- **PUT /api/tasks/<task_id>**：更新任务
- **GET /api/tasks/<task_id>/history**：获取任务历史

### 3. 部门管理API
- **GET /api/departments**：获取部门列表
- **GET /api/department/<department>**：获取部门详情

### 4. 代理管理API
- **GET /api/agents**：获取代理列表
- **GET /api/agents/<agent_id>**：获取代理详情

### 5. 模型管理API
- **GET /api/models**：获取模型列表
- **GET /api/models/<model_name>**：获取模型详情

### 6. 财务部API
- **GET /api/finance/dashboard**：财务仪表盘
- **GET /api/finance/token_usage**：Token使用统计
- **GET /api/finance/report?period=daily|weekly|monthly**：消费报告
- **GET /api/finance/alerts**：预算告警
- **POST /api/finance/budget**：设置预算

### 7. MCP管理API
- **GET /api/mcp/status**：MCP连接状态
- **GET /api/mcp/agents/search?q=xxx**：搜索GitHub Agent
- **GET /api/mcp/agents/<owner/repo>**：获取Agent详情
- **POST /api/mcp/agents/<owner/repo>/import**：导入Agent
- **GET /api/mcp/skills/search?q=xxx**：搜索GitHub Skill
- **GET /api/mcp/skills/<owner/repo>**：获取Skill详情
- **POST /api/mcp/skills/<owner/repo>/import**：导入Skill
- **GET /api/mcp/categories**：Skill类别列表
- **GET /api/mcp/history**：导入和验证历史

### 8. 系统设置API
- **GET /api/settings/**：获取系统设置
- **POST /api/settings/models**：更新模型配置
- **POST /api/settings/mcp**：更新MCP GitHub Token
- **POST /api/settings/finance/budget**：设置预算
- **POST /api/settings/test_model**：测试模型连接

### 9. 健康检查API
- **GET /api/health**：健康检查
- **GET /api/health/<component>**：检查具体组件健康状态

## 配置文件

- **config.toml**：系统配置文件
  - `[core]`：系统核心配置
  - `[models.glm]`：GLM模型配置（API Key、模型名称）
  - `[models.openai/anthropic/google]`：其他模型配置
  - `[agents.three_sages]`：三贤者配置
  - `[mcp]`：MCP GitHub集成配置（Token、Agent源、Skill源）

## 依赖关系

- **ModelManager** → model_adapters.py（GLM/OpenAI/Anthropic/Google/本地）
- **CommunicationManager** → ModelManager（GLM模型直接调用）
- **OPCManager** → CommunicationManager + TaskExecutor + HREnhancement + FinanceManager + MCPIntegration
- **HREnhancement** → MCPIntegration（GitHub搜索外部Agent/Skill）
- **FinanceManager** → CommunicationManager（Token使用统计）
- **ExecutiveOffice路由** → OPCManager（三贤者 + 任务分解 + 人事部评估 + 任务分发）
- **WebInterface** → OPCManager（所有路由通过manager协调）

## 总结

OPC-Agents是一个为一人公司设计的多代理系统，通过GLM大模型驱动，具有完整的三层架构。系统的核心业务流程是：用户发消息给总裁办 → 三贤者决策 → 人事部评估资源 → 任务分解分发 → 部门执行 → 财务监控。人事部通过MCP GitHub集成搜索外部Agent/Skill，任务失败时自动推荐替代资源。财务部实时监控Token消耗并提供消费报告。系统不再使用任何模拟实现，所有功能均通过真实API调用完成。
