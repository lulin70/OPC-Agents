# 🚀 OPC-Agents — 一人公司的 AI 执行团队

> **版本**: v0.3.10 | **状态**: Beta | **许可**: MIT

[![Beta](https://img.shields.io/badge/status-beta-blue)](https://github.com/lulin70/OPC-Agents)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI](https://img.shields.io/pypi/v/opc-agents)](https://pypi.org/project/opc-agents/)

---

**语言**: **中文** | [English](README-EN.md) | [日本語](README-JP.md)

---

## 30 秒了解 OPC-Agents

**🎯 一句话**：一人公司的 AI 执行团队——你说需求，它出成果。

**⚡ 核心流程**：
```
你说需求 → AI 分析+搜索+生成 → 你拿到成果物（报告/方案/文案/邮件...）
```

**🚀 3 步上手**：
```bash
pip install opc-agents          # 1. 安装
opc-agents                      # 2. 启动
# 3. 输入"帮我写一份周报" → 拿到成果物
```

---

## 🆕 v0.3.5 亮点

> 完整变更见 [CHANGELOG.md](CHANGELOG.md)，架构设计见 [docs/architecture/PARALLEL_SAGES_DESIGN.md](docs/architecture/PARALLEL_SAGES_DESIGN.md)。

- **⚡ 三贤者并行投票架构回归**：从串行流水线（3×RTT）改为并行投票（1×RTT），延迟降低 3 倍。借鉴 EVA MAGI 三贤者同步投票 + 少数派报告机制，关键决策点前置共识保护。
- **🎯 聚焦 3 个核心技能**：邮件 / 财务 / 报告。冻结 11 个非核心技能（详见 [docs/spec/SKILL_FREEZE_LIST.md](docs/spec/SKILL_FREEZE_LIST.md)），把每个核心技能做到真正好用。
- **🧠 IntentRouter 三路智能路由**：SIMPLE / COMPLEX / GREETING 三路分类，简单任务直接绕过三贤者，快又省；复杂任务才进入并行投票，质量有保障。
- **🛡 关键决策点前置共识保护**：ConsensusEngine 从"事后补救"改为"事前把关"，ExecutorBrain 给真意见（删除假意见规则），ReflectorBrain 前置预判 + 少数派报告。
- **📊 质量大幅提升**：总覆盖率 62.87%，核心 skill 专项测试覆盖率 email_skill 99% / finance_skill 100%（专项测试 `pytest --cov` 口径，全量测试套件口径下 email_skill 17.0% / finance_skill 14.5%，详见 `coverage.json`；Sprint 2 已从 16.96%/14.46% 基线提升专项覆盖率）；新增 7 个真实 LLM E2E 测试（CI 每周一自动运行）。
- **🌐 i18n 重构**：3857 行 → 133 行逻辑层 + JSON 化，向后兼容，维护成本骤降。

> 🧪 准备试用？请阅读 [docs/guides/USER_TRIAL_GUIDE.md](docs/guides/USER_TRIAL_GUIDE.md)（3 分钟完成配置），演示话术见 [docs/guides/DEMO_SCRIPTS.md](docs/guides/DEMO_SCRIPTS.md)，反馈表见 [docs/guides/FEEDBACK_FORM.md](docs/guides/FEEDBACK_FORM.md)。

---

## 这是什么

OPC-Agents（One-Person Company Agents）是一个**为独立创业者、自由职业者和独立创作者设计的智能任务执行系统**。

**核心理念：告诉系统你想要什么结果，它完成工作并把文件交付给你。**

不是聊天机器人。不是建议引擎。它是一个**把事情做完的执行者**。

## 它能帮你做什么

| 你说 | 它交付 |
|------|--------|
| "帮我收集OPC公司趋势" | 🔍 研究报告（真实搜索+来源链接+结构化整理） |
| "帮我写Q2营销方案" | ✍ 完整方案（SMART目标+路线图+风险+验收标准） |
| "帮我分析竞品A" | 📊 分析报告（SWOT+行动清单+优先级排序） |
| "帮我发邮件给客户" | 📧 邮件发送（模板渲染+SMTP发送+频率限制） |
| "帮我记录一笔收入" | 💰 财务记录（自动分类+月度报表+趋势分析） |
| "帮我添加客户信息" | 👥 客户档案（加密存储+沉默预警+合作跟踪） |

---

## 核心能力

**三贤者并行投票架构**——三个 AI 角色同步投票闭环协作，关键决策前置共识保护（v0.3.0 升级，详见 [docs/architecture/PARALLEL_SAGES_DESIGN.md](docs/architecture/PARALLEL_SAGES_DESIGN.md)）：
- 🧠 **策略脑（StrategistBrain）**：理解你的意图，规划执行步骤
- ⚡ **执行脑（ExecutorBrain）**：调用技能和工具，生成成果物（v0.3.0 起给"真意见"，不再用假意见规则）
- 🔍 **反思脑（ReflectorBrain）**：评估结果质量，前置预判 + 少数派报告，不达标自动修正
- 🛡 **共识引擎（ConsensusEngine）**：三贤者并行投票（1×RTT，比串行 3×RTT 快 3 倍），关键决策点前置保护

**IntentRouter 三路智能路由**——按任务复杂度分流，省时省钱：
- 🟢 **SIMPLE**：简单任务直接执行，绕过三贤者
- 🟡 **COMPLEX**：复杂任务进入并行投票，质量有保障
- 👋 **GREETING**：问候/闲聊直接回应

**3 个核心技能**——v0.3.0 聚焦打磨，覆盖一人公司最高频场景（其余技能已冻结，详见 [docs/spec/SKILL_FREEZE_LIST.md](docs/spec/SKILL_FREEZE_LIST.md)）：
- 📧 **邮件（email）**：SMTP 发送 + 模板渲染 + 频率限制
- 💰 **财务（finance）**：收支记录 + 月度报表 + 趋势分析
- 📊 **报告（report）**：周报/月报/年报自动生成

**真实搜索**——接入 DuckDuckGo 实时搜索，不编造数据，每个结论有来源。

---

## 加速器

这些功能让核心流程**更好、更快、越用越强**：

| 加速器 | 它怎么帮你更快拿到成果 |
|--------|----------------------|
| 🧠 **跨会话记忆** | 记住你的偏好和上下文，不用每次重复说明（需 [CarryMem](https://github.com/lulin70/carrymem)，`pip install opc-agents[memory]`） |
| 🔄 **飞轮成长** | 用得越多等级越高（🌱新手→👑传奇），输出质量自动提升 |
| 🏪 **技能市场** | 搜索安装第三方技能，按需扩展能力 |
| 📚 **外接知识库** | 接入 Obsidian/语雀/飞书/Notion/思源笔记，AI 参考你的私有资料 |
| 📜 **规则引擎** | 失败经验自动提炼为规则，同类错误不再犯 |
| ↩ **撤销机制** | 操作可回退，放心大胆用 |
| 🌐 **三语切换** | 中文/英文/日文界面一键切换 |
| 🧊 **LLM 缓存** | 相同问题不重复调用，省时省钱 |

## 生态工具

遇到特定场景？搭配使用效果更好：

| 场景 | 推荐工具 | 说明 |
|------|---------|------|
| 想要 AI 记住你的偏好 | [CarryMem](https://github.com/lulin70/carrymem) | 跨会话持久记忆引擎，`pip install opc-agents[memory]` 一键启用 |
| 有开发任务需要多角色协作 | [DevSquad](https://github.com/lulin70/DevSquad) | 7 角色 AI 团队（架构师/PM/安全/测试/开发/DevOps/UI），复杂开发任务拆解协作 |

## 架构概览

> v0.3.0 升级为三贤者并行投票架构，完整设计见 [docs/architecture/PARALLEL_SAGES_DESIGN.md](docs/architecture/PARALLEL_SAGES_DESIGN.md)，延迟对比见 [docs/internal/PARALLEL_LATENCY_REPORT.md](docs/internal/PARALLEL_LATENCY_REPORT.md)。

```
┌─────────────────────────────────────────────────────┐
│                    OPC-Agents v0.3.0                 │
├─────────────────────────────────────────────────────┤
│  用户输入                                            │
│       ↓                                              │
│  IntentRouter 三路智能路由                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ SIMPLE   │  │ COMPLEX  │  │ GREETING │          │
│  │ 直接执行  │  │ 进入投票 │  │ 直接回应 │          │
│  └────┬─────┘  └────┬─────┘  └──────────┘          │
│       ↓              ↓                              │
│  ┌─────────────────────────────────────────┐        │
│  │ 三贤者并行投票（1×RTT，延迟降低3倍）      │        │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ │        │
│  │  │ 策略脑    │ │ 执行脑    │ │ 反思脑    │ │        │
│  │  │ (真意见)  │ │ (真意见)  │ │ (前置预判)│ │        │
│  │  └─────┬────┘ └─────┬────┘ └─────┬────┘ │        │
│  │        └──────┬─────┴──────┬──────┘     │        │
│  │               ↓            ↓            │        │
│  │     ConsensusEngine（关键决策点前置保护） │        │
│  │     · 并行投票 · 少数派报告 · 冲突决策   │        │
│  └────────────────────┬────────────────────┘        │
│                       ↓                             │
├─────────────────────────────────────────────────────┤
│  3 个核心技能（v0.3.0 聚焦）                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐│
│  │ 📧 email     │ │ 💰 finance   │ │ 📊 report    ││
│  │ SMTP+模板+限频│ │ 收支+月报+趋势│ │ 周/月/年报    ││
│  └──────────────┘ └──────────────┘ └──────────────┘│
│  （其余 11 个非核心技能已冻结，见 SKILL_FREEZE_LIST） │
├─────────────────────────────────────────────────────┤
│  外部扩展                                            │
│  ┌──────────────┐  ┌──────────────┐                │
│  │ 🔌 技能市场   │  │ 🔗 MCP服务   │                │
│  └──────────────┘  └──────────────┘                │
│  ┌──────────────┐  ┌──────────────┐                │
│  │ 👤 用户画像   │  │ 🔒 数据安全  │                │
│  └──────────────┘  └──────────────┘                │
├─────────────────────────────────────────────────────┤
│  SQLite统一存储（AES加密 + 文件权限0600）             │
└─────────────────────────────────────────────────────┘
```

## 快速开始

> 🆕 **v0.3.0 试用用户**：非技术背景用户请直接阅读 [docs/guides/USER_TRIAL_GUIDE.md](docs/guides/USER_TRIAL_GUIDE.md)（图文版，3 分钟完成配置，含 API Key 获取链接和无 API Key 体验模式）。本节为开发者快速参考。

### 前提条件

- Python 3.10+
- 至少一个LLM API Key（推荐: [MOKA](https://moka-ai.com)）

### 方式一：pip 安装

```bash
# 1. 安装
pip install opc-agents==0.3.10

# 2. 安装加密依赖（推荐，用于邮件密码等敏感字段加密）
pip install cryptography

# 3. 创建工作目录并配置API Key
mkdir my-opc-workspace && cd my-opc-workspace
echo "MOKA_API_KEY=your-key-here" > .env

# （可选）使用加密存储代替明文.env
# python -m opc_manager.secure_storage set MOKA_API_KEY your-key-here

# 首次启动会自动生成 .env.local（含加密密钥，已加入gitignore保护）
# 如需手动设置加密密钥：
# echo "OPC_ENCRYPTION_KEY=$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" >> .env.local

# 4. 启动
opc-agents
```

> pip安装后，`.env`文件、成果物文件、日志文件都存放在当前工作目录。

### 方式二：源码安装（推荐开发者）

```bash
git clone https://github.com/lulin70/OPC-Agents.git
cd OPC-Agents
chmod +x scripts/install.sh scripts/start.sh
./scripts/install.sh

# 安装加密依赖
pip install cryptography

# 配置API Key
cp .env.example .env
# 编辑 .env，填入你的MOKA API Key

# 启动
./scripts/start.sh
```

### 方式三：Docker 部署

```bash
docker compose up -d
```

| 端口 | 服务 | 说明 |
|------|------|------|
| 8501 | 主应用 (Streamlit) | Web界面 |
| 8900 | 技能市场 API (FastAPI) | REST API |
| 8901 | MCP SSE 端点 | Model Context Protocol |

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPC_DATA_DIR` | 数据存储目录 | 项目根目录下的 `data/` |
| `OPC_ENCRYPTION_KEY` | AES加密密钥（**必须设置**，否则加密操作抛出RuntimeError） | 无（未设置时拒绝加密） |
| `MOKA_API_KEY` | MOKA LLM API密钥 | — |
| `GLM_API_KEY` | 智谱GLM API密钥 | — |
| `OPENAI_API_KEY` | OpenAI API密钥 | — |
| `OLLAMA_BASE_URL` | Ollama本地模型地址 | — |
| `OPC_SKIP_REFLECT` | 跳过反思阶段（快速模式） | `false` |
| `CARRYMEM_ENABLED` | 启用跨会话持久记忆 | `false` |
| `CARRYMEM_DB_PATH` | CarryMem 数据库路径 | `~/.opc-agents/memory.db` |
| `OPC_KB_ENABLED` | 启用外接知识库 | `false` |
| `OPC_KB_TYPE` | 知识库类型 | `local` |
| `OPC_KB_PATH` | 知识库路径（Obsidian/本地） | `~/knowledge` |

> ⚠ **安全提示**：`OPC_ENCRYPTION_KEY` 为必设项，未设置时 `encrypt_field()` 将抛出 `RuntimeError`，导致邮件密码、客户敏感字段等加密操作失败。请务必在 `.env` 中设置强随机密钥。

### 关于API Key

> ⚠ **OPC-Agents 不提供 LLM 服务。** 请选择适合你的 LLM 服务商，自行获取 API Key。项目不存储任何 API Key 等隐私信息。

| 后端 | 模型 | 配置环境变量 | 质量 | 获取方式 |
|------|------|-------------|------|---------|
| MOKA | Claude Sonnet 4 | `MOKA_API_KEY` | ⭐⭐⭐⭐⭐ | [moka-ai.com](https://moka-ai.com) |
| 智谱GLM | GLM-4 | `GLM_API_KEY` | ⭐⭐⭐⭐ | [open.bigmodel.cn](https://open.bigmodel.cn) |
| OpenAI | GPT-4o | `OPENAI_API_KEY` | ⭐⭐⭐⭐ | [platform.openai.com](https://platform.openai.com) |
| Ollama | 本地模型 | `OLLAMA_BASE_URL` / `OLLAMA_ENABLED` / `OLLAMA_MODEL` | ⭐⭐⭐ | [ollama.com](https://ollama.com) |

> 不配置API Key也能使用（模板模式），但内容质量有限。**强烈建议至少配置一个API Key。**

### 故障排查

| 问题 | 解决方案 |
|------|---------|
| 页面显示"模板模式" | 检查 `.env` 文件中 API Key 是否已填入 |
| 端口被占用 | `opc-agents -- --server.port 8502` |
| Python版本不对 | 需要 Python 3.10+，运行 `python3 --version` 检查 |
| 安装依赖失败 | 尝试 `pip install --upgrade pip` 后重试 |
| 加密功能不可用 | 运行 `pip install cryptography` 安装加密依赖 |

## 项目结构

```
OPC-Agents/
├── frontend/              # Streamlit前端（模块化重构）
│   ├── app.py             # 主界面路由（579行，仅路由逻辑）
│   ├── components/        # 共享组件
│   │   ├── shared.py      # 16个UI辅助函数（384行）
│   │   ├── session_utils.py      # 会话工具函数
│   │   ├── export_helpers.py     # 导出辅助函数
│   │   ├── progress_indicator.py # 进度指示器组件
│   │   ├── toast_notifications.py # Toast通知组件
│   │   ├── theme_manager.py      # 主题管理器
│   │   ├── timeline_data.py      # 时间线数据处理
│   │   ├── timeline_export.py    # 时间线导出
│   │   ├── timeline_filters.py   # 时间线过滤器
│   │   ├── undo_display.py       # 撤销操作显示
│   │   ├── undo_export.py        # 撤销操作导出
│   │   └── undo_actions.py       # 撤销操作动作
│   ├── page_modules/      # 页面模块
│   │   ├── dashboard_page.py   # 仪表盘页面（578行+模板）
│   │   ├── marketplace_page.py # 技能市场V2（547行）
│   │   └── settings_page.py    # 设置管理页（666行）
│   ├── routers/            # 路由模块
│   └── renderers/          # 渲染模块
├── opc_manager/           # 核心业务逻辑（99个.py模块）
│   ├── cli.py             # CLI入口（pip install后opc-agents命令）
│   ├── agent_loop.py      # 执行循环（Plan→Act→Observe→Reflect四阶段闭环）
│   ├── strategist_brain.py# 策略脑（意图理解+任务规划+复合意图拆解）
│   ├── executor_brain.py  # 执行脑（技能执行+工具调用+资源管理）
│   ├── reflector_brain.py # 反思脑（结果评估+自动修正策略建议）
│   ├── consensus_engine.py# 共识引擎（三贤者意见协调+冲突决策）
│   ├── skill_registry.py  # 技能注册表（单例模式，21内置技能+场景迁移+依赖注入）
│   ├── intent_types.py    # 意图类型SSOT（IntentType枚举+INTENT_KEYWORDS+INTENT_STEP_MAP+SKILL_INTENT_MAP）
│   ├── tool_system.py     # 工具调用框架（权限控制+安全防护+审计日志）
│   ├── utils.py           # 公共工具（BoundedDict+EventEmitter+日期解析）
│   │
│   ├── # === v0.2.0 新增核心模块 ===
│   ├── settings.py        # 📋 SettingsManager单例（5标签页：LLM/SMTP/API Keys/Security/Profile）
│   ├── onboarding.py      # 🚶 OnboardingManager（3步首次运行引导向导）
│   ├── error_handler.py   # 🛡 ErrorHandler（9种异常类型→中文友好消息）
│   ├── data_backup.py     # 💾 DataBackupManager（ZIP/JSON/CSV导出，SHA256，Zip Slip防护）
│   ├── i18n.py            # 🌐 I18nManager（zh_CN/en_US/ja_JP，1242翻译键）
│   ├── dashboard_config.py# 📊 DashboardConfig（3布局×3密度×6面板=9种组合）
│   ├── shortcuts_handler.py# ⌨ Apple Shortcuts集成（5个CLI动作）
│   │
│   ├── # === v0.2.5 新增：CarryMem + 知识库 + 飞轮 ===
│   ├── memory_bridge.py   # 🧠 MemoryBridge（CarryMem适配层，持久记忆+规则引擎+飞轮）
│   ├── knowledge_bridge.py# 📚 KnowledgeBridge（6种知识库适配：Obsidian/语雀/飞书/Notion/思源/本地）
│   ├── search_cache.py    # 🔍 搜索缓存（SQLite缓存+TTL+命中追踪）
│   ├── intent_classifier.py # 🎯 意图分类器（轻量级意图路由）
│   ├── correction_manager.py # 🔧 修正管理器（自动修正策略协调）
│   ├── embedding_service.py # 📐 嵌入服务（向量嵌入+相似度计算）
│   ├── llm_cache.py       # 🧊 LLM缓存（SQLite缓存+SHA256键+7天TTL+线程安全）
│   ├── skill_reviews.py   # ⭐ 技能评分（1-5星+文字评价+聚合平均）
│   │
│   ├── # === v0.2.0 模块化提取 ===
│   ├── task_types.py              # 从task_engine_v3提取的任务类型定义
│   ├── task_content_generators.py # 从task_engine_v3提取的内容生成器
│   ├── skill_models.py            # 从skill_registry提取的技能模型
│   ├── skill_builtin.py           # 21个内置技能定义（独立模块）
│   ├── skill_executors.py         # SkillExecutorMixin（20个execute方法）
│   ├── scenario_definitions.py    # 9个场景定义+dataclasses
│   │
│   ├── data_manager.py    # 数据管理（SQLite统一存储+AES加密+事务+迁移）
│   ├── email_skill.py     # 📧 邮件技能（SMTP发送+模板+频率限制）
│   ├── finance_skill.py   # 💰 财务技能（收支记录+月报+趋势）
│   ├── task_skill.py      # ✅ 待办技能（创建/完成/列表/今日待办）
│   ├── crm_skill.py       # 👥 CRM技能（客户管理+合作跟踪+沉默预警）
│   ├── social_skill.py    # 📱 社媒技能（5平台内容生成+草稿管理）
│   ├── invoice_skill.py   # 🧾 发票技能（自动计算+税额）
│   ├── report_skill.py    # 📊 报告技能（周报/月报/年报自动生成）
│   ├── competitor_skill.py# 🔍 竞品技能（监控+动态记录+分析报告）
│   ├── pricing_skill.py   # 💲 定价技能（4种定价法+行业基准+建议）
│   ├── dashboard_skill.py # 📈 看板技能（概览+财务+CRM+待办仪表盘）
│   ├── knowledge_skill.py # 📚 知识库技能（文章CRUD+分类+搜索+统计）
│   ├── skill_marketplace.py # 🔌 技能市场V2（搜索/安装/详情/筛选/版本锁定+MCP发现）
│   ├── user_profile.py    # 👤 用户画像（交互记录+偏好+推荐）
│   ├── skill_marketplace_api.py # 技能市场API服务（FastAPI服务端）
│   ├── mcp_protocol.py      # MCP协议支持（Model Context Protocol兼容）
│   ├── mcp_transport.py     # MCP传输层（SSE + stdio）
│   ├── simple_llm_service.py # 简化LLM服务（轻量调用接口）
│   ├── plugin_system.py     # 插件系统（沙箱隔离+生命周期管理）
│   ├── skill_editor.py      # 技能编辑器（自定义技能创建/测试/发布）
│   ├── performance_monitor.py # 性能监控（SLA管理+LLM缓存+指标采集）
│   ├── task_engine_v3.py  # 任务执行引擎
│   ├── llm_content.py     # LLM增强内容生成（RAG混合模式）
│   ├── llm_service.py     # LLM服务层（MOKA/GLM/OpenAI/Ollama）
│   ├── search_processor.py# 搜索结果后处理（TF-IDF+知识库兜底）
│   ├── async_executor.py  # 异步任务执行器
│   ├── session_context.py # 多轮对话上下文管理
│   ├── validators.py      # 输入验证层（Pydantic模型）
│   ├── business_type_detector_v2.py  # 业务类型检测
│   ├── business_types.py             # 业务类型枚举定义
│   ├── scenario_engine_v2.py         # 场景匹配引擎
│   ├── flywheel_tracker.py           # 成长飞轮追踪
│   ├── persona_manager.py            # 人格管理
│   ├── persona_variants.yaml         # 6种业务类型人格配置
│   ├── monitoring.py                 # 监控与日志
│   ├── config.py                     # 配置管理
│   ├── protocols.py                  # Protocol接口+NullProvider降级模式
│   ├── secure_storage.py             # API密钥加密存储（Fernet）
│   ├── undo_manager.py               # 撤销管理器
│   ├── audit_log.py                  # 审计日志
│   ├── confirmer.py                  # 确认机制
│   ├── progress_emitter.py           # 进度事件发射器
│   └── version.py         # 版本号管理（SSOT）
├── opc_manager/export/     # 导出模块
│   ├── manager.py          # 导出管理器
│   ├── models.py           # 导出模型
│   └── exporters/          # 格式导出器
│       ├── excel_exporter.py
│       ├── pdf_exporter.py
│       ├── word_exporter.py
│       └── image_exporter.py
├── tests/                 # 测试套件（89个测试文件，3781测试用例，100%通过）
├── docs/                  # 项目文档
│   ├── API.md             # API文档
│   └── guides/            # 快速开始指南（中/英/日三语）
├── scripts/               # 部署与运维脚本
│   ├── install.sh         # 一键安装脚本
│   └── start.sh           # 一键启动脚本
├── requirements.txt       # 核心依赖
├── requirements-dev.txt   # 开发依赖（含black/flake8/pytest）
├── .env.example           # 环境变量模板
├── .env.local             # 加密密钥自动生成（gitignore保护）
└── VERSION                # 版本号文件
```

## 测试

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 运行全部测试（3781个用例）
PYTHONPATH=. pytest tests/ -v

# 运行并生成覆盖率报告
PYTHONPATH=. pytest tests/ --cov=opc_manager --cov-report=term-missing

# 运行特定模块测试
PYTHONPATH=. pytest tests/integration/test_settings.py tests/integration/test_onboarding.py tests/unit/test_i18n.py -v
```

> **测试覆盖范围**：全部99个opc_manager模块 + 前端38模块 + 新增模块（settings/onboarding/backup/i18n/dashboard/shortcuts/marketplace_v2/error_handler/wechat等）

## 版本历史

| 版本 | 日期 | 里程碑 |
|------|------|--------|
| **0.3.10** | **2026-07-11** | **crm_skill 测试+覆盖率提升(P3-1)** — 新增 64 个 crm_skill 测试（覆盖率 14.8%→70%+），修复 3 个源码 bug（_handle_deal 金额字符串清理 / _handle_search 缺少"查""找"关键词 / undo 函数非确定性排序），CI 覆盖率阈值 64%→65%（实际 66%），测试数 3717→3781 |
| **0.3.9** | **2026-07-11** | **高复杂度函数降级(P2)** — TaskEngineV3.execute E(31)→B + extract_json_from_llm D(27)→A(4) + crm_skill.execute_goal D(26)→C(13) + email_skill.execute_goal D(23)→C(11)，提取 4 个辅助方法消除重复并行代码 |
| **0.3.8** | **2026-07-11** | **DevSquad 共识推进第一批** — cli.py 覆盖率 0%→95%(+17 测试) + mcp_transport.py 23%→92%(+31 测试) + CI 覆盖率阈值 62%→64%(实际 64.84%) + radon cc 圈复杂度门禁(non-blocking) + sse-starlette 依赖 |
| **0.3.7** | **2026-07-11** | **覆盖率优化批次** — 6 模块覆盖率提升(export/task_skill/user_profile/task_lifecycle/social_skill/task_content_generators) +234 测试 + 3 bug 修复(execute_goal 字符串替换顺序/SQL 参数化/空数据兜底) |
| **0.3.6** | **2026-07-10** | **技术债清理 P2-P3** — install.bat 删除(pip install 跨平台) + task_skill SQL 参数化(IN/NOT IN 占位符) + web_search.py 从 opc_hr/ 迁移到 opc_manager/(消除假分层) + 修复 2 个失败测试 + CI 覆盖率阈值 59%→65% |
| **0.3.5** | **2026-07-09** | **成熟度修复 + God Class 拆分** — DevSquad 7 维度评估 18 项 P0+P1+P2 修复（ruff 43→0 / 三语 README / 幽灵函数清理 / pre-commit hooks）+ tests/ 分层 unit/integration/e2e（87 文件迁移）+ StrategistBrain/ReflectorBrain Facade 拆分（884→176 / 841→222 行）+ 虚拟分层架构守护（96 测试）+ Dockerfile 版本号同步 |
| **0.3.4** | **2026-07-07** | **冻结技能彻底移除 + 发布链路修复** — 删除 tax_reminder/calendar/proposal 3 个冻结技能 + 90 条 i18n 孤儿键清理 + release.yml E2E 隔离修复 + 首次触发 release.yml 发布管道 |
| **0.3.3** | **2026-06-28** | **技术债清理** — TD-065 mypy 516→0 errors（CI 阻塞化）+ TD-066 settings_encryption fail-open→fail-closed + flake8 E501 清零 + 3174 passed |
| **0.3.2** | **2026-06-27** | **项目整理评估修复** — DevSquad 7 维度评估 72→79 (B+) + 17 处版本号同步 + check_prompt_injection 幽灵函数集成 + mypy CI 集成 + 3167 passed |
| **0.3.1** | **2026-06-26** | **幽灵功能清除** — 删除 api/events + experimental/wechat + plugin_system + plugins/ 共 ~2196 行死代码 + flake8 F401/F841 348 项清零 + 3165 passed |
| **0.3.0** | **2026-06-19** | **三贤者并行投票架构回归** — 并行投票(1×RTT，延迟降3倍)+ConsensusEngine前置+ExecutorBrain真意见+ReflectorBrain前置预判+IntentRouter三路路由+聚焦3核心技能(邮件/财务/报告)+9非核心技能冻结+i18n重构(3857→133行)+覆盖率62.87%+真实LLM E2E测试 |
| **0.2.5** | **2026-06-07** | **架构统一+安全加固** — 架构统一重构+LLM并发控制+安全加固+3305测试/76文件 |
| **0.2.4** | **2026-05-24** | **记忆+知识库增强** — CarryMem深度集成+知识库搜索优化+通知系统+扩展测试 |
| **0.2.3** | **2026-05-24** | **CarryMem集成** — 跨会话持久记忆(MemoryBridge)+规则引擎+飞轮机制+LLM缓存+技能评分 |
| **0.2.2** | **2026-05-21** | **CarryMem+知识库+飞轮** — 跨会话持久记忆+规则引擎+6种知识库适配+飞轮机制+LLM缓存+技能评分+前端模块化+E2E测试（1952测试/56文件） |
| **0.2.2** | **2026-05-20** | **品质修复** — i18n 315+硬编码清理+备份AES加密+导出脱敏+MCP默认localhost+Onboarding合并+移动端适配+快捷键修正+CI安全扫描 |
| 0.2.1 | 2026-05-18 | 8个OPC技能集成+技术债清理(32 bare except+i18n 97键) |
| **0.2.0** | **2026-05-17** | **FINAL** — 产品化发布：统一设置管理+首次引导+数据备份恢复+错误处理+微信E2E+模块化仪表盘+i18n三语+技能市场V2+全局搜索+Apple Shortcuts+API Key加密(Fernet)+代码模块化重构（87模块/56测试文件/1860测试） |
| 0.1.8 | 2026-05-14 | 21内置技能+外部技能市场+MCP服务发现+用户画像+数据安全+SQLite统一存储 |
| 0.1.9-delta | 2026-05-09 | 真实运行验证：三贤者LLM驱动+技能市场FastAPI+MCP传输+插件示例+编辑器UI+性能监控 |
| 0.1.9-gamma | 2026-05-09 | 整改优化：三贤者接入主流程+技能市场API+MCP协议+插件系统+技能编辑器 |
| 0.1.9 | 2026-05-09 | 端到端闭环：自动修正+多技能编排+任务暂停/恢复+进度可视化+长会话上下文 |
| 0.1.8 | 2026-05-08 | 核心技能开发：6技能从mock升级为真实能力+搜索增强+LLM集成 |
| 0.1.7 | 2026-05-07 | 三贤者架构：策略脑+执行脑+反思脑+共识引擎+技能注册表+工具框架 |
| 0.1.6 | 2026-05-03 | 用户引导+质量反馈+成果物搜索+空状态示例+三维度走读修复 |
| 0.1.5 | 2026-05-03 | 多轮对话增强+质量门禁+安全测试+Protocol降级+输出脱敏+Ollama支持 |
| 0.1.2 | 2026-05-03 | 安全加固+性能优化：XSS修复、Prompt注入防护、单例模式、线程安全 |
| 0.1.1-beta | 2026-04-27 | Bug修复：LLM初始化/搜索依赖/场景路径/上下文污染/占位符替换 |
| 0.1.0-beta | 2026-04-24 | Beta发布：安装流程修复、安全加固、CI通过 |
| 0.1.0 | 2026-04-23 | "可信可用"：版本统一、Mock删除、MOKA API接入、异步执行 |

## 许可

[MIT License](LICENSE)
