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
import json
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
from .performance_monitor import get_performance_monitor

logger = logging.getLogger(__name__)

MAX_USER_INPUT_LENGTH = 10000

MAX_RETRY_PER_STEP = int(os.environ.get("OPC_MAX_RETRY_PER_STEP", "3"))
MAX_CONTEXT_HISTORY = int(os.environ.get("OPC_MAX_CONTEXT_HISTORY", "100"))
MAX_REFLECT_ROUNDS = int(os.environ.get("OPC_MAX_REFLECT_ROUNDS", "3"))
RETRY_BACKOFF_BASE = 2
RETRY_BACKOFF_CAP = 10
PAUSE_TIMEOUT_SECONDS = int(os.environ.get("OPC_PAUSE_TIMEOUT_SECONDS", "1800"))
AGENT_LOOP_TIMEOUT_SECONDS = int(os.environ.get("OPC_AGENT_LOOP_TIMEOUT_SECONDS", "60"))

QUALITY_THRESHOLD_CORRECTION = 0.6
QUALITY_THRESHOLD_CONSENSUS = 0.7
QUALITY_THRESHOLD_CONFIDENCE = 0.5
QUALITY_THRESHOLD_LOW = 0.3
MAX_CORRECTION_ATTEMPTS = 2


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
                 llm_service=None,
                 max_reflect_rounds: int = MAX_REFLECT_ROUNDS,
                 max_retry_per_step: int = MAX_RETRY_PER_STEP):
        self.task_engine_adapter = task_engine_adapter or TaskEngineAdapter()
        self.llm_service = llm_service
        self.strategist_brain = strategist_brain or StrategistBrain(llm_service=llm_service)
        self.skill_registry = skill_registry or SkillRegistry()
        self.executor_brain = executor_brain or ExecutorBrain(skill_registry=self.skill_registry, task_engine_adapter=self.task_engine_adapter)
        self.reflector_brain = reflector_brain or ReflectorBrain(llm_service=llm_service)
        self.consensus_engine = consensus_engine or ConsensusEngine()
        self.tool_system = tool_system or ToolSystem()
        self.session_manager = session_manager or SessionContextManager()
        self.event_emitter = EventEmitter()

        self.max_reflect_rounds = max_reflect_rounds
        self.max_retry_per_step = max_retry_per_step

        self.contexts: BoundedDict = BoundedDict(max_size=MAX_CONTEXT_HISTORY)

    async def run(self, user_input: str, context: Optional[Dict] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        logger.info("AgentLoop 开始执行: %s...", user_input[:50])

        if not user_input or not user_input.strip():
            return {"success": False, "error": "用户输入不能为空", "message": "输入无效"}

        if len(user_input) > MAX_USER_INPUT_LENGTH:
            return {"success": False, "error": f"用户输入超过最大长度限制({MAX_USER_INPUT_LENGTH}字符)", "message": "输入过长"}

        run_start_time = time.time()
        _perf_start = time.time()

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

            deadline = time.time() + AGENT_LOOP_TIMEOUT_SECONDS
            loop_result = await self._reflect_loop(agent_context, deadline=deadline)

            if loop_result is not None:
                if loop_result.get("cancelled"):
                    return self._build_result(agent_context, cancelled=True)
                return loop_result

            agent_context.set_state(AgentState.COMPLETED)
            logger.info("AgentLoop 执行完成: %s", task_id)

            self.event_emitter.emit(
                event_type="task_completed",
                step_id="final",
                step_name="任务完成",
                status="completed"
            )

            duration_ms = (time.time() - _perf_start) * 1000
            get_performance_monitor().record("agent_loop", duration_ms, success=True)
            return self._build_result(agent_context)

        except Exception as e:
            agent_context.set_state(AgentState.FAILED)
            logger.error("AgentLoop 执行失败: %s", str(e))
            duration_ms = (time.time() - _perf_start) * 1000
            get_performance_monitor().record("agent_loop", duration_ms, success=False)
            return {
                "success": False,
                "task_id": task_id,
                "session_id": agent_context.session_id,
                "error": str(e),
                "message": "执行失败"
            }

    async def _reflect_loop(self, context: AgentContext,
                            start_step: int = 0,
                            deadline: Optional[float] = None) -> Optional[Dict[str, Any]]:
        for reflect_round in range(self.max_reflect_rounds):
            if deadline and time.time() > deadline:
                logger.warning("AgentLoop总超时，强制返回当前结果")
                context.set_state(AgentState.COMPLETED)
                return None

            context.set_state(AgentState.EXECUTING)
            await self._phase_execute(context, start_step=start_step)
            start_step = 0

            if context.cancel_requested:
                context.set_state(AgentState.CANCELLED)
                return {"cancelled": True}

            context.set_state(AgentState.OBSERVING)
            await self._phase_observe(context)

            context.set_state(AgentState.REFLECTING)
            next_action = await self._phase_reflect(context)

            if next_action.action_type == NextActionType.CONTINUE:
                break
            elif next_action.action_type == NextActionType.REVIEW:
                logger.info("反思轮次 %s: 需要人工复核，终止自动循环", reflect_round + 1)
                break
            elif next_action.action_type == NextActionType.ABANDON:
                context.set_state(AgentState.FAILED)
                return {
                    "success": False,
                    "task_id": context.task_id,
                    "session_id": context.session_id,
                    "results": context.execution_results,
                    "error": next_action.reason,
                    "message": "任务放弃",
                }
            elif next_action.action_type in (NextActionType.RETRY, NextActionType.ADJUST_STRATEGY):
                logger.info("反思轮次 %s: %s，重新执行", reflect_round + 1, next_action.action_type.name)
                context.execution_results = []
                context.current_step = 0
                if next_action.action_type == NextActionType.ADJUST_STRATEGY:
                    context.set_state(AgentState.PLANNING)
                    await self._phase_plan(context)
                continue
        else:
            logger.warning("反思循环已达上限 %s 次", self.max_reflect_rounds)

        return None

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
        loop = asyncio.get_running_loop()

        intent = await loop.run_in_executor(
            None,
            lambda: self.strategist_brain.understand_intent(
                user_input=context.user_input,
                context={"history": history}
            )
        )
        context.intent = intent
        logger.info("意图理解完成: %s - %s", intent.type.name, intent.goal)

        plan = await loop.run_in_executor(
            None,
            lambda: self.strategist_brain.plan(intent)
        )
        context.plan = plan
        logger.info("计划制定完成: %s 个步骤", len(plan.steps))

    async def _phase_execute(self, context: AgentContext, start_step: int = 0) -> None:
        logger.info("Phase 2: 执行开始")

        if not context.plan:
            raise ValueError("没有执行计划，无法执行")

        for step in context.plan.steps[start_step:]:
            if context.cancel_requested:
                return

            context.current_step += 1
            logger.info("执行步骤 %s/%s: %s", context.current_step, len(context.plan.steps), step.description)

            self.event_emitter.emit(
                event_type="step_started",
                step_id=step.id,
                step_name=step.description,
                status="running"
            )

            step_start_time = time.time()
            enriched_params = self._enrich_step_parameters(step.parameters, context.execution_results)
            result = await self._execute_step_with_retry(context, step, enriched_params)
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
                logger.warning("步骤 %s 执行失败（已重试%s次）: %s", step.id, context.step_retry_counts.get(step.id, 0), result.error)
                break

    def _enrich_step_parameters(self, params: Dict, execution_results: List[Dict]) -> Dict:
        if not params or not execution_results:
            return params or {}

        enriched = dict(params)
        prev_result = execution_results[-1] if execution_results else None
        prev_data = prev_result.get("data", {}) if prev_result and prev_result.get("success") else None

        reference_keys = {"input", "content", "data", "source", "search_results", "analysis_results", "generated_report"}
        for key in list(enriched.keys()):
            val = enriched[key]
            if isinstance(val, str) and val in reference_keys:
                if prev_data:
                    if isinstance(prev_data, dict):
                        content = prev_data.get("content", prev_data.get("results", prev_data.get("analysis_result", "")))
                        if content:
                            if isinstance(content, list):
                                enriched[key] = str(content)[:500]
                            else:
                                enriched[key] = str(content)[:500]
                    elif isinstance(prev_data, str):
                        enriched[key] = prev_data[:500]
                else:
                    enriched[key] = ""

        if "data" not in enriched and prev_data is not None:
            enriched["data"] = prev_data

        if enriched.get("query") and len(str(enriched["query"])) > 200:
            enriched["query"] = str(enriched["query"])[:200]

        return enriched

    async def _execute_step_with_retry(self, context: AgentContext, step, enriched_params: Dict = None) -> ExecutionResult:
        step_retries = context.step_retry_counts.get(step.id, 0)
        exec_params = enriched_params if enriched_params is not None else step.parameters

        result = await self.executor_brain.execute_step(
            step_id=step.id,
            skill_id=step.skill_id,
            parameters=exec_params,
            context={"task_id": context.task_id}
        )

        while not result.success and step_retries < self.max_retry_per_step:
            if context.cancel_requested:
                return result

            step_retries += 1
            context.step_retry_counts[step.id] = step_retries
            context.retry_count += 1
            logger.info("步骤 %s 失败，重试第 %s/%s 次", step.id, step_retries, self.max_retry_per_step)

            await asyncio.sleep(min(RETRY_BACKOFF_BASE ** step_retries, RETRY_BACKOFF_CAP))

            result = await self.executor_brain.execute_step(
                step_id=step.id,
                skill_id=step.skill_id,
                parameters=exec_params,
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

        logger.info("执行结果汇总: %s/%s 步骤完成，总耗时: %.2f秒", completed_steps, total_steps, total_time)

    def _build_overall_result(self, context: AgentContext) -> Dict[str, Any]:
        return {
            "success": all(r.get("success", False) for r in context.execution_results),
            "data": {
                "results": context.execution_results,
                "total_steps": len(context.execution_results),
                "completed_steps": sum(1 for r in context.execution_results if r.get("success", False)),
                "total_time": sum(r.get("execution_time", 0) for r in context.execution_results)
            }
        }

    async def _phase_reflect(self, context: AgentContext) -> NextAction:
        logger.info("Phase 4: 反思开始")

        overall_result = self._build_overall_result(context)

        loop = asyncio.get_running_loop()
        expected_intent = {"goal": context.intent.goal} if context.intent else {}

        evaluation = await loop.run_in_executor(
            None,
            lambda: self.reflector_brain.evaluate_result(
                actual_result=overall_result,
                expected_intent=expected_intent
            )
        )

        logger.info("评估结果: %s (质量评分: %.2f)", evaluation.result.name, evaluation.quality_score)

        correction_strategy = await loop.run_in_executor(
            None,
            lambda: self.reflector_brain.suggest_correction_strategy(
                evaluation=evaluation,
                execution_results=context.execution_results,
                correction_count=context.correction_count
            )
        )

        if correction_strategy is not None:
            logger.info("触发自动修正: %s", correction_strategy.value)
            correction_result = await self._apply_correction(context, correction_strategy)
            if correction_result:
                context.correction_count += 1
                re_eval_data = self._build_overall_result(context)
                re_eval = await loop.run_in_executor(
                    None,
                    lambda: self.reflector_brain.evaluate_result(
                        actual_result=re_eval_data,
                        expected_intent=expected_intent
                    )
                )
                logger.info("修正后评估: %s (质量评分: %.2f)", re_eval.result.name, re_eval.quality_score)
                if re_eval.quality_score >= QUALITY_THRESHOLD_CORRECTION:
                    return NextAction(
                        action_type=NextActionType.CONTINUE,
                        reason=f"修正后质量达标(评分: {re_eval.quality_score:.2f})",
                        confidence=re_eval.quality_score
                    )

        if context.correction_count >= MAX_CORRECTION_ATTEMPTS and evaluation.quality_score < QUALITY_THRESHOLD_CORRECTION:
            logger.warning("修正%s次仍未达标，标记需人工复核", context.correction_count)
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

        next_action = await loop.run_in_executor(
            None,
            lambda: self.reflector_brain.decide_next_action(
                evaluation=evaluation,
                plan=plan_dict
            )
        )

        consensus_decision = await self._consult_consensus(context, evaluation, next_action)
        if consensus_decision is not None:
            return consensus_decision

        logger.info("决定下一步行动: %s", next_action.action_type.name)
        return next_action

    def _make_step_result(self, step, result: ExecutionResult,
                          description_suffix: str = "",
                          correction_tag: str = "") -> Dict[str, Any]:
        return {
            "step_id": step.id,
            "skill_id": result.data.get("skill_id", step.skill_id) if isinstance(result.data, dict) and "skill_id" in result.data else step.skill_id,
            "description": f"{step.description}{description_suffix}",
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "execution_time": result.execution_time,
            **({"correction": correction_tag} if correction_tag else {}),
        }

    SKILL_FALLBACK_MAP = {
        "analysis": "content_generation",
        "content_generation": "analysis",
        "search": "analysis",
    }

    async def _apply_correction(self, context: AgentContext, strategy: CorrectionStrategy) -> bool:
        if not context.plan or not context.plan.steps:
            return False

        handler = {
            CorrectionStrategy.RETRY: self._correct_retry,
            CorrectionStrategy.SEARCH_AND_RETRY: self._correct_search_and_retry,
            CorrectionStrategy.SWITCH_SKILL: self._correct_switch_skill,
            CorrectionStrategy.DEGRADE: self._correct_degrade,
        }.get(strategy)

        if handler is None:
            return False
        return await handler(context)

    async def _correct_retry(self, context: AgentContext) -> bool:
        last_step = context.plan.steps[-1]
        result = await self.executor_brain.execute_step(
            step_id=last_step.id,
            skill_id=last_step.skill_id,
            parameters=last_step.parameters,
            context={"task_id": context.task_id}
        )
        if context.execution_results:
            context.execution_results[-1] = self._make_step_result(
                last_step, result, " (修正-重试)", "retry"
            )
        return result.success

    async def _correct_search_and_retry(self, context: AgentContext) -> bool:
        if not context.intent:
            return False
        last_step = context.plan.steps[-1]
        search_result = await self.skill_registry.execute_skill(
            "search", query=context.intent.goal, max_results=5
        )
        if not search_result.get("success"):
            return False
        enriched_params = dict(last_step.parameters or {})
        enriched_params["data"] = search_result.get("data", {}).get("results", [])
        result = await self.executor_brain.execute_step(
            step_id=last_step.id,
            skill_id=last_step.skill_id,
            parameters=enriched_params,
            context={"task_id": context.task_id}
        )
        if context.execution_results:
            context.execution_results[-1] = self._make_step_result(
                last_step, result, " (修正-补充搜索)", "search_and_retry"
            )
        return result.success

    async def _correct_switch_skill(self, context: AgentContext) -> bool:
        last_step = context.plan.steps[-1]
        new_skill = self.SKILL_FALLBACK_MAP.get(last_step.skill_id)
        if not new_skill:
            return False
        result = await self.executor_brain.execute_step(
            step_id=last_step.id,
            skill_id=new_skill,
            parameters=last_step.parameters,
            context={"task_id": context.task_id}
        )
        if context.execution_results:
            step_result = self._make_step_result(
                last_step, result, " (修正-换技能)", "switch_skill"
            )
            step_result["skill_id"] = new_skill
            context.execution_results[-1] = step_result
        return result.success

    async def _correct_degrade(self, context: AgentContext) -> bool:
        last_step = context.plan.steps[-1]
        result = await self.executor_brain.execute_step(
            step_id=last_step.id,
            skill_id=last_step.skill_id,
            parameters=last_step.parameters,
            context={"task_id": context.task_id, "degrade": True}
        )
        if context.execution_results:
            context.execution_results[-1] = self._make_step_result(
                last_step, result, " (修正-降级)", "degrade"
            )
        return result.success

    async def _consult_consensus(self, context: AgentContext,
                           evaluation: Evaluation,
                           reflector_action: NextAction) -> Optional[NextAction]:
        if evaluation.quality_score >= QUALITY_THRESHOLD_CONSENSUS:
            return None

        strategist_ctx = {"intent": context.intent}
        strategist_data = self.strategist_brain.express_opinion(strategist_ctx)
        strategist_opinion = Opinion(
            brain_type=strategist_data["brain_type"],
            opinion_type=OpinionType[strategist_data["opinion_type"]],
            reasoning=strategist_data["reasoning"],
            confidence=strategist_data["confidence"],
        )

        executor_opinion = Opinion(
            brain_type="executor",
            opinion_type=OpinionType.AGREE if context.retry_count < 2 else OpinionType.DISAGREE,
            reasoning=f"执行重试次数: {context.retry_count}",
            confidence=max(0.3, 1.0 - context.retry_count * 0.3),
        )

        reflector_ctx = {"evaluation": evaluation, "next_action": reflector_action}
        reflector_data = self.reflector_brain.express_opinion(reflector_ctx)
        reflector_opinion = Opinion(
            brain_type=reflector_data["brain_type"],
            opinion_type=OpinionType[reflector_data["opinion_type"]],
            reasoning=reflector_data["reasoning"],
            confidence=reflector_data["confidence"],
        )

        decision = self.consensus_engine.collect_opinions([
            strategist_opinion,
            executor_opinion,
            reflector_opinion
        ])

        await self._log_consensus_decision(context, evaluation, decision)

        if decision.decision_type == DecisionType.VETOED:
            logger.info("共识引擎否决: %s", decision.reasoning)
            return NextAction(
                action_type=NextActionType.ABANDON,
                reason=decision.reasoning,
                confidence=decision.confidence
            )

        if decision.decision_type == DecisionType.ESCALATED:
            logger.info("共识引擎升级: %s", decision.reasoning)
            return NextAction(
                action_type=NextActionType.REVIEW,
                reason=decision.reasoning,
                confidence=decision.confidence
            )

        return None

    async def _log_consensus_decision(self, context: AgentContext,
                                       evaluation: Evaluation,
                                       decision) -> None:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "consensus_logs")
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

        def _write_log():
            os.makedirs(log_dir, exist_ok=True)
            with open(log_file, "a") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _write_log)
        except Exception as e:
            logger.warning("共识日志写入失败: %s", e)

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
        logger.info("任务已取消: %s", task_id)
        return True

    async def pause_task(self, task_id: str) -> bool:
        context = self.contexts.get(task_id)
        if not context:
            return False

        if context.state not in (AgentState.EXECUTING, AgentState.PLANNING, AgentState.OBSERVING, AgentState.REFLECTING):
            logger.warning("任务 %s 当前状态 %s 不可暂停", task_id, context.state.value)
            return False

        context.paused_at = time.time()
        context.set_state(AgentState.PAUSED)
        logger.info("任务已暂停: %s (步骤: %s)", task_id, context.current_step)
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
            logger.warning("任务 %s 暂停超时，自动取消", task_id)
            return {"success": False, "error": "暂停超时，任务已自动取消"}

        context.paused_at = None
        context.set_state(AgentState.EXECUTING)
        resume_step = context.current_step
        logger.info("任务已恢复: %s (从步骤 %s 继续)", task_id, resume_step)

        try:
            loop_result = await self._reflect_loop(context, start_step=resume_step)

            if loop_result is not None:
                if loop_result.get("cancelled"):
                    return self._build_result(context, cancelled=True)
                return loop_result

            context.set_state(AgentState.COMPLETED)
            return self._build_result(context)

        except Exception as e:
            context.set_state(AgentState.FAILED)
            logger.error("恢复任务执行失败: %s", str(e))
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
