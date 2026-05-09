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
import os
import time
import uuid

from .strategist_brain import StrategistBrain, Intent, ExecutionPlan
from .executor_brain import ExecutorBrain, ExecutionResult
from .reflector_brain import ReflectorBrain, Evaluation, NextAction, NextActionType, CorrectionStrategy
from .consensus_engine import ConsensusEngine, Opinion, OpinionType, DecisionType
from .skill_registry import SkillRegistry
from .tool_system import ToolSystem
from .session_context import SessionContextManager
from .task_engine_adapter import TaskEngineAdapter
from .utils import BoundedDict, EventEmitter

logger = logging.getLogger(__name__)

MAX_RETRY_PER_STEP = 3
MAX_CONTEXT_HISTORY = 100
MAX_REFLECT_ROUNDS = 3
RETRY_BACKOFF_BASE = 2
RETRY_BACKOFF_CAP = 10
PAUSE_TIMEOUT_SECONDS = 1800
AGENT_LOOP_TIMEOUT_SECONDS = 60


class AgentState(Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    OBSERVING = "observing"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


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
    session_id: Optional[str] = None
    correction_count: int = 0
    paused_at: Optional[float] = None

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
                 session_manager: SessionContextManager = None,
                 task_engine_adapter: TaskEngineAdapter = None,
                 max_reflect_rounds: int = MAX_REFLECT_ROUNDS,
                 max_retry_per_step: int = MAX_RETRY_PER_STEP):
        self.task_engine_adapter = task_engine_adapter or TaskEngineAdapter()
        self.strategist_brain = strategist_brain or StrategistBrain()
        self.executor_brain = executor_brain or ExecutorBrain(task_engine_adapter=self.task_engine_adapter)
        self.reflector_brain = reflector_brain or ReflectorBrain()
        self.consensus_engine = consensus_engine or ConsensusEngine()
        self.skill_registry = skill_registry or SkillRegistry()
        self.tool_system = tool_system or ToolSystem()
        self.session_manager = session_manager or SessionContextManager()
        self.event_emitter = EventEmitter()

        self.max_reflect_rounds = max_reflect_rounds
        self.max_retry_per_step = max_retry_per_step

        self.contexts: BoundedDict = BoundedDict(max_size=MAX_CONTEXT_HISTORY)

    async def run(self, user_input: str, context: Optional[Dict] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        logger.info(f"AgentLoop 开始执行: {user_input[:50]}...")

        if not user_input or not user_input.strip():
            return {"success": False, "error": "用户输入不能为空", "message": "输入无效"}

        run_start_time = time.time()

        task_id = f"agent_task_{uuid.uuid4().hex[:8]}"
        agent_context = AgentContext(
            task_id=task_id,
            user_input=user_input.strip(),
            session_id=session_id or str(uuid.uuid4())
        )
        self.contexts[task_id] = agent_context

        conversation_history = []
        if session_id:
            history_text = self.session_manager.get_context_for_llm(max_turns=5)
            if history_text:
                conversation_history = [{"role": "history", "content": history_text}]

        try:
            agent_context.set_state(AgentState.PLANNING)
            await self._phase_plan(agent_context, conversation_history)

            if agent_context.cancel_requested:
                agent_context.set_state(AgentState.CANCELLED)
                return self._build_result(agent_context, cancelled=True)

            skip_reflect = os.environ.get("OPC_SKIP_REFLECT", "false").lower() == "true"

            if skip_reflect:
                agent_context.set_state(AgentState.EXECUTING)
                await self._phase_execute(agent_context)
                agent_context.set_state(AgentState.COMPLETED)
                return self._build_result(agent_context)

            for reflect_round in range(self.max_reflect_rounds):
                if time.time() - run_start_time > AGENT_LOOP_TIMEOUT_SECONDS:
                    logger.warning(f"AgentLoop总超时({AGENT_LOOP_TIMEOUT_SECONDS}s)，强制返回当前结果")
                    agent_context.set_state(AgentState.COMPLETED)
                    return self._build_result(agent_context)

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

            self.event_emitter.emit(
                event_type="task_completed",
                step_id="final",
                step_name="任务完成",
                status="completed"
            )

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
                "session_id": context.session_id,
                "results": context.execution_results,
                "message": "任务已取消"
            }

        result_summary = ""
        if context.execution_results:
            last_result = context.execution_results[-1]
            if last_result.get("success") and last_result.get("data"):
                data = last_result["data"]
                if isinstance(data, dict):
                    result_summary = data.get("content", data.get("analysis_result", str(data)[:200]))
                else:
                    result_summary = str(data)[:200]

        if context.session_id and result_summary:
            self.session_manager.add_turn(
                user_input=context.user_input,
                assistant_response=result_summary,
                task_type=context.intent.type.value if context.intent else None,
            )

        return {
            "success": True,
            "task_id": context.task_id,
            "session_id": context.session_id,
            "results": context.execution_results,
            "message": "执行完成"
        }

    async def _phase_plan(self, context: AgentContext, conversation_history: Optional[List[Dict]] = None) -> None:
        logger.info("Phase 1: 规划开始")

        history = conversation_history or []
        intent = self.strategist_brain.understand_intent(
            user_input=context.user_input,
            context={"history": history}
        )
        context.intent = intent
        logger.info(f"意图理解完成: {intent.type.name} - {intent.goal}")

        plan = self.strategist_brain.plan(intent)
        context.plan = plan
        logger.info(f"计划制定完成: {len(plan.steps)} 个步骤")

    async def _phase_execute(self, context: AgentContext, start_step: int = 0) -> None:
        logger.info("Phase 2: 执行开始")

        if not context.plan:
            raise ValueError("没有执行计划，无法执行")

        for step in context.plan.steps[start_step:]:
            if context.cancel_requested:
                return

            context.current_step += 1
            logger.info(f"执行步骤 {context.current_step}/{len(context.plan.steps)}: {step.description}")

            self.event_emitter.emit(
                event_type="step_started",
                step_id=step.id,
                step_name=step.description,
                status="running"
            )

            step_start_time = time.time()
            result = await self._execute_step_with_retry(context, step)
            step_duration_ms = (time.time() - step_start_time) * 1000

            context.execution_results.append({
                "step_id": step.id,
                "skill_id": step.skill_id,
                "description": step.description,
                "success": result.success,
                "data": result.data,
                "error": result.error,
                "execution_time": result.execution_time
            })

            if result.success:
                self.event_emitter.emit(
                    event_type="step_completed",
                    step_id=step.id,
                    step_name=step.description,
                    status="completed",
                    duration_ms=step_duration_ms
                )
            else:
                self.event_emitter.emit(
                    event_type="step_failed",
                    step_id=step.id,
                    step_name=step.description,
                    status="failed",
                    duration_ms=step_duration_ms,
                    data={"error": result.error}
                )
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

        correction_strategy = self.reflector_brain.suggest_correction_strategy(
            evaluation=evaluation,
            execution_results=context.execution_results,
            correction_count=context.correction_count
        )

        if correction_strategy is not None:
            logger.info(f"触发自动修正: {correction_strategy.value}")
            correction_result = await self._apply_correction(context, correction_strategy)
            if correction_result:
                context.correction_count += 1
                re_eval = self.reflector_brain.evaluate_result(
                    actual_result={
                        "success": all(r.get("success", False) for r in context.execution_results),
                        "data": {
                            "results": context.execution_results,
                            "total_steps": len(context.execution_results),
                            "completed_steps": sum(1 for r in context.execution_results if r.get("success", False)),
                            "total_time": sum(r.get("execution_time", 0) for r in context.execution_results)
                        }
                    },
                    expected_intent={"goal": context.intent.goal} if context.intent else {}
                )
                logger.info(f"修正后评估: {re_eval.result.name} (质量评分: {re_eval.quality_score:.2f})")
                if re_eval.quality_score >= 0.6:
                    return NextAction(
                        action_type=NextActionType.CONTINUE,
                        reason=f"修正后质量达标(评分: {re_eval.quality_score:.2f})",
                        confidence=re_eval.quality_score
                    )

        if context.correction_count >= 2 and evaluation.quality_score < 0.6:
            logger.warning(f"修正{context.correction_count}次仍未达标，标记需人工复核")
            return NextAction(
                action_type=NextActionType.REVIEW,
                reason=f"修正{context.correction_count}次后质量仍不达标(评分: {evaluation.quality_score:.2f})",
                confidence=evaluation.quality_score
            )

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

    async def _apply_correction(self, context: AgentContext, strategy: CorrectionStrategy) -> bool:
        if strategy == CorrectionStrategy.RETRY:
            if context.plan and context.plan.steps:
                last_step = context.plan.steps[-1]
                result = await self.executor_brain.execute_step(
                    step_id=last_step.id,
                    skill_id=last_step.skill_id,
                    parameters=last_step.parameters,
                    context={"task_id": context.task_id}
                )
                if context.execution_results:
                    context.execution_results[-1] = {
                        "step_id": last_step.id,
                        "skill_id": last_step.skill_id,
                        "description": f"{last_step.description} (修正-重试)",
                        "success": result.success,
                        "data": result.data,
                        "error": result.error,
                        "execution_time": result.execution_time,
                        "correction": "retry"
                    }
                return result.success

        elif strategy == CorrectionStrategy.SEARCH_AND_RETRY:
            if context.intent:
                search_result = await self.skill_registry.execute_skill(
                    "search", query=context.intent.goal, max_results=5
                )
                if search_result.get("success") and context.plan and context.plan.steps:
                    last_step = context.plan.steps[-1]
                    enriched_params = dict(last_step.parameters or {})
                    enriched_params["data"] = search_result.get("data", {}).get("results", [])
                    result = await self.executor_brain.execute_step(
                        step_id=last_step.id,
                        skill_id=last_step.skill_id,
                        parameters=enriched_params,
                        context={"task_id": context.task_id}
                    )
                    if context.execution_results:
                        context.execution_results[-1] = {
                            "step_id": last_step.id,
                            "skill_id": last_step.skill_id,
                            "description": f"{last_step.description} (修正-补充搜索)",
                            "success": result.success,
                            "data": result.data,
                            "error": result.error,
                            "execution_time": result.execution_time,
                            "correction": "search_and_retry"
                        }
                    return result.success
            return False

        elif strategy == CorrectionStrategy.SWITCH_SKILL:
            fallback_map = {
                "analysis": "content_generation",
                "content_generation": "analysis",
                "search": "analysis",
            }
            if context.plan and context.plan.steps:
                last_step = context.plan.steps[-1]
                new_skill = fallback_map.get(last_step.skill_id)
                if new_skill:
                    result = await self.executor_brain.execute_step(
                        step_id=last_step.id,
                        skill_id=new_skill,
                        parameters=last_step.parameters,
                        context={"task_id": context.task_id}
                    )
                    if context.execution_results:
                        context.execution_results[-1] = {
                            "step_id": last_step.id,
                            "skill_id": new_skill,
                            "description": f"{last_step.description} (修正-换技能)",
                            "success": result.success,
                            "data": result.data,
                            "error": result.error,
                            "execution_time": result.execution_time,
                            "correction": "switch_skill"
                        }
                    return result.success
            return False

        elif strategy == CorrectionStrategy.DEGRADE:
            if context.plan and context.plan.steps:
                last_step = context.plan.steps[-1]
                result = await self.executor_brain.execute_step(
                    step_id=last_step.id,
                    skill_id=last_step.skill_id,
                    parameters=last_step.parameters,
                    context={"task_id": context.task_id, "degrade": True}
                )
                if context.execution_results:
                    context.execution_results[-1] = {
                        "step_id": last_step.id,
                        "skill_id": last_step.skill_id,
                        "description": f"{last_step.description} (修正-降级)",
                        "success": result.success,
                        "data": result.data,
                        "error": result.error,
                        "execution_time": result.execution_time,
                        "correction": "degrade"
                    }
                return result.success
            return False

        return False

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

        self._log_consensus_decision(context, evaluation, decision)

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

    def _log_consensus_decision(self, context: AgentContext,
                                 evaluation: Evaluation,
                                 decision) -> None:
        import json
        import os
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "consensus_logs")
        os.makedirs(log_dir, exist_ok=True)
        log_entry = {
            "task_id": context.task_id,
            "quality_score": evaluation.quality_score,
            "result_level": evaluation.result.name,
            "decision_type": decision.decision_type.name if decision.decision_type else None,
            "confidence": decision.confidence,
            "reasoning": decision.reasoning,
            "timestamp": time.time(),
        }
        log_file = os.path.join(log_dir, f"{context.task_id}.jsonl")
        try:
            with open(log_file, "a") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"共识日志写入失败: {e}")

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

    async def pause_task(self, task_id: str) -> bool:
        context = self.contexts.get(task_id)
        if not context:
            return False

        if context.state not in (AgentState.EXECUTING, AgentState.PLANNING, AgentState.OBSERVING, AgentState.REFLECTING):
            logger.warning(f"任务 {task_id} 当前状态 {context.state.value} 不可暂停")
            return False

        context.paused_at = time.time()
        context.set_state(AgentState.PAUSED)
        logger.info(f"任务已暂停: {task_id} (步骤: {context.current_step})")
        return True

    async def resume_task(self, task_id: str) -> Dict[str, Any]:
        context = self.contexts.get(task_id)
        if not context:
            return {"success": False, "error": f"任务 {task_id} 不存在"}

        if context.state != AgentState.PAUSED:
            return {"success": False, "error": f"任务 {task_id} 当前状态 {context.state.value} 不可恢复"}

        if context.paused_at and (time.time() - context.paused_at) > PAUSE_TIMEOUT_SECONDS:
            context.cancel_requested = True
            context.set_state(AgentState.CANCELLED)
            logger.warning(f"任务 {task_id} 暂停超时，自动取消")
            return {"success": False, "error": "暂停超时，任务已自动取消"}

        context.paused_at = None
        context.set_state(AgentState.EXECUTING)
        resume_step = context.current_step
        logger.info(f"任务已恢复: {task_id} (从步骤 {resume_step} 继续)")

        try:
            for reflect_round in range(self.max_reflect_rounds):
                context.set_state(AgentState.EXECUTING)
                await self._phase_execute(context, start_step=resume_step)

                if context.cancel_requested:
                    context.set_state(AgentState.CANCELLED)
                    return self._build_result(context, cancelled=True)

                context.set_state(AgentState.OBSERVING)
                await self._phase_observe(context)

                context.set_state(AgentState.REFLECTING)
                next_action = await self._phase_reflect(context)

                if next_action.action_type == NextActionType.CONTINUE:
                    break
                elif next_action.action_type == NextActionType.REVIEW:
                    break
                elif next_action.action_type == NextActionType.ABANDON:
                    context.set_state(AgentState.FAILED)
                    return {"success": False, "task_id": task_id, "error": next_action.reason}
                elif next_action.action_type in (NextActionType.RETRY, NextActionType.ADJUST_STRATEGY):
                    context.execution_results = []
                    context.current_step = 0
                    if next_action.action_type == NextActionType.ADJUST_STRATEGY:
                        context.set_state(AgentState.PLANNING)
                        await self._phase_plan(context)
                    continue

            context.set_state(AgentState.COMPLETED)
            return self._build_result(context)

        except Exception as e:
            context.set_state(AgentState.FAILED)
            logger.error(f"恢复任务执行失败: {str(e)}")
            return {"success": False, "task_id": task_id, "error": str(e)}

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
