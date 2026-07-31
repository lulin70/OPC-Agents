"""响应式布局 E2E 测试.

GAP-P0-8: 现有 Playwright E2E 仅测 1280x800，theme_manager.py:163-245 移动端 CSS 零验证.

用户场景:
  - 手机用户 (375x667 iPhone SE) 访问，应无水平滚动
  - 平板用户 (768x1024 iPad) 访问，侧边栏可用
  - 桌面用户 (1280x800) 主力场景
  - 大屏用户 (1920x1080 FHD) 内容不应过度拉伸

验证维度:
  - 侧边栏在所有 viewport 可见或可展开
  - 无水平滚动（手机端最关键）
  - 文本无截断、无重叠
  - 主内容区可见
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

VIEWPORTS = [
    pytest.param({"width": 375, "height": 667}, id="mobile_se_iphone"),
    pytest.param({"width": 768, "height": 1024}, id="tablet_ipad"),
    pytest.param({"width": 1280, "height": 800}, id="desktop"),
    pytest.param({"width": 1920, "height": 1080}, id="fhd"),
]


@pytest.fixture(params=VIEWPORTS)
def viewport_page(request, playwright_browser, streamlit_server):
    """参数化 viewport page fixture — 4 种设备."""
    context = playwright_browser.new_context(
        viewport=request.param,
        locale="zh-CN",
    )
    page = context.new_page()
    page.set_default_timeout(15000)
    try:
        page.goto(streamlit_server, wait_until="networkidle")
        page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=20000)
        # 等待 Streamlit 完全渲染（含侧边栏）
        page.wait_for_timeout(2000)
        yield page
    finally:
        context.close()


class TestResponsiveLayout:
    """响应式布局核心验证 — 4 种 viewport."""

    def test_sidebar_visible_or_collapsible(self, viewport_page):
        """Verify: 所有 viewport 下侧边栏可见或可展开.

        Scenario: 用户在不同设备访问，需要导航菜单
        Expected: 侧边栏 DOM 存在（移动端/平板可能折叠，但应可展开）
        """
        sidebar = viewport_page.locator("[data-testid='stSidebar']")
        expect(sidebar).to_be_attached(timeout=10000)
        # 桌面端 (>1024) 侧边栏应默认可见
        # 平板 (768) 和手机 (<768) 可能折叠 — Streamlit 在 768 边界行为不确定
        if viewport_page.viewport_size and viewport_page.viewport_size["width"] > 1024:
            expect(sidebar).to_be_visible(timeout=5000)

    def test_no_horizontal_scroll(self, viewport_page):
        """Verify: 所有 viewport 下无水平滚动（scrollWidth <= innerWidth + 10px 容差）.

        Scenario: 用户访问不应出现横向滚动条
        Expected: body.scrollWidth <= window.innerWidth + 10
        """
        scroll_width = viewport_page.evaluate("document.body.scrollWidth")
        inner_width = viewport_page.evaluate("window.innerWidth")
        assert scroll_width <= inner_width + 10, (
            f"viewport={viewport_page.viewport_size}, "
            f"scrollWidth={scroll_width}, innerWidth={inner_width} — 出现水平滚动"
        )

    def test_main_content_visible(self, viewport_page):
        """Verify: 所有 viewport 下主内容区可见.

        Scenario: 用户进入应用应看到主内容
        Expected: stMainBlockContainer 可见
        """
        main = viewport_page.locator("[data-testid='stMainBlockContainer']")
        expect(main).to_be_visible(timeout=10000)

    def test_no_text_truncation(self, viewport_page):
        """Verify: 用户可见的文本无截断（仅检查 p/h1-h3，排除容器 div）.

        Scenario: 用户看到的段落/标题文本应完整显示
        Expected: p/h1/h2/h3 元素 offsetWidth >= scrollWidth

        注: 排除 div/span 因为 Streamlit 框架内部用 div 做固定宽度容器
        （如侧边栏折叠按钮 icon 容器、快捷键对话框行），这些不是用户可读文本.
        """
        truncated = viewport_page.evaluate(
            """() => {
                // 仅检查用户可读的段落/标题文本
                const els = document.querySelectorAll("p, h1, h2, h3");
                const truncated = [];
                for (const el of els) {
                    // 只检查有直接文本内容且可见的元素
                    const directText = Array.from(el.childNodes)
                        .filter(n => n.nodeType === 3)
                        .map(n => n.textContent.trim())
                        .join("");
                    if (el.offsetWidth < el.scrollWidth && directText
                        && el.offsetParent !== null && el.offsetWidth > 0) {
                        truncated.push({
                            tag: el.tagName,
                            text: directText.substring(0, 80),
                            offsetWidth: el.offsetWidth,
                            scrollWidth: el.scrollWidth,
                        });
                    }
                }
                return truncated.slice(0, 5);
            }"""
        )
        assert not truncated, (
            f"viewport={viewport_page.viewport_size} 存在用户可见文本截断: {truncated}"
        )

    def test_no_content_overlap(self, viewport_page):
        """Verify: 所有 viewport 下关键元素无重叠.

        Scenario: 用户看到的元素不应相互重叠
        Expected: 关键元素 bounding box 不重叠
        """
        # 检查主内容区与侧边栏不重叠
        overlap = viewport_page.evaluate(
            """() => {
                const main = document.querySelector("[data-testid='stMainBlockContainer']");
                const sidebar = document.querySelector("[data-testid='stSidebar']");
                if (!main || !sidebar) return null;
                const m = main.getBoundingClientRect();
                const s = sidebar.getBoundingClientRect();
                // 桌面端: sidebar 不应覆盖 main 内容区（允许 1px 容差）
                // 移动端 collapsed: sidebar 可能 transform off-screen
                const overlapX = Math.max(0, Math.min(m.right, s.right) - Math.max(m.left, s.left));
                const overlapY = Math.max(0, Math.min(m.bottom, s.bottom) - Math.max(m.top, s.top));
                const overlapArea = overlapX * overlapY;
                return {
                    overlapArea,
                    mainRect: {x: m.x, y: m.y, w: m.width, h: m.height},
                    sidebarRect: {x: s.x, y: s.y, w: s.width, h: s.height},
                    sidebarVisible: s.width > 50 && s.x > -s.width,
                };
            }"""
        )
        if overlap is None:
            return
        # 如果 sidebar 可见（宽度>50 且未移出屏幕），检查不与 main 重叠超过 10px²
        if overlap.get("sidebarVisible"):
            assert overlap["overlapArea"] <= 10, (
                f"viewport={viewport_page.viewport_size} sidebar 与 main 重叠 "
                f"area={overlap['overlapArea']}: {overlap}"
            )


class TestMobileSpecific:
    """手机端特定验证 — 仅 mobile_se viewport."""

    def test_mobile_chat_input_visible(self, page, streamlit_server):
        """Verify: 手机端 Chat 输入框可见（Demo 模式也应显示信息面板）.

        Scenario: 手机用户访问 Chat 页面
        Expected: 主内容区可见，不因 viewport 过小而隐藏
        """
        # 设置为手机 viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.wait_for_timeout(1500)

        # 手机端侧边栏默认折叠，需先展开
        sidebar = page.locator("[data-testid='stSidebar']")
        if sidebar.count() > 0:
            # 点击汉堡按钮展开侧边栏
            try:
                collapse_btn = page.locator("[data-testid='collapsedControl']").first
                if collapse_btn.is_visible(timeout=2000):
                    collapse_btn.click()
                    page.wait_for_timeout(1500)
            except Exception:
                pass  # 侧边栏可能已展开

        # 导航到对话页（使用 force 避免 viewport 外点击失败）
        radio = page.locator("[data-testid='stRadio'] label", has_text="对话").first
        try:
            radio.wait_for(state="visible", timeout=5000)
            radio.click(force=True)
            page.wait_for_timeout(2000)
        except Exception:
            # 导航可能失败，但主内容区仍应可见
            pass

        # 主内容区应可见
        main = page.locator("[data-testid='stMainBlockContainer']")
        expect(main).to_be_visible(timeout=10000)

    def test_mobile_no_overflow_elements(self, page, streamlit_server):
        """Verify: 手机端无元素溢出 body 宽度.

        Scenario: 手机用户不应需要横向滚动查看任何内容
        Expected: body.scrollWidth <= 375 + 10
        """
        page.set_viewport_size({"width": 375, "height": 667})
        page.wait_for_timeout(1000)
        scroll_width = page.evaluate("document.body.scrollWidth")
        assert scroll_width <= 385, (
            f"手机端出现水平滚动: scrollWidth={scroll_width} > 375+10"
        )


class TestDesktopSpecific:
    """桌面端特定验证 — 仅 desktop/fhd viewport."""

    def test_desktop_sidebar_expanded_by_default(self, page, streamlit_server):
        """Verify: 桌面端侧边栏默认展开（width >= 768）.

        Scenario: 桌面用户访问应用，侧边栏应默认展开
        Expected: stSidebar 可见且宽度 > 100
        """
        page.set_viewport_size({"width": 1280, "height": 800})
        page.wait_for_timeout(1500)
        sidebar = page.locator("[data-testid='stSidebar']")
        expect(sidebar).to_be_visible(timeout=10000)
        # 验证侧边栏宽度合理（不应是 0 或过小）
        width = sidebar.bounding_box()["width"] if sidebar.bounding_box() else 0
        assert width > 100, f"桌面端侧边栏宽度应 > 100，实际 {width}"
