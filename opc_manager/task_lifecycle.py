"""Task Lifecycle Manager — extracted from AgentLoop.

Manages task status queries, cancellation, pause/resume, and listing.
This separates lifecycle management concerns from the core execution loop.
"""

import asyncio
import json as _json
import logging
import time
from typing import Any, Dict, List, Optional

from .agent_context import AgentContext, AgentState
from .consensus_engine import DecisionType, Opinion, OpinionType
from .executor_brain import ExecutorBrain
from .reflector_brain import Evaluation

logger = logging.getLogger(__name__)

# Re-export constants needed by this module
PAUSE_TIMEOUT_SECONDS = int(
    __import__("os").environ.get("OPC_PAUSE_TIMEOUT_SECONDS", "1800")
)
AGENT_LOOP_TIMEOUT_SECONDS = int(
    __import__("os").environ.get("OPC_AGENT_LOOP_TIMEOUT_SECONDS", "120")
)


class TaskLifecycleManager:
    """Manages task lifecycle operations: status, cancel, pause, resume, list.

    Extracted from AgentLoop to reduce its complexity and isolate
    lifecycle management concerns.
    """

    def __init__(self, contexts: dict, executor_brain: ExecutorBrain):
        """Initialize with shared contexts dict and executor brain reference.

        Args:
            contexts: Shared BoundedDict from AgentLoop (task_id → AgentContext).
            executor_brain: ExecutorBrain instance for cancel operations.
        """
        self._contexts = contexts
        self._executor_brain = executor_brain

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a task.

        Args:
            task_id: Task identifier.

        Returns:
            Status dict or None if task not found.
        """
        context = self._contexts.get(task_id)
        if not context:
            return None

        return {
            "task_id": task_id,
            "state": context.state.value,
            "current_step": context.current_step,
            "total_steps": len(context.plan.steps) if context.plan else 0,
            "retry_count": context.retry_count,
            "results": (
                context.execution_results[-5:] if context.execution_results else []
            ),
        }

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task.

        Args:
            task_id: Task identifier.

        Returns:
            True if cancellation was successful.
        """
        context = self._contexts.get(task_id)
        if not context:
            return False

        context.cancel_requested = True
        context.set_state(AgentState.CANCELLED)
        await self._executor_brain.cancel_execution(task_id)
        logger.info("任务已取消: %s", task_id)
        return True

    async def pause_task(self, task_id: str) -> bool:
        """Pause a running task.

        Args:
            task_id: Task identifier.

        Returns:
            True if pause was successful.
        """
        context = self._contexts.get(task_id)
        if not context:
            return False

        if context.state not in (
            AgentState.EXECUTING,
            AgentState.PLANNING,
            AgentState.OBSERVING,
            AgentState.REFLECTING,
        ):
            logger.warning("任务 %s 当前状态 %s 不可暂停", task_id, context.state.value)
            return False

        context.paused_at = time.time()
        context.set_state(AgentState.PAUSED)
        logger.info("任务已暂停: %s (步骤: %s)", task_id, context.current_step)
        return True

    async def resume_task(self, task_id: str) -> Dict[str, Any]:
        """Resume a paused task.

        Args:
            task_id: Task identifier.

        Returns:
            Result dict with success status.
        """
        context = self._contexts.get(task_id)
        if not context:
            return {"success": False, "error": f"任务 {task_id} 不存在"}

        if context.state != AgentState.PAUSED:
            return {
                "success": False,
                "error": f"任务 {task_id} 当前状态 {context.state.value} 不可恢复",
            }

        if (
            context.paused_at
            and (time.time() - context.paused_at) > PAUSE_TIMEOUT_SECONDS
        ):
            context.cancel_requested = True
            context.set_state(AgentState.CANCELLED)
            logger.warning("任务 %s 暂停超时，自动取消", task_id)
            return {"success": False, "error": "暂停超时，任务已自动取消"}

        context.paused_at = None
        context.set_state(AgentState.EXECUTING)
        logger.info("任务已恢复: %s (从步骤 %s 继续)", task_id, context.current_step)

        return {
            "success": True,
            "task_id": task_id,
            "resume_step": context.current_step,
        }

    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all tracked tasks with brief info.

        Returns:
            List of task summary dicts.
        """
        tasks = []
        for task_id, context in self._contexts.items():
            tasks.append(
                {
                    "task_id": task_id,
                    "user_input": (
                        context.user_input[:50] + "..."
                        if len(context.user_input) > 50
                        else context.user_input
                    ),
                    "state": context.state.value,
                    "current_step": context.current_step,
                }
            )
        return tasks

    def to_dict(self) -> Dict[str, Any]:
        """Serialize manager state for diagnostics.

        Returns:
            Dict with task count and active task info.
        """
        return {
            "type": "task_lifecycle_manager",
            "task_count": len(self._contexts),
            "active_tasks": sum(
                1
                for ctx in self._contexts.values()
                if ctx.state
                in (
                    AgentState.PLANNING,
                    AgentState.EXECUTING,
                    AgentState.OBSERVING,
                    AgentState.REFLECTING,
                )
            ),
        }


class ConsensusConsultant:
    """Handles consensus engine consultation and logging.

    Extracted from AgentLoop to isolate the consensus decision-making
    and logging logic from the core execution loop.
    """

    def __init__(
        self, strategist_brain, reflector_brain, consensus_engine, executor_brain=None
    ):
        """Initialize with brain and engine references.

        Args:
            strategist_brain: StrategistBrain instance.
            reflector_brain: ReflectorBrain instance.
            consensus_engine: ConsensusEngine instance.
            executor_brain: ExecutorBrain instance for executor opinions.
                [S2-T3] 新增，用于替代假意见。为 None 时降级到规则判断。
        """
        self._strategist = strategist_brain
        self._reflector = reflector_brain
        self._consensus = consensus_engine
        self._executor_brain = executor_brain

    async def consult(
        self,
        context: AgentContext,
        evaluation: Evaluation,
        reflector_action,
    ):
        """Consult the consensus engine if quality is below threshold.

        共识咨询（二级补救保障）[S2-T4]

        角色变更：从事前核心决策降级为事后补救
        - 前置共识已由 AgentLoop._parallel_consensus() 在关键决策点前完成
        - 本方法仅在 quality_score < 0.7 时作为二级保障触发
        - 保留以兼容现有流程

        Args:
            context: Current agent context.
            evaluation: Evaluation result from reflector.
            reflector_action: NextAction suggested by reflector.

        Returns:
            NextAction override or None if consensus agrees.
        """
        from .reflector_brain import NextAction, NextActionType
        from .consensus_engine import Opinion, OpinionType

        # P3-17 修复：引用常量而非硬编码 0.7，避免修改时遗漏
        from .agent_loop import QUALITY_THRESHOLD_CONSENSUS

        if evaluation.quality_score >= QUALITY_THRESHOLD_CONSENSUS:
            return None

        # P0-2 修复：所有同步 LLM 调用包装为 asyncio.to_thread，避免阻塞事件循环
        strategist_ctx = {"intent": context.intent}
        strategist_data = await asyncio.to_thread(
            self._strategist.express_opinion, strategist_ctx
        )
        strategist_opinion = Opinion(
            brain_type=strategist_data["brain_type"],
            opinion_type=OpinionType[strategist_data["opinion_type"]],
            reasoning=strategist_data["reasoning"],
            confidence=strategist_data["confidence"],
        )

        executor_opinion = await asyncio.to_thread(
            self._build_executor_opinion, context
        )

        reflector_ctx = {"evaluation": evaluation, "next_action": reflector_action}
        reflector_data = await asyncio.to_thread(
            self._reflector.express_opinion, reflector_ctx
        )
        reflector_opinion = Opinion(
            brain_type=reflector_data["brain_type"],
            opinion_type=OpinionType[reflector_data["opinion_type"]],
            reasoning=reflector_data["reasoning"],
            confidence=reflector_data["confidence"],
        )

        decision = self._consensus.collect_opinions(
            [strategist_opinion, executor_opinion, reflector_opinion]
        )

        await self.log_decision(context, evaluation, decision)

        if decision.decision_type == DecisionType.VETOED:
            logger.info("共识引擎否决: %s", decision.reasoning)
            return NextAction(
                action_type=NextActionType.ABANDON,
                reason=decision.reasoning,
                confidence=decision.confidence,
            )

        if decision.decision_type == DecisionType.ESCALATED:
            logger.info("共识引擎升级: %s", decision.reasoning)
            return NextAction(
                action_type=NextActionType.REVIEW,
                reason=decision.reasoning,
                confidence=decision.confidence,
            )

        return None

    def _build_executor_opinion(self, context: AgentContext) -> Opinion:
        """构建执行脑意见（[S2-T3] 替代假意见）。

        优先调用 executor_brain.express_opinion() 获取真实 LLM 判断；
        若未注入 executor_brain 则降级到基于 retry_count 的规则判断，
        保持向后兼容。

        Args:
            context: 当前 AgentContext 对象。

        Returns:
            Opinion: 执行脑意见，brain_type 固定为 "executor"。
        """
        decision_point = self._derive_decision_point(context)
        executor_ctx = {
            "retry_count": context.retry_count,
            "user_input": context.user_input,
            "step_info": self._summarize_current_step(context),
            "execution_summary": self._summarize_results(context),
        }

        if self._executor_brain is not None:
            try:
                return self._executor_brain.express_opinion(
                    executor_ctx, decision_point
                )
            except Exception as e:
                logger.warning(
                    "executor_brain.express_opinion 异常，降级到规则判断: %s", e
                )

        # P2-10 修复：复用 ExecutorBrain._generate_retry_opinion 消除重复的假意见规则
        retry_count = context.retry_count
        opinion_data = ExecutorBrain._generate_retry_opinion(retry_count)
        opinion_type = (
            OpinionType.AGREE
            if opinion_data["opinion_type"] == "AGREE"
            else OpinionType.DISAGREE
        )
        return Opinion(
            brain_type="executor",
            opinion_type=opinion_type,
            reasoning=f"执行重试次数: {retry_count} (决策点: {decision_point})",
            confidence=opinion_data["confidence"],
        )

    @staticmethod
    def _derive_decision_point(context: AgentContext) -> str:
        """从当前步骤推导决策点字符串。"""
        plan = getattr(context, "plan", None)
        steps = getattr(plan, "steps", None) if plan else None
        if steps and 0 <= context.current_step < len(steps):
            step = steps[context.current_step]
            skill_id = getattr(step, "skill_id", None)
            if skill_id:
                return skill_id
        return "task_continuation"

    @staticmethod
    def _summarize_current_step(context: AgentContext) -> str:
        """摘要当前步骤信息用于 LLM prompt。"""
        plan = getattr(context, "plan", None)
        steps = getattr(plan, "steps", None) if plan else None
        if steps and 0 <= context.current_step < len(steps):
            step = steps[context.current_step]
            desc = getattr(step, "description", "")
            skill_id = getattr(step, "skill_id", "")
            return f"step={context.current_step + 1}/{len(steps)} skill={skill_id} desc={desc}"
        return f"step={context.current_step + 1}"

    @staticmethod
    def _summarize_results(context: AgentContext) -> str:
        """摘要执行结果用于 LLM prompt。"""
        results = context.execution_results or []
        if not results:
            return "无执行结果"
        last = results[-1]
        success = last.get("success") if isinstance(last, dict) else None
        return f"已完成{len(results)}步，最近成功={success}"

    async def log_decision(
        self, context: AgentContext, evaluation: Evaluation, decision
    ) -> None:
        """Log a consensus decision to the database.

        Args:
            context: Current agent context.
            evaluation: Evaluation result.
            decision: Consensus decision.
        """
        log_entry = {
            "task_id": context.task_id,
            "quality_score": evaluation.quality_score,
            "result_level": evaluation.result.name,
            "decision_type": (
                decision.decision_type.name if decision.decision_type else None
            ),
            "confidence": decision.confidence,
            "reasoning": decision.reasoning,
            "timestamp": time.time(),
        }

        try:
            from opc_manager.data_manager import execute_write, init_db

            init_db()
            execute_write(
                "INSERT INTO consensus_decisions "
                "(id, timestamp, opinion_count, decision_type, "
                "approved, confidence, detail) VALUES (?,?,?,?,?,?,?)",
                (
                    context.task_id,
                    log_entry["timestamp"],
                    3,
                    log_entry["decision_type"] or "",
                    1 if log_entry["confidence"] >= 0.5 else 0,
                    log_entry["confidence"],
                    _json.dumps(log_entry, ensure_ascii=False),
                ),
            )
        except Exception as e:
            logger.warning("共识日志写入失败: %s", e)
