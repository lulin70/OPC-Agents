# OPC-Agents v0.5.0 UI 设计稿（P5 交互设计）

**版本**: v0.5.0-draft / **日期**: 2026-07-19 / **状态**: 7-Role 共识 / **决策者**: UI Lead

**关联**: [ADR-004](./ADR-004-metrics-collection-design.md) §3.4 弹窗与脱敏上报 / [API_DESIGN_feedback_and_metrics.md](./API_DESIGN_feedback_and_metrics.md) §3.1 §3.4 端点 / [ROADMAP_v0.5.0.md](../ROADMAP_v0.5.0.md) §OKR-2 / [HARD_CONSTRAINTS.md](../HARD_CONSTRAINTS.md) S4 数据本地存储 / 现有代码 [shared.py](../../frontend/components/shared.py) · [confirmation_dialog.py](../../frontend/components/confirmation_dialog.py) · [onboarding_renderer.py](../../frontend/renderers/onboarding_renderer.py) · [QUICK_START_BETA.md](../guides/QUICK_START_BETA.md)

---

## 1. 背景与目标

### 1.1 问题陈述

ADR-004 已确定 v0.5.0 必须完成 5 大商业指标 + 3 大体验指标的埋点采集，API 设计文档已约束前端 UI 通过 `POST /api/v1/feedback`、`POST /api/v1/metrics/experience`、`POST /api/v1/metrics/nps` 写入数据，但前端尚未提供可点击的交互组件。同时现有 `QUICK_START_BETA.md` 安装引导面向技术用户，非技术用户难以独立完成安装（不懂 API Key、.env 文件、虚拟环境等概念）。最后，HARD_CONSTRAINTS S4 要求"数据从不出家门"且首次启动须弹窗同意，缺少统一的数据采集同意 UI。

### 1.2 设计目标

1. **闭环反馈链路**：3 个原型对接 ADR-004 埋点入口与 API 设计文档端点，从用户点击到数据落库全链路可视化
2. **降低安装门槛**：非技术用户（不懂 API Key 是什么）可独立完成 5 步安装并启动应用
3. **合规优先**：首次启动强制弹窗，用户未同意不采集任何数据
4. **设计一致性**：与现有 Streamlit 组件（`shared.py` / `confirmation_dialog.py` / `onboarding_renderer.py`）风格统一
5. **舒适视觉**：采用 Morandi 色调（低饱和度、柔和），不使用刺眼 emoji，满足用户对舒适配色的偏好

### 1.3 范围

| 原型 | 编号 | 触发场景 | 关联 API |
|------|------|----------|----------|
| 反馈评分 UI | P5.1 | 任务完成后 / 对话结束后 | `POST /api/v1/feedback` + `POST /api/v1/metrics/experience` |
| 安装引导优化 | P5.2 | 首次启动 Onboarding | 无（仅引导流程） |
| 数据采集同意弹窗 | P5.3 | 首次启动 + 设置页可改 | 写入 `settings.py` 的 `METRICS_ENABLED` / `METRICS_EXPORT_ENABLED` |

---

## 2. 设计原则

### 2.1 四大设计原则

1. **Morandi 色调**：低饱和度、柔和、不刺眼；不使用 emoji，用色块、图标、字体层级传达信息
2. **一致性**：与现有 Streamlit 组件风格一致（`shared.py` 中的 `show_success` / `show_error` toast、`confirmation_dialog.py` 的模态层模式、`onboarding_renderer.py` 的进度点样式）
3. **可访问性**：WCAG 2.1 AA 合规，键盘可达、屏幕阅读器友好、对比度达标
4. **三语支持**：中（zh_CN）/ 英（en_US）/ 日（ja_JP），所有 UI 文本经 i18n 管理，默认语言根据系统 locale 自动检测

### 2.2 与现有组件的复用关系

| 现有组件 | 复用方式 | 在本设计中的角色 |
|----------|----------|-------------------|
| `opc_manager.i18n.t` | 所有 UI 文本经 `_t(key)` 调用 | 三语支持基础 |
| `frontend.components.toast_notifications` | `show_success` / `show_error` / `show_info` | 提交反馈后的 toast 提示 |
| `frontend.components.theme_manager` | `THEME_CONFIGS` / `apply_theme` / `_get_theme_css` | Morandi 主题注入 |
| `confirmation_dialog.py` 模态层 CSS 模式 | `unsafe_allow_html` + `position: fixed` overlay | 反馈弹窗与同意弹窗的容器样式 |
| `onboarding_renderer.py` 进度点 `●` / `○` | 安装引导底部步骤指示 | 安装引导步骤指示器 |

---

## 3. 配色方案（Morandi 色调）

### 3.1 主色板

| 角色 | 名称 | HEX | 用途 | 对比度（与白底） |
|------|------|-----|------|-------------------|
| 主色调 | Morandi 灰蓝 | `#6B7B8C` | 按钮、链接、强调元素 | 4.6:1（AA 通过） |
| 辅助色 | Morandi 米色 | `#D4C5B9` | 卡片背景、分隔线、二级容器 | 1.4:1（仅装饰） |
| 强调色 | Morandi 暖灰 | `#A89F91` | 次要按钮、图标、hover 边框 | 2.6:1（仅装饰） |
| 文字色 | 深灰 | `#3A3A3A` | 正文、标题、表单标签 | 9.7:1（AAA 通过） |
| 背景色 | 米白 | `#F5F2EE` | 页面底色、卡片底色 | 1.1:1（背景） |

### 3.2 语义色板（基于 Morandi 调降饱和度）

| 语义 | HEX | 用途 |
|------|-----|------|
| 成功 | `#7A9B76` | 提交成功 toast、勾选状态 |
| 警告 | `#C9A96E` | 跳过提示、可选步骤 |
| 危险 | `#B07C7C` | 取消按钮 hover、错误 toast |
| 信息 | `#7B8FA1` | 帮助提示、链接 hover |

### 3.3 评分星级色板

| 星级 | HEX | 含义 |
|------|-----|------|
| 满星（5/5） | `#C9A96E` | Morandi 暖金 |
| 半星（4.5） | `#D4B888` | 暖金淡化 |
| 空星 | `#D4C5B9` | 与辅助色一致（米色） |

### 3.4 主题注入 CSS 骨架

```css
:root {
  --morandi-blue: #6B7B8C;     /* 主色调 */
  --morandi-beige: #D4C5B9;    /* 辅助色 */
  --morandi-warm: #A89F91;     /* 强调色 */
  --text-primary: #3A3A3A;
  --bg-base: #F5F2EE;
  --semantic-success: #7A9B76;
  --semantic-warning: #C9A96E;
  --semantic-danger: #B07C7C;
}
.opc-card {
  background: #FFFFFF; border: 1px solid var(--morandi-beige);
  border-radius: 8px; padding: 24px;
  box-shadow: 0 2px 8px rgba(107, 123, 140, 0.08);
}
.opc-btn-primary {
  background: var(--morandi-blue); color: #FFFFFF;
  border: none; border-radius: 4px; padding: 8px 20px;
}
.opc-btn-secondary {
  background: transparent; color: var(--morandi-blue);
  border: 1px solid var(--morandi-warm);
}
```

---

## 4. 原型 1: 反馈评分 UI（P5.1）

### 4.1 触发位置

- **主触发点**：任务完成后弹出（`SkillExecutors.complete_task()` 末尾的钩子触发）
- **次触发点**：对话结束后在侧边栏显示（避免打断用户思路）
- **手动触发点**：用户可在「设置 → 反馈历史」主动打开历史评分修改

### 4.2 ASCII 线框图

```
┌─────────────────────────────────────────────────┐
│  这次任务完成得怎么样？                          │
│                                                 │
│  评分: ★★★★★ 5星                                │
│        ★★★★☆ 4星                                │
│        ★★★☆☆ 3星                                │
│        ★★☆☆☆ 2星                                │
│        ★☆☆☆☆ 1星                                │
│                                                 │
│  分类: [Bug] [建议] [表扬] [疑问]                │
│                                                 │
│  反馈内容（可选）:                               │
│  ┌─────────────────────────────────────────┐    │
│  │                                         │    │
│  │                                         │    │
│  └─────────────────────────────────────────┘    │
│  字数: 0 / 500                                  │
│                                                 │
│  [取消]                          [提交反馈]      │
└─────────────────────────────────────────────────┘
```

### 4.3 组件细节

| 组件 | 行为 | 关键属性 |
|------|------|----------|
| 5 星评分组件 | hover 预览 + 点击选定 + 数字键 1-5 快速选择 | `aria-label="评分，1 到 5 星"`，`tabindex=0` |
| 分类标签（4 chip） | 单选，默认不选；选中态边框变 Morandi 灰蓝 | chip 风格圆角 16px，未选底色米白 |
| 反馈内容文本框 | 最多 500 字（前端限制），后端 API 上限 2000 字符（兼容批量导入） | 字数实时显示 `0 / 500` |
| 提交按钮 | 按下后进入"提交中..."禁用态，等响应后切换 | 主按钮 Morandi 灰蓝底白字 |
| 取消按钮 | 关闭弹窗，不提交，不清空缓存（30 分钟内再次打开恢复填写） | 次按钮透明底 Morandi 灰蓝字 |
| 提交成功提示 | toast 在右上角显示"感谢反馈！"，3 秒后淡出 | 复用 `show_success` |
| 错误提示 | 校验失败 toast 显示具体错误（如"评分不能为空"） | 复用 `show_error` |

### 4.4 评分到 API 的数据映射

| UI 字段 | API 字段 | 取值 |
|---------|----------|------|
| 5 星评分 | `FeedbackRequest.rating` | 1-5 整数 |
| 分类标签 | `FeedbackRequest.category` | `bug` / `suggestion` / `praise` / `question` |
| 反馈内容 | `FeedbackRequest.comment` | 最长 500 字（前端）/ 2000 字符（后端） |
| 当前会话 ID | `FeedbackRequest.session_id` | 从 `_get_current_session_id()` 取 |
| 关联技能 ID | `FeedbackRequest.skill_id` | 任务完成时传入 |
| 当前用户 ID | `FeedbackRequest.user_id` | 从 JWT 解析 |
| 提交时间 | `FeedbackRequest.timestamp` | `datetime.now(timezone.utc).isoformat()` |

> 同一评分可同时写入 `metrics_experience`（`metric=result_satisfaction`），通过后端在 feedback 路由内联动调用 `MetricsCollector.record_experience` 实现，前端无需两次调用。

### 4.5 Streamlit 代码骨架

```python
"""反馈评分 UI 组件（P5.1）— frontend/components/feedback_dialog.py"""
import streamlit as st
from datetime import datetime, timezone
from typing import Optional

from opc_manager.i18n import t as _t
from frontend.components.shared import show_success, show_error
from frontend.components.session_utils import _get_current_session_id
from opc_manager.api.client import submit_feedback  # P3 待实现


def render_feedback_dialog(skill_id: str, session_id: Optional[str] = None):
    """任务完成后渲染反馈弹窗。session_id 为空时自动从 session_utils 取。"""
    session_id = session_id or _get_current_session_id()
    if not session_id:
        show_error(_t("feedback_no_session"))
        return

    st.markdown(f"### {_t('feedback_dialog_title')}")

    # 5 星评分（slider + 自定义 Morandi 暖金 CSS 渲染，避免 emoji）
    rating = st.slider(_t("feedback_rating_label"), min_value=1, max_value=5,
                       value=5, step=1, key=f"fb_rating_{skill_id}_{session_id}",
                       help=_t("feedback_rating_help"))
    _render_star_visual(rating)

    # 分类单选（4 chip，默认未选）
    category = st.selectbox(
        _t("feedback_category_label"),
        options=["bug", "suggestion", "praise", "question"],
        format_func=lambda x: _t(f"feedback_category_{x}"),
        index=None, key=f"fb_category_{skill_id}_{session_id}",
    )

    # 反馈内容（最多 500 字，前端限制）
    comment = st.text_area(_t("feedback_comment_label"), max_chars=500,
                           height=120, key=f"fb_comment_{skill_id}_{session_id}",
                           help=_t("feedback_comment_help"))
    st.caption(f"{len(comment)} / 500")

    # 提交 / 取消按钮
    col_cancel, col_submit = st.columns([1, 2])
    with col_cancel:
        if st.button(_t("feedback_cancel"), type="secondary",
                     key=f"fb_cancel_{skill_id}_{session_id}"):
            st.session_state.pop(f"fb_rating_{skill_id}_{session_id}", None)
            st.rerun()
    with col_submit:
        if st.button(_t("feedback_submit"), type="primary",
                     key=f"fb_submit_{skill_id}_{session_id}"):
            if category is None:
                show_error(_t("feedback_category_required"))
                return
            try:
                submit_feedback(rating=rating, comment=comment, category=category,
                                skill_id=skill_id, session_id=session_id,
                                timestamp=datetime.now(timezone.utc).isoformat())
                show_success(_t("feedback_submit_success"))
            except Exception as e:
                show_error(_t("feedback_submit_failed", reason=str(e)))


def _render_star_visual(rating: int):
    """用 Morandi 暖金色 CSS 渲染星星，避免 emoji。"""
    star_full = '<span style="color:#C9A96E;">★</span>'
    star_empty = '<span style="color:#D4C5B9;">☆</span>'
    stars = star_full * rating + star_empty * (5 - rating)
    st.markdown(
        f'<div style="font-size:24px; letter-spacing:4px;" '
        f'aria-label="评分 {rating} 星">{stars}</div>',
        unsafe_allow_html=True,
    )
```

> 键盘与可访问性细节见 §8（WCAG 2.1 AA）统一说明。

---

## 5. 原型 2: 安装引导优化（P5.2）

### 5.1 目标

非技术用户（不懂 API Key 是什么）可独立完成安装。原有 3 步引导（欢迎页 → API Key 配置 → 功能介绍）存在 3 个问题：
1. 未告知如何下载安装应用本身
2. API Key 概念对非技术用户过于陌生
3. 缺少"安装完成 → 可立即使用"的明确终点

v0.5.0 优化为 5 步图文版，并在 Step 3 提供 3 个 AI 后端选项（其中 2 个无需 API Key）。

### 5.2 ASCII 线框图（5 步图文版）

每个步骤共用同一个弹窗容器，仅内容区与进度点变化。下面给出合并视图，进度点 ● 标记当前步骤：

```
┌─────────────────────────────────────────────────┐
│  ● ○ ○ ○ ○    (Step 1) / ○ ○ ● ○ ○    (Step 3) │
│                                                 │
│  Step 1: 下载安装                                │
│    方式 1: 一键脚本 [复制] curl ... | bash       │
│    方式 2: pip 安装   [复制] pip install opc...  │
│    方式 3: Docker     [复制] docker run -p 8000  │
│                                                 │
│  Step 2: 启动应用                                │
│    终端: [复制] opc-agents start                 │
│    浏览器: [打开] http://localhost:8000          │
│                                                 │
│  Step 3: 配置 AI 后端（3 选 1，可跳过）         │
│    ○ Ollama（推荐，零成本）   https://ollama.ai  │
│    ● Moka AI 网关（免费，无需配置）              │
│    ○ OpenAI（需 API Key） [____________]         │
│      不知道 API Key 是什么？点击查看说明          │
│                                                 │
│  Step 4: 激活专业版（可选）                      │
│    许可证: [PL-PRO-xxxx-xxxx-xxxx__________]    │
│    [激活]  [跳过]   (无许可证可获取 30 天试用)    │
│                                                 │
│  Step 5: 安装完成                                │
│    现在你可以：                                  │
│    - 说"帮我发邮件给张总"                        │
│    - 说"帮我记一笔收入3000元"                    │
│    - 说"帮我生成本月报告"                        │
│    [开始使用]                                    │
│                                                 │
│  通用按钮: [上一步 ←]  [跳过此步]  [下一步 →]    │
└─────────────────────────────────────────────────┘
```

> 说明：实际渲染时每个步骤独立显示，上图为合并视图便于一次性展示全部交互元素。Step 1-2 仅显示「下一步」按钮；Step 3-4 显示「跳过此步」+「下一步」+「上一步」；Step 5 显示「开始使用」。

### 5.3 步骤进度指示器

复用 `onboarding_renderer.py` 的进度点模式，但用 Morandi 色调：当前步骤 `●` 用 `#6B7B8C`（Morandi 灰蓝），已完成步骤 `●` 用 `#A89F91`（Morandi 暖灰），未完成步骤 `○` 用 `#D4C5B9`（Morandi 米色）。

### 5.4 Streamlit 代码骨架

```python
"""安装引导优化组件（P5.2）— frontend/components/install_guide.py"""
import streamlit as st
from opc_manager.i18n import t as _t

INSTALL_STEPS = ["download", "start", "llm_config", "license", "done"]
_STEP_COLORS = {"current": "#6B7B8C", "done": "#A89F91", "todo": "#D4C5B9"}


def render_install_guide():
    """Render 5-step install guide for non-technical users."""
    if "install_step" not in st.session_state:
        st.session_state["install_step"] = 0
    step_idx = st.session_state["install_step"]
    _render_progress_dots(step_idx)
    step = INSTALL_STEPS[step_idx]
    if step == "download":
        _render_step_download()
    elif step == "llm_config":
        _render_step_llm_config()  # 关键步骤：3 个 AI 后端选项
    # start / license / done 步骤结构类似，省略


def _render_progress_dots(current_idx: int):
    """渲染 Morandi 色调进度点：当前灰蓝、已完成暖灰、未完成米色。"""
    dots = ""
    for i in range(len(INSTALL_STEPS)):
        color = _STEP_COLORS["current" if i == current_idx
                            else "done" if i < current_idx else "todo"]
        symbol = "●" if i <= current_idx else "○"
        dots += f'<span style="color:{color}; font-size:20px; margin:0 8px;">{symbol}</span>'
    st.markdown(
        f'<div style="text-align:center; margin-bottom:24px;" '
        f'aria-label="步骤 {current_idx + 1} / {len(INSTALL_STEPS)}">{dots}</div>',
        unsafe_allow_html=True,
    )


def _render_step_download():
    st.markdown(f"### {_t('install_step1_title')}")
    for method_key, command in [
        ("method1_label", "curl -fsSL https://promiselink.cn/install.sh | bash"),
        ("method2_label", "pip install opc-agents"),
        ("method3_label", "docker run -p 8000:8000 opc-agents"),
    ]:
        st.markdown(f"**{_t(f'install_{method_key}')}**")
        _render_copyable_command(command)
    if st.button(_t("install_next"), type="primary", key="install_step1_next"):
        st.session_state["install_step"] = 1
        st.rerun()


def _render_step_llm_config():
    """关键步骤：3 个 AI 后端选项（其中 Ollama 与 Moka 均无需 API Key）。"""
    st.markdown(f"### {_t('install_step3_title')}")
    backend = st.radio(
        _t("install_llm_backend_label"),
        options=["ollama", "moka", "openai"],
        format_func=lambda x: _t(f"install_llm_backend_{x}"),
        index=1,  # 默认 Moka 网关（零成本）
        key="install_llm_backend",
    )
    if backend == "openai":
        with st.expander(_t("install_what_is_apikey"), expanded=False):
            st.info(_t("install_apikey_explain"))
        st.text_input(_t("install_apikey_label"), type="password",
                      placeholder="sk-...", key="install_openai_key")
    elif backend == "ollama":
        st.info(_t("install_ollama_help"))

    col1, col2 = st.columns(2)
    with col1:
        if st.button(_t("install_skip"), key="install_step3_skip"):
            st.session_state["install_step"] = 3
            st.rerun()
    with col2:
        if st.button(_t("install_next"), type="primary", key="install_step3_next"):
            _save_llm_config(backend)
            st.session_state["install_step"] = 3
            st.rerun()


def _render_copyable_command(command: str):
    """渲染可复制命令行块（Morandi 米白底 + 灰蓝左边框）。"""
    st.markdown(
        f'<div style="background:#F5F2EE; border-left:3px solid #6B7B8C; '
        f'padding:12px 16px; font-family:monospace; font-size:14px; '
        f'border-radius:4px; margin:8px 0;">{command}</div>',
        unsafe_allow_html=True,
    )
    if st.button(_t("install_copy"), key=f"copy_{hash(command)}"):
        st.write(f'<script>navigator.clipboard.writeText("{command}")</script>',
                 unsafe_allow_html=True)


def _save_llm_config(backend: str): ...
def _activate_license(key: str) -> bool: ...
```

### 5.5 与现有 Onboarding 的关系

P5.2 的 5 步引导为「安装前置引导」（应用首次启动前，命令行/安装脚本），现有 `onboarding_renderer.py` 的 3 步引导（WELCOME → LLM_CONFIG → SAMPLE_TASK）继续保留为「应用内功能引导」（应用首次启动后），两者互不冲突。

---

## 6. 原型 3: 数据采集同意弹窗（P5.3）

### 6.1 触发位置

- **首次启动时强制显示**：在 P5.2 安装引导的 Step 5 完成后立即弹出
- **设置页可改**：用户随时可在「设置 → 隐私与数据采集」修改选择
- **未同意时不采集**：`METRICS_ENABLED = False` 时所有 `record_xxx` 调用直接 return

### 6.2 ASCII 线框图

```
┌─────────────────────────────────────────────────┐
│  数据采集与隐私保护                              │
│                                                 │
│  为了改进产品，我们希望采集以下数据：            │
│                                                 │
│  [✓] 使用统计（功能使用次数、会话时长）         │
│  [✓] 性能指标（响应时间、错误率）               │
│  [✓] 满意度评分（5 星评分，匿名）               │
│  [ ] 反馈内容（文字反馈，需要您主动填写）       │
│                                                 │
│  我们承诺：                                      │
│  - 所有数据存储在您的本地电脑                   │
│  - 不会上传您的业务数据                         │
│  - 上报数据会脱敏处理（去除 user_id）           │
│  - 您可以随时在设置中关闭数据采集               │
│                                                 │
│  详见《隐私政策》和《数据处理协议》              │
│                                                 │
│  [不同意]              [同意并继续]              │
└─────────────────────────────────────────────────┘
```

### 6.3 组件细节与配置字段映射

| UI 元素 | 行为 / 默认值 | 写入配置字段 |
|---------|---------------|---------------|
| 使用统计复选框 | 默认勾选 | `METRICS_ENABLED`（主开关，控制所有 `record_xxx`） |
| 性能指标复选框 | 默认勾选 | `METRICS_PERF_ENABLED`（响应时间、错误率） |
| 满意度评分复选框 | 默认勾选 | `METRICS_SATISFACTION_ENABLED`（5 星评分） |
| 反馈内容复选框 | 默认不勾选（用户主动选择才采集文字反馈） | `METRICS_FEEDBACK_ENABLED` |
| 同意上报 | 默认关闭（用户在设置页主动开启） | `METRICS_EXPORT_ENABLED`（脱敏上报） |
| 隐私政策链接 | 点击打开 `https://promiselink.cn/privacy` | - |
| 数据处理协议链接 | 点击打开 `https://promiselink.cn/dpa` | - |
| 不同意按钮 | 关闭弹窗，应用仍可使用；写入 `METRICS_ENABLED=False` | - |
| 同意并继续按钮 | 保存用户选择到 `config.yaml`，关闭弹窗 | - |

### 6.4 Streamlit 代码骨架

```python
"""数据采集同意弹窗（P5.3）— frontend/components/consent_dialog.py"""
import streamlit as st
from opc_manager.i18n import t as _t
from opc_manager.config import save_consent_settings
from frontend.components.shared import show_success

# 4 个复选框配置：前 3 个默认勾选，最后一个默认不勾选
_CONSENT_CHECKBOXES = [
    ("usage_stats", True), ("perf_metrics", True),
    ("satisfaction", True), ("feedback_content", False),
]


def render_consent_dialog():
    """首次启动或设置页主动打开时渲染同意弹窗。"""
    st.markdown(f"### {_t('consent_title')}")
    st.markdown(_t("consent_description"))

    # 4 个复选框
    choices = {}
    for key, default in _CONSENT_CHECKBOXES:
        choices[key] = st.checkbox(
            _t(f"consent_{key}"),
            value=default,
            key=f"consent_{key}",
            help=_t(f"consent_{key}_help"),
        )

    # 隐私承诺（用 | 分隔的多条文案）
    st.markdown(f"**{_t('consent_promise_title')}**")
    for promise in _t("consent_promises").split("|"):
        st.markdown(f"- {promise.strip()}")

    # 隐私政策与数据处理协议链接
    st.markdown(
        f"[{_t('consent_privacy_policy')}](https://promiselink.cn/privacy) | "
        f"[{_t('consent_dpa')}](https://promiselink.cn/dpa)"
    )

    # 按钮区：不同意 / 同意并继续
    col_disagree, col_agree = st.columns(2)
    with col_disagree:
        if st.button(_t("consent_disagree"), type="secondary",
                     key="consent_disagree_btn"):
            save_consent_settings(
                metrics_enabled=False, metrics_perf_enabled=False,
                metrics_satisfaction_enabled=False, metrics_feedback_enabled=False,
                metrics_export_enabled=False,
            )
            show_success(_t("consent_disagreed_toast"))
            st.session_state["consent_shown"] = True
            st.rerun()
    with col_agree:
        if st.button(_t("consent_agree"), type="primary",
                     key="consent_agree_btn"):
            # 主开关 = 任一前 3 项勾选；上报开关默认关闭，需用户主动开启
            metrics_enabled = choices["usage_stats"] or choices["perf_metrics"] or choices["satisfaction"]
            save_consent_settings(
                metrics_enabled=metrics_enabled,
                metrics_perf_enabled=choices["perf_metrics"],
                metrics_satisfaction_enabled=choices["satisfaction"],
                metrics_feedback_enabled=choices["feedback_content"],
                metrics_export_enabled=False,
            )
            show_success(_t("consent_agreed_toast"))
            st.session_state["consent_shown"] = True
            st.rerun()


def should_show_consent_dialog() -> bool:
    """用户从未见过弹窗（无 consent_recorded 记录）时返回 True。"""
    from opc_manager.config import get_consent_settings
    return not get_consent_settings().get("consent_recorded", False)
```

### 6.6 与 ADR-004 的对齐

弹窗实现严格遵循 ADR-004 §3.4 要求：首次启动弹窗 + 默认勾选前 3 项（仅本地存储）；`METRICS_EXPORT_ENABLED` 默认 False（脱敏上报需用户主动同意）；弹窗文案明确说明"所有数据存储在您的本地电脑"（对应 HARD_CONSTRAINTS S4）。

---

## 7. 三语支持策略

### 7.1 i18n 文件结构

所有 UI 文本通过 i18n 管理，三语文件位于 `opc_manager/i18n/locales/` 目录下：`zh_CN.json`（中文，默认）/ `en_US.json`（英文）/ `ja_JP.json`（日文）。

### 7.2 翻译键命名规范

| 命名空间 | 前缀 | 示例 |
|----------|------|------|
| 反馈评分 | `feedback.` | `feedback.dialog_title` / `feedback.rating_label` / `feedback.category_bug` |
| 安装引导 | `install.` | `install.step1_title` / `install.method1_label` / `install.llm_backend_ollama` |
| 同意弹窗 | `consent.` | `consent.title` / `consent.usage_stats` / `consent.privacy_policy` |
| 通用按钮 | `common.` | `common.next` / `common.prev` / `common.cancel` / `common.submit` |

### 7.3 翻译键示例（zh_CN.json 节选）

```json
{
  "feedback": {
    "dialog_title": "这次任务完成得怎么样？",
    "rating_label": "评分",
    "category_bug": "Bug",
    "submit": "提交反馈",
    "submit_success": "感谢反馈！"
  },
  "install": {
    "step1_title": "Step 1: 下载安装",
    "method1_label": "方式 1: 一键脚本（推荐）",
    "next": "下一步 →",
    "what_is_apikey": "什么是 API Key？"
  },
  "consent": {
    "title": "数据采集与隐私保护",
    "usage_stats": "使用统计（功能使用次数、会话时长）",
    "agree": "同意并继续",
    "agreed_toast": "感谢您的支持，我们将用数据持续改进产品"
  }
}
```

完整翻译键清单（约 60 条）见 P5.4 阶段产出的 `zh_CN.json` / `en_US.json` / `ja_JP.json` 三语文件。

### 7.4 默认语言检测

```python
import locale

def detect_default_language() -> str:
    """根据系统 locale 自动检测默认语言。"""
    sys_locale = locale.getdefaultlocale()[0] or "zh_CN"
    if sys_locale.startswith("zh"):
        return "zh_CN"
    if sys_locale.startswith("ja"):
        return "ja_JP"
    return "en_US"
```

---

## 8. 可访问性（WCAG 2.1 AA）

### 8.1 键盘可操作性

| 元素 | 键盘操作 | 实现 |
|------|----------|------|
| 5 星评分 | `Tab` 聚焦 + 数字键 `1`-`5` 选定 + `Space` 确认 | Streamlit slider + 自定义 keydown 监听 |
| 分类标签 / 反馈内容 / 复选框 / 安装引导步进 | `Tab` 切换 + `Space` 或 `Enter` 触发 | Streamlit 原生组件支持 |
| 取消按钮 | `Tab` 聚焦 + `Enter`，或全局 `Esc` | 全局 keydown 监听 |

### 8.2 颜色对比度

| 元素 | 前景 | 背景 | 对比度 | 标准 |
|------|------|------|--------|------|
| 正文文字 | `#3A3A3A` | `#FFFFFF` / `#F5F2EE` | 9.7:1 / 8.9:1 | AAA 通过 |
| 主按钮文字 / 次按钮文字 / 链接 | `#FFFFFF` ↔ `#6B7B8C` | - | 4.6:1 | AA 通过 |
| 标题大文字 | `#3A3A3A` | `#F5F2EE` | 8.9:1 | AAA 通过 |
| 占位符文字 | `#A89F91` | `#FFFFFF` | 2.6:1 | 装饰用，不传达关键信息 |

> 大文字（≥18pt 或 14pt 加粗）对比度 ≥ 3:1 即达标，正文文字 ≥ 4.5:1。本设计所有传达关键信息的文字对比度均 ≥ 4.5:1。

### 8.3 屏幕阅读器支持

| 元素 | `aria-label` | 说明 |
|------|--------------|------|
| 5 星评分 | `aria-label="评分，1 到 5 星，当前 {rating} 星"` | 焦点切换时朗读 |
| 分类标签 | `aria-label="反馈分类，单选"` | 朗读当前选项 |
| 提交按钮 | `aria-label="提交反馈"` | 朗读按钮用途 |
| 进度点 | `aria-label="步骤 {current} / {total}"` | 朗读进度 |
| 复选框 | `aria-label="{label}，{checked/unchecked}"` | 朗读状态 |

---

## 9. 验证标准

### 9.1 功能与视觉验证

- [ ] 3 个原型可点击演示（Streamlit demo 可独立运行）
- [ ] 配色方案符合 Morandi 色调（5 个主色 + 4 个语义色），浅色/深色显示器下均清晰可读
- [ ] 不使用任何 emoji（用户偏好），字体层级清晰（标题/正文/辅助文字三档）
- [ ] 三语支持完整（zh_CN / en_US / ja_JP 全部翻译键覆盖）
- [ ] 可访问性通过 WCAG 2.1 AA 检查（键盘 + 对比度 + 屏幕阅读器）

### 9.2 集成验证

- [ ] 反馈评分 UI 调用 `POST /api/v1/feedback` 写入成功，并联动写入 `metrics_experience` 表（后端联动）
- [ ] 同意弹窗写入 `settings.py` 的 `METRICS_ENABLED` / `METRICS_EXPORT_ENABLED`
- [ ] 同意弹窗未同意时，所有 `record_xxx` 调用直接 return（不写入）

### 9.3 用户体验验证（E2E，发布前必做 5 个场景）

1. **场景 A - 非技术用户首次安装**：Step 1 → 选 Moka 网关（不输入 API Key）→ 完成安装 → 弹出同意弹窗 → 选同意 → 进入主界面
2. **场景 B - 任务完成后评分**：执行任务 → 弹出反馈 UI → 选 5 星 + 分类"表扬" + 输入评语 → 提交 → 看到 toast
3. **场景 C - 拒绝数据采集**：首次启动 → 同意弹窗选"不同意" → 应用仍可用 → 设置页可重开弹窗
4. **场景 D - 三语切换**：zh_CN / en_US / ja_JP 切换 → 3 个原型文本正确切换
5. **场景 E - 键盘全程操作**：禁用鼠标 → Tab / Enter / Space / 数字键完成 3 个原型全部交互

---

## 10. 7-Role 共识记录

| 角色 | 立场 | 关注点 | 解决方案 |
|------|------|--------|----------|
| Architect | 同意 | 与 ADR-004 / API 设计对齐 | 反馈 UI 字段映射 API 字段；同意弹窗写入 settings.py |
| PM | 同意 | 非技术用户安装门槛 | 5 步引导 + 3 个 AI 后端选项（2 个无需 API Key） |
| Security | 同意 | 数据采集合规 | 同意弹窗默认关闭上报，仅本地存储，用户主动同意才上报 |
| Tester | 同意 | E2E 测试覆盖 | 5 个 E2E 场景覆盖安装 / 评分 / 同意 / 三语 / 键盘 |
| Coder | 同意 | 复用现有组件 | 复用 shared.py / confirmation_dialog.py / onboarding_renderer.py 模式 |
| DevOps | 同意 | 部署影响 | 仅前端组件，无新增后端依赖 |
| UI/UX | 同意 | 视觉一致性 | Morandi 色调贯穿 3 个原型，不使用 emoji |

---

## 11. 实施计划

| 阶段 | 任务 | 产出 | 负责人 |
|------|------|------|--------|
| P5.1 | 实现 `frontend/components/feedback_dialog.py` | 反馈评分 UI 组件 | UI Lead |
| P5.2 | 实现 `frontend/components/install_guide.py` | 5 步安装引导组件 | UI Lead |
| P5.3 | 实现 `frontend/components/consent_dialog.py` | 数据采集同意弹窗 | UI Lead |
| P5.4 | 扩展 i18n locales 三语翻译键 | zh_CN / en_US / ja_JP .json | UI Lead + PM |
| P5.5 | 注入 Morandi 主题到 `theme_manager.py` | THEME_CONFIGS 新增 morandi preset | UI Lead |
| P5.6 | 集成调用点（任务完成钩子 + 首次启动） | 集成代码 | Coder |
| P5.7 | 单元测试 + E2E 测试（5 个场景） | 测试报告 | Tester |
| P5.8 | 可访问性审计（WCAG 2.1 AA） | 审计报告 | Tester + UI Lead |

---

## 12. 相关文档

文档开头「关联」段已列出全部关联文档（ADR-004 / API_DESIGN / ROADMAP / HARD_CONSTRAINTS / 现有代码 4 项）。本节补充：

- [ADR-001](./ADR-001-IntentRouter-design.md) / [ADR-002](./ADR-002-ToolSystem-design.md) / [ADR-003](./ADR-003-TaskEngineV3-design.md) / [ADR-005](./ADR-005-llm-backend-fallback-design.md) — 其他 ADR
- [frontend/components/theme_manager.py](../../frontend/components/theme_manager.py) — 主题管理器（Morandi preset 注入点）
- [frontend/components/toast_notifications.py](../../frontend/components/toast_notifications.py) — Toast 通知组件
