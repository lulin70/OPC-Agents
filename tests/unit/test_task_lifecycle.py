"""task_lifecycle 模块单元测试

覆盖 TaskLifecycleManager（状态查询/取消/暂停/恢复/列表）和
ConsensusConsultant（共识咨询/执行脑意见构建/日志写入）。
"""

import os
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from opc_manager.agent_context import AgentContext, AgentState
from opc_manager.consensus_engine import Decision, DecisionType, Opinion, OpinionType
from opc_manager.reflector_models import (
    Evaluation,
    EvaluationResult,
    NextAction,
    NextActionType,
)
from opc_manager.task_lifecycle import (
    ConsensusConsultant,
    TaskLifecycleManager,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(
    task_id: str = "task-001",
    user_input: str = "帮我分析市场",
    state: AgentState = AgentState.EXECUTING,
    current_step: int = 2,
    retry_count: int = 0,
    plan=None,
    results=None,
    paused_at=None,
) -> AgentContext:
    ctx = AgentContext(task_id=task_id, user_input=user_input, state=state)
    ctx.current_step = current_step
    ctx.retry_count = retry_count
    ctx.plan = plan
    ctx.execution_results = results or []
    ctx.paused_at = paused_at
    return ctx


def _make_plan(steps=None):
    """Build a lightweight plan object with a steps list."""
    return SimpleNamespace(steps=steps or [])


def _make_step(skill_id="search", description="搜索资料"):
    return SimpleNamespace(skill_id=skill_id, description=description)


def _make_evaluation(score: float = 0.5) -> Evaluation:
    return Evaluation(
        result=EvaluationResult.ACCEPTABLE,
        quality_score=score,
        deviation_analysis="轻微偏差",
    )


def _make_strategist_data(opinion_type="AGREE", confidence=0.8) -> dict:
    return {
        "brain_type": "strategist",
        "opinion_type": opinion_type,
        "reasoning": "策略合理",
        "confidence": confidence,
    }


def _make_reflector_data(opinion_type="AGREE", confidence=0.7) -> dict:
    return {
        "brain_type": "reflector",
        "opinion_type": opinion_type,
        "reasoning": "反思通过",
        "confidence": confidence,
    }


def _make_decision(
    decision_type: DecisionType = DecisionType.MAJORITY,
    confidence: float = 0.8,
    reasoning: str = "多数同意",
) -> Decision:
    return Decision(
        decision_type=decision_type,
        approved=True,
        reasoning=reasoning,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# TaskLifecycleManager — no DB needed
# ---------------------------------------------------------------------------


class TestGetTaskStatus:
    """get_task_status 测试"""

    def test_nonexistent_returns_none(self):
        mgr = TaskLifecycleManager({}, None)
        assert mgr.get_task_status("no-such") is None

    def test_returns_status_dict(self):
        ctx = _make_context(current_step=3, retry_count=1)
        mgr = TaskLifecycleManager({"t1": ctx}, None)
        status = mgr.get_task_status("t1")
        assert status["task_id"] == "t1"
        assert status["state"] == "executing"
        assert status["current_step"] == 3
        assert status["retry_count"] == 1
        assert status["total_steps"] == 0
        assert status["results"] == []

    def test_with_plan_counts_steps(self):
        plan = _make_plan([_make_step(), _make_step(), _make_step()])
        ctx = _make_context(plan=plan)
        mgr = TaskLifecycleManager({"t1": ctx}, None)
        status = mgr.get_task_status("t1")
        assert status["total_steps"] == 3

    def test_results_truncated_to_last_5(self):
        results = [{"success": True} for _ in range(10)]
        ctx = _make_context(results=results)
        mgr = TaskLifecycleManager({"t1": ctx}, None)
        status = mgr.get_task_status("t1")
        assert len(status["results"]) == 5


class TestCancelTask:
    """cancel_task 测试"""

    @pytest.mark.asyncio
    async def test_nonexistent_returns_false(self):
        mgr = TaskLifecycleManager({}, None)
        assert await mgr.cancel_task("no-such") is False

    @pytest.mark.asyncio
    async def test_cancel_sets_state_and_calls_executor(self):
        ctx = _make_context()
        executor = MagicMock()
        executor.cancel_execution = AsyncMock(return_value=True)
        mgr = TaskLifecycleManager({"t1": ctx}, executor)
        result = await mgr.cancel_task("t1")
        assert result is True
        assert ctx.cancel_requested is True
        assert ctx.state == AgentState.CANCELLED
        executor.cancel_execution.assert_called_once_with("t1")


class TestPauseTask:
    """pause_task 测试"""

    @pytest.mark.asyncio
    async def test_nonexistent_returns_false(self):
        mgr = TaskLifecycleManager({}, None)
        assert await mgr.pause_task("no-such") is False

    @pytest.mark.asyncio
    async def test_pause_executing_state(self):
        ctx = _make_context(state=AgentState.EXECUTING)
        mgr = TaskLifecycleManager({"t1": ctx}, None)
        result = await mgr.pause_task("t1")
        assert result is True
        assert ctx.state == AgentState.PAUSED
        assert ctx.paused_at is not None

    @pytest.mark.asyncio
    async def test_pause_planning_state(self):
        ctx = _make_context(state=AgentState.PLANNING)
        mgr = TaskLifecycleManager({"t1": ctx}, None)
        assert await mgr.pause_task("t1") is True
        assert ctx.state == AgentState.PAUSED

    @pytest.mark.asyncio
    async def test_pause_idle_state_fails(self):
        ctx = _make_context(state=AgentState.IDLE)
        mgr = TaskLifecycleManager({"t1": ctx}, None)
        assert await mgr.pause_task("t1") is False
        assert ctx.state == AgentState.IDLE

    @pytest.mark.asyncio
    async def test_pause_completed_state_fails(self):
        ctx = _make_context(state=AgentState.COMPLETED)
        mgr = TaskLifecycleManager({"t1": ctx}, None)
        assert await mgr.pause_task("t1") is False


class TestResumeTask:
    """resume_task 测试"""

    @pytest.mark.asyncio
    async def test_nonexistent_returns_error(self):
        mgr = TaskLifecycleManager({}, None)
        result = await mgr.resume_task("no-such")
        assert result["success"] is False
        assert "不存在" in result["error"]

    @pytest.mark.asyncio
    async def test_resume_non_paused_state_fails(self):
        ctx = _make_context(state=AgentState.EXECUTING)
        mgr = TaskLifecycleManager({"t1": ctx}, None)
        result = await mgr.resume_task("t1")
        assert result["success"] is False
        assert "不可恢复" in result["error"]

    @pytest.mark.asyncio
    async def test_resume_normal(self):
        ctx = _make_context(state=AgentState.PAUSED, paused_at=99999999999.0)
        mgr = TaskLifecycleManager({"t1": ctx}, None)
        result = await mgr.resume_task("t1")
        assert result["success"] is True
        assert result["task_id"] == "t1"
        assert ctx.state == AgentState.EXECUTING
        assert ctx.paused_at is None

    @pytest.mark.asyncio
    async def test_resume_timeout_cancels(self):
        ctx = _make_context(state=AgentState.PAUSED, paused_at=1.0)
        mgr = TaskLifecycleManager({"t1": ctx}, None)
        result = await mgr.resume_task("t1")
        assert result["success"] is False
        assert "超时" in result["error"]
        assert ctx.state == AgentState.CANCELLED
        assert ctx.cancel_requested is True


class TestListTasks:
    """list_tasks 测试"""

    def test_empty_returns_empty_list(self):
        mgr = TaskLifecycleManager({}, None)
        assert mgr.list_tasks() == []

    def test_lists_multiple_tasks(self):
        ctx1 = _make_context(task_id="t1", user_input="任务一")
        ctx2 = _make_context(task_id="t2", user_input="任务二")
        mgr = TaskLifecycleManager({"t1": ctx1, "t2": ctx2}, None)
        tasks = mgr.list_tasks()
        assert len(tasks) == 2
        ids = {t["task_id"] for t in tasks}
        assert ids == {"t1", "t2"}

    def test_long_input_truncated(self):
        long_input = "A" * 100
        ctx = _make_context(task_id="t1", user_input=long_input)
        mgr = TaskLifecycleManager({"t1": ctx}, None)
        tasks = mgr.list_tasks()
        assert tasks[0]["user_input"].endswith("...")
        assert len(tasks[0]["user_input"]) == 53  # 50 + "..."


class TestToDict:
    """to_dict 测试"""

    def test_empty(self):
        mgr = TaskLifecycleManager({}, None)
        d = mgr.to_dict()
        assert d["type"] == "task_lifecycle_manager"
        assert d["task_count"] == 0
        assert d["active_tasks"] == 0

    def test_counts_active_tasks(self):
        ctx_active = _make_context(state=AgentState.EXECUTING)
        ctx_idle = _make_context(task_id="t2", state=AgentState.IDLE)
        ctx_done = _make_context(task_id="t3", state=AgentState.COMPLETED)
        mgr = TaskLifecycleManager(
            {"t1": ctx_active, "t2": ctx_idle, "t3": ctx_done}, None
        )
        d = mgr.to_dict()
        assert d["task_count"] == 3
        assert d["active_tasks"] == 1


# ---------------------------------------------------------------------------
# ConsensusConsultant
# ---------------------------------------------------------------------------


@pytest.fixture()
def consultant_factory():
    """Factory to build ConsensusConsultant with mocked brains."""

    def _make(
        strategist_data=None,
        reflector_data=None,
        decision=None,
        executor_opinion=None,
        executor_brain=None,
    ):
        strategist = MagicMock()
        strategist.express_opinion = MagicMock(
            return_value=strategist_data or _make_strategist_data()
        )
        reflector = MagicMock()
        reflector.express_opinion = MagicMock(
            return_value=reflector_data or _make_reflector_data()
        )
        consensus = MagicMock()
        consensus.collect_opinions = MagicMock(
            return_value=decision or _make_decision()
        )
        if executor_brain is None:
            executor_brain = MagicMock()
            if executor_opinion is not None:
                executor_brain.express_opinion = MagicMock(
                    return_value=executor_opinion
                )
        return ConsensusConsultant(strategist, reflector, consensus, executor_brain)

    return _make


class TestConsultHighQuality:
    """consult — quality >= threshold returns None"""

    @pytest.mark.asyncio
    async def test_high_quality_returns_none(self, consultant_factory):
        consultant = consultant_factory()
        ctx = _make_context()
        evaluation = _make_evaluation(score=0.8)
        result = await consultant.consult(
            ctx,
            evaluation,
            NextAction(action_type=NextActionType.CONTINUE, reason="ok"),
        )
        assert result is None


class TestConsultLowQuality:
    """consult — quality < threshold triggers consensus"""

    @pytest.mark.asyncio
    async def test_vetoed_returns_abandon(self, consultant_factory):
        decision = _make_decision(
            decision_type=DecisionType.VETOED, reasoning="否决理由"
        )
        consultant = consultant_factory(decision=decision)
        ctx = _make_context()
        evaluation = _make_evaluation(score=0.3)
        result = await consultant.consult(
            ctx,
            evaluation,
            NextAction(action_type=NextActionType.CONTINUE, reason="ok"),
        )
        assert result is not None
        assert result.action_type == NextActionType.ABANDON
        assert "否决理由" in result.reason

    @pytest.mark.asyncio
    async def test_escalated_returns_review(self, consultant_factory):
        decision = _make_decision(
            decision_type=DecisionType.ESCALATED, reasoning="需升级"
        )
        consultant = consultant_factory(decision=decision)
        ctx = _make_context()
        evaluation = _make_evaluation(score=0.4)
        result = await consultant.consult(
            ctx,
            evaluation,
            NextAction(action_type=NextActionType.CONTINUE, reason="ok"),
        )
        assert result is not None
        assert result.action_type == NextActionType.REVIEW
        assert "需升级" in result.reason

    @pytest.mark.asyncio
    async def test_majority_returns_none(self, consultant_factory):
        decision = _make_decision(decision_type=DecisionType.MAJORITY)
        consultant = consultant_factory(decision=decision)
        ctx = _make_context()
        evaluation = _make_evaluation(score=0.5)
        result = await consultant.consult(
            ctx,
            evaluation,
            NextAction(action_type=NextActionType.CONTINUE, reason="ok"),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_calls_brains_and_consensus(self, consultant_factory):
        consultant = consultant_factory()
        ctx = _make_context()
        evaluation = _make_evaluation(score=0.3)
        await consultant.consult(
            ctx,
            evaluation,
            NextAction(action_type=NextActionType.CONTINUE, reason="ok"),
        )
        consultant._strategist.express_opinion.assert_called_once()
        consultant._reflector.express_opinion.assert_called_once()
        consultant._consensus.collect_opinions.assert_called_once()


class TestBuildExecutorOpinion:
    """_build_executor_opinion 测试"""

    def test_with_executor_brain(self):
        expected = Opinion(
            brain_type="executor",
            opinion_type=OpinionType.AGREE,
            reasoning="执行意见",
            confidence=0.9,
        )
        executor_brain = MagicMock()
        executor_brain.express_opinion = MagicMock(return_value=expected)
        consultant = ConsensusConsultant(None, None, None, executor_brain)
        ctx = _make_context()
        opinion = consultant._build_executor_opinion(ctx)
        assert opinion is expected
        executor_brain.express_opinion.assert_called_once()

    def test_without_executor_brain_degrades_to_rules(self):
        consultant = ConsensusConsultant(None, None, None, None)
        ctx = _make_context(retry_count=0)
        opinion = consultant._build_executor_opinion(ctx)
        assert opinion.brain_type == "executor"
        assert opinion.opinion_type == OpinionType.AGREE

    def test_without_executor_brain_high_retry_disagrees(self):
        consultant = ConsensusConsultant(None, None, None, None)
        ctx = _make_context(retry_count=5)
        opinion = consultant._build_executor_opinion(ctx)
        assert opinion.opinion_type == OpinionType.DISAGREE

    def test_executor_brain_exception_degrades(self):
        executor_brain = MagicMock()
        executor_brain.express_opinion = MagicMock(side_effect=RuntimeError("LLM down"))
        consultant = ConsensusConsultant(None, None, None, executor_brain)
        ctx = _make_context(retry_count=0)
        opinion = consultant._build_executor_opinion(ctx)
        assert opinion.brain_type == "executor"
        assert opinion.opinion_type == OpinionType.AGREE


class TestDeriveDecisionPoint:
    """_derive_decision_point 静态方法测试"""

    def test_with_plan_and_valid_step(self):
        plan = _make_plan([_make_step(skill_id="send_email"), _make_step()])
        ctx = _make_context(current_step=0, plan=plan)
        assert ConsensusConsultant._derive_decision_point(ctx) == "send_email"

    def test_with_plan_step_out_of_range(self):
        plan = _make_plan([_make_step()])
        ctx = _make_context(current_step=10, plan=plan)
        assert ConsensusConsultant._derive_decision_point(ctx) == "task_continuation"

    def test_without_plan(self):
        ctx = _make_context(plan=None)
        assert ConsensusConsultant._derive_decision_point(ctx) == "task_continuation"

    def test_step_without_skill_id(self):
        plan = _make_plan([SimpleNamespace(skill_id=None, description="desc")])
        ctx = _make_context(current_step=0, plan=plan)
        assert ConsensusConsultant._derive_decision_point(ctx) == "task_continuation"


class TestSummarizeCurrentStep:
    """_summarize_current_step 静态方法测试"""

    def test_with_plan_and_valid_step(self):
        plan = _make_plan([_make_step(skill_id="search", description="搜索资料")])
        ctx = _make_context(current_step=0, plan=plan)
        summary = ConsensusConsultant._summarize_current_step(ctx)
        assert "step=1/1" in summary
        assert "skill=search" in summary
        assert "desc=搜索资料" in summary

    def test_without_plan(self):
        ctx = _make_context(plan=None, current_step=2)
        summary = ConsensusConsultant._summarize_current_step(ctx)
        assert "step=3" in summary

    def test_step_out_of_range(self):
        plan = _make_plan([_make_step()])
        ctx = _make_context(current_step=5, plan=plan)
        summary = ConsensusConsultant._summarize_current_step(ctx)
        assert "step=6" in summary


class TestSummarizeResults:
    """_summarize_results 静态方法测试"""

    def test_empty_results(self):
        ctx = _make_context(results=[])
        assert ConsensusConsultant._summarize_results(ctx) == "无执行结果"

    def test_with_results(self):
        ctx = _make_context(results=[{"success": True}, {"success": False}])
        summary = ConsensusConsultant._summarize_results(ctx)
        assert "已完成2步" in summary
        assert "最近成功=False" in summary

    def test_with_non_dict_result(self):
        ctx = _make_context(results=["some string"])
        summary = ConsensusConsultant._summarize_results(ctx)
        assert "已完成1步" in summary


# ---------------------------------------------------------------------------
# ConsensusConsultant.log_decision — needs DB isolation
# ---------------------------------------------------------------------------


@pytest.fixture()
def _isolate_db(tmp_path, monkeypatch):
    """Isolate database for log_decision tests."""
    data_dir = str(tmp_path / "data")
    os.makedirs(data_dir, exist_ok=True)
    monkeypatch.setenv("OPC_DATA_DIR", data_dir)
    import opc_manager.data_manager as dm

    monkeypatch.setattr(dm, "DATA_DIR", data_dir)
    monkeypatch.setattr(dm, "DB_PATH", os.path.join(data_dir, "opc_data.db"))
    monkeypatch.setattr(dm, "BACKUP_DIR", os.path.join(data_dir, "backups"))
    monkeypatch.setattr(dm, "_db_initialized", False)
    monkeypatch.setattr(dm, "_local", threading.local())
    dm._local.conn = None
    dm.init_db()
    return dm


class TestLogDecision:
    """log_decision 测试"""

    @pytest.mark.asyncio
    async def test_writes_to_db(self, _isolate_db):
        from opc_manager.data_manager import execute_query

        consultant = ConsensusConsultant(None, None, None, None)
        ctx = _make_context(task_id="log-test-001")
        evaluation = _make_evaluation(score=0.4)
        decision = _make_decision(
            decision_type=DecisionType.VETOED, confidence=0.3, reasoning="测试否决"
        )
        await consultant.log_decision(ctx, evaluation, decision)

        rows = execute_query(
            "SELECT * FROM consensus_decisions WHERE id=?", ("log-test-001",)
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["decision_type"] == "VETOED"
        assert row["confidence"] == 0.3
        assert row["approved"] == 0  # confidence < 0.5

    @pytest.mark.asyncio
    async def test_approved_when_high_confidence(self, _isolate_db):
        from opc_manager.data_manager import execute_query

        consultant = ConsensusConsultant(None, None, None, None)
        ctx = _make_context(task_id="log-test-002")
        evaluation = _make_evaluation(score=0.5)
        decision = _make_decision(
            decision_type=DecisionType.MAJORITY, confidence=0.9, reasoning="通过"
        )
        await consultant.log_decision(ctx, evaluation, decision)

        rows = execute_query(
            "SELECT * FROM consensus_decisions WHERE id=?", ("log-test-002",)
        )
        assert rows[0]["approved"] == 1  # confidence >= 0.5

    @pytest.mark.asyncio
    async def test_db_error_does_not_raise(self, tmp_path, monkeypatch):
        """log_decision should swallow DB errors (defensive)."""
        monkeypatch.setattr(
            "opc_manager.data_manager.init_db",
            MagicMock(side_effect=RuntimeError("DB down")),
        )
        consultant = ConsensusConsultant(None, None, None, None)
        ctx = _make_context(task_id="log-test-003")
        evaluation = _make_evaluation(score=0.4)
        decision = _make_decision()
        # Should not raise
        await consultant.log_decision(ctx, evaluation, decision)
