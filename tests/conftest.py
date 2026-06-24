"""Pytest configuration and shared fixtures

Three-track test strategy:
- Default (pytest): Fast unit/integration tests with mocked search & LLM (~50s)
- UI E2E (pytest tests/test_ui_e2e_apptest.py): Streamlit AppTest UI-level tests (~8s)
- E2E (pytest -m e2e): Real API calls to validate actual system behavior (~5min)

Run commands:
  pytest                          # Fast unit tests (mocked, ~50s)
  pytest tests/test_ui_e2e_apptest.py  # UI E2E via Streamlit AppTest
  pytest -m e2e                   # All E2E tests (real search + LLM)
  pytest -m e2e_search            # Real search only (no API key needed)
  pytest -m e2e_llm               # Real LLM only (requires API key)
  pytest tests/ --ignore=tests/test_e2e_real.py  # Skip real E2E entirely
"""

import pytest
import os
import sys
from unittest.mock import Mock, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "e2e: Real API calls (slow, validates real system)"
    )
    config.addinivalue_line(
        "markers", "e2e_search: Real DuckDuckGo search (no API key needed)"
    )
    config.addinivalue_line("markers", "e2e_llm: Real LLM API call (requires API key)")


def pytest_collection_modifyitems(config, items):
    skip_e2e = os.environ.get("SKIP_E2E", "1")
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
