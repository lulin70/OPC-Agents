"""Coverage tests for opc_manager.web_search.WebSearchMCP."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from opc_manager.web_search import WebSearchMCP


@pytest.fixture(autouse=True)
def _mock_web_search():
    """Override conftest autouse fixture to test real search method."""
    yield


class TestWebSearchMCPInit:
    """Verify: WebSearchMCP initialization paths."""

    def test_init_with_ddgs_package(self):
        """Verify: init succeeds when ddgs package is available."""
        mock_ddgs = MagicMock()
        with patch.dict("sys.modules", {"ddgs": mock_ddgs}):
            instance = WebSearchMCP()
        assert instance._dds is not None

    def test_init_fallback_to_duckduckgo_search(self):
        """Verify: init falls back to duckduckgo_search when ddgs missing."""
        mock_ddgs = MagicMock()
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "ddgs":
                raise ImportError("no ddgs")
            if name == "duckduckgo_search":
                return mock_ddgs
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            instance = WebSearchMCP()
        assert instance._dds is not None

    def test_init_import_error_both_packages_missing(self, caplog):
        """Verify: init logs warning when both packages missing."""
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name in ("ddgs", "duckduckgo_search"):
                raise ImportError(f"no {name}")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            with caplog.at_level(logging.WARNING):
                instance = WebSearchMCP()
        assert instance._dds is None
        assert "not installed" in caplog.text

    def test_init_generic_exception(self, caplog):
        """Verify: init logs warning on generic exception during DDGS construction."""
        mock_ddgs = MagicMock()
        mock_ddgs.DDGS.side_effect = RuntimeError("boom")
        with patch.dict("sys.modules", {"ddgs": mock_ddgs}):
            with caplog.at_level(logging.WARNING):
                instance = WebSearchMCP()
        assert instance._dds is None
        assert "Initialization failed" in caplog.text


class TestWebSearchMCPSearch:
    """Verify: search method behavior."""

    def test_search_not_initialized_returns_empty(self):
        """Verify: search returns [] when DDGS not initialized."""
        instance = WebSearchMCP()
        instance._dds = None
        result = instance.search("query")
        assert result == []

    def test_search_empty_query_returns_empty(self):
        """Verify: search returns [] for empty query."""
        instance = WebSearchMCP()
        instance._dds = MagicMock()
        assert instance.search("") == []
        assert instance.search("   ") == []

    def test_search_success(self):
        """Verify: search returns normalized results."""
        instance = WebSearchMCP()
        mock_dds = MagicMock()
        mock_dds.text.return_value = [
            {"title": "Result 1", "href": "http://a.com", "body": "Body 1"},
            {"title": "Result 2", "href": "http://b.com", "body": "Body 2"},
        ]
        instance._dds = mock_dds
        results = instance.search("test query", max_results=5)
        assert len(results) == 2
        assert results[0]["title"] == "Result 1"
        assert results[0]["href"] == "http://a.com"
        assert results[0]["body"] == "Body 1"
        mock_dds.text.assert_called_once_with("test query", max_results=5)

    def test_search_missing_keys_default_empty(self):
        """Verify: search handles items with missing keys."""
        instance = WebSearchMCP()
        mock_dds = MagicMock()
        mock_dds.text.return_value = [{}, {"title": "Only title"}]
        instance._dds = mock_dds
        results = instance.search("q")
        assert results[0]["title"] == ""
        assert results[0]["href"] == ""
        assert results[0]["body"] == ""
        assert results[1]["title"] == "Only title"
        assert results[1]["href"] == ""

    def test_search_exception_returns_empty(self, caplog):
        """Verify: search returns [] on exception."""
        instance = WebSearchMCP()
        mock_dds = MagicMock()
        mock_dds.text.side_effect = RuntimeError("network error")
        instance._dds = mock_dds
        with caplog.at_level(logging.WARNING):
            result = instance.search("query")
        assert result == []
        assert "Search failed" in caplog.text

    def test_search_default_max_results(self):
        """Verify: search uses default max_results=8."""
        instance = WebSearchMCP()
        mock_dds = MagicMock()
        mock_dds.text.return_value = []
        instance._dds = mock_dds
        instance.search("query")
        mock_dds.text.assert_called_once_with("query", max_results=8)


class TestWebSearchMCPAvailable:
    """Verify: is_available method."""

    def test_is_available_true(self):
        """Verify: is_available returns True when DDGS initialized."""
        instance = WebSearchMCP()
        instance._dds = MagicMock()
        assert instance.is_available() is True

    def test_is_available_false(self):
        """Verify: is_available returns False when DDGS not initialized."""
        instance = WebSearchMCP()
        instance._dds = None
        assert instance.is_available() is False
