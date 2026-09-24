"""Coverage tests for opc_manager.web_search.WebSearchMCP."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from opc_manager.web_search import (
    RETRY_ATTEMPTS,
    RETRY_DELAY_SECONDS,
    STATUS_EMPTY,
    STATUS_FAILED,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    STATUS_UNSET,
    WebSearchMCP,
    _is_transient,
)


class FakeTimeoutError(Exception):
    """模拟 ddgs.TimeoutException：非 OSError 子类，靠类名兜底判定为瞬时故障。"""


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


@pytest.fixture
def _fast_retry():
    """打桩 time.sleep，避免测试等待真实退避延迟，同时断言退避确实发生。"""
    with patch("opc_manager.web_search.time.sleep") as mock_sleep:
        yield mock_sleep


class TestIsTransient:
    """W-1: 瞬时故障判定（决定是否重试）。"""

    def test_os_error_and_subclasses_are_transient(self):
        """OSError 及其子类（TimeoutError/ConnectionError）判定为瞬时。"""
        assert _is_transient(TimeoutError("timed out")) is True
        assert _is_transient(ConnectionResetError("reset")) is True

    def test_class_name_hint_is_transient(self):
        """非 OSError 子类（如 ddgs.TimeoutException）靠类名关键字兜底判定为瞬时。"""
        assert _is_transient(FakeTimeoutError("timed out")) is True

    def test_wrapped_os_error_in_chain_is_transient(self):
        """异常链上的 OSError 也应被追溯判定为瞬时。"""
        outer = RuntimeError("wrapped")
        outer.__cause__ = ConnectionAbortedError("aborted")
        assert _is_transient(outer) is True

    def test_plain_exception_is_not_transient(self):
        """普通编程错误不判为瞬时（重试无意义）。"""
        assert _is_transient(RuntimeError("programming bug")) is False


class TestWebSearchMCPRetry:
    """W-1: 有界重试 + 失败可观测（last_status / last_error）。"""

    def test_transient_failure_retried_then_succeeds(self, _fast_retry):
        """瞬时故障应重试，成功后返回结果且状态归为 OK。"""
        instance = WebSearchMCP()
        mock_dds = MagicMock()
        mock_dds.text.side_effect = [
            FakeTimeoutError("timed out"),
            [{"title": "T", "href": "http://a.com", "body": "B"}],
        ]
        instance._dds = mock_dds

        results = instance.search("query")

        assert len(results) == 1
        assert results[0]["title"] == "T"
        assert mock_dds.text.call_count == 2
        assert instance.last_status == STATUS_OK
        assert instance.last_error is None
        _fast_retry.assert_called_once_with(RETRY_DELAY_SECONDS)

    def test_transient_failure_retries_are_bounded(self, _fast_retry):
        """持续瞬时故障时重试次数有上界，且失败原因可被调用方读取。"""
        instance = WebSearchMCP()
        mock_dds = MagicMock()
        mock_dds.text.side_effect = FakeTimeoutError("timed out")
        instance._dds = mock_dds

        assert instance.search("query") == []

        assert mock_dds.text.call_count == RETRY_ATTEMPTS
        assert _fast_retry.call_count == RETRY_ATTEMPTS - 1
        assert instance.last_status == STATUS_FAILED
        assert "FakeTimeoutError" in instance.last_error

    def test_non_transient_failure_not_retried(self, _fast_retry):
        """非瞬时故障不重试（避免无意义等待）。"""
        instance = WebSearchMCP()
        mock_dds = MagicMock()
        mock_dds.text.side_effect = RuntimeError("programming bug")
        instance._dds = mock_dds

        assert instance.search("query") == []

        assert mock_dds.text.call_count == 1
        _fast_retry.assert_not_called()
        assert instance.last_status == STATUS_FAILED

    def test_status_unset_before_any_search(self):
        """Verify: 尚未搜索时状态为 UNSET。"""
        assert WebSearchMCP().last_status == STATUS_UNSET

    def test_status_empty_when_search_succeeds_without_results(self, _fast_retry):
        """确认零结果与失败必须可区分：零结果记 EMPTY 且无错误。"""
        instance = WebSearchMCP()
        mock_dds = MagicMock()
        mock_dds.text.return_value = []
        instance._dds = mock_dds

        assert instance.search("query") == []
        assert instance.last_status == STATUS_EMPTY
        assert instance.last_error is None
        assert mock_dds.text.call_count == 1

    def test_status_unavailable_when_not_initialized(self):
        """Verify: ddgs 未就绪时状态为 UNAVAILABLE。"""
        instance = WebSearchMCP()
        instance._dds = None

        assert instance.search("query") == []
        assert instance.last_status == STATUS_UNAVAILABLE
        assert instance.last_error

    def test_status_ok_for_mock_results(self, monkeypatch):
        """Verify: OPC_MOCK_LLM=true 的 Mock 结果路径状态为 OK。"""
        monkeypatch.setenv("OPC_MOCK_LLM", "true")
        instance = WebSearchMCP()

        results = instance.search("query")

        assert results
        assert instance.last_status == STATUS_OK
        assert instance.last_error is None
