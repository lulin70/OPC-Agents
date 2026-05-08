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

### 关键特性

- ✅ **三贤者架构** — 策略脑(意图理解)+执行脑(技能执行)+反思脑(结果评估)闭环协作
- ✅ **LLM增强内容生成** — 接入Claude Sonnet 4，高质量中文输出
- ✅ **真实网络搜索** — DuckDuckGo实时搜索，不编造数据
- ✅ **零占位符保证** — 每个输出都有具体的、可操作的内容
- ✅ **异步执行** — 提交即返回，后台执行，预估进度指示
- ✅ **自动重试** — 失败任务指数退避自动重试（最多2次），提升任务完成率
- ✅ **质量门禁** — 交付物自动检查零占位符+最低字数+数据来源，不达标自动标注
- ✅ **输出脱敏** — 自动检测并替换生成内容中的 API Key/GitHub Token，防止泄露
- ✅ **知识库兜底** — 6类20条专业知识，搜索失败时自动兜底
- ✅ **文件交付** — 自动生成`.md`文件，提供下载按钮
- ✅ **多轮对话** — 追问"补充XX"/"修改XX"，系统基于上次结果继续，而非从头生成
- ✅ **安全防护** — 命令白名单+路径校验+输入长度限制+审计日志+输入验证+Prompt注入防护+URL安全+错误脱敏+API Key加密存储
- ✅ **测试覆盖** — 373个测试用例，100%通过率，CI自动验证

## 快速开始

### 前提条件

- Python 3.9+
- 至少一个LLM API Key（推荐 [MOKA](https://moka-ai.com)）

### 方式一：pip 安装

```bash
# 1. 安装
pip install opc-agents

# 2. 创建工作目录并配置API Key
mkdir my-opc-workspace && cd my-opc-workspace
echo "MOKA_API_KEY=your-key-here" > .env

# （可选）使用加密存储代替明文.env
# python -m opc_manager.secure_storage set MOKA_API_KEY your-key-here

# 3. 启动
opc-agents
```

> pip安装后，`.env`文件、成果物文件、日志文件都存放在当前工作目录。

### 方式二：源码安装（推荐开发者）

```bash
git clone https://github.com/lulin70/OPC-Agents.git
cd OPC-Agents
chmod +x install.sh start.sh
./install.sh

# 配置API Key
cp .env.example .env
# 编辑 .env，填入你的MOKA API Key

# 启动
./start.sh
```

### 关于API Key

| 后端 | 模型 | 配置环境变量 | 质量 | 获取方式 |
|------|------|-------------|------|---------|
| **MOKA（推荐）** | Claude Sonnet 4 | `MOKA_API_KEY` | ⭐⭐⭐⭐⭐ | [moka-ai.com](https://moka-ai.com) |
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

## 项目结构

```
OPC-Agents/
├── frontend/              # Streamlit前端
│   └── app.py             # 主界面（异步执行+进度指示+成果物管理）
├── opc_manager/           # 核心业务逻辑
│   ├── cli.py             # CLI入口（pip install后opc-agents命令）
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
├── tests/                 # 测试套件（350+个测试，100%通过）
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
| 0.1.6 | 2026-05-03 | 用户引导+质量反馈+成果物搜索+空状态示例+三维度走读修复 |
| 0.1.5 | 2026-05-03 | 多轮对话增强+质量门禁+安全测试+Protocol降级+输出脱敏+Ollama支持 |
| 0.1.2 | 2026-04-28 | 安全加固+性能优化：XSS修复、Prompt注入防护、单例模式、线程安全 |
| 0.1.1-beta | 2026-04-27 | Bug修复：LLM初始化/搜索依赖/场景路径/上下文污染/占位符替换 |
| 0.1.0-beta | 2026-04-24 | Beta发布：安装流程修复、安全加固、CI通过 |
| 0.1.0 | 2026-04-23 | "可信可用"：版本统一、Mock删除、MOKA API接入、异步执行 |

## 许可

[MIT License](LICENSE)
