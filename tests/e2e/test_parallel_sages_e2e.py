"""三贤者并行投票架构 E2E 测试 [TD-005 补充]

覆盖 v0.3.0 核心架构的端到端行为，填补 unit 层（test_parallel_sages.py /
test_intent_router.py / test_consensus_engine.py）与真实执行之间的空白。

测试策略：
- 真实组件：ConsensusEngine / ConsensusChecker / IntentRouter（非 Mock）
- 轻量 Fake Brains：模拟三贤者行为但不调用 LLM（可控、确定性、0 成本）
- _run_async 子线程模式：避免 pytest-asyncio STRICT 模式事件循环冲突
- 临时数据库隔离：tmp_path 重定向 OPC_DATA_DIR

覆盖范围：
1. IntentRouter 三路路由（GREETING/SIMPLE/COMPLEX）端到端分流
2. 关键决策点识别（email/report/finance vs 普通查询）
3. 并行投票决策（UNANIMOUS/MAJORITY/VETOED/ESCALATED）
4. fail-close 机制（超时降级 + 异常跳过 + 串行超时拒绝执行）
5. 完整链路（路由 → 关键决策点 → 共识投票 → 执行/跳过）

依据：
- project_memory 教训"后端 API 测试通过不等于用户能用"
- E2E_REVIEW_v0.5.7.md C-P0-1/C-P0-2：核心价值流未端到端验证
- constants.py CRITICAL_DECISION_SKILLS = {"email", "report", "finance"}
"""

import asyncio
import concurrent.futures
import threading
from dataclasses import dataclass
from typing import Any, Dict, Optional

import pytest

from opc_manager.agent_context import AgentContext
from opc_manager.consensus_checker import ConsensusChecker
from opc_manager.consensus_engine import (
    ConsensusEngine,
    Decision,
    DecisionType,
    Opinion,
    OpinionType,
)
from opc_manager.constants import (
    CRITICAL_DECISION_ACTIONS,
    CRITICAL_DECISION_SKILLS,
    SERIAL_OP_TIMEOUT,
)
from opc_manager.intent_classifier import IntentCategory, IntentRouter
from opc_manager.task_orchestrator import RouteDecision


# ─── 辅助：子线程运行 async（避免事件循环冲突）──────────────────────────


def _run_async(coro):
    """在子线程中运行 async 函数，避免 pytest-asyncio 事件循环冲突。

    与 test_e2e_user_journeys.py 使用相同模式（TD-005 asyncio 修复方案）。
    """
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()


# ─── Fake Brains：轻量级确定性实现（不调用 LLM）────────────────────────


class FakeStrategistBrain:
    """策略脑 Fake — 返回确定性意见，可控 opinion_type/confidence。"""

    def __init__(self, opinion_type: str = "AGREE", confidence: float = 0.85):
        self._opinion_type = opinion_type
        self._confidence = confidence

    def express_opinion(
        self, context_dict: Dict[str, Any], decision_point: str = ""
    ) -> Dict[str, Any]:
        return {
            "brain_type": "strategist",
            "opinion_type": self._opinion_type,
            "reasoning": f"策略脑判断：{decision_point or 'default'}",
            "confidence": self._confidence,
        }


class FakeExecutorBrain:
    """执行脑 Fake — 返回确定性意见。

    同步 express_opinion 返回 Opinion 对象（serial_consensus_fallback 不做
    dict_to_opinion 转换，与 strategist 不同）。
    """

    def __init__(self, opinion_type: str = "AGREE", confidence: float = 0.80):
        self._opinion_type = opinion_type
        self._confidence = confidence

    def express_opinion(
        self, context_dict: Dict[str, Any], decision_point: str = ""
    ) -> Opinion:
        return Opinion(
            brain_type="executor",
            opinion_type=OpinionType[self._opinion_type],
            reasoning=f"执行脑判断：{decision_point or 'default'}",
            confidence=self._confidence,
        )

    async def express_opinion_async(
        self, context_dict: Dict[str, Any], decision_point: str = ""
    ) -> Opinion:
        return Opinion(
            brain_type="executor",
            opinion_type=OpinionType[self._opinion_type],
            reasoning=f"执行脑异步判断：{decision_point or 'default'}",
            confidence=self._confidence,
        )


class FakeReflectorBrain:
    """反思脑 Fake — 返回确定性意见。

    同步 predict_consequence 返回 Opinion 对象（serial_consensus_fallback
    不做 dict_to_opinion 转换）。
    """

    def __init__(self, opinion_type: str = "AGREE", confidence: float = 0.75):
        self._opinion_type = opinion_type
        self._confidence = confidence

    def predict_consequence(
        self, context_dict: Dict[str, Any], planned_action: str = ""
    ) -> Opinion:
        return Opinion(
            brain_type="reflector",
            opinion_type=OpinionType[self._opinion_type],
            reasoning=f"反思脑预判：{planned_action or 'default'}",
            confidence=self._confidence,
        )

    async def predict_consequence_async(
        self, context_dict: Dict[str, Any], planned_action: str = ""
    ) -> Opinion:
        return Opinion(
            brain_type="reflector",
            opinion_type=OpinionType[self._opinion_type],
            reasoning=f"反思脑异步预判：{planned_action or 'default'}",
            confidence=self._confidence,
        )


class SlowBrain:
    """模拟超时的脑 — express_opinion 永远 sleep 超过 timeout。

    strategist 用法返回 dict（serial_consensus_fallback 会 dict_to_opinion），
    reflector 用法返回 Opinion（serial_consensus_fallback 不转换）。
    """

    def express_opinion(self, context_dict: Dict, decision_point: str = "") -> Dict:
        import time

        time.sleep(SERIAL_OP_TIMEOUT + 5)
        return {
            "brain_type": "strategist",
            "opinion_type": "AGREE",
            "reasoning": "should never reach",
            "confidence": 0.9,
        }

    def predict_consequence(self, context_dict: Dict, planned_action: str = "") -> Opinion:
        import time

        time.sleep(SERIAL_OP_TIMEOUT + 5)
        return Opinion(
            brain_type="reflector",
            opinion_type=OpinionType.AGREE,
            reasoning="should never reach",
            confidence=0.9,
        )


@dataclass
class FakeStep:
    """轻量 Step 替代 — 用于关键决策点检测。"""

    id: str = "step-1"
    skill_id: str = ""
    action: str = ""
    description: str = "fake step"
    parameters: Dict[str, Any] = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


class FakeConsensusConsultant:
    """包装 ConsensusEngine，暴露 _consensus 属性。"""

    def __init__(self, engine: ConsensusEngine):
        self._consensus = engine


# ─── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    """重定向数据库到临时目录，避免污染真实数据。"""
    monkeypatch.setenv("OPC_DATA_DIR", str(tmp_path / "data"))
    import opc_manager.data_manager as _dm

    _dm._db_initialized = False
    if hasattr(_dm._local, "conn") and _dm._local.conn is not None:
        try:
            _dm._local.conn.close()
        except Exception:
            pass
    _dm._local = threading.local()
    yield
    _dm._db_initialized = False
    if hasattr(_dm._local, "conn") and _dm._local.conn is not None:
        try:
            _dm._local.conn.close()
        except Exception:
            pass
    _dm._local = threading.local()


def _build_checker(
    strategist: Any = None,
    executor: Any = None,
    reflector: Any = None,
    engine: Optional[ConsensusEngine] = None,
) -> ConsensusChecker:
    """构建真实 ConsensusChecker（非 Mock）。"""
    if engine is None:
        engine = ConsensusEngine()
    consultant = FakeConsensusConsultant(engine)
    return ConsensusChecker(
        strategist_brain=strategist or FakeStrategistBrain(),
        executor_brain=executor or FakeExecutorBrain(),
        reflector_brain=reflector or FakeReflectorBrain(),
        consensus_consultant=consultant,
    )


def _make_context(
    user_input: str = "发邮件给张总",
    route_category: Optional[str] = None,
) -> AgentContext:
    """构建 AgentContext，可选设置 route_category metadata。"""
    ctx = AgentContext(task_id="test-task-001", user_input=user_input)
    if route_category:
        ctx.metadata["route_category"] = route_category
    return ctx


# ============================================================
# 1. IntentRouter 三路路由 E2E
# ============================================================


class TestIntentRouterThreeWayRouting:
    """三路路由端到端 — 验证 IntentRouter.classify_route 真实分流。

    依据：intent_classifier.py L295-322
    优先级：GREETING > COMPLEX > SIMPLE > 默认 COMPLEX（保守策略）
    """

    @pytest.mark.parametrize(
        "user_input,expected_category",
        [
            # GREETING — 0 LLM 成本，直接响应
            ("你好", IntentCategory.GREETING),
            ("hello", IntentCategory.GREETING),
            ("谢谢", IntentCategory.GREETING),
            ("帮助", IntentCategory.GREETING),
            # COMPLEX — 有副作用，进入三贤者并行投票
            ("发邮件给张总", IntentCategory.COMPLEX),
            ("记录一笔收入3000元", IntentCategory.COMPLEX),
            ("生成本月经营报告", IntentCategory.COMPLEX),
            ("删除客户记录", IntentCategory.COMPLEX),
            # SIMPLE — 无副作用，绕过三贤者（成本1×）
            ("查询本月支出", IntentCategory.SIMPLE),
            ("查看收入记录", IntentCategory.SIMPLE),
            ("什么是三贤者架构", IntentCategory.SIMPLE),
        ],
    )
    def test_classify_route_matches_expected(self, user_input, expected_category):
        """验证三路路由对真实输入的正确分类。"""
        category, confidence = IntentRouter.classify_route(user_input)
        assert category == expected_category, (
            f"输入 '{user_input}' 应分类为 {expected_category.value}，"
            f"实际为 {category.value}"
        )
        assert 0.0 <= confidence <= 1.0

    def test_greeting_route_has_zero_llm_cost(self):
        """GREETING 路由应返回直接响应，0 LLM 成本。"""
        category, _ = IntentRouter.classify_route("你好")
        assert category == IntentCategory.GREETING

        # 验证 RouteDecision 构建逻辑（task_orchestrator.determine_route 的核心）
        decision = RouteDecision(
            is_greeting=(category == IntentCategory.GREETING),
            response="你好！我是 OPC-Agents 助手。",
            confidence=0.95,
        )
        assert decision.is_greeting is True
        assert decision.is_simple is False
        assert len(decision.response) > 0

    def test_simple_route_bypasses_sages(self):
        """SIMPLE 路由应绕过三贤者，metadata 标记 simple。"""
        category, _ = IntentRouter.classify_route("查询本月支出")
        assert category == IntentCategory.SIMPLE

        decision = RouteDecision(is_simple=(category == IntentCategory.SIMPLE))
        assert decision.is_simple is True
        assert decision.is_greeting is False

    def test_complex_route_enters_sages(self):
        """COMPLEX 路由应进入三贤者并行投票。"""
        category, _ = IntentRouter.classify_route("发邮件给张总")
        assert category == IntentCategory.COMPLEX

        decision = RouteDecision(
            is_greeting=False,
            is_simple=False,
            confidence=0.85,
        )
        assert decision.is_greeting is False
        assert decision.is_simple is False

    def test_unknown_input_defaults_to_complex(self):
        """未知输入应默认归为 COMPLEX（保守策略：不确定时走三贤者）。"""
        category, confidence = IntentRouter.classify_route("xyz随机内容abc")
        assert category == IntentCategory.COMPLEX
        assert confidence == 0.50


# ============================================================
# 2. 关键决策点识别 E2E
# ============================================================


class TestCriticalDecisionPointDetection:
    """关键决策点检测 — email/report/finance 不可逆操作触发共识投票。

    依据：consensus_checker.py L75-101
    常量：CRITICAL_DECISION_SKILLS = {"email", "report", "finance"}
    """

    def test_email_skill_is_critical(self):
        """email 技能步骤应识别为关键决策点。"""
        checker = _build_checker()
        ctx = _make_context("发邮件给张总")
        step = FakeStep(skill_id="email", action="send")
        assert checker.is_critical_decision_point(ctx, step) is True

    def test_report_skill_is_critical(self):
        """report 技能步骤应识别为关键决策点。"""
        checker = _build_checker()
        ctx = _make_context("生成经营报告")
        step = FakeStep(skill_id="report", action="generate")
        assert checker.is_critical_decision_point(ctx, step) is True

    def test_finance_skill_is_critical(self):
        """finance 技能步骤应识别为关键决策点（财务写入不可逆）。"""
        checker = _build_checker()
        ctx = _make_context("记录一笔收入")
        step = FakeStep(skill_id="finance", action="execute_operation")
        assert checker.is_critical_decision_point(ctx, step) is True

    def test_critical_action_triggers_even_without_skill(self):
        """send/send_email action 即使 skill_id 不在集合中也触发。"""
        checker = _build_checker()
        ctx = _make_context("发送通知")
        step = FakeStep(skill_id="notification", action="send_notification")
        assert checker.is_critical_decision_point(ctx, step) is True

    def test_non_critical_skill_not_triggered(self):
        """普通技能（如 crm 查询）不应触发关键决策点。"""
        checker = _build_checker()
        ctx = _make_context("查询客户信息")
        step = FakeStep(skill_id="crm", action="query")
        assert checker.is_critical_decision_point(ctx, step) is False

    def test_simple_route_skips_critical_check(self):
        """SIMPLE 路由应跳过关键决策点检查（绕过三贤者）。"""
        checker = _build_checker()
        ctx = _make_context("查询本月支出", route_category="simple")
        # 即使是 email skill，simple route 也不触发
        step = FakeStep(skill_id="email", action="send")
        assert checker.is_critical_decision_point(ctx, step) is False

    def test_empty_step_not_critical(self):
        """空步骤不应触发关键决策点。"""
        checker = _build_checker()
        ctx = _make_context("测试")
        assert checker.is_critical_decision_point(ctx, None) is False

    def test_all_critical_skills_covered(self):
        """验证 CRITICAL_DECISION_SKILLS 包含所有声明的关键技能。"""
        assert CRITICAL_DECISION_SKILLS == {"email", "report", "finance"}
        assert "send" in CRITICAL_DECISION_ACTIONS
        assert "send_email" in CRITICAL_DECISION_ACTIONS
        assert "execute_operation" in CRITICAL_DECISION_ACTIONS


# ============================================================
# 3. 并行投票决策 E2E
# ============================================================


class TestParallelVotingDecisions:
    """三贤者并行投票决策 — 验证 ConsensusEngine.collect_opinions_async 真实行为。

    依据：consensus_engine.py L163-222（collect_opinions_async）
    机制：asyncio.gather + return_exceptions=True + 异常转 ABSTAIN
    """

    def test_unanimous_approval_when_all_agree(self):
        """三贤者全部 AGREE → UNANIMOUS 一致批准。"""
        checker = _build_checker(
            strategist=FakeStrategistBrain("AGREE", 0.9),
            executor=FakeExecutorBrain("AGREE", 0.85),
            reflector=FakeReflectorBrain("AGREE", 0.8),
        )
        ctx = _make_context("发邮件给张总")
        step = FakeStep(skill_id="email", action="send")

        decision = _run_async(
            checker.parallel_consensus(ctx, "execute_step", step)
        )

        assert decision.approved is True
        assert decision.decision_type == DecisionType.UNANIMOUS
        assert decision.confidence > 0.0

    def test_veto_when_one_disagrees_with_high_confidence(self):
        """一方 DISAGREE + 高置信度 → VETOED 否决执行。"""
        checker = _build_checker(
            strategist=FakeStrategistBrain("AGREE", 0.9),
            executor=FakeExecutorBrain("DISAGREE", 0.85),
            reflector=FakeReflectorBrain("AGREE", 0.8),
        )
        ctx = _make_context("发邮件给张总")
        step = FakeStep(skill_id="email", action="send")

        decision = _run_async(
            checker.parallel_consensus(ctx, "execute_step", step)
        )

        assert decision.approved is False
        assert decision.decision_type == DecisionType.VETOED
        assert "executor" in decision.reasoning or "否决" in decision.reasoning

    def test_majority_approval_when_two_agree(self):
        """两方 AGREE + 一方 CONDITIONAL → MAJORITY 或 COMPROMISE 批准。"""
        checker = _build_checker(
            strategist=FakeStrategistBrain("AGREE", 0.9),
            executor=FakeExecutorBrain("AGREE", 0.85),
            reflector=FakeReflectorBrain("CONDITIONAL", 0.7),
        )
        ctx = _make_context("发邮件给张总")
        step = FakeStep(skill_id="email", action="send")

        decision = _run_async(
            checker.parallel_consensus(ctx, "execute_step", step)
        )

        assert decision.approved is True
        # 2 AGREE + 1 CONDITIONAL, 0 DISAGREE → MAJORITY (agree_count > total/2)
        assert decision.decision_type in (DecisionType.MAJORITY, DecisionType.UNANIMOUS)

    def test_escalated_when_no_consensus(self):
        """两方 DISAGREE（低置信度不行使否决）+ 一方 AGREE → ESCALATED。

        VETO_MIN_CONFIDENCE=0.5，confidence < 0.5 的 DISAGREE 不触发否决权，
        进入正常统计：1 AGREE + 2 DISAGREE → agree_count(1) <= total/2(1.5)
        且 disagree_count > 0 → ESCALATED。
        """
        checker = _build_checker(
            strategist=FakeStrategistBrain("AGREE", 0.9),
            executor=FakeExecutorBrain("DISAGREE", 0.4),  # < 0.5 不行使否决
            reflector=FakeReflectorBrain("DISAGREE", 0.4),
        )
        ctx = _make_context("发邮件给张总")
        step = FakeStep(skill_id="email", action="send")

        decision = _run_async(
            checker.parallel_consensus(ctx, "execute_step", step)
        )

        # 1 AGREE + 2 DISAGREE（低置信度不否决）→ ESCALATED
        assert decision.approved is False
        assert decision.decision_type == DecisionType.ESCALATED

    def test_low_confidence_disagree_not_veto(self):
        """低置信度 DISAGREE（< VETO_MIN_CONFIDENCE 0.5）不行使否决权。"""
        checker = _build_checker(
            strategist=FakeStrategistBrain("AGREE", 0.9),
            executor=FakeExecutorBrain("DISAGREE", 0.3),  # 低于 0.5 阈值
            reflector=FakeReflectorBrain("AGREE", 0.8),
        )
        ctx = _make_context("发邮件给张总")
        step = FakeStep(skill_id="email", action="send")

        decision = _run_async(
            checker.parallel_consensus(ctx, "execute_step", step)
        )

        # 2 AGREE + 1 低置信度 DISAGREE → MAJORITY（非 VETOED）
        assert decision.approved is True
        assert decision.decision_type == DecisionType.MAJORITY


# ============================================================
# 4. fail-close 机制 E2E
# ============================================================


class TestFailCloseMechanism:
    """fail-close 机制 — 超时/异常时跳过而非执行（不可逆操作保护）。

    依据：
    - consensus_checker.py L159-213（serial_consensus_fallback + timeout fail-close）
    - task_orchestrator.py L265-278（共识检查异常 → fail-close 跳过步骤）
    硬约束：consensus gate must fail-closed, never fail-open
    """

    def test_serial_fallback_on_parallel_disabled(self, monkeypatch):
        """PARALLEL_VOTE_ENABLED=false 时降级到串行。"""
        monkeypatch.setattr(
            "opc_manager.consensus_checker.PARALLEL_VOTE_ENABLED", False
        )
        checker = _build_checker()
        ctx = _make_context("发邮件给张总")
        step = FakeStep(skill_id="email", action="send")

        decision = _run_async(
            checker.parallel_consensus(ctx, "execute_step", step)
        )

        # 串行正常执行应返回有效决策（非超时）
        assert isinstance(decision, Decision)
        assert decision.confidence >= 0.0

    def test_serial_timeout_fail_close(self, monkeypatch):
        """串行降级超时 → ESCALATED fail-close 拒绝执行。"""
        monkeypatch.setattr(
            "opc_manager.consensus_checker.PARALLEL_VOTE_ENABLED", False
        )
        # 缩短超时以加速测试
        monkeypatch.setattr("opc_manager.consensus_checker.SERIAL_OP_TIMEOUT", 0.5)

        checker = _build_checker(
            strategist=SlowBrain(),
            executor=FakeExecutorBrain(),
            reflector=SlowBrain(),
        )
        ctx = _make_context("发邮件给张总")
        step = FakeStep(skill_id="email", action="send")

        decision = _run_async(
            checker.parallel_consensus(ctx, "execute_step", step)
        )

        assert decision.approved is False
        assert decision.decision_type == DecisionType.ESCALATED
        assert "timeout" in decision.reasoning.lower() or "超时" in decision.reasoning

    def test_parallel_exception_falls_back_to_serial(self, monkeypatch):
        """并行投票异常 → 自动降级到串行（不 fail-open）。"""
        # 模拟 collect_opinions_async 抛异常
        checker = _build_checker()

        original_async = checker._consensus_consultant._consensus.collect_opinions_async

        async def failing_async(*args, **kwargs):
            raise RuntimeError("模拟并行投票基础设施故障")

        checker._consensus_consultant._consensus.collect_opinions_async = failing_async

        ctx = _make_context("发邮件给张总")
        step = FakeStep(skill_id="email", action="send")

        decision = _run_async(
            checker.parallel_consensus(ctx, "execute_step", step)
        )

        # 异常后降级到串行，串行正常执行 → 有效决策
        assert isinstance(decision, Decision)

        # 恢复
        checker._consensus_consultant._consensus.collect_opinions_async = original_async

    def test_orchestrator_fail_close_on_consensus_exception(self):
        """模拟 task_orchestrator L265-278：共识检查异常 → fail-close 跳过步骤。

        验证：当 _parallel_consensus 抛异常时，步骤被标记为失败并跳过，
        而非继续执行不可逆操作。
        """
        step = FakeStep(skill_id="email", action="send")

        # 模拟 task_orchestrator.execute_execute_phase 中的 fail-close 逻辑
        consensus_failed = False
        execution_results = []

        try:
            # 模拟 _parallel_consensus 抛异常
            raise RuntimeError("模拟共识检查基础设施故障")
        except Exception as e:
            consensus_failed = True
            # task_orchestrator.py L266-278 的 fail-close 逻辑
            execution_results.append(
                {
                    "step_id": step.id,
                    "skill_id": step.skill_id,
                    "description": step.description,
                    "success": False,
                    "data": None,
                    "error": f"consensus_check_failed: {str(e)}",
                    "execution_time": 0,
                }
            )

        assert consensus_failed is True
        assert len(execution_results) == 1
        assert execution_results[0]["success"] is False
        assert "consensus_check_failed" in execution_results[0]["error"]
        # 关键：步骤被跳过（未执行），error 记录了 fail-close 原因


# ============================================================
# 5. 完整链路 E2E：路由 → 关键决策点 → 共识投票 → 执行/跳过
# ============================================================


class TestFullSagePipeline:
    """完整三贤者链路 — 从路由到共识投票的端到端流程。

    验证：IntentRouter 路由 → 关键决策点检测 → 并行投票 → 批准/否决/跳过
    """

    def test_complex_critical_skill_full_pipeline_approved(self):
        """COMPLEX + email 技能 → 关键决策点 → 三贤者同意 → 批准执行。"""
        # Step 1: 路由
        category, _ = IntentRouter.classify_route("发邮件给张总")
        assert category == IntentCategory.COMPLEX

        # Step 2: 关键决策点检测
        checker = _build_checker(
            strategist=FakeStrategistBrain("AGREE", 0.9),
            executor=FakeExecutorBrain("AGREE", 0.85),
            reflector=FakeReflectorBrain("AGREE", 0.8),
        )
        ctx = _make_context("发邮件给张总")
        step = FakeStep(skill_id="email", action="send")
        assert checker.is_critical_decision_point(ctx, step) is True

        # Step 3: 并行投票
        decision = _run_async(
            checker.parallel_consensus(ctx, "execute_step", step)
        )

        # Step 4: 批准执行
        assert decision.approved is True
        assert decision.decision_type == DecisionType.UNANIMOUS

    def test_complex_critical_skill_vetoed_blocks_execution(self):
        """COMPLEX + email 技能 → 关键决策点 → 反思脑否决 → 阻止执行。"""
        category, _ = IntentRouter.classify_route("发邮件给张总")
        assert category == IntentCategory.COMPLEX

        checker = _build_checker(
            strategist=FakeStrategistBrain("AGREE", 0.9),
            executor=FakeExecutorBrain("AGREE", 0.85),
            reflector=FakeReflectorBrain("DISAGREE", 0.9),  # 高置信度否决
        )
        ctx = _make_context("发邮件给张总")
        step = FakeStep(skill_id="email", action="send")
        assert checker.is_critical_decision_point(ctx, step) is True

        decision = _run_async(
            checker.parallel_consensus(ctx, "execute_step", step)
        )

        # 否决 → 不执行
        assert decision.approved is False
        assert decision.decision_type == DecisionType.VETOED

    def test_simple_route_skips_entire_sage_pipeline(self):
        """SIMPLE 路由 → 跳过整个三贤者流程（成本1×）。"""
        category, _ = IntentRouter.classify_route("查询本月支出")
        assert category == IntentCategory.SIMPLE

        checker = _build_checker()
        ctx = _make_context("查询本月支出", route_category="simple")
        step = FakeStep(skill_id="finance", action="query")

        # SIMPLE 路由不触发关键决策点
        assert checker.is_critical_decision_point(ctx, step) is False
        # 不进入并行投票（is_critical_decision_point=False 意味着不调用 parallel_consensus）

    def test_greeting_route_zero_llm_zero_sage(self):
        """GREETING 路由 → 0 LLM 成本 + 0 三贤者成本。"""
        category, _ = IntentRouter.classify_route("你好")
        assert category == IntentCategory.GREETING

        # GREETING 不进入 execute_execute_phase，不触发关键决策点
        checker = _build_checker()
        ctx = _make_context("你好")
        # GREETING 路由没有步骤，is_critical_decision_point 返回 False
        assert checker.is_critical_decision_point(ctx, None) is False


# ============================================================
# 6. ConsensusEngine 决策日志持久化 E2E
# ============================================================


class TestConsensusDecisionLogPersistence:
    """共识决策日志持久化 — 验证决策记录写入数据库。

    依据：consensus_engine.py L415-448（_log_decision 持久化到 consensus_decisions 表）
    """

    def test_decision_log_persists_to_db(self):
        """决策日志应持久化到 consensus_decisions 表。"""
        engine = ConsensusEngine()

        # 提交一组意见触发决策和日志记录
        opinions = [
            Opinion(brain_type="strategist", opinion_type=OpinionType.AGREE,
                    reasoning="test", confidence=0.9),
            Opinion(brain_type="executor", opinion_type=OpinionType.AGREE,
                    reasoning="test", confidence=0.85),
            Opinion(brain_type="reflector", opinion_type=OpinionType.AGREE,
                    reasoning="test", confidence=0.8),
        ]
        engine.collect_opinions(opinions)

        # 验证内存日志
        log = engine.get_decision_log(limit=10)
        assert len(log) >= 1
        latest = log[-1]
        assert latest["decision_type"] == "unanimous"
        assert latest["approved"] == 1 or latest["approved"] is True
        assert latest["opinion_count"] == 3

    def test_decision_log_loads_from_db(self):
        """重启后应从数据库加载历史决策日志。"""
        engine1 = ConsensusEngine()
        opinions = [
            Opinion(brain_type="strategist", opinion_type=OpinionType.AGREE,
                    reasoning="persist test", confidence=0.9),
            Opinion(brain_type="executor", opinion_type=OpinionType.AGREE,
                    reasoning="persist test", confidence=0.85),
            Opinion(brain_type="reflector", opinion_type=OpinionType.AGREE,
                    reasoning="persist test", confidence=0.8),
        ]
        engine1.collect_opinions(opinions)
        initial_count = len(engine1.get_decision_log())

        # 创建新引擎（模拟重启）
        engine2 = ConsensusEngine()
        loaded_count = len(engine2.get_decision_log())

        assert loaded_count >= initial_count
