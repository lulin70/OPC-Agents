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
