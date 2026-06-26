"""Unit tests for opc_manager brain modules:
   strategist_brain, executor_brain, reflector_brain

Covers: main methods, input validation, error handling, return types, edge cases.
All LLM calls and external dependencies are mocked.
"""

import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

from opc_manager.strategist_brain import (
    StrategistBrain,
    Intent,
    ExecutionPlan,
    ConstraintType,
)
from opc_manager.executor_brain import (
    ExecutorBrain,
    ExecutionResultType,
    ExecutionStatusType,
)
from opc_manager.reflector_brain import (
    ReflectorBrain,
    Evaluation,
    EvaluationResult,
    NextAction,
    NextActionType,
    CorrectionStrategy,
    MAX_RETRY_COUNT,
    MAX_CORRECTION_ATTEMPTS,
)
from opc_manager.intent_types import IntentType


def _run_async(coro):
    """Helper to run async coroutines in tests.

    Uses asyncio.run() instead of deprecated get_event_loop() to avoid
    event loop corruption when other tests (e.g. test_llm_concurrency)
    call asyncio.run() which creates/destroys loops.
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


# ===================================================================
# StrategistBrain tests
# ===================================================================
class TestStrategistBrainUnderstandIntent(unittest.TestCase):
    """Tests for StrategistBrain.understand_intent()"""

    def setUp(self):
        self.brain = StrategistBrain(llm_service=None)

    def test_detects_analysis_intent(self):
        intent = self.brain.understand_intent("帮我分析市场趋势")
        self.assertEqual(intent.type, IntentType.ANALYSIS)

    def test_detects_search_intent(self):
        intent = self.brain.understand_intent("搜索最新的AI论文")
        self.assertEqual(intent.type, IntentType.SEARCH)

    def test_detects_combined_intent(self):
        intent = self.brain.understand_intent("分析市场然后写报告")
        self.assertEqual(intent.type, IntentType.COMBINED)

    @patch.object(StrategistBrain, "_fallback_to_external", return_value=None)
    def test_unknown_intent_for_unrecognized_input(self, mock_fallback):
        intent = self.brain.understand_intent("随便说说")
        self.assertEqual(intent.type, IntentType.UNKNOWN)

    @patch.object(StrategistBrain, "_fallback_to_external", return_value=None)
    def test_empty_input_gives_unknown(self, mock_fallback):
        intent = self.brain.understand_intent("")
        self.assertEqual(intent.type, IntentType.UNKNOWN)

    def test_intent_has_goal(self):
        intent = self.brain.understand_intent("帮我分析数据")
        self.assertIn("分析", intent.goal)

    def test_intent_confidence_range(self):
        intent = self.brain.understand_intent("分析市场趋势")
        self.assertGreaterEqual(intent.confidence, 0.0)
        self.assertLessEqual(intent.confidence, 1.0)

    @patch("opc_manager.strategist_brain.call_llm_service", return_value=None)
    def test_llm_failure_falls_back_to_keywords(self, mock_llm):
        mock_svc = MagicMock()
        mock_svc.complete.return_value = None
        brain = StrategistBrain(llm_service=mock_svc)
        intent = brain.understand_intent("分析市场趋势")
        self.assertEqual(intent.type, IntentType.ANALYSIS)

    @patch("opc_manager.strategist_brain.call_llm_service")
    def test_llm_returns_valid_intent(self, mock_llm):
        mock_llm.return_value = '{"goal": "分析数据", "intent_type": "analysis", "confidence": 0.9, "sub_intents": [], "constraints": []}'
        mock_svc = MagicMock()
        brain = StrategistBrain(llm_service=mock_svc)
        intent = brain.understand_intent("分析数据")
        self.assertEqual(intent.type, IntentType.ANALYSIS)
        self.assertAlmostEqual(intent.confidence, 0.9)

    @patch("opc_manager.strategist_brain.call_llm_service")
    def test_llm_malformed_response_falls_back(self, mock_llm):
        mock_llm.return_value = "NOT JSON AT ALL"
        mock_svc = MagicMock()
        brain = StrategistBrain(llm_service=mock_svc)
        intent = brain.understand_intent("分析市场趋势")
        # Should fall back to keyword matching
        self.assertEqual(intent.type, IntentType.ANALYSIS)

    def test_very_long_input(self):
        long_input = "分析" + "数据" * 500
        intent = self.brain.understand_intent(long_input)
        self.assertEqual(intent.type, IntentType.ANALYSIS)

    @patch.object(StrategistBrain, "_fallback_to_external", return_value=None)
    def test_notification_intent(self, mock_fallback):
        intent = self.brain.understand_intent("发送通知给团队")
        self.assertEqual(intent.type, IntentType.NOTIFICATION)


class TestStrategistBrainPlan(unittest.TestCase):
    """Tests for StrategistBrain.plan()"""

    def setUp(self):
        self.brain = StrategistBrain(llm_service=None)

    def test_plan_returns_execution_plan(self):
        intent = Intent(goal="分析数据", type=IntentType.ANALYSIS)
        plan = self.brain.plan(intent)
        self.assertIsInstance(plan, ExecutionPlan)

    def test_plan_has_steps(self):
        intent = Intent(goal="分析数据", type=IntentType.ANALYSIS)
        plan = self.brain.plan(intent)
        self.assertGreater(len(plan.steps), 0)

    def test_plan_has_intent_analysis_step(self):
        intent = Intent(goal="分析数据", type=IntentType.ANALYSIS)
        plan = self.brain.plan(intent)
        first_skill = plan.steps[0].skill_id
        self.assertEqual(first_skill, "intent_analysis")

    def test_plan_ends_with_output_result(self):
        intent = Intent(goal="搜索信息", type=IntentType.SEARCH)
        plan = self.brain.plan(intent)
        self.assertEqual(plan.steps[-1].skill_id, "output_result")

    def test_plan_estimated_time_positive(self):
        intent = Intent(goal="分析数据", type=IntentType.ANALYSIS)
        plan = self.brain.plan(intent)
        self.assertGreater(plan.estimated_time, 0)

    def test_plan_combined_intent_has_more_steps(self):
        sub = [Intent(goal="分析", type=IntentType.ANALYSIS)]
        intent = Intent(
            goal="分析然后写报告", type=IntentType.COMBINED, sub_intents=sub
        )
        plan = self.brain.plan(intent)
        self.assertGreater(len(plan.steps), 2)

    @patch("opc_manager.strategist_brain.call_llm_service", return_value=None)
    def test_plan_llm_failure_falls_back(self, mock_llm):
        mock_svc = MagicMock()
        brain = StrategistBrain(llm_service=mock_svc)
        intent = Intent(goal="分析数据", type=IntentType.ANALYSIS)
        plan = brain.plan(intent)
        self.assertIsInstance(plan, ExecutionPlan)
        self.assertGreater(len(plan.steps), 0)

    def test_plan_search_intent_has_search_step(self):
        intent = Intent(goal="搜索信息", type=IntentType.SEARCH)
        plan = self.brain.plan(intent)
        skill_ids = [s.skill_id for s in plan.steps]
        self.assertIn("search", skill_ids)


class TestStrategistBrainHelpers(unittest.TestCase):
    """Tests for internal helper methods."""

    def setUp(self):
        self.brain = StrategistBrain(llm_service=None)

    def test_extract_goal_removes_prefix(self):
        goal = self.brain._extract_goal("帮我分析数据", IntentType.ANALYSIS)
        self.assertNotIn("帮我", goal)

    def test_extract_goal_removes_suffix_particles(self):
        goal = self.brain._extract_goal("分析数据吧", IntentType.ANALYSIS)
        self.assertNotIn("吧", goal)

    def test_calculate_confidence_unknown_low(self):
        conf = self.brain._calculate_confidence("随便说说", IntentType.UNKNOWN)
        self.assertAlmostEqual(conf, 0.3)

    def test_calculate_confidence_single_keyword(self):
        conf = self.brain._calculate_confidence("分析数据", IntentType.ANALYSIS)
        self.assertAlmostEqual(conf, 0.7)

    def test_extract_constraints_time(self):
        constraints = self.brain._extract_constraints("今天完成分析")
        types = [c.type for c in constraints]
        self.assertIn(ConstraintType.TIME, types)

    def test_extract_constraints_count(self):
        constraints = self.brain._extract_constraints("写3份报告")
        count_constraints = [c for c in constraints if c.type == ConstraintType.COUNT]
        self.assertTrue(len(count_constraints) > 0)

    def test_to_dict(self):
        d = self.brain.to_dict()
        self.assertEqual(d["type"], "strategist_brain")

    def test_express_opinion_agree(self):
        intent = Intent(goal="test", type=IntentType.ANALYSIS, confidence=0.8)
        opinion = self.brain.express_opinion({"intent": intent})
        self.assertEqual(opinion["opinion_type"], "AGREE")

    def test_express_opinion_conditional(self):
        intent = Intent(goal="test", type=IntentType.UNKNOWN, confidence=0.3)
        opinion = self.brain.express_opinion({"intent": intent})
        self.assertEqual(opinion["opinion_type"], "CONDITIONAL")

    def test_express_opinion_no_intent(self):
        opinion = self.brain.express_opinion({})
        self.assertEqual(opinion["opinion_type"], "CONDITIONAL")


# ===================================================================
# ExecutorBrain tests
# ===================================================================
class TestExecutorBrainExecuteStep(unittest.TestCase):
    """Tests for ExecutorBrain.execute_step()"""

    def _make_brain(self, skill_registry=None, task_engine=None):
        """Create ExecutorBrain with mocked task_engine to avoid real execution."""
        if task_engine is None:
            task_engine = MagicMock()
        return ExecutorBrain(skill_registry=skill_registry, task_engine=task_engine)

    def test_execute_step_no_registry_with_mocked_engine(self):
        """When no skill_registry, task_engine is used."""
        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.content = "result"
        mock_result.sources = []
        mock_result.task_type = None
        mock_result.deliverable_format = None
        mock_result.error = None
        mock_result.execution_time_ms = 100
        mock_engine.execute.return_value = mock_result
        brain = self._make_brain(task_engine=mock_engine)

        result = _run_async(brain.execute_step("s1", "search", {"query": "test"}))
        self.assertTrue(result.success)

    def test_execute_step_with_skill_registry(self):
        mock_registry = MagicMock()
        mock_skill = MagicMock()
        mock_skill.enabled = True
        mock_skill.execute = MagicMock(
            return_value={"success": True, "data": {"k": "v"}}
        )
        mock_registry.get_skill.return_value = mock_skill
        brain = self._make_brain(skill_registry=mock_registry)

        result = _run_async(brain.execute_step("s1", "search", {"query": "test"}))
        self.assertTrue(result.success)
        self.assertEqual(result.result_type, ExecutionResultType.SUCCESS)

    def test_execute_step_skill_disabled(self):
        mock_registry = MagicMock()
        mock_skill = MagicMock()
        mock_skill.enabled = False
        mock_registry.get_skill.return_value = mock_skill
        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.content = ""
        mock_result.sources = []
        mock_result.task_type = None
        mock_result.deliverable_format = None
        mock_result.error = "disabled"
        mock_result.execution_time_ms = 0
        mock_engine.execute.return_value = mock_result
        brain = self._make_brain(skill_registry=mock_registry, task_engine=mock_engine)

        result = _run_async(brain.execute_step("s1", "search", {"query": "test"}))
        self.assertFalse(result.success)

    def test_execute_step_skill_exception(self):
        mock_registry = MagicMock()
        mock_skill = MagicMock()
        mock_skill.enabled = True
        mock_skill.execute = MagicMock(side_effect=RuntimeError("boom"))
        mock_registry.get_skill.return_value = mock_skill
        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.content = ""
        mock_result.sources = []
        mock_result.task_type = None
        mock_result.deliverable_format = None
        mock_result.error = "error"
        mock_result.execution_time_ms = 0
        mock_engine.execute.return_value = mock_result
        brain = self._make_brain(skill_registry=mock_registry, task_engine=mock_engine)

        result = _run_async(brain.execute_step("s1", "search", {"query": "test"}))
        self.assertFalse(result.success)
        self.assertEqual(result.result_type, ExecutionResultType.FAILURE)

    def test_execute_step_skill_returns_none_wraps_as_success(self):
        """When skill returns None, it gets wrapped as ExecutionResult(success=True, data={"result": None}).
        This is the actual behavior of _execute_skill — non-dict results are wrapped with success=True.
        """
        mock_registry = MagicMock()
        mock_skill = MagicMock()
        mock_skill.enabled = True
        mock_skill.execute = MagicMock(return_value=None)
        mock_registry.get_skill.return_value = mock_skill
        mock_engine = MagicMock()
        mock_te_result = MagicMock()
        mock_te_result.success = False
        mock_te_result.content = ""
        mock_te_result.sources = []
        mock_te_result.task_type = None
        mock_te_result.deliverable_format = None
        mock_te_result.error = "no result"
        mock_te_result.execution_time_ms = 0
        mock_engine.execute.return_value = mock_te_result
        brain = ExecutorBrain(skill_registry=mock_registry, task_engine=mock_engine)

        result = _run_async(brain.execute_step("s1", "search", {"query": "test"}))
        # Non-dict return from skill is wrapped with success=True
        self.assertTrue(result.success)
        self.assertEqual(result.data.get("result"), None)

    def test_execute_step_async_skill(self):
        mock_registry = MagicMock()
        mock_skill = MagicMock()
        mock_skill.enabled = True
        mock_skill.execute = AsyncMock(return_value={"success": True, "data": {}})
        mock_registry.get_skill.return_value = mock_skill
        brain = self._make_brain(skill_registry=mock_registry)

        result = _run_async(brain.execute_step("s1", "search", {"query": "test"}))
        self.assertTrue(result.success)

    def test_execute_step_no_skill_no_engine_no_query(self):
        """When no skill, no engine, and no query input, should fail."""
        mock_registry = MagicMock()
        mock_registry.get_skill.return_value = None
        mock_engine = MagicMock()
        brain = self._make_brain(skill_registry=mock_registry, task_engine=mock_engine)

        result = _run_async(brain.execute_step("s1", "unknown_skill", {}))
        self.assertFalse(result.success)


class TestExecutorBrainExecutePlan(unittest.TestCase):
    """Tests for ExecutorBrain.execute_plan()"""

    def _make_brain(self, skill_registry=None, task_engine=None):
        if task_engine is None:
            task_engine = MagicMock()
        return ExecutorBrain(skill_registry=skill_registry, task_engine=task_engine)

    def test_execute_plan_all_steps_succeed(self):
        mock_registry = MagicMock()
        mock_skill = MagicMock()
        mock_skill.enabled = True
        mock_skill.execute = MagicMock(return_value={"success": True, "data": {}})
        mock_registry.get_skill.return_value = mock_skill
        brain = self._make_brain(skill_registry=mock_registry)

        steps = [
            {"id": "s1", "skill_id": "search", "parameters": {"query": "test"}},
            {"id": "s2", "skill_id": "analysis", "parameters": {"goal": "test"}},
        ]
        result = _run_async(brain.execute_plan("plan_1", steps))
        self.assertTrue(result.success)
        self.assertIn("task_id", result.data)

    def test_execute_plan_step_failure_stops(self):
        mock_registry = MagicMock()
        mock_skill = MagicMock()
        mock_skill.enabled = True
        mock_skill.execute = MagicMock(return_value={"success": False, "error": "bad"})
        mock_registry.get_skill.return_value = mock_skill
        # Use a mocked task_engine that returns failure (so fallback also fails)
        mock_engine = MagicMock()
        mock_te_result = MagicMock()
        mock_te_result.success = False
        mock_te_result.content = ""
        mock_te_result.sources = []
        mock_te_result.task_type = None
        mock_te_result.deliverable_format = None
        mock_te_result.error = "bad"
        mock_te_result.execution_time_ms = 0
        mock_engine.execute.return_value = mock_te_result
        brain = ExecutorBrain(skill_registry=mock_registry, task_engine=mock_engine)

        steps = [
            {"id": "s1", "skill_id": "search", "parameters": {"query": "test"}},
            {"id": "s2", "skill_id": "analysis", "parameters": {"goal": "test"}},
        ]
        result = _run_async(brain.execute_plan("plan_1", steps))
        self.assertFalse(result.success)

    def test_execute_plan_empty_steps(self):
        brain = self._make_brain()
        result = _run_async(brain.execute_plan("plan_1", []))
        self.assertTrue(result.success)


class TestExecutorBrainStatus(unittest.TestCase):
    """Tests for status tracking and cancellation."""

    def test_get_status_nonexistent(self):
        brain = ExecutorBrain(task_engine=MagicMock())
        self.assertIsNone(brain.get_execution_status("nonexistent"))

    def test_cancel_nonexistent_task(self):
        brain = ExecutorBrain(task_engine=MagicMock())
        result = _run_async(brain.cancel_execution("nonexistent"))
        self.assertFalse(result)

    def test_to_dict(self):
        brain = ExecutorBrain(task_engine=MagicMock())
        d = brain.to_dict()
        self.assertEqual(d["type"], "executor_brain")

    def test_cancel_running_task(self):
        brain = ExecutorBrain(task_engine=MagicMock())
        from opc_manager.executor_brain import ExecutionStatus

        brain.task_statuses["task_1"] = ExecutionStatus(
            task_id="task_1",
            status=ExecutionStatusType.RUNNING,
            progress=0.5,
        )
        result = _run_async(brain.cancel_execution("task_1"))
        self.assertTrue(result)
        self.assertEqual(
            brain.task_statuses["task_1"].status, ExecutionStatusType.CANCELLED
        )


# ===================================================================
# ReflectorBrain tests
# ===================================================================
class TestReflectorBrainEvaluate(unittest.TestCase):
    """Tests for ReflectorBrain.evaluate_result()"""

    def setUp(self):
        self.brain = ReflectorBrain(llm_service=None)

    def test_evaluate_success_result(self):
        actual = {"success": True, "data": {"content": "good result"}}
        expected = {"goal": "分析数据"}
        evaluation = self.brain.evaluate_result(actual, expected)
        self.assertIsInstance(evaluation, Evaluation)
        self.assertGreater(evaluation.quality_score, 0.0)

    def test_evaluate_failure_result(self):
        actual = {"success": False, "error": "something went wrong"}
        expected = {"goal": "分析数据"}
        evaluation = self.brain.evaluate_result(actual, expected)
        self.assertIn(
            evaluation.result,
            [EvaluationResult.POOR, EvaluationResult.FAILURE],
        )

    def test_evaluate_empty_data(self):
        actual = {"success": True, "data": {}}
        expected = {"goal": "test"}
        evaluation = self.brain.evaluate_result(actual, expected)
        self.assertIsInstance(evaluation, Evaluation)

    def test_evaluate_with_relevant_data(self):
        actual = {"success": True, "data": {"content": "市场分析结果"}}
        expected = {"goal": "市场分析"}
        evaluation = self.brain.evaluate_result(actual, expected)
        self.assertGreater(evaluation.quality_score, 0.3)

    def test_evaluate_non_dict_actual_raises_attribute_error(self):
        """When actual is not a dict, evaluate_result raises AttributeError
        (source code does not guard against non-dict at top level)."""
        actual = "not a dict"
        expected = {"goal": "test"}
        with self.assertRaises(AttributeError):
            self.brain.evaluate_result(actual, expected)

    def test_evaluate_key_findings_on_success(self):
        actual = {"success": True, "data": {"content": "result"}}
        expected = {"goal": "test"}
        evaluation = self.brain.evaluate_result(actual, expected)
        self.assertTrue(any("成功" in f for f in evaluation.key_findings))

    def test_evaluate_key_findings_on_failure(self):
        actual = {"success": False, "error": "timeout"}
        expected = {"goal": "test"}
        evaluation = self.brain.evaluate_result(actual, expected)
        self.assertTrue(any("失败" in f for f in evaluation.key_findings))

    @patch("opc_manager.reflector_brain.call_llm_service", return_value=None)
    def test_llm_failure_falls_back_to_rules(self, mock_llm):
        mock_svc = MagicMock()
        brain = ReflectorBrain(llm_service=mock_svc)
        actual = {"success": True, "data": {"content": "ok"}}
        evaluation = brain.evaluate_result(actual, {"goal": "test"})
        self.assertIsInstance(evaluation, Evaluation)

    @patch("opc_manager.reflector_brain.call_llm_service")
    def test_llm_returns_valid_evaluation(self, mock_llm):
        mock_llm.return_value = '{"quality_score": 0.85, "result_level": "GOOD", "deviation_analysis": "OK", "key_findings": ["fine"]}'
        mock_svc = MagicMock()
        brain = ReflectorBrain(llm_service=mock_svc)
        actual = {"success": True, "data": {"content": "good"}}
        evaluation = brain.evaluate_result(actual, {"goal": "test"})
        self.assertEqual(evaluation.result, EvaluationResult.GOOD)

    @patch("opc_manager.reflector_brain.call_llm_service")
    def test_llm_malformed_response_falls_back(self, mock_llm):
        mock_llm.return_value = "NOT JSON"
        mock_svc = MagicMock()
        brain = ReflectorBrain(llm_service=mock_svc)
        actual = {"success": True, "data": {"content": "ok"}}
        evaluation = brain.evaluate_result(actual, {"goal": "test"})
        self.assertIsInstance(evaluation, Evaluation)

    def test_evaluate_with_execution_time(self):
        actual = {"success": True, "data": {"content": "result"}, "execution_time": 5.0}
        expected = {"goal": "test"}
        evaluation = self.brain.evaluate_result(actual, expected)
        self.assertIsInstance(evaluation, Evaluation)

    def test_evaluate_all_steps_completed(self):
        actual = {
            "success": True,
            "data": {
                "results": [{"success": True}, {"success": True}],
            },
        }
        expected = {"goal": "test"}
        evaluation = self.brain.evaluate_result(actual, expected)
        self.assertGreater(evaluation.quality_score, 0.5)


class TestReflectorBrainDecideNextAction(unittest.TestCase):
    """Tests for ReflectorBrain.decide_next_action()"""

    def setUp(self):
        self.brain = ReflectorBrain(llm_service=None)

    def test_excellent_result_continues(self):
        evaluation = Evaluation(
            result=EvaluationResult.EXCELLENT,
            quality_score=0.95,
            deviation_analysis="",
        )
        action = self.brain.decide_next_action(evaluation)
        self.assertEqual(action.action_type, NextActionType.CONTINUE)

    def test_good_result_continues(self):
        evaluation = Evaluation(
            result=EvaluationResult.GOOD,
            quality_score=0.8,
            deviation_analysis="",
        )
        action = self.brain.decide_next_action(evaluation)
        self.assertEqual(action.action_type, NextActionType.CONTINUE)

    def test_poor_result_retries(self):
        evaluation = Evaluation(
            result=EvaluationResult.POOR,
            quality_score=0.4,
            deviation_analysis="",
        )
        action = self.brain.decide_next_action(evaluation, plan={"retry_count": 0})
        self.assertEqual(action.action_type, NextActionType.RETRY)

    def test_poor_result_adjusts_after_max_retries(self):
        evaluation = Evaluation(
            result=EvaluationResult.POOR,
            quality_score=0.4,
            deviation_analysis="",
        )
        action = self.brain.decide_next_action(
            evaluation, plan={"retry_count": MAX_RETRY_COUNT}
        )
        self.assertEqual(action.action_type, NextActionType.ADJUST_STRATEGY)

    def test_failure_result_abandons_after_max_retries(self):
        evaluation = Evaluation(
            result=EvaluationResult.FAILURE,
            quality_score=0.1,
            deviation_analysis="",
        )
        action = self.brain.decide_next_action(
            evaluation, plan={"retry_count": MAX_RETRY_COUNT}
        )
        self.assertEqual(action.action_type, NextActionType.ABANDON)

    def test_failure_result_retries_when_under_limit(self):
        evaluation = Evaluation(
            result=EvaluationResult.FAILURE,
            quality_score=0.1,
            deviation_analysis="",
        )
        action = self.brain.decide_next_action(evaluation, plan={"retry_count": 0})
        self.assertEqual(action.action_type, NextActionType.RETRY)

    def test_acceptable_with_remaining_steps_continues(self):
        evaluation = Evaluation(
            result=EvaluationResult.ACCEPTABLE,
            quality_score=0.6,
            deviation_analysis="",
        )
        action = self.brain.decide_next_action(evaluation, plan={"steps": ["s1", "s2"]})
        self.assertEqual(action.action_type, NextActionType.CONTINUE)

    def test_acceptable_last_step_reviews(self):
        evaluation = Evaluation(
            result=EvaluationResult.ACCEPTABLE,
            quality_score=0.6,
            deviation_analysis="",
        )
        action = self.brain.decide_next_action(evaluation, plan={"steps": ["s1"]})
        self.assertEqual(action.action_type, NextActionType.REVIEW)

    def test_failure_no_plan_abandons(self):
        evaluation = Evaluation(
            result=EvaluationResult.FAILURE,
            quality_score=0.1,
            deviation_analysis="",
        )
        action = self.brain.decide_next_action(evaluation)
        self.assertEqual(action.action_type, NextActionType.ABANDON)


class TestReflectorBrainCorrection(unittest.TestCase):
    """Tests for suggest_correction_strategy and suggest_improvement."""

    def setUp(self):
        self.brain = ReflectorBrain(llm_service=None)

    def test_no_correction_above_threshold(self):
        evaluation = Evaluation(
            result=EvaluationResult.GOOD, quality_score=0.8, deviation_analysis=""
        )
        strategy = self.brain.suggest_correction_strategy(evaluation, [])
        self.assertIsNone(strategy)

    def test_retry_on_error(self):
        evaluation = Evaluation(
            result=EvaluationResult.POOR, quality_score=0.3, deviation_analysis=""
        )
        results = [{"success": False, "error": "fail"}]
        strategy = self.brain.suggest_correction_strategy(evaluation, results)
        self.assertEqual(strategy, CorrectionStrategy.RETRY)

    def test_search_and_retry_on_placeholder(self):
        evaluation = Evaluation(
            result=EvaluationResult.ACCEPTABLE,
            quality_score=0.5,
            deviation_analysis="",
        )
        results = [{"success": True, "data": {"content": "[待补充]的内容"}}]
        strategy = self.brain.suggest_correction_strategy(evaluation, results)
        self.assertEqual(strategy, CorrectionStrategy.SEARCH_AND_RETRY)

    def test_switch_skill_on_poor(self):
        evaluation = Evaluation(
            result=EvaluationResult.POOR, quality_score=0.4, deviation_analysis=""
        )
        results = [{"success": True, "data": {"content": "ok"}}]
        strategy = self.brain.suggest_correction_strategy(evaluation, results)
        self.assertEqual(strategy, CorrectionStrategy.SWITCH_SKILL)

    def test_no_correction_after_max_attempts(self):
        evaluation = Evaluation(
            result=EvaluationResult.POOR, quality_score=0.3, deviation_analysis=""
        )
        strategy = self.brain.suggest_correction_strategy(
            evaluation, [], correction_count=MAX_CORRECTION_ATTEMPTS
        )
        self.assertIsNone(strategy)

    def test_suggest_improvement_for_failure(self):
        evaluation = Evaluation(
            result=EvaluationResult.FAILURE, quality_score=0.1, deviation_analysis=""
        )
        suggestions = self.brain.suggest_improvement(
            evaluation, {"steps": [], "retry_count": 0}
        )
        self.assertGreater(len(suggestions), 0)

    def test_suggest_improvement_for_good_is_empty(self):
        evaluation = Evaluation(
            result=EvaluationResult.EXCELLENT, quality_score=0.95, deviation_analysis=""
        )
        suggestions = self.brain.suggest_improvement(
            evaluation, {"steps": [], "retry_count": 0}
        )
        self.assertEqual(len(suggestions), 0)

    def test_degrade_strategy(self):
        """When no error, no placeholder, and result is not POOR, should DEGRADE."""
        evaluation = Evaluation(
            result=EvaluationResult.ACCEPTABLE,
            quality_score=0.5,
            deviation_analysis="",
        )
        results = [{"success": True, "data": {"content": "some content"}}]
        strategy = self.brain.suggest_correction_strategy(evaluation, results)
        self.assertEqual(strategy, CorrectionStrategy.DEGRADE)


class TestReflectorBrainSerialization(unittest.TestCase):
    def test_to_dict(self):
        brain = ReflectorBrain()
        d = brain.to_dict()
        self.assertEqual(d["type"], "reflector_brain")

    def test_from_dict(self):
        brain = ReflectorBrain()
        data = {"evaluation_thresholds": {"EXCELLENT": 0.9, "GOOD": 0.7}}
        brain.from_dict(data)
        self.assertEqual(brain.evaluation_thresholds[EvaluationResult.EXCELLENT], 0.9)

    def test_express_opinion_agree(self):
        brain = ReflectorBrain()
        evaluation = Evaluation(
            result=EvaluationResult.GOOD, quality_score=0.8, deviation_analysis=""
        )
        action = NextAction(
            action_type=NextActionType.CONTINUE, reason="ok", confidence=0.8
        )
        opinion = brain.express_opinion(
            {"evaluation": evaluation, "next_action": action}
        )
        self.assertEqual(opinion["opinion_type"], "AGREE")

    def test_express_opinion_disagree(self):
        brain = ReflectorBrain()
        evaluation = Evaluation(
            result=EvaluationResult.POOR, quality_score=0.3, deviation_analysis=""
        )
        action = NextAction(
            action_type=NextActionType.ABANDON, reason="bad", confidence=0.3
        )
        opinion = brain.express_opinion(
            {"evaluation": evaluation, "next_action": action}
        )
        self.assertEqual(opinion["opinion_type"], "DISAGREE")

    def test_express_opinion_no_evaluation(self):
        brain = ReflectorBrain()
        opinion = brain.express_opinion({})
        self.assertEqual(opinion["brain_type"], "reflector")


if __name__ == "__main__":
    unittest.main()
