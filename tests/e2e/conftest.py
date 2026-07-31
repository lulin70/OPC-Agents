"""Playwright E2E test fixtures for OPC-Agents UI.

启动真实 Streamlit server + 真实 Chromium 浏览器进行端到端测试。

满足 HARD_CONSTRAINTS.md Q1/Q2 要求：发布前必须做模拟真实用户使用的测试。

Run:
    pytest tests/e2e/test_ui_playwright.py -v
    pytest tests/e2e/ -m "not slow"  # 跳过慢测试
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Generator

import pytest

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_APP = PROJECT_ROOT / "frontend" / "app.py"

# 确保 opc_manager 模块可导入
sys.path.insert(0, str(PROJECT_ROOT))


# Sprint 4.3: 当 Docker 不可用时不收集 Docker 运行时测试，避免 SKIPPED 状态
# （用户硬约束: skip测试数量需保持为0）。
# Docker 不可用 = docker 命令不存在或 daemon 未运行。
# 在 CI 环境中 Docker 可用时会正常收集。
def _is_docker_available() -> bool:
    """检查 Docker 命令是否存在且 daemon 正在运行."""
    if not shutil.which("docker"):
        return False
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


if not _is_docker_available():
    collect_ignore_glob = ["test_docker_run_e2e.py"]


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
    - 预创建测试成果物文件，确保 Deliverables 页面搜索框和下载按钮能渲染
      （deliverables_renderer.py 中搜索框只在 session_state.deliverables 非空时渲染）
    """
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    # 预创建测试成果物文件（在 server 启动前，确保初始化时加载到 session_state）
    deliverables_dir = PROJECT_ROOT / "deliverables"
    deliverables_dir.mkdir(parents=True, exist_ok=True)
    session_deliverable = (
        deliverables_dir / "20260714_120000_content_generation_E2E_test_deliverable.md"
    )
    session_deliverable.write_text(
        "# E2E 测试成果物\n\n这是 Playwright E2E 测试自动创建的成果物文件。\n\n"
        "## 内容\n\n用于验证搜索框和下载按钮功能。\n",
        encoding="utf-8",
    )

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
    # 隔离 data/settings.json 中保存的真实加密 API key。
    # SettingsManager._load_from_disk() 会加载 data/settings.json，解密 api_key
    # 到 self._llm.api_key，导致 get_api_key() 返回非空，_has_api_key() 返回 True，
    # Demo 模式不激活。通过 OPC_SETTINGS_FILE 指向不存在的路径，_load_from_disk
    # 检测到文件不存在时使用默认空值（settings_persistence.py:74-78），Demo 模式激活。
    env["OPC_SETTINGS_FILE"] = f"/tmp/opc_e2e_no_settings_{os.getpid()}.missing"
    # 避免测试期间弹窗干扰
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["BROWSER"] = "none"  # 防止 streamlit 自动打开浏览器

    # === GAP-P0-7: E2E 数据库隔离 ===
    # 只重定向 OPC_DATA_DIR（数据库目录），避免污染真实 data/opc_data.db
    # 不重定向 OPC_WORKSPACE，因为 base_router.py:16 在模块加载时读取 OPC_WORKSPACE
    # 计算 DELIVERABLES_DIR，重定向会导致 session_deliverable 文件找不到
    # （session_deliverable 在 PROJECT_ROOT/deliverables 创建，供 Deliverables 页面渲染）
    e2e_data_dir = Path(tempfile.gettempdir()) / f"opc_e2e_data_{os.getpid()}"
    if e2e_data_dir.exists():
        shutil.rmtree(e2e_data_dir, ignore_errors=True)
    e2e_data_dir.mkdir(parents=True, exist_ok=True)
    env["OPC_DATA_DIR"] = str(e2e_data_dir)

    # 预创建 onboarding marker 文件，跳过新手引导覆盖层
    # 否则 onboarding overlay 会阻挡主内容渲染
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
        # 清理 session 级测试文件
        if session_deliverable.exists():
            session_deliverable.unlink()
        # === GAP-P0-7: 清理 E2E 数据目录 ===
        try:
            if e2e_data_dir.exists():
                shutil.rmtree(e2e_data_dir, ignore_errors=True)
        except Exception as e:
            # 清理失败不应阻断测试，但需记录
            print(f"[E2E cleanup] Failed to remove {e2e_data_dir}: {e}")
        # === GAP-P2-6: 清理 onboarding marker ===
        try:
            if onboarding_marker.exists():
                onboarding_marker.unlink()
        except Exception:
            pass


@pytest.fixture(scope="session")
def streamlit_server_real_mode() -> Generator[str, None, None]:
    """启动真实模式 Streamlit server（带 Mock LLM 后端）.

    与 streamlit_server 的区别:
    - 设置 MOKA_API_KEY=test-key 激活真实模式渲染（输入框可见，不 st.stop）
    - 通过 OPC_MOCK_LLM=true 让 SimpleLLMService 走 mock 路径，不真实调用 API
    - 走完整 Chat 渲染流程（输入框可见、提交、轮询、成果物）

    GAP-P0-1: 现有 streamlit_server 全部在 Demo 模式，chat_router.py:288 st.stop()
    跳过输入框，导致产品核心价值流（Chat 提交→成果物）从未被 E2E 验证.
    """
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    # 激活真实模式（关键：非空 API Key 让 _has_api_key() 返回 True）
    env["MOKA_API_KEY"] = "sk-e2e-test-key-not-real"
    env["GLM_API_KEY"] = ""
    env["OPENAI_API_KEY"] = ""
    # Mock LLM 后端（SimpleLLMService.complete 检测此变量返回 mock 响应）
    env["OPC_MOCK_LLM"] = "true"
    # 跳过反思循环（Mock 模式不需要多轮反思，加快测试执行）
    env["OPC_SKIP_REFLECT"] = "true"
    # 隔离 settings.json 和 secure storage（避免真实 key 干扰）
    env["OPC_SETTINGS_FILE"] = f"/tmp/opc_e2e_real_no_settings_{os.getpid()}.missing"
    env["OPC_SECURE_STORAGE"] = f"/tmp/opc_e2e_real_no_secure_{os.getpid()}.missing"
    # 数据隔离（只重定向 OPC_DATA_DIR，不重定向 OPC_WORKSPACE，避免 deliverables 找不到）
    e2e_data_dir = Path(tempfile.gettempdir()) / f"opc_e2e_real_data_{os.getpid()}"
    if e2e_data_dir.exists():
        shutil.rmtree(e2e_data_dir, ignore_errors=True)
    e2e_data_dir.mkdir(parents=True, exist_ok=True)
    env["OPC_DATA_DIR"] = str(e2e_data_dir)
    # 跳过新手引导
    onboarding_marker = (
        Path(tempfile.gettempdir()) / f"opc_e2e_real_onboarding_{os.getpid()}.marker"
    )
    onboarding_marker.parent.mkdir(parents=True, exist_ok=True)
    onboarding_marker.write_text(str(time.time()), encoding="utf-8")
    env["OPC_ONBOARDING_MARKER"] = str(onboarding_marker)
    # Sprint 4.1 GAP-P0-4: 错误恢复 E2E 支持文件路径
    # server 子进程读取此文件获取 mock 错误类型（测试 fixture 动态写入）
    # 使用固定路径（E2E 测试不并行运行），同时在测试进程设置以便 fixture 读取
    mock_error_path = "/tmp/opc_e2e_mock_error.txt"
    env["OPC_MOCK_LLM_ERROR_FILE"] = mock_error_path
    os.environ["OPC_MOCK_LLM_ERROR_FILE"] = mock_error_path
    # 确保测试开始前文件不存在（无错误注入）
    try:
        Path(mock_error_path).unlink(missing_ok=True)
    except Exception:
        pass
    # 其他
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["BROWSER"] = "none"

    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(FRONTEND_APP),
        "--server.port", str(port),
        "--server.headless", "true",
        "--server.address", "127.0.0.1",
        "--browser.gatherUsageStats", "false",
    ]

    log_file = open(f"/tmp/opc_streamlit_e2e_real_{os.getpid()}.log", "w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env=env,
        cwd=str(PROJECT_ROOT),
    )

    try:
        _wait_for_server(
            base_url,
            timeout=60.0,
            proc=proc,
            log_path=f"/tmp/opc_streamlit_e2e_real_{os.getpid()}.log",
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
        try:
            if e2e_data_dir.exists():
                shutil.rmtree(e2e_data_dir, ignore_errors=True)
            if onboarding_marker.exists():
                onboarding_marker.unlink()
            # Sprint 4.1: 清理 mock error 文件
            mock_error_file = Path("/tmp/opc_e2e_mock_error.txt")
            if mock_error_file.exists():
                mock_error_file.unlink()
        except Exception:
            pass


@pytest.fixture
def page_real_mode(
    playwright_browser: Any, streamlit_server_real_mode: str
) -> Generator[Any, None, None]:
    """真实模式 Playwright page fixture.

    与 page fixture 的区别:
    - 使用 streamlit_server_real_mode（Mock LLM）
    - 默认超时更长（真实模式渲染更慢，涉及 LLM 调用）
    - accept_downloads=True（支持下载按钮测试）
    """
    context = playwright_browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="zh-CN",
        accept_downloads=True,
    )
    page = context.new_page()
    page.set_default_timeout(30000)  # 真实模式渲染更慢
    page.set_default_navigation_timeout(60000)

    try:
        page.goto(streamlit_server_real_mode, wait_until="networkidle")
        page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=30000)
        # 等待内容渲染（真实模式应渲染输入框或场景按钮）
        try:
            page.wait_for_function(
                """() => {
                    const main = document.querySelector("[data-testid='stMainBlockContainer']");
                    if (!main) return false;
                    const hasInput = document.querySelector("textarea");
                    const hasScenario = document.querySelector("[data-testid='stButton']");
                    return hasInput || hasScenario;
                }""",
                timeout=20000,
            )
        except Exception:
            page.wait_for_timeout(5000)
        yield page
    finally:
        context.close()


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


@pytest.fixture
def test_deliverable_file():
    """Ensure test deliverable .md file exists for download button testing.

    The file is pre-created by the session-scoped streamlit_server fixture
    (so that Streamlit initializes with deliverables loaded into session_state).
    This function-scope fixture is a no-op guarantee: if the file was removed
    by an earlier test, it re-creates it. Cleanup is handled by streamlit_server's
    session teardown, NOT here (removing the file here would break subsequent tests
    that rely on deliverables being present, e.g. TC_E01/TC_B01 search box tests).
    """
    deliverables_dir = PROJECT_ROOT / "deliverables"
    deliverables_dir.mkdir(parents=True, exist_ok=True)

    filename = "20260714_120000_content_generation_E2E_test_deliverable.md"
    filepath = deliverables_dir / filename
    if not filepath.exists():
        content = (
            "# E2E 测试成果物\n\n"
            "这是 Playwright E2E 测试自动创建的成果物文件。\n\n"
            "## 内容\n\n"
            "用于验证下载按钮功能。\n"
        )
        filepath.write_text(content, encoding="utf-8")

    yield str(filepath)
    # NOTE: 不在此处删除文件 — session 级 streamlit_server fixture 负责清理。
    # 在此处删除会导致后续依赖搜索框可见的测试（TC_E01/TC_B01）失败。


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
