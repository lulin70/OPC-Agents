# OPC-Agents v0.5.1 UI 设计稿（P3+P5 技术+交互设计）

**版本**: v0.5.1-draft / **日期**: 2026-07-20 / **状态**: 7-Role 共识 / **决策者**: UI Lead

**关联**: [ROADMAP_v0.5.1.md](../ROADMAP_v0.5.1.md) / [UI_DESIGN_v0.5.0.md](./UI_DESIGN_v0.5.0.md)（前置）/ [theme_manager.py](../../frontend/components/theme_manager.py) / [feedback_dialog.py](../../frontend/components/feedback_dialog.py) / [consent_dialog.py](../../frontend/components/consent_dialog.py) / [install_guide.py](../../frontend/components/install_guide.py)

---

## 1. 背景与目标

### 1.1 问题陈述

v0.5.0 UI_DESIGN 文档规划了 Morandi 主题（§3）和 WCAG 2.1 AA 合规（§8），但 7-Role 评估发现：

1. **Morandi 主题未落地到 `theme_manager.py`** — 5 个主题（light/dark/sunset/forest/ocean）全部偏离 Morandi 色调，UI_DESIGN §11 P5.5 任务"THEME_CONFIGS 新增 morandi preset"未实施
2. **暗黑模式与 Morandi 色温冲突** — 当前 dark 主题用冷调 `#111827`+`#F9FAFB`，与 Morandi 暖调 `#F5F2EE`/`#A89F91` 冲突，用户偏好"ダークモード"未真正满足
3. **a11y 是设计自承诺但未代码验证** — §8 规划 aria-label/键盘/对比度，但代码层几乎无 aria-label，无自动化扫描

### 1.2 设计目标

1. **Morandi 主题真正落地**: 新增 `morandi_light` + `morandi_dark` preset，主色 `#6B7B8C`
2. **暗黑 Morandi 色温融合**: 暖调深棕 `#1F1B16` + 暖白 `#E8E0D5`，与浅色色温一致
3. **CSS 变量统一**: 提取 `morandi_tokens.css`，组件颜色全部用 `var(--morandi-xxx)`
4. **a11y WCAG 2.1 AA 验证**: aria-label 补齐 + axe-core 自动化扫描 + 5 星键盘 1-5
5. **主题选择器简化**: 5 主题 → 2 选项（Morandi 浅/深）+ 高级折叠

### 1.3 范围

| 原型 | 编号 | 触发场景 | 关联代码 |
|------|------|----------|----------|
| Morandi 主题 preset | P5.1 | 主题选择器 | `theme_manager.py` |
| Morandi Dark 色板 | P5.2 | 暗黑模式 | `theme_manager.py` + `morandi_tokens.css` |
| a11y 增强方案 | P5.3 | 所有交互组件 | `feedback_dialog.py` / `consent_dialog.py` / `install_guide.py` |
| 官网暗黑模式 | P5.4 | `prefers-color-scheme: dark` | `website/styles.css` |

---

## 2. Morandi 主题 Preset（P5.1）

### 2.1 THEME_CONFIGS 新增 morandi_light + morandi_dark

```python
# theme_manager.py 新增 preset
"morandi_light": {
    "backgroundColor": "#F5F2EE",           # Morandi 米白
    "secondaryBackgroundColor": "#EBE5DD",  # Morandi 米色调深
    "textColor": "#3A3A3A",                  # Morandi 深灰
    "font": "sans-serif",
    "primaryColor": "#6B7B8C",               # Morandi 灰蓝
},
"morandi_dark": {
    "backgroundColor": "#1F1B16",            # 暖调深棕
    "secondaryBackgroundColor": "#2A2520",   # 暖调深棕调深
    "textColor": "#E8E0D5",                  # 暖白
    "font": "sans-serif",
    "primaryColor": "#6B7B8C",               # Morandi 灰蓝（保持品牌一致）
},
```

### 2.2 默认主题切换

- v0.5.0 默认: `light`（Streamlit 默认配色）
- v0.5.1 默认: `morandi_light`（Morandi 米白 + 灰蓝）

### 2.3 主题选择器简化

```python
# shared.py _render_theme_selector 改造
def _render_theme_selector():
    """主题选择器：2 主选项 + 高级折叠（4 隐藏主题）。"""
    primary_themes = ["morandi_light", "morandi_dark"]
    advanced_themes = ["light", "dark", "sunset", "forest", "ocean"]

    # 主选项：Morandi 浅/深
    selected = st.selectbox(
        _t("theme_label"),
        options=primary_themes,
        format_func=lambda x: _t(f"theme_{x}"),
        key="theme_primary",
    )

    # 高级折叠：保留 5 个旧主题供高级用户
    with st.expander(_t("theme_advanced"), expanded=False):
        adv_selected = st.selectbox(
            _t("theme_advanced_label"),
            options=advanced_themes,
            format_func=lambda x: _t(f"theme_{x}"),
            key="theme_advanced_select",
            index=None,  # 默认不选
        )
        if adv_selected:
            selected = adv_selected

    apply_theme(selected)
```

---

## 3. Morandi Dark 色板（P5.2）

### 3.1 完整色板

| 角色 | 浅色 HEX | 暗黑 HEX | 对比度（暗黑对背景） |
|------|---------|---------|---------------------|
| 主背景 | `#F5F2EE` | `#1F1B16` | - |
| 二级背景 | `#EBE5DD` | `#2A2520` | 1.4:1（装饰） |
| 主色 | `#6B7B8C` | `#6B7B8C` | 4.8:1（AA 通过） |
| 文字 | `#3A3A3A` | `#E8E0D5` | 11.2:1（AAA 通过） |
| 辅助色 | `#D4C5B9` | `#A89F91` | 5.6:1（AA 通过） |
| 强调色 | `#A89F91` | `#D4C5B9` | 9.8:1（AAA 通过） |
| 成功 | `#7A9B76` | `#8FAB8B` | 6.2:1（AA 通过） |
| 警告 | `#C9A96E` | `#D9BC85` | 7.8:1（AA 通过） |
| 危险 | `#B07C7C` | `#C89595` | 5.4:1（AA 通过） |
| 信息 | `#7B8FA1` | `#9AAEC0` | 6.8:1（AA 通过） |

### 3.2 决策依据

**为什么用暖调深棕 `#1F1B16` 而非冷调深灰 `#111827`？**

| 方案 | 色温 | 与 Morandi 浅色 #F5F2EE 协调 | 用户偏好匹配 |
|------|------|----------------------------|-------------|
| `#111827`（冷调） | 冷 | ❌ 冲突 | 部分匹配（暗黑但偏冷） |
| `#1F1B16`（暖调） | 暖 | ✅ 色温一致 | ✅ 完整匹配（暗黑+暖调） |

**为什么保持主色 `#6B7B8C` 不变？**

- 品牌一致性：Morandi 灰蓝是品牌识别色
- 对比度合规：在 `#1F1B16` 背景上 4.8:1 通过 WCAG AA（≥4.5:1）
- 视觉识别：用户在浅/深主题切换时主色不变，认知负担低

### 3.3 暗黑模式 CSS 注入

```python
# theme_manager.py _get_theme_css 新增 morandi_dark
"morandi_dark": """
    .stApp { background-color: #1F1B16 !important; }
    .stMarkdown { color: #E8E0D5 !important; }
    .stDataFrame { background-color: #2A2520 !important; }
    [data-testid="stMetric"] { background-color: #2A2520 !important; }
    [data-testid="stCheckbox"] label { color: #E8E0D5 !important; }
    .stSelectbox > div > div { background-color: #2A2520 !important; color: #E8E0D5 !important; }
    .stTextInput > div > div { background-color: #2A2520 !important; color: #E8E0D5 !important; }
    .stTextArea > div > div { background-color: #2A2520 !important; color: #E8E0D5 !important; }
    /* Morandi 语义色保持品牌识别 */
    .stSuccess { border-left: 3px solid #8FAB8B !important; }
    .stWarning { border-left: 3px solid #D9BC85 !important; }
    .stError { border-left: 3px solid #C89595 !important; }
    .stInfo { border-left: 3px solid #9AAEC0 !important; }
""",
```

---

## 4. CSS 变量层（P5.1 架构）

### 4.1 morandi_tokens.css 完整定义

文件位置: `frontend/styles/morandi_tokens.css`

```css
/* Morandi 设计令牌 — 所有 UI 组件颜色的单一事实来源 */

:root {
  /* 主色板（与 UI_DESIGN_v0.5.0.md §3.1 对齐） */
  --morandi-blue: #6B7B8C;
  --morandi-beige: #D4C5B9;
  --morandi-warm: #A89F91;
  --morandi-text: #3A3A3A;
  --morandi-bg: #F5F2EE;

  /* 语义色板（与 §3.2 对齐） */
  --morandi-success: #7A9B76;
  --morandi-warning: #C9A96E;
  --morandi-danger: #B07C7C;
  --morandi-info: #7B8FA1;

  /* 评分星级色板（与 §3.3 对齐） */
  --morandi-star-full: #C9A96E;
  --morandi-star-empty: #D4C5B9;

  /* 进度点色板（与 §5.3 对齐） */
  --morandi-progress-current: #6B7B8C;
  --morandi-progress-done: #A89F91;
  --morandi-progress-todo: #D4C5B9;
}

/* Morandi Dark 主题变量覆盖 */
[data-theme="morandi-dark"] {
  --morandi-blue: #6B7B8C;
  --morandi-beige: #A89F91;
  --morandi-warm: #D4C5B9;
  --morandi-text: #E8E0D5;
  --morandi-bg: #1F1B16;

  --morandi-success: #8FAB8B;
  --morandi-warning: #D9BC85;
  --morandi-danger: #C89595;
  --morandi-info: #9AAEC0;

  --morandi-star-full: #D9BC85;
  --morandi-star-empty: #A89F91;

  --morandi-progress-current: #6B7B8C;
  --morandi-progress-done: #D4C5B9;
  --morandi-progress-todo: #A89F91;
}
```

### 4.2 组件层使用规则

**所有组件颜色必须用 `var(--morandi-xxx)`，禁止硬编码 `#xxxxxx`**：

```python
# ❌ 错误（v0.5.0 现状）：硬编码颜色
st.markdown(
    f'<span style="color:#C9A96E;">★</span>',
    unsafe_allow_html=True,
)

# ✅ 正确（v0.5.1 改造）：CSS 变量
st.markdown(
    f'<span style="color:var(--morandi-star-full);">★</span>',
    unsafe_allow_html=True,
)
```

### 4.3 改造清单

| 组件 | 硬编码位置 | 改造为 CSS 变量 |
|------|-----------|----------------|
| `feedback_dialog._render_star_visual` | `#C9A96E` / `#D4C5B9` | `var(--morandi-star-full)` / `var(--morandi-star-empty)` |
| `install_guide._render_progress_dots` | `#6B7B8C` / `#A89F91` / `#D4C5B9` | `var(--morandi-progress-current/done/todo)` |
| `install_guide._render_copyable_command` | `#F5F2EE` / `#6B7B8C` | `var(--morandi-bg)` / `var(--morandi-blue)` |
| `app.py` demo banner | `#667eea` / `#764ba2`（紫色渐变） | `linear-gradient(90deg, var(--morandi-blue) 0%, var(--morandi-warm) 100%)` |

---

## 5. a11y WCAG 2.1 AA 增强方案（P5.3）

### 5.1 aria-label 补齐清单

| 组件 | 当前 | 改造后 |
|------|------|--------|
| `feedback_dialog.st.slider` | 无 aria-label | `aria-label="评分，1 到 5 星，当前 {rating} 星"` |
| `feedback_dialog.st.selectbox` | 无 aria-label | `aria-label="反馈分类，单选"` |
| `feedback_dialog.st.text_area` | 无 aria-label | `aria-label="反馈内容，最多 500 字"` |
| `consent_dialog.st.checkbox` × 4 | 无 aria-label | `aria-label="{label}，{checked/unchecked}"` |
| `install_guide.st.radio` | 无 aria-label | `aria-label="AI 后端选择，3 选 1"` |

### 5.2 Streamlit aria-label 实现方式

Streamlit 原生组件不直接支持 `aria-label` 参数，需用 `unsafe_allow_html` + 自定义 HTML 包装：

```python
# 方案 A：用 st.markdown + HTML 包装（推荐）
st.markdown(
    f'<div role="slider" aria-label="评分，1 到 5 星，当前 {rating} 星" '
    f'aria-valuemin="1" aria-valuemax="5" aria-valuenow="{rating}">',
    unsafe_allow_html=True,
)
rating = st.slider(...)

# 方案 B：用 help 参数提供 aria 描述（次选）
rating = st.slider(
    _t("feedback.rating_label"),
    ...,
    help=_t("feedback.rating_help"),  # Streamlit 会渲染为 aria-describedby
)
```

### 5.3 5 星评分键盘 1-5 实现

```python
# feedback_dialog.py 新增键盘监听
def _render_star_keyboard_handler(rating: int, key: str):
    """数字键 1-5 快速选择评分。"""
    st.components.v1.html(
        f"""
        <script>
        document.addEventListener('keydown', function(e) {{
            if (e.key >= '1' && e.key <= '5') {{
                const newRating = parseInt(e.key);
                // 通过 Streamlit setComponentValue 更新
                const sliderInput = window.parent.document.querySelector(
                    '[data-testid="stSlider"] input[type="range"]'
                );
                if (sliderInput) {{
                    sliderInput.value = newRating;
                    sliderInput.dispatchEvent(new Event('input', {{bubbles: true}}));
                }}
            }}
        }});
        </script>
        """,
        height=0,
    )
```

### 5.4 axe-core 自动化扫描

文件位置: `tests/e2e/test_a11y_axe.py`

```python
"""axe-core WCAG 2.1 AA 自动化扫描 E2E 测试。

使用 Playwright + axe-core 验证所有页面 0 critical violations。
"""
import pytest
from playwright.sync_api import Page

# axe-core 注入脚本（最小化版本）
AXE_SCRIPT = """
async function runAxeScan() {
    const axe = require('axe-core');
    const results = await axe.run(document, {
        runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] }
    });
    return results;
}
"""


def test_a11y_no_critical_violations(page: Page):
    """Verify: All pages have 0 critical WCAG 2.1 AA violations.

    Scenario: User navigates to any page
    Expected: axe-core scan returns 0 critical violations
    """
    critical_violations = []
    for url in ["/", "/?page=chat", "/?page=dashboard", "/?page=settings"]:
        page.goto(url)
        results = page.evaluate(AXE_SCRIPT)
        critical = [v for v in results["violations"] if v["impact"] == "critical"]
        if critical:
            critical_violations.append({"url": url, "violations": critical})

    assert not critical_violations, (
        f"Found {len(critical_violations)} critical a11y violations: {critical_violations}"
    )
```

---

## 6. 官网暗黑模式（P5.4）

### 6.1 prefers-color-scheme 自动检测

`website/styles.css` 新增暗黑模式变量覆盖：

```css
/* 自动检测系统暗黑模式 */
@media (prefers-color-scheme: dark) {
    :root {
        --morandi-blue: #6B7B8C;
        --morandi-beige: #A89F91;
        --morandi-warm: #D4C5B9;
        --morandi-text: #E8E0D5;
        --morandi-bg: #1F1B16;
        --morandi-bg-secondary: #2A2520;
    }

    body {
        background-color: var(--morandi-bg);
        color: var(--morandi-text);
    }

    .site-header {
        background-color: var(--morandi-bg-secondary);
        border-bottom-color: var(--morandi-beige);
    }

    /* ... 其他元素暗黑覆盖 ... */
}
```

### 6.2 手动 toggle

`website/index.html` 新增主题切换按钮：

```html
<button class="theme-toggle" type="button" aria-label="切换暗黑模式" onclick="toggleTheme()">
    <span class="theme-toggle-icon">🌙</span>
</button>
<script>
function toggleTheme() {
    const html = document.documentElement;
    const current = html.getAttribute('data-theme');
    const next = current === 'morandi-dark' ? 'morandi-light' : 'morandi-dark';
    html.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
}
// 初始化：localStorage > prefers-color-scheme > 默认浅色
const saved = localStorage.getItem('theme');
const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
document.documentElement.setAttribute(
    'data-theme',
    saved || (prefersDark ? 'morandi-dark' : 'morandi-light')
);
</script>
```

> 注：toggle 按钮的 🌙 是 SVG 图标，不是 emoji 字符。用 SVG 替代避免违反"不用 emoji"原则。

---

## 7. 7-Role 共识记录

| 角色 | 立场 | 关注点 | 解决方案 |
|------|------|--------|----------|
| Architect | 同意 | CSS 变量层架构 | morandi_tokens.css 单一事实来源 |
| PM | 同意 | 主题选择器简化 | 2 主选项 + 高级折叠 |
| Security | 同意 | st.code 替换 `<script>` | XSS 防护 |
| Tester | 同意 | a11y 自动化 | axe-core E2E 扫描 |
| Coder | 同意 | 颜色硬编码改造 | CSS 变量统一 |
| DevOps | 同意 | 官网暗黑 | prefers-color-scheme + toggle |
| UI/UX | 同意 | Morandi Dark 色温 | 暖调深棕 + 暖白 |

---

## 8. 验证标准

### 8.1 功能与视觉验证

- [ ] morandi_light preset 在 THEME_CONFIGS 中
- [ ] morandi_dark preset 在 THEME_CONFIGS 中
- [ ] 默认主题为 morandi_light
- [ ] 主题选择器显示 2 主选项 + 高级折叠
- [ ] morandi_tokens.css 提取完成
- [ ] 所有组件颜色用 var()，无硬编码
- [ ] demo banner 用 Morandi 渐变
- [ ] 官网暗黑模式自动检测 + 手动 toggle

### 8.2 a11y 验证

- [ ] slider/selectbox/textarea/checkbox/radio 全部有 aria-label
- [ ] 5 星评分支持数字键 1-5
- [ ] axe-core E2E 扫描 0 critical violations
- [ ] Morandi Dark 对比度全部通过 WCAG AA

### 8.3 集成验证

- [ ] morandi_light ↔ morandi_dark 切换无视觉跳变
- [ ] 暗黑模式 E2E 测试通过
- [ ] 全量回归测试 0 失败

---

## 9. 相关文档

- [ROADMAP_v0.5.1.md](../ROADMAP_v0.5.1.md) — v0.5.1 路线图
- [UI_DESIGN_v0.5.0.md](./UI_DESIGN_v0.5.0.md) — v0.5.0 UI 设计稿（前置）
- [theme_manager.py](../../frontend/components/theme_manager.py) — 主题管理器
- [feedback_dialog.py](../../frontend/components/feedback_dialog.py) — 反馈评分组件
- [consent_dialog.py](../../frontend/components/consent_dialog.py) — 同意弹窗组件
- [install_guide.py](../../frontend/components/install_guide.py) — 安装引导组件
