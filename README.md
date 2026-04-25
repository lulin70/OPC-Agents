# 🚀 OPC-Agents — 一人公司智能任务执行系统

> **版本**: v0.1.0-beta | **状态**: Beta测试中 | **许可**: MIT

---

## 🎉 Beta 测试招募中！

OPC-Agents v0.1.0-beta 现已发布，诚邀你参与测试！

**如何参与：**
1. 一键安装：`git clone https://github.com/lulin70/OPC-Agents.git && cd OPC-Agents && ./install.sh`
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
- ✅ **异步执行** — 提交即返回，后台执行，预估进度指示
- ✅ **知识库兜底** — 6类20条专业知识，搜索失败时自动兜底
- ✅ **文件交付** — 自动生成`.md`文件，提供下载按钮
- ✅ **多轮对话** — 支持上下文连续的迭代优化
- ✅ **安全防护** — 输入验证+Prompt注入防护+URL安全+错误脱敏
- ✅ **测试覆盖** — 200个测试用例，100%通过率，CI自动验证

## 快速开始

### 方式一：一键安装（推荐）

```bash
git clone https://github.com/lulin70/OPC-Agents.git
cd OPC-Agents
chmod +x install.sh start.sh
./install.sh
```

### 方式二：手动安装

```bash
git clone https://github.com/lulin70/OPC-Agents.git
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
./start.sh
# 或手动启动：
streamlit run frontend/app.py
```

浏览器打开 http://localhost:8501 即可使用。

### 故障排查

| 问题 | 解决方案 |
|------|---------|
| 页面显示"模板模式" | 检查 `.env` 文件中 `MOKA_API_KEY` 是否已填入 |
| 端口被占用 | `streamlit run frontend/app.py --server.port 8502` |
| Python版本不对 | 需要 Python 3.9+，运行 `python3 --version` 检查 |
| 安装依赖失败 | 尝试 `pip install --upgrade pip` 后重试 |

## 项目结构

```
OPC-Agents/
├── frontend/              # Streamlit前端
│   └── app.py             # 主界面（异步执行+进度指示+成果物管理）
├── opc_manager/           # 核心业务逻辑
│   ├── task_engine_v3.py  # 任务执行引擎
│   ├── llm_content.py     # LLM增强内容生成（RAG混合模式）
│   ├── llm_service.py     # LLM服务层（MOKA/GLM/OpenAI/Ollama）
│   ├── search_processor.py# 搜索结果后处理（TF-IDF+知识库兜底）
│   ├── async_executor.py  # 异步任务执行器
│   ├── session_context.py # 多轮对话上下文管理
│   ├── validators.py      # 输入验证层（Pydantic模型）
│   ├── business_type_detector_v2.py  # 业务类型检测
│   ├── scenario_engine_v2.py         # 场景匹配引擎
│   ├── flywheel_tracker.py           # 成长飞轮追踪
│   ├── persona_manager.py            # 人格管理
│   ├── monitoring.py                 # 监控与日志
│   ├── config.py                     # 配置管理
│   └── version.py         # 版本号管理（SSOT）
├── tests/                 # 测试套件（200个测试，100%通过）
├── docs/                  # 项目文档
├── requirements.txt       # 核心依赖
├── requirements-dev.txt   # 开发依赖（含black/flake8/pytest）
├── .env.example           # 环境变量模板
├── install.sh             # 一键安装脚本
├── start.sh               # 一键启动脚本
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
| 0.1.0-beta | 2026-04-24 | Beta发布：安装流程修复、安全加固、CI通过 |
| 0.1.0 | 2026-04-23 | "可信可用"：版本统一、Mock删除、MOKA API接入、异步执行 |

## 许可

[MIT License](LICENSE)
