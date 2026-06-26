# OPC-Agents 开发路线图 v3.5 (四角色共识提升版)

> ⚠ **文档状态说明**: 本文档基于 v3.5 四角色共识编写，V35-T01~T16 任务大部分已在 v0.1.5/v0.1.6 中完成。最新进度请参考 `docs/CHANGELOG.md` 和 `docs/internal/v0.1.6-optimization-consensus.md`。

## 更新履历

| 版本 | 日期 | 状态 | 说明 |
|------|------|------|------|
| **v3.5** | **2026-04-16** | **🔄 执行中** | **四角色共识：SearchResultProcessor + LLM内容 + 异步化 + 多轮对话 (4个P0)** |
| **v3.4** | **2026-04-16** | **✅ 已交付** | **InputValidator + SearchCache + 45核心测试 + 代码注释完善 + 0 failed** |
| **v3.3** | **2026-04-16** | **✅ 已交付** | **零占位符 + TaskEngineV3 + 真实搜索 + 文件交付** |
| v3.2 | 2026-04-16 | ✅ 已交付 | 成果物文件生成 + 下载按钮 |
| v3.1.1 | 2026-04-16 | ✅ 已交付 | DuckDuckGo真实搜索替代MockLLM |
| v3.1 | 2026-04-16 | ✅ 已交付 | TaskEngine(v1)意图分类+任务执行 |
| v3.0 | 2026-04-15 | ✅ 已规划 | Phase 3完整计划（14个任务） |
| v2.2 | 2026-04-15 | ✅ 已交付 | Phase 2: 6人格+Detector V2+FlywheelTracker |
| v2.1 | 2026-04-14 | ✅ 已交付 | Phase 1 MVP: 场景引擎+检测器+人格 |

---

## ⚡ v3.3 实际完成情况 vs 原始规划

### 原始Phase 3路线图（14个任务）

| 任务ID | 任务名称 | 规划状态 | 实际状态 | 备注 |
|--------|---------|---------|---------|------|
| P3-T01 | Web应用基础框架 | 计划中 | ✅ **已完成** | Streamlit前端 |
| P3-T02 | 对话式交互界面 | 计划中 | ✅ **已完成** | ChatUI + Markdown渲染 |
| P3-T03 | 业务类型自动识别UI | 计划中 | ✅ **已完成** | 后台自动识别，用户无感 |
| P3-T04 | 飞轮仪表盘页面 | 计划中 | ✅ **已完成** | 📊成长页 |
| P3-T05 | LLM服务层抽象 | 计划中 | ⚠ **部分完成** | 抽象层OK，未接入生产 |
| P3-T06 | detect_by_llm实现 | 计划中 | ❌ **未实施** | Mock导致崩溃，延后 |
| P3-T07 | 数据库模型设计 | 计划中 | ✅ **已完成** | 6个ORM模型 |
| P3-T08 | FlywheelTracker DB化 | 计划中 | ✅ **已完成** | FlywheelTrackerDB |
| P3-T09 | 平台适配器抽象 | 计划中 | ✅ **已完成** | PlatformAdapter基类 |
| P3-T10 | 小红书适配器 | 计划中 | ⚠ **Mock实现** | 待API Key配置 |
| P3-T11 | Gumroad适配器 | 计划中 | ⚠ **Mock实现** | 待API Key配置 |
| P3-T12 | CI/CD流水线 | 计划中 | ❌ **未实施** | GitHub Actions待建 |
| P3-T13 | Docker容器化 | 计划中 | ❌ **未实施** | 待v4.0 |
| P3-T14 | 文档更新 | 计划中 | ✅ **正在进行** | 本文档 |

### v3.3 新增（原始规划中没有的）

| 任务ID | 任务名称 | 来源 | 状态 | 影响 |
|--------|---------|------|------|------|
| **P3-X1** | **TaskEngineV3 (零占位符)** | **用户反馈驱动** | ✅ **已完成** | **核心引擎替换** |
| **P3-X2** | **DuckDuckGo真实搜索集成** | **用户反馈驱动** | ✅ **已完成** | **真实数据源** |
| **P3-X3** | **成果物文件交付系统** | **用户反馈驱动** | ✅ **已完成** | **deliverables/** |
| **P3-X4** | **📁成果物管理页面** | **用户反馈驱动** | ✅ **已完成** | **文件库UI** |

---

## 时间线（实际 vs 规划）

```
2026-04-14  ──────────────────────────────────────────────
  │
  ├── v2.1.0: Phase 1 MVP (38测试通过)
  │   ScenarioEngineV1 + Detector + Persona(3)
  │
2026-04-15  ──────────────────────────────────────────────
  │
  ├── v2.2.0: Phase 2 完成 (65测试通过)
  │   6人格变体 + DetectorV2(100%) + FlywheelTracker + ScenarioV2
  │
  ├── Phase 3 规划 (多角色共识)
  │   PRD_V3 + ARCHITECTURE_V3 + TEST_PLAN_V3 + ROADMAP_V3
  │
2026-04-16  ──────────────────────────────────────────────  ← 今天
  │
  ├── v3.0: Web前端重构 (Streamlit)
  │   首屏即对话 + 场景快捷入口 + 防御性错误处理
  │
  ├── v3.1: TaskEngine(v1) — ❌ 失败
  │   调用MockLLM → 返回JSON给用户 → 用户崩溃
  │
  ├── v3.1.1: 真实搜索接入
  │   DuckDuckGo替代Mock → 但仍用task_engine_v2空模板
  │
  ├── v3.2: 成果物交付功能
  │   deliverables/ + 下载按钮 + 成果物库页面
  │   ❌ 发现文件全是___占位符！
  │
  ├── v3.3: ⭐ 彻底修复 (当前版本)
  │   TaskEngineV3 (660行) = 零占位符铁律
  │   _gen_real_plan() / _gen_real_report()
  │   真实搜索 + 结构化输出 + 文件交付
  │   ✅ 命令行验证全部通过
  │
  └── 文档全面更新 (README + PRD + 架构 + 测试计划 + 路线图)
      ← 你在这里
```

---

## v3.4 路线图（下一步计划）

### P0 - 必须解决

| ID | 任务 | 目标 | 预计工作量 | 依赖 |
|----|------|------|----------|------|
| V34-01 | **Streamlit超时修复** | 任务执行不再显示"未返回结果" | 2天 | 无 |
| V34-02 | **GLM-4 API接入** | 内容质量从规则引擎升级到LLM生成 | 3天 | config.toml已有API Key |

### P1 - 应该尽快做

| ID | 任务 | 目标 | 预计工作量 | 依赖 |
|----|------|------|----------|------|
| V34-03 | 会话持久化(DB) | 刷新页面不丢失历史 | 2天 | db_models已就绪 |
| V34-04 | PDF/Word导出 | 成果物支持更多格式 | 3天 | 无 |
| V34-05 | 多轮对话上下文 | 支持追问和修正 | 2天 | V34-03 |

### P2 - 锦上添花

| ID | 任务 | 目标 | 预计工作量 | 依赖 |
|----|------|------|----------|------|
| V35-01 | 多搜索引擎整合 | 百度/Google/Bing补充DuckDuckGo | 3天 | 无 |
| V35-02 | 平台API真实对接 | 小红书/Gumroad真实数据 | 5天 | API Key |
| V35-03 | CI/CD流水线 | GitHub Actions自动化测试 | 2天 | 无 |
| V35-04 | Docker部署 | 一键启动 | 1天 | 无 |
| V35-05 | 国际化(i18n) | 英文界面支持 | 2天 | 无 |

---

## 里程碑回顾

### ✅ Milestone M1: MVP (v2.1) — 已完成
**日期**: 2026-04-14  
**目标**: 可运行的最小可用产品  
**交付物**:
- [x] ScenarioEngineV1 (9场景)
- [x] BusinessTypeDetector (关键词匹配)
- [x] PersonaManager (3基础人格)
- [x] 38个单元测试通过

### ✅ Milestone M2: 智能增强 (v2.2) — 已完成
**日期**: 2026-04-15  
**目标**: 更智能的检测和更丰富的能力  
**交付物**:
- [x] ScenarioEngineV2 (工作流编排)
- [x] BusinessTypeDetectorV2 (100%准确率)
- [x] PersonaManager (6种人格)
- [x] FlywheelTracker (五维飞轮)
- [x] 65个测试通过

### ✅ Milestone M3: 产品化 (v3.0-v3.3) — 已完成
**日期**: 2026-04-16  
**目标**: 从开发工具进化为可使用的产品  
**交付物**:
- [x] Streamlit Web前端
- [x] TaskEngineV3 (零占位符执行引擎)
- [x] WebSearchMCP (真实网络搜索)
- [x] 成果物文件交付系统
- [x] 400+测试用例
- [x] 完整文档体系

### 🎯 Milestone M4: 生产级 (v3.4+) — 进行中
**目标**: 解决已知问题，达到生产可用标准  
**关键指标**:
- [ ] Streamlit超时问题修复
- [ ] LLM(GLM-4)接入生产
- [ ] 会话持久化
- [ ] PDF/Word导出
- [ ] CI/CD自动化
- [ ] 测试覆盖率 >90%

---

## 关键决策记录

| # | 决策 | 日期 | 原因 | 结果 |
|---|------|------|------|------|
| D1 | 选择Streamlit而非Flask/FastAPI作为主前端 | 04-15 | 快速原型；降低门槛 | ✅ 快速上线，但遇到超时问题 |
| D2 | 废弃TaskEngine(v1/v2)，新建v3 | 04-16 | v1返回JSON、v2返回空模板 | ✅ 彻底解决问题 |
| D3 | 不接入LLM到生产流程 | 04-16 | MockLLM导致前端崩溃 | ⚠ 临时决定，v3.4需重新评估 |
| D4 | 使用文件系统而非DB存储成果物 | 04-16 | 简单直接；用户可查看文件 | ✅ 合理，DB留作扩展 |
| D5 | DuckDuckGo作为唯一搜索源 | 04-16 | 免费;无需API Key;够用 | ⚠ 中文质量待提升 |

---

## 资源消耗统计

| 维度 | v2.1 | v2.2 | v3.0 | v3.3 |
|------|------|------|------|------|
| **代码行数** | ~2000 | ~3500 | ~6000 | ~8500 |
| **测试用例数** | 38 | 65 | 112 | 400+ |
| **核心模块数** | 5 | 8 | 12 | 14 |
| **文档数量** | 1 | 3 | 9 | 10 |
| **Git提交数** | 3 | 5 | 12 | 25+ |
| **开发人日** | 1 | 1.5 | 2 | 3.5 |

---

> **文档维护说明**：本路线图反映OPC-Agents从v2.1到v3.3的实际演进过程。最关键的转折点是v3.3——由用户反馈驱动的"零占位符"革命，彻底改变了产品的质量和定位。

---

# ⚡ v3.5 四角色共识提升 — 执行计划

## 触发事件与决策依据

**触发**: 用户提出"从用户角度来看，这是一款好产品吗？" → 四角色独立评审 → 全票通过4个P0改进项  
**权威参考**: [v3.5-consensus-decision-record.md](../internal/v3.5-consensus-decision-record.md)  
**共识日期**: 2026-04-16 (PM/ARCH/QA/UI 4/4全票)

### v3.5 解决的核心问题（来自用户旅程走查）

| 问题ID | 用户痛点 | 严重度 | 解决方案 | 对应P0 |
|--------|---------|--------|---------|--------|
| U-1 | "我要Q2营销方案，你给我书信格式？" | 🔴致命 | SearchResultProcessor后处理层 | P0-1 |
| U-2 | "基准值待测——这我自己也会写" | 🔴致命 | LLMEnhancedContentGenerator RAG混合模式 | P0-2 |
| U-3 | "还在处理吗？卡死了吗？" (Streamlit超时) | 🟠严重 | AsyncTaskExecutor异步执行+轮询 | P0-3 |
| U-4 | "第三阶段时间太长，能改吗？" → 不能 | 🟠严重 | SessionContextManager多轮对话 | P0-4 |
| U-5 | "9个按钮，我该点哪个？" (认知负荷高) | 🟡中等 | UI首屏简化+引导流程 | P1-1 (延后) |

---

## v3.5 任务清单（V35-T01 ~ V35-T12）

### Week 1: 基础设施 + 搜索质量修复

| 任务ID | 任务名称 | 优先级 | 状态 | 依赖 | 预估工作量 | 交付物 |
|--------|---------|--------|------|------|----------|--------|
| **V35-T01** | **实现SearchResultProcessor核心** | **P0** | ⏳ 待开始 | 无 | 1.5天 | `opc_manager/search_processor.py` (~200行) |
| **V35-T02** | **编写TestSearchRelevance测试(5个)** | **P0** | ⏳ 待开始 | T01 | 0.5天 | `tests/test_search_processor.py` |
| **V35-T03** | **实现AsyncTaskExecutor** | **P0** | ⏳ 待开始 | 无 | 1天 | `opc_manager/async_executor.py` (~150行) |
| **V35-T04** | **编写TestAsyncExecution测试(4个)** | **P0** | ⏳ 待开始 | T03 | 0.5天 | `tests/test_async_executor.py` |
| **V35-T05** | **前端改造: 集成AsyncTaskExecutor** | **P0** | ⏳ 待开始 | T03 | 1天 | `frontend/app.py` 改造 (submit→poll→display) |

### Week 2: 内容智能 + 多轮对话

| 任务ID | 任务名称 | 优先级 | 状态 | 依赖 | 预估工作量 | 交付物 |
|--------|---------|--------|------|------|----------|--------|
| **V35-T06** | **实现LLMEnhancedContentGenerator** | **P0** | ⏳ 待开始 | 无 | 2天 | `opc_manager/llm_content.py` (~300行) |
| **V35-T07** | **编写TestContentTargeting(6个)+TestLLMFallback(3个)** | **P0** | ⏳ 待开始 | T06 | 1天 | `tests/test_llm_content.py` |
| **V35-T08** | **实现SessionContextManager** | **P0** | ⏳ 待开始 | 无 | 1天 | `opc_manager/session_context.py` (~150行) |
| **V35-T09** | **编写TestSessionIteration测试(5个)** | **P0** | ⏳ 待开始 | T08 | 0.5天 | `tests/test_session_context.py` |

### Week 3: 集成 + UI优化

| 任务ID | 任务名称 | 优先级 | 状态 | 依赖 | 预估工作量 | 交付物 |
|--------|---------|--------|------|------|----------|--------|
| **V35-T10** | **TaskEngineV3集成4个新组件** | **P0** | ⏳ 待开始 | T01,T03,T06,T08 | 1.5天 | `task_engine_v3.py` 改版 |
| **V35-T11** | **UI三项改进(首屏/等待/CTA)** | **P1** | ⏳ 待开始 | T05 | 1天 | `frontend/app.py` UI优化 |
| **V35-T12** | **编写TestIntegrationV35集成测试(12个)** | **P0** | ⏳ 待开始 | T10 | 1.5天 | `tests/test_integration_v35.py` |

### Week 4: 回归测试 + 发布准备

| 任务ID | 任务名称 | 优先级 | 状态 | 依赖 | 预估工作量 | 交付物 |
|--------|---------|--------|------|------|----------|--------|
| **V35-T13** | **全量回归测试(82个用例)** | **P0** | ⏳ 待开始 | T02,T04,T07,T09,T12 | 1天 | 测试报告 + 修复 |
| **V35-T14** | **文档更新(CDR→PRD→ARCH→TEST→ROADMAP闭环)** | **P0** | ⏳ 待开始 | T13 | 1天 | 全套文档v3.5最终版 |
| **V35-T15** | **性能基准测试+优化** | **P1** | ⏳ 待开始 | T13 | 1天 | 性能报告 |
| **V35-T16** | **v3.5发布+CHANGELOG** | **P0** | ⏳ 待开始 | T14 | 0.5天 | Git tag + Release Notes |

---

## v3.5 里程碑定义

### 🎯 Milestone M1: 搜索质量修复 (Week 1 Day 1-3)
**目标**: 用户输入"Q2营销方案"不再返回"书信格式""写小说"等无关结果  
**关键指标**:
- [ ] SearchResultProcessor.process() 通过 G-SEARCH-01 门禁
- [ ] TestSearchRelevance 5个测试全部通过
- [ ] 关键词提取准确率 >= 80%（人工抽检10条）
- [ ] 无关结果过滤率 >= 90%（模拟数据集）

**验收标准**:
```python
# 门禁脚本示例
processor = SearchResultProcessor()
result = processor.process("Q2营销方案", irrelevant_results)
assert len(result.results) == 0 or \
       all('营销' in r['title'] or 'Q2' in r['title'] for r in result.results[:3])
```

### 🎯 Milestone M2: 异步化改造完成 (Week 1 Day 4-5 + Week 2 Day 1)
**目标**: Streamlit前端不再因任务超时崩溃，用户体验流畅  
**关键指标**:
- [ ] AsyncTaskExecutor.submit() 返回task_id < 100ms
- [ ] get_status() 轮询间隔可配置（默认1s）
- [ ] cancel() 成功率 >= 95%
- [ ] 前端集成后无超时报错（实测10次）

**验收标准**:
```python
# 门禁脚本示例
executor = AsyncTaskExecutor()
tid = executor.submit(long_running_task, timeout=30)
assert executor.get_status(tid) in ['pending', 'running']
time.sleep(1)
assert executor.cancel(tid) == True
```

### 🎯 Milestone M3: 内容智能升级 (Week 2 Day 1-3)
**目标**: 生成内容包含用户特定业务信息，消除"基准值待测"等通用占位符  
**关键指标**:
- [ ] LLMEnhancedContentGenerator.generate() 通过 G-CONTENT-01 门禁
- [ ] TestContentTargeting 6个测试全部通过
- [ ] TestLLMFallback 3个降级测试全部通过
- [ ] 业务信息注入率 >= 70%（含产品名/数字/行业关键词）

**验收标准**:
```python
# 门禁脚本示例
generator = LLMEnhancedContentGenerator()
result = generator.generate(
    user_input="AI写作助手，月活5000→10000",
    template=skeleton,
    search_results=relevant_search_data,
)
assert 'AI写作助手' in result.content
assert '5000' in result.content and '10000' in result.content
assert '基准值待测' not in result.content
```

### 🎯 Milestone M4: 多轮对话支持 (Week 2 Day 4-5)
**目标**: 用户可以基于前一轮结果进行迭代修正（如"第三阶段缩短到2周"）  
**关键指标**:
- [ ] SessionContextManager.add_turn() 正确保存上下文
- [ ] get_context_for_llm() 返回格式化的历史记录
- [ ] 轮次上限20轮强制生效
- [ ] TestSessionIteration 5个测试全部通过

**验收标准**:
```python
# 门禁脚本示例
session = SessionContextManager(max_turns=20)
session.add_turn("写Q2方案", response1, sources)
session.add_turn("第三阶段缩短到2周", response2)
ctx = session.get_context_for_llm()
assert "Q2方案" in ctx and "缩短到2周" in ctx
```

### 🎯 Milestone M5: 全面集成+发布 (Week 3-4)
**目标**: 4个P0组件全部集成，全量测试82个通过，文档闭环，正式发布v3.5  
**关键指标**:
- [ ] TestIntegrationV35 12个集成测试全部通过
- [ ] 全量回归测试 82/82 通过（0 failed）
- [ ] 前端E2E流程完整（输入→异步执行→结果展示→下载→迭代）
- [ ] 全套文档更新完毕（PRD/ARCH/TEST/ROADMAP/CDR）
- [ ] CHANGELOG_V35.md 发布说明就绪

---

## v3.5 执行时间线（甘特图风格）

```
2026-04-16 (今天) ──────────────────────────────────────────────
│
├── Week 1 (Day 1-3):  M1 搜索质量修复
│   ├── V35-T01: SearchResultProcessor 实现     [=====>          ]
│   └── V35-T02: TestSearchRelevance 编写        [======>        ]
│
├── Week 1 (Day 4-5):  M2 异步化改造 (Part 1)
│   ├── V35-T03: AsyncTaskExecutor 实现         [==========>     ]
│   ├── V35-T04: TestAsyncExecution 编写         [============>   ]
│   └── V35-T05: 前端集成AsyncTaskExecutor        [==============> ]
│
├── Week 2 (Day 1-3):  M3 内容智能升级
│   ├── V35-T06: LLMEnhancedContentGenerator      [==============>]
│   └── V35-T07: TestContentTargeting + Fallback  [============> ]
│
├── Week 2 (Day 4-5):  M4 多轮对话支持
│   ├── V35-T08: SessionContextManager            [=============>  ]
│   └── V35-T09: TestSessionIteration             [==============>]
│
├── Week 3 (Day 1-2):  集成 + UI优化
│   ├── V35-T10: TaskEngineV3集成4组件            [==============>]
│   ├── V35-T11: UI三项改进                       [==========>     ]
│   └── V35-T12: TestIntegrationV35               [============>   ]
│
├── Week 3 (Day 3-5):  回归测试
│   └── V35-T13: 全量回归(82个)                   [==============>]
│
└── Week 4:           M5 发布准备
    ├── V35-T14: 文档闭环                        [==============>]
    ├── V35-T15: 性能基准                        [========>       ]
    └── V35-T16: v3.5发布!                       [★ RELEASE ★    ]
```

---

## 风险矩阵与缓解措施

| 风险ID | 风险描述 | 概率 | 影响 | 缓解措施 | 负责人 |
|--------|---------|------|------|---------|--------|
| R-01 | DuckDuckGo搜索结果质量仍然差（即使处理后） | 中 | 高 | ADR-008决策：先做规则处理；效果不够再换搜索引擎 | ARCH |
| R-02 | GLM-4 API不稳定或响应慢 | 中 | 高 | ADR-009决策：RAG混合模式+优雅降级到模板 | ARCH |
| R-03 | Streamlit异步改造引入新bug | 低 | 高 | 先在CLI验证AsyncTaskExecutor，再集成前端 | QA |
| R-04 | 多轮对话上下文膨胀导致LLM成本过高 | 中 | 中 | 限制20轮+截断策略（保留最近5轮详情） | PM |
| R-05 | 4个P0组件开发进度延期 | 中 | 高 | 同步推进测试（每个组件完成后立即写测试） | 全员 |
| R-06 | 集成测试发现架构不兼容问题 | 低 | 高 | 架构设计阶段已预留接口（见ARCHITECTURE_DESIGN_V3.md Section 3.5） | ARCH |

---

## 资源需求评估

| 资源类型 | v3.5 需求 | 现有资源 | 差距 | 应对方案 |
|---------|----------|---------|------|---------|
| 开发时间 | ~16人日 | 可用 | ✅ 充足 | 按4周节奏推进 |
| GLM-4 API配额 | ~1000次调用/月 | config.toml已有Key | ✅ 已有 | 监控用量 |
| DuckDuckGo访问 | 无限制 | WebSearchMCP已接入 | ✅ 已有 | — |
| 测试环境 | pytest + CI/CD | GitHub Actions待建 | ⚠ 部分 | 本地pytest先跑通 |
| 文档维护 | 5份文档同步更新 | 已有体系 | ✅ 充足 | CDR为单一权威来源 |

---

## v3.5 → v3.6 展望

### 已识别的后续改进方向（来自四角色评审的P1/P2项）

| ID | 改进项 | 来源角色 | 预计版本 | 备注 |
|----|--------|---------|---------|------|
| P1-1 | UI首屏简化+等待体验+CTA优化 | UI Designer | v3.6 | 当前延后，v3.5聚焦功能 |
| P1-2 | 5类新测试门禁自动化 | QA Expert | v3.5.1 | 已纳入TEST_PLAN_V3.md |
| P2-1 | 多搜索引擎整合(Baidu/Google) | PM | v3.6 | 取决于P0-1效果 |
| P2-2 | PDF/Word导出功能 | PM | v3.6 | 用户高频需求 |
| P2-3 | 会话持久化(DB存储) | ARCH | v3.6 | 刷新页面不丢失历史 |
| P2-4 | CI/CD流水线(GitHub Actions) | SOLO CODER | v3.5.1 | 自动化回归测试 |
| P2-5 | 国际化(i18n)英文界面 | UI Designer | v3.7 | 海外用户扩展 |

### 成功标准（v3.5发布时检验）

| 维度 | v3.4 基线 | **v3.5 目标** | 测量方法 |
|------|----------|-------------|---------|
| 搜索相关性 | ❌ 返回无关结果 | ✅ Top3结果相关率>=80% | TestSearchRelevance SR-002 |
| 内容针对性 | ❌ 含"基准值待测" | ✅ 占位符消除率100% | G-CONTENT-01门禁 |
| 前端稳定性 | ❌ 5s+超时崩溃 | ✅ 异步执行无阻塞 | G-ASYNC-01门禁 |
| 迭代能力 | ❌ 单次对话 | ✅ 支持20轮多轮对话 | G-ITERATE-01门禁 |
| 测试覆盖 | 45个用例 | **82个用例(+82%)** | pytest统计 |
| 文档完整性 | 4份文档 | **6份文档(CDR新增)** | 文档清单检查 |

---

> **文档维护说明**：本路线图已从v3.3升级到v3.5，反映四角色共识决策的完整执行计划。核心变更是：
> 1. **16个具体任务**（V35-T01~T16），按4周时间线排列
> 2. **5个里程碑**（M1~M5），每个有明确的验收标准和门禁脚本
> 3. **风险矩阵**（6项风险+缓解措施）
> 4. **成功标准表**（v3.4基线 vs v3.5目标）
>
> **执行原则**: 文档先行 → 按文档推进 → 完成即更新文档 → 闭环确认
>
> **权威参考**: [v3.5-consensus-decision-record.md](../internal/v3.5-consensus-decision-record.md)（唯一权威决策来源）
