"""TaskOrchestrator — 任务编排组件

从AgentLoop提取的任务编排职责，负责：
- 意图分类和路由
- 执行阶段编排（Plan→Act→Observe→Reflect）
- 反思循环管理
- 重试和策略调整

重构目标：将任务编排逻辑从AgentLoop中分离，使AgentLoop成为轻量级协调器。
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .agent_context import AgentContext, AgentState
from .intent_classifier import IntentRouter, IntentCategory
from .reflector_brain import NextAction, NextActionType
from .task_engine_v3 import TaskType, TaskResult
from .result_builder import ResultBuilder
from .progress_tracker import ProgressTracker
from .error_handler_component import ErrorHandler

logger = logging.getLogger(__name__)

AGENT_LOOP_TIMEOUT_SECONDS = int(
    os.environ.get("OPC_AGENT_LOOP_TIMEOUT_SECONDS", "120")
)


@dataclass
class RouteDecision:
    """路由决策结果。"""

    is_greeting: bool = False
    is_simple: bool = False
    response: str = ""
    confidence: float = 0.0


class TaskOrchestrator:
    """任务编排器。

    职责：
    - 意图分类和路由决策
    - 编排Plan→Act→Observe→Reflect执行流程
    - 管理反思循环和重试逻辑
    - 协调各阶段之间的数据传递

    设计原则：
    - 编排逻辑集中管理，与状态管理和结果构建分离
    - 支持灵活的执行策略
    - 保持与原有行为的完全兼容
    """

    def __init__(
        self,
        strategist_brain,
        executor_brain,
        reflector_brain,
        consensus_consultant,
        correction_manager,
        result_builder: ResultBuilder,
        progress_tracker: ProgressTracker,
        max_reflect_rounds: int = 3,
        max_retry_per_step: int = 3,
    ):
        """初始化任务编排器。

        Args:
            strategist_brain: 策略脑
            executor_brain: 执行脑
            reflector_brain: 反思脑
            consensus_consultant: 共识顾问
            correction_manager: 修正管理器
            result_builder: 结果构建器
            progress_tracker: 进度跟踪器
            max_reflect_rounds: 最大反思轮次
            max_retry_per_step: 每步最大重试次数
        """
        self.strategist_brain = strategist_brain
        self.executor_brain = executor_brain
        self.reflector_brain = reflector_brain
        self._consensus_consultant = consensus_consultant
        self._correction_manager = correction_manager
        self._result_builder = result_builder
        self._progress = progress_tracker
        self.max_reflect_rounds = max_reflect_rounds
        self.max_retry_per_step = max_retry_per_step

    def determine_route(self, user_input: str) -> RouteDecision:
        """确定任务路由。

        Args:
            user_input: 用户输入

        Returns:
            RouteDecision: 路由决策
        """
        category, confidence = IntentRouter.classify_route(user_input)

        if category == IntentCategory.GREETING:
            return RouteDecision(
                is_greeting=True,
                response=self._generate_greeting_response(user_input),
                confidence=confidence,
            )

        if category == IntentCategory.SIMPLE:
            return RouteDecision(
                is_simple=True,
                confidence=confidence,
            )

        return RouteDecision(confidence=confidence)

    def _generate_greeting_response(self, user_input: str) -> str:
        """生成问候响应（0 LLM成本，基于关键词模板）。"""
        text = user_input.lower()
        if any(w in text for w in ["你好", "您好", "hi", "hello", "嗨", "哈喽"]):
            return (
                "你好！我是 OPC-Agents 助手。我可以帮你：\n"
                "- 发送邮件\n- 记录收支\n- 生成报告\n\n"
                "请告诉我你需要什么帮助？"
            )
        if any(w in text for w in ["谢谢", "感谢", "thanks"]):
            return "不客气！还有其他需要帮助的吗？"
        if any(w in text for w in ["再见", "bye", "拜拜"]):
            return "再见！有需要随时找我。"
        if any(w in text for w in ["帮助", "help", "怎么用"]):
            return (
                "我可以帮你：\n"
                "1. 发送邮件（如：发邮件给张总）\n"
                "2. 记录收支（如：记一笔收入3000元）\n"
                "3. 生成报告（如：生成本月经营报告）\n\n"
                "直接用自然语言告诉我你的需求即可。"
            )
        return "你好，有什么可以帮你的吗？"

    async def execute_plan_phase(
        self,
        context: AgentContext,
        conversation_history: Optional[List[Dict]] = None,
    ) -> None:
        """执行规划阶段。

        Args:
            context: Agent上下文
            conversation_history: 对话历史
        """
        logger.info("Phase 1: 规划开始")
        self._progress.emit_plan_start(context.task_id)

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
            logger.debug("[TaskOrchestrator] MemoryBridge 规则注入跳过: %s", e)

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

        self._progress.emit_intent_detected(
            context.task_id,
            intent.type.name,
            intent.goal,
            getattr(intent, "confidence", None),
        )

        plan = await loop.run_in_executor(
            None, lambda: self.strategist_brain.plan(intent)
        )
        context.plan = plan
        logger.info("计划制定完成: %s 个步骤", len(plan.steps))

    async def execute_execute_phase(
        self, context: AgentContext, start_step: int = 0
    ) -> None:
        """执行执行阶段。

        Args:
            context: Agent上下文
            start_step: 起始步骤索引
        """
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

            self._progress.emit_step_start(
                context.task_id, step.id, step.skill_id, i, total_steps
            )

            # 关键决策点前置共识检查
            try:
                if self._is_critical_decision_point(context, step):
                    decision = await self._parallel_consensus(
                        context, "execute_step", step
                    )
                    if not decision.approved:
                        logger.info("关键决策点被三贤者否决: %s", decision.reasoning)
                        context.execution_results.append(
                            {
                                "step_id": step.id,
                                "skill_id": step.skill_id,
                                "description": step.description,
                                "success": False,
                                "data": None,
                                "error": f"consensus_veto: {decision.reasoning}",
                                "execution_time": 0,
                            }
                        )
                        continue
            except Exception as e:
                logger.error("关键决策点共识检查失败，fail-close 跳过步骤: %s", e)
                context.execution_results.append(
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
                continue

            step_start_time = time.time()
            enriched_params = self._enrich_step_parameters(
                step.parameters, context.execution_results
            )
            result = await self._execute_step_with_retry(context, step, enriched_params)

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
                self._progress.emit_step_complete(
                    context.task_id, step.skill_id, i, total_steps
                )
            else:
                logger.warning(
                    "步骤 %s 执行失败（已重试%s次）: %s",
                    step.id,
                    context.step_retry_counts.get(step.id, 0),
                    result.error,
                )
                break

    async def execute_observe_phase(self, context: AgentContext) -> None:
        """执行观察阶段。

        Args:
            context: Agent上下文
        """
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

    async def execute_reflect_phase(self, context: AgentContext) -> NextAction:
        """执行反思阶段。

        Args:
            context: Agent上下文

        Returns:
            NextAction: 下一步行动决策
        """
        logger.info("Phase 4: 反思开始")
        self._progress.emit_reflect_start(context.task_id)

        overall_result = self._result_builder.build_overall_result(context)

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
                logger.debug("[TaskOrchestrator] MemoryBridge 失败经验记录跳过: %s", e)

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
                re_eval_data = self._result_builder.build_overall_result(context)
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
                if re_eval.quality_score >= 0.6:  # QUALITY_THRESHOLD_CORRECTION
                    return NextAction(
                        action_type=NextActionType.CONTINUE,
                        reason=f"修正后质量达标(评分: {re_eval.quality_score:.2f})",
                        confidence=re_eval.quality_score,
                    )

        if (
            context.correction_count >= 2  # MAX_CORRECTION_ATTEMPTS
            and evaluation.quality_score < 0.6
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

    async def run_reflect_loop(
        self,
        context: AgentContext,
        deadline: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """运行反思循环。

        Args:
            context: Agent上下文
            deadline: 超时时间戳

        Returns:
            Optional[Dict]: 循环结果（None表示正常完成）
        """
        for reflect_round in range(self.max_reflect_rounds):
            if deadline and time.time() > deadline:
                logger.warning("AgentLoop总超时，强制返回当前结果")
                context.set_state(AgentState.COMPLETED)
                return None

            context.set_state(AgentState.EXECUTING)
            await self.execute_execute_phase(context)
            start_step = 0

            if context.cancel_requested:
                context.set_state(AgentState.CANCELLED)
                self._progress.emit_cancelled(context.task_id)
                return {"cancelled": True}

            context.set_state(AgentState.OBSERVING)
            await self.execute_observe_phase(context)

            context.set_state(AgentState.REFLECTING)
            next_action = await self.execute_reflect_phase(context)

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
                    await self.execute_plan_phase(context)
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

    # 以下方法从AgentLoop迁移，保持原有逻辑
    # 这些是执行阶段所需的辅助方法

    def _is_critical_decision_point(self, context, step=None) -> bool:
        """判断当前是否为关键决策点。"""
        from .agent_loop import CRITICAL_DECISION_SKILLS, CRITICAL_DECISION_ACTIONS

        if isinstance(context, dict):
            metadata = context.get("metadata", {}) or {}
        else:
            metadata = getattr(context, "metadata", None) or {}
        if isinstance(metadata, dict) and metadata.get("route_category") == "simple":
            return False

        if step is None:
            if not isinstance(context, dict):
                current_step_idx = getattr(context, "current_step", 0)
                plan = getattr(context, "plan", None)
                steps = getattr(plan, "steps", None) if plan else None
                if steps and 0 < current_step_idx <= len(steps):
                    step = steps[current_step_idx - 1]
        if not step:
            return False
        skill_id = (getattr(step, "skill_id", "") or "").lower()
        action = (getattr(step, "action", "") or "").lower()
        return (
            skill_id in CRITICAL_DECISION_SKILLS or action in CRITICAL_DECISION_ACTIONS
        )

    async def _parallel_consensus(self, context, decision_point: str, step=None):
        """三贤者并行投票决策。"""
        from .agent_loop import (
            PARALLEL_VOTE_ENABLED,
            PARALLEL_VOTE_TIMEOUT,
        )

        if not PARALLEL_VOTE_ENABLED:
            return await self._serial_consensus_fallback(context, decision_point, step)
        try:
            from .agent_loop import AgentLoop

            context_dict = AgentLoop._context_to_dict(context)
            planned_action = AgentLoop._extract_planned_action(context, step)

            from .consensus_engine import Opinion, OpinionType

            decision = await asyncio.wait_for(
                self._consensus_consultant._consensus.collect_opinions_async(
                    self._strategist_opinion_async(context_dict, decision_point),
                    self.executor_brain.express_opinion_async(
                        context_dict, decision_point
                    ),
                    self.reflector_brain.predict_consequence_async(
                        context_dict, planned_action
                    ),
                ),
                timeout=PARALLEL_VOTE_TIMEOUT,
            )
            return decision
        except Exception as e:
            logger.warning("并行投票失败，降级到串行: %s", e)
            return await self._serial_consensus_fallback(context, decision_point, step)

    async def _strategist_opinion_async(self, context_dict, decision_point):
        """策略脑异步意见。"""
        from .agent_loop import AgentLoop
        from .consensus_engine import Opinion, OpinionType

        result = await asyncio.to_thread(
            self.strategist_brain.express_opinion, context_dict, decision_point
        )
        return AgentLoop._dict_to_opinion(result, brain_type="strategist")

    async def _serial_consensus_fallback(self, context, decision_point: str, step=None):
        """串行降级路径。"""
        from .agent_loop import AgentLoop

        context_dict = AgentLoop._context_to_dict(context)
        planned_action = AgentLoop._extract_planned_action(context, step)
        SERIAL_OP_TIMEOUT = 15

        try:
            from .consensus_engine import Decision

            s_op = AgentLoop._dict_to_opinion(
                await asyncio.wait_for(
                    asyncio.to_thread(
                        self.strategist_brain.express_opinion, context_dict
                    ),
                    timeout=SERIAL_OP_TIMEOUT,
                ),
                "strategist",
            )
            e_op = await asyncio.wait_for(
                asyncio.to_thread(
                    self.executor_brain.express_opinion, context_dict, decision_point
                ),
                timeout=SERIAL_OP_TIMEOUT,
            )
            r_op = await asyncio.wait_for(
                asyncio.to_thread(
                    self.reflector_brain.predict_consequence,
                    context_dict,
                    planned_action,
                ),
                timeout=SERIAL_OP_TIMEOUT,
            )
            return self._consensus_consultant._consensus.collect_opinions(
                [s_op, e_op, r_op]
            )
        except asyncio.TimeoutError as e:
            logger.error(
                "串行降级共识超时（>%ds），fail-close 拒绝执行: %s",
                SERIAL_OP_TIMEOUT * 3,
                e,
            )
            from .consensus_engine import Decision

            return Decision(
                approved=False,
                reasoning=f"serial_consensus_timeout: 串行降级共识超时（>{SERIAL_OP_TIMEOUT * 3}s）",
                opinions=[],
                consensus_score=0.0,
            )

    def _enrich_step_parameters(
        self, params: Dict, execution_results: List[Dict]
    ) -> Dict:
        """丰富步骤参数。"""
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
    ):
        """带重试的步骤执行。"""
        from .agent_loop import RETRY_BACKOFF_BASE, RETRY_BACKOFF_CAP

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
