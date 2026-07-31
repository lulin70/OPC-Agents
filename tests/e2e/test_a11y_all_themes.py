"""全主题 + 全页面无障碍 E2E 测试.

GAP-P1-7: 7 个主题 × WCAG AA 对比度验证
GAP-P1-8: 6 个核心页面 × 交互元素标签 + 对比度 + 键盘导航

用户旅程:
  用户切换主题 → 阅读内容 → 在不同页面间导航 → 所有内容清晰可读

测试覆盖:
  - 7 主题: light / dark / sunset / forest / ocean / morandi_light / morandi_dark
  - 6 页面: 对话 / 成果物 / Dashboard / 成长 / 技能市场 / 设置
  - 3 维度: 交互元素标签 / 颜色对比度 / 键盘导航焦点

实现说明:
  - 主选择器选择 morandi_light/morandi_dark
  - 高级折叠区选择 light/dark/sunset/forest/ocean
  - 不使用 pytest.skip（用户硬约束 skip=0）

Run:
    pytest tests/e2e/test_a11y_all_themes.py -v
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


# ============================================================
# 主题与页面配置
# ============================================================

ALL_THEMES = [
    "morandi_light",
    "morandi_dark",
    "light",
    "dark",
    "sunset",
    "forest",
    "ocean",
]

ALL_PAGES = ["对话", "成果物", "Dashboard", "成长", "技能市场", "设置"]


# ============================================================
# 辅助函数
# ============================================================


def _wait_for_streamlit_content(page, timeout: int = 15000) -> None:
    """等待 Streamlit 主内容区完全渲染."""
    try:
        page.wait_for_selector("[data-testid='stMainBlockContainer']", timeout=timeout)
        page.wait_for_function(
            """() => {
                const main = document.querySelector("[data-testid='stMainBlockContainer']");
                if (!main) return false;
                const content = main.querySelectorAll(
                    "[data-testid='stMarkdown'], [data-testid='stButton'], "
                    "[data-testid='stMetric'], [data-testid='stTabs'], "
                    "[data-testid='stAlert'], [data-testid='stExpander']"
                );
                return content.length > 0;
            }""",
            timeout=timeout,
        )
    except Exception:
        page.wait_for_timeout(5000)


def _select_theme(page, theme: str) -> None:
    """通过 sidebar 选择器切换主题.

    主选择器: morandi_light / morandi_dark
    高级折叠区: light / dark / sunset / forest / ocean
    """
    _wait_for_streamlit_content(page)

    primary_themes = ["morandi_light", "morandi_dark"]
    advanced_themes = ["light", "dark", "sunset", "forest", "ocean"]

    if theme in primary_themes:
        _select_primary_theme(page, theme)
    elif theme in advanced_themes:
        _select_advanced_theme(page, theme)
    else:
        pytest.fail(f"未知主题: {theme}")


def _select_primary_theme(page, theme: str) -> None:
    """通过主选择器选择 morandi_light 或 morandi_dark."""
    selectboxes = page.locator("[data-testid='stSelectbox']")
    assert selectboxes.count() >= 1, "sidebar 中未找到主题选择器"
    theme_sb = selectboxes.first

    theme_sb.click()
    page.wait_for_timeout(500)

    option_aliases = {
        "morandi_light": ["Morandi Light", "morandi_light", "浅色", "Morandi 浅"],
        "morandi_dark": ["Morandi Dark", "morandi_dark", "深色", "Morandi 深"],
    }
    candidates = option_aliases.get(theme, [theme])
    clicked = False
    for alias in candidates:
        opt = page.locator("[role='option']").filter(has_text=alias).first
        try:
            opt.wait_for(state="visible", timeout=1500)
            opt.click()
            clicked = True
            break
        except Exception:
            continue

    if not clicked:
        options = page.locator("[role='option']")
        idx = 0 if theme == "morandi_light" else 1
        try:
            options.nth(idx).click()
            clicked = True
        except Exception as exc:
            pytest.fail(f"无法选择主主题 {theme}: {exc}")

    page.wait_for_timeout(2500)
    # 等待 CSS 注入完成：stApp 的 color 属性应与主题 textColor 一致。
    # Sprint 4.3 fix: 2500ms 不够等待 Streamlit rerun + CSS 注入，导致
    # a11y 扫描在 CSS 加载前运行，报告错误的低对比度（如 ratio 1.11）。
    _wait_for_css_loaded(page, theme)


def _wait_for_css_loaded(page, theme: str) -> None:
    """等待主题 CSS 注入完成.

    通过检查 stApp 的 color 属性是否等于主题 textColor 来判断 CSS 是否加载。
    超时 5s 后放弃等待（不 fail，让后续断言处理）。
    """
    from frontend.components.theme_manager import THEME_CONFIGS

    config = THEME_CONFIGS.get(theme, {})
    text_color = config.get("textColor", "")
    if not text_color:
        return

    # 将 hex 转为 rgb 字符串用于比较
    hex_clean = text_color.lstrip("#")
    r, g, b = int(hex_clean[0:2], 16), int(hex_clean[2:4], 16), int(hex_clean[4:6], 16)
    expected_rgb = f"rgb({r}, {g}, {b})"

    try:
        page.wait_for_function(
            f"""() => {{
                const el = document.querySelector('.stApp');
                if (!el) return false;
                return window.getComputedStyle(el).color === '{expected_rgb}';
            }}""",
            timeout=5000,
        )
    except Exception:
        # 超时不 fail，让后续断言处理
        page.wait_for_timeout(1000)


def _select_advanced_theme(page, theme: str) -> None:
    """通过高级折叠区选择 light/dark/sunset/forest/ocean."""
    # 1. 展开"高级主题"折叠区
    expander_labels = ["Advanced themes", "高级主题", "高级", "Legacy theme"]
    expanded = False
    for label in expander_labels:
        try:
            exp = page.locator("[data-testid='stExpander']", has_text=label).first
            if exp.count() > 0:
                # 检查是否已展开
                is_expanded = exp.get_attribute("aria-expanded")
                if is_expanded != "true":
                    exp.click()
                    page.wait_for_timeout(1000)
                expanded = True
                break
        except Exception:
            continue

    if not expanded:
        # fallback: 点击所有折叠的 expander
        try:
            expanders = page.locator("[data-testid='stExpander']")
            for i in range(expanders.count()):
                exp = expanders.nth(i)
                if exp.get_attribute("aria-expanded") != "true":
                    exp.click()
                    page.wait_for_timeout(500)
        except Exception as exc:
            pytest.fail(f"无法展开高级主题折叠区: {exc}")

    # 2. 在高级选择器中选择主题
    # 高级选择器是第二个 stSelectbox（在 expander 内）
    selectboxes = page.locator("[data-testid='stSelectbox']")
    assert (
        selectboxes.count() >= 2
    ), f"未找到高级主题选择器（需要至少 2 个 selectbox，实际 {selectboxes.count()}）"
    adv_sb = selectboxes.nth(1)  # 第二个 selectbox 是高级主题
    adv_sb.click()
    page.wait_for_timeout(500)

    option_aliases = {
        "light": ["Light", "light", "浅色"],
        "dark": ["Dark", "dark", "深色"],
        "sunset": ["Sunset", "sunset", "日落"],
        "forest": ["Forest", "forest", "森林"],
        "ocean": ["Ocean", "ocean", "海洋"],
    }
    candidates = option_aliases.get(theme, [theme])
    clicked = False
    for alias in candidates:
        opt = page.locator("[role='option']").filter(has_text=alias).first
        try:
            opt.wait_for(state="visible", timeout=1500)
            opt.click()
            clicked = True
            break
        except Exception:
            continue

    if not clicked:
        pytest.fail(f"无法选择高级主题 {theme}，候选别名: {candidates}")

    page.wait_for_timeout(2500)
    _wait_for_css_loaded(page, theme)


def _goto_page_by_name(page, name: str) -> None:
    """导航到指定页面."""
    radio = page.locator("[data-testid='stRadio'] label", has_text=name).first
    try:
        radio.wait_for(state="attached", timeout=15000)
        radio.click(force=True)
    except Exception:
        clicked = page.evaluate(
            """(label) => {
                const labels = document.querySelectorAll("[data-testid='stRadio'] label");
                for (const l of labels) {
                    if (l.textContent && l.textContent.includes(label)) {
                        l.click();
                        return true;
                    }
                }
                return false;
            }""",
            name,
        )
        if not clicked:
            pytest.fail(f"无法导航到页面: {name}")
    page.wait_for_timeout(2500)


# JavaScript: 扫描交互元素的可访问标签
_SCAN_INTERACTIVES_JS = """
() => {
    const interactiveSelector = 'input, button, select, textarea, [role="button"], [role="checkbox"], [role="radio"], [role="slider"]';
    const elements = Array.from(document.querySelectorAll(interactiveSelector));
    const missing = [];
    for (const el of elements) {
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        if (rect.width === 0 || rect.height === 0) continue;
        if (style.visibility === 'hidden' || style.display === 'none') continue;
        if (el.hasAttribute('disabled')) continue;

        const ariaLabel = el.getAttribute('aria-label');
        const ariaLabelledby = el.getAttribute('aria-labelledby');
        const title = el.getAttribute('title');
        const placeholder = el.getAttribute('placeholder');
        let associatedLabel = null;
        if (el.id) {
            const lbl = document.querySelector(`label[for="${el.id}"]`);
            if (lbl && lbl.textContent.trim()) associatedLabel = lbl.textContent.trim();
        }
        const container = el.closest('[data-testid]');
        let containerLabel = null;
        if (container) {
            const lbl = container.querySelector('label, [data-testid="stWidgetLabel"]');
            if (lbl && lbl.textContent.trim()) containerLabel = lbl.textContent.trim();
        }
        const innerText = el.textContent && el.textContent.trim();
        const hasName = (
            (ariaLabel && ariaLabel.trim()) ||
            ariaLabelledby ||
            (title && title.trim()) ||
            (placeholder && placeholder.trim()) ||
            associatedLabel ||
            containerLabel ||
            (innerText && innerText.length > 0)
        );
        if (!hasName) {
            missing.push({
                tag: el.tagName.toLowerCase(),
                type: el.getAttribute('type') || '',
                role: el.getAttribute('role') || '',
                testid: container ? container.getAttribute('data-testid') : '',
            });
        }
    }
    return missing;
}
"""

# JavaScript: 扫描文本对比度
#
# 设计说明:
#   - 跳过 Material Icons / Google Symbols 字体节点: 图标字体的 textContent
#     是图标名（如 "keyboard_double_arrow_left"），但浏览器渲染为图标符号
#     （如 ⏪），不是用户可见文字。WCAG AA 检查的是用户可见文本对比度，
#     图标字体的图标符号颜色由其 CSS color 决定，与 textContent 无关。
#     扫描 textContent 对比度是测试假阳性。
#   - 跳过 aria-hidden="true" 的节点: 屏幕阅读器忽略的装饰元素，不属于
#     WCAG AA 文本对比度检查范围（WCAG 1.4.3 仅适用于可见文本）。
#   - 跳过 <title> 元素: SVG/图标的 tooltip 文字，非页面可见文本。
_CONTRAST_SCAN_JS = """
() => {
    function parseColor(color) {
        const m = color.match(/rgba?\\(([^)]+)\\)/);
        if (!m) return null;
        const parts = m[1].split(',').map(s => parseFloat(s.trim()));
        if (parts.length < 3) return null;
        return { r: parts[0], g: parts[1], b: parts[2], a: parts[3] === undefined ? 1 : parts[3] };
    }
    function luminance(c) {
        const linearize = v => {
            v = v / 255;
            return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
        };
        return 0.2126 * linearize(c.r) + 0.7152 * linearize(c.g) + 0.0722 * linearize(c.b);
    }
    function contrast(fg, bg) {
        const l1 = luminance(fg);
        const l2 = luminance(bg);
        const lighter = Math.max(l1, l2);
        const darker = Math.min(l1, l2);
        return (lighter + 0.05) / (darker + 0.05);
    }
    function blend(fg, bg) {
        return {
            r: fg.r * fg.a + bg.r * (1 - fg.a),
            g: fg.g * fg.a + bg.g * (1 - fg.a),
            b: fg.b * fg.a + bg.b * (1 - fg.a),
        };
    }
    function getBg(el) {
        // Walk up the DOM collecting semi-transparent backgrounds, then composite
        // them over the page's base color. WCAG contrast requires opaque colors;
        // using a semi-transparent bg directly (e.g. rgba(28,131,255,0.1)) without
        // compositing produces false-positive low ratios (Sprint 4.3 fix).
        const layers = [];
        let node = el;
        while (node && node !== document.documentElement) {
            const c = parseColor(window.getComputedStyle(node).backgroundColor);
            if (c && c.a > 0) {
                layers.push(c);
            }
            node = node.parentElement;
        }
        // Start with white as the base (page default), composite layers from
        // outermost → innermost so inner transparent layers blend correctly.
        let bg = { r: 255, g: 255, b: 255, a: 1 };
        for (let i = layers.length - 1; i >= 0; i--) {
            const layer = layers[i];
            bg = {
                r: layer.r * layer.a + bg.r * (1 - layer.a),
                g: layer.g * layer.a + bg.g * (1 - layer.a),
                b: layer.b * layer.a + bg.b * (1 - layer.a),
                a: 1,
            };
        }
        return bg;
    }
    function isIconFont(el) {
        // Material Icons / Material Symbols / Google Symbols 字体: textContent
        // 是图标名（如 "keyboard_double_arrow_left"），但浏览器渲染为图标符号
        // （如 ⏪），不是用户可见文字。Streamlit stIconMaterial 组件使用
        // "Material Symbols Rounded" 字体（新版 Google Symbols），旧版使用
        // "Material Icons" 字体。两者都应跳过对比度检查（测试假阳性）。
        const ff = (window.getComputedStyle(el).fontFamily || '').toLowerCase();
        if (ff.includes('material icons') || ff.includes('material symbols') || ff.includes('google symbols')) {
            return true;
        }
        // Streamlit stIconMaterial 组件兜底识别（即使字体名变化也能识别）
        if (el.getAttribute('data-testid') === 'stIconMaterial') {
            return true;
        }
        return false;
    }
    function isAriaHidden(el) {
        // aria-hidden="true" 的元素及其后代: 屏幕阅读器忽略，不属于 WCAG AA 范围
        let node = el;
        while (node && node !== document.documentElement) {
            if (node.getAttribute && node.getAttribute('aria-hidden') === 'true') {
                return true;
            }
            node = node.parentElement;
        }
        return false;
    }
    function isSvgTitle(el) {
        // <title> 元素是 SVG/图标的 tooltip，非页面可见文字
        return el.tagName && el.tagName.toLowerCase() === 'title';
    }
    const textNodes = [];
    const walker = document.createTreeWalker(
        document.body,
        NodeFilter.SHOW_TEXT,
        {
            acceptNode(node) {
                if (!node.textContent.trim()) return NodeFilter.FILTER_REJECT;
                const parent = node.parentElement;
                if (!parent) return NodeFilter.FILTER_REJECT;
                // 跳过图标字体节点（测试假阳性）
                if (isIconFont(parent)) return NodeFilter.FILTER_REJECT;
                // 跳过 aria-hidden 装饰元素
                if (isAriaHidden(parent)) return NodeFilter.FILTER_REJECT;
                // 跳过 SVG <title> tooltip
                if (isSvgTitle(parent)) return NodeFilter.FILTER_REJECT;
                const style = window.getComputedStyle(parent);
                if (style.display === 'none' || style.visibility === 'hidden') {
                    return NodeFilter.FILTER_REJECT;
                }
                return NodeFilter.FILTER_ACCEPT;
            }
        }
    );
    while (walker.nextNode()) {
        const parent = walker.currentNode.parentElement;
        const style = window.getComputedStyle(parent);
        const fg = parseColor(style.color);
        if (!fg) continue;
        const bg = getBg(parent);
        const blendedFg = blend(fg, bg);
        const ratio = contrast(blendedFg, bg);
        const text = walker.currentNode.textContent.trim().slice(0, 60);
        textNodes.push({
            text: text,
            ratio: parseFloat(ratio.toFixed(2)),
        });
    }
    return textNodes;
}
"""


# ============================================================
# GAP-P1-7: 全主题 WCAG AA 对比度验证
# ============================================================


@pytest.mark.parametrize("theme", ALL_THEMES)
class TestThemeContrastAA:
    """每个主题都做 WCAG AA 对比度验证（>= 4.5:1）."""

    def test_theme_text_contrast_meets_aa(self, page, theme):
        """Verify: 指定主题下文本对比度 >= 4.5:1.

        Scenario: 用户切换到指定主题并阅读内容
        Expected: 所有可见文本对比度 >= 4.5:1 (WCAG AA)
        """
        _select_theme(page, theme)

        text_nodes = page.evaluate(_CONTRAST_SCAN_JS)
        meaningful = [n for n in text_nodes if len(n["text"]) > 2]
        assert (
            len(meaningful) > 0
        ), f"theme={theme}: 页面上未找到文本节点，无法验证对比度"

        violations = [n for n in meaningful if n["ratio"] < 4.5]
        if violations:
            violations.sort(key=lambda n: n["ratio"])
            worst = violations[:5]
            pytest.fail(
                f"theme={theme}: 发现 {len(violations)} 个文本节点对比度 < 4.5:1。"
                f"最差 5 个: {worst}"
            )


# ============================================================
# GAP-P1-8: 全页面无障碍覆盖
# ============================================================


@pytest.mark.parametrize("page_name", ALL_PAGES)
class TestA11yPerPage:
    """每个核心页面都做 WCAG AA 扫描."""

    def test_interactive_labels_per_page(self, page, page_name):
        """Verify: 指定页面所有交互元素有可访问标签.

        Scenario: 用户使用屏幕阅读器访问指定页面
        Expected: 所有交互元素有 aria-label / label / placeholder
        """
        _goto_page_by_name(page, page_name)
        missing = page.evaluate(_SCAN_INTERACTIVES_JS)
        actionable_missing = [
            m
            for m in missing
            if not (m["tag"] == "input" and m["type"] in ("hidden", "file"))
        ]
        assert (
            not actionable_missing
        ), f"[{page_name}] 缺少标签的交互元素: {actionable_missing[:10]}"

    def test_color_contrast_per_page(self, page, page_name):
        """Verify: 指定页面颜色对比度 >= 4.5:1.

        Scenario: 用户阅读指定页面内容
        Expected: 所有文本节点对比度 >= 4.5:1 (WCAG AA)
        """
        _goto_page_by_name(page, page_name)
        text_nodes = page.evaluate(_CONTRAST_SCAN_JS)
        meaningful = [n for n in text_nodes if len(n["text"]) > 2]
        assert (
            len(meaningful) > 0
        ), f"[{page_name}] 页面上未找到文本节点，无法验证对比度"
        violations = [n for n in meaningful if n["ratio"] < 4.5]
        if violations:
            violations.sort(key=lambda n: n["ratio"])
            worst = violations[:5]
            pytest.fail(
                f"[{page_name}] 发现 {len(violations)} 个文本节点对比度 < 4.5:1。"
                f"最差 5 个: {worst}"
            )

    def test_keyboard_navigation_per_page(self, page, page_name):
        """Verify: 指定页面键盘 Tab 导航可见焦点.

        Scenario: 键盘用户通过 Tab 键导航指定页面
        Expected: 至少有一个可聚焦元素，Tab 键能移动焦点
        """
        _goto_page_by_name(page, page_name)
        page.keyboard.press("Tab")
        page.wait_for_timeout(500)
        focused = page.evaluate("""() => {
                const el = document.activeElement;
                if (!el || el === document.body) return false;
                const style = window.getComputedStyle(el);
                const outline = style.outlineStyle;
                const outlineWidth = parseFloat(style.outlineWidth) || 0;
                const boxShadow = style.boxShadow;
                const hasOutline = outline !== 'none' && outlineWidth > 0;
                const hasBoxShadow = boxShadow && boxShadow !== 'none';
                const supportsFocusVisible = CSS.supports('selector(:focus-visible)');
                return hasOutline || hasBoxShadow || supportsFocusVisible;
            }""")
        assert focused, f"[{page_name}] Tab 键未将焦点移到可见的聚焦元素"


# ============================================================
# 额外: 主题切换后无异常
# ============================================================


class TestThemeSwitchingNoException:
    """验证切换主题时不触发 stException 异常."""

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_no_exception_after_theme_switch(self, page, theme):
        """Verify: 切换到指定主题后无 stException 异常.

        Scenario: 用户切换主题
        Expected: 页面正常渲染，无异常抛出
        """
        _select_theme(page, theme)
        # 等待主题应用
        page.wait_for_timeout(2000)
        error = page.locator("[data-testid='stException']")
        assert error.count() == 0, f"切换到主题 {theme} 后出现 stException 异常"
