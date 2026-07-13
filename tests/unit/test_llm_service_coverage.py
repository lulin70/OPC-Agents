"""Coverage tests for opc_manager.llm_service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opc_manager.llm_service import (
    LLMConfig,
    LLMProvider,
    LLMResponse,
    LLMService,
    OllamaBackend,
    OpenAIBackend,
    UsageTracker,
)


class TestLLMConfig:
    """Verify: LLMConfig defaults."""

    def test_default_config(self):
        config = LLMConfig()
        assert config.provider == LLMProvider.MOKA
        assert config.model == "moka/claude-sonnet-4-6"
        assert config.max_tokens == 500
        assert config.temperature == 0.3
        assert config.timeout_seconds == 60.0
        assert config.max_retries == 2
        assert config.cost_budget_daily == 5.0


class TestOpenAIBackend:
    """Verify: OpenAIBackend behavior."""

    def test_validate_config_valid(self):
        config = LLMConfig(api_key="sk-1234567890abcdef")
        backend = OpenAIBackend(config)
        assert backend.validate_config() is True

    def test_validate_config_empty_key(self):
        config = LLMConfig(api_key="")
        backend = OpenAIBackend(config)
        assert backend.validate_config() is False

    def test_validate_config_short_key(self):
        config = LLMConfig(api_key="short")
        backend = OpenAIBackend(config)
        assert backend.validate_config() is False

    def test_estimate_cost_gpt4(self):
        config = LLMConfig(model="gpt-4")
        backend = OpenAIBackend(config)
        cost = backend.estimate_cost("a" * 4000)
        assert cost > 0

    def test_estimate_cost_gpt35(self):
        config = LLMConfig(model="gpt-3.5-turbo")
        backend = OpenAIBackend(config)
        cost = backend.estimate_cost("a" * 4000)
        assert cost > 0

    def test_estimate_cost_other_model(self):
        config = LLMConfig(model="claude-sonnet")
        backend = OpenAIBackend(config)
        cost = backend.estimate_cost("a" * 4000)
        assert cost > 0

    @pytest.mark.asyncio
    async def test_get_client_creates_async_openai(self):
        config = LLMConfig(api_key="sk-test1234567890")
        backend = OpenAIBackend(config)
        with patch.dict("sys.modules", {"openai": MagicMock()}):
            mock_openai = MagicMock()
            mock_client = MagicMock()
            mock_openai.AsyncOpenAI.return_value = mock_client
            import sys

            sys.modules["openai"] = mock_openai
            client = await backend._get_client()
            assert client is mock_client

    @pytest.mark.asyncio
    async def test_get_client_import_error(self):
        config = LLMConfig(api_key="sk-test1234567890")
        backend = OpenAIBackend(config)
        backend.client = None
        with patch.dict("sys.modules", {"openai": None}):
            import builtins

            real_import = builtins.__import__

            def fake_import(name, *args, **kwargs):
                if name == "openai":
                    raise ImportError("no openai")
                return real_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=fake_import):
                with pytest.raises(RuntimeError, match="openai package not installed"):
                    await backend._get_client()

    @pytest.mark.asyncio
    async def test_complete_success(self):
        config = LLMConfig(api_key="sk-test1234567890", model="gpt-4")
        backend = OpenAIBackend(config)
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        backend.client = mock_client

        response = await backend.complete("test prompt", "system prompt")
        assert response.content == "Hello"
        assert response.provider == LLMProvider.OPENAI
        assert response.usage["total_tokens"] == 15

    @pytest.mark.asyncio
    async def test_complete_exception_reraises(self):
        config = LLMConfig(api_key="sk-test1234567890")
        backend = OpenAIBackend(config)
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("API error")
        )
        backend.client = mock_client

        with pytest.raises(RuntimeError, match="API error"):
            await backend.complete("prompt")


class TestOllamaBackend:
    """Verify: OllamaBackend behavior."""

    def test_estimate_cost_zero(self):
        config = LLMConfig(provider=LLMProvider.OLLAMA)
        backend = OllamaBackend(config)
        assert backend.estimate_cost("any prompt") == 0.0

    def test_validate_config_success(self):
        config = LLMConfig(
            provider=LLMProvider.OLLAMA, base_url="http://localhost:11434"
        )
        backend = OllamaBackend(config)
        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            assert backend.validate_config() is True

    def test_validate_config_failure(self):
        config = LLMConfig(
            provider=LLMProvider.OLLAMA, base_url="http://localhost:11434"
        )
        backend = OllamaBackend(config)
        with patch("httpx.get", side_effect=Exception("connection refused")):
            assert backend.validate_config() is False

    @pytest.mark.asyncio
    async def test_complete_success(self):
        config = LLMConfig(
            provider=LLMProvider.OLLAMA,
            model="llama2",
            base_url="http://localhost:11434",
        )
        backend = OllamaBackend(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "response": "Ollama result",
            "prompt_eval_count": 10,
            "eval_count": 5,
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            response = await backend.complete("test", "system")
        assert response.content == "Ollama result"
        assert response.provider == LLMProvider.OLLAMA
        assert response.usage["total_tokens"] == 15

    @pytest.mark.asyncio
    async def test_complete_with_total_duration(self):
        config = LLMConfig(
            provider=LLMProvider.OLLAMA,
            model="llama2",
            base_url="http://localhost:11434",
        )
        backend = OllamaBackend(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "response": "result",
            "prompt_eval_count": 5,
            "eval_count": 3,
            "total_duration": 50_000_000,
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            response = await backend.complete("test")
        assert response.latency_ms == 50.0


class TestUsageTracker:
    """Verify: UsageTracker budget tracking."""

    def test_record_usage(self):
        tracker = UsageTracker(daily_budget=5.0)
        tracker.record("user1", {"total_tokens": 100}, cost_usd=0.01)
        report = tracker.get_report()
        today_key = list(report["daily"].keys())[0]
        assert report["daily"][today_key]["tokens"] == 100
        assert report["daily"][today_key]["calls"] == 1
        assert report["daily"][today_key]["cost"] == 0.01

    def test_is_budget_exceeded_false(self):
        tracker = UsageTracker(daily_budget=5.0)
        tracker.record("user1", {"total_tokens": 100}, cost_usd=1.0)
        assert not tracker.is_budget_exceeded()

    def test_is_budget_exceeded_true(self):
        tracker = UsageTracker(daily_budget=5.0)
        tracker.record("user1", {"total_tokens": 100}, cost_usd=5.0)
        assert tracker.is_budget_exceeded()

    def test_get_report(self):
        tracker = UsageTracker(daily_budget=10.0)
        report = tracker.get_report()
        assert report["budget"] == 10.0
        assert "daily" in report


class TestLLMService:
    """Verify: LLMService unified entry point."""

    def test_create_backend_moka(self):
        config = LLMConfig(provider=LLMProvider.MOKA)
        service = LLMService(config)
        assert isinstance(service.backend, OpenAIBackend)

    def test_create_backend_ollama(self):
        config = LLMConfig(provider=LLMProvider.OLLAMA)
        service = LLMService(config)
        assert isinstance(service.backend, OllamaBackend)

    def test_create_backend_unknown_falls_back(self):
        config = LLMConfig(provider=LLMProvider.MOKA)
        service = LLMService(config)
        with patch.object(LLMService, "BACKEND_MAP", {}):
            backend = service._create_backend(LLMProvider.MOKA)
        assert isinstance(backend, OpenAIBackend)

    def test_default_config(self):
        service = LLMService()
        assert service.config is not None
        assert service.usage_tracker is not None

    @pytest.mark.asyncio
    async def test_detect_business_type_success(self):
        config = LLMConfig(provider=LLMProvider.MOKA, api_key="sk-test1234567890")
        service = LLMService(config)

        mock_response = LLMResponse(
            content='{"business_type": "content_creator", "confidence": 0.95, "reasoning": "test"}',
            provider=LLMProvider.MOKA,
            model="test",
            usage={"total_tokens": 10},
            latency_ms=100.0,
        )
        service.backend.complete = AsyncMock(return_value=mock_response)

        result = await service.detect_business_type_by_llm("I write articles")
        assert result["business_type"] == "content_creator"
        assert result["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_detect_business_type_with_markdown_fence(self):
        config = LLMConfig(provider=LLMProvider.MOKA, api_key="sk-test1234567890")
        service = LLMService(config)

        mock_response = LLMResponse(
            content='```json\n{"business_type": "ecommerce", "confidence": 0.8, "reasoning": "shop"}\n```',
            provider=LLMProvider.MOKA,
            model="test",
            usage={"total_tokens": 10},
            latency_ms=100.0,
        )
        service.backend.complete = AsyncMock(return_value=mock_response)

        result = await service.detect_business_type_by_llm("I sell products")
        assert result["business_type"] == "ecommerce"

    @pytest.mark.asyncio
    async def test_detect_business_type_json_decode_error_retries(self):
        config = LLMConfig(provider=LLMProvider.MOKA, api_key="sk-test1234567890")
        service = LLMService(config)

        mock_response = LLMResponse(
            content="not valid json",
            provider=LLMProvider.MOKA,
            model="test",
            usage={"total_tokens": 10},
            latency_ms=100.0,
        )
        service.backend.complete = AsyncMock(return_value=mock_response)

        result = await service.detect_business_type_by_llm("test", max_retries=1)
        assert result["business_type"] == "unknown"
        assert "JSON" in result["reasoning"] or "格式" in result["reasoning"]

    @pytest.mark.asyncio
    async def test_detect_business_type_missing_field(self):
        config = LLMConfig(provider=LLMProvider.MOKA, api_key="sk-test1234567890")
        service = LLMService(config)

        mock_response = LLMResponse(
            content='{"confidence": 0.5}',
            provider=LLMProvider.MOKA,
            model="test",
            usage={"total_tokens": 10},
            latency_ms=100.0,
        )
        service.backend.complete = AsyncMock(return_value=mock_response)

        result = await service.detect_business_type_by_llm("test", max_retries=0)
        assert result["business_type"] == "unknown"

    @pytest.mark.asyncio
    async def test_detect_business_type_exception(self):
        config = LLMConfig(provider=LLMProvider.MOKA, api_key="sk-test1234567890")
        service = LLMService(config)

        service.backend.complete = AsyncMock(side_effect=RuntimeError("network error"))

        result = await service.detect_business_type_by_llm("test", max_retries=0)
        assert result["business_type"] == "unknown"
        assert "network error" in result["reasoning"]

    @pytest.mark.asyncio
    async def test_generate_persona_response_success(self):
        config = LLMConfig(provider=LLMProvider.MOKA, api_key="sk-test1234567890")
        service = LLMService(config)

        mock_response = LLMResponse(
            content="Hello, I am your assistant!",
            provider=LLMProvider.MOKA,
            model="test",
            usage={"total_tokens": 10},
            latency_ms=100.0,
        )
        service.backend.complete = AsyncMock(return_value=mock_response)

        result = await service.generate_persona_response(
            "hi",
            {
                "display_name": "AI Assistant",
                "expertise_tags": ["coding"],
                "style_overrides": {"tone": "friendly"},
            },
        )
        assert result == "Hello, I am your assistant!"

    @pytest.mark.asyncio
    async def test_generate_persona_response_exception(self):
        config = LLMConfig(provider=LLMProvider.MOKA, api_key="sk-test1234567890")
        service = LLMService(config)

        service.backend.complete = AsyncMock(side_effect=RuntimeError("fail"))

        result = await service.generate_persona_response("hi", {})
        assert "抱歉" in result

    def test_switch_provider(self):
        config = LLMConfig(provider=LLMProvider.MOKA, api_key="sk-test1234567890")
        service = LLMService(config)
        service.switch_provider(LLMProvider.OLLAMA, base_url="http://localhost:11434")
        assert service.config.provider == LLMProvider.OLLAMA
        assert isinstance(service.backend, OllamaBackend)

    def test_get_usage_report(self):
        config = LLMConfig(provider=LLMProvider.MOKA, api_key="sk-test1234567890")
        service = LLMService(config)
        report = service.get_usage_report()
        assert "daily" in report
        assert "budget" in report
