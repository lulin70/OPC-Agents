# OPC-Agents v0.1.9-delta 七角色批判性Review报告

**日期**: 2026-05-10
**版本**: v0.1.9-delta
**审查范围**: opc_manager/ 全部核心模块 + frontend/app.py + 配置/部署/文档
**审查方法**: 7角色各自维度批判性审查
**前置数据**: 470测试100%通过, 7维度代码走读综合评分94.6

---

## 📊 综合评估

| 角色 | P0 | P1 | P2 | 综合评分 |
|------|----|----|-----|---------|
| 🏗️ 架构师 | 2 | 3 | 2 | 88/100 |
| 📋 产品经理 | 1 | 3 | 2 | 82/100 |
| 🔒 安全专家 | 2 | 2 | 1 | 85/100 |
| 🧪 测试专家 | 1 | 3 | 2 | 86/100 |
| 💻 开发者 | 1 | 4 | 3 | 87/100 |
| 🚀 DevOps | 1 | 2 | 2 | 83/100 |
| 🎨 UI设计师 | 0 | 3 | 3 | 80/100 |
| **合计** | **8** | **20** | **15** | **84.4/100** |

---

## 🏗️ 架构师 Review

### P0-ARCH-01: AgentLoop与TaskEngineV3双入口架构混乱
- **位置**: `frontend/app.py:469-569` + `opc_manager/task_engine_adapter.py`
- **问题**: 系统存在两套执行路径（AgentLoop和TaskEngineV3），通过环境变量`OPC_USE_AGENT_LOOP`切换。这导致：(1) 用户无法在UI中直观理解两种模式的差异；(2) 降级路径在AgentLoop失败时跳回TaskEngineV3，但两者的输入/输出格式不完全兼容；(3) TaskEngineAdapter作为桥接层增加了不必要的复杂度
- **影响**: 架构复杂度上升，维护成本翻倍，新开发者理解困难
- **修复建议**: v0.2.0统一为AgentLoop单入口，TaskEngineV3作为内部实现细节而非并列入口。移除`OPC_USE_AGENT_LOOP`环境变量

### P0-ARCH-02: 三贤者LLM调用无全局并发控制
- **位置**: `opc_manager/strategist_brain.py:262` + `opc_manager/reflector_brain.py:206`
- **问题**: 策略脑和反思脑各自独立调用LLM，没有全局并发限制。当多个用户同时提交任务时，LLM API调用可能超出速率限制，导致批量429错误。PerformanceMonitor的LRUCache仅缓存相同prompt，不控制并发
- **影响**: 多用户场景下可能触发API限流，导致服务降级
- **修复建议**: 引入全局LLM调用信号量（如`asyncio.Semaphore(5)`），限制同时进行的LLM调用数

### P1-ARCH-01: ConsensusEngine决策日志仅本地JSONL，无查询API
- **位置**: `opc_manager/consensus_engine.py:98-110`
- **问题**: 共识决策日志写入`data/consensus_logs/`目录的JSONL文件，但没有查询接口。随着使用量增长，日志文件会无限增长，且无法检索历史决策
- **影响**: 运维无法追溯决策历史，磁盘空间可能被占满
- **修复建议**: 添加日志轮转（按大小/时间）和查询API

### P1-ARCH-02: SkillMarketplace数据持久化用JSON文件，无事务保证
- **位置**: `opc_manager/skill_marketplace.py` 数据存储
- **问题**: 技能市场数据存储在JSON文件中，并发写入可能导致数据丢失或损坏。没有WAL/事务机制
- **影响**: 多实例部署时数据不一致
- **修复建议**: v0.2.0迁移到SQLite，至少添加文件锁

### P1-ARCH-03: MCP协议实现缺少会话管理
- **位置**: `opc_manager/mcp_transport.py:40-70`
- **问题**: SSE端点没有会话标识，所有客户端共享同一个MCP Server实例。无法区分不同客户端的请求上下文
- **影响**: 多客户端同时使用MCP时可能交叉污染
- **修复建议**: 添加session_id到SSE连接，每个连接独立的MCPServer实例

### P2-ARCH-01: PluginSandbox受限import列表硬编码
- **位置**: `opc_manager/plugin_system.py`
- **问题**: 沙箱允许的import列表硬编码在代码中，扩展需要修改源码
- **修复建议**: 提取到配置文件

### P2-ARCH-02: PerformanceMonitor指标仅内存存储，重启丢失
- **位置**: `opc_manager/performance_monitor.py`
- **问题**: 性能指标存储在内存中，进程重启后全部丢失
- **修复建议**: 添加定期持久化到磁盘

---

## 📋 产品经理 Review

### P0-PM-01: 技能市场/编辑器/MCP/插件功能在UI中不可见
- **位置**: `frontend/app.py` — 主界面
- **问题**: v0.1.9-delta新增了技能市场API、MCP协议、插件系统、性能监控等能力，但用户在Streamlit UI中只能看到"技能编辑器"按钮。技能市场没有浏览/搜索UI，MCP没有配置入口，插件没有管理界面，性能监控没有仪表盘
- **影响**: 用户无法感知和使用这些新功能，投入的开发资源无法转化为用户价值
- **修复建议**: v0.2.0优先添加技能市场浏览UI和性能监控仪表盘

### P1-PM-01: 质量/快速模式切换不直观
- **位置**: `frontend/app.py:738-746`
- **问题**: 执行模式切换通过`os.environ`设置全局环境变量，这意味着：(1) 切换影响所有用户（多用户场景下互相干扰）；(2) 用户不理解两种模式的具体差异
- **影响**: 多用户场景下模式切换冲突
- **修复建议**: 模式切换应基于session_state而非环境变量

### P1-PM-02: 错误提示技术化，用户难以理解
- **位置**: `frontend/app.py:1181-1230` FRIENDLY_ERRORS
- **问题**: 虽然有友好错误映射，但AgentLoop降级到TaskEngineV3时的错误信息仍然是技术性的（如"AgentLoop execution failed"）
- **影响**: 非技术用户困惑
- **修复建议**: 所有面向用户的错误信息统一经过友好映射

### P1-PM-03: 缺少用户引导教程
- **位置**: 整体用户体验
- **问题**: 新用户首次使用时，不知道三贤者架构如何工作、质量模式和快速模式的区别、如何创建自定义技能
- **影响**: 用户上手门槛高
- **修复建议**: 添加交互式引导教程

### P2-PM-01: 成果物缺少版本对比功能
- **问题**: 多轮对话修改成果物时，无法对比前后版本差异
- **修复建议**: 添加diff视图

### P2-PM-02: 缺少使用统计和反馈闭环
- **问题**: 质量反馈按钮(👍/👎)的数据没有用于自动优化系统
- **修复建议**: 反馈数据驱动技能权重调整

---

## 🔒 安全专家 Review

### P0-SEC-01: 技能市场API Key以SHA256哈希存储但无盐值
- **位置**: `opc_manager/skill_marketplace.py` — API Key存储
- **问题**: API Key使用SHA256哈希存储，但没有使用随机盐值。相同API Key总是产生相同哈希，容易受到彩虹表攻击。且API Key在创建时以明文返回一次，如果被中间人截获则完全暴露
- **影响**: API Key安全性不足
- **修复建议**: 使用bcrypt或PBKDF2+随机盐存储API Key哈希，传输使用HTTPS

### P0-SEC-02: MCP SSE端点无认证
- **位置**: `opc_manager/mcp_transport.py:40-55`
- **问题**: SSE端点`/sse`和`/messages`没有任何认证机制。任何人都可以连接并发送MCP请求，执行任意技能
- **影响**: 暴露在公网时被未授权访问
- **修复建议**: 添加Bearer Token认证或API Key认证

### P1-SEC-01: LLM Prompt注入防护不完整
- **位置**: `opc_manager/strategist_brain.py:148-180` + `opc_manager/reflector_brain.py`
- **问题**: 策略脑的LLM prompt中对用户输入做了sanitize（截断500字符+去除markdown标记），但反思脑的LLM prompt中直接使用了`content[:800]`，没有去除markdown标记。攻击者可以通过精心构造的执行结果注入反思脑的LLM调用
- **影响**: 反思脑可能被注入恶意指令
- **修复建议**: 反思脑的LLM prompt中对content也做sanitize

### P1-SEC-02: 插件沙箱import限制可被绕过
- **位置**: `opc_manager/plugin_system.py` — PluginSandbox
- **问题**: 沙箱通过限制`__import__`和`import`语句来控制可用模块，但Python的`importlib.import_module()`、`__builtins__`、`getattr`等机制可能绕过限制
- **影响**: 恶意插件可能访问文件系统或网络
- **修复建议**: 使用subprocess隔离而非同进程沙箱，或使用RestrictedPython

### P2-SEC-01: FastAPI CORS配置过于宽松
- **位置**: `opc_manager/skill_marketplace_api.py:34-38`
- **问题**: `allow_origins=["*"]`允许任何来源的跨域请求
- **修复建议**: 限制为已知域名

---

## 🧪 测试专家 Review

### P0-TEST-01: LLM驱动路径测试覆盖不足
- **位置**: `tests/test_delta_integration.py`
- **问题**: 470个测试中，策略脑LLM驱动(`_understand_intent_with_llm`)和反思脑LLM驱动(`_evaluate_with_llm`)的测试都是mock LLM响应。没有真实LLM调用的端到端测试。当LLM返回非预期格式（如非JSON、截断JSON、空响应）时，系统的鲁棒性未经验证
- **影响**: LLM驱动路径在生产环境可能因LLM响应格式问题而崩溃
- **修复建议**: 添加LLM响应异常格式的专项测试（空响应、非JSON、截断JSON、超长响应、包含代码块的JSON）

### P1-TEST-01: 技能市场API缺少集成测试
- **位置**: `tests/test_delta_integration.py`
- **问题**: 技能市场API的测试仅验证了SkillMarketplace类的逻辑，没有启动FastAPI服务进行HTTP级别的集成测试
- **影响**: API端点的认证、CORS、错误处理未在真实HTTP环境下验证
- **修复建议**: 使用`httpx.AsyncClient` + `TestClient`进行API集成测试

### P1-TEST-02: MCP传输层无测试
- **位置**: `opc_manager/mcp_transport.py`
- **问题**: MCP的SSE和stdio传输层没有任何测试
- **影响**: 传输层bug可能在生产环境才暴露
- **修复建议**: 添加SSE连接测试和stdio消息传递测试

### P1-TEST-03: 插件系统缺少安全边界测试
- **位置**: `opc_manager/plugin_system.py`
- **问题**: 插件沙箱的安全限制（禁止文件系统/网络/子进程访问）没有测试验证
- **影响**: 沙箱逃逸可能在生产环境才被发现
- **修复建议**: 添加恶意插件测试用例（尝试访问文件系统、网络、环境变量）

### P2-TEST-01: 性能监控缺少SLA违规测试
- **问题**: SLA违规告警逻辑没有测试
- **修复建议**: 添加SLA阈值触发的单元测试

### P2-TEST-02: 缺少并发场景测试
- **问题**: 多用户同时提交任务的场景没有测试
- **修复建议**: 添加并发执行的集成测试

---

## 💻 开发者 Review

### P0-CODE-01: asyncio事件循环使用模式不安全
- **位置**: `frontend/app.py:530-540`
- **问题**: 前端使用`asyncio.new_event_loop()` + `loop.run_until_complete()`执行异步AgentLoop。在Streamlit的同步上下文中创建新事件循环，如果AgentLoop内部创建了后台任务（如审计日志写入），这些任务可能在loop关闭时被取消
- **影响**: 审计日志可能丢失
- **修复建议**: 使用`asyncio.run()`或确保所有后台任务在loop关闭前完成

### P1-CODE-01: strategist_brain.py中LLM响应解析脆弱
- **位置**: `opc_manager/strategist_brain.py:195-240`
- **问题**: `_understand_intent_with_llm`使用`re.search(r'\{[\s\S]*\}', llm_response)`提取JSON，但这个正则匹配最外层的`{}`，如果LLM响应中包含多个JSON对象或代码块中的`{}`，会匹配到错误的内容
- **影响**: LLM返回包含代码示例时可能解析错误
- **修复建议**: 使用更精确的JSON提取策略（如找到第一个`{`后逐字符匹配括号层级）

### P1-CODE-02: reflector_brain.py的LLM评估同样存在JSON解析脆弱性
- **位置**: `opc_manager/reflector_brain.py:170-210`
- **问题**: 与策略脑相同的问题，`re.search(r'\{[\s\S]*\}', llm_response)`可能匹配到错误内容
- **影响**: 评估结果解析错误可能导致错误的修正策略
- **修复建议**: 同P1-CODE-01

### P1-CODE-03: performance_monitor.py的LRUCache非线程安全
- **位置**: `opc_manager/performance_monitor.py:40-79`
- **问题**: LRUCache使用普通dict实现，在多线程环境下（AsyncTaskExecutor的worker线程）可能产生竞态条件
- **影响**: 缓存数据可能损坏
- **修复建议**: 添加threading.Lock

### P1-CODE-04: mcp_transport.py的StdioTransport没有优雅关闭
- **位置**: `opc_manager/mcp_transport.py:80-110`
- **问题**: StdioTransport的run()方法是无限循环读取stdin，没有提供关闭机制。当需要停止MCP服务时，只能通过kill信号
- **影响**: 优雅关闭时可能丢失未处理的消息
- **修复建议**: 添加shutdown_event

### P2-CODE-01: 多处重复的JSON提取逻辑
- **位置**: strategist_brain.py + reflector_brain.py
- **问题**: 两个文件都有相同的`re.search(r'\{[\s\S]*\}', ...)` + `json.loads()`逻辑
- **修复建议**: 提取为公共工具函数

### P2-CODE-02: skill_marketplace_api.py缺少请求体大小限制
- **位置**: `opc_manager/skill_marketplace_api.py`
- **问题**: 没有限制POST请求体大小，恶意用户可以发送超大请求
- **修复建议**: 添加请求体大小中间件

### P2-CODE-03: install.sh中数据目录不完整
- **位置**: `install.sh:97-107`
- **问题**: 创建了data/schedules等目录，但没有创建data/consensus_logs/（共识引擎需要）和plugins/（插件系统需要）
- **修复建议**: 补充缺失目录

---

## 🚀 DevOps Review

### P0-DEVOPS-01: 无Docker化部署方案
- **位置**: 项目根目录
- **问题**: 项目没有Dockerfile和docker-compose.yml。技能市场API(FastAPI)和主服务(Streamlit)需要分别部署，但没有容器化方案
- **影响**: 部署复杂，环境一致性问题
- **修复建议**: 添加Dockerfile（多阶段构建）和docker-compose.yml（Streamlit + FastAPI + 可选Ollama）

### P1-DEVOPS-01: 无健康检查端点
- **位置**: `frontend/app.py` — Streamlit服务
- **问题**: Streamlit主服务没有健康检查端点。MCP的SSE端点有`/health`，但主服务没有
- **影响**: 容器编排无法判断服务健康状态
- **修复建议**: 添加`/_stcore/health`或自定义健康检查

### P1-DEVOPS-02: 日志无轮转策略
- **位置**: `opc_manager/monitoring.py` + `opc_manager/tool_system.py`
- **问题**: 审计日志写入JSONL文件，没有轮转策略。随着使用量增长，日志文件会无限增长
- **影响**: 磁盘空间耗尽
- **修复建议**: 添加按大小/时间的日志轮转

### P2-DEVOPS-01: 无CI/CD配置
- **位置**: 项目根目录
- **问题**: 没有GitHub Actions或其他CI/CD配置
- **修复建议**: 添加`.github/workflows/ci.yml`

### P2-DEVOPS-02: pyproject.toml缺少可选依赖组
- **位置**: `pyproject.toml`
- **问题**: FastAPI/uvicorn/sse-starlette是技能市场API和MCP的依赖，但不在核心依赖中，也没有可选依赖组
- **修复建议**: 添加`[marketplace]`和`[mcp]`可选依赖组

---

## 🎨 UI设计师 Review

### P1-UI-01: 侧边栏功能堆叠过多，信息架构混乱
- **位置**: `frontend/app.py` — 侧边栏
- **问题**: 侧边栏堆叠了：执行模式切换、API配置、技能编辑器、历史记录等多个功能区域。随着功能增加，侧边栏越来越长，用户难以快速找到需要的功能
- **影响**: 用户迷失在功能列表中
- **修复建议**: 使用折叠面板或标签页组织侧边栏功能

### P1-UI-02: 执行进度缺乏可视化
- **位置**: `frontend/app.py` — 任务执行区域
- **问题**: 三贤者架构的执行过程（Plan→Act→Observe→Reflect）在UI中只显示简单的spinner。用户无法看到当前处于哪个阶段、每个阶段花了多长时间
- **影响**: 用户焦虑等待，不知道系统在做什么
- **修复建议**: 添加4阶段进度条（Plan→Act→Observe→Reflect），每阶段显示耗时

### P1-UI-03: 技能编辑器UI过于简陋
- **位置**: `frontend/app.py` — 技能编辑器区域
- **问题**: 技能编辑器只有一个创建表单和简单列表，缺少：参数配置UI、模板预览、技能测试、发布到市场等交互
- **影响**: 自定义技能功能体验差
- **修复建议**: 添加多步骤编辑器（定义→配置→测试→发布）

### P2-UI-01: 缺少暗色模式
- **问题**: 长时间使用时白色背景对眼睛不友好
- **修复建议**: 添加暗色模式切换

### P2-UI-02: 成果物预览缺少格式化渲染
- **问题**: Markdown成果物以纯文本显示，没有渲染为格式化内容
- **修复建议**: 使用st.markdown渲染预览

### P2-UI-03: 缺少键盘快捷键
- **问题**: 常用操作（提交、暂停、下载）没有键盘快捷键
- **修复建议**: 添加常用快捷键支持

---

## 📋 整改优先级排序

### 🔴 P0 — 必须立即修复（8项）

| 编号 | 角色 | 问题 | 风险 |
|------|------|------|------|
| P0-ARCH-01 | 架构师 | 双入口架构混乱 | 维护成本翻倍 |
| P0-ARCH-02 | 架构师 | LLM调用无全局并发控制 | 多用户限流 |
| P0-PM-01 | 产品经理 | 新功能UI不可见 | 用户无法使用 |
| P0-SEC-01 | 安全专家 | API Key存储无盐值 | 彩虹表攻击 |
| P0-SEC-02 | 安全专家 | MCP SSE无认证 | 未授权访问 |
| P0-TEST-01 | 测试专家 | LLM驱动路径测试不足 | 生产环境崩溃 |
| P0-CODE-01 | 开发者 | asyncio事件循环不安全 | 审计日志丢失 |
| P0-DEVOPS-01 | DevOps | 无Docker化方案 | 部署困难 |

### 🟡 P1 — 本迭代修复（20项）

| 编号 | 问题摘要 |
|------|---------|
| P1-ARCH-01 | 共识日志无查询API |
| P1-ARCH-02 | 技能市场JSON无事务 |
| P1-ARCH-03 | MCP无会话管理 |
| P1-PM-01 | 模式切换用环境变量 |
| P1-PM-02 | 错误提示技术化 |
| P1-PM-03 | 缺少用户引导 |
| P1-SEC-01 | 反思脑Prompt注入 |
| P1-SEC-02 | 插件沙箱可绕过 |
| P1-TEST-01 | 技能市场无API集成测试 |
| P1-TEST-02 | MCP传输层无测试 |
| P1-TEST-03 | 插件沙箱无安全测试 |
| P1-CODE-01 | LLM JSON解析脆弱 |
| P1-CODE-02 | 反思脑JSON解析脆弱 |
| P1-CODE-03 | LRUCache非线程安全 |
| P1-CODE-04 | StdioTransport无优雅关闭 |
| P1-DEVOPS-01 | 无健康检查端点 |
| P1-DEVOPS-02 | 日志无轮转策略 |
| P1-UI-01 | 侧边栏信息架构混乱 |
| P1-UI-02 | 执行进度缺乏可视化 |
| P1-UI-03 | 技能编辑器过于简陋 |

### 🟢 P2 — 后续迭代优化（15项）

略，见各角色P2部分。

---

## 🎯 v0.2.0 建议重点

基于7角色Review，v0.2.0应聚焦：

1. **架构统一**：消除双入口，AgentLoop为唯一入口
2. **安全加固**：MCP认证 + API Key加盐 + 反思脑Prompt注入防护
3. **UI补全**：执行进度可视化 + 技能市场浏览 + 性能监控仪表盘
4. **测试补全**：LLM异常响应测试 + MCP/插件集成测试
5. **部署完善**：Docker化 + CI/CD + 健康检查
