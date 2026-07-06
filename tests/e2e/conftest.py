"""Playwright E2E test fixtures for OPC-Agents UI.

启动真实 Streamlit server + 真实 Chromium 浏览器进行端到端测试。

满足 HARD_CONSTRAINTS.md Q1/Q2 要求：发布前必须做模拟真实用户使用的测试。

Run:
    pytest tests/e2e/test_ui_playwright.py -v
    pytest tests/e2e/ -m "not slow"  # 跳过慢测试
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Generator

import pytest

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_APP = PROJECT_ROOT / "frontend" / "app.py"

# 确保 opc_manager 模块可导入
sys.path.insert(0, str(PROJECT_ROOT))


def _find_free_port() -> int:
    """动态分配空闲端口，避免冲突。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(
    url: str,
    timeout: float = 60.0,
    proc: subprocess.Popen | None = None,
    log_path: str | None = None,
) -> None:
    """轮询健康检查端点直到 server 就绪。

    Streamlit 1.57.0 健康检查: GET /_stcore/health 应返回 "ok"

    如果 proc 提供，会检查进程是否已退出（端口冲突等情况）。
    """
    import urllib.request

    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        # 检查进程是否已意外退出
        if proc is not None and proc.poll() is not None:
            log_content = ""
            if log_path:
                try:
                    with open(log_path, encoding="utf-8") as f:
                        log_content = f.read()[-2000:]
                except Exception:
                    pass
            raise RuntimeError(
                f"Streamlit process exited with code {proc.returncode} before becoming healthy.\n"
                f"log: {log_content}"
            )
        try:
            req = urllib.request.Request(f"{url}/_stcore/health")
            with urllib.request.urlopen(req, timeout=2) as resp:
                body = resp.read().decode("utf-8").strip()
                if resp.status == 200 and body == "ok":
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(1.0)
    # 超时时输出日志帮助诊断
    log_content = ""
    if log_path:
        try:
            with open(log_path, encoding="utf-8") as f:
                log_content = f.read()[-3000:]
        except Exception:
            pass
    raise RuntimeError(
        f"Streamlit server failed to start within {timeout}s (last error: {last_error})\n"
        f"--- streamlit log (last 3000 chars) ---\n{log_content}"
    )


@pytest.fixture(scope="session")
def streamlit_server() -> Generator[str, None, None]:
    """启动真实 Streamlit server，返回 base_url。

    - 动态分配端口
    - headless 模式（无浏览器自动打开）
    - 不设置 API key 环境变量 → 自动激活 Demo 模式
    - 会话级复用（避免每个测试都重启 server）
    """
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    # 清理环境变量，确保 Demo 模式激活
    env = os.environ.copy()
    # 设为空字符串覆盖 .env 文件中的值（load_dotenv 默认不覆盖已有环境变量）
    env["MOKA_API_KEY"] = ""
    env["GLM_API_KEY"] = ""
    env["OPENAI_API_KEY"] = ""
    # 隔离本地 .env.encrypted 中保存的真实 API key。
    # app.py 启动时调用 init_secure_storage()，其 load_to_env() 会无条件下发
    # os.environ[name] = value 覆盖上面的空值，导致 _has_api_key() 返回 True，
    # is_demo_mode() 返回 False，Demo 横幅不渲染，E2E 测试 TC_H04 失败。
    # 指向不存在路径后，_load_storage 返回空 keys（secure_storage.py:222-223），
    # load_to_env 循环不执行，env 空值得以保留。
    env["OPC_SECURE_STORAGE"] = f"/tmp/opc_e2e_no_secure_{os.getpid()}.missing"
    # 避免测试期间弹窗干扰
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["BROWSER"] = "none"  # 防止 streamlit 自动打开浏览器

    # 预创建 onboarding marker 文件，跳过新手引导覆盖层
    # 否则 onboarding overlay 会阻挡主内容渲染
    import tempfile

    onboarding_marker = (
        Path(tempfile.gettempdir()) / f"opc_e2e_onboarding_{os.getpid()}.marker"
    )
    onboarding_marker.parent.mkdir(parents=True, exist_ok=True)
    onboarding_marker.write_text(str(time.time()), encoding="utf-8")
    env["OPC_ONBOARDING_MARKER"] = str(onboarding_marker)

    cmd = [
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
    ]

    # 将 stdout/stderr 写入文件避免缓冲区阻塞
    log_file = open("/tmp/opc_streamlit_e2e.log", "w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env=env,
        cwd=str(PROJECT_ROOT),
    )

    try:
        _wait_for_server(
            base_url, timeout=60.0, proc=proc, log_path="/tmp/opc_streamlit_e2e.log"
        )
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        log_file.close()


@pytest.fixture(scope="session")
def playwright_browser() -> Generator[Any, None, None]:
    """会话级 Playwright Chromium 浏览器实例。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        pytest.skip(f"playwright not installed: {exc}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture
def page(playwright_browser: Any, streamlit_server: str) -> Generator[Any, None, None]:
    """每个测试一个新页面，导航到 Streamlit。

    - 新 context 隔离 cookie/session
    - 默认导航到首页
    - 测试后关闭页面
    """
    context = playwright_browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="zh-CN",
    )
    page = context.new_page()
    # 设置默认超时，Streamlit 渲染较慢
    page.set_default_timeout(15000)
    page.set_default_navigation_timeout(30000)

    try:
        page.goto(streamlit_server, wait_until="networkidle")
        # 等待 Streamlit 完全渲染
        page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=20000)
        yield page
    finally:
        context.close()


@pytest.fixture
def context_with_download(
    playwright_browser: Any, streamlit_server: str
) -> Generator[Any, None, None]:
    """带下载支持的浏览器 context（用于 FD-004 下载按钮测试）。

    使用 accept_downloads=True 确保能捕获下载事件。
    """
    context = playwright_browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="zh-CN",
        accept_downloads=True,
    )
    page = context.new_page()
    page.set_default_timeout(15000)
    page.set_default_navigation_timeout(30000)

    try:
        page.goto(streamlit_server, wait_until="networkidle")
        page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=20000)
        yield page
    finally:
        context.close()


def navigate_to_page(page: Any, page_name: str) -> None:
    """辅助函数：通过侧边栏导航到指定页面。

    Args:
        page: Playwright Page 实例
        page_name: 目标页面名称（chat/deliverables/dashboard/growth/marketplace/settings）
    """
    radio_group = page.locator("[data-testid='stRadio'] [role='radio']")
    # 按 label 文本匹配（支持多语言后的英文/日文标签）
    target = radio_group.filter(has_text=page_name).first
    target.click()
    # 等待页面切换完成
    page.wait_for_load_state("networkidle")
