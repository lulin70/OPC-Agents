# OPC-Agents v0.2.0 前端架构重组方案

> **文档版本**: v1.0  
> **日期**: 2026-05-17  
> **状态**: 待评审  
> **分析基线**: `frontend/app.py` (1913行) + 11个模块文件，总计 12,156 行

---

## 目录

- [Section 1: 现状诊断](#section-1-现状诊断)
- [Section 2: 目标架构](#section-2-目标架构)
- [Section 3: 分阶段实施计划](#section-3-分阶段实施计划)
- [Section 4: 影响评估](#section-4-影响评估)
- [Section 5: 验证标准](#section-5-验证标准)

---

## Section 1: 现状诊断

### 1.1 文件清单与行数统计

| 文件路径 | 行数 | 职责 | 中文字符串行数 | i18n覆盖率 |
|----------|------|------|----------------|------------|
| `frontend/app.py` | **1913** | 路由+状态初始化+聊天UI+侧边栏+引导+任务执行+成果物+审计日志+成长页 | **~1706** (89%) | ~11% |
| `frontend/components/shared.py` | **1023** | 导出工具/主题/Toast通知/进度条/语言选择器/快捷键 | **~860** (84%) | ~16% |
| `frontend/components/undo_panel.py` | **1173** | 撤销面板UI/操作记录展示/批量撤销 | **~777** (66%) | ~34% |
| `frontend/components/timeline_view.py` | 1140 | 时间线视图组件 | 未详扫 | 待确认 |
| `frontend/components/live_log_panel.py` | 803 | 实时日志面板 | 未详扫 | 待确认 |
| `frontend/components/smart_suggestions.py` | 647 | 智能建议面板 | 未详扫 | 待确认 |
| `frontend/components/input_autocomplete.py` | 649 | 输入自动补全 | 未详扫 | 待确认 |
| `frontend/components/result_cards.py` | 472 | 结果卡片渲染 | 未详扫 | 待确认 |
| `frontend/components/confirmation_dialog.py` | 370 | 确认对话框 | 未详扫 | 待确认 |
| `frontend/page_modules/_dashboard_page.py` | 862 | 仪表盘页面 | **~0** (0%) | ✅ ~100% |
| `frontend/page_modules/_marketplace_page.py` | 543 | 技能市场页面 | **~55** (10%) | ~90% |
| `frontend/page_modules/_settings_page.py` | 675 | 设置页面 | **~24** (4%) | ~96% |
| `opc_manager/i18n.py` | 1886 | 国际化字典 (zh_CN/en_US/ja_JP, ~617个key) | N/A | N/A |
| **合计** | **12,156** | | **~3,422处硬编码** | |

### 1.2 app.py 内部职责分解（1913行的构成）

```
app.py 结构解剖:
├── L001-036:   模块文档字符串 (36行)
├── L037-082:   导入+环境初始化+目录创建 (46行)
├── L086-102:   _save_chat_history / _load_chat_history     ← 工具函数
├── L105-116:   _has_api_key / _is_demo_mode                ← 状态查询
├── L119-146:   _get_demo_dashboard_data                    ← Demo数据(硬编码中文)
├── L149-151:   _show_success_toast                         ← UI辅助
├── L155-196:   from imports (42行, 大量shared函数导入)
├── L199-268:   PERSONA_MAP / TYPE_DISPLAY / SCENARIOS_*    ← 业务常量(硬编码中文)
├── L271-337:   safe_detect / safe_get_persona / safe_track_flywheel  ← 安全包装器
├── L340-370:   generate_filename / save_deliverable         ← 文件IO
├── L373-472:   execute_with_agent_loop                     ← 任务执行(AgentLoop)
├── L475-557:   execute_task_and_deliver                    ← 任务执行(TaskEngineV3)
├── L560-663:   _async_execute_task                         ← 异步执行包装
├── L666-690:   st.set_page_config + Demo模式Banner          ← 页面配置
├── L692-767:   session_state 初始化块 (75行!)               ← 状态管理
├── L769-862:   _show_onboarding_overlay + 调用             ← 引导流程
├── L879-1046:  with st.sidebar: 块 (167行!)                 ← 侧边栏(含内联市场/技能编辑器/性能监控)
├── L1049-1098: _render_deliverables_list                   ← 成果物列表
├── L1101-1257: _render_audit_log_page                      ← 审计日志
├── L1260-1821: if page == "chat": 块 (561行!!!)            ← 主聊天页面
├── L1823-1835: elif page == "deliverables":                 ← 成果物页路由
├── L1840-1887: elif page == "growth":                       ← 成长页路由
├── L1892-1893: elif page == "marketplace":                  ← 市场页路由
├── L1898-1899: elif page == "dashboard":                    ← 仪表盘路由
├── L1904-1906: elif page == "settings":                     ← 设置页路由
└── L1911-1913: Health Check端点
```

**核心问题**: app.py 承担了 **至少 9 种不同职责**，其中最大的单个代码块（聊天页面）达 **561 行**。

### 1.3 依赖关系图

```
                          ┌─────────────────┐
                          │    app.py       │
                          │  (1913行巨石)    │
                          └──────┬───────┬───┘
                                 │       │
              ┌──────────────────┼───┐   │
              │                  │   │   │
              ▼                  ▼   ▼   ▼
    ┌─────────────┐  ┌──────────────┐ ┌─▼───────────┐
    │ shared.py   │  │ undo_panel.py│ │ page_modules │
    │ (1023行)    │  │ (1173行)     │ │              │
    └──────┬──────┘  └──────┬───────┘ │  dashboard   │
           │                │         │  marketplace  │
           │                │         │  settings     │
           ▼                ▼         └──────┬────────┘
    ┌──────────────┐  ┌──────────┐          │
    │ confirmation  │  │ result_  │          │
    │ _dialog.py    │  │ cards.py │          │
    │ input_auto-   │  │ smart_   │          │
    │ complete.py   │  │ sugges-  │          │
    │ live_log_     │  │ tions.py│          │
    │ panel.py      │  │ timeline│          │
    └──────────────┘  │ _view.py│          │
                      └─────────┘          │
                                           ▼
                                   ┌───────────────┐
                                   │  opc_manager   │
                                   │  i18n.py       │
                                   └───────────────┘

异常依赖（问题）:
  ★ _dashboard_page.py → app.py._get_demo_dashboard_data  (反向依赖!)
  ★ app.py 使用 read_file() 但未在可见作用域定义/导入
  ★ shared.py 引用 ErrorHandler 但未在文件头导入（运行时导入）
  ★ undo_panel.py 与 shared.py 存在重复定义 (_get_undo_manager, _get_current_session_id)
```

### 1.4 反模式完整清单（超出已知7类的额外发现）

#### P0 — 必须立即修复（会导致运行时崩溃或数据丢失）

| # | 反模式 | 位置 | 详情 | 复现概率 |
|---|--------|------|------|----------|
| F01 | **God Object (巨石模块)** | `app.py:1-1913` | 单文件承担路由/状态/UI/业务逻辑/IO 9种职责 | 100% (持续恶化) |
| F02 | **幽灵函数调用** | `app.py:L1093` | `read_file(real_fp)` 被调用但从未在 app.py 中定义或导入 | 100% (触发即崩溃) |
| F03 | **循环依赖风险** | `_dashboard_page.py:L333` → `app.py` | 页面模块反向依赖主模块的 demo 数据函数 | 100% (重构必断) |
| F04 | **session_state 初始化散落** | `app.py:L692-767` | 75行初始化代码与配置代码混杂，无封装 | 高 (维护易遗漏) |

#### P1 — 高优先级（影响功能正确性或可维护性）

| # | 反模式 | 位置 | 详情 | 复现概率 |
|---|--------|------|------|----------|
| F05 | **if/elif 路由链脆弱性** | `app.py:L1825-1906` | 用字符串字面量 ("chat", "deliverables"...) 做 routing key，i18n切换后可能断裂 | 中 (i18n切换时) |
| F06 | **i18n 灾难性缺口** | `app.py`(1706行), `shared.py`(860行), `undo_panel.py`(777行) | ~3422处硬编码中/日文字符串未走 i18n 系统 | 100% (每行新代码都可能添加) |
| F07 | **函数定义顺序敏感** | `app.py` | Python 自顶向下执行，虽然当前定义在调用前，但任何重排都会引入 NameError | 低 (但有隐患) |
| F08 | **重复定义** | `shared.py` vs `undo_panel.py` | `_get_undo_manager()`, `_get_current_session_id()` 在两个文件中各自实现 | 100% (行为可能漂移) |
| F09 | **业务常量硬编码在前端** | `app.py:L199-268` | PERSONA_MAP, TYPE_DISPLAY, SCENARIOS_CORE/MORE 含大量中文 | 高 (新增场景必改前端) |
| F10 | **Demo数据硬编码中文** | `app.py:L119-146` | `_get_demo_dashboard_data()` 返回纯中文 demo 数据 | 100% (日文/英文模式显示中文) |
| F11 | **全局搜索功能重复** | `app.py sidebar` + `_marketplace_page.py` | 两套独立的全局搜索实现，逻辑不一致 | 中 (维护成本翻倍) |
| F12 | **内联巨型代码块** | `app.py:L1260-1821` | 聊天页面 561 行 if 块不可拆分、不可测试 | 高 (任何改动都是高风险) |

#### P2 — 中优先级（影响代码质量和扩展性）

| # | 反模式 | 位置 | 详情 | 复现概率 |
|---|--------|------|------|----------|
| F13 | **双语言选择器** | `settings_page.py:L397-409` vs `shared.py:_render_language_selector()` | 设置页有自己的语言下拉框(disabled)，与侧边栏选择器不同步 | 中 (用户困惑) |
| F14 | **Streamlit pages/ 干扰** | `frontend/pages/__init__.py` | 目录存在导致 Streamlit 自动检测为 multipage 应用 | 低 (当前仅__init__.py) |
| F15 | **CSS 内嵌Python** | `shared.py:L157-185`, `app.py:L782-803` | 大段HTML/CSS以字符串形式嵌入Python代码 | 高 (每次修改需重启) |
| F16 | **错误处理不统一** | 多处混用 | 有的用 `ErrorHandler.translate()`，有的用 `st.error(raw)`，有的用 `show_error()` | 中 (用户体验不一致) |
| F17 | **import 散落在函数内部** | `app.py` 多处, `shared.py:L142` | 如 `from opc_manager.secure_storage import ...` 在 try/except 中延迟导入 | 中 (掩盖了真实的依赖关系) |
| F18 | **侧边栏过重** | `app.py:L879-1046` | 167行侧边栏代码包含：搜索/导航/人格展示/执行模式/技能编辑器(内联)/市场面板(内联)/性能监控/撤销面板/实时日志/主题/语言/快捷键/版本号 | 高 (每次加功能都改这里) |

### 1.5 风险矩阵

| 问题ID | 严重度 | 影响 | 发现难度 | 修复成本 | 综合风险分 |
|--------|--------|------|----------|----------|-----------|
| F02 幽灵函数 | **P0** | 运行时崩溃 | 低 (lint可发现) | 低 (加一行import) | **🔴 9/10** |
| F01 巨石模块 | **P0** | 无法维护/无法测试 | 显而易见 | 高 (需大重构) | **🔴 8/10** |
| F06 i18n缺口 | **P0** | 国际化完全失效 | 中 (需扫描工具) | 很高 (~3400处) | **🔴 8/10** |
| F03 循环依赖 | **P1** | 重构必断 | 中 (静态分析) | 中 (提取函数) | **🟠 7/10** |
| F05 路由脆弱性 | **P1** | 页面路由失效 | 低 (显而易见) | 低 (改用枚举) | **🟠 6/10** |
| F12 聊天页巨型块 | **P1** | 改动高风险 | 显而易见 | 高 (需拆分) | **🟠 6/10** |
| F09 常量硬编码 | **P1** | 扩展困难 | 低 | 中 (提取到config) | **🟡 5/10** |
| F10 Demo数据中文 | **P1** | 非 zh_CN 模式异常 | 低 | 低 (走i18n) | **🟡 5/10** |
| F08 重复定义 | **P1** | 行为漂移 | 中 (需人工比对) | 低 (统一入口) | **🟡 5/10** |
| F11 搜索重复 | **P2** | 维护成本×2 | 中 | 中 (统一) | **🟡 4/10** |
| F13 双语言选择器 | **P2** | 用户困惑 | 低 | 低 (删除一个) | **🟢 3/10** |
| F14 pages/干扰 | **P2** | Streamlit行为异常 | 低 | 极低 (删目录) | **🟢 2/10** |

---

## Section 2: 目标架构

### 2.1 目标目录结构

```
frontend/
├── __init__.py                    # 包标记
├── app.py                         # 【目标 <150行】纯入口: 配置→初始化→路由分发
│
├── config.py                      # 【新建】应用级常量/配置集中管理
│   ├── PAGE_REGISTRY              # 页面注册表
│   ├── PERSONA_MAP / TYPE_DISPLAY # 业务常量 (从app.py迁出)
│   ├── SCENARIOS_CORE / MORE      # 场景按钮配置
│   ├── DEMO_DATA                  # Demo数据 (支持i18n)
│   └── EXPORT_FORMAT_MAP          # 导出格式映射
│
├── state.py                       # 【新建】session_state 初始化与管理器
│   ├── init_session_state()       # 封装75行初始化逻辑
│   ├── get/set 封装               # 类型安全的state访问
│   └── restore_deliverables()     # 磁盘恢复逻辑
│
├── router.py                      # 【新建】注册制路由引擎
│   ├── PageKey 枚举               # 替代字符串字面量
│   ├── PageRegistry               # {PageKey: render_fn} 映射
│   ├── route(page_key)            # 核心分发函数
│   └── get_nav_labels()           # i18n感知的导航标签生成
│
├── sidebar.py                     # 【新建】侧边栏模块 (从app.py 167行提取)
│   ├── render_sidebar()           # 主入口
│   ├── _render_search()           # 全局搜索 (统一两处实现)
│   ├── _render_persona_info()     # 人格信息展示
│   ├── _render_exec_mode()        # 执行模式选择
│   ├── _render_tool_buttons()     # 技能编辑器/市场/监控等按钮
│   └── _render_theme_lang()       # 主题+语言+版本号
│
├── pages/                         # ⚠️ 【删除】避免Streamlit multipage干扰
│   └── (移除此目录或保留空__init__.py做包标记)
│
├── page_modules/                  # 页面渲染模块 (已有, 扩展)
│   ├── __init__.py
│   ├── _chat_page.py              # 【新建】聊天页面 (从app.py 561行提取)
│   │   ├── render_chat_page()     # 主入口
│   │   ├── _render_welcome()      # 欢迎区域
│   │   ├── _render_scenarios()    # 场景按钮
│   │   ├── _render_message_list() # 消息历史
│   │   ├── _handle_user_input()   # 用户输入处理
│   │   ├── _poll_task_status()    # 任务轮询 (从561行中提取的最大子块)
│   │   └── _render_error_fallback() # 错误友好化
│   ├── _deliverables_page.py      # 【新建】成果物页面 (从app.py提取)
│   │   ├── render_deliverables_page()
│   │   └── (复用 shared.py 的导出/列表组件)
│   ├── _audit_log_page.py         # 【新建】审计日志页面 (从app.py提取)
│   │   └── render_audit_log_page()
│   ├── _growth_page.py            # 【新建】成长飞轮页面 (从app.py提取)
│   │   └── render_growth_page()
│   ├── _dashboard_page.py         # 【已有】基本OK, 修循环依赖
│   ├── _marketplace_page.py       # 【已有】基本OK, 补i18n缺口
│   └── _settings_page.py          # 【已有】基本OK, 删除冗余语言选择器
│
├── components/                    # 可复用UI组件 (已有, 清理)
│   ├── __init__.py
│   ├── shared.py                  # 【拆分】目标 <400行
│   │   ├── toasts.py              # show_success/error/info  (提取)
│   │   ├── export_helpers.py      # 导出相关全部函数 (提取)
│   │   ├── theme.py               # 主题配置/CSS (提取)
│   │   ├── selectors.py           # 语言/主题选择器 (提取)
│   │   └── progress.py            # 进度指示器 (提取)
│   ├── undo_panel.py              # 【拆分】目标 <600行, 补i18n
│   ├── confirmation_dialog.py     # 保持不变
│   ├── input_autocomplete.py      # 保持不变
│   ├── live_log_panel.py          # 保持不变
│   ├── result_cards.py            # 保持不变
│   ├── smart_suggestions.py       # 保持不变
│   └── timeline_view.py           # 保持不变
│
└── tasks/                         # 【新建】任务执行逻辑 (从app.py提取)
    ├── __init__.py
    ├── execution.py               # execute_with_agent_loop / execute_task_and_deliver
    ├── async_execution.py         # _async_execute_task
    ├── safety_wrappers.py         # safe_detect / safe_get_persona / safe_track_flywheel
    └── deliverable_io.py          # generate_filename / save_deliverable / _load_chat_history
```

### 2.2 模块职责矩阵（SRP 合规）

| 模块 | 单一职责 | 最大行数限制 | 依赖方向 |
|------|----------|-------------|---------|
| `app.py` | 入口点：加载配置→初始化状态→调用router | **≤150** | 仅依赖 router, state, config |
| `config.py` | 所有前端常量和配置数据 | **≤200** | 无外部依赖 |
| `state.py` | session_state 的初始化和类型安全访问 | **≤150** | 依赖 config |
| `router.py` | 页面注册与请求分发 | **≤120** | 依赖 page_modules.*, config |
| `sidebar.py` | 侧边栏渲染 | **≤250** | 依赖 components.shared, config |
| `pages/_chat_page.py` | 聊天交互界面 | **≤500** | 依赖 components.*, tasks.*, router |
| `pages/_deliverables_page.py` | 成果物列表+操作日志 | **≤200** | 依赖 components.shared |
| `pages/_audit_log_page.py` | 审计日志查看器 | **≤200** | 依赖 opc_manager.audit_log |
| `pages/_growth_page.py` | 成长飞轮可视化 | **≤150** | 仅 st + i18n |
| `tasks/execution.py` | 同步任务执行管道 | **≤250** | 依赖 opc_manager.* |
| `tasks/async_execution.py` | 异步任务包装 | **≤150** | 依赖 tasks.execution |
| `components/shared.py` (拆分后) | 通用UI工具集 | **≤400/每个子模块** | 依赖 opc_manager.i18n |
| `components/undo_panel.py` (清理后) | 撤销操作UI | **≤600** | 依赖 opc_manager.undo_manager |

### 2.3 依赖方向规则

```
禁止的依赖方向:
  ✗ page_modules/* → app.py          (当前: _dashboard_page → app.py._get_demo_dashboard_data)
  ✗ components/* → app.py            (当前: 无直接依赖, 但demo数据耦合)
  ✗ 任意模块 → 循环依赖

允许的依赖方向 (严格单向):
  app.py → router.py → page_modules/* → components/* → opc_manager/*
                                              ↓
                                         tasks/* → opc_manager/*

  app.py → state.py → config.py
  app.py → sidebar.py → components/*
  page_modules/* → tasks/* → opc_manager/*
  components/*.py → opc_manager/i18n.py (唯一允许的后端依赖)
```

### 2.4 新路由机制设计

**核心思路**: 用 **枚举 + 注册表** 替代 `if/elif` 字符串匹配链。

```python
# frontend/router.py
from enum import Enum, auto
from typing import Callable, Dict

class PageKey(Enum):
    """页面标识符 — 内部键，永不用于用户显示"""
    CHAT = auto()
    DELIVERABLES = auto()
    DASHBOARD = auto()
    GROWTH = auto()
    MARKETPLACE = auto()
    SETTINGS = auto()

# 注册表: PageKey → 渲染函数
_PAGE_REGISTRY: Dict[PageKey, Callable] = {}

def register_page(key: PageKey):
    """装饰器: 将渲染函数注册到路由表"""
    def decorator(fn: Callable):
        _PAGE_REGISTRY[key] = fn
        return fn
    return decorator

def get_current_page() -> PageKey:
    """从 session_state.radio 获取当前页面枚举值"""
    raw = st.session_state.get("selected_page", PageKey.CHAT.value)
    try:
        return PageKey(raw)
    except ValueError:
        return PageKey.CHAT

def navigate():
    """核心路由分发 — 替代整个 if/elif 链"""
    page_key = get_current_page()
    renderer = _PAGE_REGISTRY.get(page_key)
    if renderer:
        renderer()
    else:
        st.error(f"未知页面: {page_key}")

def get_nav_labels() -> Dict[PageKey, str]:
    """返回 i18n 感知的导航标签"""
    from opc_manager.i18n import t as _t
    return {
        PageKey.CHAT: _t("nav_chat"),
        PageKey.DELIVERABLES: _t("nav_deliverables"),
        PageKey.DASHBOARD: _t("nav_dashboard"),
        PageKey.GROWTH: _t("nav_growth"),
        PageKey.MARKETPLACE: _t("nav_marketplace"),
        PageKey.SETTINGS: _t("nav_settings"),
    }
```

**使用方式** (在各 page module 中):

```python
# frontend/page_modules/_chat_page.py
from frontend.router import PageKey, register_page

@register_page(PageKey.CHAT)
def render_chat_page():
    # ... 原 app.py 中 if page=="chat" 块的全部内容 ...
```

**新 app.py** (目标 ≤150行):

```python
"""OPC-Agents Frontend Entry Point"""

import streamlit as st
from frontend.config import *
from frontend.state import init_session_state
from frontend.router import navigate, get_nav_labels, PageKey
from frontend.sidebar import render_sidebar

def main():
    st.set_page_config(page_title="一人公司助手", ...)
    init_session_state()
    render_sidebar()
    navigate()

if __name__ == "__main__":
    main()
```

### 2.5 i18n 集成模式

#### 2.5.1 硬编码字符串扫描规则

建立 **CI 自动检查**，阻止新的硬编码字符串进入代码库:

```bash
# .trae/rules/no_hardcoded_strings.sh
# 扫描 frontend/ 下所有 .py 文件中的中/日/韩文字符
# 排除: i18n.py 字典本身, 注释行, docstring
find frontend/ -name "*.py" -not -name "i18n.py" -not -path "*__pycache__*" \
  | xargs grep -n '[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]' \
  | grep -v '^\s*#' | grep -v '^\s*"""' | grep -v 'i18n\.py'
```

#### 2.5.2 三阶段迁移策略

| 优先级 | 文件 | 硬编码行数 | 迁移方案 |
|--------|------|-----------|----------|
| **Phase 3A** | `app.py` | ~1706 | 最高优先。将所有用户可见字符串替换为 `_t('key')`，常量(PERSONA_MAP等)移入 config.py 并走 i18n |
| **Phase 3B** | `shared.py` | ~860 | 导出按钮标签/格式提示/事件类型标签 全部抽取为 i18n key |
| **Phase 3C** | `undo_panel.py` | ~777 | OPERATION_TYPE_CONFIG / STATUS_CONFIG 的 label 字段走 i18n |
| **Phase 3D** | `_marketplace_page.py` | ~55 | 全局搜索中的硬编码中文提示语 |
| **Phase 3E** | `_settings_page.py` | ~24 | 少量残留字符串 |

#### 2.5.3 新增 i18n Key 命名规范

```
原有命名风格 (保持):  nav_chat, settings_llm, mp_title
新增分类前缀:
  app_*.py  →  chat_*, onboarding_*, sidebar_*, exec_*, error_*
  shared_*.py →  export_*, theme_*, toast_*, progress_*, event_*
  undo_*.py →  undo_op_*, undo_status_*, undo_action_*
  config_*.py →  persona_*, scenario_*, type_*, demo_*
```

---

## Section 3: 分阶段实施计划

### Phase 0: 安全网搭建 (预计 1-2 小时)

**目标**: 在任何重构之前建立回归保护机制。

#### 0.1 创建 Golden Snapshot

```bash
# scripts/capture_golden_snapshot.sh
# 1. 截图每个页面 (chat/deliverables/dashboard/growth/marketplace/settings)
# 2. 记录当前 session_state 初始状态JSON
# 3. 记录侧边栏所有按钮的可见性
# 4. 保存到 docs/internal/golden_snapshot_v020/
```

#### 0.2 编写冒烟测试

创建 `tests/frontend/smoke_test.py`:

```python
"""前端冒烟测试 — 验证重构不破坏基本功能"""
import pytest

class TestGoldenPath:
    def test_app_imports_without_error(self):
        """app.py 可以被正常 import（无 NameError/ImportError）"""
        import frontend.app
    
    def test_all_page_keys_registered(self):
        """路由表中包含所有6个页面"""
        from frontend.router import _PAGE_REGISTRY, PageKey
        for key in PageKey:
            assert key in _PAGE_REGISTRY, f"页面 {key} 未注册"
    
    def test_i18n_coverage_threshold(self):
        """i18n 覆盖率不低于当前基线 (逐步提升)"""
        # 统计 frontend/ 下硬编码CJK字符行数
        # 断言: 不超过 golden snapshot 的数量
    
    def test_no_circular_import(self):
        """无循环导入"""
        import importlib
        modules = [
            'frontend.app', 'frontend.router', 'frontend.config',
            'frontend.state', 'frontend.sidebar',
            'frontend.page_modules._chat_page',
            'frontend.page_modules._dashboard_page',
        ]
        for mod in modules:
            importlib.import_module(mod)

class TestRoutingIntegrity:
    def test_chat_page_renders(self): ...
    def test_dashboard_page_renders(self): ...
    def test_settings_page_renders(self): ...
    def test_marketplace_page_renders(self): ...

class TestSessionStateInit:
    def test_initialized_flag_set(self): ...
    def test_messages_list_exists(self): ...
    def test_deliverables_list_exists(self): ...
    def test_async_executor_created(self): ...
```

#### 0.3 Git 分支策略

```bash
git checkout -b reorg/phase0-safety-net    # 安全网
git checkout -b reorg/phase1-extraction    # 结构提取
git checkout -b reorg/phase2-router         # 路由替换
git checkout -b reorg/phase3-i18n           # 国际化加固
```

**回滚预案**: 每个 Phase 完成后打 tag (`v0.2.0-phase0`, `v0.2.0-phase1`, ...)。出问题时 `git reset --hard v0.2.0-phaseN-1` 即可。

---

### Phase 1: 结构化提取 (预计 4-6 小时)

**目标**: app.py 从 1913 行缩减至 ≤300 行（中间态），所有函数归位到正确模块。

#### 1.1 提取步骤（按依赖顺序）

| 步骤 | 操作 | 提取源 | 目标文件 | 行数变化 | 风险 |
|------|------|--------|----------|----------|------|
| 1.1a | 创建 `config.py` | app.py L199-268, L119-146 | `frontend/config.py` | ~120行 | 低 (纯数据移动) |
| 1.1b | 创建 `state.py` | app.py L692-767 | `frontend/state.py` | ~80行 | 低 (纯逻辑移动) |
| 1.1c | 创建 `tasks/` 包 | app.py L271-557, L560-663 | `tasks/*.py` | ~350行 | 中 (需验证异步执行) |
| 1.1d | 创建 `sidebar.py` | app.py L879-1046 | `frontend/sidebar.py` | ~170行 | 中 (UI提取) |
| 1.1e | 创建 `_chat_page.py` | app.py L1260-1821 | `page_modules/_chat_page.py` | ~560行 | **高** (最复杂块) |
| 1.1f | 创建 `_deliverables_page.py` | app.py L1049-1098, L1823-1835 | `page_modules/_deliverables_page.py` | ~70行 | 低 |
| 1.1g | 创建 `_audit_log_page.py` | app.py L1101-1257 | `page_modules/_audit_log_page.py` | ~160行 | 低 |
| 1.1h | 创建 `_growth_page.py` | app.py L1840-1887 | `page_modules/_growth_page.py` | ~50行 | 低 |
| 1.1i | 修复 F02 (read_file) | app.py L1093 | 在 deliverables_page 或 shared 中补充 | 3行 | 低 |
| 1.1j | 修复 F03 (循环依赖) | _dashboard_page.py L333 | 将 `_get_demo_dashboard_data` 移入 config.py | 5行 | 低 |

#### 1.2 提取后的 app.py 样貌 (中间态, ~300行)

```python
"""...docstring..."""

# ── Imports ──────────────────────────────────────
import streamlit as st
# ... 标准库 ...
from frontend.config import *           # 1.1a
from frontend.state import init_session_state  # 1.1b
from frontend.tasks.execution import *    # 1.1c
from frontend.tasks.async_execution import _async_execute_task  # 1.1c
from frontend.tasks.deliverable_io import *  # 1.1c
from frontend.tasks.safety_wrappers import *  # 1.1c
from frontend.sidebar import render_sidebar  # 1.1d
from frontend.page_modules._chat_page import render_chat_page  # 1.1e
from frontend.page_modules._deliverables_page import render_deliverables_page  # 1.1f
from frontend.page_modules._audit_log_page import render_audit_log_page  # 1.1g
from frontend.page_modules._growth_page import render_growth_page  # 1.1h
from frontend.page_modules._dashboard_page import _render_dashboard_page
from frontend.page_modules._marketplace_page import _render_skill_marketplace_page
from frontend.page_modules._settings_page import _create_settings_page
from frontend.components.shared import (...)  # 保持现有
from frontend.components.undo_panel import (...)
# ... 其他 component imports ...

# ── Page Config & Init ──────────────────────────
st.set_page_config(...)
DEMO_MODE = _is_demo_mode()
init_session_state()

# ── Onboarding ─────────────────────────────────
_show_onboarding_overlay()  # 或也提取到独立模块

# ── Sidebar ────────────────────────────────────
render_sidebar()

# ── Routing (临时: 仍用 if/elif, Phase 2 替换) ──
page = st.radio(...)
if page == "chat":
    render_chat_page()
elif page == "deliverables":
    render_deliverables_page()
elif page == "dashboard":
    _render_dashboard_page(demo_mode=DEMO_MODE)
# ... 其余页面 ...

# Health Check
if st.query_params.get("_stcore_health"):
    st.write("ok")
```

#### 1.3 验证清单

- [ ] `python -c "import frontend.app"` 无报错
- [ ] 启动 Streamlit，6个页面均可访问
- [ ] 聊天页面提交任务 → 能执行并显示结果
- [ ] 成果物页面可以下载文件
- [ ] 设置页面保存配置后刷新仍有效
- [ ] 侧边栏所有折叠面板可展开
- [ ] Demo 模式下 Dashboard 显示示例数据
- [ ] 冒烟测试全绿

---

### Phase 2: 路由系统替换 (预计 2-3 小时)

**目标**: 用注册制路由替代 if/elif 链，彻底消除 F05 脆弱性。

#### 2.1 实施步骤

| 步骤 | 操作 | 详情 |
|------|------|------|
| 2.1a | 创建 `router.py` | 实现 PageKey 枚举 + register_page 装饰器 + navigate() 函数 |
| 2.1b | 改造 `sidebar.py` | `st.radio` 的 options 从 `PAGE_KEYS` 列表获取，format_func 用 `get_nav_labels()` |
| 2.1c | 为每个 page module 加 `@register_page` 装饰器 | 6个页面各加一行 |
| 2.1d | 重写 `app.py` 路由部分 | `navigate()` 一行替代 20+ 行 if/elif |
| 2.1e | 清理 `pages/` 目录 | 确认无 `.py` 文件残留 (仅留 `__init__.py`) |

#### 2.2 关键代码: router.py

```python
"""Registry-based page router for OPC-Agents frontend."""

from enum import Enum, auto
from typing import Callable, Dict, Optional
import streamlit as st


class PageKey(Enum):
    CHAT = "chat"
    DELIVERABLES = "deliverables"
    DASHBOARD = "dashboard"
    GROWTH = "growth"
    MARKETPLACE = "marketplace"
    SETTINGS = "settings"


_REGISTRY: Dict[PageKey, Callable[[], None]] = {}


def register_page(key: PageKey):
    def decorator(fn: Callable[[], None]):
        if key in _REGISTRY:
            raise ValueError(f"页面 {key} 已被注册")
        _REGISTRY[key] = fn
        return fn
    return decorator


def get_current_page() -> PageKey:
    raw = st.session_state.get("selected_page", PageKey.CHAT.value)
    try:
        return PageKey(raw)
    except ValueError:
        return PageKey.CHAT


def get_all_keys() -> list:
    return list(PageKey)


def get_nav_labels() -> dict:
    from opc_manager.i18n import t as _t
    return {
        PageKey.CHAT: _t("nav_chat"),
        PageKey.DELIVERABLES: _t("nav_deliverables"),
        PageKey.DASHBOARD: _t("nav_dashboard"),
        PageKey.GROWTH: _t("nav_growth"),
        PageKey.MARKETPLACE: _t("nav_marketplace"),
        PageKey.SETTINGS: _t("nav_settings"),
    }


def navigate():
    page_key = get_current_page()
    renderer = _REGISTRY.get(page_key)
    if renderer:
        renderer()
    else:
        st.error(f"页面未注册: {page_key}")
```

#### 2.3 最终 app.py 目标形态 (≤150行)

```python
"""OPC-Agents v0.2.1 Streamlit Frontend."""

import streamlit as st
import os
from pathlib import Path
from dotenv import load_dotenv

_WORKSPACE_DIR = os.environ.get("OPC_WORKSPACE", os.getcwd())
load_dotenv(Path(_WORKSPACE_DIR) / ".env")

from opc_manager.monitoring import init_monitoring
from opc_manager.error_handler import ErrorHandler
init_monitoring()

from frontend.config import DEMO_MODE, DEMO_MODE_BANNER
from frontend.state import init_session_state
from frontend.sidebar import render_sidebar
from frontend.router import navigate

st.set_page_config(
    page_title="OPC-Agents",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

if DEMO_MODE:
    st.markdown(DEMO_MODE_BANNER, unsafe_allow_html=True)

init_session_state()
render_sidebar()
navigate()

if st.query_params.get("_stcore_health") == "1":
    st.write("ok")
    st.stop()
```

#### 2.4 验证清单

- [ ] 所有 6 个 PageKey 枚举值对应一个 `@register_page` 装饰器
- [ ] `st.radio` 的 options 是 `PageKey` 列表而非字符串
- [ ] 切换语言后，导航标签跟随变化但路由不受影响
- [ ] 新增页面只需: (1) 在 PageKey 加枚举值 (2) 写渲染函数加装饰器
- [ ] URL 参数 `?_stcore_health=1` 仍然工作

---

### Phase 3: i18n 加固 (预计 3-4 小时)

**目标**: 将硬编码 CJK 字符串从 ~3422 处降至 <100 处（仅允许注释/docstring）。

#### 3.1 实施步骤

| 步骤 | 操作 | 涉及文件 | 新增i18n key数估计 |
|------|------|----------|-------------------|
| 3.1a | **app.py 残留字符串迁移** | app.py (中间态残留), config.py | ~120 key |
| 3.1b | **shared.py 全面i18n** | shared.py → 拆分出的子模块 | ~80 key |
| 3.1c | **undo_panel.py 全面i18n** | undo_panel.py | ~50 key |
| 3.1d | **marketplace_page.py 收尾** | _marketplace_page.py (全局搜索部分) | ~10 key |
| 3.1e | **settings_page.py 收尾** | _settings_page.py | ~5 key |
| 3.1f | **CI 扫描脚本接入** | `.github/workflows/` 或 Makefile | 0 (工具) |
| 3.1g | **删除设置页冗余语言选择器** | _settings_page.py L397-409 | 0 (删除代码) |

#### 3.2 批量替换工具

```python
"""scripts/i18n_migrate_helper.py — 辅助批量提取硬编码字符串为i18n key"""
import re
from pathlib import Path

CJK_PATTERN = re.compile(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+')

def scan_file(filepath: Path):
    results = []
    for lineno, line in enumerate(filepath.open(encoding='utf-8'), 1):
        if line.strip().startswith('#') or line.strip().startswith('"""'):
            continue
        matches = CJK_PATTERN.findall(line)
        if matches and '_t(' not in line and '" not in line[:line.find(matches[0])]:
            results.append((lineno, line.rstrip(), matches))
    return results

# 对每个文件运行，输出建议的 i18n key 和替换方案
```

#### 3.3 CI 检查配置

```yaml
# .github/workflows/i18n-check.yml (或 Makefile target)
name: i18n Hardcoded String Check
on: [pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Scan hardcoded CJK strings
        run: |
          python scripts/i18n_scan.py || echo "::warning::发现新的硬编码字符串"
          # 允许 baseline 数量内的硬编码 (逐步递减)
          COUNT=$(scripts/i18n_scan.py --count-only)
          BASELINE=100  # Phase 3 完成后的目标上限
          if [ "$COUNT" -gt "$BASELINE" ]; then
            echo "::error::硬编码字符串数量 ${COUNT} 超过上限 ${BASELINE}"
            exit 1
          fi
```

---

## Section 4: 影响评估

### 4.1 可能受影响的功能

| 功能 | 影响程度 | 说明 | 缓解措施 |
|------|----------|------|----------|
| 聊天页面 (核心) | **高** | 561行代码整体迁移 | Phase 1.1e 单独作为最大测试单元；golden snapshot 对比 |
| 异步任务执行 | **高** | execute_with_agent_loop / _async_execute_task 迁移 | 保持函数签名不变；集成测试覆盖 happy path |
| Session State | **中** | 初始化逻辑移入 state.py | init_session_state() 保持相同副作用；对比初始状态 JSON |
| 侧边栏搜索 | **低** | 统一两处搜索实现 | 保留原有搜索接口签名 |
| 成果物下载 | **低** | 纯 UI 移动 | 文件路径逻辑不变 |
| Demo 模式 | **低** | Demo 数据移入 config.py | 数据结构不变 |
| Onboarding 引导 | **低** | 独立代码块，可整体移动 | 保持调用时机不变 |
| Undo/撤销 | **低** | undo_panel.py 不在 Phase 1-2 移动范围 | Phase 3 才改动 |

### 4.2 session_state 迁移路径

当前 app.py 中 session_state 的 key 列表:

```
必须保留的 key (共 22 个):
  initialized, messages, deliverables, scenario_count,
  detected_type, detected_name, onboarding_complete,
  onboarding_step, quality_feedback, flywheel_scores,
  flywheel_level, achievements, session_ctx, async_executor,
  show_skill_editor, show_marketplace, show_perf,
  show_undo_panel, show_log_panel, exec_mode,
  selected_page (★ 新增: 替代 radio 隐式存储),
  pending_prompt, last_failed_prompt
```

**迁移原则**:
- key 名称 **不改变** (保证已有浏览器会话兼容)
- 初始值 **不改变**
- `init_session_state()` 封装后行为与当前内联代码 **完全一致**

### 4.3 向后兼容性考虑

| 兼容性维度 | 策略 |
|------------|------|
| **URL 参数** | `?_stcore_health=1` 保持不变 |
| **session_state key** | 不重命名任何 key |
| **环境变量** | `OPC_WORKSPACE`, `MOKA_API_KEY` 等全部不变 |
| **文件系统** | `deliverables/`, `data/` 路径不变 |
| **Component API** | shared.py 导出的函数名不变 (只拆分内部) |
| **Page Module API** | 每个 page module 的 `render_*()` 函数签名为公开契约 |

### 4.4 各 Phase 回滚方案

| Phase | 回滚操作 | 数据风险 | 时间成本 |
|-------|----------|----------|----------|
| Phase 0 | 删除测试文件 | 无 | <1min |
| Phase 1 | `git checkout -- frontend/` 恢复到 phase0 tag | 无 (代码变更) | <1min |
| Phase 2 | `git checkout -- frontend/app.py frontend/router.py frontend/sidebar.py` | 无 | <1min |
| Phase 3 | `git checkout -- frontend/ opc_manager/i18n.py` | 无 (仅字符串替换) | <1min |

---

## Section 5: 验证标准

### 5.1 各 Phase 完成标准

#### Phase 0 完成标志

| 检查项 | 通过条件 |
|--------|----------|
| Golden Snapshot | 6个页面截图 + session_state JSON 已保存 |
| 冒烟测试 | `pytest tests/frontend/smoke_test.py` 至少 8 个测试通过 |
| 基线指标 | 记录当前启动时间、各页面加载时间 |
| Git Tag | `v0.2.0-phase0` 已打 |

#### Phase 1 完成标志

| 检查项 | 通过条件 |
|--------|----------|
| app.py 行数 | **≤ 300 行** (从 1913 行下降 ≥84%) |
| Import 无报错 | `python -c "import frontend.app"` 零错误 |
| 功能回归 | Golden Snapshot 对比: 所有页面视觉一致 |
| 无循环依赖 | `python -c` 遍历 import 所有新模块无 CircularImportError |
| F02 修复 | `read_file` 有明确定义和 import |
| F03 修复 | `_dashboard_page.py` 不再 import app.py |
| 测试通过 | 冒烟测试 + 至少 15 个新单元测试 |
| Git Tag | `v0.2.0-phase1` 已打 |

#### Phase 2 完成标志

| 检查项 | 通过条件 |
|--------|----------|
| app.py 行数 | **≤ 150 行** |
| if/elif 链 | app.py 中 **零处** `if page ==` 或 `elif page ==` |
| PageKey 覆盖 | 6 个枚举值 = 6 个 `@register_page` 装饰器 |
| 导航健壮性 | 切换语言后点击导航仍正确跳转 |
| 可扩展性 | 新增页面只需 <10 行代码 (枚举值+函数+装饰器) |
| Git Tag | `v0.2.0-phase2` 已打 |

#### Phase 3 完成标志

| 检查项 | 通过条件 |
|--------|----------|
| 硬编码 CJK | `frontend/` 目录下 **<100 行** (不含 i18n.py 本身) |
| app.py 中文 | **= 0 行** (仅 docstring/注释) |
| shared.py 中文 | **< 20 行** (仅 debug log) |
| undo_panel.py 中文 | **< 30 行** (仅 debug log) |
| CI 扫描 | PR 触发自动检查，超阈值阻断合并 |
| 三语言切换 | zh_CN → en_US → ja_JP 切换后 **零中文残留** |
| F13 修复 | 设置页冗余语言选择器已删除 |
| F10 修复 | Demo 数据走 i18n |
| Git Tag | `v0.2.0-phase3` 已打 |

### 5.2 性能基准

| 指标 | 当前基线 | Phase 1 后目标 | Phase 2 后目标 |
|------|----------|---------------|---------------|
| **首次 import 时间** | 待测量 | ≤ 当前 × 1.05 | ≤ 当前 × 1.03 |
| **页面冷启动时间** | 待测量 | 不变 | 不变 (路由分发开销 <1ms) |
| **内存占用增量** | 待测量 | ≤ 当前 × 1.0 | ≤ 当前 × 1.0 |
| **.py 文件总数** | 14 | 22 (+8) | 23 (+1) |
| **最大单文件行数** | 1913 (app.py) | **≤ 300** (app.py) | **≤ 150** (app.py) |

### 5.3 代码质量指标

| 指标 | 当前 | Phase 1 目标 | Phase 2 目标 | Phase 3 目标 |
|------|------|-------------|-------------|-------------|
| 最大文件行数 | 1913 | **≤ 300** | **≤ 150** | **≤ 150** |
| app.py 圈复杂度 | ~25 (估算) | **≤ 10** | **≤ 5** | **≤ 5** |
| 函数平均行数 | ~45 (app.py内) | **≤ 30** | **≤ 30** | **≤ 30** |
| i18n 覆盖率 | ~40% (估算) | ~40% | ~40% | **≥ 97%** |
| 硬编码 CJK 行数 | ~3422 | ~3422 | ~3422 | **<100** |
| 模块数 | 14 | 22 | 23 | 23+ |
| 循环依赖对数 | 1 (dashboard→app) | **0** | **0** | **0** |
| P0 问题数 | 3 (F01,F02,F06) | **1** (F06残留) | **1** (F06残留) | **0** |
| P1 问题数 | 9 | **≤ 4** | **≤ 2** | **≤ 1** |

### 5.4 长期演进路线

```
v0.2.0 (当前)                    v0.2.1 (Phase 1-2 完成)        v0.2.2 (远期)
┌─────────────┐                 ┌─────────────┐                ┌─────────────┐
│  app.py     │ 1913行         │  app.py     │ ≤150行         │  app.py     │ ≤100行
│  ○ 巨石     │                 │  ✓ 精简入口  │                │  ✓ 极简入口  │
│  ○ if/elif  │                 │  ✓ 注册制路由│                │  ✓ 插件化    │
│  ○ 3400处   │ 硬编码          │  ○ ~3400处  │ (Phase 3清)     │  ✓ 0处      │
│    硬编码   │                 │             │                │             │
└─────────────┘                 └─────────────┘                └─────────────┘
       │                               │                              │
       ▼                               ▼                              ▼
  14个文件混杂                     23个文件清晰分层              组件可独立发布
  3个P0问题                       0个P0, ≤2个P1                0个P0/P1/P2
  不可测试                        核心路径可测试                全面的单元+集成测试
```

---

> **文档结束**  
> 
> 下一步行动: 请审阅本文档 Section 1 的诊断结论是否准确，确认后从 **Phase 0** 开始执行。
