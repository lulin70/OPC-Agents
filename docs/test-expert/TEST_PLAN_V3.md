# OPC-Agents 测试计划 v3.3 (实际交付版)

## 更新履历

| 版本 | 日期 | 更新人 | 更新内容 |
|------|------|--------|----------|
| **v3.3.0** | **2026-04-16** | **测试专家** | **TaskEngineV3核心测试、零占位符验收、文件交付验证、真实搜索验证** |
| v3.0.0 | 2026-04-15 | 测试专家 | Phase 3完整测试计划：Web/LLM/DB/Platform/E2E |

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
