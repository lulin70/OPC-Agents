"""Ollama backend integration tests

Tests cover:
- OllamaBackend instantiation and config validation
- _get_llm_config() Ollama priority chain
- _call_llm_api() with Ollama (no API Key)
- config.py Ollama default model selection
- Graceful degradation when Ollama is unavailable

Run with:
  pytest tests/test_ollama_backend.py -v
  # With real Ollama running:
  OLLAMA_BASE_URL=http://localhost:11434 pytest tests/test_ollama_backend.py -v -k "real"
"""

import unittest
import os
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock


class TestOllamaBackendConfig(unittest.TestCase):
    """OllamaBackend configuration and validation tests"""

    def test_ollama_backend_instantiation(self):
        from opc_manager.llm_service import OllamaBackend, LLMConfig, LLMProvider

        config = LLMConfig(
            provider=LLMProvider.OLLAMA,
            model="llama3",
            base_url="http://localhost:11434",
        )
        backend = OllamaBackend(config)
        self.assertEqual(backend.base_url, "http://localhost:11434")
        self.assertEqual(backend.config.model, "llama3")

    def test_ollama_backend_default_url(self):
        from opc_manager.llm_service import OllamaBackend, LLMConfig, LLMProvider

        config = LLMConfig(provider=LLMProvider.OLLAMA, model="llama3", base_url=None)
        backend = OllamaBackend(config)
        self.assertEqual(backend.base_url, "http://localhost:11434")

    def test_ollama_backend_custom_url(self):
        from opc_manager.llm_service import OllamaBackend, LLMConfig, LLMProvider

        config = LLMConfig(
            provider=LLMProvider.OLLAMA,
            model="mistral",
            base_url="http://192.168.1.100:11434",
        )
        backend = OllamaBackend(config)
        self.assertEqual(backend.base_url, "http://192.168.1.100:11434")

    def test_ollama_backend_zero_cost(self):
        from opc_manager.llm_service import OllamaBackend, LLMConfig, LLMProvider

        config = LLMConfig(provider=LLMProvider.OLLAMA, model="llama3", base_url=None)
        backend = OllamaBackend(config)
        self.assertEqual(backend.estimate_cost("test prompt"), 0.0)
        self.assertEqual(backend.estimate_cost("a" * 10000), 0.0)

    def test_ollama_validate_config_unavailable(self):
        from opc_manager.llm_service import OllamaBackend, LLMConfig, LLMProvider

        config = LLMConfig(
            provider=LLMProvider.OLLAMA,
            model="llama3",
            base_url="http://localhost:19999",
        )
        backend = OllamaBackend(config)
        self.assertFalse(backend.validate_config())

    def test_llm_provider_enum_has_ollama(self):
        from opc_manager.llm_service import LLMProvider

        self.assertTrue(hasattr(LLMProvider, "OLLAMA"))
        self.assertEqual(LLMProvider.OLLAMA.value, "ollama")

    def test_llm_service_backend_map_includes_ollama(self):
        from opc_manager.llm_service import LLMService, LLMProvider, OllamaBackend

        self.assertIn(LLMProvider.OLLAMA, LLMService.BACKEND_MAP)
        self.assertEqual(LLMService.BACKEND_MAP[LLMProvider.OLLAMA], OllamaBackend)


class TestOllamaGetLLMConfig(unittest.TestCase):
    """_get_llm_config() Ollama priority chain tests"""

    def setUp(self):
        self._original_env = {}
        for key in [
            "MOKA_API_KEY",
            "MOKA_API_BASE",
            "MOKA_MODEL",
            "GLM_API_KEY",
            "OPENAI_API_KEY",
            "OPENAI_API_BASE",
            "OLLAMA_BASE_URL",
            "OLLAMA_MODEL",
            "OLLAMA_ENABLED",
        ]:
            self._original_env[key] = os.environ.get(key)

    def tearDown(self):
        for key, val in self._original_env.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val

    def _clear_llm_env(self):
        for key in [
            "MOKA_API_KEY",
            "GLM_API_KEY",
            "OPENAI_API_KEY",
            "OLLAMA_BASE_URL",
            "OLLAMA_ENABLED",
        ]:
            os.environ.pop(key, None)

    def test_ollama_with_base_url(self):
        from opc_manager.llm_content import LLMEnhancedContentGenerator

        self._clear_llm_env()
        os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"

        gen = LLMEnhancedContentGenerator()
        api_key, api_base, model = gen._get_llm_config()

        self.assertEqual(api_key, "ollama")
        self.assertEqual(api_base, "http://localhost:11434")
        self.assertEqual(model, "llama3")

    def test_ollama_with_enabled_flag(self):
        from opc_manager.llm_content import LLMEnhancedContentGenerator

        self._clear_llm_env()
        os.environ["OLLAMA_ENABLED"] = "true"

        gen = LLMEnhancedContentGenerator()
        api_key, api_base, model = gen._get_llm_config()

        self.assertEqual(api_key, "ollama")
        self.assertEqual(api_base, "http://localhost:11434")
        self.assertEqual(model, "llama3")

    def test_ollama_custom_model(self):
        from opc_manager.llm_content import LLMEnhancedContentGenerator

        self._clear_llm_env()
        os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
        os.environ["OLLAMA_MODEL"] = "mistral"

        gen = LLMEnhancedContentGenerator()
        api_key, api_base, model = gen._get_llm_config()

        self.assertEqual(model, "mistral")

    def test_ollama_url_already_has_v1(self):
        from opc_manager.llm_content import LLMEnhancedContentGenerator

        self._clear_llm_env()
        os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434/v1"

        gen = LLMEnhancedContentGenerator()
        api_key, api_base, model = gen._get_llm_config()

        self.assertEqual(api_base, "http://localhost:11434/v1")

    def test_ollama_url_trailing_slash(self):
        from opc_manager.llm_content import LLMEnhancedContentGenerator

        self._clear_llm_env()
        os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434/"

        gen = LLMEnhancedContentGenerator()
        api_key, api_base, model = gen._get_llm_config()

        self.assertEqual(api_base, "http://localhost:11434/")

    def test_moka_takes_priority_over_ollama(self):
        from opc_manager.llm_content import LLMEnhancedContentGenerator

        self._clear_llm_env()
        os.environ["MOKA_API_KEY"] = "test-key-12345"
        os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"

        gen = LLMEnhancedContentGenerator()
        api_key, api_base, model = gen._get_llm_config()

        self.assertIsNotNone(api_key)
        self.assertIn("moka", api_base.lower())

    def test_no_llm_configured_returns_empty(self):
        from opc_manager.llm_content import LLMEnhancedContentGenerator

        self._clear_llm_env()

        gen = LLMEnhancedContentGenerator()
        api_key, api_base, model = gen._get_llm_config()

        self.assertIsNone(api_key)
        self.assertEqual(api_base, "")
        self.assertEqual(model, "")

    def test_ollama_enabled_false_ignored(self):
        from opc_manager.llm_content import LLMEnhancedContentGenerator

        self._clear_llm_env()
        os.environ["OLLAMA_ENABLED"] = "false"

        gen = LLMEnhancedContentGenerator()
        api_key, api_base, model = gen._get_llm_config()

        self.assertIsNone(api_key)
        self.assertEqual(api_base, "")


class TestOllamaCallLLMAPI(unittest.TestCase):
    """_call_llm_api() with Ollama (no API Key) tests"""

    def setUp(self):
        self._original_env = {}
        for key in [
            "MOKA_API_KEY",
            "GLM_API_KEY",
            "OPENAI_API_KEY",
            "OLLAMA_BASE_URL",
            "OLLAMA_MODEL",
            "OLLAMA_ENABLED",
        ]:
            self._original_env[key] = os.environ.get(key)

    def tearDown(self):
        for key, val in self._original_env.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val

    def _clear_llm_env(self):
        for key in [
            "MOKA_API_KEY",
            "GLM_API_KEY",
            "OPENAI_API_KEY",
            "OLLAMA_BASE_URL",
            "OLLAMA_ENABLED",
        ]:
            os.environ.pop(key, None)

    @patch("requests.post")
    def test_ollama_call_without_api_key(self, mock_post):
        from opc_manager.llm_content import LLMEnhancedContentGenerator

        self._clear_llm_env()
        os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Ollama generated content"}}]
        }
        mock_post.return_value = mock_response

        gen = LLMEnhancedContentGenerator()
        result = gen._call_llm_api("test prompt")

        self.assertIsNotNone(result)
        self.assertEqual(result, "Ollama generated content")

        call_args = mock_post.call_args
        headers = call_args.kwargs.get("headers") or call_args[1].get("headers")
        self.assertEqual(headers.get("Authorization"), "Bearer ollama")

    @patch("requests.post")
    def test_ollama_endpoint_url(self, mock_post):
        from opc_manager.llm_content import LLMEnhancedContentGenerator

        self._clear_llm_env()
        os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "test"}}]
        }
        mock_post.return_value = mock_response

        gen = LLMEnhancedContentGenerator()
        gen._call_llm_api("test prompt")

        call_args = mock_post.call_args
        endpoint = call_args[0][0] if call_args[0] else call_args.kwargs.get("url")
        self.assertIn("localhost:11434/chat/completions", endpoint)

    @patch("requests.post")
    def test_ollama_connection_error_returns_none(self, mock_post):
        from opc_manager.llm_content import LLMEnhancedContentGenerator
        import requests

        self._clear_llm_env()
        os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"

        mock_post.side_effect = requests.ConnectionError("Ollama not running")

        gen = LLMEnhancedContentGenerator()
        result = gen._call_llm_api("test prompt")

        self.assertIsNone(result)

    @patch("requests.post")
    def test_ollama_500_error_returns_none(self, mock_post):
        from opc_manager.llm_content import LLMEnhancedContentGenerator

        self._clear_llm_env()
        os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        gen = LLMEnhancedContentGenerator()
        result = gen._call_llm_api("test prompt")

        self.assertIsNone(result)

    @patch("requests.post")
    def test_ollama_model_not_found_error(self, mock_post):
        from opc_manager.llm_content import LLMEnhancedContentGenerator

        self._clear_llm_env()
        os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
        os.environ["OLLAMA_MODEL"] = "nonexistent-model"

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = '{"error":"model \\"nonexistent-model\\" not found"}'
        mock_post.return_value = mock_response

        gen = LLMEnhancedContentGenerator()
        result = gen._call_llm_api("test prompt")

        self.assertIsNone(result)


class TestOllamaConfigDefaultSelection(unittest.TestCase):
    """config.py Ollama default model selection tests"""

    def setUp(self):
        self._original_env = {}
        for key in [
            "MOKA_API_KEY",
            "GLM_API_KEY",
            "OPENAI_API_KEY",
            "OLLAMA_BASE_URL",
            "OLLAMA_MODEL",
            "OLLAMA_ENABLED",
        ]:
            self._original_env[key] = os.environ.get(key)

    def tearDown(self):
        for key, val in self._original_env.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val

    def _clear_llm_env(self):
        for key in [
            "MOKA_API_KEY",
            "GLM_API_KEY",
            "OPENAI_API_KEY",
            "OLLAMA_BASE_URL",
            "OLLAMA_ENABLED",
        ]:
            os.environ.pop(key, None)

    def test_ollama_selected_when_only_ollama_configured(self):
        from opc_manager.config import ConfigManager

        self._clear_llm_env()
        os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"

        cm = ConfigManager()
        cfg = cm.config
        self.assertEqual(cfg["models"]["default"], "ollama")

    def test_moka_still_priority_over_ollama(self):
        from opc_manager.config import ConfigManager

        self._clear_llm_env()
        os.environ["MOKA_API_KEY"] = "test-key"
        os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"

        cm = ConfigManager()
        cfg = cm.config
        self.assertEqual(cfg["models"]["default"], "moka")

    def test_ollama_not_selected_without_explicit_base_url(self):
        from opc_manager.config import ConfigManager

        self._clear_llm_env()

        cm = ConfigManager()
        cfg = cm.config
        default_model = cfg["models"]["default"]
        self.assertNotEqual(default_model, "ollama")

    def test_ollama_model_config_returned(self):
        from opc_manager.config import ConfigManager

        self._clear_llm_env()
        os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
        os.environ["OLLAMA_MODEL"] = "mistral"

        cm = ConfigManager()
        model_cfg = cm.get_model_config("ollama")

        self.assertEqual(model_cfg.get("base_url"), "http://localhost:11434")
        self.assertEqual(model_cfg.get("model"), "mistral")

    def test_available_models_includes_ollama(self):
        from opc_manager.config import ConfigManager

        self._clear_llm_env()
        os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"

        cm = ConfigManager()
        available = cm.get_available_models()

        self.assertIn("ollama", available)


class TestOllamaBackendAsyncComplete(unittest.TestCase):
    """OllamaBackend.complete() async tests with mocked httpx"""

    def test_complete_success(self):
        from opc_manager.llm_service import OllamaBackend, LLMConfig, LLMProvider

        config = LLMConfig(
            provider=LLMProvider.OLLAMA,
            model="llama3",
            base_url="http://localhost:11434",
        )
        backend = OllamaBackend(config)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": "Generated text from Ollama",
            "prompt_eval_count": 10,
            "eval_count": 20,
            "total_duration": 1500000000,
        }
        mock_response.raise_for_status = MagicMock()

        mock_post = AsyncMock(return_value=mock_response)

        async def run_test():
            with patch("httpx.AsyncClient") as MockClient:
                client_instance = MockClient.return_value
                client_instance.post = mock_post
                client_instance.__aenter__ = AsyncMock(return_value=client_instance)
                client_instance.__aexit__ = AsyncMock(return_value=False)
                return await backend.complete("test prompt")

        result = asyncio.get_event_loop().run_until_complete(run_test())

        self.assertEqual(result.content, "Generated text from Ollama")
        self.assertEqual(result.provider, LLMProvider.OLLAMA)
        self.assertEqual(result.model, "llama3")
        self.assertEqual(result.usage["prompt_tokens"], 10)
        self.assertEqual(result.usage["completion_tokens"], 20)
        self.assertEqual(result.usage["total_tokens"], 30)

    def test_complete_with_system_prompt(self):
        from opc_manager.llm_service import OllamaBackend, LLMConfig, LLMProvider

        config = LLMConfig(
            provider=LLMProvider.OLLAMA,
            model="llama3",
            base_url="http://localhost:11434",
        )
        backend = OllamaBackend(config)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": "Response with system prompt",
            "prompt_eval_count": 15,
            "eval_count": 25,
        }
        mock_response.raise_for_status = MagicMock()

        mock_post = AsyncMock(return_value=mock_response)

        async def run_test():
            with patch("httpx.AsyncClient") as MockClient:
                client_instance = MockClient.return_value
                client_instance.post = mock_post
                client_instance.__aenter__ = AsyncMock(return_value=client_instance)
                client_instance.__aexit__ = AsyncMock(return_value=False)
                return await backend.complete(
                    "test prompt", system_prompt="You are a helpful assistant"
                )

        result = asyncio.get_event_loop().run_until_complete(run_test())

        call_args = mock_post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        self.assertEqual(payload["system"], "You are a helpful assistant")

    def test_complete_connection_error(self):
        import httpx
        from opc_manager.llm_service import OllamaBackend, LLMConfig, LLMProvider

        config = LLMConfig(
            provider=LLMProvider.OLLAMA,
            model="llama3",
            base_url="http://localhost:19999",
            timeout_seconds=2.0,
        )
        backend = OllamaBackend(config)

        mock_post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        async def run_test():
            with patch("httpx.AsyncClient") as MockClient:
                client_instance = MockClient.return_value
                client_instance.post = mock_post
                client_instance.__aenter__ = AsyncMock(return_value=client_instance)
                client_instance.__aexit__ = AsyncMock(return_value=False)
                return await backend.complete("test prompt")

        with self.assertRaises(httpx.ConnectError):
            asyncio.get_event_loop().run_until_complete(run_test())


class TestOllamaLLMServiceIntegration(unittest.TestCase):
    """LLMService with Ollama provider integration tests"""

    def test_switch_to_ollama_provider(self):
        from opc_manager.llm_service import (
            LLMService,
            LLMConfig,
            LLMProvider,
            OllamaBackend,
        )

        config = LLMConfig(provider=LLMProvider.MOKA, api_key="test-key")
        service = LLMService(config)

        self.assertNotIsInstance(service.backend, OllamaBackend)

        service.switch_provider(
            LLMProvider.OLLAMA, base_url="http://localhost:11434", model="llama3"
        )

        self.assertIsInstance(service.backend, OllamaBackend)
        self.assertEqual(service.config.provider, LLMProvider.OLLAMA)

    def test_create_ollama_backend_directly(self):
        from opc_manager.llm_service import (
            LLMService,
            LLMConfig,
            LLMProvider,
            OllamaBackend,
        )

        config = LLMConfig(
            provider=LLMProvider.OLLAMA,
            model="llama3",
            base_url="http://localhost:11434",
        )
        service = LLMService(config)

        self.assertIsInstance(service.backend, OllamaBackend)


if __name__ == "__main__":
    unittest.main()
