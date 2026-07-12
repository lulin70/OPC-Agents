"""Tests for opc_manager.correction_manager module — coverage improvement (P2-11)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from opc_manager.correction_manager import (
    CorrectionManager,
    SKILL_FALLBACK_MAP,
)
from opc_manager.reflector_models import CorrectionStrategy


class FakeStep:
    def __init__(
        self, step_id="s1", skill_id="email", parameters=None, description="Send email"
    ):
        self.id = step_id
        self.skill_id = skill_id
        self.parameters = parameters or {}
        self.description = description


class FakePlan:
    def __init__(self, steps=None):
        if steps is None:
            steps = [FakeStep()]
        self.steps = steps


class FakeIntent:
    def __init__(self, goal="Write Q2 report"):
        self.goal = goal


class FakeResult:
    def __init__(self, success=True, data=None, error=None, execution_time=0.5):
        self.success = success
        self.data = data if data is not None else {}
        self.error = error
        self.execution_time = execution_time


class FakeContext:
    def __init__(
        self, plan=None, execution_results=None, task_id="task-1", intent=None
    ):
        if plan is None:
            plan = FakePlan()
        self.plan = plan
        self.execution_results = (
            execution_results if execution_results is not None else []
        )
        self.task_id = task_id
        self.intent = intent


class FakeExecutorBrain:
    def __init__(self, result=None):
        self._result = result or FakeResult()
        self.execute_step = AsyncMock(return_value=self._result)


class FakeSkillRegistry:
    def __init__(self, search_result=None):
        self._search_result = search_result or {
            "success": True,
            "data": {"results": []},
        }
        self.execute_skill = AsyncMock(return_value=self._search_result)


class TestSkillFallbackMap:
    def test_known_skills_have_fallback(self):
        assert SKILL_FALLBACK_MAP["email"] == "send_notification"
        assert SKILL_FALLBACK_MAP["finance"] == "analysis"
        assert SKILL_FALLBACK_MAP["calendar"] == "task_manager"

    def test_all_frozen_skills_mapped(self):
        frozen_skills = {
            "social_publish",
            "proposal",
            "invoice",
            "competitor_watch",
            "pricing",
            "dashboard",
            "knowledge_mgmt",
        }
        for skill in frozen_skills:
            assert skill in SKILL_FALLBACK_MAP, f"Missing fallback for {skill}"


class TestApplyCorrection:
    @pytest.mark.asyncio
    async def test_empty_plan_returns_false(self):
        mgr = CorrectionManager()
        ctx = FakeContext(plan=FakePlan(steps=[]))
        result = await mgr.apply_correction(ctx, CorrectionStrategy.RETRY)
        assert result is False

    @pytest.mark.asyncio
    async def test_none_plan_returns_false(self):
        mgr = CorrectionManager()
        ctx = FakeContext()
        ctx.plan = None
        result = await mgr.apply_correction(ctx, CorrectionStrategy.RETRY)
        assert result is False

    @pytest.mark.asyncio
    async def test_unknown_strategy_returns_false(self):
        mgr = CorrectionManager()
        ctx = FakeContext()
        result = await mgr.apply_correction(ctx, MagicMock())
        assert result is False

    @pytest.mark.asyncio
    async def test_retry_strategy_dispatches(self):
        executor = FakeExecutorBrain(FakeResult(success=True))
        mgr = CorrectionManager(executor_brain=executor)
        ctx = FakeContext(execution_results=[{"step_id": "s1"}])
        result = await mgr.apply_correction(ctx, CorrectionStrategy.RETRY)
        assert result is True
        executor.execute_step.assert_called_once()


class TestCorrectRetry:
    @pytest.mark.asyncio
    async def test_retry_success(self):
        executor = FakeExecutorBrain(FakeResult(success=True))
        mgr = CorrectionManager(executor_brain=executor)
        ctx = FakeContext(execution_results=[{"step_id": "s1"}])
        result = await mgr.correct_retry(ctx)
        assert result is True
        assert ctx.execution_results[-1]["correction"] == "retry"

    @pytest.mark.asyncio
    async def test_retry_max_attempts_exceeded(self):
        executor = FakeExecutorBrain()
        mgr = CorrectionManager(executor_brain=executor)
        ctx = FakeContext(
            execution_results=[
                {"correction": "retry"},
                {"correction": "retry"},
                {"correction": "retry"},
            ]
        )
        result = await mgr.correct_retry(ctx)
        assert result is False
        executor.execute_step.assert_not_called()

    @pytest.mark.asyncio
    async def test_retry_empty_results(self):
        executor = FakeExecutorBrain(FakeResult(success=True))
        mgr = CorrectionManager(executor_brain=executor)
        ctx = FakeContext(execution_results=[])
        result = await mgr.correct_retry(ctx)
        assert result is True

    @pytest.mark.asyncio
    async def test_retry_failure(self):
        executor = FakeExecutorBrain(FakeResult(success=False, error="timeout"))
        mgr = CorrectionManager(executor_brain=executor)
        ctx = FakeContext(execution_results=[{"step_id": "s1"}])
        result = await mgr.correct_retry(ctx)
        assert result is False


class TestCorrectSearchAndRetry:
    @pytest.mark.asyncio
    async def test_no_intent_returns_false(self):
        mgr = CorrectionManager()
        ctx = FakeContext(intent=None)
        result = await mgr.correct_search_and_retry(ctx)
        assert result is False

    @pytest.mark.asyncio
    async def test_search_fails_returns_false(self):
        registry = FakeSkillRegistry(search_result={"success": False})
        executor = FakeExecutorBrain()
        mgr = CorrectionManager(skill_registry=registry, executor_brain=executor)
        ctx = FakeContext(intent=FakeIntent())
        result = await mgr.correct_search_and_retry(ctx)
        assert result is False
        executor.execute_step.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_success_and_retry(self):
        registry = FakeSkillRegistry(
            search_result={"success": True, "data": {"results": [{"title": "info"}]}}
        )
        executor = FakeExecutorBrain(FakeResult(success=True))
        mgr = CorrectionManager(skill_registry=registry, executor_brain=executor)
        ctx = FakeContext(
            intent=FakeIntent(),
            execution_results=[{"step_id": "s1"}],
        )
        result = await mgr.correct_search_and_retry(ctx)
        assert result is True
        assert ctx.execution_results[-1]["correction"] == "search_and_retry"

    @pytest.mark.asyncio
    async def test_search_enriches_parameters(self):
        registry = FakeSkillRegistry(
            search_result={"success": True, "data": {"results": [{"title": "info"}]}}
        )
        executor = FakeExecutorBrain(FakeResult(success=True))
        mgr = CorrectionManager(skill_registry=registry, executor_brain=executor)
        step = FakeStep(parameters={"template": "report"})
        ctx = FakeContext(
            plan=FakePlan(steps=[step]),
            intent=FakeIntent(),
            execution_results=[{"step_id": "s1"}],
        )
        await mgr.correct_search_and_retry(ctx)
        call_kwargs = executor.execute_step.call_args
        enriched_params = call_kwargs.kwargs.get("parameters") or call_kwargs[1].get(
            "parameters"
        )
        assert "data" in enriched_params
        assert enriched_params["template"] == "report"


class TestCorrectSwitchSkill:
    @pytest.mark.asyncio
    async def test_switch_to_fallback(self):
        executor = FakeExecutorBrain(FakeResult(success=True))
        mgr = CorrectionManager(executor_brain=executor)
        step = FakeStep(skill_id="email")
        ctx = FakeContext(
            plan=FakePlan(steps=[step]),
            execution_results=[{"step_id": "s1"}],
        )
        result = await mgr.correct_switch_skill(ctx)
        assert result is True
        call_kwargs = executor.execute_step.call_args
        skill_id = call_kwargs.kwargs.get("skill_id") or call_kwargs[1].get("skill_id")
        assert skill_id == "send_notification"

    @pytest.mark.asyncio
    async def test_switch_no_fallback_returns_false(self):
        executor = FakeExecutorBrain()
        mgr = CorrectionManager(executor_brain=executor)
        step = FakeStep(skill_id="nonexistent_skill")
        ctx = FakeContext(plan=FakePlan(steps=[step]))
        result = await mgr.correct_switch_skill(ctx)
        assert result is False
        executor.execute_step.assert_not_called()

    @pytest.mark.asyncio
    async def test_switch_updates_skill_id_in_result(self):
        executor = FakeExecutorBrain(FakeResult(success=True))
        mgr = CorrectionManager(executor_brain=executor)
        step = FakeStep(skill_id="email")
        ctx = FakeContext(
            plan=FakePlan(steps=[step]),
            execution_results=[{"step_id": "s1"}],
        )
        await mgr.correct_switch_skill(ctx)
        assert ctx.execution_results[-1]["skill_id"] == "send_notification"
        assert ctx.execution_results[-1]["correction"] == "switch_skill"


class TestCorrectDegrade:
    @pytest.mark.asyncio
    async def test_degrade_success(self):
        executor = FakeExecutorBrain(FakeResult(success=True))
        mgr = CorrectionManager(executor_brain=executor)
        ctx = FakeContext(execution_results=[{"step_id": "s1"}])
        result = await mgr.correct_degrade(ctx)
        assert result is True
        assert ctx.execution_results[-1]["correction"] == "degrade"

    @pytest.mark.asyncio
    async def test_degrade_passes_degrade_flag(self):
        executor = FakeExecutorBrain(FakeResult(success=True))
        mgr = CorrectionManager(executor_brain=executor)
        ctx = FakeContext(execution_results=[{"step_id": "s1"}])
        await mgr.correct_degrade(ctx)
        call_kwargs = executor.execute_step.call_args
        ctx_arg = call_kwargs.kwargs.get("context") or call_kwargs[1].get("context")
        assert ctx_arg.get("degrade") is True

    @pytest.mark.asyncio
    async def test_degrade_failure(self):
        executor = FakeExecutorBrain(FakeResult(success=False, error="degraded fail"))
        mgr = CorrectionManager(executor_brain=executor)
        ctx = FakeContext(execution_results=[{"step_id": "s1"}])
        result = await mgr.correct_degrade(ctx)
        assert result is False


class TestMakeStepResult:
    def test_basic_result(self):
        step = FakeStep(description="Send email")
        result = FakeResult(success=True, data={"output": "sent"}, execution_time=1.2)
        res = CorrectionManager._make_step_result(step, result, " (test)", "retry")
        assert res["step_id"] == "s1"
        assert res["skill_id"] == "email"
        assert res["description"] == "Send email (test)"
        assert res["success"] is True
        assert res["data"] == {"output": "sent"}
        assert res["correction"] == "retry"

    def test_skill_id_from_result_data(self):
        step = FakeStep(skill_id="original")
        result = FakeResult(success=True, data={"skill_id": "override"})
        res = CorrectionManager._make_step_result(step, result)
        assert res["skill_id"] == "override"

    def test_no_correction_tag(self):
        step = FakeStep()
        result = FakeResult()
        res = CorrectionManager._make_step_result(step, result)
        assert "correction" not in res

    def test_error_in_result(self):
        step = FakeStep()
        result = FakeResult(success=False, error="something failed", execution_time=0.1)
        res = CorrectionManager._make_step_result(step, result)
        assert res["success"] is False
        assert res["error"] == "something failed"
