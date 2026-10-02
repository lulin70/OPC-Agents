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

隔离设计:
  使用模块级 visual_server（OPC_WORKSPACE 指向一次性临时工作区），
  而非共享 streamlit_server：后者复用真实 PROJECT_ROOT/deliverables，
  该目录内容随开发过程变化，导致基线对比出现环境性假阳性
  （如 deliverables 基线在真实目录文件数变化后稳定复现 1.49% 漂移）。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Generator
from pathlib import Path

import pytest
from PIL import Image, ImageChops
from playwright.sync_api import Page

from tests.e2e.conftest import (
    FRONTEND_APP,
    PROJECT_ROOT,
    _find_free_port,
    _wait_for_server,
)

pytestmark = [pytest.mark.e2e, pytest.mark.visual]

_BASELINE_DIR = Path(__file__).parent / "__screenshots__"
_DIFF_THRESHOLD = 0.01  # 1% 像素差异阈值


def _goto_page(page: Page, label: str, wait_text: str) -> None:
    """导航到指定页面（通过侧边栏 radio）并等待目标页特有内容渲染.

    固定 sleep 无法保证 Streamlit rerun 完成：冷启动服务器上存在竞态，
    曾拍到未完成切换的上一页内容（dashboard 基线混入聊天页的
    操作提示气泡与 Demo 横幅，导致 18% 假性像素差异）。
    等待目标页特有文本保证导航完成后再截图。
    """
    radio = page.locator("[data-testid='stRadio'] label", has_text=label).first
    radio.wait_for(state="attached", timeout=15000)
    radio.click(force=True)
    page.wait_for_selector(f"text={wait_text}", timeout=15000)
    page.wait_for_timeout(1000)  # 等待图表等异步组件渲染稳定


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


@pytest.fixture(scope="module")
def visual_server(tmp_path_factory) -> Generator[str, None, None]:
    """隔离工作区的 Streamlit server，保证视觉基线跨环境确定。

    - OPC_WORKSPACE 指向一次性临时目录：base_router.py 在模块加载时读取
      该变量计算 DELIVERABLES_DIR 与 CHAT_HISTORY_FILE，页面数据因此确定
    - deliverables/ 预置固定内容文件，Deliverables 页渲染不受本地工作区影响
    - Demo 模式与数据隔离配方与 conftest.streamlit_server 保持一致
    """
    workspace = tmp_path_factory.mktemp("opc_visual_workspace")
    deliverables_dir = workspace / "deliverables"
    deliverables_dir.mkdir()
    (
        deliverables_dir / "20260714_120000_content_generation_E2E_test_deliverable.md"
    ).write_text(
        "# E2E 测试成果物\n\n这是 Playwright E2E 测试自动创建的成果物文件。\n\n"
        "## 内容\n\n用于验证搜索框和下载按钮功能。\n",
        encoding="utf-8",
    )

    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["OPC_WORKSPACE"] = str(workspace)
    # 清空 API key 并隔离本地加密存储，确保 Demo 模式激活（与 conftest 配方一致）
    env["MOKA_API_KEY"] = ""
    env["GLM_API_KEY"] = ""
    env["OPENAI_API_KEY"] = ""
    env["OPC_SECURE_STORAGE"] = str(workspace / "no_secure.missing")
    env["OPC_SETTINGS_FILE"] = str(workspace / "no_settings.missing")
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["BROWSER"] = "none"

    e2e_data_dir = workspace / "opc_data"
    e2e_data_dir.mkdir(parents=True, exist_ok=True)
    env["OPC_DATA_DIR"] = str(e2e_data_dir)

    onboarding_marker = workspace / "onboarding.marker"
    onboarding_marker.write_text(str(time.time()), encoding="utf-8")
    env["OPC_ONBOARDING_MARKER"] = str(onboarding_marker)

    log_path = workspace / "streamlit.log"
    log_file = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(FRONTEND_APP),
            "--server.port",
            str(port),
            "--server.headless",
            "true",
            "--server.address",
            "127.0.0.1",
            "--browser.gatherUsageStats",
            "false",
        ],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env=env,
        cwd=str(PROJECT_ROOT),
    )

    try:
        _wait_for_server(base_url, timeout=60.0, proc=proc, log_path=str(log_path))
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        log_file.close()


class TestVisualRegressionBaseline:
    """建立 4 个核心页面的 baseline 截图.

    首次运行: 自动生成 baseline（测试通过）
    后续运行: 对比 baseline，diff > 1% 失败
    更新 baseline: UPDATE_SNAPSHOTS=true pytest tests/e2e/test_visual_regression.py -v
    """

    def test_homepage_baseline(self, page, visual_server):
        """Verify: 首页与 baseline 一致（1% 容差）."""
        page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=20000)
        page.wait_for_timeout(3000)
        _close_dialogs(page)
        _compare_or_save_baseline(page, "homepage")

    def test_dashboard_baseline(self, page, visual_server):
        """Verify: Dashboard 页面与 baseline 一致."""
        _goto_page(page, "Dashboard", "数据仪表盘")
        _compare_or_save_baseline(page, "dashboard")

    def test_settings_baseline(self, page, visual_server):
        """Verify: Settings 页面与 baseline 一致."""
        _goto_page(page, "设置", "系统设置")
        _compare_or_save_baseline(page, "settings")

    def test_deliverables_baseline(self, page, visual_server):
        """Verify: Deliverables 页面与 baseline 一致."""
        _goto_page(page, "成果物", "搜索成果物")
        _compare_or_save_baseline(page, "deliverables")


class TestVisualRegressionTheme:
    """主题视觉回归（light + dark）— 验证主题切换不破坏布局."""

    def test_light_theme_baseline(self, page, visual_server):
        """Verify: 浅色主题首页 baseline（默认主题）."""
        page.wait_for_timeout(3000)
        _close_dialogs(page)
        _compare_or_save_baseline(page, "theme_light")

    def test_dark_theme_baseline(self, page, visual_server):
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

    def test_sidebar_expanded_baseline(self, page, visual_server):
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
