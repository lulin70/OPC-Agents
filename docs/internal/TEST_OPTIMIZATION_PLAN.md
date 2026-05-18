# OPC-Agents v0.2.0 前端测试优化方案

> **文档版本**: v1.0
> **编制日期**: 2026-05-17
> **编制角色**: Senior QA / Test Engineer
> **适用范围**: `frontend/` 目录下全部 Streamlit 前端模块
> **数据基线**: 1841 个已收集测试用例 / 55 个测试文件 / 11 个核心前端测试模块

---

## 目录

- [1 当前测试覆盖现状](#1-当前测试覆盖现状)
- [2 测试盲区分析](#2-测试盲区分析)
- [3 防回归测试机制设计](#3-防回归测试机制设计)
- [4 测试方案优化建议](#4-测试方案优化建议)
- [5 测试质量门禁标准](#5-测试质量门禁标准)

---

## 1 当前测试覆盖现状

### 1.1 测试资产清单

| 维度 | 数据 |
|------|------|
| **测试文件总数** | 55 个 `.py` 文件（含 `__init__.py` / `conftest.py` / benchmark） |
| **可执行测试用例总数** | **1841 个**（`pytest --collect-only` 统计） |
| **前端专用测试文件** | 11 个核心文件（见下表） |
| **前端组件源码文件** | `components/` 下 ~12 个模块 + `page_modules/` 下 3 个页面 + `app.py` 主文件 |
| **测试框架** | pytest + unittest.TestCase 混合模式 |
| **Mock 策略** | `unittest.mock.patch("module.streamlit as st")` 统一 mock Streamlit |

#### 前端核心测试文件明细

| # | 测试文件 | 行数 | 估算用例数 | 被测源码模块 | 覆盖质量评级 |
|---|---------|------|-----------|-------------|------------|
| 1 | `test_i18n.py` | 248 | ~30 | `opc_manager/i18n.py` | ⭐⭐⭐⭐ 良好 |
| 2 | `test_result_cards.py` | 432 | 39 (TC-001~039) | `components/result_cards.py` | ⭐⭐⭐⭐⭐ 非常充分 |
| 3 | `test_smart_suggestions.py` | 502 | ~35 | `components/smart_suggestions.py` | ⭐⭐⭐⭐⭐ 优秀 |
| 4 | `test_confirmation_dialog.py` | 717 | ~40+ | `components/confirmation_dialog.py` | ⭐⭐⭐⭐⭐ 全面深入 |
| 5 | `test_undo_panel.py` | 721 | 40+ | `components/undo_panel.py` | ⭐⭐⭐⭐ 充分 |
| 6 | `test_unified_types.py` | 832 | 60+ | `components/unified_types.py` | ⭐⭐⭐⭐⭐ 极其完整 |
| 7 | `test_input_autocomplete.py` | 722 | 55+ | `components/input_autocomplete.py` | ⭐⭐⭐⭐⭐ 非常全面 |
| 8 | `test_live_log_panel.py` | 840 | 60+ | `components/live_log_panel.py` | ⭐⭐⭐⭐⭐ 优秀 |
| 9 | `test_timeline_view.py` | 808 | 58 (TC-TL-001~058) | `components/timeline_view.py` | ⭐⭐⭐⭐ 良好（部分集成跳过） |
| 10 | `test_parallel_executor.py` | 805 | 45+ | `opc_manager/parallel_executor.py` | ⭐⭐⭐⭐⭐ 非常彻底 |
| 11 | `test_real_progress.py` | 629 | 35+ | 进度事件链路 | ⭐⭐⭐⭐ 良好 |

**前端子领域测试合计**: 约 **497+** 个用例，占总量 **27%**

### 1.2 模块级覆盖热力图

```
模块                          │ 已测 │ 未测 │ 覆盖率 │ 备注
─────────────────────────────┼──────┼──────┼────────┼───────────────────
components/result_cards      │  ✅  │      │  ~95%  │ 39个TC全覆盖渲染路径
components/smart_suggestions │  ✅  │      │  ~90%  │ 7类建议+去重+排序
components/confirmation_diag │  ✅  │      │  ~95%  │ 风险等级+异步回调
components/undo_panel        │  ✅  │      │  ~90%  │ 11种操作类型全覆盖
components/unified_types     │  ✅  │      │  ~98%  │ 13类枚举+i18n+风险
components/input_autocomplete│  ✅  │      │  ~95%  │ 算法+缓存+安全
components/live_log_panel    │  ✅  │      │  ~92%  │ 5数据源+导出+脱敏
components/timeline_view     │  ✅  │      │  ~80%  │ 部分集成测试skipped
components/shared            │  🔶  │  🔴  │  ~30%  │ 间接测试为主,无独立文件
page_modules/_dashboard_page │      │  🔴  │   0%   │ ❌ 完全无测试
page_modules/_marketplace_pg │  🔶  │  🔴  │  ~20%  │ 仅marketplace_v2部分
page_modules/_settings_page  │  🔶  │  🔴  │  ~25%  │ test_settings存在但浅层
app.py (主应用)              │      │  🔴  │   0%   │ ❌ 1913行完全无测试
i18n 国际化系统              │  ✅  │      │  ~85%  │ 3语种+fallback+格式化
```

图例: ✅ 已覆盖 | 🔶 部分覆盖 | 🔴 未覆盖/盲区

### 1.3 现有测试质量评估

#### 优势（做得好的地方）

1. **组件级单元测试成熟度高**: `result_cards`、`confirmation_dialog`、`input_autocomplete` 等核心交互组件均有 TC 编号体系（TC-001~TC-039），断言粒度细到 DOM 属性级别。

2. **Mock 策略统一规范**: 全部采用 `@patch("frontend.components.xxx.st")` 模式注入 mock 对象，通过 `st.xxx.return_value` / `st.xxx.side_effect` 控制 UI 行为，避免了对真实 Streamlit 运行时的依赖。

3. **边界条件意识强**:
   - `test_input_autocomplete`: 覆盖 SQL 注入安全、超长查询、Unicode、时间戳边界
   - `test_live_log_panel`: 包含性能基准（1000 条目 <100ms）
   - `test_confirmation_dialog`: 覆盖敏感 key 脱敏（10 种 case）

4. **事件驱动架构验证到位**: `test_confirmation_dialog` 中验证了 ProgressEmitter 事件发射（confirm_requested → confirmed → rejected），`test_real_progress` 验证了 TaskEngineV3 事件序列顺序。

5. **国际化测试覆盖 3 语种**: `test_i18n.py` 和 `test_unified_types.py` 均验证了 zh_CN / en_US / ja_JP 三套翻译的键值完整性。

#### 劣势与风险点

1. **app.py 主文件零测试 — 最大盲区**: 1913 行代码包含：
   - 会话初始化逻辑（692~767 行）
   - Onboarding 引导流程（771~862 行）
   - 侧边栏导航与全局搜索（879~1046 行）
   - 成果物列表渲染 `_render_deliverables_list()`（1049~1098 行）
   - 审计日志页面 `_render_audit_log_page()`（1101~1257 行）
   - 主聊天页面完整交互流（1262~1820 行）
   - 异步任务执行管道 `_async_execute_task()`（560~663 行）
   - 成长飞轮页面（1840~1887 行）

   以上 **零个测试用例**覆盖。

2. **Page Module 层几乎空白**: `_dashboard_page.py`（862 行）、`_marketplace_page.py`（543 行）、`_settings_page.py`（675 行）三个页面模块合计 **2080 行**，无 dedicated 测试文件或仅有极浅层覆盖。

3. **集成/路由层面缺失**: 页面切换（chat ↔ deliverables ↔ dashboard ↔ settings）、session_state 生命周期、Streamlit rerun 行为均未测试。

4. **硬编码 CJK 字符串未被发现**: 多处源码中直接写死中文而绕过 i18n `t()` 函数（详见第 2 节 GAP 分析）。

5. **函数定义顺序依赖无防护**: app.py 中函数调用顺序依赖定义先后，但无 AST 级静态检查确保前向引用安全。

---

## 2 测试盲区分析

### 2.1 盲区清单（Gap Registry）

本节逐一列出 **7 个已知生产缺陷**对应的测试盲区，每个盲区赋予唯一 ID、严重程度和根因定位。

---

#### GAP-001: 函数前向引用 NameError — 致命级

| 属性 | 值 |
|------|-----|
| **盲区 ID** | GAP-001 |
| **缺陷描述** | `app.py` 中调用 `_render_deliverables_list()` / `_render_audit_log_page()` / `_show_onboarding_overlay()` 时，若函数定义位于调用点之后，Python 执行到调用语句时抛出 `NameError: name '_render_xxx' is not defined` |
| **严重程度** | 🔴 **P0 — 致命**（整页白屏） |
| **影响范围** | 成果物页、审计日志页、首次访问引导 |
| **对应 Bug** | Bug #1/#2/#3: NameError for undefined functions |
| **根因分析** | Python 是解释型语言，`def` 语句在运行时才绑定名称。app.py 采用脚本式自顶向下执行模式（非函数入口包装），若重构时将函数定义移到调用点之下即触发此 bug。当前版本中三个函数的定义位置：`_show_onboarding_overlay` @ L771（调用 @ L870 ✓）、`_render_deliverables_list` @ L1049（调用 @ L1832 ✓）、`_render_audit_log_page` @ L1101（调用 @ L1835 ✓）。**当前虽已修正，但无测试防止回归。** |
| **现有测试覆盖** | ❌ 无任何测试验证函数定义-调用顺序 |
| **所需测试类型** | AST 静态分析 + import 可达性检查 |

---

#### GAP-002: i18n 键缺失导致的运行时 KeyError — 高危级

| 属性 | 值 |
|------|-----|
| **盲区 ID** | GAP-002 |
| **缺陷描述** | 前端代码中调用 `_t("missing_key")` 时，若该 key 未在任何 locale JSON 中注册，`I18nManager.t()` 抛出 `KeyError` 或返回丑陋的原始 key 字符串暴露给用户 |
| **严重程度** | 🟠 **P1 — 高**（用户可见异常文本） |
| **影响范围** | 所有使用 `_t()` 的页面（chat/deliverables/dashboard/settings/marketplace/growth + sidebar） |
| **对应 Bug** | Bug #4: i18n routing issues |
| **根因分析** | app.py 中有 **50+ 处** `_t()` 调用，分散在 6 个页面区域和 sidebar 中。新增页面或重构时极易遗漏注册新 key。现有 `test_i18n.py` 仅验证 I18nManager 自身行为，**不扫描源码中的 `_t()` 调用并与 locale JSON 做交叉校验**。 |
| **现有测试覆盖** | ⚠️ 仅测试 I18nManager 内部逻辑，无"源码调用 vs 注册表"交叉验证 |
| **硬编码 CJK 证据** | app.py L956: `"技能名称只能包含字母..."`; L957: `"描述不能超过500字符"`; L1191: `"[frontend] 审计日志查询失败"`; shared.py 多处 `_render_batch_export_section` 等 |

---

#### GAP-003: 硬编码 CJK 字符串绕过 i18n — 中高危级

| 属性 | 值 |
|------|-----|
| **盲区 ID** | GAP-003 |
| **缺陷描述** | 源码中混用 `_t("key")"` 和硬编码中文/日文字符串，导致切换语言后部分 UI 仍显示中文，用户体验不一致 |
| **严重程度** | 🟠 **P1 — 高**（国际化质量缺陷） |
| **影响范围** | `shared.py`、`app.py`、`_marketplace_page.py`、`_dashboard_page.py`、`_settings_page.py` |
| **对应 Bug** | Bug #5: Mixed CJK text |
| **根因分析** | 开发过程中快速迭代时直接写入 CJK 字符串，事后未做 i18n 审计。典型违规位置：|
| | • `app.py:L956` — `"技能名称只能包含字母、数字、中文、下划线、连字符，且不超过50字符"` |
| | • `app.py:L957` — `"描述不能超过500字符"` |
| | • `app.py:L1191` — `logger.warning("[frontend] 审计日志查询失败: %s", e)` |
| | • `app.py:L1784` — `show_error(f"{_t('chat_op_failed')}: {friendly_title}")` 中间拼接 |
| | • `shared.py:_render_batch_export_section` — 多处批量导出相关 CJK |
| | • `shared.py:_execute_batch_export` — 导出执行反馈 CJK |
| | • `_marketplace_page.py:L~搜索结果` — `"未找到与「{search_query}」相关的内容"` |
| **现有测试覆盖** | ❌ 完全没有"硬编码字符串检测"测试 |
| **所需测试类型** | AST 扫描 + 正则匹配 + 白名单机制 |

---

#### GAP-004: Streamlit pages/ 目录自动检测冲突 — 中级

| 属性 | 值 |
|------|-----|
| **盲区 ID** | GAP-004 |
| **缺陷描述** | 若项目 `pages/` 目录下残留旧版 Streamlit multi-page 文件，Streamlit 会自动检测并生成额外菜单项，与 app.py 内置的 `st.radio` 导航冲突，导致重复菜单、路由混乱 |
| **严重程度** | 🟡 **P2 — 中**（功能异常但可 workaround） |
| **影响范围** | 侧边栏导航、页面路由 |
| **对应 Bug** | Bug #6: Streamlit pages auto-detection issues |
| **根因分析** | Streamlit framework 的自动 page discovery 机制：任何 `pages/*.py` 文件都会被自动注册为多页面应用的一页。v0.2.0 重构后采用单文件 `app.py` + 内置 tab/radio 导航，但如果 `pages/` 目录未清理干净则产生冲突。**无测试验证 pages/ 目录清洁性。** |
| **现有测试覆盖** | ❌ 无 |
| **所需测试类型** | 文件系统断言 + 启动时健康检查 |

---

#### GAP-005: session_state 初始化竞态与默认值缺失 — 高危级

| 属性 | 值 |
|------|-----|
| **盲区 ID** | GAP-005 |
| **缺陷描述** | app.py 大量代码直接访问 `st.session_state.xxx` 而未做 `.get("xxx", default)` 保护。若 session_state 初始化块（L692~767）因异常中断，后续所有页面渲染均抛出 `KeyError` |
| **严重程度** | 🟠 **P1 — 高**（潜在全面崩溃） |
| **影响范围** | 全部 6 个页面 + sidebar |
| **典型危险代码** | |
| | • `app.py:L897` — `if st.session_state.get("sidebar_global_search", "").strip():` ✅ 安全 |
| | • `app.py:L916` — `if st.session_state.detected_type:` ⚠️ 若初始化跳过则 KeyError |
| | • `app.py:L922` — `if st.session_state.deliverables:` ⚠️ 同上 |
| | • `app.py:L928` — `if "exec_mode" not in st.session_state:` ✅ 有保护 |
| | • `app.py:L1291` — `len(st.session_state.messages) > 0` ⚠️ 无 .get() |
| | • `app.py:L1348` — `has_api_key = _has_api_key()` 后续大量直接引用 |
| **根因分析** | 初始化块使用 `if "initialized" not in st.session_state:` 作为守卫，但该守卫本身如果因为 import 失败等原因被跳过，后续代码全部裸访 session_state。**无测试模拟初始化失败场景。** |
| **现有测试覆盖** | ❌ 无 session_state 安全性测试 |

---

#### GAP-006: 异步任务执行管道错误传播断裂 — 中高危级

| 属性 | 值 |
|------|-----|
| **盲区 ID** | GAP-006 |
| **缺陷描述** | `_async_execute_task()` → `execute_with_agent_loop()` → `execute_task_and_deliver()` 三层调用链中，某层吞掉异常并返回 `(None, False, None, None, None)` 元组，上层误判为"正常完成但无内容"，导致用户看到空结果而非错误提示 |
| **严重程度** | 🟠 **P1 — 高**（静默失败） |
| **影响范围** | 聊天页面任务提交→结果展示完整链路 |
| **根因分析** | `execute_task_and_deliver()` (L475~557) 的 except 块返回五元组 `None, False, None, None, None`，调用方 `execute_with_agent_loop()` (L373~472) 在降级路径也返回同样结构，最终 `_async_execute_task()` (L560~663) 判断 `if content and success` 为 False 后进入 error 分支——**当前逻辑看似正确，但每一层的异常分支未被单独测试验证**，一旦有人修改返回元组的结构或判断条件，就会引入静默失败。 |
| **现有测试覆盖** | ❌ 无端到端的 async pipeline 测试 |
| **所需测试类型** | Mock 后端 + 异步执行 + 结果校验 |

---

#### GAP-007: Dashboard / Marketplace / Settings 页面模块零覆盖 — 高危级

| 属性 | 值 |
|------|-----|
| **盲区 ID** | GAP-007 |
| **缺陷描述** | 三个页面模块合计 2080 行代码，包含复杂的布局渲染、表单处理、数据聚合逻辑，但没有任何 dedicated 测试文件覆盖其核心功能 |
| **严重程度** | 🟠 **P1 — 高**（大面积功能无防护） |
| **影响范围** | |
| | • **Dashboard** (`_dashboard_page.py`, 862 行): 3 种布局模板 × 3 种密度 = 9 种组合、6 个面板渲染器、demo mode fallback、DashboardConfig 集成 |
| | • **Marketplace** (`_marketplace_page.py`, 543 行): 技能卡片 V2 渲染、版本 pinning、分类过滤、全局搜索、安装/卸载状态管理 |
| | • **Settings** (`_settings_page.py`, 675 行): 6 个设置 Tab（LLM/SMTP/API Keys/Security/Profile/Backup）、备份创建/列表/导出/恢复、ZIP 解压确认 |
| **根因分析** | 这些模块重度依赖 Streamlit widget 状态（`st.text_input`、`st.selectbox`、`st.form_submit_button`），编写测试需要精细控制 `st.session_state` 和 widget 回调，开发成本较高因而被搁置。现有 `test_settings.py` / `test_marketplace_v2.py` 存在但仅覆盖模型层数据操作，**不涉及 UI 渲染路径**。 |
| **现有测试覆盖** | < 10%（仅数据层） |
| **所需测试类型** | 组件级渲染测试（mock st）+ 表单提交流程测试 |

---

### 2.2 盘点汇总

| 盲区 ID | 严重度 | 类别 | 影响行数(估) | 可自动化预防? |
|---------|--------|------|-------------|-------------|
| GAP-001 | P0 致命 | 函数定义顺序 | ~150 | ✅ AST 静态分析 |
| GAP-002 | P1 高 | i18n 键完整性 | ~2000 (分布) | ✅ 源码扫描交叉验证 |
| GAP-003 | P1 高 | 硬编码 CJK | ~300 | ✅ AST + 正则 |
| GAP-004 | P2 中 | pages/ 冲突 | N/A | ✅ 文件系统检查 |
| GAP-005 | P1 高 | session_state 安全 | ~400 | ✅ 模式匹配 |
| GAP-006 | P1 高 | 异步管道错误传播 | ~250 | ✅ 链路测试 |
| GAP-007 | P1 高 | Page Module 零覆盖 | 2080 | ⚠️ 需手工编写 |

**核心结论**: 7 个盲区中 **6 个可通过自动化测试/静态分析手段预防**，仅 GAP-007 需要较大规模的手工测试编写投入。

---

## 3 防回归测试机制设计

针对上述 7 个盲区，设计以下 **5 套防回归测试**（编号 A~E），每套包含伪代码实现。

---

### 3.1 测试 A: AST 函数定义顺序守护者（防 GAP-001）

**目标**: 确保 `app.py` 中所有被调用的顶层函数在调用点之前已完成 `def` 绑定。

**策略**: 用 Python `ast` 模块解析 `app.py`，提取所有 `FunctionDef` 节点的名称和行号，再提取所有 `Name` 节点（作为调用表达式），构建"定义位置 → 引用位置"映射，报告所有前向引用。

```python
# tests/test_frontend_regression.py

import ast
import os
import pytest

APP_PY_PATH = os.path.join(os.path.dirname(__file__), "..", "frontend", "app.py")


def _extract_function_defs(source: str) -> dict[str, int]:
    """提取所有顶层函数定义及其行号"""
    tree = ast.parse(source)
    defs = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            defs[node.name] = node.lineno
    return defs


def _extract_call_names_after_line(source: str, after_line: int) -> list[tuple[str, int]]:
    """提取指定行之后的所有函数调用名称和位置"""
    tree = ast.parse(source)
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.lineno > after_line:
                calls.append((node.func.id, node.lineno))
    return calls


class TestFunctionDefinitionOrder:
    """GAP-001 防回归: 验证 app.py 中无前向函数引用"""

    @pytest.fixture(scope="class")
    def app_source(self):
        with open(APP_PY_PATH, "r", encoding="utf-8") as f:
            return f.read()

    def test_no_forward_reference_for_render_deliverables(self, app_source):
        """_render_deliverables_list 必须在调用前定义"""
        defs = _extract_function_defs(app_source)
        assert "_render_deliverables_list" in defs, \
            "_render_deliverables_list 未在 app.py 中定义"
        def_line = defs["_render_deliverables_list"]
        for call_name, call_line in _extract_call_names_after_line(app_source, 0):
            if call_name == "_render_deliverables_list":
                assert call_line > def_line, \
                    f"前向引用: {call_name} 在第 {call_line} 行调用，但在第 {def_line} 行才定义"

    def test_no_forward_reference_for_render_audit_log(self, app_source):
        """_render_audit_log_page 必须在调用前定义"""
        defs = _extract_function_defs(app_source)
        assert "_render_audit_log_page" in defs
        def_line = defs["_render_audit_log_page"]
        for call_name, call_line in _extract_call_names_after_line(app_source, 0):
            if call_name == "_render_audit_log_page":
                assert call_line > def_line

    def test_no_forward_reference_for_onboarding_overlay(self, app_source):
        """_show_onboarding_overlay 必须在调用前定义"""
        defs = _extract_function_defs(app_source)
        assert "_show_onboarding_overlay" in defs
        def_line = defs["_show_onboarding_overlay"]
        for call_name, call_line in _extract_call_names_after_line(app_source, 0):
            if call_name == "_show_onboarding_overlay":
                assert call_line > def_line

    def test_all_called_functions_defined_before_module_level_calls(self, app_source):
        """广义检查: 模块级作用域（非函数内部）的所有函数调用，
        其目标函数必须在此调用之前已有定义"""
        defs = _extract_function_defs(app_source)
        tree = ast.parse(source=app_source)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                func_name = node.value.func.id if isinstance(node.value.func, ast.Name) else None
                if func_name and func_name in defs:
                    assert node.value.lineno > defs[func_name], \
                        f"模块级前向引用: {func_name} 于第 {node.value.lineno} 行 " \
                        f"调用，定义于第 {defs[func_name]} 行"
```

**预期效果**: 任何人将函数定义移到调用点之下时，CI 立即报错，阻断合并。

---

### 3.2 测试 B: i18n 键完整性交叉验证（防 GAP-002 + GAP-003）

**目标**: 双重保证 —— (1) 源码中每个 `_t("key")` 的 key 都在 3 套 locale JSON 中注册；(2) 源码中不含绕过 i18n 的硬编码 CJK 用户可见字符串。

```python
# tests/test_i18n_completeness.py

import ast
import os
import re
import json
import pytest
from pathlib import Path

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
LOCALE_DIR = Path(__file__).parent.parent / "opc_manager" / "locales"


def _get_all_registered_keys() -> dict[str, set[str]]:
    """加载 3 套 locale JSON，返回 {locale: set of keys}"""
    result = {}
    for locale_name in ["zh_CN", "en_US", "ja_JP"]:
        locale_file = LOCALE_DIR / f"{locale_name}.json"
        if locale_file.exists():
            with open(locale_file, "r", encoding="utf-8") as f:
                result[locale_name] = set(json.load(f).keys())
        else:
            result[locale_name] = set()
    return result


def _extract_t_call_keys(source: str) -> list[tuple[str, int]]:
    """从源码 AST 提取所有 _t("key") 和 t("key") 调用的 key"""
    tree = ast.parse(source)
    keys = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            func_name = ""
            if isinstance(func, ast.Name):
                func_name = func.id
            elif isinstance(func, ast.Attribute):
                func_name = func.attr
            if func_name in ("t", "_t") and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    keys.append((arg.value, arg.lineno))
    return keys


def _find_hardcoded_cjk_strings(source: str, filename: str) -> list[tuple[str, int, str]]:
    """查找硬编码的中日韩用户可见字符串（排除注释和 logging）"""
    results = []
    lines = source.split("\n")
    cjk_pattern = re.compile(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]')
    skip_contexts = ["logger.", "logging.", "# ", "    # ", '"""', "'''"]
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if any(skip in line for skip in skip_contexts):
            continue
        if cjk_pattern.search(stripped) and (
            '"' in stripped or "'" in stripped
        ):
            results.append((stripped.strip(), lineno, filename))
    return results


class TestI18nCompleteness:
    """GAP-002 防回归: i18n 键完整性"""

    @pytest.fixture(scope="class")
    def registered_keys(self):
        return _get_all_registered_keys()

    def test_all_t_calls_have_registered_key_in_zh_cn(self, registered_keys):
        """所有 _t() 调用的 key 必须在 zh_CN.json 中注册"""
        zh_keys = registered_keys.get("zh_CN", set())
        missing = []
        for py_file in FRONTEND_DIR.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            for key, line in _extract_t_call_keys(source):
                if key not in zh_keys:
                    missing.append(f"  {py_file.name}:{line} — _t('{key}')")
        assert not missing, f"缺少 zh_CN 注册的 i18n key:\n" + "\n".join(missing[:20])

    def test_three_locales_have_same_keys(self, registered_keys):
        """三套 locale 的 key 集合必须一致"""
        zh = registered_keys.get("zh_CN", set())
        en = registered_keys.get("en_US", set())
        ja = registered_keys.get("ja_JP", set())
        assert zh == en, f"zh_CN({len(zh)} keys) != en_US({len(en)} keys), 差集: {zh ^ en}"
        assert zh == ja, f"zh_CN({len(zh)} keys) != ja_JP({len(ja)} keys), 差集: {zh ^ ja}"


class TestNoHardcodedCJK:
    """GAP-003 防回归: 禁止硬编码 CJK 用户可见字符串"""

    def test_app_py_no_hardcoded_cjk_user_strings(self):
        """app.py 中不应有硬编码 CJK 用户可见字符串"""
        app_py = FRONTEND_DIR / "app.py"
        source = app_py.read_text(encoding="utf-8")
        violations = _find_hardcoded_cjk_strings(source, "app.py")
        allowed_whitelist = {
            "文档字符串中的 CJK",
            "PERSONA_MAP / TYPE_DISPLAY / SCENARIOS 配置字典",
        }
        assert len(violations) == 0, \
            f"发现 {len(violations)} 处硬编码 CJK 字符串:\n" + \
            "\n".join(f"  L{line}: {code[:80]}" for code, line, _ in violations[:15])

    def test_shared_py_no_hardcoded_cjk_user_strings(self):
        """shared.py 中不应有硬编码 CJK 用户可见字符串（UI 渲染路径）"""
        shared_py = FRONTEND_DIR / "components" / "shared.py"
        source = shared_py.read_text(encoding="utf-8")
        violations = _find_hardcoded_cjk_strings(source, "shared.py")
        assert len(violations) == 0, \
            f"shared.py 发现 {len(violations)} 处硬编码 CJK:\n" + \
            "\n".join(f"  L{line}: {code[:80]}" for code, line, _ in violations[:15])

    def test_page_modules_no_hardcoded_cjk(self):
        """所有 page_module 不应有硬编码 CJK"""
        pm_dir = FRONTEND_DIR / "page_modules"
        all_violations = []
        for py_file in pm_dir.glob("_*.py"):
            source = py_file.read_text(encoding="utf-8")
            v = _find_hardcoded_cjk_strings(source, py_file.name)
            all_violations.extend(v)
        assert len(all_violations) == 0, \
            f"page_modules 发现 {len(all_violations)} 处硬编码 CJK"
```

**预期效果**: 新增任何未注册的 `_t()` key 或硬编码 CJK 字符串时 CI 失败。

---

### 3.3 测试 C: Streamlit pages/ 目录清洁性检查（防 GAP-004）

**目标**: 确保 `pages/` 目录不存在或为空，防止 Streamlit 自动多页检测冲突。

```python
# tests/test_streamlit_pages_conflict.py

import os
import pytest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
PAGES_DIR = os.path.join(PROJECT_ROOT, "pages")


class TestPagesDirectoryClean:
    """GAP-004 防回归: pages/ 目录不得存在 Streamlit 页面文件"""

    def test_pages_dir_not_exist_or_empty(self):
        """pages/ 目录要么不存在，要么只含 .gitkeep"""
        if not os.path.isdir(PAGES_DIR):
            return
        py_files = [
            f for f in os.listdir(PAGES_DIR)
            if f.endswith(".py") and not f.startswith("__")
        ]
        assert len(py_files) == 0, (
            f"pages/ 目录中发现 {len(py_files)} 个 Streamlit 页面文件，"
            f"会与 app.py 内置导航冲突: {py_files}"
        )

    def test_no_stml_automatic_pages(self):
        """项目中不应有任何 *.st.py 或 streamspec 文件"""
        for root, dirs, files in os.walk(PROJECT_ROOT):
            for f in files:
                if f.endswith(".st.py") or f == ".streamlit.toml":
                    full_path = os.path.join(root, f)
                    content = open(full_path).read()
                    if "pages" in content.lower():
                        pytest.fail(
                            f"发现可能触发 Streamlit 自动页面检测的配置: {full_path}"
                        )
```

---

### 3.4 测试 D: session_state 安全访问审计（防 GAP-005）

**目标**: 扫描 `app.py` 及所有 frontend 源码，确保所有 `st.session_state.xxx` 直接属性访问都有 `.get()` 保护或前置初始化守卫。

```python
# tests/test_session_state_safety.py

import ast
import os
import re
import pytest

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


def _unsafe_session_state_accesses(source: str) -> list[tuple[int, str]]:
    """
    识别不安全的 session_state 访问模式:
    - st.session_state["key"] (下标访问，无 .get)
    - st.session_state.key  (属性访问，用于 if/len/迭代等裸用场景)
    排除安全模式:
    - st.session_state.get(...)
    - "key" in st.session_state
    - st.session_state[key] = value (赋值)
    """
    unsafe = []
    lines = source.split("\n")
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if "session_state" not in stripped:
            continue
        pattern = r'st\.session_state\["([^"]+)"\]'
        matches = re.findall(pattern, stripped)
        for key in matches:
            if ".get(" not in stripped and '"key"' not in stripped:
                unsafe.append((lineno, stripped.rstrip()))
        attr_pattern = r'st\.session_state\.(\w+)'
        attr_matches = re.findall(attr_pattern, stripped)
        for key in attr_matches:
            if ".get(" not in stripped and f'"{key}"' not in stripped:
                if any(kw in stripped for kw in ["if ", "elif ", "while ", "len(", "for "]):
                    unsafe.append((lineno, stripped.rstrip()))
    return unsafe


class TestSessionStateSafety:
    """GAP-005 防回归: session_state 安全访问"""

    def test_app_py_session_state_safe_access(self):
        """app.py 中所有 session_state 条件读取应使用 .get() 或 in 检查"""
        app_py = os.path.join(FRONTEND_DIR, "app.py")
        with open(app_py, "r", encoding="utf-8") as f:
            source = f.read()
        unsafe = _unsafe_session_state_accesses(source)
        known_safe_keys = {"initialized"}
        filtered = [
            (ln, code) for ln, code in unsafe
            if not any(safe in code for safe in known_safe_keys)
        ]
        assert len(filtered) == 0, (
            f"发现 {len(filtered)} 处不安全的 session_state 直接访问:\n" +
            "\n".join(f"  L{ln}: {code[:100]}" for ln, code in filtered[:20])
        )
```

---

### 3.5 测试 E: 异步任务执行管道端到端测试（防 GAP-006）

**目标**: 模拟完整的 `用户提交 → 异步执行 → 成功/失败/取消 → 结果渲染` 流程，验证每一层错误正确传播到 UI 层。

```python
# tests/test_async_pipeline_regression.py

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio


class TestAsyncExecutionPipeline:
    """GAP-006 防回归: 异步执行管道错误传播完整性"""

    @patch("frontend.app.st")
    @patch("frontend.app.execute_with_agent_loop")
    @patch("frontend.app._get_current_session_id", return_value="test-session-001")
    def test_pipeline_success_returns_content(self, mock_sid, mock_exec, mock_st):
        """成功路径: execute_with_agent_loop 返回有效内容 → _async_execute_task 返回 success=True"""
        mock_exec.return_value = (
            "# 测试成果物\n\n内容详情...",
            True,
            "/tmp/test_deliverable.md",
            "content_generation",
            {"filename": "test.md", "task_type": "content_generation"},
        )
        from frontend.app import _async_execute_task
        result = asyncio.get_event_loop().run_until_complete(
            _async_execute_task(
                prompt="帮我写一份报告",
                cancel_event=asyncio.Event(),
                session_ctx=MagicMock(),
                business_type="content_creator",
            )
        )
        assert result["success"] is True
        assert result["content"] is not None
        assert "测试成果物" in result["content"]
        assert result["filepath"] is not None
        assert result["task_type"] == "content_generation"

    @patch("frontend.app.st")
    @patch("frontend.app.execute_with_agent_loop")
    @patch("frontend.app._get_current_session_id", return_value="test-session-002")
    def test_pipeline_engine_failure_returns_error_dict(self, mock_sid, mock_exec, mock_st):
        """失败路径: TaskEngineV3 抛异常 → execute_with_agent_loop 降级也失败 → 最终返回 error"""
        mock_exec.return_value = (None, False, None, None, None)
        from frontend.app import _async_execute_task
        result = asyncio.get_event_loop().run_until_complete(
            _async_execute_task(
                prompt="触发失败的请求",
                cancel_event=asyncio.Event(),
                session_ctx=MagicMock(),
            )
        )
        assert result["success"] is False
        assert result["content"] is None
        assert result["error"] is not None
        assert "task_type" not in result or result["task_type"] is None

    @patch("frontend.app.st")
    @patch("frontend.app.execute_with_agent_loop")
    @patch("frontend.app._get_current_session_id", return_value="test-session-003")
    def test_pipeline_empty_content_not_marked_success(self, mock_sid, mock_exec, mock_st):
        """边界: 返回空字符串内容 → 应判定为失败而非成功"""
        mock_exec.return_value = ("", True, None, None, None)
        from frontend.app import _async_execute_task
        result = asyncio.get_event_loop().run_until_complete(
            _async_execute_task(
                prompt="返回空内容的请求",
                cancel_event=asyncio.Event(),
            )
        )
        assert result["success"] is False
        assert result["error"] is not None

    @patch("frontend.app.st")
    @patch("frontend.app.execute_with_agent_loop", side_effect=Exception("网络超时"))
    @patch("frontend.app._get_current_session_id", return_value="test-session-004")
    def test_pipeline_exception_caught_and_returned(self, mock_sid, mock_exec, mock_st):
        """异常路径: execute_with_agent_loop 抛出未预期异常 → 不崩溃，返回 error dict"""
        from frontend.app import _async_execute_task
        result = asyncio.get_event_loop().run_until_complete(
            _async_execute_task(
                prompt="触发异常的请求",
                cancel_event=asyncio.Event(),
            )
        )
        assert result["success"] is False
        assert result["content"] is None
        assert "网络超时" in result["error"]

    @patch("frontend.app.st")
    @patch("frontend.app.build_confirm_callback")
    @patch("frontend.app.Confirmer")
    @patch("frontend.app.execute_with_agent_loop")
    @patch("frontend.app._get_current_session_id", return_value="test-session-005")
    def test_pipeline_user_cancelled_returns_cancelled_flag(self, mock_sid, mock_exec,
                                                              mock_confirmer_class, mock_build_cb, mock_st):
        """取消路径: Confirmer 返回 not confirmed + cancelled → _cancelled_by_user=True"""
        mock_exec.return_value = ("ok", True, "/tmp/f.md", "general_chat", None)
        mock_confirmer_instance = MagicMock()
        mock_confirmer_instance.check_confirmation = AsyncMock(return_value=MagicMock(
            confirmed=False,
            method="cancelled",
        ))
        mock_confirmer_class.return_value = mock_confirmer_instance
        from frontend.app import _async_execute_task
        result = asyncio.get_event_loop().run_until_complete(
            _async_execute_task(
                prompt="被用户取消的任务",
                cancel_event=asyncio.Event(),
            )
        )
        assert result["success"] is False
        assert result.get("_cancelled_by_user") is True
```

---

## 4 测试方案优化建议

### 4.1 优先级矩阵

| 优先级 | 行动项 | 对应 GAP | 工作量估计 | 收益评估 |
|--------|--------|----------|-----------|---------|
| **P0** | 实施测试 A (AST 函数定义顺序) | GAP-001 | 0.5 天 | 阻断致命级 NameError 回归 |
| **P0** | 实施测试 B-i18n 部分 (键完整性) | GAP-002 | 1 天 | 阻断运行时 KeyError |
| **P1** | 实施测试 B-CJK 部分 (硬编码检测) | GAP-003 | 0.5 天 | 保证国际化一致性 |
| **P1** | 实施测试 D (session_state 安全) | GAP-005 | 0.5 天 | 防止 session 初始化竞态崩溃 |
| **P1** | 实施测试 E (异步管道 E2E) | GAP-006 | 1 天 | 防止静默失败 |
| **P2** | 实施测试 C (pages/ 清洁性) | GAP-004 | 0.2 天 | 避免路由冲突 |
| **P1** | 补充 `test_dashboard_page.py` | GAP-007 | 3-4 天 | 覆盖 862 行页面模块 |
| **P1** | 补充 `test_marketplace_page.py` | GAP-007 | 2-3 天 | 覆盖 543 行页面模块 |
| **P2** | 补充 `test_settings_page.py` UI 层 | GAP-007 | 2-3 天 | 覆盖 675 行设置页面 |
| **P2** | 补充 `test_shared.py` 独立测试 | — | 2 天 | shared.py 1023 行当前仅间接测试 |
| **P2** | 补充 `test_app.py` 核心路径 | — | 5-7 天 | app.py 1913 行最大盲区 |
| **P3** | 建立 CI 质量门禁（见第 5 节） | 全部 | 1 天 | 自动化防护网 |

**总工作量估算**: **18-26 人天**

### 4.2 分阶段实施路线图

```
Phase 1 (Week 1-2): 防回归基础设施 ──────────────────────
├── 测试 A: AST 定义顺序检查        ← 0.5d
├── 测试 B: i18n + CJK 扫描         ← 1.5d
├── 测试 C: pages/ 清洁性           ← 0.2d
├── 测试 D: session_state 安全      ← 0.5d
└── 接入 CI pipeline               ← 0.5d
   小计: ~3.2d

Phase 2 (Week 3-4): 关键路径补全 ────────────────────────
├── 测试 E: 异步管道 E2E            ← 1d
├── dashboard_page 测试             ← 3-4d
└── marketplace_page 测试           ← 2-3d
   小计: ~6-8d

Phase 3 (Week 5-6): 广度覆盖 ───────────────────────────
├── settings_page UI 测试           ← 2-3d
├── shared.py 独立测试              ← 2d
└── app.py 核心路径测试             ← 5-7d
   小计: ~9-12d

Phase 4 (Week 7): 门禁与度量 ───────────────────────────
├── CI 质量门禁配置                 ← 1d
├── 覆盖率报告集成                  ← 0.5d
└── 度看板搭建                      ← 0.5d
   小计: ~2d
```

### 4.3 工具推荐

| 用途 | 推荐工具 | 说明 |
|------|---------|------|
| **覆盖率测量** | `pytest-cov` (带 `--cov=frontend` | 生成行/分支覆盖率报告，建议阈值 ≥ 70% |
| **AST 静态分析** | Python 内置 `ast` 模块（测试 A/B/D 已基于此） | 零依赖，CI 友好 |
| **硬编码检测** | `ast` + `re` 组合（测试 B-CJK 部分） | 可扩展为 pre-commit hook |
| **Mock 框架** | `unittest.mock` (已有约定) + `pytest-mock` | 保持现有 `@patch("...st")` 模式 |
| **异步测试** | `pytest-asyncio` | 测试 E 需要 event_loop 管理 |
| **Lint 规则** | 自定义 flake8 插件检测 `st.session_state.xxx` 裸访问 | 补充测试 D 的静态防御 |
| **CI 集成** | GitHub Actions / GitLab CI | 每次 PR 自动运行全量测试 + 新增 5 套回归测试 |
| **Pre-commit** | `pre-commit` 框架 | 将测试 A/B/C/D 作为 commit-time gate |

### 4.4 测试编写规范补充建议

基于对现有 11 个测试文件的分析，建议补充以下规范：

1. **TC 编号体系推广**: 目前仅 `test_result_cards.py` (TC-001~039) 和 `test_timeline_view.py` (TC-TL-001~058) 使用 TC 编号。建议所有新建测试统一采用 `{模块缩写}-{序号}` 格式，便于追踪。

2. **Mock 注入路径标准化**: 统一使用 `@patch("frontend.{module}.st")` 而非 `@patch("streamlit")`，避免 mock 泄漏到其他模块。

3. **Session State 初始化模板**: 每个 app.py 相关测试都应在 `setUp` 或 fixture 中准备最小 session_state：

```python
@pytest.fixture
def minimal_session(self, mock_st):
    mock_st.session_state = {
        "initialized": True,
        "messages": [],
        "deliverables": [],
        "scenario_count": 0,
        "detected_type": None,
        "flywheel_scores": {"内容质量": 0, "受众增长": 0, "变现能力": 0, "跨域推广": 0, "生态协同": 0},
        "flywheel_level": 1,
        "quality_feedback": {},
        "exec_mode": "质量模式",
    }
```

---

## 5 测试质量门禁标准

### 5.1 覆盖率目标

| 模块 | 当前覆盖率(估) | 目标覆盖率 | 最低门槛 |
|------|---------------|-----------|---------|
| `components/` (整体) | ~65% | **≥ 85%** | ≥ 70% |
| `components/shared.py` | ~30% | **≥ 70%** | ≥ 50% |
| `components/result_cards.py` | ~95% | **≥ 95%** (维持) | ≥ 90% |
| `page_modules/_dashboard_page.py` | 0% | **≥ 70%** | ≥ 50% |
| `page_modules/_marketplace_page.py` | ~20% | **≥ 70%** | ≥ 50% |
| `page_modules/_settings_page.py` | ~25% | **≥ 70%** | ≥ 50% |
| `app.py` (主文件) | 0% | **≥ 50%** | ≥ 30% |
| **前端总体加权平均** | **~35%** | **≥ 70%** | **≥ 55%** |

### 5.2 Pre-Merge Checklist（PR 提交前自查）

每位开发者在提交 PR 前必须确认以下项目：

```
□ 1. 本地通过全量测试: pytest tests/ -v --tb=short
     └─ 预期: 1841+ 用例全部 PASS，0 FAIL, 0 ERROR

□ 2. 新增/修改代码覆盖率不低于准入线:
     └─ 运行: pytest --cov=frontend --cov-report=term-missing --cov-fail-under=55
     └─ 新增代码行覆盖率 ≥ 80%

□ 3. 5 套防回归测试全部通过:
     ├─ TestFunctionDefinitionOrder (测试 A) ✅
     ├─ TestI18nCompleteness (测试 B-i18n) ✅
     ├─ TestNoHardcodedCJK (测试 B-CJK) ✅
     ├─ TestPagesDirectoryClean (测试 C) ✅
     ├─ TestSessionStateSafety (测试 D) ✅
     └─ TestAsyncExecutionPipeline (测试 E) ✅

□ 4. 无新增硬编码 CJK 用户可见字符串:
     └─ 运行: python -m pytest tests/test_i18n_completeness.py::TestNoHardcodedCJK -v

□ 5. 无新增未注册 i18n key:
     └─ 运行: python -m pytest tests/test_i18n_completeness.py::TestI18nCompleteness -v

□ 6. app.py 函数定义顺序无回退:
     └─ 运行: python -m pytest tests/test_frontend_regression.py -v

□ 7. 若修改了以下文件，必须同步更新对应测试:
     ├─ [ ] frontend/app.py → test_app.py 或 test_async_pipeline_regression.py
     ├─ [ ] frontend/components/shared.py → test_shared.py
     ├─ [ ] frontend/page_modules/_dashboard_page.py → test_dashboard_page.py
     ├─ [ ] frontend/page_modules/_marketplace_page.py → test_marketplace_page.py
     ├─ [ ] frontend/page_modules/_settings_page.py → test_settings_page.py
     └─ [ ] opc_manager/locales/*.json → test_i18n_completeness.py

□ 8. Lint 检查通过:
     └─ (如有配置 flake8/black/isort)

□ 9. 新增测试自身质量要求:
     ├─ 每个测试方法有清晰的 docstring 说明测试意图
     ├─ 断言数量 ≥ 1（禁止空测试体）
     ├─ 不使用 pytest.mark.skipfixte除非有明确理由
     └─ 测试方法命名遵循 test_{scenario}_{expected}_{condition} 格式
```

### 5.3 CI 自动化门禁配置

建议在 CI pipeline（GitHub Actions / GitLab CI）中添加以下阶段：

```yaml
# .github/workflows/frontend-test-gate.yml (示例)

name: Frontend Test Gate
on:
  pull_request:
    paths:
      - "frontend/**"
      - "tests/**"
      - "opc_manager/locales/**"

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev,test]"
      - name: Run existing test suite (1841 tests)
        run: pytest tests/ -v --tb=short --junitxml=results.xml
      - name: Run regression guard tests (A-E)
        run: |
          pytest tests/test_frontend_regression.py -v          # 测试A
          pytest tests/test_i18n_completeness.py -v             # 测试B
          pytest tests/test_streamlit_pages_conflict.py -v       # 测试C
          pytest tests/test_session_state_safety.py -v           # 测试D
          pytest tests/test_async_pipeline_regression.py -v      # 测试E

  coverage-gate:
    needs: unit-tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -e ".[dev,test]"
      - name: Coverage check (threshold ≥ 55% for frontend)
        run: |
          pytest tests/ --cov=frontend --cov-report=xml \
            --cov-fail-under=55

  static-analysis:
    needs: unit-tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: AST definition order check (测试A等效)
        run: python -c "
import ast, sys
# ... (内联测试A的核心逻辑)
"
      - name: Hardcoded CJK scan (测试B-CJK等效)
        run: python tests/scripts/scan_hardcoded_cjk.py
```

### 5.4 度量与持续改进指标

| 指标 | 当前值 | Q1 目标 | Q2 目标 |
|------|--------|---------|---------|
| 前端测试总用例数 | ~497 | ≥ 700 | ≥ 1000 |
| 前端代码行覆盖率 | ~35% | ≥ 55% | ≥ 70% |
| 防回归测试套件数 | 0 | 5 (A-E) | 5 + 扩展 |
| P0/P1 盲区消除数 | 0/7 | 5/7 | 7/7 |
| 平均缺陷逃逸周期 | 未知 | ≤ 3 天 | ≤ 1 天 |
| CI 平均执行时间 | 未知 | ≤ 5 min | ≤ 8 min (含覆盖率) |

---

## 附录

### A. 术语表

| 术语 | 定义 |
|------|------|
| **TC (Test Case)** | 测试用例，采用 `{模块}-{序号}` 编号 |
| **GAP** | 测试盲区编号，GAP-001 ~ GAP-007 |
| **P0/P1/P2** | 优先级: P0=致命/阻断, P1=高/重要, P2=中/改善 |
| **AST** | Abstract Syntax Tree，Python 抽象语法树 |
| **CJK** | Chinese/Japanese/Korean，中日韩统一表意文字 |
| **i18n** | Internationalization，国际化 |
| **E2E** | End-to-End，端到端测试 |
| **CI** | Continuous Integration，持续集成 |

### B. 参考文献

- 现有 11 个前端测试文件（详见 1.1 节表格）
- `frontend/app.py` (1913 行，主应用文件)
- `frontend/components/shared.py` (1023 行，共享组件)
- `frontend/page_modules/_dashboard_page.py` (862 行)
- `frontend/page_modules/_marketplace_page.py` (543 行)
- `frontend/page_modules/_settings_page.py` (675 行)

### C. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| v1.0 | 2026-05-17 | 初版，基于 v0.2.0 代码库全量审计 |
