"""
执行循环 (AgentLoop) - 负责协调三贤者的完整执行流程

这是三贤者架构的核心协调器，实现 Plan→Act→Observe→Reflect 循环：
- Plan: 策略脑制定执行计划
- Act: 执行脑执行计划
- Observe: 收集执行结果
- Reflect: 反思脑评估并决定下一步
"""

from typing import Dict, List, Optional, Any
import asyncio
import logging
import os
import time
import uuid

from .strategist_brain import StrategistBrain
from .executor_brain import ExecutorBrain, ExecutionResult
from .reflector_brain import (
    ReflectorBrain,
    NextAction,
    NextActionType,
)
from .consensus_engine import ConsensusEngine
from .skill_registry import SkillRegistry
from .tool_system import ToolSystem
from .session_context import SessionContextManager
from .task_engine_v3 import TaskEngineV3, TaskType, TaskResult
from .correction_manager import CorrectionManager
from .agent_context import AgentContext, AgentState
from .task_lifecycle import TaskLifecycleManager, ConsensusConsultant
from .utils import BoundedDict, EventEmitter
from .performance_monitor import get_performance_monitor
from .confirmer import Confirmer
from .progress_emitter import ProgressEmitter, ProgressEvent, EventType

logger = logging.getLogger(__name__)

MAX_USER_INPUT_LENGTH = 10000

MAX_RETRY_PER_STEP = int(os.environ.get("OPC_MAX_RETRY_PER_STEP", "3"))
MAX_CONTEXT_HISTORY = int(os.environ.get("OPC_MAX_CONTEXT_HISTORY", "100"))
MAX_REFLECT_ROUNDS = int(os.environ.get("OPC_MAX_REFLECT_ROUNDS", "3"))
RETRY_BACKOFF_BASE = 2
RETRY_BACKOFF_CAP = 10
PAUSE_TIMEOUT_SECONDS = int(os.environ.get("OPC_PAUSE_TIMEOUT_SECONDS", "1800"))
AGENT_LOOP_TIMEOUT_SECONDS = int(
    os.environ.get("OPC_AGENT_LOOP_TIMEOUT_SECONDS", "120")
)

QUALITY_THRESHOLD_CORRECTION = 0.6
QUALITY_THRESHOLD_CONSENSUS = 0.7
MAX_CORRECTION_ATTEMPTS = 2


class AgentLoop:

    def __init__(
        self,
        strategist_brain: StrategistBrain = None,
        executor_brain: ExecutorBrain = None,
        reflector_brain: ReflectorBrain = None,
        consensus_engine: ConsensusEngine = None,
        skill_registry: SkillRegistry = None,
        tool_system: ToolSystem = None,
        session_manager: SessionContextManager = None,
        task_engine=None,
        llm_service=None,
        max_reflect_rounds: int = MAX_REFLECT_ROUNDS,
        max_retry_per_step: int = MAX_RETRY_PER_STEP,
    ):
        self.task_engine = task_engine or TaskEngineV3()
        self.llm_service = llm_service
        self.strategist_brain = strategist_brain or StrategistBrain(
            llm_service=llm_service
        )
        self.skill_registry = skill_registry or SkillRegistry()
        self.executor_brain = executor_brain or ExecutorBrain(
            skill_registry=self.skill_registry,
            task_engine=self.task_engine,
        )
        self.reflector_brain = reflector_brain or ReflectorBrain(
            llm_service=llm_service
        )
        self.consensus_engine = consensus_engine or ConsensusEngine()
        self.tool_system = tool_system or ToolSystem()
        self.session_manager = session_manager or SessionContextManager()
        self.event_emitter = EventEmitter()
        self.confirmer = Confirmer()
        self.progress = ProgressEmitter()
        self.contexts: BoundedDict = BoundedDict(max_size=MAX_CONTEXT_HISTORY)
        self._correction_manager = CorrectionManager(
            skill_registry=self.skill_registry, executor_brain=self.executor_brain
        )
        self._lifecycle = TaskLifecycleManager(self.contexts, self.executor_brain)
        self._consensus_consultant = ConsensusConsultant(
            self.strategist_brain, self.reflector_brain, self.consensus_engine
        )

        self.max_reflect_rounds = max_reflect_rounds
        self.max_retry_per_step = max_retry_per_step

    async def run(
        self,
        user_input: str,
        context: Optional[Dict] = None,
        session_id: Optional[str] = None,
    ) -> TaskResult:
        logger.info("AgentLoop 开始执行: %s...", user_input[:50])

        if not user_input or not user_input.strip():
            return TaskResult(
                success=False,
                content="",
                task_type=TaskType.GENERAL_CHAT,
                error="用户输入不能为空",
            )

        if len(user_input) > MAX_USER_INPUT_LENGTH:
            return TaskResult(
                success=False,
                content="",
                task_type=TaskType.GENERAL_CHAT,
                error=f"用户输入超过最大长度限制({MAX_USER_INPUT_LENGTH}字符)",
            )

        time.time()
        _perf_start = time.time()

        task_id = f"agent_task_{uuid.uuid4().hex[:8]}"
        agent_context = AgentContext(
            task_id=task_id,
            user_input=user_input.strip(),
            session_id=session_id or str(uuid.uuid4()),
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
                if self.progress:
                    self.progress.emit(
                        ProgressEvent(
                            event_type=EventType.CANCELLED,
                            session_id=task_id,
                            message="任务已取消",
                        )
                    )
                return self._build_result(agent_context, cancelled=True)

            intent_type = (
                agent_context.intent.type.name if agent_context.intent else "UNKNOWN"
            )
            goal = agent_context.intent.goal if agent_context.intent else ""
            confidence = (
                getattr(agent_context.intent, "confidence", 0.85)
                if agent_context.intent
                else 0.85
            )
            confirm_result = await self.confirmer.check_confirmation(
                session_id=agent_context.session_id,
                intent_type=intent_type,
                goal=goal,
                confidence=confidence,
                params={"user_input": user_input[:200]},
            )
            if not confirm_result.confirmed and confirm_result.method != "no_callback":
                agent_context.set_state(AgentState.CONFIRMATION_NEEDED)
                return TaskResult(
                    success=False,
                    content="",
                    task_type=TaskType.GENERAL_CHAT,
                    error="需要用户确认后才能执行",
                    metadata={
                        "needs_confirmation": True,
                        "confirmation_message": (
                            confirm_result.message
                            if hasattr(confirm_result, "message")
                            else ""
                        ),
                    },
                )

            skip_reflect = os.environ.get("OPC_SKIP_REFLECT", "false").lower() == "true"

            if skip_reflect:
                agent_context.set_state(AgentState.EXECUTING)
                await self._phase_execute(agent_context)
                has_results = bool(agent_context.execution_results)
                all_failed = has_results and all(
                    not r.get("success", False) for r in agent_context.execution_results
                )
                if not has_results or all_failed:
                    agent_context.set_state(AgentState.FAILED)
                    if self.progress:
                        self.progress.emit(
                            ProgressEvent(
                                event_type=EventType.ERROR,
                                session_id=task_id,
                                message="执行步骤全部失败",
                            )
                        )
                    return self._build_result(agent_context)
                agent_context.set_state(AgentState.COMPLETED)
                if self.progress:
                    self.progress.emit(
                        ProgressEvent(
                            event_type=EventType.COMPLETE,
                            session_id=task_id,
                            message="全部完成!",
                            progress_pct=100,
                        )
                    )
                return self._build_result(agent_context)

            deadline = time.time() + AGENT_LOOP_TIMEOUT_SECONDS
            loop_result = await self._reflect_loop(agent_context, deadline=deadline)

            if loop_result is not None:
                if loop_result.get("cancelled"):
                    return self._build_result(agent_context, cancelled=True)
                loop_error = loop_result.get("error", "")
                fallback_content = (
                    loop_error or "任务执行遇到问题，请重试或换一种方式描述"
                )
                return TaskResult(
                    success=loop_result.get("success", False),
                    content=fallback_content,
                    task_type=TaskType.GENERAL_CHAT,
                    error=loop_error,
                )

            agent_context.set_state(AgentState.COMPLETED)
            logger.info("AgentLoop 执行完成: %s", task_id)

            self.event_emitter.emit(
                event_type="task_completed",
                step_id="final",
                step_name="任务完成",
                status="completed",
            )

            if self.progress:
                self.progress.emit(
                    ProgressEvent(
                        event_type=EventType.COMPLETE,
                        session_id=task_id,
                        message="全部完成!",
                        progress_pct=100,
                    )
                )

            duration_ms = (time.time() - _perf_start) * 1000
            get_performance_monitor().record("agent_loop", duration_ms, success=True)
            return self._build_result(agent_context)

        except Exception as e:
            agent_context.set_state(AgentState.FAILED)
            logger.error("AgentLoop 执行失败: %s", str(e))

            if self.progress:
                self.progress.emit(
                    ProgressEvent(
                        event_type=EventType.ERROR,
                        session_id=task_id,
                        message=f"执行失败: {str(e)}",
                        detail={"error": str(e)},
                    )
                )

            duration_ms = (time.time() - _perf_start) * 1000
            get_performance_monitor().record("agent_loop", duration_ms, success=False)
            return TaskResult(
                success=False, content="", task_type=TaskType.GENERAL_CHAT, error=str(e)
            )

    async def _reflect_loop(
        self,
        context: AgentContext,
        start_step: int = 0,
        deadline: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
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
                if self.progress:
                    self.progress.emit(
                        ProgressEvent(
                            event_type=EventType.CANCELLED,
                            session_id=context.task_id,
                            message="任务已取消",
                        )
                    )
                return {"cancelled": True}

            context.set_state(AgentState.OBSERVING)
            await self._phase_observe(context)

            context.set_state(AgentState.REFLECTING)
            next_action = await self._phase_reflect(context)

            if next_action.action_type == NextActionType.CONTINUE:
                break
            elif next_action.action_type == NextActionType.REVIEW:
                logger.info(
                    "反思轮次 %s: 需要人工复核，终止自动循环", reflect_round + 1
                )
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
            elif next_action.action_type in (
                NextActionType.RETRY,
                NextActionType.ADJUST_STRATEGY,
            ):
                logger.info(
                    "反思轮次 %s: %s，重新执行",
                    reflect_round + 1,
                    next_action.action_type.name,
                )
                context.execution_results = [
                    r for r in context.execution_results if r.get("success", False)
                ]
                context.current_step = 0
                if next_action.action_type == NextActionType.ADJUST_STRATEGY:
                    context.set_state(AgentState.PLANNING)
                    await self._phase_plan(context)
                continue
        else:
            logger.warning("反思循环已达上限 %s 次", self.max_reflect_rounds)
            if context.execution_results and not all(
                r.get("success", False) for r in context.execution_results
            ):
                context.set_state(AgentState.FAILED)
                return {
                    "success": False,
                    "task_id": context.task_id,
                    "session_id": context.session_id,
                    "results": context.execution_results,
                    "error": "反思循环已达上限，且执行结果存在失败",
                }

        return None

    def _build_result(
        self, context: AgentContext, cancelled: bool = False
    ) -> TaskResult:
        if cancelled:
            return TaskResult(
                success=False,
                content="",
                task_type=TaskType.GENERAL_CHAT,
                error="任务已取消",
            )

        results = context.execution_results
        content = ""
        sources = []
        task_type = TaskType.GENERAL_CHAT
        execution_time_ms = 0

        if results:
            last = results[-1]
            data = last.get("data", {})
            if isinstance(data, dict):
                content = data.get("content", "")
                sources = data.get("sources", [])
                tt_str = data.get("task_type", "")
                for tt in TaskType:
                    if tt.value == tt_str:
                        task_type = tt
                        break
            elif isinstance(data, str):
                content = data
            execution_time_ms = sum(r.get("execution_time", 0) for r in results) * 1000

        result_summary = ""
        if content:
            result_summary = content[:200]

        if context.session_id and result_summary:
            self.session_manager.add_turn(
                user_input=context.user_input,
                assistant_response=result_summary,
                task_type=context.intent.type.value if context.intent else None,
            )

        success = all(r.get("success", False) for r in results) if results else True

        if not content and not results:
            content = "已收到您的消息，我会尽力帮助您。"

        return TaskResult(
            success=success,
            content=content,
            task_type=task_type,
            sources=sources,
            execution_time_ms=execution_time_ms,
            error="" if success else "执行失败",
        )

    async def _phase_plan(
        self, context: AgentContext, conversation_history: Optional[List[Dict]] = None
    ) -> None:
        logger.info("Phase 1: 规划开始")

        if self.progress:
            self.progress.emit(
                ProgressEvent(
                    event_type=EventType.PLAN_START,
                    session_id=context.task_id,
                    message="正在分析你的需求...",
                )
            )

        history = conversation_history or []
        loop = asyncio.get_running_loop()

        # MemoryBridge: 注入规则约束到策略脑 context
        memory_rules = {}
        try:
            from opc_manager.memory_bridge import get_memory_bridge

            _mb = get_memory_bridge()
            if _mb.enabled:
                memory_rules = _mb.get_rules_for_context(context.user_input)
        except Exception as e:
            logger.debug("[AgentLoop] MemoryBridge 规则注入跳过: %s", e)

        plan_context = {"history": history}
        if memory_rules.get("rules_prompt"):
            plan_context["rules_prompt"] = memory_rules["rules_prompt"]
        if memory_rules.get("rules"):
            plan_context["rules"] = memory_rules["rules"]

        intent = await loop.run_in_executor(
            None,
            lambda: self.strategist_brain.understand_intent(
                user_input=context.user_input, context=plan_context
            ),
        )
        context.intent = intent
        logger.info("意图理解完成: %s - %s", intent.type.name, intent.goal)

        if self.progress:
            self.progress.emit(
                ProgressEvent(
                    event_type=EventType.INTENT_DETECTED,
                    session_id=context.task_id,
                    message=f"意图识别: {intent.type.name} - {intent.goal[:50]}",
                    detail={
                        "intent_type": intent.type.name,
                        "confidence": getattr(intent, "confidence", None),
                    },
                    progress_pct=10,
                )
            )

        plan = await loop.run_in_executor(
            None, lambda: self.strategist_brain.plan(intent)
        )
        context.plan = plan
        logger.info("计划制定完成: %s 个步骤", len(plan.steps))

    async def _phase_execute(self, context: AgentContext, start_step: int = 0) -> None:
        logger.info("Phase 2: 执行开始")

        if not context.plan:
            raise ValueError("没有执行计划，无法执行")

        total_steps = len(context.plan.steps)

        for i, step in enumerate(context.plan.steps[start_step:]):
            if context.cancel_requested:
                return

            context.current_step += 1
            logger.info(
                "执行步骤 %s/%s: %s",
                context.current_step,
                total_steps,
                step.description,
            )

            self.event_emitter.emit(
                event_type="step_started",
                step_id=step.id,
                step_name=step.description,
                status="running",
            )

            if self.progress:
                self.progress.emit(
                    ProgressEvent(
                        event_type=EventType.STEP_START,
                        session_id=context.task_id,
                        message=f"[执行脑] 执行步骤: {step.skill_id}",
                        detail={"step_id": step.id, "skill_id": step.skill_id},
                        progress_pct=int((i / total_steps) * 70) + 10,
                    )
                )

            step_start_time = time.time()
            enriched_params = self._enrich_step_parameters(
                step.parameters, context.execution_results
            )
            result = await self._execute_step_with_retry(context, step, enriched_params)
            step_duration_ms = (time.time() - step_start_time) * 1000

            context.execution_results.append(
                {
                    "step_id": step.id,
                    "skill_id": step.skill_id,
                    "description": step.description,
                    "success": result.success,
                    "data": result.data,
                    "error": result.error,
                    "execution_time": result.execution_time,
                }
            )

            if result.success:
                self.event_emitter.emit(
                    event_type="step_completed",
                    step_id=step.id,
                    step_name=step.description,
                    status="completed",
                    duration_ms=step_duration_ms,
                )

                if self.progress:
                    self.progress.emit(
                        ProgressEvent(
                            event_type=EventType.STEP_COMPLETE,
                            session_id=context.task_id,
                            message=f"✅ 步骤完成: {step.skill_id}",
                            progress_pct=int(((i + 1) / total_steps) * 70) + 10,
                        )
                    )
            else:
                self.event_emitter.emit(
                    event_type="step_failed",
                    step_id=step.id,
                    step_name=step.description,
                    status="failed",
                    duration_ms=step_duration_ms,
                    data={"error": result.error},
                )
                logger.warning(
                    "步骤 %s 执行失败（已重试%s次）: %s",
                    step.id,
                    context.step_retry_counts.get(step.id, 0),
                    result.error,
                )
                break

    def _enrich_step_parameters(
        self, params: Dict, execution_results: List[Dict]
    ) -> Dict:
        if not params or not execution_results:
            return params or {}

        enriched = dict(params)
        prev_result = execution_results[-1] if execution_results else None
        prev_data = (
            prev_result.get("data", {})
            if prev_result and prev_result.get("success")
            else None
        )

        reference_keys = {
            "input",
            "content",
            "data",
            "source",
            "search_results",
            "analysis_results",
            "generated_report",
        }
        for key in list(enriched.keys()):
            val = enriched[key]
            if isinstance(val, str) and val in reference_keys:
                if prev_data:
                    if isinstance(prev_data, dict):
                        content = prev_data.get(
                            "content",
                            prev_data.get(
                                "results", prev_data.get("analysis_result", "")
                            ),
                        )
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

    async def _execute_step_with_retry(
        self, context: AgentContext, step, enriched_params: Dict = None
    ) -> ExecutionResult:
        step_retries = context.step_retry_counts.get(step.id, 0)
        exec_params = (
            enriched_params if enriched_params is not None else step.parameters
        )

        result = await self.executor_brain.execute_step(
            step_id=step.id,
            skill_id=step.skill_id,
            parameters=exec_params,
            context={"task_id": context.task_id},
        )

        while not result.success and step_retries < self.max_retry_per_step:
            if context.cancel_requested:
                return result

            step_retries += 1
            context.step_retry_counts[step.id] = step_retries
            context.retry_count += 1
            logger.info(
                "步骤 %s 失败，重试第 %s/%s 次",
                step.id,
                step_retries,
                self.max_retry_per_step,
            )

            await asyncio.sleep(
                min(RETRY_BACKOFF_BASE**step_retries, RETRY_BACKOFF_CAP)
            )

            result = await self.executor_brain.execute_step(
                step_id=step.id,
                skill_id=step.skill_id,
                parameters=exec_params,
                context={"task_id": context.task_id},
            )

            context.execution_results.append(
                {
                    "step_id": step.id,
                    "skill_id": step.skill_id,
                    "description": f"{step.description} (重试#{step_retries})",
                    "success": result.success,
                    "data": result.data,
                    "error": result.error,
                    "execution_time": result.execution_time,
                    "retry": step_retries,
                }
            )

        context.step_retry_counts[step.id] = step_retries
        return result

    async def _phase_observe(self, context: AgentContext) -> None:
        logger.info("Phase 3: 观察开始")

        total_steps = len(context.plan.steps) if context.plan else 0
        completed_steps = sum(
            1 for r in context.execution_results if r.get("success", False)
        )
        total_time = sum(r.get("execution_time", 0) for r in context.execution_results)

        logger.info(
            "执行结果汇总: %s/%s 步骤完成，总耗时: %.2f秒",
            completed_steps,
            total_steps,
            total_time,
        )

    def _build_overall_result(self, context: AgentContext) -> Dict[str, Any]:
        return {
            "success": all(r.get("success", False) for r in context.execution_results),
            "data": {
                "results": context.execution_results,
                "total_steps": len(context.execution_results),
                "completed_steps": sum(
                    1 for r in context.execution_results if r.get("success", False)
                ),
                "total_time": sum(
                    r.get("execution_time", 0) for r in context.execution_results
                ),
            },
        }

    async def _phase_reflect(self, context: AgentContext) -> NextAction:
        logger.info("Phase 4: 反思开始")

        if self.progress:
            self.progress.emit(
                ProgressEvent(
                    event_type=EventType.REFLECT_START,
                    session_id=context.task_id,
                    message="[反思脑] 正在评估执行结果...",
                    progress_pct=85,
                )
            )

        overall_result = self._build_overall_result(context)

        loop = asyncio.get_running_loop()
        expected_intent = {"goal": context.intent.goal} if context.intent else {}

        evaluation = await loop.run_in_executor(
            None,
            lambda: self.reflector_brain.evaluate_result(
                actual_result=overall_result, expected_intent=expected_intent
            ),
        )

        logger.info(
            "评估结果: %s (质量评分: %.2f)",
            evaluation.result.name,
            evaluation.quality_score,
        )

        # MemoryBridge: 质量不佳时记录失败经验
        if evaluation.quality_score < 0.5:
            try:
                from opc_manager.memory_bridge import get_memory_bridge

                _mb = get_memory_bridge()
                if _mb.enabled:
                    _mb.record_failure(
                        user_input=context.user_input,
                        failure_reason=str(evaluation.deviation_analysis or "")[:200],
                        quality_score=evaluation.quality_score,
                    )
            except Exception as e:
                logger.debug("[AgentLoop] MemoryBridge 失败经验记录跳过: %s", e)

        correction_strategy = await loop.run_in_executor(
            None,
            lambda: self.reflector_brain.suggest_correction_strategy(
                evaluation=evaluation,
                execution_results=context.execution_results,
                correction_count=context.correction_count,
            ),
        )

        if correction_strategy is not None:
            logger.info("触发自动修正: %s", correction_strategy.value)
            correction_result = await self._correction_manager.apply_correction(
                context, correction_strategy
            )
            if correction_result:
                context.correction_count += 1
                re_eval_data = self._build_overall_result(context)
                re_eval = await loop.run_in_executor(
                    None,
                    lambda: self.reflector_brain.evaluate_result(
                        actual_result=re_eval_data, expected_intent=expected_intent
                    ),
                )
                logger.info(
                    "修正后评估: %s (质量评分: %.2f)",
                    re_eval.result.name,
                    re_eval.quality_score,
                )
                if re_eval.quality_score >= QUALITY_THRESHOLD_CORRECTION:
                    return NextAction(
                        action_type=NextActionType.CONTINUE,
                        reason=f"修正后质量达标(评分: {re_eval.quality_score:.2f})",
                        confidence=re_eval.quality_score,
                    )

        if (
            context.correction_count >= MAX_CORRECTION_ATTEMPTS
            and evaluation.quality_score < QUALITY_THRESHOLD_CORRECTION
        ):
            logger.warning("修正%s次仍未达标，标记需人工复核", context.correction_count)
            return NextAction(
                action_type=NextActionType.REVIEW,
                reason=f"修正{context.correction_count}次后质量仍不达标(评分: {evaluation.quality_score:.2f})",
                confidence=evaluation.quality_score,
            )

        plan_dict = None
        if context.plan:
            plan_dict = {
                "steps": [
                    {"id": s.id, "skill_id": s.skill_id, "description": s.description}
                    for s in context.plan.steps
                ],
                "retry_count": context.retry_count,
            }

        next_action = await loop.run_in_executor(
            None,
            lambda: self.reflector_brain.decide_next_action(
                evaluation=evaluation, plan=plan_dict
            ),
        )

        consensus_decision = await self._consensus_consultant.consult(
            context, evaluation, next_action
        )
        if consensus_decision is not None:
            return consensus_decision

        logger.info("决定下一步行动: %s", next_action.action_type.name)
        return next_action

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._lifecycle.get_task_status(task_id)

    async def cancel_task(self, task_id: str) -> bool:
        return await self._lifecycle.cancel_task(task_id)

    async def pause_task(self, task_id: str) -> bool:
        return await self._lifecycle.pause_task(task_id)

    async def resume_task(self, task_id: str) -> Dict[str, Any]:
        result = await self._lifecycle.resume_task(task_id)
        if not result.get("success"):
            return result

        # If resume succeeded, continue the reflect loop
        context = self.contexts.get(task_id)
        if not context:
            return result

        resume_step = result.pop("resume_step", context.current_step)
        deadline = time.time() + AGENT_LOOP_TIMEOUT_SECONDS

        try:
            loop_result = await self._reflect_loop(
                context, start_step=resume_step, deadline=deadline
            )

            if loop_result is not None:
                if loop_result.get("cancelled"):
                    return self._build_result(context, cancelled=True)
                loop_error = loop_result.get("error", "")
                fallback_content = loop_error or "任务恢复执行遇到问题，请重试"
                return TaskResult(
                    success=loop_result.get("success", False),
                    content=fallback_content,
                    task_type=TaskType.GENERAL_CHAT,
                    error=loop_error,
                )

            context.set_state(AgentState.COMPLETED)
            return self._build_result(context)

        except Exception as e:
            context.set_state(AgentState.FAILED)
            logger.error("恢复任务执行失败: %s", str(e))
            return {"success": False, "task_id": task_id, "error": str(e)}

    def list_tasks(self) -> List[Dict[str, Any]]:
        return self._lifecycle.list_tasks()

    def to_dict(self) -> Dict[str, Any]:
        return self._lifecycle.to_dict()
