# OPC-Agents 代码地图

## 系统架构

OPC-Agents 是一个多代理系统，用于 One Person Company，具有三层架构：

1. **Executive Office**：总裁办，负责整体战略规划和决策
2. **Departments**：各个部门，负责具体业务领域
3. **Agents**：各个部门的具体代理，负责执行具体任务

## 项目结构

```
OPC-Agents/
├── opc_manager/          # 核心管理器（系统大脑）
├── model_integration/    # AI模型集成（GLM/OpenAI/Anthropic/Google/本地）
├── opc_hr/               # 人事部（Agent管理/Skill/MCP GitHub集成）
├── opc_finance/          # 财务部（Token监控/消费报告/预算告警）
├── monitoring/           # 系统监控（健康检查/指标/告警）
├── message_queue/        # 消息队列（消息处理/降级/进度推送）
├── data_storage/         # 数据存储（数据库/对话管理）
├── task_deliverables/    # 任务交付物（生成/管理）
├── official_agents/      # 官方Agent档案（JSON定义）
├── web_interface/        # Web界面（Flask + 11个路由模块）
├── templates/            # HTML页面模板
├── tests/                # 测试用例
├── docs/                 # 文档
└── config.toml.sample    # 配置文件模板
```

## 核心模块

### 1. OPC管理器 (opc_manager/)
- **core.py**：核心管理器，系统初始化和协调中心
  - 集成：CommunicationManager + TaskExecutor + HREnhancement + FinanceManager + MCPIntegration
  - 提供：任务CRUD、Agent查询、部门管理、三贤者决策、任务分解
- **communication_manager.py**：代理间通信，消息传递/上下文共享/共识构建
- **task_manager.py**：任务管理器，任务创建/分配/跟踪/历史
- **task_executor.py**：任务执行器，异步执行任务
- **agent_manager.py**：官方Agent管理器，按部门查询/获取Agent列表
- **three_sages.py**：三贤者决策系统（战略/执行/创新三视角，调用GLM）
- **personal_assistant.py**：个人助理（待办/天气/出行，调用真实天气API）
- **architecture.py**：三层架构初始化
- **config.py**：配置管理器

### 2. 模型集成 (model_integration/)
- **model_manager.py**：模型管理器，多模型集成和切换
- **model_adapters.py**：模型适配器（GLM/OpenAI/Anthropic/Google/本地）
- **model_evaluator.py**：模型评估器

### 3. 人事部 (opc_hr/)

**HR核心** — Agent管理、技能匹配、部门管理
- **hr_enhancement.py**：人事部增强模块（Agent档案/技能匹配/招聘/优化/MCP搜索）
- **hr_api.py**：HR API接口
- **skill_manager.py**：技能管理器
- **department_manager.py**：部门管理器

**MCP集成** — GitHub Agent/Skill搜索、导入、安装
- **mcp_integration.py**：MCP GitHub集成（搜索/获取/导入Agent和Skill）
- **installation_manager.py**：安装管理器

**A2A协议** — Agent间通信
- **a2a_api.py**：A2A API接口
- **a2a_protocol.py**：A2A协议定义
- **a2a_integration.py**：A2A集成实现

**优化器** — Agent性能优化
- **agent_optimizer.py**：Agent优化器
- **auto_optimizer.py**：自动优化器

### 4. 财务部 (opc_finance/)
- **finance_manager.py**：Token监控/消费成本计算/日周月报告/预算告警
- **finance_routes.py**：财务部Web API路由

### 5. 监控系统 (monitoring/)
- **monitor.py**：系统监控器
- **health_check.py**：健康检查器
- **metrics.py**：指标收集器
- **alerts.py**：告警管理器

### 6. 消息队列 (message_queue/)
- **queue_manager.py**：队列管理器
- **message_processor.py**：消息处理器
- **fallback_handler.py**：降级处理器
- **models.py**：消息模型
- **progress_streamer.py**：进度流式传输器

### 7. 数据存储 (data_storage/)
- **dao.py**：数据访问对象（SQLite）
- **models.py**：数据模型
- **conversation_manager.py**：对话管理器

### 8. 任务交付物 (task_deliverables/)
- **deliverable_generator.py**：交付物生成器
- **deliverable_manager.py**：交付物管理器

### 9. Web界面 (web_interface/)
- **app.py**：Flask应用主文件（端口5009）
- **routes/**：11个路由模块
  - **executive_office.py**：总裁办（智能任务处理链）
  - **task_management.py**：任务管理
  - **department_management.py**：部门管理
  - **agent_management.py**：代理管理
  - **model_management.py**：模型管理
  - **auto_optimizer.py**：自动优化
  - **personal_assistant.py**：个人助理
  - **progress_routes.py**：进度路由
  - **health_routes.py**：健康检查
  - **mcp_management.py**：MCP管理（GitHub搜索/导入）
  - **settings.py**：系统设置（模型/MCP/预算配置）

### 10. 页面模板 (templates/)
- **index.html**：首页/总裁办对话（Markdown渲染/SSE进度/HR推荐卡片）
- **finance.html**：财务部仪表盘（消费报告/预算设置/告警）
- **monitoring.html**：系统监控（组件状态/CPU内存/任务统计）
- **department.html**：部门详情（真实任务列表/完成失败交互）
- **agent_management.html**：代理管理

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

## 依赖关系

```
web_interface/app.py
  └── opc_manager/core.py (OPCManager)
        ├── opc_manager/communication_manager.py
        │     ├── model_integration/model_manager.py
        │     ├── message_queue/
        │     └── data_storage/dao.py
        ├── opc_manager/task_manager.py
        │     └── task_deliverables/
        ├── opc_manager/agent_manager.py (官方Agent查询)
        ├── opc_hr/hr_enhancement.py
        │     └── opc_hr/mcp_integration.py (GitHub API)
        ├── opc_hr/skill_manager.py
        └── opc_finance/finance_manager.py
```

## 主要API

| 分类 | 端点 | 说明 |
|------|------|------|
| 总裁办 | POST /api/chat/<id>/message | 发送消息（智能任务处理链） |
| 总裁办 | POST /api/task/<id>/complete | 任务完成处理 |
| 总裁办 | POST /api/hr/import | 引入外部Agent/Skill |
| 总裁办 | POST /api/three_sages_decision | 三贤者决策 |
| 任务 | GET/POST /api/tasks | 任务列表/创建 |
| 任务 | PUT /api/tasks/<id> | 更新任务 |
| 部门 | GET /api/departments | 部门列表 |
| Agent | GET /api/agents | Agent列表 |
| 财务 | GET /api/finance/dashboard | 财务仪表盘 |
| 财务 | GET /api/finance/report?period=daily | 消费报告 |
| 财务 | POST /api/finance/budget | 设置预算 |
| MCP | GET /api/mcp/agents/search?q=xxx | 搜索GitHub Agent |
| MCP | GET /api/mcp/skills/search?q=xxx | 搜索GitHub Skill |
| MCP | POST /api/mcp/agents/<repo>/import | 导入Agent |
| 设置 | GET /api/settings/ | 系统设置 |
| 设置 | POST /api/settings/test_model | 测试模型连接 |
| 健康 | GET /api/health/ | 健康检查 |
| 进度 | GET /api/progress/stream | SSE实时进度 |

## 配置文件

- **config.toml**：系统配置
  - `[models.glm]`：GLM模型配置（API Key、模型名称）
  - `[models.openai/anthropic/google]`：其他模型配置
  - `[agents.three_sages]`：三贤者配置
  - `[mcp]`：MCP GitHub集成配置（Token、Agent源、Skill源）
  - `[finance]`：财务预算配置
