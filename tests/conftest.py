"""Pytest configuration and shared fixtures

Three-track test strategy:
- Default (pytest): Fast unit/integration tests with mocked search & LLM (~50s)
- UI E2E (pytest tests/test_ui_e2e_apptest.py): Streamlit AppTest UI-level tests (~8s)
- E2E (pytest -m e2e): Real API calls to validate actual system behavior (~5min)

E2E tests run by default (SKIP_E2E=0). Each e2e test class self-skips via
setUpClass when its dependencies are unavailable (no API key, no network).
Set SKIP_E2E=1 to globally skip all e2e-marked tests.

Run commands:
  pytest                          # All tests including E2E (self-skip if deps missing)
  SKIP_E2E=1 pytest               # Fast unit tests only (skip all e2e)
  pytest tests/test_ui_e2e_apptest.py  # UI E2E via Streamlit AppTest
  pytest -m e2e                   # All E2E tests (real search + LLM)
  pytest -m e2e_search            # Real search only (no API key needed)
  pytest -m e2e_llm               # Real LLM only (requires API key)
  pytest tests/ --ignore=tests/test_e2e_real.py  # Skip real E2E entirely
"""

import pytest
import os
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def _reset_global_singletons(monkeypatch):
    """Clean up global singletons after every test to prevent background
    threads and DB connections from leaking across tests.

    This addresses P0-1 where AuditLog's background writer threads and
    data_manager thread-local SQLite connections caused cascading lock
    contention during full-suite runs. It also isolates the onboarding
    marker so tests do not pollute the user's real ~/.opc-agents directory.
    """
    marker_path = (
        Path(tempfile.gettempdir())
        / f"opc_test_onboarding_{os.getpid()}_{threading.current_thread().ident}.marker"
    )
    monkeypatch.setenv("OPC_ONBOARDING_MARKER", str(marker_path))
    if marker_path.exists():
        marker_path.unlink()
    yield
    try:
        from opc_manager.audit_log import AuditLog

        instance = AuditLog._instance
        if instance is not None:
            try:
                instance.stop(wait=True)
            except Exception:
                pass
        AuditLog._instance = None
    except Exception:
        pass

    try:
        import opc_manager.data_manager as _dm

        if hasattr(_dm._local, "conn") and _dm._local.conn is not None:
            try:
                _dm._local.conn.close()
            except Exception:
                pass
            _dm._local.conn = None
    except Exception:
        pass

    try:
        from opc_manager.i18n import get_i18n

        get_i18n().locale = "zh_CN"
    except Exception:
        pass

    if marker_path.exists():
        try:
            marker_path.unlink()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def _mock_web_search(request):
    """Mock WebSearchMCP.search for non-e2e tests to prevent real network calls.

    conftest docstring states "mocked search & LLM" but the search mock was
    missing, causing 4 tests to timeout (21-28s each) under full-suite load.
    E2E tests (@pytest.mark.e2e) bypass this mock to use real services.
    """
    if request.node.get_closest_marker("e2e"):
        yield
        return

    from opc_manager.web_search import WebSearchMCP

    fake_results = [
        {
            "title": "测试搜索结果",
            "href": "https://example.com/test",
            "body": "测试内容",
        },
    ]
    patcher = patch.object(WebSearchMCP, "search", return_value=fake_results)
    patcher.start()
    try:
        yield
    finally:
        patcher.stop()


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "e2e: Real API calls (slow, validates real system)"
    )
    config.addinivalue_line(
        "markers", "e2e_search: Real DuckDuckGo search (no API key needed)"
    )
    config.addinivalue_line("markers", "e2e_llm: Real LLM API call (requires API key)")
    # GAP-P0-6: Docker E2E 标记为 slow，CI 默认跳过，release workflow 跑
    config.addinivalue_line(
        "markers", "slow: Slow tests (Docker build, real network) — CI 默认跳过"
    )
    # GAP-P0-9: 视觉回归 baseline 标记
    config.addinivalue_line(
        "markers", "visual: Visual regression tests (screenshot baseline)"
    )


def pytest_collection_modifyitems(config, items):
    # P1 fix (2026-06-29): default changed from "1" to "0" so E2E tests run
    # by default. Individual e2e test classes already self-skip via setUpClass
    # when their dependencies are unavailable (e.g. no API key, no network),
    # so a global skip is no longer needed and was hiding dead E2E tests.
    # Set SKIP_E2E=1 to opt out of E2E tests entirely.
    skip_e2e = os.environ.get("SKIP_E2E", "0")
    if skip_e2e == "1":
        skip_e2e_marker = pytest.mark.skip(
            reason="E2E tests skipped (set SKIP_E2E=0 to run)"
        )
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e_marker)


# ============== Shared Fixtures ==============


@pytest.fixture
def mock_strategist_brain():
    """Mock StrategistBrain with configurable express_opinion return value."""
    brain = Mock()
    brain.express_opinion = Mock(
        return_value={
            "brain_type": "strategist",
            "opinion_type": "AGREE",
            "reasoning": "test",
            "confidence": 0.8,
        }
    )
    return brain


@pytest.fixture
def mock_executor_brain():
    """Mock ExecutorBrain with configurable express_opinion return value."""
    from opc_manager.consensus_engine import Opinion, OpinionType

    brain = Mock()
    brain.express_opinion = Mock(
        return_value=Opinion(
            brain_type="executor",
            opinion_type=OpinionType.AGREE,
            reasoning="test",
            confidence=0.8,
        )
    )
    return brain


@pytest.fixture
def mock_reflector_brain():
    """Mock ReflectorBrain with configurable predict_consequence return value."""
    from opc_manager.consensus_engine import Opinion, OpinionType

    brain = Mock()
    brain.predict_consequence = Mock(
        return_value=Opinion(
            brain_type="reflector",
            opinion_type=OpinionType.AGREE,
            reasoning="test",
            confidence=0.8,
        )
    )
    return brain


@pytest.fixture
def mock_consensus_engine():
    """Mock ConsensusEngine with patched DB methods."""
    from unittest.mock import patch
    from opc_manager.consensus_engine import ConsensusEngine

    with (
        patch.object(ConsensusEngine, "_load_decision_log_from_db"),
        patch.object(ConsensusEngine, "_log_decision"),
    ):
        return ConsensusEngine()


@pytest.fixture
def agent_context():
    """Create a fresh AgentContext for testing."""
    from opc_manager.agent_context import AgentContext, AgentState

    return AgentContext(user_input="test input", state=AgentState.IDLE)


@pytest.fixture
def mock_task_result():
    """Create a mock TaskResult for testing."""
    from opc_manager.task_engine_v3 import TaskResult, TaskType

    return TaskResult(
        success=True,
        task_type=TaskType.INFO,
        content="test content",
        summary="test summary",
    )
