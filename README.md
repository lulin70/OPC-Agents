# 🚀 OPC-Agents — 一人公司的 AI 执行团队

> **版本**: v0.2.5 | **状态**: Beta | **许可**: MIT

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

## 它能帮你做什么

| 你说 | 它交付 |
|------|--------|
| "帮我收集OPC公司趋势" | 🔍 研究报告（真实搜索+来源链接+结构化整理） |
| "帮我写Q2营销方案" | ✍️ 完整方案（SMART目标+路线图+风险+验收标准） |
| "帮我分析竞品A" | 📊 分析报告（SWOT+行动清单+优先级排序） |
| "帮我发邮件给客户" | 📧 邮件发送（模板渲染+SMTP发送+频率限制） |
| "帮我记录一笔收入" | 💰 财务记录（自动分类+月度报表+趋势分析） |
| "帮我添加客户信息" | 👥 客户档案（加密存储+沉默预警+合作跟踪） |

---

## 核心能力

**三贤者架构**——三个 AI 角色闭环协作，确保输出质量：
- 🧠 **策略脑**：理解你的意图，规划执行步骤
- ⚡ **执行脑**：调用技能和工具，生成成果物
- 🔍 **反思脑**：评估结果质量，不达标自动修正

**21 个内置技能**——覆盖一人公司日常运营：邮件、财务、CRM、方案、报告、社媒、报价、竞品分析...

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
| ↩️ **撤销机制** | 操作可回退，放心大胆用 |
| 🌐 **三语切换** | 中文/英文/日文界面一键切换 |
| 🧊 **LLM 缓存** | 相同问题不重复调用，省时省钱 |

## 生态工具

遇到特定场景？搭配使用效果更好：

| 场景 | 推荐工具 | 说明 |
|------|---------|------|
| 想要 AI 记住你的偏好 | [CarryMem](https://github.com/lulin70/carrymem) | 跨会话持久记忆引擎，`pip install opc-agents[memory]` 一键启用 |
| 有开发任务需要多角色协作 | [DevSquad](https://github.com/lulin70/DevSquad) | 7 角色 AI 团队（架构师/PM/安全/测试/开发/DevOps/UI），复杂开发任务拆解协作 |

## 架构概览

```
┌─────────────────────────────────────────────────────┐
│                    OPC-Agents v0.2.5                 │
├─────────────────────────────────────────────────────┤
│  三贤者架构                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ 策略脑    │→│ 执行脑    │→│ 反思脑    │          │
│  │ 意图理解  │  │ 技能执行  │  │ 结果评估  │          │
│  │ 任务规划  │  │ 工具调用  │  │ 自动修正  │          │
│  └──────────┘  └──────────┘  └──────────┘          │
│       ↕             ↕             ↕                  │
│            共识引擎（意见协调+冲突决策）               │
├─────────────────────────────────────────────────────┤
│  intent_types.py — 意图类型SSOT                       │
│  IntentType枚举 / INTENT_KEYWORDS / INTENT_STEP_MAP  │
│  SkillRegistry单例 — 技能注册/发现/调用/依赖注入      │
│  execute_goal — 各技能模块统一委托入口                 │
├─────────────────────────────────────────────────────┤
│  21个内置技能                                        │
│  ┌─ P0 核心 ─────────────────────────────────────┐  │
│  │ 📧 email  💰 finance  ✅ task  👥 crm         │  │
│  ├─ P1 业务 ─────────────────────────────────────┤  │
│  │ 📱 social  📋 proposal  🧾 invoice            │  │
│  │ 📊 report  📅 calendar                         │  │
│  ├─ P2 进阶 ─────────────────────────────────────┤  │
│  │ 🔍 competitor  💲 pricing  🧾 tax_reminder    │  │
│  │ 📈 dashboard  📚 knowledge                     │  │
│  └───────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────┤
│  外部扩展                                            │
│  ┌──────────────┐  ┌──────────────┐                │
│  │ 🔌 技能市场   │  │ 🔗 MCP服务   │                │
│  │ 搜索/安装/管理│  │ 发现/连接    │                │
│  └──────────────┘  └──────────────┘                │
│  ┌──────────────┐  ┌──────────────┐                │
│  │ 👤 用户画像   │  │ 🔒 数据安全  │                │
│  │ 偏好/推荐    │  │ 加密/沙箱    │                │
│  └──────────────┘  └──────────────┘                │
├─────────────────────────────────────────────────────┤
│  SQLite统一存储（AES加密 + 文件权限0600）             │
└─────────────────────────────────────────────────────┘
```

## 快速开始

### 前提条件

- Python 3.10+
- 至少一个LLM API Key

### 方式一：pip 安装

```bash
# 1. 安装
pip install opc-agents==0.2.5

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
chmod +x install.sh start.sh
./install.sh

# 安装加密依赖
pip install cryptography

# 配置API Key
cp .env.example .env
# 编辑 .env，填入你的MOKA API Key

# 启动
./start.sh
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

> ⚠️ **安全提示**：`OPC_ENCRYPTION_KEY` 为必设项，未设置时 `encrypt_field()` 将抛出 `RuntimeError`，导致邮件密码、客户敏感字段等加密操作失败。请务必在 `.env` 中设置强随机密钥。

### 关于API Key

> ⚠️ **OPC-Agents 不提供 LLM 服务。** 请选择适合你的 LLM 服务商，自行获取 API Key。项目不存储任何 API Key 等隐私信息。

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
│   │   └── shared.py      # 16个UI辅助函数（384行）
│   ├── page_modules/      # 页面模块
│   │   ├── dashboard_page.py   # 仪表盘页面（578行+模板）
│   │   ├── marketplace_page.py # 技能市场V2（547行）
│   │   └── settings_page.py    # 设置管理页（666行）
│   ├── routers/            # 路由模块
│   └── renderers/          # 渲染模块
├── opc_manager/           # 核心业务逻辑（92个.py模块）
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
│   ├── error_handler.py   # 🛡️ ErrorHandler（9种异常类型→中文友好消息）
│   ├── data_backup.py     # 💾 DataBackupManager（ZIP/JSON/CSV导出，SHA256，Zip Slip防护）
│   ├── i18n.py            # 🌐 I18nManager（zh_CN/en_US/ja_JP，58+翻译键）
│   ├── dashboard_config.py# 📊 DashboardConfig（3布局×3密度×6面板=9种组合）
│   ├── shortcuts_handler.py# ⌨️ Apple Shortcuts集成（5个CLI动作）
│   ├── wechat_agent.py    # 💬 微信E2E智能体
│   ├── wechat_gateway.py  # 💬 微信网关
│   │
│   ├── # === v0.2.5 新增：CarryMem + 知识库 + 飞轮 ===
│   ├── memory_bridge.py   # 🧠 MemoryBridge（CarryMem适配层，持久记忆+规则引擎+飞轮）
│   ├── knowledge_bridge.py# 📚 KnowledgeBridge（6种知识库适配：Obsidian/语雀/飞书/Notion/思源/本地）
│   │
│   ├── # === v0.2.0 模块化提取 ===
│   ├── task_types.py              # 从task_engine_v3提取的任务类型定义
│   ├── task_content_generators.py # 从task_engine_v3提取的内容生成器
│   ├── skill_models.py            # 从skill_registry提取的技能模型
│   ├── skill_builtin.py           # 21个内置技能定义（独立模块）
│   ├── skill_executors.py         # SkillExecutorMixin（20个execute方法）
│   ├── scenario_definitions.py    # 9个场景定义+dataclasses
│   │
│   ├── scenario_migrator.py# 场景迁移器（9场景→技能映射）
│   ├── task_engine_adapter.py# TaskEngine适配器（三贤者↔TaskEngineV3桥接）
│   ├── data_manager.py    # 数据管理（SQLite统一存储+AES加密+事务+迁移）
│   ├── email_skill.py     # 📧 邮件技能（SMTP发送+模板+频率限制）
│   ├── finance_skill.py   # 💰 财务技能（收支记录+月报+趋势）
│   ├── task_skill.py      # ✅ 待办技能（创建/完成/列表/今日待办）
│   ├── crm_skill.py       # 👥 CRM技能（客户管理+合作跟踪+沉默预警）
│   ├── social_skill.py    # 📱 社媒技能（5平台内容生成+草稿管理）
│   ├── proposal_skill.py  # 📋 报价技能（5类服务模板+Markdown渲染）
│   ├── invoice_skill.py   # 🧾 发票技能（自动计算+税额+税务日历）
│   ├── report_skill.py    # 📊 报告技能（周报/月报/年报自动生成）
│   ├── calendar_skill.py  # 📅 日程技能（事件管理+提醒+周视图）
│   ├── competitor_skill.py# 🔍 竞品技能（监控+动态记录+分析报告）
│   ├── pricing_skill.py   # 💲 定价技能（4种定价法+行业基准+建议）
│   ├── tax_reminder_skill.py# 🧾 税务提醒技能（截止日+清单+完成跟踪）
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
├── opc_manager/api/        # API事件模块
│   └── events.py          # 事件定义
├── opc_manager/export/     # 导出模块
│   ├── manager.py          # 导出管理器
│   ├── models.py           # 导出模型
│   └── exporters/          # 格式导出器
│       ├── excel_exporter.py
│       ├── pdf_exporter.py
│       ├── word_exporter.py
│       └── image_exporter.py
├── opc_hr/                # 搜索与知识库
│   └── web_search.py      # DuckDuckGo网络搜索
├── plugins/               # 社区插件
│   ├── plugin_config.json
│   ├── data_converter.py
│   └── text_summarizer.py
├── tests/                 # 测试套件（76个测试文件，2939测试用例，100%通过）
├── docs/                  # 项目文档
│   ├── API.md             # API文档
│   └── guides/            # 快速开始指南（中/英/日三语）
├── requirements.txt       # 核心依赖
├── requirements-dev.txt   # 开发依赖（含black/flake8/pytest）
├── .env.example           # 环境变量模板
├── .env.local             # 加密密钥自动生成（gitignore保护）
├── install.sh             # 一键安装脚本
├── start.sh               # 一键启动脚本
└── VERSION                # 版本号文件
```

## 测试

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 运行全部测试（2939个用例）
PYTHONPATH=. pytest tests/ -v

# 运行并生成覆盖率报告
PYTHONPATH=. pytest tests/ --cov=opc_manager --cov-report=term-missing

# 运行特定模块测试
PYTHONPATH=. pytest tests/test_settings.py tests/test_onboarding.py tests/test_i18n.py -v
```

> **测试覆盖范围**：全部92个opc_manager模块 + 前端38模块 + 新增模块（settings/onboarding/backup/i18n/dashboard/shortcuts/marketplace_v2/error_handler/wechat等）

## 版本历史

| 版本 | 日期 | 里程碑 |
|------|------|--------|
| **0.2.5** | **2026-06-07** | **架构统一+安全加固** — 架构统一重构+LLM并发控制+安全加固+2939测试/76文件 |
| **0.2.4** | **2026-05-25** | **记忆+知识库增强** — CarryMem深度集成+知识库搜索优化+通知系统+扩展测试 |
| **0.2.3** | **2026-05-22** | **CarryMem集成** — 跨会话持久记忆(MemoryBridge)+规则引擎+飞轮机制+LLM缓存+技能评分 |
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
