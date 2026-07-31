"""Docker 真实部署 E2E 测试.

Verify: Dockerfile 构建产物可运行、健康检查通过、端口可访问.

GAP-P0-6: 原 test_docker_deployment.py 仅静态文件检查（Dockerfile 内容扫描），
无 `docker run` + 健康检查 + 端口访问验证，Dockerfile 运行时错误无法捕获.

本文件补齐真实运行时验证：
1. docker build 成功
2. 容器启动后 /_stcore/health 返回 ok
3. 首页返回 200 + HTML
4. 容器内写入数据不污染宿主机

Run:
    pytest tests/e2e/test_docker_run_e2e.py -v           # 含慢测试
    pytest tests/e2e/test_docker_run_e2e.py -v -m "not slow"  # 跳过慢测试
"""

from __future__ import annotations

import hashlib
import socket
import subprocess
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_IMAGE_TAG = "opc-e2e-test:latest"
_CONTAINER_NAME = "opc-e2e-runner"


def _find_free_port() -> int:
    """动态分配空闲端口."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_health(url: str, timeout: float = 90.0) -> None:
    """轮询健康检查端点直到通过或超时.

    Streamlit 健康检查: GET /_stcore/health 返回 "ok"
    """
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            req = urllib.request.Request(f"{url}/_stcore/health")
            with urllib.request.urlopen(req, timeout=3) as resp:
                body = resp.read().decode().strip()
                if resp.status == 200 and body == "ok":
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(2.0)
    raise RuntimeError(
        f"Container health check failed within {timeout}s (last error: {last_error})"
    )


@contextmanager
def _docker_container(port: int) -> Generator[str, None, None]:
    """启动 Docker 容器并返回 base_url，退出时自动清理.

    Yields:
        base_url: http://127.0.0.1:<port>
    """
    # 清理同名容器（防残留）
    subprocess.run(
        ["docker", "rm", "-f", _CONTAINER_NAME],
        capture_output=True,
        timeout=10,
    )
    # 启动容器
    proc = subprocess.Popen(
        [
            "docker",
            "run",
            "--rm",
            "--name",
            _CONTAINER_NAME,
            "-p",
            f"{port}:8501",
            _IMAGE_TAG,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_health(base_url, timeout=90.0)
        yield base_url
    finally:
        subprocess.run(
            ["docker", "stop", _CONTAINER_NAME],
            capture_output=True,
            timeout=15,
        )
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="module")
def docker_image() -> str:
    """构建 Docker 镜像，返回 tag 名. 若 Docker 不可用则 skip."""
    # 检查 docker 可用
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            pytest.skip("Docker daemon not available")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("Docker not installed")

    # 构建镜像（若已存在则跳过构建）
    result = subprocess.run(
        ["docker", "images", "-q", _IMAGE_TAG],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if not result.stdout.strip():
        print(f"[Docker E2E] Building image {_IMAGE_TAG}...")
        build = subprocess.run(
            ["docker", "build", "-t", _IMAGE_TAG, str(_PROJECT_ROOT)],
            capture_output=True,
            text=True,
            timeout=600,  # 10 min
        )
        assert build.returncode == 0, (
            f"docker build 失败 (exit {build.returncode}):\n"
            f"--- stdout (last 1000 chars) ---\n{build.stdout[-1000:]}\n"
            f"--- stderr (last 1000 chars) ---\n{build.stderr[-1000:]}"
        )
    return _IMAGE_TAG


class TestDockerBuildE2E:
    """验证 Docker 镜像构建成功."""

    def test_image_built_successfully(self, docker_image):
        """Verify: docker build 产物存在."""
        result = subprocess.run(
            ["docker", "images", "-q", docker_image],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert result.stdout.strip(), f"镜像 {docker_image} 不存在"


class TestDockerRunHealthE2E:
    """验证容器启动后健康检查通过."""

    def test_container_health_check_passes(self, docker_image):
        """Verify: 容器启动后 90s 内 /_stcore/health 返回 ok.

        Side-Effect: _docker_container 内部已轮询健康检查，
        到这里说明已通过；再次显式验证确保真实可访问.
        """
        port = _find_free_port()
        with _docker_container(port) as base_url:
            req = urllib.request.Request(f"{base_url}/_stcore/health")
            with urllib.request.urlopen(req, timeout=5) as resp:
                assert resp.status == 200
                assert resp.read().decode().strip() == "ok"


class TestDockerRunHomepageE2E:
    """验证容器首页可访问."""

    def test_homepage_returns_200(self, docker_image):
        """Verify: http://127.0.0.1:<port>/ 返回 200 + HTML."""
        port = _find_free_port()
        with _docker_container(port) as base_url:
            req = urllib.request.Request(base_url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                assert resp.status == 200
                body = resp.read().decode("utf-8", errors="ignore")
                # Streamlit 首页应包含基础 HTML 结构
                assert "<html" in body.lower(), "首页未返回 HTML"
                assert "streamlit" in body.lower(), "首页未含 streamlit 标识"


class TestDockerRunIsolationE2E:
    """验证容器内数据隔离（不污染宿主机）."""

    def test_container_writes_to_volume_not_host(self, docker_image):
        """Verify: 容器内写入数据不影响宿主机 data/ 目录.

        Side-Effect: 对比容器启动前后宿主机 data/opc_data.db 的 md5,
        应保持一致（或均不存在），证明容器内写入不污染宿主机.
        """
        host_db = _PROJECT_ROOT / "data" / "opc_data.db"
        host_hash_before = (
            hashlib.md5(host_db.read_bytes()).hexdigest()
            if host_db.exists()
            else "not-exist"
        )

        port = _find_free_port()
        with _docker_container(port) as base_url:
            # 触发一次首页访问（可能初始化 DB）
            try:
                urllib.request.urlopen(base_url, timeout=10).read()
            except Exception:
                pass

        host_hash_after = (
            hashlib.md5(host_db.read_bytes()).hexdigest()
            if host_db.exists()
            else "not-exist"
        )
        assert (
            host_hash_before == host_hash_after
        ), f"宿主机 DB 被污染: before={host_hash_before}, after={host_hash_after}"
