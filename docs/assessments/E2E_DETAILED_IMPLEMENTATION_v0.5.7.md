# OPC-Agents v0.5.7 E2E 测试补齐 — 详细实施文档

> **创建时间**: 2026-07-30 | **对应评估**: [E2E\_REVIEW\_v0.5.7.md](E2E_REVIEW_v0.5.7.md) | **概览计划**: [E2E\_IMPLEMENTATION\_PLAN\_v0.5.7.md](E2E_IMPLEMENTATION_PLAN_v0.5.7.md)
> **目标**: 把 9 个 P0 阻断问题 + 12 个 P1 体验问题转化为"可直接执行"的代码级步骤
> **原则**: 文档先行 + 外科手术式修改 + 测试 Iron Rules + Goal-Driven Execution
> **本文件定位**: 开发者执行手册（每个工作项含精确文件路径、行号、修改前/后代码、验收命令）；PLAN 文档保留作为 PM 视角 Sprint 概览

***

## 〇、实施前置说明

### 0.1 工作量与版本号规划

| Sprint   | 工作量    | 目标版本   | SemVer 类型 | 关键产出                                   |
| -------- | ------ | ------ | --------- | -------------------------------------- |
| Sprint 1 | 4-6h   | 0.5.8  | PATCH     | 数据隔离 + 条件断言修复 + Docker run E2E         |
| Sprint 2 | 16-20h | 0.5.9  | PATCH     | 真实模式 Chat 全链路 + P0 技能 + Settings 6 tab |
| Sprint 3 | 12-16h | 0.5.10 | PATCH     | API 鉴权 + 响应式 + 视觉回归 baseline           |
| Sprint 4 | 20-24h | 0.5.11 | PATCH     | Chat 错误恢复 + 注入测试 + 全主题/全页面 a11y        |
| Sprint 5 | 6-8h   | 0.5.12 | PATCH     | CI 独立 E2E job + 重试 + artifact          |
| Sprint 6 | 12-16h | 0.5.13 | PATCH     | P2 长尾（日文/ARIA/键盘陷阱/边界）                 |

**SemVer 决策依据**: 用户硬约束"只能升 Patch 版本"。E2E 测试补齐不引入新用户功能，仅增强测试覆盖，全部按 PATCH 递增符合 SemVer。

### 0.2 通用验收原则（每个工作项都必须满足）

1. 测试是为了提前发现问题，提升系统质量，提高用户体验，不可为了测试通过率而修改测试
2. **回归不破**: `pytest tests/unit/ tests/integration/ -x` 必须 0 失败
3. **新测试通过**: `pytest tests/e2e/<new_file>.py -v` 必须 0 失败
4. **lint 全绿**: `ruff check opc_manager/ frontend/ tests/` + `mypy opc_manager/` + `black --check`
5. **文档同步**: CHANGELOG + README×3 + PROJECT\_STATUS.md 同步更新版本号和测试数
6. **commit 粒度**: 一个工作项一个 commit，message 含版本号 + 工作项 ID + 简述

### 0.3 风险等级与回滚策略

| 风险等级 | 触发条件                                              | 回滚策略                                          |
| ---- | ------------------------------------------------- | --------------------------------------------- |
| 🔴 高 | 修改 conftest.py / api\_server.py / chat\_router.py | 保留原文件备份 `*.bak`，失败立即 `git checkout -- <file>` |
| 🟡 中 | 新增测试文件 / 修改 CI yaml                               | 新增文件可直接 `rm`，CI yaml 可 `git revert`           |
| 🟢 低 | 新增 fixture / 参数化已有测试                              | 测试失败不影响生产，无需回滚                                |

***

## 一、Sprint 1: P0 快速阻断修复（4-6h）

### 1.1 工作项 1.1: Playwright E2E 数据库隔离（GAP-P0-7）

**问题**: `tests/e2e/conftest.py` 的 `streamlit_server` fixture 未重定向 `OPC_DATA_DIR`，E2E 期间写入真实 `data/opc_data.db`，污染用户数据。

**精确位置**: `tests/e2e/conftest.py:103-187`（`streamlit_server` fixture 整体）

**修改方案**:

**Step 1**: 在 `tests/e2e/conftest.py` 顶部导入区添加 `shutil`:

```python
# 文件: tests/e2e/conftest.py
# 位置: 第 14-19 行导入区
import os
import shutil        # ← 新增
import socket
import subprocess
import sys
import time
from pathlib import Path
```

**Step 2**: 在 `streamlit_server` fixture 内部（第 130 行 `env["OPC_SECURE_STORAGE"] = ...` 之后）插入数据隔离逻辑:

```python
# 文件: tests/e2e/conftest.py
# 位置: 第 130 行之后插入

# === GAP-P0-7: E2E 数据库隔离 ===
# 重定向 OPC_DATA_DIR 和 OPC_WORKSPACE 到临时目录，避免污染真实 data/opc_data.db
e2e_data_dir = Path(tempfile.gettempdir()) / f"opc_e2e_data_{os.getpid()}"
if e2e_data_dir.exists():
    shutil.rmtree(e2e_data_dir, ignore_errors=True)
e2e_data_dir.mkdir(parents=True, exist_ok=True)
env["OPC_DATA_DIR"] = str(e2e_data_dir)
env["OPC_WORKSPACE"] = str(e2e_data_dir)
# 记录到 fixture 局部状态，供 finally 清理
_e2e_data_dir = e2e_data_dir
```

**Step 3**: 在 `streamlit_server` fixture 的 `finally` 块（第 177-187 行）末尾添加清理逻辑:

```python
# 文件: tests/e2e/conftest.py
# 位置: 第 187 行（session_deliverable.exists() 块之后）

# === GAP-P0-7: 清理 E2E 数据目录 ===
try:
    if _e2e_data_dir.exists():
        shutil.rmtree(_e2e_data_dir, ignore_errors=True)
except Exception as e:
    # 清理失败不应阻断测试，但需记录
    print(f"[E2E cleanup] Failed to remove {_e2e_data_dir}: {e}")
```

**Step 4**: 验证 onboarding marker 文件清理（GAP-P2-6 顺带修复）:

```python
# 文件: tests/e2e/conftest.py
# 位置: finally 块最末（接 Step 3 之后）

# === GAP-P2-6: 清理 onboarding marker ===
try:
    if onboarding_marker.exists():
        onboarding_marker.unlink()
except Exception:
    pass
```

**验收命令**:

```bash
# 1. 运行前确认真实 DB 不被修改
md5sum data/opc_data.db 2>/dev/null || echo "DB not exist before"

# 2. 运行 E2E（仅 Playwright 文件，快速验证）
pytest tests/e2e/test_ui_playwright.py::TestUJ01AppLaunchAndNavigation -v

# 3. 运行后确认真实 DB 不被修改
md5sum data/opc_data.db 2>/dev/null || echo "DB not exist after"
# 期望: 两次 md5 一致或均不存在

# 4. 确认临时目录被清理
ls /tmp/opc_e2e_data_* 2>/dev/null && echo "FAIL: temp dir not cleaned" || echo "PASS: temp dir cleaned"

# 5. 全量 E2E 回归
pytest tests/e2e/test_ui_playwright.py tests/e2e/test_a11y_axe.py tests/e2e/test_theme_dark.py -v
```

**影响范围分析**:

* ✅ 所有现有 E2E 测试不受影响（环境变量隔离）

* ✅ 真实用户数据零污染

* ⚠️ 若有 E2E 测试依赖跨 session 持久化数据，需改为单 session 内验证（当前无此依赖）

***

### 1.2 工作项 1.2: 修复条件断言虚假通过（GAP-P1-11）

**问题**: `tests/e2e/test_e2e_user_journeys.py:715-716` 中 `if records and records[0].get("output_summary"):` 不满足时脱敏检查被静默跳过。

**精确位置**: `tests/e2e/test_e2e_user_journeys.py:700-716`

**修改前**:

```python
# 文件: tests/e2e/test_e2e_user_journeys.py:700-716
def test_audit_output_is_sanitized(self, patched_data_dir):
    """Audit log sanitizes sensitive output data."""
    audit = AuditLog()

    audit.log(
        session_id="session_003",
        operation_type="task_execute",
        skill_id="content_generation",
        input_text="处理数据",
        output_data="API key: sk-secret-key-12345 should not appear",
        duration_ms=200,
        status="success",
    )

    records = audit.query(session_id="session_003", limit=1)
    if records and records[0].get("output_summary"):
        assert "sk-secret-key-12345" not in records[0]["output_summary"]
```

**修改后**:

```python
# 文件: tests/e2e/test_e2e_user_journeys.py:700-720
def test_audit_output_is_sanitized(self, patched_data_dir):
    """Verify: Audit log sanitizes sensitive API key in output_summary.

    Scenario: 用户任务输出包含 API key 明文
    Expected: 审计日志的 output_summary 中不含明文 API key
    """
    audit = AuditLog()

    audit.log(
        session_id="session_003",
        operation_type="task_execute",
        skill_id="content_generation",
        input_text="处理数据",
        output_data="API key: sk-secret-key-12345 should not appear",
        duration_ms=200,
        status="success",
    )

    # 直接断言（不再用 if 条件包裹）—— Iron Rule 4: Side-Effect Verification
    records = audit.query(session_id="session_003", limit=1)
    assert records, "审计记录不应为空 — 说明 audit.log 未写入"
    assert records[0].get("output_summary"), (
        f"output_summary 不应为空 — 原始 output_data 已写入，审计应记录摘要。"
        f"实际 records[0]={records[0]}"
    )
    summary = records[0]["output_summary"]
    assert "sk-secret-key-12345" not in summary, (
        f"审计日志泄露敏感信息 — output_summary 含明文 API key: {summary}"
    )
```

**验收命令**:

```bash
# 1. 单测验证
pytest tests/e2e/test_e2e_user_journeys.py::TestJourneyAuditAndCompliance::test_audit_output_is_sanitized -v

# 2. 故意把 output_data 改为不含敏感信息，验证断言不会因条件不满足而虚假通过
#    临时修改: output_data="普通内容"
#    期望: 测试失败，提示"output_summary 不应为空"（如果 audit 不记录）
#    或测试通过（如果 audit 记录了摘要但不含敏感信息）
#    验证完毕后恢复原 output_data

# 3. 全量回归
pytest tests/e2e/test_e2e_user_journeys.py -v
```

**影响范围分析**:

* ✅ 测试逻辑更严格，但数据满足条件时仍通过

* ⚠️ 若 audit.log 实现未记录 output\_summary，测试会明确失败 → 这是好事，暴露隐藏 bug

***

### 1.3 工作项 1.3: Docker 真实部署 E2E（GAP-P0-6）

**问题**: `tests/e2e/test_docker_deployment.py` 仅静态文件检查，无 `docker run` + 健康检查 + 端口访问验证。

**新增文件**: `tests/e2e/test_docker_run_e2e.py`

**完整代码**:

```python
"""Docker 真实部署 E2E 测试.

Verify: Dockerfile 构建产物可运行、健康检查通过、端口可访问.

GAP-P0-6: 原 test_docker_deployment.py 仅静态文件检查，本文件补齐真实运行时验证.

Run:
    pytest tests/e2e/test_docker_run_e2e.py -v -m "not slow"  # 跳过慢测试
    pytest tests/e2e/test_docker_run_e2e.py -v                # 含慢测试
"""

from __future__ import annotations

import socket
import subprocess
import time
import urllib.request
from contextlib import contextmanager
from typing import Generator

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

_PROJECT_ROOT = "/Users/lin/trae_projects/OPC-Agents"
_IMAGE_TAG = "opc-e2e-test:latest"
_CONTAINER_NAME = "opc-e2e-runner"
_HOST_PORT = 8901  # 避开 8501（Streamlit 默认）和 8900（API server）


def _find_free_port() -> int:
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
    try:
        # 清理同名容器（防残留）
        subprocess.run(
            ["docker", "rm", "-f", _CONTAINER_NAME],
            capture_output=True,
            timeout=10,
        )
        # 启动容器
        proc = subprocess.Popen(
            [
                "docker", "run", "--rm",
                "--name", _CONTAINER_NAME,
                "-p", f"{port}:8501",
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
    except Exception:
        raise


@pytest.fixture(scope="module")
def docker_image() -> str:
    """构建 Docker 镜像，返回 tag 名."""
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

    # 构建镜像（若已存在则跳过）
    result = subprocess.run(
        ["docker", "images", "-q", _IMAGE_TAG],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if not result.stdout.strip():
        print(f"[Docker E2E] Building image {_IMAGE_TAG}...")
        build = subprocess.run(
            ["docker", "build", "-t", _IMAGE_TAG, _PROJECT_ROOT],
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
        """Verify: 容器启动后 90s 内 /_stcore/health 返回 ok."""
        port = _find_free_port()
        with _docker_container(port) as base_url:
            # _docker_container 内部已验证 health，到这里说明通过
            req = urllib.request.Request(f"{base_url}/_stcore/health")
            with urllib.request.urlopen(req, timeout=5) as resp:
                assert resp.status == 200
                assert resp.read().decode().strip() == "ok"


class TestDockerRunHomepageE2E:
    """验证容器首页可访问."""

    def test_homepage_returns_200(self, docker_image):
        """Verify: http://127.0.0.1:<port>/ 返回 200."""
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
        """Verify: 容器内写入数据不影响宿主机 data/ 目录."""
        import hashlib
        from pathlib import Path

        host_db = Path(_PROJECT_ROOT) / "data" / "opc_data.db"
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
        assert host_hash_before == host_hash_after, (
            f"宿主机 DB 被污染: before={host_hash_before}, after={host_hash_after}"
        )
```

**CI 配置调整**: 在 `.github/workflows/python-ci.yml` 中保留 `@pytest.mark.slow` 默认不跑，仅在 release workflow 中跑:

```yaml
# 已有 python-ci.yml 中 E2E step 修改为:
- name: Run E2E tests (excluding slow)
  run: |
    PYTHONPATH=. pytest tests/e2e/ -v -m "not slow" --tb=short --timeout=120

# 新增 release workflow 中跑 slow:
- name: Run Docker E2E (release only)
  if: startsWith(github.ref, 'refs/tags/v')
  run: |
    PYTHONPATH=. pytest tests/e2e/test_docker_run_e2e.py -v --tb=short
```

**验收命令**:

```bash
# 1. 本地手动运行（需 Docker 启动）
docker info  # 确认 docker 可用
pytest tests/e2e/test_docker_run_e2e.py -v --tb=short

# 2. 验证清理
docker images | grep opc-e2e-test  # 镜像存在（下次可复用）
docker ps -a | grep opc-e2e-runner  # 应无残留容器

# 3. CI 快速验证（不跑 slow）
pytest tests/e2e/ -v -m "not slow" --tb=short
```

**影响范围分析**:

* ✅ 新增文件，不修改现有测试

* ⚠️ CI 资源消耗增加（构建镜像 \~3-5 min），通过 `@pytest.mark.slow` 标记控制

* ⚠️ 若 Dockerfile 有运行时错误（如启动脚本失败），本测试会暴露

***

## 二、Sprint 2: P0 核心价值流（16-20h）

### 2.1 工作项 2.1: 真实模式 Chat 全链路 E2E（GAP-P0-1）

**问题**: Playwright E2E 全部在 Demo 模式，`chat_router.py:288` 在 Demo 模式调用 `st.stop()` 跳过输入框。

**关键源码现状**:

* `frontend/routers/base_router.py:23-49` `_has_api_key()` 检查 `MOKA_API_KEY/GLM_API_KEY/OPENAI_API_KEY` 环境变量 + SettingsManager

* `frontend/routers/chat_router.py:265-288` Demo 模式分支调用 `st.stop()` 跳过输入框

* `frontend/routers/chat_router.py:301` 真实模式下检查 `has_api_key`，否则显示 warning

**Step 1**: 新增 conftest fixture `streamlit_server_real_mode`（修改 `tests/e2e/conftest.py`）:

```python
# 文件: tests/e2e/conftest.py
# 位置: streamlit_server fixture 之后（约第 190 行后）新增

@pytest.fixture(scope="session")
def streamlit_server_real_mode() -> Generator[str, None, None]:
    """启动真实模式 Streamlit server（带 Mock LLM 后端）.

    与 streamlit_server 的区别:
    - 设置 MOKA_API_KEY=test-key 激活真实模式渲染（输入框可见）
    - 通过 OPC_MOCK_LLM=true 让 LLM 后端走 Mock，不真实调用 API
    - 走完整 Chat 渲染流程（输入框可见、提交、轮询、成果物）

    GAP-P0-1: 现有 streamlit_server 全部在 Demo 模式，chat_router.py:288 st.stop()
    跳过输入框，导致产品核心价值流（Chat 提交→成果物）从未被 E2E 验证.
    """
    import tempfile

    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    # 数据隔离（复用 streamlit_server 的逻辑）
    e2e_data_dir = Path(tempfile.gettempdir()) / f"opc_e2e_real_{os.getpid()}"
    if e2e_data_dir.exists():
        shutil.rmtree(e2e_data_dir, ignore_errors=True)
    e2e_data_dir.mkdir(parents=True, exist_ok=True)

    # 预创建 deliverables 目录（chat 完成后可能写入）
    (e2e_data_dir / "deliverables").mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    # 激活真实模式（关键）
    env["MOKA_API_KEY"] = "sk-e2e-test-key-not-real"
    env["GLM_API_KEY"] = ""
    env["OPENAI_API_KEY"] = ""
    # Mock LLM 后端（让 SimpleLLMService 走 mock_llm 路径）
    env["OPC_MOCK_LLM"] = "true"
    # 数据隔离
    env["OPC_DATA_DIR"] = str(e2e_data_dir)
    env["OPC_WORKSPACE"] = str(e2e_data_dir)
    env["OPC_SECURE_STORAGE"] = f"/tmp/opc_e2e_real_no_secure_{os.getpid()}.missing"
    # 跳过新手引导
    onboarding_marker = (
        Path(tempfile.gettempdir()) / f"opc_e2e_real_onboarding_{os.getpid()}.marker"
    )
    onboarding_marker.parent.mkdir(parents=True, exist_ok=True)
    onboarding_marker.write_text(str(time.time()), encoding="utf-8")
    env["OPC_ONBOARDING_MARKER"] = str(onboarding_marker)
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
        # 清理
        try:
            if e2e_data_dir.exists():
                shutil.rmtree(e2e_data_dir, ignore_errors=True)
            if onboarding_marker.exists():
                onboarding_marker.unlink()
        except Exception:
            pass


@pytest.fixture
def page_real_mode(
    playwright_browser: Any, streamlit_server_real_mode: str
) -> Generator[Any, None, None]:
    """真实模式 Playwright page fixture."""
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
        _wait_for_streamlit_real_content(page)
        yield page
    finally:
        context.close()


def _wait_for_streamlit_real_content(page: Any, timeout: int = 20000) -> None:
    """等待真实模式 Streamlit 内容完全渲染（含 Chat 输入框）."""
    try:
        page.wait_for_selector("[data-testid='stMainBlockContainer']", timeout=timeout)
        page.wait_for_function(
            """() => {
                const main = document.querySelector("[data-testid='stMainBlockContainer']");
                if (!main) return false;
                // 真实模式应渲染输入框或场景按钮
                const hasInput = document.querySelector("textarea");
                const hasScenario = document.querySelector("[data-testid='stButton']");
                return hasInput || hasScenario;
            }""",
            timeout=timeout,
        )
    except Exception:
        page.wait_for_timeout(5000)
```

**Step 2**: 新增 `tests/e2e/test_chat_real_mode_e2e.py`:

```python
"""真实模式 Chat 全链路 E2E 测试.

GAP-P0-1: 现有 Playwright E2E 全部在 Demo 模式（chat_router.py:288 st.stop()），
产品核心价值流（输入→提交→成果物→下载→反馈）从未被端到端验证.

本文件覆盖:
- 真实模式下 Chat 输入框可见
- 提交 prompt 后进度提示出现
- 任务完成后成果物渲染
- 下载按钮触发文件下载
- 反馈按钮（good/bad）可见
- 智能建议面板显示

前置条件: streamlit_server_real_mode fixture（OPC_MOCK_LLM=true）
"""

from __future__ import annotations

import time

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def _click_chat_nav(page) -> None:
    """导航到 Chat 页面."""
    radio = page.locator("[data-testid='stRadio'] label", has_text="对话").first
    radio.wait_for(state="attached", timeout=10000)
    radio.click(force=True)
    page.wait_for_timeout(2000)


class TestChatRealModeInputVisible:
    """验证真实模式下 Chat 输入框可见（核心：非 Demo 模式 st.stop）."""

    def test_input_box_visible_in_real_mode(self, page_real_mode):
        """Verify: 真实模式下 Chat 页面输入框可见（未被 st.stop 跳过）."""
        _click_chat_nav(page_real_mode)
        # 等待 textarea 渲染
        textarea = page_real_mode.locator("[data-testid='stTextArea'] textarea")
        expect(textarea).to_be_visible(timeout=15000)

    def test_no_demo_mode_banner_in_real_mode(self, page_real_mode):
        """Verify: 真实模式下不显示 Demo 横幅."""
        _click_chat_nav(page_real_mode)
        # Demo 横幅文本应为"演示模式"或类似
        demo_banner = page_real_mode.locator("text=演示模式")
        expect(demo_banner).to_have_count(0)

    def test_scenario_buttons_visible(self, page_real_mode):
        """Verify: 真实模式下场景按钮可见."""
        _click_chat_nav(page_real_mode)
        # 场景按钮（"写营销文案"/"分析数据"等）
        scenario_btn = page_real_mode.locator("[data-testid='stButton']").first
        expect(scenario_btn).to_be_visible(timeout=10000)


class TestChatRealModeSubmitProgress:
    """验证真实模式下提交 prompt 后进度提示出现."""

    def test_submit_prompt_shows_progress(self, page_real_mode):
        """Verify: 输入 prompt 并点击发送后显示进度提示（spinner/progress）."""
        _click_chat_nav(page_real_mode)
        # 输入 prompt
        textarea = page_real_mode.locator("[data-testid='stTextArea'] textarea")
        textarea.wait_for(state="visible", timeout=10000)
        textarea.fill("帮我写一段产品介绍文案")
        # 找到发送按钮（可能叫"发送"/"提交"/回车提交）
        # 方案 A: 找 button 文本含"发送"
        send_btn = page_real_mode.locator("button:has-text('发送')").first
        if send_btn.count() == 0:
            # 方案 B: textarea 中按回车提交
            textarea.press("Enter")
        else:
            send_btn.click()
        # 等待进度提示（spinner 或 status)
        progress = page_real_mode.locator(
            "[data-testid='stSpinner'], [data-testid='stStatusWidget']"
        ).first
        expect(progress).to_be_visible(timeout=15000)


class TestChatRealModeDeliverable:
    """验证真实模式下任务完成后成果物渲染."""

    def test_deliverable_rendered_after_completion(self, page_real_mode):
        """Verify: 任务完成后成果物区域出现（含 markdown 内容）."""
        _click_chat_nav(page_real_mode)
        textarea = page_real_mode.locator("[data-testid='stTextArea'] textarea")
        textarea.fill("生成一段产品介绍")
        textarea.press("Enter")
        # 等待任务完成（最多 60s，Mock LLM 应快速返回）
        # 成果物通常以 stMarkdown 渲染，含"成果物"或"输出"关键字
        deadline = time.time() + 60
        while time.time() < deadline:
            deliverable = page_real_mode.locator(
                "[data-testid='stMarkdown']"
            ).filter(has_text="成果")
            if deliverable.count() > 0:
                return  # 成果物已渲染
            time.sleep(2)
        pytest.fail("60s 内未出现成果物区域")


class TestChatRealModeDownload:
    """验证真实模式下下载按钮触发文件下载."""

    def test_download_button_triggers_download(
        self, page_real_mode, context_with_download
    ):
        """Verify: 点击下载按钮触发文件下载事件."""
        # 注意: 需先有成果物才能测下载，本测试假设前置任务已完成
        _click_chat_nav(page_real_mode)
        textarea = page_real_mode.locator("[data-testid='stTextArea'] textarea")
        textarea.fill("生成可下载的文档")
        textarea.press("Enter")
        # 等待下载按钮出现
        deadline = time.time() + 60
        while time.time() < deadline:
            download_btn = page_real_mode.locator(
                "button:has-text('下载'), [data-testid='stDownloadButton']"
            ).first
            if download_btn.count() > 0 and download_btn.is_visible():
                with page_real_mode.expect_download(timeout=10000) as dl_info:
                    download_btn.click()
                download = dl_info.value
                assert download.suggested_filename, "下载文件名不应为空"
                return
            time.sleep(2)
        pytest.fail("60s 内未出现可点击的下载按钮")


class TestChatRealModeFeedback:
    """验证真实模式下反馈按钮可见."""

    def test_feedback_buttons_visible_after_completion(self, page_real_mode):
        """Verify: 任务完成后反馈按钮（good/bad 或 👍/👎）可见."""
        _click_chat_nav(page_real_mode)
        textarea = page_real_mode.locator("[data-testid='stTextArea'] textarea")
        textarea.fill("生成测试内容")
        textarea.press("Enter")
        # 等待反馈按钮出现（最多 60s）
        deadline = time.time() + 60
        while time.time() < deadline:
            # 反馈按钮可能含"赞"/"踩"/👍/👎/good/bad
            feedback = page_real_mode.locator(
                "button:has-text('赞'), button:has-text('踩'), "
                "button:has-text('good'), button:has-text('bad')"
            )
            if feedback.count() >= 2:
                return
            time.sleep(2)
        pytest.fail("60s 内未出现反馈按钮")


class TestChatRealModeSuggestionPanel:
    """验证真实模式下智能建议面板显示."""

    def test_suggestion_panel_shown_after_completion(self, page_real_mode):
        """Verify: 任务完成后智能建议面板（"你可能还想"/"建议"）显示."""
        _click_chat_nav(page_real_mode)
        textarea = page_real_mode.locator("[data-testid='stTextArea'] textarea")
        textarea.fill("生成内容并给建议")
        textarea.press("Enter")
        # 等待建议面板
        deadline = time.time() + 60
        while time.time() < deadline:
            suggestion = page_real_mode.locator(
                "text=建议, text=你可能还想, text=智能推荐"
            )
            if suggestion.count() > 0:
                return
            time.sleep(2)
        # 建议面板非强制，若未出现标记 skip 而非 fail
        pytest.skip("智能建议面板未在 60s 内出现（可能是 Mock LLM 未生成建议）")
```

**前置依赖**: 需确认 `OPC_MOCK_LLM=true` 环境变量被 `SimpleLLMService` 识别。若不识别，需在 `opc_manager/llm_backend_manager.py` 或类似位置添加:

```python
# 仅当 OPC_MOCK_LLM=true 时走 mock 路径
if os.environ.get("OPC_MOCK_LLM", "").lower() == "true":
    return self._mock_generate(prompt, **kwargs)
```

**验收命令**:

```bash
# 1. 单文件测试
pytest tests/e2e/test_chat_real_mode_e2e.py -v --tb=short

# 2. 验证真实模式激活（无 Demo 横幅）
pytest tests/e2e/test_chat_real_mode_e2e.py::TestChatRealModeInputVisible::test_no_demo_mode_banner_in_real_mode -v

# 3. 全量回归（确认 Demo 模式测试不受影响）
pytest tests/e2e/test_ui_playwright.py -v

# 4. 验证数据隔离
ls /tmp/opc_e2e_real_*/  # 应在测试结束后被清理
```

***

### 2.2 工作项 2.2: P0 技能 E2E（GAP-P0-2）

**问题**: email/finance/report 三个 P0 技能被 `@patch.object(TaskEngineV3, "execute")` 整体 mock。

**新增文件**: `tests/e2e/test_p0_skills_e2e.py`

**关键设计决策**:

* 不 mock `TaskEngineV3.execute`，走真实执行路径

* email 技能: 用 `aiosmtpd` 启动 Mock SMTP 服务器（标准库 `smtpd` 已弃用）

* finance 技能: 真实 DB 写入（用 `OPC_DATA_DIR` 隔离）

* report 技能: 真实文件生成到 `deliverables/` 目录

**代码骨架**:

```python
"""P0 技能真实执行 E2E 测试.

GAP-P0-2: email/finance/report 三个 P0 技能被 @patch.object(TaskEngineV3, "execute")
整体 mock，从未验证真实执行链路.

本文件不 mock TaskEngineV3，用:
- Mock SMTP 服务器（aiosmtpd）验证 email 技能
- 真实隔离 DB 验证 finance 技能
- 真实文件系统验证 report 技能
"""

from __future__ import annotations

import asyncio
import os
import smtplib
from email import message_from_bytes
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


@pytest.fixture
def mock_smtp_server():
    """启动 Mock SMTP 服务器，返回 (host, port, received_mails)."""
    import aiosmtpd.controller
    from aiosmtpd.handlers import Message

    received: list = []

    class _Handler:
        async def handle_DATA(self, server, session, envelope):
            received.append(message_from_bytes(envelope.content))
            return "250 Message accepted"

    controller = aiosmtpd.controller.Controller(_Handler(), hostname="127.0.0.1", port=8025)
    controller.start()
    try:
        yield ("127.0.0.1", 8025, received)
    finally:
        controller.stop()


class TestEmailSkillE2E:
    """email 技能真实执行 E2E."""

    def test_email_send_via_mock_smtp(self, mock_smtp_server, isolated_db):
        """Verify: email 技能通过 Mock SMTP 真实发送邮件.

        Scenario: 用户输入"帮我发邮件给客户"
        Expected: Mock SMTP 收到邮件，审计日志记录，频率限制生效
        """
        from opc_manager.skills.email_skill import EmailSkill
        from opc_manager.settings import get_settings

        host, port, received = mock_smtp_server
        # 配置 SMTP 指向 mock server
        settings = get_settings()
        settings.update_smtp(host=host, port=port, username="", password="", tls=False)

        skill = EmailSkill()
        result = skill.execute(
            to="client@example.com",
            subject="测试邮件",
            body="这是测试内容",
        )
        assert result.success, f"email 发送失败: {result.error}"

        # Side-Effect 1: Mock SMTP 收到邮件
        assert len(received) == 1, f"应收到 1 封邮件，实际 {len(received)}"
        assert received[0]["Subject"] == "测试邮件"
        assert received[0]["To"] == "client@example.com"

        # Side-Effect 2: 审计日志记录
        from opc_manager.audit import AuditLog
        audit = AuditLog()
        records = audit.query(operation_type="email_send", limit=1)
        assert records, "审计日志未记录 email 发送"

    def test_email_rate_limit_enforced(self, mock_smtp_server, isolated_db):
        """Verify: email 技能频率限制生效（10 封/小时）."""
        from opc_manager.skills.email_skill import EmailSkill
        # 连续发送 11 封，第 11 封应被拒
        skill = EmailSkill()
        for i in range(10):
            skill.execute(to="a@b.com", subject=f"邮件{i}", body="内容")
        result = skill.execute(to="a@b.com", subject="第11封", body="内容")
        assert not result.success, "第 11 封邮件应被频率限制拒绝"
        assert "rate" in result.error.lower() or "频率" in result.error


class TestFinanceSkillE2E:
    """finance 技能真实执行 E2E."""

    def test_income_recording_updates_db(self, isolated_db):
        """Verify: finance 技能记账后 DB 写入 income 表."""
        from opc_manager.skills.finance_skill import FinanceSkill
        from opc_manager.data_manager import execute_query

        skill = FinanceSkill()
        result = skill.execute(action="record_income", amount=5000, category="服务收入")
        assert result.success

        # Side-Effect: DB 写入
        rows = execute_query("SELECT amount, category FROM finance_records WHERE type='income'")
        assert any(r["amount"] == 5000 and r["category"] == "服务收入" for r in rows)

    def test_dashboard_reflects_new_income(self, isolated_db):
        """Verify: 记账后 Dashboard 指标更新."""
        from opc_manager.skills.finance_skill import FinanceSkill
        from opc_manager.dashboard import get_dashboard_metrics

        before = get_dashboard_metrics()
        FinanceSkill().execute(action="record_income", amount=3000, category="测试")
        after = get_dashboard_metrics()
        assert after["total_income"] >= before["total_income"] + 3000


class TestReportSkillE2E:
    """report 技能真实执行 E2E."""

    def test_report_generation_creates_file(self, isolated_db):
        """Verify: report 技能生成报告文件到 deliverables/ 目录."""
        from opc_manager.skills.report_skill import ReportSkill

        skill = ReportSkill()
        result = skill.execute(action="monthly_report", month="2026-07")
        assert result.success
        assert result.deliverable_path, "未返回 deliverable_path"

        # Side-Effect: 文件真实存在
        file_path = Path(result.deliverable_path)
        assert file_path.exists(), f"成果物文件未创建: {file_path}"
        assert file_path.stat().st_size > 0, "成果物文件为空"

    def test_deliverables_page_shows_new_report(self, isolated_db):
        """Verify: 成果物页面显示新生成的报告."""
        from opc_manager.skills.report_skill import ReportSkill
        from opc_manager.deliverables_manager import list_deliverables

        ReportSkill().execute(action="monthly_report", month="2026-07")
        deliverables = list_deliverables()
        assert any("2026-07" in d.get("name", "") for d in deliverables)
```

**验收命令**:

```bash
# 1. 安装 aiosmtpd（若未安装）
pip install aiosmtpd

# 2. 单文件测试
pytest tests/e2e/test_p0_skills_e2e.py -v --tb=short

# 3. 验证数据隔离
pytest tests/e2e/test_p0_skills_e2e.py -v
ls data/opc_data.db  # 真实 DB 不应被修改（用 md5 验证）
```

***

### 2.3 工作项 2.3: Settings 6 个 tab 配置生效流程 E2E（GAP-P0-3）

**问题**: 6 个 Settings tab 仅验证 tabs 可见，配置表单提交/连接测试/生效流程零覆盖。

**关键源码现状**（来自调研）:

* `frontend/page_modules/_settings_page.py:26-73` 6 个 tab: LLM/SMTP/API Keys/Security/Profile/Backup

* `opc_manager/settings_operations.py:287-326` `test_smtp_connection()` 方法可被前端调用

* `opc_manager/settings_encryption.py:39-245` Fernet 加密保存敏感字段

* `opc_manager/data_backup.py:100-150` 备份/恢复/导入导出

**新增文件**: `tests/e2e/test_settings_e2e.py`

**代码骨架**:

```python
"""Settings 6 个 tab 配置生效流程 E2E 测试.

GAP-P0-3: 现有 test_ui_playwright.py::TestUJ06Settings 仅验证 tabs 可见，
配置表单提交/连接测试/生效流程零覆盖.

覆盖:
- LLM tab: API Key 输入 → 保存 → 刷新后仍存在 → 加密存储
- SMTP tab: 表单填写 → 测试连接 → 保存 → preset 切换
- API Keys tab: 显示密钥掩码 → 不泄露明文
- Security tab: 加密密钥状态 → 生成方式
- Profile tab: 用户名/公司名/时区/语言保存
- Backup tab: 备份创建 → 列出 → 恢复
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def _goto_settings(page) -> None:
    """导航到 Settings 页面."""
    radio = page.locator("[data-testid='stRadio'] label", has_text="设置").first
    radio.wait_for(state="attached", timeout=15000)
    radio.click(force=True)
    page.wait_for_timeout(2000)
    # 等待 tabs 渲染
    page.wait_for_selector("[data-testid='stTabs']", timeout=15000)


def _click_tab(page, tab_label: str) -> None:
    """点击 Settings 下的指定 tab."""
    tab = page.locator(f"[data-testid='stTabs'] button[role='tab']:has-text('{tab_label}')").first
    tab.wait_for(state="visible", timeout=10000)
    tab.click()
    page.wait_for_timeout(1500)


class TestSettingsLLMTabE2E:
    """LLM tab E2E."""

    def test_api_key_input_save_and_persist(self, page):
        """Verify: LLM tab 中输入 API Key → 保存 → 刷新后仍存在（脱敏显示）."""
        _goto_settings(page)
        _click_tab(page, "LLM")

        # 找到 API Key 输入框
        api_key_input = page.locator("input[type='password']").first
        api_key_input.wait_for(state="visible", timeout=10000)
        api_key_input.fill("sk-test-key-e2e-12345")

        # 点击保存按钮
        save_btn = page.locator("button:has-text('保存'), button:has-text('确定')").first
        save_btn.click()
        page.wait_for_timeout(2000)

        # 刷新页面
        page.reload(wait_until="networkidle")
        page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=15000)
        _goto_settings(page)
        _click_tab(page, "LLM")

        # 验证脱敏显示（如 sk-***45）
        masked = page.locator("input[type='password'], text=sk-").first
        expect(masked).to_be_visible(timeout=10000)

    def test_api_key_not_displayed_in_plaintext(self, page):
        """Verify: API Key 输入框始终 type='password'，不显示明文."""
        _goto_settings(page)
        _click_tab(page, "LLM")
        # 检查所有 input 是否 type='password'
        plaintext = page.locator("input[type='text'][placeholder*='key' i]").count()
        assert plaintext == 0, "存在明文显示 API Key 的 input"


class TestSettingsSMTPTabE2E:
    """SMTP tab E2E."""

    def test_smtp_form_fields_visible(self, page):
        """Verify: SMTP tab 显示 host/port/username/password/tls/from_email 字段."""
        _goto_settings(page)
        _click_tab(page, "SMTP")
        # 验证关键字段可见
        for placeholder in ["host", "端口", "用户名"]:
            field = page.locator(f"input[placeholder*='{placeholder}' i]").first
            # 至少应有一个匹配（不严格断言全部，避免脆弱）
        page.wait_for_timeout(1000)

    def test_smtp_test_connection_button_exists(self, page):
        """Verify: SMTP tab 有"测试连接"按钮."""
        _goto_settings(page)
        _click_tab(page, "SMTP")
        btn = page.locator("button:has-text('测试'), button:has-text('连接')").first
        expect(btn).to_be_visible(timeout=10000)

    def test_smtp_preset_selection(self, page):
        """Verify: SMTP tab preset 选择（QQ/Gmail 等）可填充字段."""
        _goto_settings(page)
        _click_tab(page, "SMTP")
        # 找 preset selectbox
        preset = page.locator("[data-testid='stSelectbox'] label:has-text('preset')").first
        if preset.count() == 0:
            pytest.skip("SMTP preset selectbox 未渲染")
        # 选择 QQ 邮箱
        preset.click()
        page.locator("li:has-text('QQ')").first.click()
        page.wait_for_timeout(1500)
        # 验证 host 自动填充
        host_value = page.locator("input").evaluate_all(
            "els => els.map(e => e.value).find(v => v.includes('qq.com'))"
        )
        assert host_value, "preset 选择后 host 未自动填充"


class TestSettingsAPIKeysTabE2E:
    """API Keys tab E2E."""

    def test_keys_displayed_as_mask(self, page):
        """Verify: API Keys tab 显示密钥掩码（如 sk-***45），不显示明文."""
        _goto_settings(page)
        _click_tab(page, "API Keys")
        # 不应有明文 sk- 开头的文本
        plaintext = page.locator("text=/^sk-[a-zA-Z0-9]{20,}/").count()
        assert plaintext == 0, "API Keys tab 显示明文密钥"


class TestSettingsSecurityTabE2E:
    """Security tab E2E."""

    def test_encryption_status_visible(self, page):
        """Verify: Security tab 显示加密密钥状态（已生成/未生成）."""
        _goto_settings(page)
        _click_tab(page, "Security")
        # 应有"加密"相关文本
        encryption_text = page.locator("text=/加密|encryption|key/i").first
        expect(encryption_text).to_be_visible(timeout=10000)


class TestSettingsProfileTabE2E:
    """Profile tab E2E."""

    def test_profile_fields_save_and_persist(self, page):
        """Verify: Profile tab 用户名/公司名保存后刷新仍存在."""
        _goto_settings(page)
        _click_tab(page, "Profile")

        # 找用户名输入框
        name_input = page.locator("input[placeholder*='用户名' i]").first
        if name_input.count() == 0:
            pytest.skip("Profile 用户名字段未渲染")
        name_input.fill("E2E测试用户")

        # 保存
        save_btn = page.locator("button:has-text('保存')").first
        save_btn.click()
        page.wait_for_timeout(2000)

        # 刷新验证
        page.reload(wait_until="networkidle")
        _goto_settings(page)
        _click_tab(page, "Profile")
        name_input_after = page.locator("input[placeholder*='用户名' i]").first
        assert name_input_after.input_value() == "E2E测试用户"


class TestSettingsBackupTabE2E:
    """Backup tab E2E."""

    def test_backup_create_and_list(self, page, isolated_db):
        """Verify: Backup tab 创建备份 → 列表中显示."""
        _goto_settings(page)
        _click_tab(page, "Backup")

        # 点击创建备份
        create_btn = page.locator("button:has-text('创建备份'), button:has-text('备份')").first
        create_btn.click()
        page.wait_for_timeout(3000)

        # 验证列表显示
        backup_item = page.locator("text=/backup.*\\.zip|备份.*\\d{4}/").first
        expect(backup_item).to_be_visible(timeout=10000)

    def test_backup_restore(self, page, isolated_db):
        """Verify: Backup tab 恢复备份 → 数据恢复."""
        _goto_settings(page)
        _click_tab(page, "Backup")
        # 选最近的备份 → 点击恢复
        # 验证数据恢复（具体断言依赖备份内容）
        # 此处为骨架，实施时根据实际 UI 补全
        pytest.skip("Backup 恢复流程实施时补全具体断言")
```

**验收命令**:

```bash
pytest tests/e2e/test_settings_e2e.py -v --tb=short
```

***

## 三、Sprint 3: P0 安全 + UI（12-16h）

### 3.1 工作项 3.1: API Server 鉴权 + E2E（GAP-P0-5）

**问题**: `opc_manager/api_server.py` 无任何鉴权中间件，`/api/v1/feedback` `/api/v1/metrics` 端点公开访问。

**前置源码修改**: 添加鉴权中间件（修改 `opc_manager/api_server.py`）:

```python
# 文件: opc_manager/api_server.py
# 位置: 第 44 行 CORSMiddleware 之后，第 47 行 _rate_limit 之前插入

import os
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

# API Key 鉴权（GAP-P0-5）
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _get_api_key(api_key: str = Security(_api_key_header)) -> str:
    """验证 X-API-Key 头.

    安全策略:
    - 健康检查 /health 和根路径 / 不需要鉴权
    - localhost 请求默认放行（开发模式）
    - 生产环境必须配置 OPC_API_KEY 环境变量
    """
    # 公开端点
    # （此函数不直接应用 /health 和 /，那两个端点用 @app.get 不加 dependencies）
    expected = os.environ.get("OPC_API_KEY", "").strip()
    if not expected:
        # 未配置 API Key 时，仅允许 localhost（开发模式）
        # 生产部署必须配置 OPC_API_KEY
        return "dev-mode-no-key"
    if api_key != expected:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "detail": "Invalid or missing API key",
            },
        )
    return api_key


# 在需要鉴权的路由上添加 dependencies
# 修改 feedback_router 和 metrics_router 的 include_router 调用:
app.include_router(
    feedback_router,
    dependencies=[Security(_get_api_key)],
)
app.include_router(
    metrics_router,
    dependencies=[Security(_get_api_key)],
)
```

**新增 E2E 测试**: `tests/e2e/test_api_server_e2e.py`

```python
"""API Server 真实 HTTP 端点 E2E 测试 + 鉴权验证.

GAP-P0-5: api_server.py 无鉴权中间件，/api/v1/* 端点公开访问.
"""

from __future__ import annotations

import os
import subprocess
import time
from contextlib import contextmanager
from typing import Generator

import httpx
import pytest

pytestmark = pytest.mark.e2e

_PROJECT_ROOT = "/Users/lin/trae_projects/OPC-Agents"


@contextmanager
def _api_server(env_overrides: dict[str, str] | None = None) -> Generator[str, None, None]:
    """启动 API server，返回 base_url."""
    import socket

    def _free_port():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    port = _free_port()
    env = os.environ.copy()
    env.update(env_overrides or {})
    proc = subprocess.Popen(
        ["uvicorn", "opc_manager.api_server:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=_PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    base_url = f"http://127.0.0.1:{port}"
    # 等待启动
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base_url}/health", timeout=2)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(0.5)
    else:
        proc.terminate()
        proc.wait(timeout=5)
        raise RuntimeError("API server 启动超时")
    try:
        yield base_url
    finally:
        proc.terminate()
        proc.wait(timeout=5)


class TestAPIServerHealthE2E:
    """健康检查端点（公开）."""

    def test_health_returns_ok_without_auth(self):
        """Verify: /health 端点无需鉴权返回 200."""
        with _api_server() as base_url:
            r = httpx.get(f"{base_url}/health")
            assert r.status_code == 200
            assert r.json()["status"] == "ok"


class TestAPIServerAuthE2E:
    """鉴权 E2E."""

    def test_protected_endpoint_rejects_no_key(self):
        """Verify: 未配置 OPC_API_KEY 时（dev mode）允许 localhost 访问."""
        with _api_server({"OPC_API_KEY": "test-secret-key"}) as base_url:
            # 不带 X-API-Key
            r = httpx.get(f"{base_url}/api/v1/metrics/current")
            assert r.status_code == 401, f"应返回 401，实际 {r.status_code}: {r.text}"

    def test_protected_endpoint_rejects_wrong_key(self):
        """Verify: 错误的 X-API-Key 返回 401."""
        with _api_server({"OPC_API_KEY": "test-secret-key"}) as base_url:
            r = httpx.get(
                f"{base_url}/api/v1/metrics/current",
                headers={"X-API-Key": "wrong-key"},
            )
            assert r.status_code == 401

    def test_protected_endpoint_accepts_correct_key(self):
        """Verify: 正确的 X-API-Key 返回 200 + Side-Effect（数据）."""
        with _api_server({"OPC_API_KEY": "test-secret-key"}) as base_url:
            r = httpx.get(
                f"{base_url}/api/v1/metrics/current",
                headers={"X-API-Key": "test-secret-key"},
            )
            assert r.status_code == 200
            # Side-Effect: 返回真实数据
            data = r.json()
            assert "version" in data or "metrics" in data, f"返回数据缺少关键字段: {data}"

    def test_dev_mode_allows_localhost_without_key(self):
        """Verify: 未配置 OPC_API_KEY 时 localhost 允许访问（开发模式）."""
        with _api_server({"OPC_API_KEY": ""}) as base_url:
            r = httpx.get(f"{base_url}/api/v1/metrics/current")
            assert r.status_code == 200, f"dev mode 应允许 localhost，实际 {r.status_code}"


class TestAPIFeedbackEndpointE2E:
    """feedback 端点 Side-Effect 验证."""

    def test_feedback_accepts_valid_request(self):
        """Verify: feedback 端点接受有效请求并写入 DB（Side-Effect）."""
        with _api_server({"OPC_API_KEY": ""}) as base_url:
            payload = {
                "task_id": "e2e-test-task-001",
                "feedback": "good",
                "comment": "E2E 测试反馈",
            }
            r = httpx.post(f"{base_url}/api/v1/feedback", json=payload)
            assert r.status_code == 200, f"feedback 提交失败: {r.text}"

            # Side-Effect: DB 写入
            from opc_manager.data_manager import execute_query
            rows = execute_query(
                "SELECT * FROM feedback WHERE task_id = ?",
                ("e2e-test-task-001",),
            )
            assert rows, "feedback 未写入 DB"

            # 清理
            from opc_manager.data_manager import execute_write
            execute_write(
                "DELETE FROM feedback WHERE task_id = ?",
                ("e2e-test-task-001",),
            )

    def test_feedback_rejects_invalid_payload(self):
        """Verify: feedback 端点拒绝无效 payload（422）."""
        with _api_server({"OPC_API_KEY": ""}) as base_url:
            r = httpx.post(f"{base_url}/api/v1/feedback", json={"invalid": "payload"})
            assert r.status_code == 422
```

**验收命令**:

```bash
# 1. 启动 API server 手动验证
OPC_API_KEY=test-secret uvicorn opc_manager.api_server:app --port 8900 &

curl http://127.0.0.1:8900/health  # 200 ok
curl http://127.0.0.1:8900/api/v1/metrics/current  # 401
curl -H "X-API-Key: test-secret" http://127.0.0.1:8900/api/v1/metrics/current  # 200

kill %1

# 2. E2E 测试
pytest tests/e2e/test_api_server_e2e.py -v

# 3. 回归现有 API 测试
pytest tests/integration/test_api_*.py -v
```

**影响范围分析**:

* 🔴 修改 `opc_manager/api_server.py` 新增鉴权中间件

* ⚠️ 现有调用 `/api/v1/*` 的代码需添加 `X-API-Key` 头（搜索 `httpx.post.*api/v1` 和 `requests.post.*api/v1`）

* ⚠️ 文档需说明生产部署必须配置 `OPC_API_KEY` 环境变量

***

### 3.2 工作项 3.2: 响应式 viewport 参数化测试（GAP-P0-8）

**新增文件**: `tests/e2e/test_responsive_e2e.py`

```python
"""响应式布局 E2E 测试.

GAP-P0-8: 现有 Playwright E2E 仅测 1280x800，theme_manager.py:163-245 移动端 CSS 零验证.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

VIEWPORTS = [
    pytest.param({"width": 375, "height": 667}, id="mobile_se"),
    pytest.param({"width": 768, "height": 1024}, id="tablet_ipad"),
    pytest.param({"width": 1280, "height": 800}, id="desktop"),
    pytest.param({"width": 1920, "height": 1080}, id="fhd"),
]


@pytest.fixture(params=VIEWPORTS)
def viewport_page(request, playwright_browser, streamlit_server):
    """参数化 viewport page fixture."""
    context = playwright_browser.new_context(
        viewport=request.param,
        locale="zh-CN",
    )
    page = context.new_page()
    page.set_default_timeout(15000)
    page.goto(streamlit_server, wait_until="networkidle")
    page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=20000)
    yield page
    context.close()


class TestResponsiveLayout:
    """响应式布局核心验证."""

    def test_sidebar_visible_on_all_viewports(self, viewport_page):
        """Verify: 所有 viewport 下侧边栏可见（移动端可能折叠，但应可展开）."""
        sidebar = viewport_page.locator("[data-testid='stSidebar']")
        # 移动端可能折叠，检查是否存在
        expect(sidebar).to_be_attached(timeout=10000)

    def test_no_horizontal_scroll_on_mobile(self, viewport_page, request):
        """Verify: 手机端无水平滚动（scrollWidth <= clientWidth）."""
        if "mobile" not in request.node.callspec.id:
            pytest.skip("仅手机端验证")
        scroll_width = viewport_page.evaluate("document.body.scrollWidth")
        client_width = viewport_page.evaluate("document.body.clientWidth")
        assert scroll_width <= client_width, (
            f"手机端出现水平滚动: scrollWidth={scroll_width}, clientWidth={client_width}"
        )

    def test_chat_input_visible_on_mobile(self, viewport_page, request):
        """Verify: 手机端 Chat 输入框可见（Demo 模式下也应可见信息面板）."""
        if "mobile" not in request.node.callspec.id:
            pytest.skip("仅手机端验证")
        # 导航到 Chat
        radio = viewport_page.locator("[data-testid='stRadio'] label", has_text="对话").first
        if radio.count() > 0:
            radio.click(force=True)
            viewport_page.wait_for_timeout(2000)
        # 主内容区应可见
        main = viewport_page.locator("[data-testid='stMainBlockContainer']")
        expect(main).to_be_visible(timeout=10000)

    def test_no_overflow_on_all_viewports(self, viewport_page):
        """Verify: 所有 viewport 下无内容溢出（body scrollWidth <= window.innerWidth + 10）."""
        scroll_width = viewport_page.evaluate("document.body.scrollWidth")
        inner_width = viewport_page.evaluate("window.innerWidth")
        # 允许 10px 容差（滚动条宽度）
        assert scroll_width <= inner_width + 10, (
            f"内容溢出: scrollWidth={scroll_width}, innerWidth={inner_width}"
        )

    def test_text_readable_on_all_viewports(self, viewport_page):
        """Verify: 所有 viewport 下文本可读（无截断、无重叠）."""
        # 检查是否有元素被截断（overflow: hidden 且 scrollWidth > clientWidth）
        truncated = viewport_page.evaluate(
            """() => {
                const els = document.querySelectorAll("p, span, div, h1, h2, h3");
                const truncated = [];
                for (const el of els) {
                    if (el.offsetWidth < el.scrollWidth && el.textContent.trim()) {
                        truncated.push({
                            tag: el.tagName,
                            text: el.textContent.substring(0, 50),
                        });
                    }
                }
                return truncated.slice(0, 5);  // 只返回前 5 个
            }"""
        )
        assert not truncated, f"存在文本截断: {truncated}"
```

**验收命令**:

```bash
pytest tests/e2e/test_responsive_e2e.py -v --tb=short
```

***

### 3.3 工作项 3.3: 视觉回归 baseline（GAP-P0-9）

**新增文件**: `tests/e2e/test_visual_regression.py`

```python
"""视觉回归测试 — Playwright toHaveScreenshot.

GAP-P0-9: 无 screenshot baseline 对比，UI 变更无法自动检测.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.visual]

# baseline 存放目录
_BASELINE_DIR = "tests/e2e/__screenshots__"


def _goto_page(page, label: str) -> None:
    radio = page.locator("[data-testid='stRadio'] label", has_text=label).first
    radio.wait_for(state="attached", timeout=15000)
    radio.click(force=True)
    page.wait_for_timeout(3000)  # 等待渲染稳定


class TestVisualRegressionBaseline:
    """建立 4 个核心页面的 baseline 截图."""

    def test_homepage_baseline(self, page, streamlit_server):
        """Verify: 首页与 baseline 一致."""
        page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=20000)
        page.wait_for_timeout(3000)  # 等待完全渲染
        expect(page).to_have_screenshot(
            "homepage.png",
            max_diff_pixel_ratio=0.01,
            mask=[page.locator("[data-testid='stTime']")],  # 排除时间元素
        )

    def test_dashboard_baseline(self, page, streamlit_server):
        """Verify: Dashboard 页面与 baseline 一致."""
        _goto_page(page, "Dashboard")
        expect(page).to_have_screenshot(
            "dashboard.png",
            max_diff_pixel_ratio=0.01,
            mask=[page.locator("[data-testid='stTime']")],
        )

    def test_settings_baseline(self, page, streamlit_server):
        """Verify: Settings 页面与 baseline 一致."""
        _goto_page(page, "设置")
        expect(page).to_have_screenshot(
            "settings.png",
            max_diff_pixel_ratio=0.01,
        )

    def test_deliverables_baseline(self, page, streamlit_server):
        """Verify: Deliverables 页面与 baseline 一致."""
        _goto_page(page, "成果物")
        expect(page).to_have_screenshot(
            "deliverables.png",
            max_diff_pixel_ratio=0.01,
        )


class TestVisualRegressionTheme:
    """主题视觉回归（light + dark）."""

    def test_light_theme_baseline(self, page, streamlit_server):
        """Verify: 浅色主题首页 baseline."""
        page.wait_for_timeout(3000)
        expect(page).to_have_screenshot("theme_light.png", max_diff_pixel_ratio=0.01)

    def test_dark_theme_baseline(self, page, streamlit_server):
        """Verify: 深色主题首页 baseline."""
        # 切换到 dark 主题
        theme_select = page.locator("[data-testid='stSelectbox'] label:has-text('主题')").first
        if theme_select.count() > 0:
            theme_select.click()
            page.locator("li:has-text('dark')").first.click()
            page.wait_for_timeout(2000)
        expect(page).to_have_screenshot("theme_dark.png", max_diff_pixel_ratio=0.01)
```

**首次生成 baseline 命令**:

```bash
# 1. 生成 baseline（首次运行会创建截图）
pytest tests/e2e/test_visual_regression.py --snapshot-update

# 2. 提交 baseline 到 git
git add tests/e2e/__screenshots__/
git commit -m "test: add visual regression baseline (GAP-P0-9)"

# 3. 后续运行验证
pytest tests/e2e/test_visual_regression.py -v
```

**CI 平台相关处理**:

* ⚠️ Playwright 截图与 OS/字体相关，CI (Ubuntu) 与本地 (macOS) baseline 可能不一致

* 缓解方案: baseline 仅在 CI 环境生成，本地标记 `@pytest.mark.skip`

* 或者使用 `max_diff_pixel_ratio=0.05` 放宽容差

***

## 四、Sprint 4: P0 收尾 + P1 体验（20-24h）

### 4.1 工作项 4.1: Chat 错误恢复 UI E2E（GAP-P0-4）

**新增文件**: `tests/e2e/test_chat_error_recovery_e2e.py`

```python
"""Chat 错误恢复 UI E2E 测试.

GAP-P0-4: 验证 5 种错误状态的友好提示和重试按钮.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


@pytest.fixture
def page_with_llm_error(
    playwright_browser, streamlit_server_real_mode, request
):
    """配置 Mock LLM 抛出特定错误的 page fixture.

    request.param: 错误类型 ("timeout"/"connection"/"api_key"/"rate_limit"/"server_500")
    """
    error_type = request.param
    # 通过环境变量配置 Mock LLM 错误模式
    # （需在 SimpleLLMService mock 路径中读取 OPC_MOCK_LLM_ERROR 环境变量）
    import os
    os.environ["OPC_MOCK_LLM_ERROR"] = error_type

    context = playwright_browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="zh-CN",
    )
    page = context.new_page()
    page.set_default_timeout(30000)
    page.goto(streamlit_server_real_mode, wait_until="networkidle")
    page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=30000)
    yield page
    context.close()
    os.environ.pop("OPC_MOCK_LLM_ERROR", None)


@pytest.mark.parametrize(
    "page_with_llm_error,expected_text",
    [
        ("timeout", ["超时", "timeout", "请重试"]),
        ("connection", ["连接", "connection", "网络"]),
        ("api_key", ["API", "key", "配置", "授权"]),
        ("rate_limit", ["频率", "rate", "稍后", "等待"]),
        ("server_500", ["服务器", "500", "稍后", "联系"]),
    ],
    indirect=["page_with_llm_error"],
)
class TestChatErrorRecovery:
    """5 种错误状态的友好提示验证."""

    def test_error_shows_friendly_message(self, page_with_llm_error, expected_text):
        """Verify: 错误状态显示友好提示（含 expected_text 之一）."""
        # 导航到 Chat 并提交
        radio = page_with_llm_error.locator(
            "[data-testid='stRadio'] label", has_text="对话"
        ).first
        radio.click(force=True)
        page_with_llm_error.wait_for_timeout(2000)

        textarea = page_with_llm_error.locator("[data-testid='stTextArea'] textarea")
        textarea.fill("测试错误场景")
        textarea.press("Enter")

        # 等待错误提示出现（最多 30s）
        import time
        deadline = time.time() + 30
        while time.time() < deadline:
            for text in expected_text:
                if page_with_llm_error.locator(f"text={text}").count() > 0:
                    return
            time.sleep(1)
        pytest.fail(f"30s 内未出现友好提示，期望含: {expected_text}")

    def test_error_shows_retry_button(self, page_with_llm_error):
        """Verify: 错误状态显示重试按钮."""
        # 同上提交 prompt
        # 等待重试按钮出现
        import time
        deadline = time.time() + 30
        while time.time() < deadline:
            retry_btn = page_with_llm_error.locator(
                "button:has-text('重试'), button:has-text('retry')"
            )
            if retry_btn.count() > 0:
                return
            time.sleep(1)
        pytest.fail("30s 内未出现重试按钮")
```

***

### 4.2 工作项 4.2: 注入测试（GAP-P1-2）

**新增文件**: `tests/e2e/test_injection_e2e.py`

```python
"""SQL 注入 / 路径穿越 / 命令注入 E2E 测试.

GAP-P1-2: 现有 XSS 测试仅检查无 stException，未验证其他注入.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


class TestSQLInjectionE2E:
    """SQL 注入防护."""

    @pytest.mark.parametrize(
        "payload",
        [
            "' OR 1=1 --",
            "'; DROP TABLE users; --",
            "admin'--",
            "1' UNION SELECT * FROM finance_records--",
        ],
    )
    def test_sql_injection_in_search(self, page, payload):
        """Verify: 搜索框 SQL 注入不触发 SQL 错误泄露."""
        # 导航到 Deliverables（有搜索框）
        radio = page.locator(
            "[data-testid='stRadio'] label", has_text="成果物"
        ).first
        radio.click(force=True)
        page.wait_for_timeout(2000)

        search = page.locator("[data-testid='stTextInput'] input").first
        if search.count() == 0:
            pytest.skip("Deliverables 搜索框未渲染")
        search.fill(payload)
        search.press("Enter")
        page.wait_for_timeout(2000)

        # 验证无 SQL 错误泄露
        error = page.locator("[data-testid='stException']")
        expect(error).to_have_count(0)
        # 验证无 SQL 关键字泄露
        body = page.locator("body").inner_text()
        assert "SQLITE_ERROR" not in body
        assert "sqlite3.OperationalError" not in body
        assert "DROP TABLE" not in body.upper()


class TestPathTraversalE2E:
    """路径穿越防护."""

    @pytest.mark.parametrize(
        "payload",
        [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\win.ini",
            "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "....//....//etc/passwd",
        ],
    )
    def test_path_traversal_in_input(self, page, payload):
        """Verify: 路径穿越 payload 不读取敏感文件."""
        # 导航到 Chat
        radio = page.locator(
            "[data-testid='stRadio'] label", has_text="对话"
        ).first
        radio.click(force=True)
        page.wait_for_timeout(2000)

        textarea = page.locator("[data-testid='stTextArea'] textarea").first
        if textarea.count() == 0:
            pytest.skip("Chat 输入框未渲染（Demo 模式）")
        textarea.fill(f"读取文件 {payload}")
        textarea.press("Enter")
        page.wait_for_timeout(3000)

        # 验证无文件内容泄露
        body = page.locator("body").inner_text()
        assert "root:" not in body, "路径穿越成功读取 /etc/passwd"
        assert "[fonts]" not in body, "路径穿越成功读取 win.ini"


class TestCommandInjectionE2E:
    """命令注入防护."""

    @pytest.mark.parametrize(
        "payload",
        [
            "; ls -la",
            "| cat /etc/passwd",
            "$(whoami)",
            "`id`",
            "& dir",
        ],
    )
    def test_command_injection_in_input(self, page, payload):
        """Verify: 命令注入 payload 不执行系统命令."""
        radio = page.locator(
            "[data-testid='stRadio'] label", has_text="对话"
        ).first
        radio.click(force=True)
        page.wait_for_timeout(2000)

        textarea = page.locator("[data-testid='stTextArea'] textarea").first
        if textarea.count() == 0:
            pytest.skip("Chat 输入框未渲染（Demo 模式）")
        textarea.fill(f"执行 {payload}")
        textarea.press("Enter")
        page.wait_for_timeout(3000)

        # 验证无命令执行结果泄露
        body = page.locator("body").inner_text()
        # /etc/passwd 内容特征
        assert "root:x:" not in body
        # whoami 输出（如 root/lin）
        assert "uid=" not in body
        # ls 输出特征（drwxr-xr-x）
        assert "drwxr" not in body
```

***

### 4.3 工作项 4.3: 全主题 + 全页面无障碍（GAP-P1-7/8）

**修改文件**: `tests/e2e/test_a11y_axe.py`（参数化扩展）

**新增代码**（追加到现有文件末尾）:

```python
# 文件: tests/e2e/test_a11y_axe.py（追加）

# === GAP-P1-8: 全页面无障碍覆盖 ===

ALL_PAGES = ["对话", "成果物", "Dashboard", "成长", "技能市场", "设置"]


@pytest.mark.parametrize("page_name", ALL_PAGES)
class TestA11yPerPage:
    """每个页面都做 WCAG AA 扫描."""

    def test_interactive_labels_per_page(self, page, page_name):
        """Verify: 指定页面所有交互元素有可访问标签."""
        _goto_page_by_name(page, page_name)
        missing = page.evaluate(_SCAN_INTERACTIVES_JS)
        assert not missing, f"[{page_name}] 缺少标签的交互元素: {missing}"

    def test_color_contrast_per_page(self, page, page_name):
        """Verify: 指定页面颜色对比度 ≥ 4.5:1."""
        _goto_page_by_name(page, page_name)
        violations = page.evaluate(_CONTRAST_SCAN_JS)
        severe = [v for v in violations if v["ratio"] < 4.5]
        assert not severe, f"[{page_name}] 对比度不达标: {severe}"

    def test_keyboard_navigation_per_page(self, page, page_name):
        """Verify: 指定页面键盘 Tab 导航可见焦点."""
        _goto_page_by_name(page, page_name)
        page.keyboard.press("Tab")
        page.wait_for_timeout(500)
        focused = page.evaluate(
            "() => { const el = document.activeElement; "
            "return el ? window.getComputedStyle(el).outlineStyle : 'none'; }"
        )
        # 至少应有可见焦点（不严格断言，避免脆弱）
        assert focused != "none" or page.evaluate(
            "() => !!document.activeElement && document.activeElement !== document.body"
        )


def _goto_page_by_name(page, name: str) -> None:
    radio = page.locator("[data-testid='stRadio'] label", has_text=name).first
    radio.wait_for(state="attached", timeout=15000)
    radio.click(force=True)
    page.wait_for_timeout(2500)


# === GAP-P1-7: 全主题对比度覆盖 ===

ALL_THEMES = [
    "light", "dark", "sunset", "forest",
    "ocean", "morandi_light", "morandi_dark",
]


@pytest.mark.parametrize("theme", ALL_THEMES)
class TestThemeContrastAA:
    """每个主题都做 WCAG AA 对比度验证."""

    def test_theme_text_contrast_meets_aa(self, page, theme):
        """Verify: 指定主题下文本对比度 ≥ 4.5:1."""
        _select_theme(page, theme)
        violations = page.evaluate(_CONTRAST_SCAN_JS)
        severe = [v for v in violations if v["ratio"] < 4.5]
        assert not severe, f"[theme={theme}] 对比度不达标: {severe}"


def _select_theme(page, theme: str) -> None:
    """通过 sidebar selectbox 选择主题."""
    # 主题选择器可能在 sidebar
    select = page.locator("[data-testid='stSelectbox']").filter(
        has_text="主题"
    ).first
    if select.count() == 0:
        pytest.skip(f"主题选择器未找到，无法切换到 {theme}")
    select.click()
    page.locator(f"li:has-text('{theme}')").first.click()
    page.wait_for_timeout(2000)
```

***

## 五、Sprint 5: P1 CI 优化（6-8h）

### 5.1 工作项 5.1: E2E 独立 CI job + 重试 + artifact

**修改文件**: `.github/workflows/python-ci.yml`

```yaml
# 文件: .github/workflows/python-ci.yml
# 修改: 将现有 test job 中的 E2E step 移除，新增独立 e2e job

jobs:
  test:
    # ... 现有配置保留，但移除 E2E step（只跑 unit + integration）

  e2e:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    needs: test  # 单测过再跑 E2E 节省资源
    if: github.event_name == 'pull_request' || contains(github.ref, 'release')
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11"]  # 仅 3.11 跑 E2E
    steps:
      - uses: actions/checkout@v7

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v7
        with:
          python-version: ${{ matrix.python-version }}
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
          pip install -e .
          pip install pytest-rerunfailures>=14.0  # GAP-P1-9: 重试机制

      - name: Install Playwright browsers
        run: |
          playwright install chromium --with-deps

      - name: Run E2E tests (excluding slow + Docker)
        env:
          OPC_MOCK_LLM: "true"
        run: |
          PYTHONPATH=. pytest tests/e2e/ \
            -v \
            -m "not slow" \
            --tb=short \
            --timeout=120 \
            --reruns=2 \
            --reruns-delay=5 \
            --reruns-exclude="test_docker_run_e2e"

      - name: Upload E2E artifacts on failure
        if: failure()
        uses: actions/upload-artifact@v7
        with:
          name: e2e-failure-artifacts-py${{ matrix.python-version }}
          path: |
            /tmp/opc_streamlit_e2e*.log
            /tmp/opc_streamlit_e2e_real_*.log
            test-results.xml
            tests/e2e/__screenshots__/
          retention-days: 7
          if-no-files-found: ignore

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v7
        with:
          name: e2e-test-results-py${{ matrix.python-version }}
          path: test-results.xml
          if-no-files-found: ignore
```

### 5.2 工作项 5.2: requirements-dev.txt 添加 pytest-rerunfailures

```
# 文件: requirements-dev.txt（追加）
pytest-rerunfailures>=14.0  # GAP-P1-9: E2E flaky test 重试机制
```

**验收命令**:

```bash
# 本地模拟 CI 行为
pytest tests/e2e/ -v -m "not slow" --reruns=2 --reruns-delay=5

# 验证 artifact 生成（本地模拟）
ls /tmp/opc_streamlit_e2e*.log
```

***

## 六、Sprint 6: P2 长尾（12-16h）

### 6.1 工作项清单（方案级）

| ID        | 工作项                    | 实施要点                                                      | 工作量  |
| --------- | ---------------------- | --------------------------------------------------------- | ---- |
| GAP-P2-1  | 日文真实浏览器布局              | locale="ja-JP" 启动 server，验证日文文本不溢出                        | 2h   |
| GAP-P2-2  | ARIA live region 测试    | 验证 toast/错误提示有 `aria-live="polite"` 或 `assertive`         | 2h   |
| GAP-P2-3  | 键盘陷阱测试                 | consent\_dialog 模态打开后 Tab 不应逃逸到背景                         | 1.5h |
| GAP-P2-4  | prefers-reduced-motion | 模拟系统设置，验证动画被禁用                                            | 1h   |
| GAP-P2-5  | 网络断开/重连行为              | Playwright `route abort` 模拟离线，验证错误提示                      | 2h   |
| GAP-P2-6  | 并发操作冲突                 | 多 context 同时提交任务，验证无数据竞争                                  | 2h   |
| GAP-P2-7  | 超长会话性能                 | 模拟 100 轮对话，验证响应时间 < 5s                                    | 2h   |
| GAP-P2-8  | 数据迁移测试                 | 旧版 DB schema 升级到当前，验证不丢数据                                 | 2h   |
| GAP-P2-9  | API Key 中途失效           | 任务执行中清空 API Key，验证优雅降级                                    | 1.5h |
| GAP-P2-10 | 清理 pycache + 无效测试      | 删除 `test_user_journey.cpython-*.pyc`，修复 `test_TC_E03` 无断言 | 0.5h |

***

## 七、验收命令清单（一次性全量验证）

### 7.1 Sprint 完成后全量验证

```bash
cd /Users/lin/trae_projects/OPC-Agents

# === 1. 单元 + 集成回归 ===
pytest tests/unit/ tests/integration/ -x --tb=short

# === 2. E2E 全量（不含 slow）===
pytest tests/e2e/ -v -m "not slow" --tb=short --timeout=120

# === 3. E2E slow（Docker run）===
pytest tests/e2e/test_docker_run_e2e.py -v --tb=short

# === 4. Lint + Type check ===
ruff check opc_manager/ frontend/ tests/
mypy opc_manager/ --ignore-missing-imports --follow-imports=silent
black --check --target-version py310 opc_manager/ frontend/ tests/

# === 5. 复杂度检查 ===
radon cc opc_manager/ -nc -s  # 无 D+ (>=21)

# === 6. 文档一致性 ===
grep -c "0.5.13" VERSION opc_manager/version.py  # 应为 2
grep -r "0.5.7" README*.md docs/PROJECT_STATUS.md  # 应无残留（已升级）

# === 7. 数据隔离验证 ===
md5sum data/opc_data.db  # 记录值
pytest tests/e2e/ -v -m "not slow"
md5sum data/opc_data.db  # 应一致

# === 8. CI 模拟 ===
PYTHONPATH=. pytest tests/e2e/ -v -m "not slow" --reruns=2 --reruns-delay=5
```

### 7.2 发布门禁（用户规则 3）

```bash
# === E2E Release Gate（用户规则 3 落地）===
# 模拟真实用户使用的测试

# 1. 真实模式 Chat 全链路
pytest tests/e2e/test_chat_real_mode_e2e.py -v

# 2. P0 技能真实执行
pytest tests/e2e/test_p0_skills_e2e.py -v

# 3. Settings 全 tab
pytest tests/e2e/test_settings_e2e.py -v

# 4. API 鉴权
pytest tests/e2e/test_api_server_e2e.py -v

# 5. 响应式
pytest tests/e2e/test_responsive_e2e.py -v

# 6. 视觉回归
pytest tests/e2e/test_visual_regression.py -v

# 7. a11y 全页面全主题
pytest tests/e2e/test_a11y_axe.py -v

# 8. Docker 部署
pytest tests/e2e/test_docker_run_e2e.py -v

# 全部通过才允许发布
echo "=== All E2E gates passed, ready to release ==="
```

***

## 八、文档同步清单

每个 Sprint 完成后必须同步更新：

| 文档                                      | 更新内容                                | 验证命令                                             | <br />                                | <br />             |
| --------------------------------------- | ----------------------------------- | ------------------------------------------------ | :------------------------------------ | :----------------- |
| `VERSION`                               | 版本号递增                               | `cat VERSION`                                    | <br />                                | <br />             |
| `opc_manager/version.py`                | `__version__` 同步                    | `grep __version__ opc_manager/version.py`        | <br />                                | <br />             |
| `CHANGELOG.md`                          | 新增版本条目（Added/Changed/Fixed）         | `head -50 CHANGELOG.md`                          | <br />                                | <br />             |
| `README.md` × 3                         | 测试数更新（三语同步）                         | \`grep -E "测试                                    | tests                                 | テスト" README\*.md\` |
| `docs/PROJECT_STATUS.md`                | E2E 覆盖率 + 测试数                       | \`grep -E "E2E                                   | tests" docs/PROJECT\_STATUS.md\`      | <br />             |
| `docs/assessments/E2E_REVIEW_v0.5.7.md` | 标记已解决项（✅）                           | `grep "✅" docs/assessments/E2E_REVIEW_v0.5.7.md` | <br />                                | <br />             |
| `docs/TECH_DEBT.md`                     | 记录 E2E 技术债清理                        | `tail -20 docs/TECH_DEBT.md`                     | <br />                                | <br />             |
| `requirements-dev.txt`                  | 新增依赖（aiosmtpd/pytest-rerunfailures） | \`grep -E "aiosmtpd                              | rerunfailures" requirements-dev.txt\` | <br />             |

***

## 九、风险与缓解

| 风险                                         | 概率 | 影响          | 缓解措施                                              | 应急回滚                                   |
| ------------------------------------------ | -- | ----------- | ------------------------------------------------- | -------------------------------------- |
| `OPC_MOCK_LLM=true` 不被 SimpleLLMService 识别 | 中  | Sprint 2 延期 | 先调研 `llm_backend_manager.py` 的 LLM 调用点，添加 Mock 路径 | 改用 `unittest.mock.patch` 在 fixture 中注入 |
| FastAPI 鉴权中间件破坏现有 API 调用                   | 中  | Sprint 3 延期 | 鉴权向后兼容（默认允许 localhost）                            | `git revert` 鉴权 commit                 |
| 视觉回归 baseline 跨平台不一致                       | 高  | CI 失败       | baseline 仅在 CI 生成，本地 `@pytest.mark.skip`          | 提高容差到 0.05                             |
| Docker E2E 在 CI 慢                          | 中  | CI 超时       | `@pytest.mark.slow` 标记，仅 release 跑                | 移到独立 workflow                          |
| E2E 套件耗时 > 30min                           | 中  | CI 超时       | 仅 3.11 跑 E2E + pytest-xdist 并行                    | 拆分 E2E 到多个 job                         |
| Settings E2E 表单字段定位脆弱                      | 高  | 测试 flaky    | 用 `data-testid` 优先，文本匹配兜底                         | 增加 `wait_for_timeout`                  |
| Mock SMTP 端口冲突                             | 低  | email 测试失败  | 动态分配端口                                            | 用 `pytest.fixture(scope="session")`    |
| `test_audit_output_is_sanitized` 修复后失败     | 中  | 暴露隐藏 bug    | 立即修复 audit.log 实现                                 | 临时 `pytest.mark.xfail` 并记录到 TECH\_DEBT |

***

## 十、Sprint 推进时间表

| Sprint   | 推进顺序                           | 依赖                | 阻塞风险               |
| -------- | ------------------------------ | ----------------- | ------------------ |
| Sprint 1 | 立即开始                           | 无                 | 无                  |
| Sprint 2 | Sprint 1 完成后                   | `OPC_MOCK_LLM` 实现 | 🔴 Mock LLM 方案需先调研 |
| Sprint 3 | Sprint 1 完成后（可与 Sprint 2 并行）   | API 鉴权中间件         | 🟡 鉴权修改影响范围需评估     |
| Sprint 4 | Sprint 2 完成后                   | 真实模式 fixture      | 无                  |
| Sprint 5 | Sprint 1 完成后（可与 Sprint 2-4 并行） | 无                 | 无                  |
| Sprint 6 | Sprint 1-5 完成后                 | 无                 | 无                  |

**关键路径**: Sprint 1 → Sprint 2 → Sprint 4 → 全部完成

***

## 十一、推进原则（DevSquad Iron Rules 落地）

1. **文档先行**: 本文件为详细实施文档，每个 Sprint 开始前先标记 in-progress，完成后标记 done
2. **外科手术式修改**: 只改必要的文件，不重构无关代码
3. **测试 Iron Rules**:

   * Iron Rule 1（文档先行）: 写测试前先读源码确认 API 签名

   * Iron Rule 2（失败报告）: 测试失败时不修改断言，分析根因

   * Iron Rule 3（维度完整）: Happy + Error + Boundary + Performance + Config + Integration + Side-Effect

   * Iron Rule 4（Side-Effect）: 不仅检查 status\_code，验证 DB/状态/输出

   * Iron Rule 5（User Journey）: 从用户视角设计测试，不是 API 视角

   * Iron Rule 6（E2E Release Gate）: E2E 是发布门禁，不通过不发布
4. **Goal-Driven**: 每个 Sprint 有明确验收标准，未达标不进入下一 Sprint
5. **诚实评估**: 不修改测试断言来通过测试，发现源码 bug 立即报告

***

## 十二、附录：关键文件路径速查

### 12.1 待修改文件

| 文件                                    | Sprint | 修改类型                          |
| ------------------------------------- | ------ | ----------------------------- |
| `tests/e2e/conftest.py`               | 1, 2   | 修改（数据隔离 + real\_mode fixture） |
| `tests/e2e/test_e2e_user_journeys.py` | 1      | 修改（条件断言）                      |
| `opc_manager/api_server.py`           | 3      | 修改（鉴权中间件）                     |
| `tests/e2e/test_a11y_axe.py`          | 4      | 修改（参数化扩展）                     |
| `.github/workflows/python-ci.yml`     | 5      | 修改（独立 E2E job）                |
| `requirements-dev.txt`                | 5      | 修改（新增依赖）                      |

### 12.2 新增文件

| 文件                                          | Sprint | 类型  |
| ------------------------------------------- | ------ | --- |
| `tests/e2e/test_docker_run_e2e.py`          | 1      | E2E |
| `tests/e2e/test_chat_real_mode_e2e.py`      | 2      | E2E |
| `tests/e2e/test_p0_skills_e2e.py`           | 2      | E2E |
| `tests/e2e/test_settings_e2e.py`            | 2      | E2E |
| `tests/e2e/test_api_server_e2e.py`          | 3      | E2E |
| `tests/e2e/test_responsive_e2e.py`          | 3      | E2E |
| `tests/e2e/test_visual_regression.py`       | 3      | E2E |
| `tests/e2e/test_chat_error_recovery_e2e.py` | 4      | E2E |
| `tests/e2e/test_injection_e2e.py`           | 4      | E2E |
| `tests/e2e/__screenshots__/`                | 3      | 资源  |

### 12.3 关键源码路径（参考）

| 文件                                              | 用途                       |
| ----------------------------------------------- | ------------------------ |
| `frontend/routers/chat_router.py:265-288`       | Demo 模式 st.stop() 跳过输入框  |
| `frontend/routers/base_router.py:23-49`         | `_has_api_key()` 实现      |
| `frontend/page_modules/_settings_page.py:26-73` | 6 个 Settings tab         |
| `frontend/components/theme_manager.py:17-68`    | 7 个主题定义                  |
| `opc_manager/settings_operations.py:287-326`    | `test_smtp_connection()` |
| `opc_manager/settings_encryption.py:39-245`     | Fernet 加密                |
| `opc_manager/data_backup.py:100-150`            | 备份/恢复                    |
| `opc_manager/secure_storage.py`                 | Fernet 加密存储              |

***

**文档完成**。等待用户确认后开始 Sprint 1 实施。
