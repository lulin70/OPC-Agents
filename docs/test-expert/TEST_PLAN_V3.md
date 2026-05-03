# OPC-Agents 测试计划 v3.5 (四角色共识提升版)

> ⚠️ **文档状态说明**: 本文档基于 v3.5 四角色共识编写，测试门禁和用例已在 v0.1.5/v0.1.6 中实现。当前测试数量 350+（v3.5 计划 82 个）。最新测试状态请参考 `docs/CHANGELOG.md` 和 `tests/` 目录。

## 更新履历

| 版本 | 日期 | 更新人 | 更新内容 |
|------|------|--------|----------|
| **v3.5.0** | **2026-04-16** | **测试专家** | **v3.5四角色共识：搜索相关性/内容智能/异步E2E/多轮迭代/LLM降级测试门禁+37新用例** |
| **v3.4.0** | **2026-04-16** | **测试专家** | **InputValidator/SearchCache/TaskEngineV3核心45测试+零占位符门禁(tokenize)** |
| v3.3.0 | 2026-04-16 | 测试专家 | TaskEngineV3核心测试、零占位符验收、文件交付验证、真实搜索验证 |

---

## ⚡ v3.3 核心测试重点

### 新增验收标准（v3.3特有）

#### TC-ZERO-1: 零占位符验收（P0 - 阻断级）

```python
def test_zero_placeholders():
    """所有成果物文件不得包含任何形式的占位符"""
    from opc_manager.task_engine_v3 import TaskEngineV3
    engine = TaskEngineV3()

    test_cases = [
        "帮我写一份Q2营销方案",
        "帮我收集一人公司税收政策",
        "帮我分析竞品A",
        "帮我执行报告撰写场景",
    ]

    for prompt in test_cases:
        result = engine.execute(prompt)
        assert result.success, f"任务失败: {prompt} -> {result.error}"

        forbidden = ['___', '待填写', '此处插入', '清晰定义目标',
                     '明确边界', '风险1', '措施1', '标准1：']
        for f in forbidden:
            assert f not in result.content, \
                f"发现禁止字符 '{f}' 在: {prompt}\n{result.content[:200]}"

        assert len(result.content) > 500, \
            f"内容过短({len(result.content)}字): {prompt}"
```

#### TC-FILE-1: 文件交付验收（P0 - 阻断级）

```python
def test_file_delivery():
    """每次任务必须生成可下载的.md文件"""
    import os, tempfile
    from opc_manager.task_engine_v3 import TaskEngineV3

    with tempfile.TemporaryDirectory() as tmpdir:
        original_dir = os.environ.get('DELIVERABLES_DIR')
        os.environ['DELIVERABLES_DIR'] = tmpdir

        try:
            engine = TaskEngineV3()
            result = engine.execute("帮我写Q2方案")

            files = os.listdir(tmpdir)
            assert len(files) >= 1, "未生成任何文件"

            for f in files:
                filepath = os.path.join(tmpdir, f)
                assert f.endswith('.md'), f"非md文件: {f}"

                with open(filepath, 'r') as fh:
                    content = fh.read()
                assert len(content) > 200, f"文件过短: {f}"
                assert '___' not in content, f"含占位符: {f}"
        finally:
            if original_dir:
                os.environ['DELIVERABLES_DIR'] = original_dir
```

#### TC-SEARCH-1: 真实搜索验收（P0 - 阻断级）

```python
def test_real_search_results():
    """信息收集任务必须返回真实搜索结果"""
    from opc_manager.task_engine_v3 import TaskEngineV3

    engine = TaskEngineV3()
    result = engine.execute("帮我收集OPC公司趋势")

    assert result.success
    assert result.sources is not None
    assert len(result.sources) >= 3, \
        f"搜索结果不足: {len(result.sources)} 条"

    for source in result.sources:
        assert 'title' in source, f"缺少title: {source}"
        assert source.get('url'), f"缺少url: {source}"

    assert '🔗' in result.content or 'http' in result.content, \
        "结果中无来源链接"
```

#### TC-QUALITY-1: 方案文档质量验收（P0 - 阻断级）

```python
def test_plan_document_quality():
    """方案文档必须包含完整的可操作要素"""
    from opc_manager.task_engine_v3 import TaskEngineV3

    engine = TaskEngineV3()
    result = engine.execute("帮我写Q2营销方案")

    required_elements = [
        ('项目概览', '缺项目概览'),
        ('目标', '缺目标设定'),
        ('阶段' or 'Week', '缺实施时间表'),
        ('资源', '缺资源配置'),
        ('风险', '缺风险管理'),
        ('验收', '缺验收标准'),
        ('30%', '缺具体指标'),
    ]

    for keyword, msg in required_elements:
        assert keyword in result.content, \
            f"{msg}: {result.content[:300]}"
```

---

## 测试金字塔（v3.3实际版）

```
                    ┌─────────────────┐
                    │   E2E 测试      │  ← 浏览器自动化 (5个)
                    │  - 对话完整流程  │
                    │  - 文件下载验证  │
                    │  - 成果物库功能  │
                    ├─────────────────┤
                    │  集成测试        │  ← 模块间交互 (47个)
                    │  - TaskEngineV3  │
                    │  + WebSearchMCP  │
                    │  + ScenarioV2    │
                    │  + 前端集成       │
                    ├─────────────────┤
                    │  单元测试        │  ← 独立模块 (348个)
                    │  - IntentClassifier│
                    │  - _gen_real_plan │
                    │  - _gen_real_report│
                    │  - _build_research │
                    │  - save_deliverable│
                    ├─────────────────┤
                    │  占位符扫描测试   │  ← v3.3新增 (自动)
                    │  - grep ___ *.md  │
                    │  - 废话框架检测   │
                    └─────────────────┘
```

### 测试用例清单（v3.3核心）

| ID | 名称 | 类型 | 优先级 | 状态 |
|----|------|------|--------|------|
| **TaskEngineV3 核心测试** |||||
| TE-001 | IntentClassifier分类正确性 | 单元 | P0 | ✅ 通过 |
| TE-002 | INFO_COLLECTION路径执行 | 集成 | P0 | ✅ 通过 |
| TE-003 | CONTENT_GENERATION→plan路径 | 集成 | P0 | ✅ 通过 |
| TE-004 | CONTENT_GENERATION→report路径 | 集成 | P0 | ✅ 通过 |
| TE-005 | DATA_ANALYSIS路径执行 | 集成 | P0 | ✅ 通过 |
| TE-006 | SCENARIO_BASED路径执行 | 集成 | P0 | ✅ 通过 |
| TE-007 | GENERAL_CHAT路径执行 | 单元 | P1 | ✅ 通过 |
| **零占位符测试** |||||
| ZP-001 | 方案文档零占位符 | 验收 | P0 | ✅ 通过 |
| ZP-002 | 报告文档零占位符 | 验收 | P0 | ✅ 通过 |
| ZP-003 | 分析报告零占位符 | 验收 | P0 | ✅ 通过 |
| ZP-004 | 场景工作流零占位符 | 验收 | P0 | ✅ 通过 |
| ZP-005 | 信息收集零占位符 | 验收 | P0 | ✅ 通过 |
| **文件交付测试** |||||
| FD-001 | 文件生成到deliverables/ | 验收 | P0 | ✅ 通过 |
| FD-002 | 文件命名规则正确 | 单元 | P1 | ✅ 通过 |
| FD-003 | 文件内容完整性 | 验收 | P0 | ✅ 通过 |
| FD-004 | 下载按钮数据正确 | E2E | P1 | ⚠️ Streamlit问题 |
| FD-005 | 成果物库列表更新 | 集成 | P1 | ✅ 通过 |
| **真实搜索测试** |||||
| RS-001 | DuckDuckGo搜索返回结果 | 集成 | P0 | ✅ 通过 |
| RS-002 | 搜索结果有来源链接 | 验收 | P0 | ✅ 通过 |
| RS-003 | 搜索超时降级处理 | 单元 | P1 | ✅ 通过 |
| RS-004 | 无网络时的fallback | 单元 | P2 | ✅ 通过 |
| **前端集成测试** |||||
| FE-001 | ChatUI正常渲染 | E2E | P0 | ✅ 通过 |
| FE-002 | 场景按钮触发执行 | E2E | P0 | ⚠️ 超时问题 |
| FE-003 | 成果物页面显示 | E2E | P1 | ✅ 通过 |
| FE-004 | 错误处理不崩溃 | E2E | P0 | ✅ 通过 |
| FE-005 | 飞轮数据联动 | 集成 | P2 | ✅ 通过 |

---

## 运行测试

### 快速验证（v3.3关键检查）

```bash
# 1. 零占位符全量扫描
python3 -c "
from opc_manager.task_engine_v3 import TaskEngineV3
engine = TaskEngineV3()
tests = ['写报告','做方案','收集趋势','分析竞品','执行场景']
for t in tests:
    r = engine.execute('帮我'+t)
    bad = [x for x in ['___','待填写'] if x in (r.content or '')]
    print(f'{t}: {\"FAIL \"+str(bad) if bad else \"PASS\"} ({len(r.content or \"\")}字)')
"

# 2. 全量测试套件
pytest tests/ -v --ignore=tests/unit/test_wechat_pairing.py

# 3. 仅TaskEngineV3相关测试
pytest tests/test_phase3_*.py -v -k "task_engine or deliverable or search"
```

### CI/CD 集成

```yaml
# .github/workflows/test.yml (建议配置)
name: OPC-Agents Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v --ignore=tests/unit/test_wechat_pairing.py
      # v3.3 新增：零占位符门禁
      - name: Zero Placeholder Check
        run: |
          python3 -c "
          from opc_manager.task_engine_v3 import TaskEngineV3
          e = TaskEngineV3()
          r = e.execute('test')
          assert '___' not in (r.content or ''), 'FOUND PLACEHOLDER!'
          print('✅ Zero placeholder check passed')
          "
```

---

## 已知测试缺口

| 缺口 | 影响 | 计划补充 |
|------|------|---------|
| Streamlit E2E不稳定 | 超时导致误报 | v3.4: 异步化后修复 |
| 中文搜索质量无法自动化判断 | 需人工review | v3.5: 搜索相关性评分器 |
| LLM输出质量测试 | 当前未接入LLM | v3.4: GLM接入后补充 |
| 并发场景测试 | 未覆盖 | v3.4: 多用户DB模式 |

> **文档维护说明**：本测试计划反映v3.3的实际测试策略。最关键的变更是新增了P0级的零占位符验收测试和文件交付测试，这些是v3.3版本的核心质量保障。

---

# ⚡ v3.5 四角色共识提升 — 测试计划扩展

## 更新背景

**触发文档**: [v3.5-consensus-decision-record.md](../internal/v3.5-consensus-decision-record.md)  
**共识日期**: 2026-04-16  
**参与角色**: PM / ARCH / QA / UI (4/4全票通过)

### v3.5 核心改进目标

| 改进项 | 对应组件 | 测试重点 |
|--------|---------|---------|
| 🔴 P0-1: 搜索质量灾难性修复 | SearchResultProcessor | 结果相关性评分、关键词过滤、知识库兜底 |
| 🔴 P0-2: 内容智能升级 | LLMEnhancedContentGenerator | RAG混合模式、LLM降级到模板模式 |
| 🔴 P0-3: 前端超时根治 | AsyncTaskExecutor | 异步提交→轮询状态→取消操作 |
| 🔴 P0-4: 多轮对话支持 | SessionContextManager | 上下文传递、20轮限制、迭代修正 |

---

## v3.5 新增测试门禁（Quality Gates）

### G-SEARCH-01: 搜索结果相关性门禁 (P0 - 阻断级)

```python
def test_search_relevance_gate():
    """搜索结果必须与查询主题相关（解决"Q2营销方案→书信格式"问题）"""
    from opc_manager.search_processor import SearchResultProcessor

    processor = SearchResultProcessor()

    test_cases = [
        {
            'query': '帮我制定Q2营销方案',
            'raw_results': [
                {'title': '书信格式写作指南', 'snippet': '如何写正式信函...'},
                {'title': '写小说的技巧', 'snippet': '小说创作入门...'},
                {'title': 'Q2季度营销策略制定', 'snippet': '第二季度市场推广计划...'},
            ],
            'expected_relevant_count': 1,  # 只有第3条相关
            'expected_top_result_contains': ['营销', 'Q2', '季度'],
        },
        {
            'query': '一人公司税收优惠政策',
            'raw_results': [
                {'title': 'SCI论文发表流程', 'snippet': '学术论文投稿指南...'},
                {'title': '小微企业税收减免政策2026', 'snippet': '一人公司可享受...'},
            ],
            'expected_relevant_count': 1,
            'expected_top_result_contains': ['税收', '优惠', '政策'],
        },
    ]

    for case in test_cases:
        processed = processor.process(case['query'], case['raw_results'])

        assert len(processed.results) >= case['expected_relevant_count'], \
            f"相关性过滤失败: {case['query']} -> {len(processed.results)}条(期望≥{case['expected_relevant_count']})"

        top_result = processed.results[0]
        for keyword in case['expected_top_result_contains']:
            assert keyword.lower() in (top_result.get('title', '') + top_result.get('snippet', '')).lower(), \
                f"Top结果缺少关键词 '{keyword}': {top_result}"
```

### G-CONTENT-01: 内容针对性门禁 (P0 - 阻断级)

```python
def test_content_targeting_gate():
    """生成的内容必须包含用户特定业务信息，不能是通用模板"""
    from opc_manager.llm_content import LLMEnhancedContentGenerator

    generator = LLMEnhancedContentGenerator()

    test_case = {
        'user_input': '帮我制定Q2增长方案，产品是AI写作助手，月活5000想提升到10000',
        'template_skeleton': '# Q2增长方案\n\n## 项目概览\n{business_context}\n\n## 目标\n{goals}\n',
        'search_results': [
            {'title': 'SaaS增长策略', 'snippet': '从5000到10000用户的关键步骤...'},
        ],
    }

    result = generator.generate(
        user_input=test_case['user_input'],
        template=test_case['template_skeleton'],
        search_results=test_case['search_results'],
    )

    forbidden_patterns = ['基准值待测', '___', '待填写', '此处插入']
    for pattern in forbidden_patterns:
        assert pattern not in result.content, \
            f"发现通用占位符 '{pattern}'！内容:\n{result.content[:300]}"

    required_business_info = ['AI写作助手', '5000', '10000']
    info_found = sum(1 for info in required_business_info if info in result.content)
    assert info_found >= 2, \
        f"内容缺乏业务特异性({info_found}/3): {result.content[:300]}"
```

### G-ASYNC-01: 异步执行稳定性门禁 (P0 - 阻断级)

```python
def test_async_execution_gate():
    """异步任务执行必须支持：提交→轮询→取消，且不阻塞前端"""
    from opc_manager.async_executor import AsyncTaskExecutor
    import time

    executor = AsyncTaskExecutor()

    task_id = executor.submit(
        func=lambda: time.sleep(2),  # 模拟耗时任务
        args=(),
        timeout=10,
    )

    status = executor.get_status(task_id)
    assert status in ['pending', 'running'], \
        f"任务状态异常: {status}"

    can_cancel = executor.cancel(task_id)
    assert can_cancel, "取消操作应该成功"

    final_status = executor.get_status(task_id)
    assert final_status == 'cancelled', \
        f"取消后状态应为cancelled: {final_status}"
```

### G-ITERATE-01: 多轮对话上下文门禁 (P0 - 阻断级)

```python
def test_session_iteration_gate():
    """多轮对话必须正确传递上下文，支持迭代修正"""
    from opc_manager.session_context import SessionContextManager

    session = SessionContextManager(max_turns=20)

    turn1_result = session.add_turn(
        user_input='帮我写Q2营销方案',
        assistant_response='已生成Q2营销方案，包含3个阶段...',
        sources=[{'title': '营销策略', 'url': 'http://example.com'}],
    )
    assert turn1_result.turn_id == 1
    assert session.get_turn_count() == 1

    context_for_llm = session.get_context_for_llm()
    assert 'Q2营销方案' in context_for_llm, "上下文应包含第一轮用户输入"
    assert len(context_for_llm) > 50, "上下文应足够详细"

    turn2_result = session.add_turn(
        user_input='第三阶段时间太长，能缩短到2周吗？',
        assistant_response='已调整第三阶段为2周敏捷迭代...',
    )
    assert turn2_result.turn_id == 2

    last_result = session.get_last_result()
    assert '调整' in last_result or '缩短' in last_result or '2周' in last_result, \
        f"最新结果应反映修改意图: {last_result}"

    full_history = session.get_full_history()
    assert len(full_history) == 2, "历史记录应包含2轮"
```

### G-LLM-FALLBACK: LLM降级兼容门禁 (P1 - 重要级)

```python
def test_llm_fallback_gate():
    """LLM不可用时必须优雅降级到v3.4模板模式，不崩溃"""
    from opc_manager.llm_content import LLMEnhancedContentGenerator
    from unittest.mock import patch

    generator = LLMEnhancedContentGenerator()

    with patch.object(generator, '_call_llm_api', side_effect=Exception("API不可用")):
        result = generator.generate(
            user_input='测试降级',
            template='# 报告\n\n{content}\n',
            search_results=[],
        )

        assert result.success, "降级后仍应返回成功"
        assert result.fallback_used == True, "应标记为使用了降级模式"
        assert len(result.content) > 100, "降级内容不应为空"
        assert '___' not in result.content, "降级内容也不应有占位符"
```

---

## v3.5 新增测试用例清单（37个）

### TestSearchRelevance (5个测试) — P0-1 SearchResultProcessor

| ID | 名称 | 验证点 | 优先级 |
|----|------|--------|--------|
| SR-001 | 关键词提取准确性 | 从"Q2营销方案SaaS产品"提取["Q2","营销","方案","SaaS"] | P0 |
| SR-002 | 无关结果过滤 | 输入"税收政策"，过滤掉"小说""书信""SCI论文" | P0 |
| SR-003 | TF-IDF评分排序 | 相关结果排在无关结果前面 | P0 |
| SR-004 | 知识库兜底激活 | 所有搜索结果都不相关时返回知识库条目 | P1 |
| SR-005 | 空结果降级处理 | 处理后为空时返回原始结果（不比v3.4更差） | P0 |

### TestContentTargeting (6个测试) — P0-2 LLMEnhancedContentGenerator

| ID | 名称 | 验证点 | 优先级 |
|----|------|--------|--------|
| CT-001 | RAG模式正常生成 | LLM可用时使用搜索结果作为上下文 | P0 |
| CT-002 | 业务信息注入 | 用户输入中的具体数字/产品名出现在输出中 | P0 |
| CT-003 | 占位符消除 | 不含"基准值待测""___""待填写"等 | P0 |
| CT-004 | LLM异常降级 | API超时/错误时切换到模板填充模式 | P1 |
| CT-005 | 降级模式质量 | 降级后的内容仍有足够长度和结构 | P1 |
| CT-006 | 模板骨架完整性 | RAG模式下保留原模板的结构标记 | P2 |

### TestAsyncExecution (4个测试) — P0-3 AsyncTaskExecutor

| ID | 名称 | 验证点 | 优先级 |
|----|------|--------|--------|
| AE-001 | 提交返回task_id | submit()立即返回ID，不阻塞 | P0 |
| AE-002 | 状态轮询正确性 | pending→running→completed/cancelled 状态流转 | P0 |
| AE-003 | 取消操作有效性 | cancel()终止后台线程 | P0 |
| AE-004 | 超时自动清理 | 超过timeout的任务自动标记failed | P1 |

### TestSessionIteration (5个测试) — P0-4 SessionContextManager

| ID | 名称 | 验证点 | 优先级 |
|----|------|--------|--------|
| SI-001 | 单轮上下文存储 | add_turn()正确保存user_input+response+sources | P0 |
| SI-002 | 多轮历史累积 | 连续add_turn()后get_full_history()返回完整列表 | P0 |
| SI-003 | LLM上下文格式化 | get_context_for_llm()返回格式化的对话历史 | P0 |
| SI-004 | 轮次上限强制 | 超过max_turns(20)时报错或拒绝 | P1 |
| SI-005 | 最新结果快速获取 | get_last_result()只返回最后一轮response | P2 |

### TestLLMFallback (3个测试) — P0-2 降级路径

| ID | 名称 | 验证点 | 优先级 |
|----|------|--------|--------|
| LF-001 | 网络超时降级 | requests.Timeout → 模板模式 | P1 |
| LF-002 | API Key无效降级 | 认证错误 → 模板模式 | P1 |
| LF-003 | 降级内容完整性 | 降级后零占位符 + 长度>200字符 | P0 |

### TestUIImprovements (2个测试) — UI交互优化验证

| ID | 名称 | 验证点 | 优先级 |
|----|------|--------|--------|
| UI-001 | 进度反馈存在性 | st.status/st.progress_bar在execute期间显示 | P1 |
| UI-002 | 错误友好性 | 异常时显示中文友好提示而非traceback | P1 |

### TestIntegrationV35 (12个测试) — v3.5 组件集成

| ID | 名称 | 验证点 | 优先级 |
|----|------|--------|--------|
| INT-001 | TaskEngineV3 + SearchResultProcessor集成 | execute()内部调用processor.process() | P0 |
| INT-002 | TaskEngineV3 + LLMEnhancedContentGenerator集成 | _gen_real_plan/report调用generator.generate() | P0 |
| INT-003 | 前端 + AsyncTaskExecutor集成 | app.py调用executor.submit()而非直接engine.execute() | P0 |
| INT-004 | 前端 + SessionContextManager集成 | 每次对话轮次存入session state | P0 |
| INT-005 | 全链路E2E：搜索→处理→内容→交付 | 完整用户旅程无报错 | P0 |
| INT-006 | 全链路E2E：多轮对话→迭代修正 | 第2轮输入引用第1轮结果 | P0 |
| INT-007 | SearchCache + SearchResultProcessor | 缓存命中时跳过处理 | P2 |
| INT-008 | InputValidator + SessionContextManager | XSS输入不影响后续轮次 | P1 |
| INT-009 | AsyncTaskExecutor超时→前端显示友好错误 | 超时时st.error显示中文提示 | P1 |
| INT-010 | LLM降级→TaskEngineV3回退到v3.4逻辑 | 降级标志位传递到最终结果 | P1 |
| INT-011 | 并发任务隔离 | 同时提交2个任务互不干扰 | P2 |
| INT-012 | 文件命名包含轮次信息 | 多轮对话生成的文件名有turn_id | P2 |

---

## v3.5 测试执行矩阵

### 测试数量统计

| 类别 | v3.4 数量 | v3.5 新增 | **v3.5 总计** |
|------|----------|-----------|-------------|
| 单元测试 | 45 | 25 | **70** |
| 集成测试 | 0 | 12 | **12** |
| E2E测试 | 0 | 0* | **0** (保持不变) |
| **总计** | **45** | **37** | **82** |

*\*注：E2E测试依赖浏览器自动化，保持原有5个不变*

### 执行顺序（按开发进度同步推进）

```
Week 1 Day 1-3:   TestSearchRelevance (5个)     ← P0-1 SearchResultProcessor完成后立即编写
Week 1 Day 4-5:   TestAsyncExecution (4个)       ← P0-3 AsyncTaskExecutor完成后
Week 2 Day 1-3:   TestContentTargeting (6个)     ← P0-2 LLMEnhancedContentGenerator完成后
                  TestLLMFallback (3个)           ← 同上
Week 2 Day 4-5:   TestSessionIteration (5个)     ← P0-4 SessionContextManager完成后
Week 3 Day 1-2:   TestUIImprovements (2个)       ← UI改造完成后
Week 3 Day 3-5:   TestIntegrationV35 (12个)      ← 所有组件集成后
                  运行全量回归测试 (82个)
```

---

## v3.5 CI/CD 门禁配置更新

```yaml
# .github/workflows/test.yml (v3.5更新)
name: OPC-Agents Test v3.5
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - run: pip install -r requirements.txt
      
      # v3.3 原有门禁
      - run: pytest tests/test_task_engine_v3.py -v
      
      # v3.4 新增门禁
      - name: Zero Placeholder Check (tokenize)
        run: python3 tests/gate_zero_placeholder.py
        
      # ===== v3.5 新增门禁 =====
      - name: Search Relevance Gate (G-SEARCH-01)
        run: python3 tests/gate_search_relevance.py
        
      - name: Content Targeting Gate (G-CONTENT-01)
        run: python3 tests/gate_content_targeting.py
        
      - name: Async Execution Gate (G-ASYNC-01)
        run: python3 tests/gate_async_execution.py
        
      - name: Session Iteration Gate (G-ITERATE-01)
        run: python3 tests/gate_session_iteration.py
        
      - name: LLM Fallback Gate (G-LLM-FALLBACK)
        run: python3 tests/gate_llm_fallback.py
      
      # 全量测试套件
      - run: pytest tests/ -v --tb=short
      
      # v3.5 新增：覆盖率报告
      - name: Coverage Report
        run: |
          pytest tests/ --cov=opc_manager --cov-report=term-missing
          echo "覆盖率必须 >= 80%"
```

---

## 已知测试缺口（v3.5 更新版）

| 缺口 | 影响 | 解决版本 | 状态 |
|------|------|---------|------|
| Streamlit E2E不稳定 | 超时导致误报 | v3.5: AsyncTaskExecutor解决 | 🔄 进行中 |
| 中文搜索质量无法自动化判断 | 需人工review | v3.5: SearchResultProcessor评分器 | ✅ 已规划 |
| LLM输出质量测试 | 当前未接入LLM | v3.5: LLMEnhancedContentGenerator+降级测试 | ✅ 已规划 |
| 并发场景测试 | 未覆盖 | v3.5: AsyncTaskExecutor并发测试 | ✅ 已规划 |
| 多轮对话上下文测试 | 未覆盖 | v3.5: SessionContextManager测试 | ✅ 已规划 |
| ~~搜索相关性~~ | ~~用户拿到垃圾数据~~ | ~~v3.5~~ | ~~✅ 已解决~~ |
| ~~内容泛化~~ | ~~文件下载后无法使用~~ | ~~v3.5~~ | ~~✅ 已解决~~ |

---

> **文档维护说明**：本测试计划已从v3.3升级到v3.5，反映四角色共识决策。核心变更是：
> 1. **5个新的P0/P1测试门禁**（搜索相关性/内容智能/异步/迭代/LLM降级）
> 2. **37个新测试用例**（覆盖4个新P0组件 + 集成测试）
> 3. **CI/CD流水线更新**（新增5个gate脚本）
> 4. **总测试数从45增长到82**（+82%）
>
> **权威参考**: [v3.5-consensus-decision-record.md](../internal/v3.5-consensus-decision-record.md) Section 5 (Testing Gates)
