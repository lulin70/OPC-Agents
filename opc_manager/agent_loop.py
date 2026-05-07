"""
执行循环 (AgentLoop) - 负责协调三贤者的完整执行流程

这是三贤者架构的核心协调器，实现 Plan→Act→Observe→Reflect 循环：
- Plan: 策略脑制定执行计划
- Act: 执行脑执行计划
- Observe: 收集执行结果
- Reflect: 反思脑评估并决定下一步
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging
import uuid

from .strategist_brain import StrategistBrain, Intent, ExecutionPlan
from .executor_brain import ExecutorBrain, ExecutionResult, ExecutionStatus
from .reflector_brain import ReflectorBrain, Evaluation, NextAction, NextActionType
from .consensus_engine import ConsensusEngine, Opinion, OpinionType, DecisionType
from .skill_registry import SkillRegistry
from .tool_system import ToolSystem
from .utils import BoundedDict

logger = logging.getLogger(__name__)

MAX_RETRY_PER_STEP = 3
MAX_CONTEXT_HISTORY = 100
MAX_REFLECT_ROUNDS = 3
RETRY_BACKOFF_BASE = 2
RETRY_BACKOFF_CAP = 10


class AgentState(Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    OBSERVING = "observing"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentContext:
    task_id: str
    user_input: str
    state: AgentState = AgentState.IDLE
    intent: Optional[Intent] = None
    plan: Optional[ExecutionPlan] = None
    execution_results: List[Dict] = field(default_factory=list)
    current_step: int = 0
    retry_count: int = 0
    step_retry_counts: Dict[str, int] = field(default_factory=dict)
    cancel_requested: bool = False

    def set_state(self, new_state: AgentState) -> None:
        self.state = new_state


class AgentLoop:

    def __init__(self,
                 strategist_brain: StrategistBrain = None,
                 executor_brain: ExecutorBrain = None,
                 reflector_brain: ReflectorBrain = None,
                 consensus_engine: ConsensusEngine = None,
                 skill_registry: SkillRegistry = None,
                 tool_system: ToolSystem = None,
                 max_reflect_rounds: int = MAX_REFLECT_ROUNDS,
                 max_retry_per_step: int = MAX_RETRY_PER_STEP):
        self.strategist_brain = strategist_brain or StrategistBrain()
        self.executor_brain = executor_brain or ExecutorBrain()
        self.reflector_brain = reflector_brain or ReflectorBrain()
        self.consensus_engine = consensus_engine or ConsensusEngine()
        self.skill_registry = skill_registry or SkillRegistry()
        self.tool_system = tool_system or ToolSystem()

        self.max_reflect_rounds = max_reflect_rounds
        self.max_retry_per_step = max_retry_per_step

        self.contexts: BoundedDict = BoundedDict(max_size=MAX_CONTEXT_HISTORY)

    async def run(self, user_input: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        logger.info(f"AgentLoop 开始执行: {user_input[:50]}...")

        if not user_input or not user_input.strip():
            return {"success": False, "error": "用户输入不能为空", "message": "输入无效"}

        task_id = f"agent_task_{uuid.uuid4().hex[:8]}"
        agent_context = AgentContext(
            task_id=task_id,
            user_input=user_input.strip()
        )
        self.contexts[task_id] = agent_context

        try:
            agent_context.set_state(AgentState.PLANNING)
            await self._phase_plan(agent_context)

            if agent_context.cancel_requested:
                agent_context.set_state(AgentState.CANCELLED)
                return self._build_result(agent_context, cancelled=True)

            for reflect_round in range(self.max_reflect_rounds):
                agent_context.set_state(AgentState.EXECUTING)
                await self._phase_execute(agent_context)

                if agent_context.cancel_requested:
                    agent_context.set_state(AgentState.CANCELLED)
                    return self._build_result(agent_context, cancelled=True)

                agent_context.set_state(AgentState.OBSERVING)
                await self._phase_observe(agent_context)

                agent_context.set_state(AgentState.REFLECTING)
                next_action = await self._phase_reflect(agent_context)

                if next_action.action_type == NextActionType.CONTINUE:
                    break
                elif next_action.action_type == NextActionType.REVIEW:
                    logger.info(f"反思轮次 {reflect_round + 1}: 需要人工复核，终止自动循环")
                    break
                elif next_action.action_type == NextActionType.ABANDON:
                    agent_context.set_state(AgentState.FAILED)
                    return {
                        "success": False,
                        "task_id": task_id,
                        "results": agent_context.execution_results,
                        "error": next_action.reason,
                        "message": "任务放弃"
                    }
                elif next_action.action_type in (NextActionType.RETRY, NextActionType.ADJUST_STRATEGY):
                    logger.info(f"反思轮次 {reflect_round + 1}: {next_action.action_type.name}，重新执行")
                    agent_context.execution_results = []
                    agent_context.current_step = 0
                    if next_action.action_type == NextActionType.ADJUST_STRATEGY:
                        agent_context.set_state(AgentState.PLANNING)
                        await self._phase_plan(agent_context)
                    continue
            else:
                logger.warning(f"反思循环已达上限 {self.max_reflect_rounds} 次")

            agent_context.set_state(AgentState.COMPLETED)
            logger.info(f"AgentLoop 执行完成: {task_id}")

            return self._build_result(agent_context)

        except Exception as e:
            agent_context.set_state(AgentState.FAILED)
            logger.error(f"AgentLoop 执行失败: {str(e)}")
            return {
                "success": False,
                "task_id": task_id,
                "error": str(e),
                "message": "执行失败"
            }

    def _build_result(self, context: AgentContext, cancelled: bool = False) -> Dict[str, Any]:
        if cancelled:
            return {
                "success": False,
                "task_id": context.task_id,
                "results": context.execution_results,
                "message": "任务已取消"
            }
        return {
            "success": True,
            "task_id": context.task_id,
            "results": context.execution_results,
            "message": "执行完成"
        }

    async def _phase_plan(self, context: AgentContext) -> None:
        logger.info("Phase 1: 规划开始")

        intent = self.strategist_brain.understand_intent(
            user_input=context.user_input,
            context={"history": []}
        )
        context.intent = intent
        logger.info(f"意图理解完成: {intent.type.name} - {intent.goal}")

        plan = self.strategist_brain.plan(intent)
        context.plan = plan
        logger.info(f"计划制定完成: {len(plan.steps)} 个步骤")

    async def _phase_execute(self, context: AgentContext) -> None:
        logger.info("Phase 2: 执行开始")

        if not context.plan:
            raise ValueError("没有执行计划，无法执行")

        for step in context.plan.steps:
            if context.cancel_requested:
                return

            context.current_step += 1
            logger.info(f"执行步骤 {context.current_step}/{len(context.plan.steps)}: {step.description}")

            result = await self._execute_step_with_retry(context, step)

            context.execution_results.append({
                "step_id": step.id,
                "skill_id": step.skill_id,
                "description": step.description,
                "success": result.success,
                "data": result.data,
                "error": result.error,
                "execution_time": result.execution_time
            })

            if not result.success:
                logger.warning(f"步骤 {step.id} 执行失败（已重试{context.step_retry_counts.get(step.id, 0)}次）: {result.error}")
                break

    async def _execute_step_with_retry(self, context: AgentContext, step) -> ExecutionResult:
        step_retries = context.step_retry_counts.get(step.id, 0)

        result = await self.executor_brain.execute_step(
            step_id=step.id,
            skill_id=step.skill_id,
            parameters=step.parameters,
            context={"task_id": context.task_id}
        )

        while not result.success and step_retries < self.max_retry_per_step:
            if context.cancel_requested:
                return result

            step_retries += 1
            context.step_retry_counts[step.id] = step_retries
            context.retry_count += 1
            logger.info(f"步骤 {step.id} 失败，重试第 {step_retries}/{self.max_retry_per_step} 次")

            await asyncio.sleep(min(RETRY_BACKOFF_BASE ** step_retries, RETRY_BACKOFF_CAP))

            result = await self.executor_brain.execute_step(
                step_id=step.id,
                skill_id=step.skill_id,
                parameters=step.parameters,
                context={"task_id": context.task_id}
            )

            context.execution_results.append({
                "step_id": step.id,
                "skill_id": step.skill_id,
                "description": f"{step.description} (重试#{step_retries})",
                "success": result.success,
                "data": result.data,
                "error": result.error,
                "execution_time": result.execution_time,
                "retry": step_retries
            })

        context.step_retry_counts[step.id] = step_retries
        return result

    async def _phase_observe(self, context: AgentContext) -> None:
        logger.info("Phase 3: 观察开始")

        total_steps = len(context.plan.steps) if context.plan else 0
        completed_steps = sum(1 for r in context.execution_results if r.get("success", False))
        total_time = sum(r.get("execution_time", 0) for r in context.execution_results)

        logger.info(f"执行结果汇总: {completed_steps}/{total_steps} 步骤完成，总耗时: {total_time:.2f}秒")

    async def _phase_reflect(self, context: AgentContext) -> NextAction:
        logger.info("Phase 4: 反思开始")

        overall_result = {
            "success": all(r.get("success", False) for r in context.execution_results),
            "data": {
                "results": context.execution_results,
                "total_steps": len(context.execution_results),
                "completed_steps": sum(1 for r in context.execution_results if r.get("success", False)),
                "total_time": sum(r.get("execution_time", 0) for r in context.execution_results)
            }
        }

        evaluation = self.reflector_brain.evaluate_result(
            actual_result=overall_result,
            expected_intent={"goal": context.intent.goal} if context.intent else {}
        )

        logger.info(f"评估结果: {evaluation.result.name} (质量评分: {evaluation.quality_score:.2f})")

        plan_dict = None
        if context.plan:
            plan_dict = {
                "steps": [
                    {"id": s.id, "skill_id": s.skill_id, "description": s.description}
                    for s in context.plan.steps
                ],
                "retry_count": context.retry_count
            }

        next_action = self.reflector_brain.decide_next_action(
            evaluation=evaluation,
            plan=plan_dict
        )

        consensus_decision = self._consult_consensus(context, evaluation, next_action)
        if consensus_decision is not None:
            return consensus_decision

        logger.info(f"决定下一步行动: {next_action.action_type.name}")
        return next_action

    def _consult_consensus(self, context: AgentContext,
                           evaluation: Evaluation,
                           reflector_action: NextAction) -> Optional[NextAction]:
        if evaluation.quality_score >= 0.7:
            return None

        strategist_opinion = Opinion(
            brain_type="strategist",
            opinion_type=OpinionType.AGREE if context.intent and context.intent.confidence > 0.5 else OpinionType.CONDITIONAL,
            reasoning=f"策略脑置信度: {context.intent.confidence:.2f}" if context.intent else "无意图信息",
            confidence=context.intent.confidence if context.intent else 0.5
        )

        executor_opinion = Opinion(
            brain_type="executor",
            opinion_type=OpinionType.AGREE if context.retry_count < 2 else OpinionType.DISAGREE,
            reasoning=f"执行重试次数: {context.retry_count}",
            confidence=max(0.3, 1.0 - context.retry_count * 0.3)
        )

        reflector_opinion = Opinion(
            brain_type="reflector",
            opinion_type=OpinionType.AGREE if reflector_action.action_type in (NextActionType.CONTINUE, NextActionType.RETRY) else OpinionType.DISAGREE,
            reasoning=f"反思评估: {evaluation.result.name}",
            confidence=evaluation.quality_score
        )

        decision = self.consensus_engine.collect_opinions([
            strategist_opinion,
            executor_opinion,
            reflector_opinion
        ])

        if decision.decision_type == DecisionType.VETOED:
            logger.info(f"共识引擎否决: {decision.reasoning}")
            return NextAction(
                action_type=NextActionType.ABANDON,
                reason=decision.reasoning,
                confidence=decision.confidence
            )

        if decision.decision_type == DecisionType.ESCALATED:
            logger.info(f"共识引擎升级: {decision.reasoning}")
            return NextAction(
                action_type=NextActionType.REVIEW,
                reason=decision.reasoning,
                confidence=decision.confidence
            )

        return None

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        context = self.contexts.get(task_id)
        if not context:
            return None

        return {
            "task_id": task_id,
            "state": context.state.value,
            "current_step": context.current_step,
            "total_steps": len(context.plan.steps) if context.plan else 0,
            "retry_count": context.retry_count,
            "results": context.execution_results[-5:] if context.execution_results else []
        }

    async def cancel_task(self, task_id: str) -> bool:
        context = self.contexts.get(task_id)
        if not context:
            return False

        context.cancel_requested = True
        context.set_state(AgentState.CANCELLED)
        await self.executor_brain.cancel_execution(task_id)
        logger.info(f"任务已取消: {task_id}")
        return True

    def list_tasks(self) -> List[Dict[str, Any]]:
        tasks = []
        for task_id, context in self.contexts.items():
            tasks.append({
                "task_id": task_id,
                "user_input": context.user_input[:50] + "..." if len(context.user_input) > 50 else context.user_input,
                "state": context.state.value,
                "current_step": context.current_step
            })
        return tasks

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "agent_loop",
            "task_count": len(self.contexts),
            "active_tasks": sum(
                1 for ctx in self.contexts.values()
                if ctx.state in (AgentState.PLANNING, AgentState.EXECUTING, AgentState.OBSERVING, AgentState.REFLECTING)
            )
        }
