# OPC-Agents

**Version**: 0.0.1

> **你对总裁办下一个指令，总裁办调动全公司 18 个专业部门、180+AI 员工协同合作完成。**

一个为一人公司（OPC）设计的 AI 多代理操作系统。你不需要逐个调用 AI 工具——只需像给 CEO 下指令一样告诉总裁办你想做什么，系统会自动分解任务、调度合适的 AI 部门、协同完成，并把结果汇报给你。

## 工作方式

```
你 → 总裁办 (意图判断) → 双层上下文注入 → 三贤者结构化决策 → 动态任务分解
→ 智能角色匹配 → 用户确认计划 → DAG 依赖调度 → Agent 协同执行 (上下文传递)
→ 完成校验 → 经验沉淀 → 结果汇报
```

**一句话：你是 CEO，总裁办是你的 AI Chief of Staff，18 个专业部门是你的 AI 团队，系统越用越聪明。**

## 核心能力

**智能调度与决策**
- **总裁办智能调度**：4 种意图判断（闲聊/搜索/任务/追问），模糊需求主动追问
- **三贤者决策系统**：战略/执行/创新三视角结构化评估（资源/关系/风险/战略/行动项），已解耦为独立模块
- **动态任务分解**：基于三贤者评估动态生成执行步骤（含依赖关系/技能需求/验收标准）
- **智能角色匹配**：三层匹配策略（历史表现 30%+ 技能匹配 40%+ 关键词 30%），自动找到最佳 Agent

**双层上下文管理**（参考 TraeMultiAgentSkill + Memory Classification Engine，已集成到主流程）
- **全局上下文（长期记忆）**：知识库 + 经验库（6 种类型）+ 用户画像，跨任务持久化
- **任务上下文（工作记忆）**：任务定义 + 思考记录 + 产出物 + 注入引用
- **双向同步**：任务开始时注入相关知识（sync_global_to_task），任务完成时沉淀经验（sync_task_to_global）
- **经验分类**：6 种类型（user_preference/correction/decision/task_pattern/agent_optimization/skill_usage）
- **权重计算**：4 维度（置信度 40%+ 时效性 30%+ 使用频率 20%+ 来源可靠性 10%）
- **冲突检测**：自动识别矛盾经验，智能处理（权重比较/标记过时/待用户确认）
- **遗忘机制**：基于时间衰减 + 使用频率，低权重经验自动淘汰
- **越用越聪明**：每次任务都积累知识和经验，后续任务自动复用高价值经验

**任务执行与质量保障**
- **工作流引擎**：WorkflowDefinition→Instance→Step 状态机，支持条件分支、${variable} 模板、暂停/恢复
- **DAG 依赖调度**：任务间依赖关系管理，循环检测，按依赖顺序执行
- **TaskScheduler 抽象层**：统一调度接口（schedule/cancel/pause/resume），支持多种调度策略
- **步骤自动重试**：失败自动重试（可配置次数），重试耗尽才标记 failed
- **循环控制器**：迭代计数器 + 最大迭代限制 + 退出条件 + 进度持久化
- **上下文传递**：后续 Agent 获取前序 Agent 的实际产出物内容（非路径字符串）
- **完成自动校验**：产出物存在/非空/验收标准/GLM 质量评估，4 项检查
- **断点恢复**：系统崩溃后可从断点继续，不丢失进度
- **交接文档**：Agent 间标准化交接（已完成工作/当前状态/下一步骤/注意事项）

**智能化改进（Phase 1-3 已完成）**
- **错误分类与处理**：4 类错误智能处理（自动重试/建议重试/停止/高风险），50+ 错误模式识别
- **通知分级系统**：P0-P3 四级通知，多渠道（站内/邮件/微信），免打扰时段（22:00-08:00）
- **调度透明化**：思考过程可视化（类似 Trae/DeepSeek），HTML/Markdown/JSON 输出，可折叠展示
- **优先级智能推荐**：3 维度评分（截止时间 40%+ 依赖 30%+ 业务价值 30%），自动推荐优先级
- **资源优化建议**：CPU/内存/磁盘实时监控，健康度评分（0-100），CPU>95% 自动暂停低优先级任务
- **任务历史增强**：全文搜索（任务名称/描述/结果），自动归档（>100 个或>7 天），JSON/CSV 导出
- **场景化模式**：简单模式（默认，高自动化）/高级模式（完全控制），运行时切换

**多任务并发管理**
- **并发执行**：不同 Agent 可同时执行任务，同 Agent 串行执行（避免资源冲突）
- **6 级优先级**：CRITICAL(10)/URGENT(8)/HIGH(6)/MEDIUM(4)/LOW(2)/BACKGROUND(0)
- **优先级调度**：高优先级优先，同优先级按提交时间排序（FIFO），支持运行时调整
- **资源隔离**：任务间互不影响，独立工作目录
- **实时监控**：CPU/内存/磁盘使用率，任务进度，Agent 状态（idle/busy/paused/error）

**事件总线**
- **EventBus**：解耦模块间依赖，支持事件发布/订阅机制
- **任务事件**：task_completed/task_failed 事件，HR 模块自动响应

**配置管理**
- **配置热更新**：监控 config.toml 变化，自动重载配置，无需重启服务
- **集中配置**：所有硬编码值已提取为配置项，便于调优

**18 个专业部门**，覆盖设计/开发/营销/财务/运营/游戏/空间计算等领域
**180+ 专业 AI 员工**（来自官方 Agency-Agents 项目 + A2A 协议）
**网页搜索**：DuckDuckGo 免费搜索，获取最新信息辅助决策
**MCP GitHub 集成**：搜索/获取/导入外部 Agent 和 Skill（含代码安全审核）
**多模型支持**：GLM、OpenAI、Anthropic、Google、Azure、本地模型
**财务部**：Token 监控、消费报告、预算告警
**系统监控**：CPU/内存/磁盘、组件健康、任务统计、告警
**SSE 实时推送**：任务完成/失败事件实时推送到前端
**深色主题**：CSS 变量驱动，🌓一键切换，localStorage 持久化
**响应式布局**：768px/480px 断点，侧边栏自动折叠/隐藏

## 目录结构

```
OPC-Agents/
├── config.toml.sample        # 配置文件模板
├── OPCstart.sh               # 一键启动脚本
├── CODE_MAP.md               # 代码地图（架构/模块/API）
├── ARCHITECTURE.md           # 系统架构设计文档
├── official_agents/          # 官方 Agent 档案（JSON 定义）
├── task_workspaces/          # 任务工作目录（自动创建）
├── templates/                # HTML 页面模板
├── temp-use/                 # 已归档的旧模块
├── opc_manager/              # 核心管理器
│   ├── core.py               # OPCManager（系统大脑）
│   ├── communication_manager.py # 代理间通信
│   ├── task_manager.py       # 任务管理（CRUD/工作目录）
│   ├── task_executor.py      # 异步任务执行
│   ├── agent_manager.py      # 官方 Agent 查询
│   ├── three_sages.py        # 三贤者决策
│   ├── context_manager.py    # 双层上下文（知识库 + 经验库 + 用户画像）
│   ├── completion_checker.py # 任务完成自动校验
│   ├── dag_scheduler.py      # DAG 依赖调度
│   ├── scheduler.py          # TaskScheduler 抽象层
│   ├── event_bus.py          # 事件总线
│   ├── checkpoint_manager.py # 断点恢复 + 交接文档
│   ├── workflow_engine.py    # 工作流引擎（状态机 + 条件分支 + 变量模板）
│   ├── loop_controller.py    # 长程任务循环控制器
│   ├── personal_assistant.py # 个人助理
│   ├── architecture.py       # 三层架构
│   └── config.py             # 配置管理（支持热更新）
├── model_integration/        # AI 模型集成
│   ├── model_manager.py      # 多模型管理
│   └── model_adapters.py     # GLM/OpenAI/Anthropic/Google 适配器
├── opc_hr/                   # 人事部
│   ├── hr_enhancement.py     # HR 核心（Agent 管理/技能匹配）
│   ├── role_matcher.py       # 智能角色匹配
│   ├── skill_manager.py      # 技能管理
│   ├── department_manager.py # 部门管理
│   ├── mcp_integration.py    # MCP GitHub 集成
│   ├── installation_manager.py # 安装管理
│   ├── web_search.py         # 网页搜索（DuckDuckGo）
│   ├── a2a_api.py            # A2A API
│   ├── a2a_protocol.py       # A2A 协议
│   └── a2a_integration.py    # A2A 集成
├── opc_finance/              # 财务部
│   ├── finance_manager.py    # Token 监控/消费报告/预算告警
│   └── finance_routes.py     # 财务 API 路由
├── monitoring/               # 系统监控
│   ├── monitor.py            # 监控器
│   ├── health_check.py       # 健康检查
│   ├── metrics.py            # 指标收集
│   └── alerts.py             # 告警管理
├── message_queue/            # 消息队列
├── data_storage/             # 数据存储（SQLite）
├── task_deliverables/        # 任务交付物
├── web_interface/            # Web 界面（Flask，端口 5009）
│   ├── app.py                # 主应用
│   └── routes/               # 11 个路由模块
└── docs/                     # 文档
```

## 安装

### 方法 1：一键安装（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/your-org/OPC-Agents.git
cd OPC-Agents

# 2. 运行一键安装脚本
chmod +x install.sh
./install.sh

# 3. 配置 API 密钥
vim config.toml

# 4. 启动服务
./OPCstart.sh
```

**详细安装指南**: [INSTALL.md](INSTALL.md)

---

### 方法 2：手动安装

```bash
# 1. 安装依赖
pip3 install requests toml flask ddgs

# 2. 创建配置文件
cp config.toml.sample config.toml

# 3. 配置 API 密钥（必填）
vim config.toml

# 4. 启动服务
python3 web_interface/app.py
```

---

### 配置 API 密钥（必填）

**至少配置一个模型**，推荐智谱 AI GLM（国内可用）：

```toml
[models.glm]
api_key = "sk.xxxxxxxxxxxxxxxxxxxxxxxx"  # ← 替换为你的密钥
model = "glm-4.7"
```

**获取 GLM API Key**:
1. 访问 https://open.bigmodel.cn/
2. 注册/登录账号
3. 进入控制台 → API 密钥管理
4. 创建 API 密钥
5. 复制密钥到配置文件

**更多配置选项**: [INSTALL.md](INSTALL.md#配置说明)

## 使用

### 一键启动

```bash
chmod +x OPCstart.sh
./OPCstart.sh
```

访问 **http://localhost:5009**

### Web 界面功能

| 页面 | URL | 功能 |
|------|-----|------|
| 总裁办 | `/` | 对话（闲聊/搜索/任务）、任务管理、HR 推荐 |
| 财务部 | `/finance` | 消费报告、预算设置、告警 |
| 系统监控 | `/monitoring` | CPU/内存/磁盘、组件状态、任务统计 |
| 代理管理 | `/agent_management` | Agent 列表、创建/编辑/删除 |
| 部门详情 | `/department/<名称>` | 部门任务列表、完成/失败操作 |

### 任务管理

- **创建**：总裁办页面右上角"新建任务"按钮
- **重命名**：hover 任务卡片 → ✏️按钮（行内编辑，Enter 确认）
- **删除**：hover 任务卡片 → 🗑️按钮（删除任务 + 工作目录）
- **打开工作目录**：hover 任务卡片 → 📁按钮（Finder 打开）

### 总裁办对话模式

```
用户消息 → GLM 判断意图
├── 闲聊 → 直接友好回复
├── 搜索 → DuckDuckGo 搜索 → GLM 基于搜索结果回答
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
| `GET /api/agents/` | Agent 列表 |
| `GET /api/finance/dashboard` | 财务仪表盘 |
| `GET /api/finance/report?period=daily` | 消费报告 |
| `GET /api/health/` | 健康检查 |
| `GET /api/mcp/web/search?q=xxx` | 网页搜索 |
| `GET /api/mcp/agents/search?q=xxx` | GitHub Agent 搜索 |
| `GET /api/progress/stream` | SSE 实时进度 |

## 配置

`config.toml` 主要配置项：

```toml
[models.glm]
api_key = "your_glm_api_key"    # 必需
model = "glm-4.7"

[mcp]
github_token = ""                # 可选，提升 GitHub API 频率

[finance]
monthly_budget = 100             # 月预算（元）
```

## 扩展系统

### 添加新 Agent
1. 在 `official_agents/` 中添加 JSON 档案
2. 系统自动加载，无需修改代码

### 添加新功能
1. **总裁办扩展**：`opc_manager/core.py`
2. **新 API 路由**：`web_interface/routes/` 下新建 Blueprint
3. **新 MCP 能力**：`opc_hr/` 下新建模块，在 core.py 中集成

## 测试

```bash
python3 -m pytest tests/ -v
```

**测试覆盖**：
- 核心流程：14 个测试
- 智能化改进：52 个测试（错误处理/通知系统/优先级推荐等）
- 技能系统：20 个测试（网页搜索/文档处理/内容摘要等）
- 工作流引擎：10 个测试
- API 回归：6 个测试
- **总计**：225 个测试通过，4 个跳过，0 个失败

## 许可证

Apache License 2.0
