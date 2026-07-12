"""
ExecutorBrain.express_opinion() 单元测试 [S2-T3]

覆盖三贤者并行投票架构中执行脑真实 LLM 意见方法：
- 有 llm_service 时调用 LLM 返回 Opinion
- 无 llm_service 时降级到规则判断
- 异步版本正常工作
- brain_type 固定为 "executor"
- AGREE / DISAGREE / CONDITIONAL 解析
- LLM 调用失败时降级到规则判断
"""

import asyncio
import json
import unittest

from opc_manager.executor_brain import ExecutorBrain
from opc_manager.consensus_engine import Opinion, OpinionType


class MockLLMService:
    """Mock LLM 服务，返回预设响应。

    call_llm_service() 优先调用 llm_service.complete(prompt, ...)，
    因此实现 complete 方法即可。
    """

    def __init__(self, response: str):
        self._response = response
        self.call_count = 0
        self.last_prompt = ""

    def complete(self, prompt, max_tokens=500, timeout=15):
        self.call_count += 1
        self.last_prompt = prompt
        return self._response


class RaisingLLMService:
    """Mock LLM 服务，complete 调用总是抛出指定异常。

    用于验证 LLM 调用失败时执行脑降级到规则判断的容错路径。
    """

    def __init__(self, exc: Exception):
        self._exc = exc
        self.call_count = 0

    def complete(self, prompt, max_tokens=500, timeout=15):
        self.call_count += 1
        raise self._exc


def _llm_json(opinion_type: str, reasoning: str, confidence: float) -> str:
    """构造 LLM 返回的 JSON 字符串。"""
    return json.dumps(
        {
            "opinion_type": opinion_type,
            "reasoning": reasoning,
            "confidence": confidence,
        },
        ensure_ascii=False,
    )


class TestExpressOpinionWithLLM(unittest.TestCase):
    """有 llm_service 时的 LLM 判断路径"""

    def test_express_opinion_with_llm(self):
        """有 llm_service 时调用 LLM 返回 Opinion"""
        llm = MockLLMService(_llm_json("AGREE", "执行可行", 0.9))
        executor = ExecutorBrain(llm_service=llm)

        opinion = executor.express_opinion(
            {"retry_count": 0, "user_input": "发送邮件"},
            "send_email",
        )

        self.assertEqual(llm.call_count, 1)
        self.assertIsInstance(opinion, Opinion)
        self.assertEqual(opinion.opinion_type, OpinionType.AGREE)
        self.assertEqual(opinion.reasoning, "执行可行")
        self.assertAlmostEqual(opinion.confidence, 0.9)

    def test_express_opinion_agree(self):
        """LLM 返回同意时 OpinionType.AGREE"""
        llm = MockLLMService(_llm_json("AGREE", "无风险", 0.85))
        executor = ExecutorBrain(llm_service=llm)

        opinion = executor.express_opinion({"retry_count": 0}, "execute_operation")

        self.assertEqual(opinion.opinion_type, OpinionType.AGREE)
        self.assertGreater(opinion.confidence, 0.5)

    def test_express_opinion_disagree(self):
        """LLM 返回不同意时 OpinionType.DISAGREE"""
        llm = MockLLMService(_llm_json("DISAGREE", "已多次失败", 0.8))
        executor = ExecutorBrain(llm_service=llm)

        opinion = executor.express_opinion({"retry_count": 3}, "data_persist")

        self.assertEqual(opinion.opinion_type, OpinionType.DISAGREE)

    def test_express_opinion_conditional(self):
        """LLM 返回条件同意时 OpinionType.CONDITIONAL"""
        llm = MockLLMService(_llm_json("CONDITIONAL", "需确认收件人", 0.6))
        executor = ExecutorBrain(llm_service=llm)

        opinion = executor.express_opinion({"retry_count": 0}, "send_email")

        self.assertEqual(opinion.opinion_type, OpinionType.CONDITIONAL)

    def test_express_opinion_returns_correct_brain_type(self):
        """返回的 brain_type 为 'executor'"""
        llm = MockLLMService(_llm_json("AGREE", "ok", 0.7))
        executor = ExecutorBrain(llm_service=llm)

        opinion = executor.express_opinion({"retry_count": 0}, "send_email")

        self.assertEqual(opinion.brain_type, "executor")

    def test_express_opinion_lowercase_type_parsed(self):
        """LLM 返回小写 opinion_type 时仍能正确解析"""
        llm = MockLLMService(_llm_json("agree", "ok", 0.7))
        executor = ExecutorBrain(llm_service=llm)

        opinion = executor.express_opinion({"retry_count": 0}, "send_email")

        self.assertEqual(opinion.opinion_type, OpinionType.AGREE)

    def test_express_opinion_invalid_confidence_defaults(self):
        """LLM 返回非法 confidence 时降级到默认值"""
        llm = MockLLMService(
            json.dumps(
                {"opinion_type": "AGREE", "reasoning": "ok", "confidence": "bad"},
                ensure_ascii=False,
            )
        )
        executor = ExecutorBrain(llm_service=llm)

        opinion = executor.express_opinion({"retry_count": 0}, "send_email")

        self.assertEqual(opinion.opinion_type, OpinionType.AGREE)
        self.assertAlmostEqual(opinion.confidence, 0.7)


class TestExpressOpinionWithoutLLM(unittest.TestCase):
    """无 llm_service 时降级到规则判断"""

    def test_express_opinion_without_llm(self):
        """无 llm_service 时降级到规则判断"""
        executor = ExecutorBrain()

        opinion = executor.express_opinion({"retry_count": 0}, "send_email")

        self.assertIsInstance(opinion, Opinion)
        self.assertEqual(opinion.brain_type, "executor")
        self.assertEqual(opinion.opinion_type, OpinionType.AGREE)

    def test_rulebased_agree_when_low_retry(self):
        """retry_count < 2 时规则判断为 AGREE"""
        executor = ExecutorBrain()

        opinion = executor.express_opinion({"retry_count": 1}, "execute_operation")

        self.assertEqual(opinion.opinion_type, OpinionType.AGREE)
        self.assertGreaterEqual(opinion.confidence, 0.3)

    def test_rulebased_disagree_when_high_retry(self):
        """retry_count >= 2 时规则判断为 DISAGREE"""
        executor = ExecutorBrain()

        opinion = executor.express_opinion({"retry_count": 5}, "data_persist")

        self.assertEqual(opinion.opinion_type, OpinionType.DISAGREE)

    def test_rulebased_confidence_floor(self):
        """规则判断置信度不低于 0.3"""
        executor = ExecutorBrain()

        opinion = executor.express_opinion({"retry_count": 10}, "data_persist")

        self.assertGreaterEqual(opinion.confidence, 0.3)

    def test_rulebased_brain_type_executor(self):
        """规则判断返回 brain_type 为 'executor'"""
        executor = ExecutorBrain()

        opinion = executor.express_opinion({"retry_count": 0}, "send_email")

        self.assertEqual(opinion.brain_type, "executor")


class TestExpressOpinionLLMFailure(unittest.TestCase):
    """LLM 调用失败时降级到规则判断"""

    def test_llm_returns_empty_falls_back_to_rule(self):
        """LLM 返回空字符串时降级到规则判断"""
        llm = MockLLMService("")
        executor = ExecutorBrain(llm_service=llm)

        opinion = executor.express_opinion({"retry_count": 0}, "send_email")

        self.assertEqual(opinion.opinion_type, OpinionType.AGREE)
        self.assertEqual(opinion.brain_type, "executor")

    def test_llm_returns_invalid_json_falls_back(self):
        """LLM 返回非法 JSON 时降级到规则判断"""
        llm = MockLLMService("not a json at all")
        executor = ExecutorBrain(llm_service=llm)

        opinion = executor.express_opinion({"retry_count": 3}, "send_email")

        self.assertEqual(opinion.opinion_type, OpinionType.DISAGREE)

    def test_llm_raises_exception_falls_back(self):
        """LLM 调用抛异常时降级到规则判断，不抛出"""
        llm = RaisingLLMService(RuntimeError("network error"))
        executor = ExecutorBrain(llm_service=llm)

        opinion = executor.express_opinion({"retry_count": 0}, "send_email")

        self.assertEqual(opinion.brain_type, "executor")
        self.assertEqual(opinion.opinion_type, OpinionType.AGREE)


class TestExpressOpinionAsync(unittest.TestCase):
    """异步版本测试"""

    def test_express_opinion_async(self):
        """异步版本正常工作"""
        llm = MockLLMService(_llm_json("AGREE", "异步可行", 0.8))
        executor = ExecutorBrain(llm_service=llm)

        opinion = asyncio.run(
            executor.express_opinion_async({"retry_count": 0}, "send_email")
        )

        self.assertIsInstance(opinion, Opinion)
        self.assertEqual(opinion.brain_type, "executor")
        self.assertEqual(opinion.opinion_type, OpinionType.AGREE)
        self.assertEqual(llm.call_count, 1)

    def test_express_opinion_async_without_llm(self):
        """异步版本无 llm_service 时降级到规则判断"""
        executor = ExecutorBrain()

        opinion = asyncio.run(
            executor.express_opinion_async({"retry_count": 0}, "send_email")
        )

        self.assertEqual(opinion.brain_type, "executor")
        self.assertEqual(opinion.opinion_type, OpinionType.AGREE)

    def test_express_opinion_async_returns_opinion_type(self):
        """异步版本正确解析 DISAGREE"""
        llm = MockLLMService(_llm_json("DISAGREE", "风险过高", 0.9))
        executor = ExecutorBrain(llm_service=llm)

        opinion = asyncio.run(
            executor.express_opinion_async({"retry_count": 2}, "data_persist")
        )

        self.assertEqual(opinion.opinion_type, OpinionType.DISAGREE)


class TestExpressOpinionPromptContent(unittest.TestCase):
    """验证 prompt 包含决策点和上下文"""

    def test_prompt_contains_decision_point(self):
        """prompt 应包含决策点"""
        llm = MockLLMService(_llm_json("AGREE", "ok", 0.7))
        executor = ExecutorBrain(llm_service=llm)

        executor.express_opinion(
            {"retry_count": 1, "user_input": "测试输入"}, "send_email"
        )

        self.assertIn("send_email", llm.last_prompt)

    def test_prompt_contains_retry_count(self):
        """prompt 应包含重试次数"""
        llm = MockLLMService(_llm_json("AGREE", "ok", 0.7))
        executor = ExecutorBrain(llm_service=llm)

        executor.express_opinion({"retry_count": 2}, "send_email")

        self.assertIn("2", llm.last_prompt)


if __name__ == "__main__":
    unittest.main()
