# 🚀 OPC-Agents — 一人公司智能任务执行系统

> **版本**: v0.1.9 | **状态**: Beta | **许可**: MIT

[![Beta](https://img.shields.io/badge/status-beta-blue)](https://github.com/lulin70/OPC-Agents)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI](https://img.shields.io/pypi/v/opc-agents)](https://pypi.org/project/opc-agents/)

---

**语言**: **中文** | [English](README-EN.md) | [日本語](README-JP.md)

---

## 这是什么

OPC-Agents（One-Person Company Agents）是一个**面向一人公司/独立创业者/自由职业者的智能任务执行系统**。

**核心理念：告诉系统你要什么结果，它直接做完并交付文件给你。**

不是聊天机器人，不是建议引擎，是**能干活的执行者**。

## 它能做什么

| 你说 | 系统交付 |
|------|---------|
| "帮我收集OPC公司趋势" | 🔍 **研究报告**（真实搜索结果+来源链接+结构化整理） |
| "帮我写Q2营销方案" | ✍️ **完整方案文档**（SMART目标+路线图+资源/风险/验收标准） |
| "帮我分析竞品A" | 📊 **分析报告**（SWOT+行动清单+优先级排序） |
| "帮我制定产品发布计划" | 🚀 **发布方案**（定价策略+推广渠道+时间线） |
| "帮我发邮件给客户" | 📧 **邮件发送**（模板渲染+SMTP发送+频率限制） |
| "帮我记录一笔收入" | 💰 **财务记录**（自动分类+月度报表+趋势分析） |
| "帮我添加客户信息" | 👥 **客户档案**（加密存储+沉默客户预警+合作跟踪） |
| "帮我生成报价单" | 📋 **报价文档**（服务模板+Markdown渲染+有效期管理） |

### 关键特性

- ✅ **三贤者架构** — 策略脑(意图理解)+执行脑(技能执行)+反思脑(结果评估)闭环协作
- ✅ **21个内置技能** — P0核心(email/finance/task/crm) + P1业务(social/proposal/invoice/report/calendar) + P2进阶(competitor/pricing/tax_reminder/dashboard/knowledge)，无限扩展
- ✅ **🔌 外部技能市场** — 搜索、安装第三方技能，信任等级体系(official/verified/community/unverified)
- ✅ **🔗 MCP服务发现** — 搜索和连接MCP协议服务器，发现远程工具
- ✅ **👤 用户画像** — 偏好记录、使用模式分析、智能技能推荐
- ✅ **🤝 技能协作** — 跨技能联动（CRM→Email、Finance→Tax、Deal→Income）
- ✅ **🔒 数据安全** — 加密强制密钥（OPC_ENCRYPTION_KEY）、AES加密存储、SQLite文件权限0600、外部技能沙箱隔离、UNVERIFIED技能禁止安装、网络白名单
- ✅ **技能上下文传递** — SkillContext支持技能间数据流转，搜索→分析→创作闭环
- ✅ **LLM增强内容生成** — 接入Claude Sonnet 4，高质量中文输出
- ✅ **真实网络搜索** — DuckDuckGo实时搜索，不编造数据
- ✅ **零占位符保证** — 每个输出都有具体的、可操作的内容
- ✅ **自动修正** — 结果质量不达标自动触发修正策略（重试/补充搜索/换技能/降级）
- ✅ **多技能编排** — 复合意图自动拆解为多步骤执行计划
- ✅ **任务暂停/恢复** — 支持暂停正在执行的任务，稍后从断点恢复继续
- ✅ **执行进度可视化** — 事件驱动的实时进度跟踪，支持SSE推送
- ✅ **长会话上下文** — 多轮对话保持上下文，追问"补充XX"基于上次结果继续
- ✅ **异步执行** — 提交即返回，后台执行，预估进度指示
- ✅ **质量门禁** — 交付物自动检查零占位符+最低字数+数据来源，不达标自动标注
- ✅ **输出脱敏** — 自动检测并替换生成内容中的 API Key/GitHub Token，防止泄露
- ✅ **知识库兜底** — 6类20条专业知识，搜索失败时自动兜底
- ✅ **文件交付** — 自动生成`.md`文件，提供下载按钮
- ✅ **安全防护** — 命令白名单+路径校验+输入长度限制+审计日志+输入验证+Prompt注入防护+URL安全+错误脱敏+API Key加密存储
- ✅ **测试覆盖** — 470个测试用例，100%通过率，CI自动验证
- ✅ **技能市场API** — 外部技能注册/发现/调用，API Key认证+权限分级
- ✅ **MCP协议兼容** — 兼容微软Model Context Protocol标准，支持工具/资源/提示词
  > MCP SSE模式需要额外依赖：`pip install opc-agents[mcp]`，stdio模式无需额外安装。
- ✅ **插件系统** — 社区插件热加载+沙箱隔离+生命周期管理
- ✅ **自定义技能编辑器** — 表单式技能创建/测试/预览/发布
- ✅ **质量/快速模式** — 用户可选三贤者完整闭环或跳过反思快速执行

## 架构概览

```
┌─────────────────────────────────────────────────────┐
│                    OPC-Agents v0.1.9                 │
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

- Python 3.9+
- 至少一个LLM API Key

### 方式一：pip 安装

```bash
# 1. 安装
pip install opc-agents

# 2. 安装加密依赖（推荐，用于邮件密码等敏感字段加密）
pip install cryptography

# 3. 创建工作目录并配置API Key
mkdir my-opc-workspace && cd my-opc-workspace
echo "MOKA_API_KEY=your-key-here" > .env

# （可选）使用加密存储代替明文.env
# python -m opc_manager.secure_storage set MOKA_API_KEY your-key-here

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
| `OPC_USE_AGENT_LOOP` | 使用三贤者执行循环 | `false` |
| `OPC_SKIP_REFLECT` | 跳过反思阶段（快速模式） | `false` |

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
| Python版本不对 | 需要 Python 3.9+，运行 `python3 --version` 检查 |
| 安装依赖失败 | 尝试 `pip install --upgrade pip` 后重试 |
| 加密功能不可用 | 运行 `pip install cryptography` 安装加密依赖 |

## 项目结构

```
OPC-Agents/
├── frontend/              # Streamlit前端
│   └── app.py             # 主界面（异步执行+进度指示+成果物管理）
├── opc_manager/           # 核心业务逻辑
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
│   ├── skill_marketplace.py # 🔌 技能市场（搜索/安装/管理+MCP发现）
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
│   ├── secure_storage.py             # API密钥加密存储
│   └── version.py         # 版本号管理（SSOT）
├── opc_hr/                # 搜索与知识库
│   └── web_search.py      # DuckDuckGo网络搜索
├── tests/                 # 测试套件（470个测试，100%通过）
├── docs/                  # 项目文档
├── requirements.txt       # 核心依赖
├── requirements-dev.txt   # 开发依赖（含black/flake8/pytest）
├── .env.example           # 环境变量模板
├── install.sh             # 一键安装脚本
├── start.sh               # 一键启动脚本
└── VERSION                # 版本号文件
```

## 测试

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 运行全部测试
PYTHONPATH=. pytest tests/ -v

# 运行并生成覆盖率报告
PYTHONPATH=. pytest tests/ --cov=opc_manager --cov-report=term-missing
```

## 版本历史

| 版本 | 日期 | 里程碑 |
|------|------|--------|
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
