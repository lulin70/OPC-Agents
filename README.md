# 🚀 OPC-Agents — 一人公司智能任务执行系统

> **版本**: v0.1.0-beta | **状态**: Beta测试中 | **许可**: MIT

---

## 🎉 Beta 测试招募中！

OPC-Agents v0.1.0-beta 现已发布，诚邀你参与测试！

**Beta 用户福利：**
- ✅ 免费使用所有功能
- ✅ 优先获得新功能
- ✅ 直接影响产品方向

**如何参与：**
1. 克隆仓库并安装：`git clone https://github.com/lulin70/OPC-Agents.git && cd OPC-Agents && pip install -r requirements.txt`
2. 在 [Issue #1](https://github.com/lulin70/OPC-Agents/issues/1) 分享你的反馈
3. 发现Bug？创建Issue并标记为`bug`

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

- ✅ **LLM增强内容生成** — 接入Claude Sonnet 4，91.2%中文能力
- ✅ **真实网络搜索** — DuckDuckGo实时搜索，不编造数据
- ✅ **零占位符保证** — 每个输出都有具体的、可操作的内容
- ✅ **异步执行** — 提交即返回，后台执行，5阶段进度指示
- ✅ **知识库兜底** — 6类20条专业知识，搜索失败时自动兜底
- ✅ **文件交付** — 自动生成`.md`文件，提供下载按钮
- ✅ **多轮对话** — 支持上下文连续的迭代优化
- ✅ **输入验证** — 完整的安全防护（XSS/SQL注入/路径遍历/DoS）
- ✅ **版本管理** — 语义化版本号，单一数据源（SSOT）
- ✅ **测试覆盖** — 58个测试用例，100%通过率

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
│   ├── validators.py      # 输入验证层（Pydantic模型）
│   └── version.py         # 版本号管理（SSOT）
├── opc_hr/                # HR/搜索模块
│   └── web_search.py      # DuckDuckGo搜索封装
├── tests/                 # 测试套件（58个核心测试，100%通过）
│   ├── test_version.py    # 版本管理测试（9个）
│   ├── test_validators.py # 输入验证测试（35个）
│   └── integration/       # 集成测试
│       └── test_real_llm.py # LLM集成测试（14个）
├── docs/                  # 项目文档
│   ├── OPC_AGENTS_REVIEW_REPORT.md    # 完整评审报告
│   ├── LLM_INTEGRATION_REPORT.md      # LLM测试报告
│   ├── OPTIMIZATION_SUMMARY.md        # 优化总结
│   ├── FINAL_REPORT.md                # 最终报告
│   ├── architect/         # 架构设计
│   ├── product-manager/   # 产品需求
│   ├── solo-coder/        # 路线图
│   ├── test-expert/       # 测试计划
│   ├── user_guides/       # 用户指南
│   └── reviews/           # 评审记录
├── requirements.txt       # 核心依赖
├── .env.example           # 环境变量模板
└── VERSION                # 版本号文件
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

### 核心测试套件（58个测试，100%通过）

```bash
# 安装测试依赖
pip install -r requirements.txt

# 运行核心测试套件
pytest tests/test_version.py tests/test_validators.py tests/integration/test_real_llm.py -v

# 测试结果：
# - 版本管理测试：9/9 通过 ✅
# - 输入验证测试：35/35 通过 ✅
# - LLM集成测试：14/14 通过 ✅（需配置MOKA_API_KEY）
```

### 单独运行测试

```bash
# 版本管理测试（0.26秒）
pytest tests/test_version.py -v

# 输入验证测试（0.28秒）
pytest tests/test_validators.py -v

# LLM集成测试（125秒，需API Key）
MOKA_API_KEY=sk-xxx pytest tests/integration/test_real_llm.py -v
```

### 测试覆盖率

```bash
# 生成覆盖率报告
pytest tests/ --cov=opc_manager --cov-report=html
open htmlcov/index.html
```

### 性能指标

- **版本管理测试：** 0.26秒
- **输入验证测试：** 0.28秒
- **LLM集成测试：** 125秒（包含真实API调用）
- **总测试时间：** ~127秒

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
