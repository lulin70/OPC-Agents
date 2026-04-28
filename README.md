# 🚀 OPC-Agents — 一人公司智能任务执行系统

> **版本**: v0.1.2 | **状态**: ✅ Beta测试就绪 | **许可**: MIT

[![Beta Status](https://img.shields.io/badge/status-beta%20ready-brightgreen)](https://github.com/lulin70/OPC-Agents)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎉 Beta 测试招募中！

**最新更新（2026-04-27）**：v0.1.1-beta 已修复所有P0/P1问题，系统更稳定可靠！

✅ 修复了LLM初始化问题（is_available方法）  
✅ 更新了搜索引擎依赖（ddgs替代duckduckgo-search）  
✅ 修复了场景路径崩溃问题  
✅ 修复了多轮对话上下文污染搜索的问题  
✅ 修复了闲聊消息不保存的问题  
✅ 修复了LLM降级模板占位符问题  
✅ 可用性评分：6.5/10 → 8.5/10

**如何参与：**
1. 📖 阅读 [Beta测试快速启动指南](QUICK_START_BETA.md)
2. 🚀 快速安装：`git clone https://github.com/lulin70/OPC-Agents.git && cd OPC-Agents && ./start.sh`
3. 💬 在 [Discussions](https://github.com/lulin70/OPC-Agents/discussions) 分享你的反馈
4. 🐛 发现Bug？创建 [Issue](https://github.com/lulin70/OPC-Agents/issues) 并标记为`bug`

**Beta测试奖励**：完成测试并提供反馈的用户将获得正式版终身免费使用权！

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

- ✅ **LLM增强内容生成** — 接入Claude Sonnet 4，高质量中文输出
- ✅ **真实网络搜索** — DuckDuckGo实时搜索，不编造数据
- ✅ **零占位符保证** — 每个输出都有具体的、可操作的内容
- ✅ **异步执行** — 提交即返回，后台执行，预估进度指示
- ✅ **知识库兜底** — 6类20条专业知识，搜索失败时自动兜底
- ✅ **文件交付** — 自动生成`.md`文件，提供下载按钮
- ✅ **多轮对话** — 支持上下文连续的迭代优化
- ✅ **安全防护** — 输入验证+Prompt注入防护+URL安全+错误脱敏
- ✅ **测试覆盖** — 229个测试用例，100%通过率，CI自动验证

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
├── opc_hr/                # 搜索与知识库
│   └── web_search.py      # DuckDuckGo网络搜索
├── config/                # 配置文件
│   └── persona_variants.yaml  # 6种业务类型人格配置
├── tests/                 # 测试套件（229个测试，100%通过）
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
| 0.1.2 | 2026-04-27 | 安全加固+性能优化：XSS修复、Prompt注入防护、单例模式、线程安全 |
| 0.1.1-beta | 2026-04-27 | Bug修复：LLM初始化/搜索依赖/场景路径/上下文污染/占位符替换 |
| 0.1.0-beta | 2026-04-24 | Beta发布：安装流程修复、安全加固、CI通过 |
| 0.1.0 | 2026-04-23 | "可信可用"：版本统一、Mock删除、MOKA API接入、异步执行 |

## 许可

[MIT License](LICENSE)
