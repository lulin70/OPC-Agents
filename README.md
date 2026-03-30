# OPC-Agents

> **你对总裁办下一个指令，总裁办调动全公司36个部门、180+AI员工协同合作完成。**

一个为一人公司（OPC）设计的AI多代理操作系统。你不需要逐个调用AI工具——只需像给CEO下指令一样告诉总裁办你想做什么，系统会自动分解任务、调度合适的AI部门、协同完成，并把结果汇报给你。

## 工作方式

```
你 → 总裁办 → 三贤者决策 → 人事部评估资源 → 任务分解 → 各部门AI员工协同执行 → 结果汇报
```

**一句话：你是CEO，总裁办是你的AI Chief of Staff，36个部门是你的AI团队。**

## 核心能力

- **总裁办智能调度**：你下指令，总裁办自动判断意图（闲聊/搜索/任务），调动全公司资源协同完成
- **36个专业部门**，覆盖设计/开发/营销/财务/运营等领域
- **180+专业AI员工**（来自官方Agency-Agents项目 + A2A协议）
- **三贤者决策系统**：战略/执行/创新三视角分析，确保决策质量
- **网页搜索**：DuckDuckGo免费搜索，获取最新信息辅助决策
- **MCP GitHub集成**：搜索/获取/导入外部Agent和Skill（含代码安全审核）
- **多模型支持**：GLM、OpenAI、Anthropic、Google、Azure、本地模型
- **任务管理**：创建/重命名/删除，自动创建工作目录
- **财务部**：Token监控、消费报告、预算告警
- **系统监控**：CPU/内存/磁盘、组件健康、任务统计、告警
- **HR生命周期管理**：招聘、培训、绩效评估、Agent优化
- **A2A协议**：标准化Agent间通信
- **Web界面**：统一顶部导航，5个页面（总裁办/财务部/监控/代理管理/部门详情）

## 目录结构

```
OPC-Agents/
├── config.toml.sample        # 配置文件模板
├── OPCstart.sh               # 一键启动脚本
├── CODE_MAP.md               # 代码地图（架构/模块/API）
├── official_agents/           # 官方Agent档案（JSON定义）
├── task_workspaces/           # 任务工作目录（自动创建）
├── templates/                 # HTML页面模板
├── temp-use/                  # 已归档的旧模块
├── opc_manager/               # 核心管理器
│   ├── core.py                # OPCManager（系统大脑）
│   ├── communication_manager.py # 代理间通信
│   ├── task_manager.py        # 任务管理（CRUD/工作目录）
│   ├── task_executor.py       # 异步任务执行
│   ├── agent_manager.py       # 官方Agent查询
│   ├── three_sages.py         # 三贤者决策
│   ├── personal_assistant.py  # 个人助理
│   ├── architecture.py        # 三层架构
│   └── config.py              # 配置管理
├── model_integration/         # AI模型集成
│   ├── model_manager.py       # 多模型管理
│   └── model_adapters.py      # GLM/OpenAI/Anthropic/Google适配器
├── opc_hr/                    # 人事部
│   ├── hr_enhancement.py      # HR核心（Agent管理/技能匹配）
│   ├── skill_manager.py       # 技能管理
│   ├── department_manager.py  # 部门管理
│   ├── mcp_integration.py     # MCP GitHub集成
│   ├── installation_manager.py # 安装管理
│   ├── web_search.py          # 网页搜索（DuckDuckGo）
│   ├── a2a_api.py             # A2A API
│   ├── a2a_protocol.py        # A2A协议
│   └── a2a_integration.py     # A2A集成
├── opc_finance/               # 财务部
│   ├── finance_manager.py     # Token监控/消费报告/预算告警
│   └── finance_routes.py      # 财务API路由
├── monitoring/                # 系统监控
│   ├── monitor.py             # 监控器
│   ├── health_check.py        # 健康检查
│   ├── metrics.py             # 指标收集
│   └── alerts.py              # 告警管理
├── message_queue/             # 消息队列
├── data_storage/              # 数据存储（SQLite）
├── task_deliverables/         # 任务交付物
├── web_interface/             # Web界面（Flask，端口5009）
│   ├── app.py                 # 主应用
│   └── routes/                # 11个路由模块
└── docs/                      # 文档
```

## 安装

1. **克隆仓库**
2. **安装依赖**：
   ```bash
   pip3 install requests toml flask ddgs
   ```
3. **配置API密钥**：
   ```bash
   cp config.toml.sample config.toml
   # 编辑 config.toml，填入GLM API密钥（必需）
   ```

## 使用

### 一键启动

```bash
chmod +x OPCstart.sh
./OPCstart.sh
```

访问 **http://localhost:5009**

### Web界面功能

| 页面 | URL | 功能 |
|------|-----|------|
| 总裁办 | `/` | 对话（闲聊/搜索/任务）、任务管理、HR推荐 |
| 财务部 | `/finance` | 消费报告、预算设置、告警 |
| 系统监控 | `/monitoring` | CPU/内存/磁盘、组件状态、任务统计 |
| 代理管理 | `/agent_management` | Agent列表、创建/编辑/删除 |
| 部门详情 | `/department/<名称>` | 部门任务列表、完成/失败操作 |

### 任务管理

- **创建**：总裁办页面右上角"新建任务"按钮
- **重命名**：hover任务卡片 → ✏️按钮（行内编辑，Enter确认）
- **删除**：hover任务卡片 → 🗑️按钮（删除任务+工作目录）
- **打开工作目录**：hover任务卡片 → 📁按钮（Finder打开）

### 总裁办对话模式

```
用户消息 → GLM判断意图
├── 闲聊 → 直接友好回复
├── 搜索 → DuckDuckGo搜索 → GLM基于搜索结果回答
└── 任务 → 搜索辅助 → 三贤者决策 → 任务分解 → 分发执行
```

## API

| 端点 | 说明 |
|------|------|
| `POST /api/chat/<id>/message` | 总裁办对话 |
| `POST/GET /api/tasks` | 任务创建/列表 |
| `PUT /api/tasks/<id>/rename` | 重命名任务 |
| `DELETE /api/tasks/<id>` | 删除任务 |
| `GET /api/tasks/<id>/workdir` | 获取工作目录 |
| `POST /api/tasks/<id>/open_workdir` | 打开工作目录 |
| `GET /api/departments` | 部门列表 |
| `GET /api/agents/` | Agent列表 |
| `GET /api/finance/dashboard` | 财务仪表盘 |
| `GET /api/finance/report?period=daily` | 消费报告 |
| `GET /api/health/` | 健康检查 |
| `GET /api/mcp/web/search?q=xxx` | 网页搜索 |
| `GET /api/mcp/agents/search?q=xxx` | GitHub Agent搜索 |
| `GET /api/progress/stream` | SSE实时进度 |

## 配置

`config.toml` 主要配置项：

```toml
[models.glm]
api_key = "your_glm_api_key"    # 必需
model = "glm-4.7"

[mcp]
github_token = ""                # 可选，提升GitHub API频率

[finance]
monthly_budget = 100             # 月预算（元）
```

## 扩展系统

### 添加新Agent
1. 在 `official_agents/` 中添加JSON档案
2. 系统自动加载，无需修改代码

### 添加新功能
1. **总裁办扩展**：`opc_manager/core.py`
2. **新API路由**：`web_interface/routes/` 下新建Blueprint
3. **新MCP能力**：`opc_hr/` 下新建模块，在core.py中集成

## 许可证

Apache License 2.0
