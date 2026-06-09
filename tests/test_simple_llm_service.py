"""Unit tests for opc_manager.simple_llm_service

Covers: discover_llm_config, circuit breaker, retry logic, timeout,
        provider fallback, error handling.
All external calls (requests, settings, semaphore) are mocked.
"""

import unittest
from unittest.mock import patch, MagicMock
import time

from opc_manager.simple_llm_service import (
    SimpleLLMService,
    discover_llm_config,
    _discover_all_providers,
    _CIRCUIT_BREAKER_THRESHOLD,
    LLM_MAX_RETRIES,
    LLM_CALL_TIMEOUT,
    LLM_TOTAL_TIMEOUT,
    LLM_RETRY_BACKOFF,
)


# ---------------------------------------------------------------------------
# discover_llm_config
# ---------------------------------------------------------------------------
class TestDiscoverLLMConfig(unittest.TestCase):
    """Tests for the discover_llm_config() free function."""

    @patch("opc_manager.simple_llm_service.os.environ.get")
    @patch("opc_manager.settings.get_settings")
    def test_returns_moka_config_from_settings(self, mock_get_settings, mock_env_get):
        """When SettingsManager provides an api_key, it should be used."""
        mock_settings_obj = MagicMock()
        mock_settings_obj.get_llm_config.return_value = {
            "api_key": "sk-moka-test",
            "base_url": "https://api.moka-ai.com/v1",
            "model": "moka/claude-sonnet-4-6",
        }
        mock_get_settings.return_value = mock_settings_obj
        config = discover_llm_config()
        self.assertEqual(config["api_key"], "sk-moka-test")
        self.assertEqual(config["base_url"], "https://api.moka-ai.com/v1")

    @patch("opc_manager.simple_llm_service.os.environ.get")
    @patch("opc_manager.settings.get_settings", side_effect=ImportError)
    def test_falls_back_to_moka_env_var(self, mock_get_settings, mock_env_get):
        """When SettingsManager fails, MOKA_API_KEY env var is used."""

        def env_side_effect(key, default=""):
            mapping = {
                "MOKA_API_KEY": "sk-moka-env",
                "MOKA_API_BASE": "https://moka.test/v1",
                "MOKA_MODEL": "moka/claude-sonnet-4-6",
                "GLM_API_KEY": "",
                "OPENAI_API_KEY": "",
                "OPENAI_API_BASE": "https://api.openai.com/v1",
                "OLLAMA_BASE_URL": "",
                "OLLAMA_ENABLED": "",
                "OLLAMA_MODEL": "llama3",
            }
            return mapping.get(key, default)

        mock_env_get.side_effect = env_side_effect
        config = discover_llm_config()
        self.assertEqual(config["api_key"], "sk-moka-env")
        self.assertEqual(config["base_url"], "https://moka.test/v1")

    @patch("opc_manager.simple_llm_service.os.environ.get")
    @patch("opc_manager.settings.get_settings", side_effect=ImportError)
    def test_falls_back_to_glm_env_var(self, mock_get_settings, mock_env_get):
        """When no MOKA key, GLM_API_KEY is used."""

        def env_side_effect(key, default=""):
            mapping = {
                "MOKA_API_KEY": "",
                "MOKA_API_BASE": "https://api.moka-ai.com/v1",
                "MOKA_MODEL": "moka/claude-sonnet-4-6",
                "GLM_API_KEY": "glm-test-key",
                "OPENAI_API_KEY": "",
                "OPENAI_API_BASE": "https://api.openai.com/v1",
                "OLLAMA_BASE_URL": "",
                "OLLAMA_ENABLED": "",
                "OLLAMA_MODEL": "llama3",
            }
            return mapping.get(key, default)

        mock_env_get.side_effect = env_side_effect
        config = discover_llm_config()
        self.assertEqual(config["api_key"], "glm-test-key")
        self.assertEqual(config["base_url"], "https://open.bigmodel.cn/api/paas/v4")
        self.assertEqual(config["model"], "glm-4")

    @patch("opc_manager.simple_llm_service.os.environ.get")
    @patch("opc_manager.settings.get_settings", side_effect=ImportError)
    def test_falls_back_to_openai_env_var(self, mock_get_settings, mock_env_get):
        """When no MOKA/GLM key, OPENAI_API_KEY is used."""

        def env_side_effect(key, default=""):
            mapping = {
                "MOKA_API_KEY": "",
                "MOKA_API_BASE": "https://api.moka-ai.com/v1",
                "MOKA_MODEL": "moka/claude-sonnet-4-6",
                "GLM_API_KEY": "",
                "OPENAI_API_KEY": "sk-openai-test",
                "OPENAI_API_BASE": "https://api.openai.com/v1",
                "OLLAMA_BASE_URL": "",
                "OLLAMA_ENABLED": "",
                "OLLAMA_MODEL": "llama3",
            }
            return mapping.get(key, default)

        mock_env_get.side_effect = env_side_effect
        config = discover_llm_config()
        self.assertEqual(config["api_key"], "sk-openai-test")
        self.assertEqual(config["model"], "gpt-4")

    @patch("opc_manager.simple_llm_service.os.environ.get")
    @patch("opc_manager.settings.get_settings", side_effect=ImportError)
    def test_ollama_config_when_enabled(self, mock_get_settings, mock_env_get):
        """Ollama config is returned when OLLAMA_ENABLED=true."""

        def env_side_effect(key, default=""):
            mapping = {
                "MOKA_API_KEY": "",
                "MOKA_API_BASE": "https://api.moka-ai.com/v1",
                "MOKA_MODEL": "moka/claude-sonnet-4-6",
                "GLM_API_KEY": "",
                "OPENAI_API_KEY": "",
                "OPENAI_API_BASE": "https://api.openai.com/v1",
                "OLLAMA_BASE_URL": "http://ollama:11434",
                "OLLAMA_ENABLED": "true",
                "OLLAMA_MODEL": "llama3",
            }
            return mapping.get(key, default)

        mock_env_get.side_effect = env_side_effect
        config = discover_llm_config()
        self.assertTrue(config["is_ollama"])
        self.assertEqual(config["base_url"], "http://ollama:11434")

    @patch("opc_manager.simple_llm_service.os.environ.get")
    @patch("opc_manager.settings.get_settings", side_effect=ImportError)
    def test_empty_config_when_no_keys(self, mock_get_settings, mock_env_get):
        """Returns empty config when no keys are available."""

        def env_side_effect(key, default=""):
            return default

        mock_env_get.side_effect = env_side_effect
        config = discover_llm_config()
        self.assertEqual(config["api_key"], "")
        self.assertFalse(config["is_ollama"])


# ---------------------------------------------------------------------------
# SimpleLLMService — init & is_available
# ---------------------------------------------------------------------------
class TestSimpleLLMServiceInit(unittest.TestCase):
    def test_init_with_explicit_params(self):
        svc = SimpleLLMService(
            api_key="sk-test", base_url="https://api.test/v1", model="test-model"
        )
        self.assertTrue(svc.is_available())
        self.assertEqual(svc._api_key, "sk-test")
        self.assertFalse(svc._is_ollama)

    def test_is_available_false_when_no_key(self):
        svc = SimpleLLMService.__new__(SimpleLLMService)
        svc._api_key = ""
        self.assertFalse(svc.is_available())

    def test_is_available_true_when_key_present(self):
        svc = SimpleLLMService.__new__(SimpleLLMService)
        svc._api_key = "sk-something"
        self.assertTrue(svc.is_available())


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------
class TestCircuitBreaker(unittest.TestCase):
    def setUp(self):
        self.svc = SimpleLLMService.__new__(SimpleLLMService)
        self.svc._circuit_breaker = {}

    def test_circuit_initially_closed(self):
        self.assertFalse(self.svc._is_provider_circuit_open("moka"))

    def test_circuit_opens_after_threshold_failures(self):
        for _ in range(_CIRCUIT_BREAKER_THRESHOLD):
            self.svc._record_provider_failure("moka")
        self.assertTrue(self.svc._is_provider_circuit_open("moka"))

    def test_circuit_stays_closed_below_threshold(self):
        for _ in range(_CIRCUIT_BREAKER_THRESHOLD - 1):
            self.svc._record_provider_failure("moka")
        self.assertFalse(self.svc._is_provider_circuit_open("moka"))

    def test_success_resets_circuit(self):
        self.svc._record_provider_failure("moka")
        self.svc._record_provider_failure("moka")
        self.svc._record_provider_success("moka")
        self.assertFalse(self.svc._is_provider_circuit_open("moka"))

    def test_independent_providers(self):
        """Circuit for one provider should not affect another."""
        for _ in range(_CIRCUIT_BREAKER_THRESHOLD):
            self.svc._record_provider_failure("moka")
        self.assertTrue(self.svc._is_provider_circuit_open("moka"))
        self.assertFalse(self.svc._is_provider_circuit_open("glm"))


# ---------------------------------------------------------------------------
# _call_openai_compat / _call_ollama
# ---------------------------------------------------------------------------
class TestCallOpenAICompat(unittest.TestCase):
    def setUp(self):
        self.svc = SimpleLLMService.__new__(SimpleLLMService)
        self.svc._api_key = "sk-test"
        self.svc._base_url = "https://api.test/v1"
        self.svc._model = "test-model"
        self.svc._is_ollama = False

    @patch("opc_manager.simple_llm_service.requests.post")
    def test_successful_call(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Hello world"}}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = self.svc._call_openai_compat("hi", "sys", 100, 30)
        self.assertEqual(result, "Hello world")

    @patch("opc_manager.simple_llm_service.requests.post")
    def test_returns_none_on_empty_content(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": ""}}]}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = self.svc._call_openai_compat("hi", None, 100, 30)
        self.assertIsNone(result)

    @patch("opc_manager.simple_llm_service.requests.post")
    def test_raises_on_http_error(self, mock_post):
        mock_post.side_effect = Exception("Connection refused")
        with self.assertRaises(Exception):
            self.svc._call_openai_compat("hi", None, 100, 30)

    @patch("opc_manager.simple_llm_service.requests.post")
    def test_sends_correct_headers(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        self.svc._call_openai_compat("hi", "sys", 100, 30)
        call_kwargs = mock_post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
        self.assertIn("Bearer", headers.get("Authorization", ""))


class TestCallOllama(unittest.TestCase):
    def setUp(self):
        self.svc = SimpleLLMService.__new__(SimpleLLMService)
        self.svc._api_key = "ollama"
        self.svc._base_url = "http://localhost:11434"
        self.svc._model = "llama3"
        self.svc._is_ollama = True

    @patch("opc_manager.simple_llm_service.requests.post")
    def test_successful_ollama_call(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "Ollama reply"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = self.svc._call_ollama("hi", "sys", 100, 30)
        self.assertEqual(result, "Ollama reply")

    @patch("opc_manager.simple_llm_service.requests.post")
    def test_ollama_returns_none_on_empty(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": ""}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = self.svc._call_ollama("hi", None, 100, 30)
        self.assertIsNone(result)

    @patch("opc_manager.simple_llm_service.requests.post")
    def test_ollama_includes_system_prompt_in_payload(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "ok"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        self.svc._call_ollama("hi", "system instruction", 100, 30)
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json", {})
        self.assertEqual(payload["system"], "system instruction")


# ---------------------------------------------------------------------------
# complete() — retry, fallback, error handling
# ---------------------------------------------------------------------------
class TestComplete(unittest.TestCase):
    def setUp(self):
        self.svc = SimpleLLMService.__new__(SimpleLLMService)
        self.svc._api_key = "sk-test"
        self.svc._base_url = "https://api.test/v1"
        self.svc._model = "test-model"
        self.svc._is_ollama = False
        self.svc._circuit_breaker = {}

    @patch("opc_manager.simple_llm_service._discover_all_providers", return_value=[])
    @patch("opc_manager.llm_cache.get_llm_cache", return_value=None)
    @patch("opc_manager.utils._llm_thread_semaphore")
    @patch("opc_manager.utils.sanitize_for_llm", side_effect=lambda x, _: x)
    def test_complete_returns_none_when_no_api_key(
        self, mock_sanitize, mock_sem, mock_cache, mock_providers
    ):
        self.svc._api_key = ""
        result = self.svc.complete("hello")
        self.assertIsNone(result)

    @patch("opc_manager.simple_llm_service._discover_all_providers", return_value=[])
    @patch("opc_manager.llm_cache.get_llm_cache", return_value=None)
    @patch("opc_manager.utils._llm_thread_semaphore")
    @patch("opc_manager.utils.sanitize_for_llm", side_effect=lambda x, _: x)
    @patch.object(SimpleLLMService, "_call_openai_compat", return_value="LLM response")
    def test_complete_success_on_first_try(
        self, mock_call, mock_sanitize, mock_sem, mock_cache, mock_providers
    ):
        mock_sem.acquire = MagicMock()
        mock_sem.release = MagicMock()
        result = self.svc.complete("hello")
        self.assertEqual(result, "LLM response")

    @patch("opc_manager.simple_llm_service._discover_all_providers", return_value=[])
    @patch("opc_manager.llm_cache.get_llm_cache", return_value=None)
    @patch("opc_manager.utils._llm_thread_semaphore")
    @patch("opc_manager.utils.sanitize_for_llm", side_effect=lambda x, _: x)
    @patch.object(
        SimpleLLMService, "_call_openai_compat", side_effect=Exception("fail")
    )
    @patch("opc_manager.simple_llm_service.time.sleep", return_value=None)
    def test_complete_retries_on_failure(
        self, mock_sleep, mock_call, mock_sanitize, mock_sem, mock_cache, mock_providers
    ):
        mock_sem.acquire = MagicMock()
        mock_sem.release = MagicMock()
        result = self.svc.complete("hello")
        self.assertIsNone(result)
        self.assertEqual(mock_call.call_count, LLM_MAX_RETRIES)

    @patch("opc_manager.simple_llm_service._discover_all_providers")
    @patch("opc_manager.llm_cache.get_llm_cache", return_value=None)
    @patch("opc_manager.utils._llm_thread_semaphore")
    @patch("opc_manager.utils.sanitize_for_llm", side_effect=lambda x, _: x)
    @patch.object(
        SimpleLLMService, "_call_openai_compat", side_effect=Exception("primary fail")
    )
    @patch.object(SimpleLLMService, "_try_provider", return_value="fallback response")
    @patch("opc_manager.simple_llm_service.time.sleep", return_value=None)
    def test_complete_fallback_to_other_provider(
        self,
        mock_sleep,
        mock_try,
        mock_call,
        mock_sanitize,
        mock_sem,
        mock_cache,
        mock_providers,
    ):
        mock_sem.acquire = MagicMock()
        mock_sem.release = MagicMock()
        mock_providers.return_value = [
            {
                "api_key": "sk-other",
                "base_url": "https://other.test/v1",
                "model": "other-model",
                "is_ollama": False,
                "name": "glm",
            }
        ]
        result = self.svc.complete("hello")
        self.assertEqual(result, "fallback response")

    @patch("opc_manager.simple_llm_service._discover_all_providers", return_value=[])
    @patch("opc_manager.llm_cache.get_llm_cache")
    @patch("opc_manager.utils._llm_thread_semaphore")
    @patch("opc_manager.utils.sanitize_for_llm", side_effect=lambda x, _: x)
    @patch.object(SimpleLLMService, "_call_openai_compat", return_value="cached miss")
    def test_complete_uses_cache(
        self, mock_call, mock_sanitize, mock_sem, mock_cache_fn, mock_providers
    ):
        mock_cache = MagicMock()
        mock_cache.get.return_value = "cached response"
        mock_cache_fn.return_value = mock_cache
        mock_sem.acquire = MagicMock()
        mock_sem.release = MagicMock()
        result = self.svc.complete("hello")
        self.assertEqual(result, "cached response")
        mock_call.assert_not_called()


# ---------------------------------------------------------------------------
# _discover_all_providers
# ---------------------------------------------------------------------------
class TestDiscoverAllProviders(unittest.TestCase):
    @patch("opc_manager.simple_llm_service.os.environ.get")
    @patch("opc_manager.settings.get_settings", side_effect=ImportError)
    def test_discovers_glm_and_openai(self, mock_get_settings, mock_env_get):
        def env_side_effect(key, default=""):
            mapping = {
                "MOKA_API_KEY": "",
                "MOKA_API_BASE": "https://api.moka-ai.com/v1",
                "MOKA_MODEL": "moka/claude-sonnet-4-6",
                "GLM_API_KEY": "glm-key",
                "OPENAI_API_KEY": "openai-key",
                "OPENAI_API_BASE": "https://api.openai.com/v1",
                "OLLAMA_BASE_URL": "",
                "OLLAMA_ENABLED": "",
                "OLLAMA_MODEL": "llama3",
            }
            return mapping.get(key, default)

        mock_env_get.side_effect = env_side_effect
        providers = _discover_all_providers()
        names = [p["name"] for p in providers]
        self.assertIn("glm", names)
        self.assertIn("openai", names)

    @patch("opc_manager.simple_llm_service.os.environ.get")
    @patch("opc_manager.settings.get_settings", side_effect=ImportError)
    def test_discovers_ollama(self, mock_get_settings, mock_env_get):
        def env_side_effect(key, default=""):
            mapping = {
                "MOKA_API_KEY": "",
                "MOKA_API_BASE": "https://api.moka-ai.com/v1",
                "MOKA_MODEL": "moka/claude-sonnet-4-6",
                "GLM_API_KEY": "",
                "OPENAI_API_KEY": "",
                "OPENAI_API_BASE": "https://api.openai.com/v1",
                "OLLAMA_BASE_URL": "http://localhost:11434",
                "OLLAMA_ENABLED": "true",
                "OLLAMA_MODEL": "llama3",
            }
            return mapping.get(key, default)

        mock_env_get.side_effect = env_side_effect
        providers = _discover_all_providers()
        names = [p["name"] for p in providers]
        self.assertIn("ollama", names)
        ollama = next(p for p in providers if p["name"] == "ollama")
        self.assertTrue(ollama["is_ollama"])


if __name__ == "__main__":
    unittest.main()
