# Mock 分类判定标准与监控指南

> **版本**: v1.0 | **创建日期**: 2026-07-18 | **状态**: active
>
> **背景**: T7 Mock 反模式系列已于 v0.3.36 正式关闭（5 文件 42 处替换，剩余 56 文件 532 处经评估为"必要 Mock"）。本文档建立 Mock 分类判定标准，监控新增测试遵循"必要 Mock"原则，避免 Mock 反模式回潮。

---

## 1. Mock 分类总览

| 类别 | 是否反模式 | 处理方式 | T7 处理情况 |
|------|-----------|----------|-------------|
| streamlit MagicMock | ❌ 否 | 保留（ScriptRunContext 运行时上下文所必需） | 不处理 |
| @patch.object 测试隔离 | ❌ 否 | 保留（避免真实 SQLite DB 副作用） | 不处理 |
| @patch.dict(os.environ) | ❌ 否 | 保留（环境变量测试标准做法） | 不处理 |
| @patch 外部服务 | ❌ 否 | 保留（CarryMem/LLM 不可在 CI 调用） | 不处理 |
| MagicMock + assert_called | ❌ 否 | 保留（断言依赖 mock 调用记录） | 不处理 |
| 局部 MagicMock 替代数据对象 | ✅ **是** | **替换为 Fake 类** | T7.7 已处理 6 处 |
| PropertyMock 异常测试 | ❌ 否 | 保留（异常注入标准做法） | 不处理 |

---

## 2. 判定标准详解

### 2.1 必要 Mock（保留）

#### 2.1.1 streamlit MagicMock

**理由**: Streamlit 的 ScriptRunContext 是运行时上下文，单元测试中无法真实运行前端框架。

**示例**:
```python
# ✅ 必要 Mock — 保留
mock_st = MagicMock()
mock_st.session_state = {"user_id": "test"}
```

**判定条件**:
- Mock 对象是 `streamlit` 模块或其子模块
- 测试目的是验证业务逻辑，而非 Streamlit UI 行为

#### 2.1.2 @patch.object 测试隔离

**理由**: 某些源码方法会调用 `data_manager.init_db()` + `execute_query()` / `execute_write()`，真实执行会创建 SQLite DB 文件并产生副作用。

**示例**:
```python
# ✅ 必要 Mock — 保留
@patch.object(ConsensusEngine, "_load_decision_log_from_db")
def test_consensus(self, mock_load):
    # 避免真实创建 SQLite DB 文件
    ...
```

**判定条件**:
- 被patch的方法会触发真实 DB 操作（init_db / execute_query / execute_write）
- 测试目的是验证被测方法的业务逻辑，而非 DB 层
- 无法用 tmp_path 替代（如 patch 的是实例方法）

#### 2.1.3 @patch.dict(os.environ)

**理由**: 环境变量测试是标准做法，测试需要控制环境变量值。

**示例**:
```python
# ✅ 必要 Mock — 保留
@patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
def test_llm_service(self):
    ...
```

#### 2.1.4 @patch 外部服务

**理由**: CarryMem、LLM、HTTP API 等外部服务不可在 CI 中调用（速度/成本/网络依赖）。

**示例**:
```python
# ✅ 必要 Mock — 保留
@patch("opc_manager.memory_bridge.is_memory_enabled", return_value=False)
def test_memory_disabled(self, mock_enabled):
    ...
```

#### 2.1.5 MagicMock + assert_called_once_with

**理由**: 测试需要验证某个对象的方法被调用（调用次数、参数），mock 对象的 `assert_called_once_with` 是标准断言手段。

**示例**:
```python
# ✅ 必要 Mock — 保留
mock_executor = MagicMock()
result = some_function(mock_executor)
mock_executor.run.assert_called_once_with(expected_arg)
```

#### 2.1.6 PropertyMock 异常测试

**理由**: 测试需要模拟属性抛出异常的场景，PropertyMock 是标准做法。

**示例**:
```python
# ✅ 必要 Mock — 保留
with patch.object(obj, "prop", new_callable=PropertyMock, side_effect=Exception):
    ...
```

### 2.2 Mock 反模式（必须替换为 Fake 类）

#### 2.2.1 局部 MagicMock 替代数据对象

**理由**: 当 MagicMock 仅用于模拟一个数据对象（具有几个固定属性），且不依赖 `assert_called` 断言时，应该用 Fake 类替代。Fake 类更真实、更可读、更易于维护。

**反模式示例**:
```python
# ❌ 反模式 — 不要这样写
def test_something():
    match = MagicMock()
    match.trigger = "营销"
    match.action = "营销推广"
    match.rule_type = "soft"
    # ... 使用 match 对象
```

**正确做法**:
```python
# ✅ 正确 — 用 Fake 类替代
class FakeRuleMatch:
    """Fake RuleMatch object for testing."""
    def __init__(self, trigger: str = "", action: str = "", rule_type: str = ""):
        self.trigger = trigger
        self.action = action
        self.rule_type = rule_type

def test_something():
    match = FakeRuleMatch(trigger="营销", action="营销推广", rule_type="soft")
    # ... 使用 match 对象
```

**判定条件**:
- MagicMock 仅作为数据容器（不验证方法调用）
- MagicMock 有多个固定属性被手动设置
- 测试逻辑不依赖 `assert_called` / `assert_called_with`

---

## 3. 新增测试 Mock 自检清单

新增测试时，请按以下清单自检 Mock 使用是否合理：

| # | 检查项 | 通过条件 |
|---|--------|----------|
| 1 | 是否使用 `MagicMock()` 替代数据对象？ | 如是，替换为 Fake 类（参照 2.2.1） |
| 2 | 是否 `@patch.object` 内部方法以避免 DB 副作用？ | 如是，保留（必要 Mock） |
| 3 | 是否 `@patch.dict(os.environ)` 控制环境变量？ | 如是，保留（必要 Mock） |
| 4 | 是否 `@patch` 外部服务（CarryMem/LLM/HTTP）？ | 如是，保留（必要 Mock） |
| 5 | 是否使用 `assert_called_once_with` 验证调用？ | 如是，保留（必要 Mock） |
| 6 | 是否 Mock streamlit 模块？ | 如是，保留（必要 Mock） |
| 7 | 是否用 `PropertyMock(side_effect=Exception)` 测试异常？ | 如是，保留（必要 Mock） |

**判定结果**:
- 全部为 2-7 项 → ✅ 必要 Mock，保留
- 包含第 1 项 → ❌ 反模式，必须替换为 Fake 类

---

## 4. T7 系列关闭总结

### 4.1 处理明细

| 版本 | 阶段 | 文件数 | 替换数 | 状态 |
|------|------|--------|--------|------|
| v0.3.33 | T7 计划制定 | 0 | 0 | ✅ 完成 |
| v0.3.34 | T7 第1批推迟 | 0 | 0 | ✅ 完成 |
| v0.3.35 | T7 第1批实施 | 4 | 36 | ✅ 完成 |
| v0.3.36 | T7 第2批实施 + 关闭 | 1 | 6 | ✅ 完成 |
| **合计** | — | **5** | **42** | — |

### 4.2 已处理的 5 个文件

1. **test_email_skill_coverage.py** (v0.3.18 第一批) — 已处理
2. **test_simple_llm_service.py** (v0.3.18 第一批) — 已处理
3. **test_executor_opinion.py** (v0.3.18 第一批) — 已处理
4. **test_delta_integration.py** (v0.3.18 第二批) — 已处理
5. **test_integration_modules.py** (v0.3.18 第二批) — 已处理
6. **test_undo_panel.py** (v0.3.18 第三批) — 已处理
7. **test_skill_executors.py** (v0.3.18 第三批) — 已处理
8. **test_timeline_view.py** (v0.3.18 第四批) — 已处理
9. **test_brain_modules.py** (v0.3.22 扩展) — 40 处 MagicMock → 6 个 Fake 类
10. **test_live_log_panel.py** (v0.3.22 扩展) — 4 处 MagicMock → 2 个 Fake 类
11. **test_consensus_engine.py** (v0.3.36 T7.6) — 0 处替换（77 处 @patch.object 全部必要）
12. **test_memory_bridge.py** (v0.3.36 T7.7) — 6 处局部 MagicMock → FakeRuleMatch/FakeSuggestion

### 4.3 校准记录

| 版本 | 原估计 | 实际替换 | 偏差 |
|------|--------|----------|------|
| v0.3.35 | 266 处 | 36 处 | -86% |
| v0.3.36 | ~45 处 | 6 处 | -87% |
| **合计** | ~311 处 | **42 处** | **-86%** |

**教训**: 基于过期 ROADMAP 描述的 Mock 替换数量严重高估，实际可替换 Mock 远少于描述。T7 系列总替换 42 处（非原估计 ~311 处）。

### 4.4 剩余 Mock 状态

- **剩余文件数**: 56 个
- **剩余 Mock 总数**: 532 处
- **状态**: 经评估全部为"必要 Mock"（测试隔离/分支控制/外部服务/assert_called 依赖）
- **处理方式**: 不再处理，遵循本文档判定标准

---

## 5. 监控机制

### 5.1 新增测试 Mock 审查

新增测试时，开发者应按以下流程审查 Mock 使用：

1. **自检**: 按"第 3 节 新增测试 Mock 自检清单"逐项检查
2. **Code Review**: PR 评审者检查 Mock 使用是否符合本文档标准
3. **CI 检查**: （未来可考虑）添加自动化检查脚本，扫描新增 MagicMock 使用

### 5.2 定期评估

- **频率**: 每个大版本（如 v0.5.0 / v0.6.0）评估一次
- **方法**: 重新扫描剩余 Mock，判断是否有新的反模式出现
- **记录**: 评估结果记入对应版本的评估报告

### 5.3 反模式回潮防护

如果新增测试中再次出现 Mock 反模式（局部 MagicMock 替代数据对象），应：

1. **立即修复**: 替换为 Fake 类
2. **根因分析**: 为何反模式回潮？（开发者不熟悉本文档？时间压力？）
3. **预防措施**: 补充培训 / 在 CI 中添加检查 / 在 PR 模板中提醒

---

## 6. 参考文档

- [D07 项目整理评估 v0.3.36](../assessments/ASSESSMENT_D07_TIDY_v0.3.36.md) — T7 系列关闭依据 + Mock 反模式判定标准
- [CHANGELOG v0.3.36](../../CHANGELOG.md) — T7.6/7.7/7.8 详细记录
- [用户测试哲学](../../README.md) — "Tests exist to find bugs and make the system better"

---

## 7. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-07-18 | 初始版本，基于 T7 系列关闭总结建立 Mock 分类判定标准 |
