"""Phase 3: LLM 服务层测试"""
import pytest
import asyncio
from opc_manager.llm_service import (
    LLMService, LLMConfig, LLMProvider,
    MockLLMBackend, UsageTracker
)


class TestMockLLMBackend:
    """Mock 后端测试"""

    @pytest.fixture
    def mock_backend(self):
        return MockLLMBackend(LLMConfig(provider=LLMProvider.MOCK))

    @pytest.mark.asyncio
    async def test_complete_returns_valid_response(self, mock_backend):
        response = await mock_backend.complete("测试输入")
        assert response.content is not None
        assert len(response.content) > 0
        assert response.provider == LLMProvider.MOCK
        assert response.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_detect_type_prompt_returns_json(self, mock_backend):
        response = await mock_backend.complete("detect this type: 我写小红书笔记")
        import json
        parsed = json.loads(response.content)
        assert "business_type" in parsed
        assert "confidence" in parsed

    @pytest.mark.asyncio
    async def test_latency_in_range(self, mock_backend):
        response = await mock_backend.complete("latency test")
        assert 50 <= response.latency_ms <= 200

    def test_validate_config_always_true(self, mock_backend):
        assert mock_backend.validate_config() is True

    def test_estimate_cost_zero(self, mock_backend):
        assert mock_backend.estimate_cost("anything") == 0.0


class TestLLMService:
    """LLM 服务统一入口测试"""

    @pytest.fixture
    def llm_service(self):
        return LLMService(LLMConfig(provider=LLMProvider.MOCK))

    @pytest.mark.asyncio
    async def test_detect_by_llm_returns_dict(self, llm_service):
        result = await llm_service.detect_business_type_by_llm(
            "我是一个做自媒体的博主"
        )
        assert isinstance(result, dict)
        assert "business_type" in result
        assert "confidence" in result

    @pytest.mark.asyncio
    async def test_detect_all_six_types(self, llm_service):
        inputs = [
            ("content_creator 我是一个写小红书的博主", "content_creator"),
            ("digital_product 我想卖电子书和课程", "digital_product"),
            ("ai_tool_builder 开发一个AI SaaS工具", "ai_tool_builder"),
            ("consultant 做企业数字化转型咨询", "consultant"),
            ("ecommerce 在抖音上卖货运营", "ecommerce"),
            ("creative_work 做UI设计和摄影", "creative_work"),
        ]
        for text, expected in inputs:
            result = await llm_service.detect_business_type_by_llm(text)
            assert result["business_type"] == expected, f"Failed: {text} -> {result}"

    @pytest.mark.asyncio
    async def test_persona_response_generation(self, llm_service):
        persona_config = {
            "display_name": "内容小助理",
            "style_overrides": {"tone": "轻松活泼"},
            "expertise_tags": ["内容趋势", "平台算法"],
        }
        response = await llm_service.generate_persona_response(
            "今天有什么热点？", persona_config
        )
        assert isinstance(response, str)
        assert len(response) > 5

    def test_switch_provider(self, llm_service):
        original = llm_service.config.provider
        llm_service.switch_provider(LLMProvider.MOCK)
        assert llm_service.config.provider == LLMProvider.MOCK


class TestUsageTracker:
    """用量追踪器测试"""

    def test_record_usage(self):
        tracker = UsageTracker(daily_budget=10.0)
        tracker.record("detect", {"total_tokens": 100}, 0.01)
        today = list(tracker.get_report()["daily"].keys())[0]
        data = tracker.get_report()["daily"][today]
        assert data["tokens"] == 100
        assert data["calls"] == 1

    def test_budget_exceeded(self):
        tracker = UsageTracker(daily_budget=0.01)
        tracker.record("test", {"total_tokens": 1000}, 0.02)
        assert tracker.is_budget_exceeded() is True

    def test_budget_not_exceeded(self):
        tracker = UsageTracker(daily_budget=100.0)
        tracker.record("test", {"total_tokens": 100}, 0.001)
        assert tracker.is_budget_exceeded() is False
