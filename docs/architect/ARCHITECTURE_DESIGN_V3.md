# OPC-Agents 架构设计文档 v3.5 (四角色共识提升版)

## 更新履历

| 版本 | 日期 | 更新人 | 更新内容 |
|------|------|--------|----------|
| **v3.5.0** | **2026-04-16** | **架构师+四方共识** | **SearchResultProcessor / LLMEnhancedContentGenerator / AsyncTaskExecutor / SessionContextManager** |
| v3.4.0 | 2026-04-16 | 架构师 | v3.4审计重构: InputValidator/SearchCache/注释完善 |
| v3.3.0 | 2026-04-16 | 架构师 | TaskEngineV3核心架构、零占位符设计、真实搜索集成、文件交付链路 |

---

## ⚡ v3.3 架构总览（实际交付版）

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    用户层 (User Layer)                      │
│                                                             │
│   ┌───────────┐    ┌───────────┐    ┌───────────────────┐    │
│   │ 浏览器     │    │ CLI      │    │ 第三方集成         │    │
│   │ Streamlit  │    │ Python   │    │ API / Webhook      │    │
│   │ :8502      │    │ 调用     │    │                   │    │
│   └─────┬─────┘    └─────┬───┘    └─────────┬─────────┘    │
│         │                │                    │              │
└─────────┼────────────────┼────────────────────┼──────────────┘
          │                │                    │
          ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                  前端层 (Frontend Layer)                       │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │              frontend/app.py                         │   │
│   │  - ChatUI (对话界面)                                 │   │
│   │  - 📁 成果物管理页 (文件列表+预览+下载)               │   │
│   │  - 📊 成长飞轮仪表盘                                  │   │
│   │  - ⚙️ 设置页面                                       │   │
│   │  - execute_task_and_deliver() ← 核心入口             │   │
│   │  - save_deliverable() ← 文件生成                     │   │
│   └────────────────────┬────────────────────────────────┘   │
│                        │                                   │
└────────────────────────┼───────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                 引擎层 (Engine Layer) ⭐核心                   │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │        opc_manager/task_engine_v3.py (660行)         │   │
│   │                                                     │   │
│   │   ┌──────────────┐                                   │   │
│   │   │IntentClassifier│ → 分类: INFO/CONTENT/ANALYSIS/   │   │
│   │   │  (正则匹配)    │   SCENARIO/GENERAL               │   │
│   │   └──────┬───────┘                                   │   │
│   │          │                                           │   │
│   │   ┌──────▼───────┐                                   │   │
│   │   │TaskEngineV3  │                                   │   │
│   │   │ .execute()    │                                   │   │
│   │   └──────┬───────┘                                   │   │
│   │          │                                           │   │
│   │   ┌──────▼──────────────────────────────┐           │   │
│   │   │  执行路径分发:                          │           │   │
│   │   │                                        │           │   │
│   │   │  INFO_COLLECTION → _execute_info_       │           │   │
│   │   │    collection()                        │           │   │
│   │   │    → WebSearchMCP.search()            │           │   │
│   │   │    → _build_research_report()        │           │   │
│   │   │                                        │           │   │
│   │   │  CONTENT_GENERATION → _execute_content_│           │   │
│   │   │    generation()                       │           │   │
│   │   │    → WebSearchMCP.search(参考)        │           │   │
│   │   │    → _gen_real_plan() / _gen_real_    │           │   │
│   │   │      report() / _gen_real_content()   │           │   │
│   │   │                                        │           │   │
│   │   │  DATA_ANALYSIS → _execute_analysis()   │           │   │
│   │   │    → WebSearchMCP.search(数据)        │           │   │
│   │   │    → _build_analysis_report()        │           │   │
│   │   │                                        │           │   │
│   │   │  SCENARIO_BASED → _execute_scenario_  │           │   │
│   │   │    based()                             │           │   │
│   │   │    → ScenarioEngineV2.process_input() │           │   │
│   │   │    → _exec_step_with_data() × N步     │           │   │
│   │   └───────────────────────────────────────┘           │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   铁律声明 (v3.3):                                          │
│   1. 绝对不允许占位符（___、待填写、此处插入）                  │
│   2. 绝对不允许空模板框架                                    │
│   3. 每个输出必须有具体的、真实的、可操作的内容                │
│   4. 信息必须来自真实网络搜索或专业知识库                      │
│   5. 用户拿到文件后可以直接使用或微调后使用                    │
└─────────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌──────────────────┐
│ 数据层       │  │ 场景引擎层    │  │ 搜索层           │
│             │  │             │  │                  │
│ deliverables│  │ Scenario-  │  │ opc_hr/          │
│ / *.md 文件 │  │ EngineV2    │  │ web_search.py    │
│             │  │ (9场景)     │  │ DuckDuckGo Search│
│ [文件系统]  │  │             │  │ MCP              │
│             │  │ 工作流编排   │  │ 8条结果/请求     │
│ 备选: DB    │  │ Step执行器   │  │ 真实网络搜索     │
│ (SQLAlchemy)│  │ 交付物模板   │  │                  │
└─────────────┘  └─────────────┘  └──────────────────┘
```

### 数据流图

```
用户输入: "帮我写一份Q2营销方案"
         │
         ▼
[前端] execute_task_and_deliver(prompt)
    │
    ├──→ [TaskEngineV3] engine = TaskEngineV3()
    │       │
    │       ├──→ [IntentClassifier] classify("帮我写一份Q2营销方案")
    │       │   └──→ 返回: (CONTENT_GENERATION, 0.85)
    │       │
    │       └──→ [_execute_content_generation()]
    │               │
    │               ├──→ [WebSearchMCP] search("Q2营销方案 方案 案例")
    │               │   └──→ 返回: [{title, body, href}, ...] ×5条
    │               │
    │               ├──→ [_gen_real_plan(query, context, results)]
    │               │   ├── 项目概览表
    │               │   ├── SMART目标 (效率↑30%, 质量≥95%, ...)
    │               │   ├── 三阶段路线图 (第1-8周, 含具体任务表)
    │               │   ├── 资源配置 (3-5人角色分工)
    │               │   ├── 风险管理 (4项具体风险+应对措施)
    │               │   └── 验收标准 (6项可检查清单)
    │               │
    │               └──→ 返回: TaskResult(success=True, content=2364字)
    │
    ├──→ [save_deliverable()] 
    │   ├── 生成文件名: 20260416_xxxx_content_generation_Q2营销方案.md
    │   ├── 写入: deliverables/20260416_xxxx_content_generation_Q2营销方案.md
    │   └── 记录到: st.session_state.deliverables[]
    │
    └──→ 返回 (content, success, filepath, task_type)
            │
            ▼
[前端显示]
    ├── st.markdown(content)        # 完整Markdown渲染
    ├── st.download_button(data=...)  # 📥 下载按钮
    └── st.success("已生成: xxx.md") # 成功提示
```

---

## ADR-006: TaskEngineV3 设计决策

**日期**: 2026-04-16  
**状态**: 已实施  
**决策者**: 架构师 + 产品经理（基于用户反馈）

### 背景

v3.2交付的成果物文件中发现大量空模板：
```
- 人力资源：___
- 风险1 | 中 | 高 | 措施1
- 清晰定义本方案要达成的目标
```
用户明确反馈："这个文件我能用什么？！"

### 决策

创建全新的TaskEngineV3，替代有问题的TaskEngine(v1)和TaskEngineV2。

### 方案对比

| 方案 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| A. 修复v2中的_get_content_template() | 改动小 | 根本设计就是返回空模板 | ❌ |
| B. 接入LLM生成所有内容 | 内容质量高 | MockLLM导致前端崩溃；LLM成本 | ❌ |
| C. **新建TaskEngineV3，铁律零占位符** | **彻底解决；规则引擎稳定可控** | **需要重写约660行代码** | ✅ |

### 实施细节

1. **删除** `task_engine.py` 和 `task_engine_v2.py`（标记为废弃）
2. **新建** `task_engine_v3.py`，包含：
   - `IntentClassifier`: 正则意图分类（5种类型）
   - `TaskEngineV3`: 主引擎（`execute()`方法）
   - `_gen_real_report()`: 真实报告生成（含背景/现状/分析/结论/行动项）
   - `_gen_real_plan()`: 真实方案生成（含SMART目标/路线图/资源/风险/验收）
   - `_gen_real_content()`: 通用内容生成（基于搜索结果）
   - `_build_research_report()`: 搜索结果结构化整理
   - `_build_analysis_report()`: SWOT分析报告
   - `_exec_step_with_data()`: 场景步骤执行（基于真实数据）
3. **前端切换**到TaskEngineV3：`from opc_manager.task_engine_v3 import TaskEngineV3`
4. **验证脚本**：`assert '___' not in result.content`

### 结果

- ✅ 零占位符验证通过（命令行测试）
- ✅ 方案文档从"不可用"变为"含SMART目标/路线图/资源/风险/验收"
- ✅ 信息收集从"无数据"变为"8条DuckDuckGo真实结果"
- ⚠️ Streamlit前端集成存在超时问题（独立于引擎本身）

---

## ADR-007: 文件交付机制设计

**日期**: 2026-04-16  
**状态**: 已实施

### 决策

每次任务执行完成后，将结果保存为`deliverables/`目录下的`.md`文件，并在前端提供下载功能。

### 设计

```python
# 文件命名规则
DELIVERABLES_DIR = "deliverables/"
filename = "{timestamp}_{task_type}_{prompt摘要}.md"
# 例: 20260416_132814_content_generation_帮我写一份Q2营销方案.md

# 保存流程
def save_deliverable(content, prompt, task_type, meta):
    filepath = os.path.join(DELIVERABLES_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    record = {
        "filename": filename,
        "filepath": filepath,
        "prompt": prompt[:50],
        "task_type": task_type,
        "created_at": datetime.now().isoformat(),
        "size_kb": round(len(content.encode('utf-8')) / 1024, 1),
        "meta": meta,
    }
    session_state.deliverables.insert(0, record)  # 最新在前
    return filepath

# 下载按钮
st.download_button(
    label="📥 下载成果物",
    data=file_content,
    file_name=os.path.basename(filepath),
    mime="text/markdown",
)
```

### 存储策略对比

| 方案 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| A. 仅内存(session_state) | 最快 | 刷新丢失 | ❌ |
| **B. 文件系统(deliverables/)** | **简单可靠；可直接查看；可备份** | **多实例需同步** | ✅ |
| C. 数据库(SQLAlchemy) | 可查询；支持多用户 | 较重；当前不需要 | ⚠️ 预留 |

**结论**: 当前使用B方案（文件系统），C方案（数据库）模型已建好作为后续扩展。

---

## 模块依赖关系（v3.3实际版）

```
frontend/app.py
    └──→ opc_manager/task_engine_v3.py (TaskEngineV3)
            ├──→ opc_hr/web_search.py (WebSearchMCP)
            ├──→ opc_manager/scenario_engine_v2.py (ScenarioEngineV2) [可选]
            └──→ 无 LLM 调用 (v3.3不依赖MockLLM)

废弃模块（不再被生产流程调用）:
    ├── opc_manager/task_engine.py (v1 - 调用MockLLM返回JSON)
    └── opc_manager/task_engine_v2.py (v2 - 使用_get_content_template()返回空模板)

保留但未接入生产:
    ├── opc_manager/llm_service.py (LLMService抽象层 - 待v3.4接入)
    └── opc_manager/platform_adapters.py (平台适配器 - 待配置API Key)
```

---

## 关键技术约束

| 约束 | 影响 | 应对策略 |
|------|------|---------|
| Python 3.9 | 不支持asynccontextmanager | FastAPI用@app.on_event替代lifespan |
| DuckDuckGo搜索延迟 | 5-10秒/次 | 命令行正常；Streamlit需异步优化 |
| Streamlit单线程 | 长时间操作阻塞UI | P0待解决：后台线程或缓存 |
| 中文搜索质量 | 长尾词相关性不稳定 | 搜索关键词提取优化 + 多源整合 |

---

## ⚡ v3.5 架构变更（四角色共识）

> **决策文档**: [v3.5-consensus-decision-record.md](../v3.5-consensus-decision-record.md)

### ADR-008: SearchResultProcessor — 后处理层替代引擎替换

**决策**: 保持DuckDuckGo数据源，新增SearchResultProcessor后处理层  
**理由**: 换引擎需API Key+2周集成，Processor纯规则1天交付  
**风险**: 处理能力有限，极端情况仍可能返回低质量结果

### ADR-009: RAG混合模式 — 模板骨架 + LLM填充

**决策**: _gen_real_*()生成结构骨架 → LLM基于搜索上下文填充具体内容  
**理由**: 纯LLM不可控(幻觉)、纯模板无针对性 → RAG兼顾结构与智能  
**降级**: LLM异常时自动回退到v3.4模板模式

### ADR-010: Streamlit异步轮询 — 保持框架不变

**决策**: 不换FastAPI/Vue，改为AsyncTaskExecutor后台线程+前端2s轮询  
**理由**: 迁移成本2周+ vs 异步改造0.5天，降低风险优先  
**局限**: 轮询有2s延迟感，不适用高并发场景

### v3.5 新增组件架构图

```
TaskEngineV3.execute(user_input, session_ctx)
    │
    ├── [P0-4] SessionContextManager.get_context_for_llm()  ← 新增
    │       └── 构建含历史的enriched_input
    │
    ├── InputValidator.sanitize()  ← 已有 (v3.4)
    ├── IntentClassifier.classify()  ← 已有 (v3.4)
    │
    ├── [P0-3] AsyncTaskExecutor.submit(enriched_input)  ← 新增
    │       └── 立即返回 task_id (不阻塞!)
    │
    └── [后台线程] 
            ├── _search(query) → SearchCache  ← 已有
            │   └── WebSearchMCP.search()
            │       └── [P0-1] SearchResultProcessor.process(raw)  ← 新增
            │           ├── _filter_irrelevant()  关键词过滤
            │           ├── _score_relevance()     TF-IDF评分
            │           └── _fallback_knowledge_base() 兜底
            │
            ├── [P0-2] LLMEnhancedContentGenerator.generate()  ← 新增
            │   或 └── _gen_real_plan/_gen_real_report()  ← 已有(Fallback)
            │
            ├── save_deliverable()  ← 已有
            └── [P0-4] SessionContextManager.add_turn()  ← 新增
```

### 新模块接口规格

**SearchResultProcessor** (`opc_manager/search_processor.py`, ~200行):
```python
class SearchResultProcessor:
    def process(self, query, raw_results) -> ProcessedResult:
        """过滤→评分→排序→截断"""
    def _extract_keywords(self, query) -> List[str]
    def _filter_irrelevant(self, keywords, results) -> List[Dict]
    def _score_relevance(self, query, results) -> List[Dict]
```

**LLMEnhancedContentGenerator** (`opc_manager/llm_content.py`, ~300行):
```python
class LLMEnhancedContentGenerator:
    def generate_plan(self, query, search_results) -> str      # RAG方案
    def generate_report(self, query, search_results) -> str    # RAG报告
    def _build_prompt(self, query, skeleton, context) -> str
    def _call_llm(self, prompt) -> str                           # 可插拔backend
```

**AsyncTaskExecutor** (`opc_manager/async_executor.py`, ~150行):
```python
class AsyncTaskExecutor:
    TASK_PENDING / TASK_RUNNING / TASK_DONE / TASK_FAILED
    def submit(self, prompt) -> str        # → task_id
    def get_status(self, task_id) -> dict  # → {status,result,filepath,error}
    def cancel(self, task_id) -> bool
```

**SessionContextManager** (`opc_manager/session_context.py`, ~150行):
```python
class SessionContextManager:
    def add_turn(self, user_msg, asst_msg, task_type, filepath)
    def get_context_for_llm(self, max_turns=5) -> str
    def get_last_result(self) -> Optional[dict]
    def get_history_summary(self) -> str
```

### 数据流对比

| | v3.4 (当前) | v3.5 (目标) |
|--|-----------|-----------|
| **输入→响应** | 同步阻塞(~8s) | 异步非阻塞(<1s提交+轮询) |
| **搜索结果** | 原样返回 | Processor过滤/评分/排序 |
| **内容生成** | 纯模板填充 | RAG混合(LLM或模板Fallback) |
| **状态管理** | 无状态 | SessionContextManager(20轮上限) |
| **前端体验** | st.spinner超时崩溃 | st.status+轮询+取消按钮 |

---

> **文档维护说明**：本架构文档反映v3.5四角色共识提升后的系统架构。核心变化是4个新组件(SearchResultProcessor/LLMEnhancedContentGenerator/AsyncTaskExecutor/SessionContextManager)的引入，以及从同步阻塞到异步轮询的执行模型变更。详见[v3.5-consensus-decision-record.md](../v3.5-consensus-decision-record.md)。
