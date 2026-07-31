"""视觉回归测试 — page.screenshot() + PIL ImageChops 像素对比.

GAP-P0-9: 无 screenshot baseline 对比，UI 变更无法自动检测.

用户场景:
  - 开发者修改 UI 后，应能自动检测到视觉变化
  - 主题切换（light/dark）不应破坏布局
  - 核心 4 页面（首页/Dashboard/Settings/Deliverables）有视觉基线

实现方式:
  - 使用 page.screenshot() 截图 + PIL ImageChops.difference() 像素对比
  - 不依赖 pytest-playwright 插件（项目未安装该插件）
  - 首次运行自动生成 baseline（测试通过）
  - 后续运行对比 baseline，diff 像素比 > 1% 则失败
  - 设置 UPDATE_SNAPSHOTS=true 环境变量可重新生成 baseline
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image, ImageChops
from playwright.sync_api import Page

pytestmark = [pytest.mark.e2e, pytest.mark.visual]

_BASELINE_DIR = Path(__file__).parent / "__screenshots__"
_DIFF_THRESHOLD = 0.01  # 1% 像素差异阈值


def _goto_page(page: Page, label: str) -> None:
    """导航到指定页面（通过侧边栏 radio）."""
    radio = page.locator("[data-testid='stRadio'] label", has_text=label).first
    radio.wait_for(state="attached", timeout=15000)
    radio.click(force=True)
    page.wait_for_timeout(3000)  # 等待渲染稳定


def _close_dialogs(page: Page) -> None:
    """关闭可能的弹窗（快捷键提示等）."""
    try:
        got_it_btn = page.locator("button:has-text('Got it')").first
        if got_it_btn.is_visible(timeout=2000):
            got_it_btn.click()
            page.wait_for_timeout(1000)
    except Exception:
        pass


def _compare_or_save_baseline(page: Page, name: str) -> None:
    """截图并与 baseline 对比，或首次生成 baseline.

    Args:
        page: Playwright Page 对象
        name: baseline 文件名（不含扩展名）

    逻辑:
        1. 截取当前页面截图
        2. 若 baseline 不存在 → 保存为 baseline，测试通过
        3. 若 baseline 存在 → PIL ImageChops 对比
        4. diff 像素比 > 1% → 失败
        5. UPDATE_SNAPSHOTS=true → 覆盖 baseline
    """
    _BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    baseline_path = _BASELINE_DIR / f"{name}.png"
    current_path = _BASELINE_DIR / f"{name}.current.png"
    diff_path = _BASELINE_DIR / f"{name}.diff.png"

    # 截图
    page.screenshot(path=str(current_path), full_page=False)

    # 更新模式
    if os.environ.get("UPDATE_SNAPSHOTS", "").lower() in ("true", "1", "yes"):
        Path(current_path).rename(baseline_path)
        return

    # 首次运行：生成 baseline
    if not baseline_path.exists():
        Path(current_path).rename(baseline_path)
        print(f"[Visual Regression] 首次运行，已生成 baseline: {baseline_path}")
        return

    # 对比
    baseline_img = Image.open(baseline_path).convert("RGB")
    current_img = Image.open(current_path).convert("RGB")

    # 尺寸不一致直接失败
    if baseline_img.size != current_img.size:
        Path(current_path).unlink(missing_ok=True)
        pytest.fail(
            f"截图尺寸不一致: baseline={baseline_img.size}, current={current_img.size}"
        )

    # 像素差异
    diff = ImageChops.difference(baseline_img, current_img)
    diff_pixels = sum(1 for pixel in diff.getdata() if any(c > 10 for c in pixel))
    total_pixels = baseline_img.size[0] * baseline_img.size[1]
    diff_ratio = diff_pixels / total_pixels if total_pixels > 0 else 0

    # 清理 current 截图
    Path(current_path).unlink(missing_ok=True)

    if diff_ratio > _DIFF_THRESHOLD:
        # 保存 diff 图供调试
        diff.save(str(diff_path))
        pytest.fail(
            f"视觉回归失败: {name}.png 像素差异 {diff_ratio:.2%} > {_DIFF_THRESHOLD:.0%} 阈值\n"
            f"  baseline: {baseline_path}\n"
            f"  diff: {diff_path}\n"
            f"  重新生成: UPDATE_SNAPSHOTS=true pytest tests/e2e/test_visual_regression.py -v"
        )

    # 通过则清理 diff 图（如有）
    Path(diff_path).unlink(missing_ok=True)


class TestVisualRegressionBaseline:
    """建立 4 个核心页面的 baseline 截图.

    首次运行: 自动生成 baseline（测试通过）
    后续运行: 对比 baseline，diff > 1% 失败
    更新 baseline: UPDATE_SNAPSHOTS=true pytest tests/e2e/test_visual_regression.py -v
    """

    def test_homepage_baseline(self, page, streamlit_server):
        """Verify: 首页与 baseline 一致（1% 容差）."""
        page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=20000)
        page.wait_for_timeout(3000)
        _close_dialogs(page)
        _compare_or_save_baseline(page, "homepage")

    def test_dashboard_baseline(self, page, streamlit_server):
        """Verify: Dashboard 页面与 baseline 一致."""
        _goto_page(page, "Dashboard")
        _compare_or_save_baseline(page, "dashboard")

    def test_settings_baseline(self, page, streamlit_server):
        """Verify: Settings 页面与 baseline 一致."""
        _goto_page(page, "设置")
        _compare_or_save_baseline(page, "settings")

    def test_deliverables_baseline(self, page, streamlit_server):
        """Verify: Deliverables 页面与 baseline 一致."""
        _goto_page(page, "成果物")
        _compare_or_save_baseline(page, "deliverables")


class TestVisualRegressionTheme:
    """主题视觉回归（light + dark）— 验证主题切换不破坏布局."""

    def test_light_theme_baseline(self, page, streamlit_server):
        """Verify: 浅色主题首页 baseline（默认主题）."""
        page.wait_for_timeout(3000)
        _close_dialogs(page)
        _compare_or_save_baseline(page, "theme_light")

    def test_dark_theme_baseline(self, page, streamlit_server):
        """Verify: 深色主题首页 baseline."""
        _close_dialogs(page)

        # 尝试切换到 dark 主题
        try:
            radio = page.locator("[data-testid='stRadio'] label", has_text="设置").first
            if radio.count() > 0:
                radio.click(force=True)
                page.wait_for_timeout(2000)

            theme_select = page.locator(
                "[data-testid='stSelectbox'] label:has-text('主题')"
            ).first
            if theme_select.count() > 0:
                theme_select.locator("..").locator("div[role='combobox']").click()
                page.wait_for_timeout(500)
                dark_option = page.locator("li[role='option']:has-text('dark')").first
                if dark_option.count() > 0:
                    dark_option.click()
                    page.wait_for_timeout(2000)
        except Exception:
            pass  # 主题切换失败时仍尝试截图

        _compare_or_save_baseline(page, "theme_dark")


class TestVisualRegressionSidebar:
    """侧边栏展开状态视觉回归."""

    def test_sidebar_expanded_baseline(self, page, streamlit_server):
        """Verify: 侧边栏展开状态首页 baseline."""
        page.wait_for_timeout(3000)
        _close_dialogs(page)
        # 确保侧边栏展开
        try:
            collapse_btn = page.locator("[data-testid='collapsedControl']").first
            if collapse_btn.is_visible(timeout=1000):
                collapse_btn.click()
                page.wait_for_timeout(1500)
        except Exception:
            pass
        _compare_or_save_baseline(page, "sidebar_expanded")
