# 🚀 OPC-Agents — 一人公司智能任务执行系统

> **版本**: v0.1.0 | **状态**: 可用 | **许可**: MIT

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

- ✅ **LLM增强内容生成** — 接入Claude Sonnet 4，96%质量合格率
- ✅ **真实网络搜索** — DuckDuckGo实时搜索，不编造数据
- ✅ **零占位符保证** — 每个输出都有具体的、可操作的内容
- ✅ **异步执行** — 提交即返回，后台执行，5阶段进度指示
- ✅ **知识库兜底** — 6类20条专业知识，搜索失败时自动兜底
- ✅ **文件交付** — 自动生成`.md`文件，提供下载按钮
- ✅ **多轮对话** — 支持上下文连续的迭代优化

## 快速开始

### 前置要求

- Python 3.9+
- pip

### 安装

```bash
git clone https://github.com/your-username/OPC-Agents.git
cd OPC-Agents
pip install -r requirements.txt
```

### 配置LLM API（推荐）

```bash
cp .env.example .env
# 编辑 .env，填入你的MOKA API Key:
# MOKA_API_KEY=sk-your-key-here
```

> 不配置API Key也能使用（模板模式），但LLM增强内容质量远高于模板。

### 启动

```bash
streamlit run frontend/app.py
```

浏览器打开 http://localhost:8501 即可使用。

## 项目结构

```
OPC-Agents/
├── frontend/              # Streamlit前端
│   └── app.py             # 主界面（异步执行+5阶段进度+成果物管理）
├── opc_manager/           # 核心业务逻辑
│   ├── task_engine_v3.py  # 任务执行引擎
│   ├── llm_content.py     # LLM增强内容生成（RAG混合模式）
│   ├── llm_service.py     # LLM服务层（MOKA/GLM/OpenAI/Ollama）
│   ├── search_processor.py# 搜索结果后处理（TF-IDF+知识库兜底）
│   ├── async_executor.py  # 异步任务执行器
│   ├── session_context.py # 多轮对话上下文管理
│   └── version.py         # 版本号（SSOT）
├── opc_hr/                # HR/搜索模块
│   └── web_search.py      # DuckDuckGo搜索封装
├── tests/                 # 测试套件（174个测试）
├── docs/                  # 项目文档
│   ├── architect/         # 架构设计
│   ├── product-manager/   # 产品需求
│   ├── solo-coder/        # 路线图
│   ├── test-expert/       # 测试计划
│   ├── user_guides/       # 用户指南
│   └── reviews/           # 评审记录
├── requirements.txt       # 核心依赖
├── requirements-dev.txt   # 开发依赖
├── .env.example           # 环境变量模板
└── VERSION                # 版本号
```

## 支持的LLM后端

| 后端 | 模型 | 配置环境变量 | 质量 |
|------|------|-------------|------|
| **MOKA（推荐）** | Claude Sonnet 4 | `MOKA_API_KEY` | ⭐⭐⭐⭐⭐ |
| 智谱GLM | GLM-4 | `GLM_API_KEY` | ⭐⭐⭐⭐ |
| OpenAI | GPT-4 | `OPENAI_API_KEY` | ⭐⭐⭐⭐ |
| Ollama | 本地模型 | `OLLAMA_BASE_URL` | ⭐⭐⭐ |

优先级：MOKA > GLM > OpenAI > Ollama

## 测试

```bash
# 运行全部测试
pip install -r requirements-dev.txt
pytest tests/ -v

# 运行LLM E2E门禁（需配置API Key）
MOKA_API_KEY=sk-xxx python tests/gate_llm_real_e2e.py --quick

# 运行前端E2E门禁
pytest tests/gate_e2e_frontend.py -v
```

## 版本历史

| 版本 | 日期 | 里程碑 |
|------|------|--------|
| 0.1.0 | 2026-04-23 | "可信可用"：版本统一、Mock删除、MOKA API接入、异步执行、首屏简化 |
| — | 2026-04-22 | v3.6：真实LLM E2E验证通过（96%合格率）、前端异步集成、知识库扩展 |
| — | 2026-04-20 | v3.5：四角色共识、4个P0组件（SearchProcessor/LLMContent/AsyncExecutor/SessionContext） |

## 贡献

欢迎贡献！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可

[MIT License](LICENSE)
