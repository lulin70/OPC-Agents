"""
三贤者并行投票测试 [S2-T2][S2-T4]

覆盖：
- 并行投票正常/否决/超时降级/全失败降级
- 串行降级路径
- 关键决策点识别
- 异步共识收集（含异常处理）
- 并行 vs 串行延迟对比 [S2-T9 预览]
"""

import asyncio
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch

from opc_manager.agent_loop import (
    AgentLoop,
)
from opc_manager.consensus_engine import (
    ConsensusEngine,
    Decision,
    DecisionType,
    Opinion,
    OpinionType,
)
from opc_manager.strategist_brain import Step


def _make_opinion(
    brain_type="strategist",
    opinion_type=OpinionType.AGREE,
    reasoning="test",
    confidence=0.8,
    alternative=None,
):
    """构造 Opinion 对象"""
    return Opinion(
        brain_type=brain_type,
        opinion_type=opinion_type,
        reasoning=reasoning,
        confidence=confidence,
        alternative=alternative,
    )


def _make_strategist_dict(opinion_type="AGREE", confidence=0.8):
    """构造 StrategistBrain.express_opinion 返回的 Dict"""
    return {
        "brain_type": "strategist",
        "opinion_type": opinion_type,
        "reasoning": "策略脑判断",
        "confidence": confidence,
    }


def _build_agent_loop():
    """构建带 mock brains 的 AgentLoop 用于测试。

    Returns:
        (loop, strategist, executor, reflector, engine) 元组
    """
    strategist = Mock()
    executor = Mock()
    reflector = Mock()

    with (
        patch.object(ConsensusEngine, "_load_decision_log_from_db"),
        patch.object(ConsensusEngine, "_log_decision"),
    ):
        engine = ConsensusEngine()

    loop = AgentLoop(
        strategist_brain=strategist,
        executor_brain=executor,
        reflector_brain=reflector,
        consensus_engine=engine,
        skill_registry=Mock(),
        tool_system=Mock(),
        session_manager=Mock(),
        task_engine=Mock(),
    )
    return loop, strategist, executor, reflector, engine


def _run_async(coro):
    """Helper to run async coroutines in tests."""
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


class TestParallelConsensus(unittest.TestCase):
    """三贤者并行投票测试 [S2-T2]"""

    def test_parallel_consensus_normal(self):
        """并行投票正常流程：三脑 AGREE → Decision.approved == True"""
        loop, strategist, executor, reflector, engine = _build_agent_loop()

        strategist.express_opinion = Mock(return_value=_make_strategist_dict())
        executor.express_opinion_async = AsyncMock(
            return_value=_make_opinion("executor", OpinionType.AGREE)
        )
        reflector.predict_consequence_async = AsyncMock(
            return_value=_make_opinion("reflector", OpinionType.AGREE)
        )

        context = {"user_input": "test", "retry_count": 0}
        step = Step(id="s1", skill_id="search", description="search")

        decision = _run_async(loop._parallel_consensus(context, "execute_step", step))

        self.assertIsInstance(decision, Decision)
        self.assertTrue(decision.approved)
        self.assertEqual(decision.decision_type, DecisionType.UNANIMOUS)

    def test_parallel_consensus_veto(self):
        """某脑否决时投票不通过：executor DISAGREE → approved == False"""
        loop, strategist, executor, reflector, engine = _build_agent_loop()

        strategist.express_opinion = Mock(return_value=_make_strategist_dict())
        executor.express_opinion_async = AsyncMock(
            return_value=_make_opinion("executor", OpinionType.DISAGREE, confidence=0.9)
        )
        reflector.predict_consequence_async = AsyncMock(
            return_value=_make_opinion("reflector", OpinionType.AGREE)
        )

        context = {"user_input": "test", "retry_count": 0}
        step = Step(id="s1", skill_id="search", description="search")

        decision = _run_async(loop._parallel_consensus(context, "execute_step", step))

        self.assertIsInstance(decision, Decision)
        self.assertFalse(decision.approved)

    def test_parallel_consensus_timeout_degrades_to_serial(self):
        """并行超时降级到串行"""
        loop, strategist, executor, reflector, engine = _build_agent_loop()

        # 串行 mock（超时降级后使用）
        strategist.express_opinion = Mock(return_value=_make_strategist_dict())
        executor.express_opinion = Mock(
            return_value=_make_opinion("executor", OpinionType.AGREE)
        )
        reflector.predict_consequence = Mock(
            return_value=_make_opinion("reflector", OpinionType.AGREE)
        )

        # 异步 mock 故意延迟以触发超时
        async def slow_executor(ctx, dp):
            await asyncio.sleep(5)
            return _make_opinion("executor")

        async def slow_reflector(ctx, pa):
            await asyncio.sleep(5)
            return _make_opinion("reflector")

        executor.express_opinion_async = AsyncMock(side_effect=slow_executor)
        reflector.predict_consequence_async = AsyncMock(side_effect=slow_reflector)

        context = {"user_input": "test", "retry_count": 0}
        step = Step(id="s1", skill_id="search", description="search")

        with patch("opc_manager.task_orchestrator.PARALLEL_VOTE_TIMEOUT", 0.1):
            decision = _run_async(
                loop._parallel_consensus(context, "execute_step", step)
            )

        self.assertIsInstance(decision, Decision)
        # 串行降级后三脑 AGREE → approved
        self.assertTrue(decision.approved)
        # 验证串行方法被调用
        strategist.express_opinion.assert_called()
        executor.express_opinion.assert_called()
        reflector.predict_consequence.assert_called()

    def test_parallel_consensus_all_fail_degrades(self):
        """并行投票全部失败时降级到串行"""
        loop, strategist, executor, reflector, engine = _build_agent_loop()

        # 串行 mock（降级后使用）
        strategist.express_opinion = Mock(return_value=_make_strategist_dict())
        executor.express_opinion = Mock(
            return_value=_make_opinion("executor", OpinionType.AGREE)
        )
        reflector.predict_consequence = Mock(
            return_value=_make_opinion("reflector", OpinionType.AGREE)
        )

        # 让 collect_opinions_async 抛异常触发降级
        engine.collect_opinions_async = AsyncMock(
            side_effect=RuntimeError("all failed")
        )

        context = {"user_input": "test", "retry_count": 0}
        step = Step(id="s1", skill_id="search", description="search")

        decision = _run_async(loop._parallel_consensus(context, "execute_step", step))

        self.assertIsInstance(decision, Decision)
        # 串行降级后三脑 AGREE → approved
        self.assertTrue(decision.approved)
        # 验证串行方法被调用
        strategist.express_opinion.assert_called_once()
        executor.express_opinion.assert_called_once()
        reflector.predict_consequence.assert_called_once()

    def test_serial_consensus_fallback(self):
        """串行降级路径正常"""
        loop, strategist, executor, reflector, engine = _build_agent_loop()

        strategist.express_opinion = Mock(return_value=_make_strategist_dict())
        executor.express_opinion = Mock(
            return_value=_make_opinion("executor", OpinionType.AGREE)
        )
        reflector.predict_consequence = Mock(
            return_value=_make_opinion("reflector", OpinionType.AGREE)
        )

        context = {"user_input": "test", "retry_count": 0}
        step = Step(id="s1", skill_id="search", description="search")

        decision = _run_async(
            loop._serial_consensus_fallback(context, "execute_step", step)
        )

        self.assertIsInstance(decision, Decision)
        self.assertTrue(decision.approved)
        self.assertEqual(decision.decision_type, DecisionType.UNANIMOUS)
        strategist.express_opinion.assert_called_once()
        executor.express_opinion.assert_called_once()
        reflector.predict_consequence.assert_called_once()

    def test_serial_consensus_fallback_timeout_fail_close(self):
        """串行降级超时时必须返回 ESCALATED 且 approved=False [P1-1]"""
        loop, strategist, executor, reflector, engine = _build_agent_loop()

        # 模拟策略脑超时，触发 fail-close 路径
        strategist.express_opinion = Mock(
            side_effect=asyncio.TimeoutError("strategist timeout")
        )
        executor.express_opinion = Mock(
            return_value=_make_opinion("executor", OpinionType.AGREE)
        )
        reflector.predict_consequence = Mock(
            return_value=_make_opinion("reflector", OpinionType.AGREE)
        )

        context = {"user_input": "test", "retry_count": 0}
        step = Step(id="s1", skill_id="search", description="search")

        decision = _run_async(
            loop._serial_consensus_fallback(context, "execute_step", step)
        )

        self.assertIsInstance(decision, Decision)
        self.assertFalse(decision.approved)
        self.assertEqual(decision.decision_type, DecisionType.ESCALATED)
        self.assertIn("serial_consensus_timeout", decision.reasoning)
        self.assertEqual(decision.confidence, 0.0)

    def test_parallel_disabled_uses_serial(self):
        """PARALLEL_VOTE_ENABLED=false 时使用串行"""
        loop, strategist, executor, reflector, engine = _build_agent_loop()

        strategist.express_opinion = Mock(return_value=_make_strategist_dict())
        executor.express_opinion = Mock(
            return_value=_make_opinion("executor", OpinionType.AGREE)
        )
        reflector.predict_consequence = Mock(
            return_value=_make_opinion("reflector", OpinionType.AGREE)
        )

        context = {"user_input": "test", "retry_count": 0}
        step = Step(id="s1", skill_id="search", description="search")

        with patch("opc_manager.task_orchestrator.PARALLEL_VOTE_ENABLED", False):
            decision = _run_async(
                loop._parallel_consensus(context, "execute_step", step)
            )

        self.assertIsInstance(decision, Decision)
        self.assertTrue(decision.approved)
        # 串行方法被调用，异步方法不应被调用
        strategist.express_opinion.assert_called_once()
        executor.express_opinion.assert_called_once()


class TestCriticalDecisionPoint(unittest.TestCase):
    """关键决策点识别测试 [S2-T4]"""

    def test_is_critical_email_skill(self):
        """email 技能是关键决策点"""
        loop, _, _, _, _ = _build_agent_loop()
        step = Step(id="s1", skill_id="email", description="send email")
        context = {"user_input": "test"}

        self.assertTrue(loop._is_critical_decision_point(context, step))

    def test_is_critical_report_skill(self):
        """report 技能是关键决策点"""
        loop, _, _, _, _ = _build_agent_loop()
        step = Step(id="s1", skill_id="report", description="generate report")
        context = {"user_input": "test"}

        self.assertTrue(loop._is_critical_decision_point(context, step))

    def test_is_critical_finance_skill(self):
        """finance 技能是关键决策点 [P1-2]"""
        loop, _, _, _, _ = _build_agent_loop()
        step = Step(id="s1", skill_id="finance", description="record expense")
        context = {"user_input": "test"}

        self.assertTrue(loop._is_critical_decision_point(context, step))

    def test_is_critical_send_action(self):
        """send 动作是关键决策点（通过 action 属性）"""
        loop, _, _, _, _ = _build_agent_loop()
        step = Mock()
        step.skill_id = "some_skill"
        step.action = "send"
        context = {"user_input": "test"}

        self.assertTrue(loop._is_critical_decision_point(context, step))

    def test_is_critical_execute_operation_action(self):
        """execute_operation 动作是关键决策点"""
        loop, _, _, _, _ = _build_agent_loop()
        step = Mock()
        step.skill_id = "some_skill"
        step.action = "execute_operation"
        context = {"user_input": "test"}

        self.assertTrue(loop._is_critical_decision_point(context, step))

    def test_is_not_critical_query(self):
        """查询不是关键决策点"""
        loop, _, _, _, _ = _build_agent_loop()
        step = Step(id="s1", skill_id="search", description="search")
        context = {"user_input": "test"}

        self.assertFalse(loop._is_critical_decision_point(context, step))

    def test_is_not_critical_no_step(self):
        """无步骤时不是关键决策点"""
        loop, _, _, _, _ = _build_agent_loop()
        context = {"user_input": "test"}

        self.assertFalse(loop._is_critical_decision_point(context, None))

    def test_is_not_critical_empty_skill(self):
        """空 skill_id 不是关键决策点"""
        loop, _, _, _, _ = _build_agent_loop()
        step = Step(id="s1", skill_id="", description="empty")
        context = {"user_input": "test"}

        self.assertFalse(loop._is_critical_decision_point(context, step))


class TestCollectOpinionsAsync(unittest.TestCase):
    """异步共识收集测试"""

    def test_collect_opinions_async_normal(self):
        """异步收集正常：三个 coroutine 返回 Opinion → Decision 正确"""
        with (
            patch.object(ConsensusEngine, "_load_decision_log_from_db"),
            patch.object(ConsensusEngine, "_log_decision"),
        ):
            engine = ConsensusEngine()

        async def strategist_coro():
            return _make_opinion("strategist", OpinionType.AGREE)

        async def executor_coro():
            return _make_opinion("executor", OpinionType.AGREE)

        async def reflector_coro():
            return _make_opinion("reflector", OpinionType.AGREE)

        decision = _run_async(
            engine.collect_opinions_async(
                strategist_coro(), executor_coro(), reflector_coro()
            )
        )

        self.assertIsInstance(decision, Decision)
        self.assertTrue(decision.approved)
        self.assertEqual(decision.decision_type, DecisionType.UNANIMOUS)

    def test_collect_opinions_async_with_exception(self):
        """异步收集某脑异常 → 该脑返回 ABSTAIN"""
        with (
            patch.object(ConsensusEngine, "_load_decision_log_from_db"),
            patch.object(ConsensusEngine, "_log_decision"),
        ):
            engine = ConsensusEngine()

        async def strategist_coro():
            return _make_opinion("strategist", OpinionType.AGREE)

        async def executor_coro():
            raise RuntimeError("executor LLM failed")

        async def reflector_coro():
            return _make_opinion("reflector", OpinionType.AGREE)

        decision = _run_async(
            engine.collect_opinions_async(
                strategist_coro(), executor_coro(), reflector_coro()
            )
        )

        self.assertIsInstance(decision, Decision)
        # 2 AGREE + 1 ABSTAIN → 多数同意
        self.assertTrue(decision.approved)

    def test_collect_opinions_async_all_exception(self):
        """异步收集全部异常 → 全部 ABSTAIN → 不通过"""
        with (
            patch.object(ConsensusEngine, "_load_decision_log_from_db"),
            patch.object(ConsensusEngine, "_log_decision"),
        ):
            engine = ConsensusEngine()

        async def failing_coro():
            raise RuntimeError("brain failed")

        decision = _run_async(
            engine.collect_opinions_async(
                failing_coro(), failing_coro(), failing_coro()
            )
        )

        self.assertIsInstance(decision, Decision)
        # 全部 ABSTAIN → 无 AGREE → ESCALATED
        self.assertFalse(decision.approved)

    def test_collect_opinions_async_veto(self):
        """异步收集含否决 → 不通过"""
        with (
            patch.object(ConsensusEngine, "_load_decision_log_from_db"),
            patch.object(ConsensusEngine, "_log_decision"),
        ):
            engine = ConsensusEngine()

        async def strategist_coro():
            return _make_opinion("strategist", OpinionType.AGREE)

        async def executor_coro():
            return _make_opinion("executor", OpinionType.DISAGREE, confidence=0.9)

        async def reflector_coro():
            return _make_opinion("reflector", OpinionType.AGREE)

        decision = _run_async(
            engine.collect_opinions_async(
                strategist_coro(), executor_coro(), reflector_coro()
            )
        )

        self.assertFalse(decision.approved)
        self.assertEqual(decision.decision_type, DecisionType.VETOED)


class TestParallelVsSerialLatency(unittest.TestCase):
    """延迟对比测试 [S2-T9 预览]"""

    def test_parallel_faster_than_serial(self):
        """并行延迟 < 串行延迟 × 0.6"""
        loop, strategist, executor, reflector, engine = _build_agent_loop()

        DELAY = 0.3

        # 串行 mock（sync，用 time.sleep）
        def slow_strategist(ctx):
            time.sleep(DELAY)
            return _make_strategist_dict()

        def slow_executor_sync(ctx, dp):
            time.sleep(DELAY)
            return _make_opinion("executor")

        def slow_reflector_sync(ctx, pa):
            time.sleep(DELAY)
            return _make_opinion("reflector")

        strategist.express_opinion = Mock(side_effect=slow_strategist)
        executor.express_opinion = Mock(side_effect=slow_executor_sync)
        reflector.predict_consequence = Mock(side_effect=slow_reflector_sync)

        # 异步 mock（用 asyncio.sleep）
        async def slow_executor_async(ctx, dp):
            await asyncio.sleep(DELAY)
            return _make_opinion("executor")

        async def slow_reflector_async(ctx, pa):
            await asyncio.sleep(DELAY)
            return _make_opinion("reflector")

        executor.express_opinion_async = AsyncMock(side_effect=slow_executor_async)
        reflector.predict_consequence_async = AsyncMock(
            side_effect=slow_reflector_async
        )

        context = {"user_input": "test", "retry_count": 0}
        step = Step(id="s1", skill_id="search", description="search")

        # 测量串行时间
        serial_start = time.time()
        _run_async(loop._serial_consensus_fallback(context, "test", step))
        serial_time = time.time() - serial_start

        # 测量并行时间
        parallel_start = time.time()
        _run_async(loop._parallel_consensus(context, "test", step))
        parallel_time = time.time() - parallel_start

        self.assertLess(
            parallel_time,
            serial_time * 0.6,
            f"并行({parallel_time:.2f}s)应快于串行({serial_time:.2f}s)的60%",
        )


class TestDictToOpinion(unittest.TestCase):
    """_dict_to_opinion 辅助方法测试"""

    def test_dict_to_opinion_agree(self):
        """AGREE 字典转 Opinion"""
        loop, _, _, _, _ = _build_agent_loop()
        result = _make_strategist_dict("AGREE", 0.9)

        opinion = loop._dict_to_opinion(result, "strategist")

        self.assertEqual(opinion.brain_type, "strategist")
        self.assertEqual(opinion.opinion_type, OpinionType.AGREE)
        self.assertAlmostEqual(opinion.confidence, 0.9)

    def test_dict_to_opinion_invalid_type(self):
        """无效 opinion_type 转 ABSTAIN"""
        loop, _, _, _, _ = _build_agent_loop()
        result = {"opinion_type": "INVALID", "reasoning": "test", "confidence": 0.5}

        opinion = loop._dict_to_opinion(result, "strategist")

        self.assertEqual(opinion.opinion_type, OpinionType.ABSTAIN)

    def test_dict_to_opinion_non_dict(self):
        """非 dict 输入转 ABSTAIN"""
        loop, _, _, _, _ = _build_agent_loop()

        opinion = loop._dict_to_opinion("not a dict", "strategist")

        self.assertEqual(opinion.opinion_type, OpinionType.ABSTAIN)
        self.assertEqual(opinion.confidence, 0.0)

    def test_dict_to_opinion_lowercase_type(self):
        """小写 opinion_type 正确解析"""
        loop, _, _, _, _ = _build_agent_loop()
        result = {"opinion_type": "agree", "reasoning": "ok", "confidence": 0.7}

        opinion = loop._dict_to_opinion(result, "strategist")

        self.assertEqual(opinion.opinion_type, OpinionType.AGREE)


class TestExtractPlannedAction(unittest.TestCase):
    """_extract_planned_action 辅助方法测试"""

    def test_extract_with_step(self):
        """传入 step 时正确提取"""
        loop, _, _, _, _ = _build_agent_loop()
        step = Step(
            id="s1",
            skill_id="email",
            description="send",
            parameters={"to": "user@example.com"},
        )

        action = loop._extract_planned_action({}, step)

        self.assertEqual(action["skill_id"], "email")
        self.assertEqual(action["parameters"], {"to": "user@example.com"})

    def test_extract_without_step_returns_empty(self):
        """无 step 且无法从 context 查找时返回空"""
        loop, _, _, _, _ = _build_agent_loop()

        action = loop._extract_planned_action({})

        self.assertEqual(action["skill_id"], "")
        self.assertEqual(action["action"], "")


if __name__ == "__main__":
    unittest.main()
