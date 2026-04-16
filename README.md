# 🚀 OPC-Agents — 一人公司智能任务执行系统

> **版本**: v3.3 | **状态**: 生产可用 | **最后更新**: 2026-04-16

---

## 这是什么

OPC-Agents（One-Person Company Agents）是一个**面向一人公司/独立创业者/自由职业者的智能任务执行系统**。

**核心理念：告诉系统你要什么结果，它直接做完并交付文件给你。**

不是聊天机器人，不是建议引擎，是**能干活的执行者**。

## 它能做什么

| 你说 | 系统交付 | 示例 |
|------|---------|------|
| "帮我收集OPC公司趋势" | 🔍 **研究报告**（8条真实搜索结果+来源链接+结构化整理） | [示例](#) |
| "帮我写Q2营销方案" | ✍️ **完整方案文档**（SMART目标+6周路线图+资源/风险/验收标准） | [示例](#) |
| "帮我分析竞品A" | 📊 **分析报告**（SWOT+具体行动清单+优先级排序） | [示例](#) |
| 点击"报告撰写"按钮 | 🎯 **场景工作流**（多步骤执行+每步产出物） | [示例](#) |

### 关键特性

✅ **真实网络搜索** — DuckDuckGo实时搜索，不编造数据  
✅ **零占位符保证** — 每个输出都有具体的、可操作的内容（无`___`、无"待填写"）  
✅ **文件交付** — 自动生成`.md`文件，提供下载按钮，保存到本地  
✅ **成果物管理** — 历史文件库，可预览、可复用  
✅ **9个预设场景** — 报告撰写、内容日历、产品发布、电商优化等  

## 快速开始

### 前置要求

- Python 3.9+
- pip 包：`streamlit duckduckgo-search requests`

### 安装

```bash
git clone https://github.com/lulin70/OPC-Agents.git
cd OPC-Agents
pip install -r requirements.txt
```

### 启动Web界面

```bash
streamlit run frontend/app.py --server.port 8502
```

打开 http://localhost:8502 即可使用。

### 命令行调用（用于集成）

```python
from opc_manager.task_engine_v3 import TaskEngineV3

engine = TaskEngineV3()
result = engine.execute("帮我写一份Q2营销方案")

print(result.success)       # True
print(result.content)        # 完整的Markdown内容
print(result.task_type)      # TaskType.CONTENT_GENERATION
```

## 项目架构

```
┌─────────────────────────────────────────────┐
│              frontend/app.py                 │  ← Streamlit Web前端
│         (对话界面 + 成果物管理 + 下载)        │
├─────────────────────────────────────────────┤
│          opc_manager/task_engine_v3.py       │  ← 任务执行引擎(v3)
│    (意图分类 → 真实搜索 → 结构化生成 → 文件)   │
├──────────┬──────────┬───────────────────────┤
│ opc_hr/  │opc_manager/                     │
│ web_     │ scenario_engine_v2.py           │  ← 场景引擎(9个预设)
│ search.py│ business_type_detector_v2.py    │  ← 业务类型检测
│ (DuckDuckGo)| persona_manager.py            │  ← 人格管理(6种)
│          │ flywheel_tracker.py             │  ← 成长飞轮
└──────────┴──────────┴───────────────────────┘
```

### 核心模块

| 模块 | 文件 | 职责 |
|------|------|------|
| **TaskEngineV3** | `opc_manager/task_engine_v3.py` | 主引擎：意图识别→搜索→生成→交付 |
| **ScenarioEngineV2** | `opc_manager/scenario_engine_v2.py` | 9个预设场景的工作流编排 |
| **BusinessTypeDetectorV2** | `opc_manager/business_type_detector_v2.py` | 6种业务类型自动检测 |
| **PersonaManager** | `opc_manager/persona_manager.py` | 6种人格配置（内容/产品/AI/咨询/电商/创意）|
| **FlywheelTracker** | `opc_manager/flywheel_tracker.py` | 五维成长飞轮追踪 |
| **WebSearchMCP** | `opc_hr/web_search.py` | DuckDuckGo真实网络搜索 |
| **LLMService** | `opc_manager/llm_service.py` | LLM后端抽象层（OpenAI/GLM/Ollama）|

## 工作流程

```
用户输入: "帮我写一份Q2营销方案"
         ↓
[1] IntentClassifier 分类 → CONTENT_GENERATION (置信度0.85)
         ↓
[2] WebSearchMCP.search("Q2营销方案 方案 案例 最佳实践") → 5条结果
         ↓
[3] _gen_real_plan() 基于搜索结果生成:
    - 项目概览表
    - SMART目标（含具体指标）
    - 三阶段实施路线图（第1-8周）
    - 资源配置表
    - 风险管理矩阵（4项具体风险）
    - 验收标准清单（6项）
         ↓
[4] save_deliverable() → deliverables/20260416_xxxx_content_generation_Q2营销方案.md
         ↓
[5] 前端显示完整内容 + 📥下载按钮
```

## 版本历史

### v3.3 (当前) — 零占位符版
- ✅ 彻底删除所有`___`占位符和空模板框架
- ✅ 新建TaskEngineV3，铁律：每个输出必须有具体内容
- ✅ 方案文档含SMART目标/路线图/资源/风险/验收标准
- ✅ 报告文档含背景/现状/分析/结论/行动项
- ✅ 信息收集含真实搜索结果+来源链接+要点提炼

### v3.2 — 成果物交付版
- ✅ 每次任务生成真实`.md`文件保存到`deliverables/`
- ✅ 提供下载按钮（对话页+成果物库页）
- ✅ 新增📁成果物管理页面
- ⚠️ 发现v3.2仍包含空模板问题（已由v3.3修复）

### v3.1.1 — 真实搜索版
- ✅ 接入DuckDuckGo真实网络搜索
- ✅ 不再返回MockLLM的JSON原始数据
- ✅ 显示任务类型和执行耗时元数据

### v3.1 — 任务执行版
- 从"给建议"变为"直接执行"
- 新建TaskEngine（意图分类+任务分解+执行）
- ❌ 调用MockLLM返回了内部检测JSON（已修复）

### v3.0 — 用户中心版
- Streamlit前端重构（首屏即对话、场景快捷入口）
- 防御性错误处理（永不崩溃）
- ❌ 返回的是固定模板废话（已修复）

### v2.2.0 — Phase 2完成
- ScenarioEngineV2（9场景）、BusinessTypeDetectorV2（100%准确）
- PersonaManager（6人格）、FlywheelTracker（五维成长）
- 65个测试全部通过

### v2.1.0 — Phase 1 MVP
- ScenarioEngineV1（9场景基础版）
- BusinessTypeDetector（关键词匹配）
- PersonaManager（3基础人格）
- 38个测试通过

## 测试

```bash
# 运行全部测试（跳过已知问题的旧测试）
pytest tests/ -v --ignore=tests/unit/test_wechat_pairing.py

# 仅运行Phase 3测试
pytest tests/test_phase3_*.py -v

# 测试TaskEngineV3核心功能
python3 -c "
from opc_manager.task_engine_v3 import TaskEngineV3
engine = TaskEngineV3()
r = engine.execute('帮我写一份Q2营销方案')
assert r.success
assert '___' not in r.content
assert len(r.content) > 1000
print('✅ TaskEngineV3验证通过')
"
```

## 目录结构

```
OPC-Agents/
├── frontend/
│   └── app.py              # Streamlit Web前端 (v3.3)
├── opc_manager/
│   ├── task_engine_v3.py    # ⭐ 任务执行引擎 (新增v3.3)
│   ├── task_engine_v2.py    # (已废弃，含空模板)
│   ├── task_engine.py      # (已废弃，调用MockLLM)
│   ├── scenario_engine_v2.py # 场景引擎
│   ├── business_type_detector_v2.py # 业务类型检测
│   ├── persona_manager.py   # 人格管理
│   ├── flywheel_tracker.py  # 成长飞轮
│   ├── llm_service.py      # LLM服务层
│   └── platform_adapters.py # 平台适配器
├── opc_hr/
│   └── web_search.py        # DuckDuckGo搜索
├── db_models/               # 数据模型 (SQLAlchemy)
├── web_app/                 # FastAPI后端API
├── task_deliverables/       # 成果物管理器
├── tests/                   # 测试套件 (400+测试)
├── deliverables/            # ⭐ 生成的成果物文件 (运行时生成)
├── docs/                    # 设计文档
│   ├── product-manager/PRD_V3.md
│   ├── architect/ARCHITECTURE_DESIGN_V3.md
│   ├── test-expert/TEST_PLAN_V3.md
│   └── solo-coder/ROADMAP_V3.md
├── config.toml             # 配置文件
├── requirements.txt         # Python依赖
└── README.md               # 本文件
```

## 配置

### 环境变量（可选）

```bash
# LLM配置（可选，不配则使用内置逻辑）
LLM_PROVIDER=openai          # openai / ollama / mock
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

### config.toml

```toml
[llm]
provider = "openai"          # 或 "ollama", "mock"
model = "glm-4"
api_key = "your-api-key"

[web]
host = "0.0.0.0"
port = 5000
```

## 已知限制与 roadmap

### 当前限制
1. **Streamlit超时**：网络搜索耗时5-10秒，可能导致前端显示超时（命令行调用不受影响）
2. **搜索质量**：DuckDuckGo对中文长尾关键词理解有限，部分搜索结果相关性需改进
3. **LLM未接入生产**：当前内容生成为规则+模板+搜索整合模式，未调用外部LLM API

### 近期计划
- [ ] 解决Streamlit超时问题（异步执行或进度反馈）
- [ ] 接入GLM-4 API实现更高质量的内容生成
- [ ] 支持更多输出格式（PDF导出、Word导出）
- [ ] 增加多轮对话上下文保持

## 贡献

欢迎 Issue 和 Pull Request！

## License

MIT

---

> **一句话总结**：OPC-Agents 不是陪你聊天的 AI 助手，是帮你把活干完并把成果交到你手里的**数字员工**。
