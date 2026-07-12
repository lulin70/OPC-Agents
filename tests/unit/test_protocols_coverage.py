"""Coverage tests for opc_manager.protocols

Tests the Null Provider pattern and provider factory functions.
Module-level provider singletons are reset between tests via the
reset_providers fixture.
"""

from unittest.mock import MagicMock, patch

import pytest

from opc_manager.protocols import (
    LLMProvider,
    MonitorProvider,
    NullLLMProvider,
    NullMonitorProvider,
    NullSearchProvider,
    NullSecureProvider,
    SearchProvider,
    SecureProvider,
    _LLMProviderWrapper,
    _SearchProviderWrapper,
    _SecureProviderWrapper,
    get_llm_provider,
    get_monitor_provider,
    get_search_provider,
    get_secure_provider,
)
import opc_manager.protocols as protocols_module


@pytest.fixture(autouse=True)
def reset_providers():
    """Reset module-level provider singletons before each test."""
    protocols_module._llm_provider = None
    protocols_module._search_provider = None
    protocols_module._secure_provider = None
    protocols_module._monitor_provider = None
    yield
    protocols_module._llm_provider = None
    protocols_module._search_provider = None
    protocols_module._secure_provider = None
    protocols_module._monitor_provider = None


class TestNullLLMProvider:
    def test_is_available_returns_false(self):
        assert NullLLMProvider().is_available() is False

    def test_generate_returns_none(self):
        assert NullLLMProvider().generate("prompt") is None

    def test_generate_with_system_prompt(self):
        result = NullLLMProvider().generate("p", system_prompt="s")
        assert result is None

    def test_generate_with_kwargs(self):
        result = NullLLMProvider().generate("p", temperature=0.5, max_tokens=100)
        assert result is None


class TestNullSearchProvider:
    def test_is_available_returns_false(self):
        assert NullSearchProvider().is_available() is False

    def test_search_returns_empty_list(self):
        assert NullSearchProvider().search("query") == []

    def test_search_with_max_results(self):
        result = NullSearchProvider().search("query", max_results=5)
        assert result == []


class TestNullSecureProvider:
    def test_is_available_returns_false(self):
        assert NullSecureProvider().is_available() is False

    def test_set_key_returns_false(self):
        assert NullSecureProvider().set_key("name", "value") is False

    def test_get_key_returns_none(self):
        assert NullSecureProvider().get_key("name") is None

    def test_load_to_env_returns_zero(self):
        assert NullSecureProvider().load_to_env() == 0


class TestNullMonitorProvider:
    def test_is_available_returns_false(self):
        assert NullMonitorProvider().is_available() is False

    def test_track_does_not_raise(self):
        NullMonitorProvider().track("event")
        NullMonitorProvider().track("event", {"key": "value"})


class TestGetLLMProvider:
    def test_returns_null_when_init_raises(self):
        with patch(
            "opc_manager.llm_content.LLMEnhancedContentGenerator"
        ) as mock_gen_cls:
            mock_gen_cls.side_effect = ImportError("no llm_content module")
            provider = get_llm_provider()
            assert isinstance(provider, NullLLMProvider)

    def test_returns_null_when_no_api_base(self):
        mock_gen = MagicMock()
        mock_gen._get_llm_config.return_value = ("key", "", "model")
        with patch(
            "opc_manager.llm_content.LLMEnhancedContentGenerator",
            return_value=mock_gen,
        ):
            provider = get_llm_provider()
            assert isinstance(provider, NullLLMProvider)

    def test_returns_wrapper_when_api_base_present(self):
        mock_gen = MagicMock()
        mock_gen._get_llm_config.return_value = ("key", "https://api.test", "model")
        with patch(
            "opc_manager.llm_content.LLMEnhancedContentGenerator",
            return_value=mock_gen,
        ):
            provider = get_llm_provider()
            assert isinstance(provider, _LLMProviderWrapper)

    def test_caches_provider(self):
        mock_gen = MagicMock()
        mock_gen._get_llm_config.return_value = ("key", "", "model")
        with patch(
            "opc_manager.llm_content.LLMEnhancedContentGenerator",
            return_value=mock_gen,
        ):
            p1 = get_llm_provider()
            p2 = get_llm_provider()
            assert p1 is p2


class TestGetSearchProvider:
    def test_returns_null_when_init_raises(self):
        with patch("opc_manager.search_processor.SearchResultProcessor") as mock_cls:
            mock_cls.side_effect = ImportError("no module")
            provider = get_search_provider()
            assert isinstance(provider, NullSearchProvider)

    def test_returns_wrapper_when_init_succeeds(self):
        mock_processor = MagicMock()
        with patch(
            "opc_manager.search_processor.SearchResultProcessor",
            return_value=mock_processor,
        ):
            provider = get_search_provider()
            assert isinstance(provider, _SearchProviderWrapper)

    def test_caches_provider(self):
        mock_processor = MagicMock()
        with patch(
            "opc_manager.search_processor.SearchResultProcessor",
            return_value=mock_processor,
        ):
            p1 = get_search_provider()
            p2 = get_search_provider()
            assert p1 is p2


class TestGetSecureProvider:
    def test_returns_null_when_init_raises(self):
        with patch("opc_manager.secure_storage.SecureKeyStore") as mock_cls:
            mock_cls.side_effect = ImportError("no secure_storage")
            provider = get_secure_provider()
            assert isinstance(provider, NullSecureProvider)

    def test_returns_null_when_store_unavailable(self):
        mock_store = MagicMock()
        mock_store.is_available = False
        with patch(
            "opc_manager.secure_storage.SecureKeyStore",
            return_value=mock_store,
        ):
            provider = get_secure_provider()
            assert isinstance(provider, NullSecureProvider)

    def test_returns_wrapper_when_store_available(self):
        mock_store = MagicMock()
        mock_store.is_available = True
        with patch(
            "opc_manager.secure_storage.SecureKeyStore",
            return_value=mock_store,
        ):
            provider = get_secure_provider()
            assert isinstance(provider, _SecureProviderWrapper)

    def test_caches_provider(self):
        mock_store = MagicMock()
        mock_store.is_available = False
        with patch(
            "opc_manager.secure_storage.SecureKeyStore",
            return_value=mock_store,
        ):
            p1 = get_secure_provider()
            p2 = get_secure_provider()
            assert p1 is p2


class TestGetMonitorProvider:
    def test_returns_null_monitor(self):
        provider = get_monitor_provider()
        assert isinstance(provider, NullMonitorProvider)

    def test_caches_provider(self):
        p1 = get_monitor_provider()
        p2 = get_monitor_provider()
        assert p1 is p2


class TestLLMProviderWrapper:
    def test_is_available_true_when_api_base(self):
        gen = MagicMock()
        gen._get_llm_config.return_value = ("k", "https://api.test", "m")
        wrapper = _LLMProviderWrapper(gen)
        assert wrapper.is_available() is True

    def test_is_available_false_when_no_api_base(self):
        gen = MagicMock()
        gen._get_llm_config.return_value = ("k", "", "m")
        wrapper = _LLMProviderWrapper(gen)
        assert wrapper.is_available() is False

    def test_generate_delegates_to_gen(self):
        gen = MagicMock()
        gen._call_llm_api.return_value = "generated text"
        wrapper = _LLMProviderWrapper(gen)
        assert wrapper.generate("prompt") == "generated text"
        gen._call_llm_api.assert_called_once_with("prompt")


class TestSearchProviderWrapper:
    def test_is_available_returns_true(self):
        wrapper = _SearchProviderWrapper(MagicMock())
        assert wrapper.is_available() is True

    def test_search_delegates_to_processor(self):
        processor = MagicMock()
        processor.search.return_value = [{"title": "result"}]
        wrapper = _SearchProviderWrapper(processor)
        result = wrapper.search("query", max_results=5)
        assert result == [{"title": "result"}]
        processor.search.assert_called_once_with("query", max_results=5)


class TestSecureProviderWrapper:
    def test_is_available_returns_store_value(self):
        store = MagicMock()
        store.is_available = True
        assert _SecureProviderWrapper(store).is_available() is True
        store.is_available = False
        assert _SecureProviderWrapper(store).is_available() is False

    def test_set_key_delegates(self):
        store = MagicMock()
        store.set_key.return_value = True
        wrapper = _SecureProviderWrapper(store)
        assert wrapper.set_key("name", "value") is True
        store.set_key.assert_called_once_with("name", "value")

    def test_get_key_delegates(self):
        store = MagicMock()
        store.get_key.return_value = "secret"
        wrapper = _SecureProviderWrapper(store)
        assert wrapper.get_key("name") == "secret"
        store.get_key.assert_called_once_with("name")

    def test_load_to_env_delegates(self):
        store = MagicMock()
        store.load_to_env.return_value = 5
        wrapper = _SecureProviderWrapper(store)
        assert wrapper.load_to_env() == 5
        store.load_to_env.assert_called_once()


class TestProtocolRuntimeCheckable:
    """Verify runtime_checkable protocols accept compliant objects."""

    def test_llm_provider_accepts_compliant(self):
        class CompliantLLM:
            def is_available(self) -> bool:
                return True

            def generate(self, prompt, system_prompt="", **kwargs):
                return "ok"

        assert isinstance(CompliantLLM(), LLMProvider)

    def test_search_provider_accepts_compliant(self):
        class CompliantSearch:
            def is_available(self) -> bool:
                return True

            def search(self, query, max_results=10):
                return []

        assert isinstance(CompliantSearch(), SearchProvider)

    def test_secure_provider_accepts_compliant(self):
        class CompliantSecure:
            def is_available(self) -> bool:
                return True

            def set_key(self, name, value):
                return True

            def get_key(self, name):
                return None

            def load_to_env(self):
                return 0

        assert isinstance(CompliantSecure(), SecureProvider)

    def test_monitor_provider_accepts_compliant(self):
        class CompliantMonitor:
            def is_available(self) -> bool:
                return True

            def track(self, event, data=None):
                pass

        assert isinstance(CompliantMonitor(), MonitorProvider)

    def test_null_providers_satisfy_protocols(self):
        assert isinstance(NullLLMProvider(), LLMProvider)
        assert isinstance(NullSearchProvider(), SearchProvider)
        assert isinstance(NullSecureProvider(), SecureProvider)
        assert isinstance(NullMonitorProvider(), MonitorProvider)
