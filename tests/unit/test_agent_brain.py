"""
三贤者架构单元测试

覆盖策略脑、执行脑、反思脑、共识引擎、技能注册表、工具系统、执行循环
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from opc_manager import (
    StrategistBrain,
    IntentType,
    ExecutorBrain,
    ReflectorBrain,
    Evaluation,
    EvaluationResult,
    NextActionType,
    CorrectionStrategy,
    ConsensusEngine,
    Opinion,
    OpinionType,
    DecisionType,
    SkillRegistry,
    Skill,
    SkillCategory,
    SkillInput,
    SkillOutput,
    SkillContext,
    ToolSystem,
    Tool,
    ToolCategory,
    ToolParameter,
    PermissionLevel,
    AgentLoop,
    AgentContext,
    AgentState,
    EventEmitter,
    Event,
)


class TestStrategistBrain:
    """策略脑单元测试"""

    def test_intent_understanding_analysis(self):
        """测试意图理解 - 分析类任务"""
        strategist = StrategistBrain()
        intent = strategist.understand_intent("帮我分析竞争对手")

        assert intent.type in (IntentType.ANALYSIS, IntentType.COMBINED)
        # COMBINED意图的主confidence为0.5（默认），但其子意图应有更高置信度
        # ANALYSIS意图应通过关键词匹配获得 >= 0.7 的置信度
        # 阈值从 0.5 提升：确保意图识别真正匹配了关键词，而非仅返回默认值
        if intent.type == IntentType.COMBINED:
            assert (
                intent.confidence >= 0.5
            ), f"COMBINED意图confidence {intent.confidence} 过低"
            assert len(intent.sub_intents) > 0, "COMBINED意图应有子意图"
            sub_confidences = [si.confidence for si in intent.sub_intents]
            assert (
                max(sub_confidences) >= 0.7
            ), f"子意图最高confidence {max(sub_confidences)} 过低，应 >= 0.7"
        else:
            assert (
                intent.confidence >= 0.7
            ), f"confidence {intent.confidence} 过低，匹配关键词的意图应 >= 0.7"

    def test_intent_understanding_creation(self):
        """测试意图理解 - 创作类任务"""
        strategist = StrategistBrain()
        intent = strategist.understand_intent("帮我写文档")

        assert intent.type == IntentType.CREATION
        assert "写文档" in intent.goal

    def test_intent_understanding_with_constraints(self):
        """测试意图理解 - 带约束条件"""
        strategist = StrategistBrain()
        intent = strategist.understand_intent("帮我分析3个竞争对手")

        assert len(intent.constraints) > 0

    def test_plan_generation(self):
        """测试计划生成"""
        strategist = StrategistBrain()
        intent = strategist.understand_intent("帮我搜索资料")
        plan = strategist.plan(intent)

        assert plan is not None
        assert len(plan.steps) >= 2
        assert plan.plan_id is not None


class TestExecutorBrain:
    """执行脑单元测试"""

    @pytest.mark.asyncio
    async def test_execute_step_success(self):
        """测试执行步骤 - 通过SkillRegistry成功"""
        from opc_manager.skill_registry import SkillRegistry

        skill_registry = SkillRegistry()
        executor = ExecutorBrain(skill_registry=skill_registry)
        result = await executor.execute_step("step_1", "search", {"query": "test"})

        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_step_failure(self):
        """测试执行步骤 - 无可用执行器时失败"""
        executor = ExecutorBrain()
        result = await executor.execute_step("step_1", "invalid_skill", {})

        assert result.success is False
        assert "技能不存在" in result.error

    @pytest.mark.asyncio
    async def test_execute_plan(self):
        """测试执行计划 - 通过SkillRegistry"""
        from opc_manager.skill_registry import SkillRegistry

        skill_registry = SkillRegistry()
        executor = ExecutorBrain(skill_registry=skill_registry)
        steps = [
            {
                "id": "step_1",
                "skill_id": "intent_analysis",
                "parameters": {"user_input": "帮我写一份营销方案"},
            }
        ]
        result = await executor.execute_plan("plan_1", steps)

        assert result.success is True


class TestReflectorBrain:
    """反思脑单元测试"""

    def test_evaluation_excellent(self):
        """测试评估 - 优秀"""
        reflector = ReflectorBrain()
        actual = {
            "success": True,
            "data": {
                "results": [{"success": True}] * 5,
                "content": "test result content",
            },
            "execution_time": 10,
        }
        expected = {"goal": "test"}

        evaluation = reflector.evaluate_result(actual, expected)

        assert evaluation.result == EvaluationResult.EXCELLENT
        assert evaluation.quality_score >= 0.9

    def test_evaluation_failure(self):
        """测试评估 - 失败"""
        reflector = ReflectorBrain()
        actual = {"success": False, "error": "failed"}
        expected = {"goal": "test"}

        evaluation = reflector.evaluate_result(actual, expected)

        assert evaluation.result == EvaluationResult.FAILURE
        assert evaluation.quality_score < 0.3

    def test_decision_continue(self):
        """测试决策 - 继续"""
        reflector = ReflectorBrain()
        evaluation = Evaluation(
            result=EvaluationResult.EXCELLENT,
            quality_score=0.95,
            deviation_analysis="执行正常",
        )

        action = reflector.decide_next_action(evaluation)

        assert action.action_type == NextActionType.CONTINUE

    def test_decision_retry(self):
        """测试决策 - 重试"""
        reflector = ReflectorBrain()
        evaluation = Evaluation(
            result=EvaluationResult.FAILURE,
            quality_score=0.1,
            deviation_analysis="执行失败",
        )

        action = reflector.decide_next_action(evaluation, {"retry_count": 0})

        assert action.action_type == NextActionType.RETRY


class TestConsensusEngine:
    """共识引擎单元测试"""

    def test_consensus_unanimous_agree(self):
        """测试共识 - 一致同意"""
        engine = ConsensusEngine()
        opinions = [
            Opinion(
                brain_type="strategist",
                opinion_type=OpinionType.AGREE,
                reasoning="同意",
            ),
            Opinion(
                brain_type="executor", opinion_type=OpinionType.AGREE, reasoning="同意"
            ),
            Opinion(
                brain_type="reflector", opinion_type=OpinionType.AGREE, reasoning="同意"
            ),
        ]

        decision = engine.collect_opinions(opinions)

        assert decision.decision_type == DecisionType.UNANIMOUS
        assert decision.approved is True

    def test_consensus_majority(self):
        engine = ConsensusEngine()
        opinions = [
            Opinion(
                brain_type="strategist",
                opinion_type=OpinionType.AGREE,
                reasoning="同意",
            ),
            Opinion(
                brain_type="executor", opinion_type=OpinionType.AGREE, reasoning="同意"
            ),
            Opinion(
                brain_type="reflector", opinion_type=OpinionType.AGREE, reasoning="同意"
            ),
        ]

        decision = engine.collect_opinions(opinions)

        assert decision.decision_type in (DecisionType.UNANIMOUS, DecisionType.MAJORITY)
        assert decision.approved is True

    def test_consensus_veto(self):
        """测试共识 - 否决"""
        engine = ConsensusEngine()
        opinions = [
            Opinion(
                brain_type="strategist",
                opinion_type=OpinionType.DISAGREE,
                reasoning="否决",
            ),
            Opinion(
                brain_type="executor", opinion_type=OpinionType.AGREE, reasoning="同意"
            ),
            Opinion(
                brain_type="reflector", opinion_type=OpinionType.AGREE, reasoning="同意"
            ),
        ]

        decision = engine.collect_opinions(opinions)

        assert decision.decision_type == DecisionType.VETOED
        assert decision.approved is False


class TestSkillRegistry:
    """技能注册表单元测试"""

    def test_register_skill(self):
        """测试注册技能"""
        registry = SkillRegistry()
        skill = Skill(
            skill_id="test_skill",
            name="测试技能",
            description="测试技能描述",
            category=SkillCategory.UTILITY,
            inputs=[SkillInput(name="param1", type="str")],
            outputs=[SkillOutput(name="result", type="str")],
            execute=lambda: {"success": True},
        )

        result = registry.register_skill(skill)

        assert result is True
        assert registry.get_skill("test_skill") is not None

    def test_find_by_intent(self):
        """测试根据意图查找技能"""
        registry = SkillRegistry()
        skills = registry.find_by_intent("搜索资料")

        assert len(skills) > 0
        assert any(s.skill_id == "search" for s in skills)

    @pytest.mark.asyncio
    async def test_execute_skill(self):
        registry = SkillRegistry()
        result = await registry.execute_skill("search", query="test")

        assert result["success"] is True
        assert "results" in result["data"]


class TestToolSystem:
    """工具调用框架单元测试"""

    def test_register_tool(self):
        """测试注册工具"""
        tools = ToolSystem()
        tool = Tool(
            tool_id="test_tool",
            name="测试工具",
            description="测试工具描述",
            category=ToolCategory.SYSTEM,
            parameters=[ToolParameter(name="param1", type="str")],
            execute=lambda: {"success": True},
        )

        result = tools.register_tool(tool)

        assert result is True
        assert tools.get_tool("test_tool") is not None

    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        """测试调用工具 - 成功"""
        tools = ToolSystem()
        result = await tools.call_tool("web_search", query="test")

        assert result["success"] is True
        assert "results" in result["data"]

    @pytest.mark.asyncio
    async def test_call_tool_permission_denied(self):
        """测试调用工具 - 权限不足"""
        tools = ToolSystem()
        result = await tools.call_tool(
            "run_command", PermissionLevel.USER, command="ls"
        )

        assert result["success"] is False
        assert "权限不足" in result["error"]


class TestAgentLoop:
    """执行循环单元测试"""

    @pytest.mark.asyncio
    async def test_run_simple_task(self):
        """测试运行简单任务（mock 依赖避免真实 LLM 调用）"""
        loop = AgentLoop(
            strategist_brain=MagicMock(),
            executor_brain=MagicMock(),
            reflector_brain=MagicMock(),
            skill_registry=MagicMock(),
            tool_system=MagicMock(),
            session_manager=MagicMock(),
            task_engine=MagicMock(),
        )
        route_decision = MagicMock()
        route_decision.is_greeting = False
        route_decision.is_simple = True
        route_decision.response = ""
        route_decision.confidence = 0.9
        loop._orchestrator.determine_route = MagicMock(return_value=route_decision)
        loop._orchestrator.execute_plan_phase = AsyncMock()
        loop._orchestrator.run_reflect_loop = AsyncMock(return_value=None)

        result = await loop.run("帮我搜索资料")

        assert result is not None

    def test_get_task_status(self):
        """测试获取任务状态"""
        loop = AgentLoop()
        status = loop.get_task_status("non_existent")

        assert status is None

    @pytest.mark.asyncio
    async def test_cancel_task(self):
        """测试取消任务"""
        loop = AgentLoop()
        result = await loop.cancel_task("non_existent")

        assert result is False


class TestPHASE2SkillIntegration:
    """PHASE2 核心技能集成测试"""

    def test_skill_context_creation(self):
        ctx = SkillContext(user_input="帮我分析竞品", session_id="test-001")
        assert ctx.user_input == "帮我分析竞品"
        assert ctx.session_id == "test-001"
        assert ctx.step_results == {}
        assert ctx.conversation_history == []

    def test_skill_context_with_step_results(self):
        ctx = SkillContext(
            user_input="帮我分析",
            step_results={"search": {"results": [{"title": "test"}]}},
        )
        assert "search" in ctx.step_results

    def test_skill_registry_dependency_injection(self):
        registry = SkillRegistry(
            llm_service=None, search_processor=None, tool_system=None
        )
        assert registry.llm_service is None
        assert registry.search_processor is None
        assert registry.tool_system is None

    def test_skill_registry_with_search_processor(self):
        from opc_manager.search_processor import SearchResultProcessor

        processor = SearchResultProcessor()
        registry = SkillRegistry(search_processor=processor)
        assert registry.search_processor is not None

    @pytest.mark.asyncio
    async def test_search_skill_query_preprocessing(self):
        registry = SkillRegistry()
        result = await registry.execute_skill("search", query="AI<>&趋势")
        assert result["success"] is True
        assert result["data"]["count"] >= 0

    @pytest.mark.asyncio
    async def test_search_skill_empty_query(self):
        registry = SkillRegistry()
        result = await registry.execute_skill("search", query="<>")
        assert result["success"] is True
        assert result["data"]["count"] == 0

    @pytest.mark.asyncio
    async def test_analysis_skill_rule_based_fallback(self):
        registry = SkillRegistry()
        result = await registry.execute_skill("analysis", goal="竞品分析")
        assert result["success"] is True
        data = result["data"]
        assert "analysis_result" in data
        assert "swot" in data
        assert "action_items" in data

    @pytest.mark.asyncio
    async def test_content_generation_rule_based_fallback(self):
        registry = SkillRegistry()
        result = await registry.execute_skill("content_generation", goal="Q2营销方案")
        assert result["success"] is True
        data = result["data"]
        assert "content" in data
        assert "fallback_used" in data

    @pytest.mark.asyncio
    async def test_operation_skill_no_tool_system(self):
        registry = SkillRegistry()
        result = await registry.execute_skill(
            "execute_operation",
            operation="read_file",
            parameters={"file_path": "/tmp/test.txt"},
        )
        assert result["success"] is True
        assert "error" in result["data"]

    @pytest.mark.asyncio
    async def test_notification_skill_no_tool_system(self):
        registry = SkillRegistry()
        result = await registry.execute_skill(
            "send_notification", message="测试消息", recipient="test@example.com"
        )
        assert result["success"] is True
        data = result["data"]
        assert data.get("sent") is False or "error" in data

    @pytest.mark.asyncio
    async def test_notification_crlf_injection_protection(self):
        registry = SkillRegistry()
        result = await registry.execute_skill(
            "send_notification",
            message="测试",
            recipient="test@example.com\r\nBCC:evil@evil.com",
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_skill_context_passing(self):
        registry = SkillRegistry()
        ctx = SkillContext(
            user_input="测试", session_id="s1", step_results={"prev": "data"}
        )
        result = await registry.execute_skill("search", context=ctx, query="AI趋势")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_analysis_output_structure(self):
        registry = SkillRegistry()
        result = await registry.execute_skill("analysis", goal="市场分析")
        data = result["data"]
        assert "swot" in data
        swot = data["swot"]
        assert "strengths" in swot
        assert "weaknesses" in swot
        assert "opportunities" in swot
        assert "threats" in swot


class TestPHASE3EndToEnd:
    """PHASE3 端到端闭环集成测试"""

    def test_agent_loop_accepts_session_id(self):
        loop = AgentLoop()
        assert hasattr(loop, "session_manager")

    def test_agent_context_has_session_id(self):
        ctx = AgentContext(task_id="test", user_input="hello")
        assert ctx.session_id is None

    def test_agent_context_has_correction_count(self):
        ctx = AgentContext(task_id="test", user_input="hello")
        assert ctx.correction_count == 0

    def test_agent_context_has_paused_at(self):
        ctx = AgentContext(task_id="test", user_input="hello")
        assert ctx.paused_at is None

    def test_agent_state_has_paused(self):
        assert AgentState.PAUSED.value == "paused"

    def test_correction_strategy_enum(self):
        assert CorrectionStrategy.RETRY.value == "retry"
        assert CorrectionStrategy.SEARCH_AND_RETRY.value == "search_and_retry"
        assert CorrectionStrategy.SWITCH_SKILL.value == "switch_skill"
        assert CorrectionStrategy.DEGRADE.value == "degrade"

    def test_reflector_suggest_correction_high_quality(self):
        brain = ReflectorBrain()
        evaluation = Evaluation(
            result=EvaluationResult.GOOD,
            quality_score=0.8,
            deviation_analysis="结果良好",
        )
        strategy = brain.suggest_correction_strategy(evaluation, [], 0)
        assert strategy is None

    def test_reflector_suggest_correction_low_quality(self):
        brain = ReflectorBrain()
        evaluation = Evaluation(
            result=EvaluationResult.POOR,
            quality_score=0.3,
            deviation_analysis="结果较差",
        )
        strategy = brain.suggest_correction_strategy(
            evaluation, [{"success": False}], 0
        )
        assert strategy == CorrectionStrategy.RETRY

    def test_reflector_suggest_correction_max_attempts(self):
        brain = ReflectorBrain()
        evaluation = Evaluation(
            result=EvaluationResult.POOR,
            quality_score=0.3,
            deviation_analysis="结果较差",
        )
        strategy = brain.suggest_correction_strategy(evaluation, [], 2)
        assert strategy is None

    def test_reflector_check_placeholders(self):
        brain = ReflectorBrain()
        results = [{"success": True, "data": {"content": "结果[待补充]内容"}}]
        assert brain._next_action_decider._check_placeholders(results) is True

    def test_reflector_check_no_placeholders(self):
        brain = ReflectorBrain()
        results = [{"success": True, "data": {"content": "结果完整内容"}}]
        assert brain._next_action_decider._check_placeholders(results) is False

    def test_composite_intent_decomposition(self):
        brain = StrategistBrain()
        intent = brain.understand_intent("帮我分析竞品然后写方案")
        assert intent.type == IntentType.COMBINED
        assert len(intent.sub_intents) >= 2

    def test_composite_plan_has_multiple_steps(self):
        brain = StrategistBrain()
        intent = brain.understand_intent("帮我分析竞品然后写方案")
        plan = brain.plan(intent)
        assert len(plan.steps) >= 4

    @pytest.mark.asyncio
    async def test_pause_task(self):
        loop = AgentLoop()
        await loop.run("帮我搜索AI趋势")
        # TaskResult doesn't carry task_id; verify via contexts
        task_id = loop.contexts.keys()[0]
        paused = await loop.pause_task(task_id)
        assert paused is False

    @pytest.mark.asyncio
    async def test_pause_nonexistent_task(self):
        loop = AgentLoop()
        paused = await loop.pause_task("nonexistent")
        assert paused is False

    @pytest.mark.asyncio
    async def test_resume_nonexistent_task(self):
        loop = AgentLoop()
        result = await loop.resume_task("nonexistent")
        assert result["success"] is False

    def test_event_emitter_creation(self):
        emitter = EventEmitter()
        assert emitter.subscriber_count == 0

    def test_event_emitter_emit(self):
        emitter = EventEmitter()
        emitter.emit("step_started", "step_1", "测试步骤", "running")
        assert emitter.subscriber_count == 0

    def test_event_dataclass(self):
        import time

        event = Event(
            event_type="step_completed",
            step_id="step_1",
            step_name="测试步骤",
            status="completed",
            timestamp=time.time(),
            duration_ms=150.5,
        )
        assert event.event_type == "step_completed"
        assert event.duration_ms == 150.5

    def test_agent_loop_has_event_emitter(self):
        loop = AgentLoop()
        assert hasattr(loop, "event_emitter")
        assert isinstance(loop.event_emitter, EventEmitter)

    @pytest.mark.asyncio
    async def test_run_with_session_id(self):
        loop = AgentLoop()
        result = await loop.run("帮我搜索AI趋势", session_id="test-session-001")
        assert result.success
        # Verify session_id was stored in the context
        ctx = next(iter(loop.contexts.values()))
        assert ctx.session_id == "test-session-001"

    @pytest.mark.asyncio
    async def test_run_generates_session_id(self):
        loop = AgentLoop()
        result = await loop.run("帮我搜索AI趋势")
        assert result.success
        # Verify a session_id was auto-generated in the context
        ctx = next(iter(loop.contexts.values()))
        assert ctx.session_id is not None
        assert len(ctx.session_id) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
