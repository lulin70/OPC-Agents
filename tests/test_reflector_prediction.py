"""
[S2-T5] ReflectorBrain.predict_consequence() 前置预判方法测试

少数派报告模式：在执行前预测行动后果，用于三贤者并行投票架构。
覆盖：LLM 预判、规则降级、异步版本、brain_type 校验、高/低风险行动、reasoning 校验。
"""

import asyncio
import json

import pytest

from opc_manager.reflector_brain import ReflectorBrain
from opc_manager.consensus_engine import Opinion, OpinionType


class MockLLMService:
    """Mock LLM service for testing - returns preset response"""

    def __init__(self, response: str):
        self.response = response
        self.call_count = 0
        self.last_prompt = ""

    def complete(self, prompt, max_tokens=500, timeout=15):
        self.call_count += 1
        self.last_prompt = prompt
        return self.response


class FailingLLMService:
    """LLM service that always raises an exception"""

    def complete(self, prompt, max_tokens=500, timeout=15):
        raise RuntimeError("LLM service unavailable")


def _run_async(coro):
    """Helper to run async coroutines in tests.

    Uses asyncio.run() to avoid event loop corruption.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=30)
    return asyncio.run(coro)


def _make_context(user_input="帮我搜索AI趋势", intent="search", plan="搜索并分析"):
    return {
        "user_input": user_input,
        "intent": intent,
        "plan": plan,
    }


def _make_low_risk_action():
    return {
        "skill_id": "search",
        "action": "query",
        "parameters": {"query": "AI趋势"},
    }


def _make_high_risk_action():
    return {
        "skill_id": "send_email",
        "action": "send",
        "parameters": {
            "to": "user@example.com",
            "subject": "test",
            "body": "content",
        },
    }


# LLM preset responses
_LLM_AGREE_RESPONSE = json.dumps(
    {
        "opinion_type": "AGREE",
        "reasoning": "该查询操作可逆且无副作用，符合用户搜索意图，预判无风险",
        "confidence": 0.85,
        "alternative": None,
    }
)

_LLM_DISAGREE_RESPONSE = json.dumps(
    {
        "opinion_type": "DISAGREE",
        "reasoning": "发送邮件操作不可逆，可能泄露敏感信息，且未确认收件人意图",
        "confidence": 0.8,
        "alternative": "建议先草拟邮件内容并请求用户确认",
    }
)


class TestPredictConsequence:
    """predict_consequence() 方法测试"""

    def test_predict_consequence_with_llm(self):
        """有 llm_service 时调用 LLM 返回 Opinion"""
        mock_llm = MockLLMService(_LLM_AGREE_RESPONSE)
        brain = ReflectorBrain(llm_service=mock_llm)
        opinion = brain.predict_consequence(_make_context(), _make_low_risk_action())

        assert isinstance(opinion, Opinion)
        assert mock_llm.call_count == 1
        assert opinion.opinion_type == OpinionType.AGREE
        assert opinion.confidence == 0.85

    def test_predict_consequence_without_llm(self):
        """无 llm_service 时降级到规则预判"""
        brain = ReflectorBrain(llm_service=None)
        opinion = brain.predict_consequence(_make_context(), _make_low_risk_action())

        assert isinstance(opinion, Opinion)
        assert opinion.opinion_type == OpinionType.AGREE
        assert opinion.reasoning != ""

    def test_predict_consequence_async(self):
        """异步版本正常工作"""
        brain = ReflectorBrain(llm_service=None)
        opinion = _run_async(
            brain.predict_consequence_async(_make_context(), _make_low_risk_action())
        )

        assert isinstance(opinion, Opinion)
        assert opinion.brain_type == "reflector"
        assert opinion.opinion_type == OpinionType.AGREE

    def test_predict_consequence_returns_correct_brain_type(self):
        """返回的 brain_type 为 reflector"""
        brain = ReflectorBrain(llm_service=None)
        opinion = brain.predict_consequence(_make_context(), _make_low_risk_action())

        assert opinion.brain_type == "reflector"

    def test_predict_consequence_high_risk_action(self):
        """高风险行动（如发送邮件）预判返回 DISAGREE 或 CONDITIONAL"""
        brain = ReflectorBrain(llm_service=None)
        opinion = brain.predict_consequence(_make_context(), _make_high_risk_action())

        assert opinion.opinion_type in (
            OpinionType.DISAGREE,
            OpinionType.CONDITIONAL,
        )
        assert opinion.brain_type == "reflector"

    def test_predict_consequence_low_risk_action(self):
        """低风险行动（如查询）预判返回 AGREE"""
        brain = ReflectorBrain(llm_service=None)
        opinion = brain.predict_consequence(_make_context(), _make_low_risk_action())

        assert opinion.opinion_type == OpinionType.AGREE

    def test_predict_consequence_reasoning_not_empty(self):
        """reasoning 非空，包含后果描述"""
        brain = ReflectorBrain(llm_service=None)
        opinion = brain.predict_consequence(_make_context(), _make_low_risk_action())

        assert opinion.reasoning
        assert len(opinion.reasoning) > 0
        # reasoning 应包含后果相关描述关键词
        assert any(
            kw in opinion.reasoning for kw in ["预判", "风险", "操作", "可逆", "副作用"]
        )

    def test_predict_consequence_llm_failure_degrades_gracefully(self):
        """LLM 调用失败时降级到规则预判，不抛异常"""
        brain = ReflectorBrain(llm_service=FailingLLMService())
        opinion = brain.predict_consequence(_make_context(), _make_low_risk_action())

        assert isinstance(opinion, Opinion)
        assert opinion.opinion_type == OpinionType.AGREE

    def test_predict_consequence_llm_malformed_response_degrades(self):
        """LLM 返回非 JSON 时降级到规则预判"""
        mock_llm = MockLLMService("NOT JSON AT ALL")
        brain = ReflectorBrain(llm_service=mock_llm)
        opinion = brain.predict_consequence(_make_context(), _make_low_risk_action())

        assert isinstance(opinion, Opinion)
        assert opinion.opinion_type == OpinionType.AGREE

    def test_predict_consequence_llm_disagree_response(self):
        """LLM 返回 DISAGREE 时正确解析"""
        mock_llm = MockLLMService(_LLM_DISAGREE_RESPONSE)
        brain = ReflectorBrain(llm_service=mock_llm)
        opinion = brain.predict_consequence(_make_context(), _make_high_risk_action())

        assert opinion.opinion_type == OpinionType.DISAGREE
        assert "不可逆" in opinion.reasoning
        assert opinion.alternative is not None

    def test_predict_consequence_prompt_contains_action_info(self):
        """LLM prompt 应包含计划行动信息"""
        mock_llm = MockLLMService(_LLM_AGREE_RESPONSE)
        brain = ReflectorBrain(llm_service=mock_llm)
        brain.predict_consequence(_make_context(), _make_low_risk_action())

        assert "search" in mock_llm.last_prompt
        assert "query" in mock_llm.last_prompt

    def test_predict_consequence_preserves_existing_methods(self):
        """确保现有方法仍然可用（向后兼容）"""
        brain = ReflectorBrain(llm_service=None)
        actual = {"success": True, "data": {"content": "result"}}
        expected = {"goal": "test"}
        evaluation = brain.evaluate_result(actual, expected)

        assert evaluation is not None
        assert hasattr(brain, "decide_next_action")
        assert hasattr(brain, "suggest_correction_strategy")
        assert hasattr(brain, "express_opinion")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
