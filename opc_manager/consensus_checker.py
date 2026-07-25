"""ConsensusChecker — 三贤者共识检查组件

Extracted from task_orchestrator.py (v0.5.3) to clarify module boundaries.
TaskOrchestrator delegates consensus-checking decisions here, keeping its
own responsibility focused on task orchestration (Plan→Act→Observe→Reflect).

Design notes:
- Constants (PARALLEL_VOTE_ENABLED, etc.) are imported from .constants so
  tests can patch `opc_manager.consensus_checker.PARALLEL_VOTE_ENABLED`
  to control behavior.
- TaskOrchestrator keeps thin delegate methods (_parallel_consensus, etc.)
  for backward compatibility with existing call sites and tests that
  invoke `loop._parallel_consensus(...)` directly.
- The checker holds references to strategist/executor/reflector brains and
  the consensus_consultant; it does not own their lifecycles.
"""

import asyncio
import logging
from typing import Any

from .constants import (
    CRITICAL_DECISION_ACTIONS,
    CRITICAL_DECISION_SKILLS,
    PARALLEL_VOTE_ENABLED,
    PARALLEL_VOTE_TIMEOUT,
    SERIAL_OP_TIMEOUT,
)
from .agent_utils import (
    context_to_dict,
    dict_to_opinion,
    extract_planned_action,
)

logger = logging.getLogger(__name__)


class ConsensusChecker:
    """Three-sage consensus checker.

    Encapsulates critical-decision detection and parallel/serial consensus
    voting. Extracted from TaskOrchestrator to separate consensus logic
    from task orchestration flow control.

    Public API:
        - is_critical_decision_point(context, step) -> bool
        - parallel_consensus(context, decision_point, step) -> Decision (async)
        - serial_consensus_fallback(context, decision_point, step) -> Decision (async)

    Internal:
        - _strategist_opinion_async(context_dict, decision_point) -> Opinion (async)
    """

    def __init__(
        self,
        strategist_brain: Any,
        executor_brain: Any,
        reflector_brain: Any,
        consensus_consultant: Any,
    ) -> None:
        """Initialize the consensus checker.

        Args:
            strategist_brain: Strategist brain instance (express_opinion).
            executor_brain: Executor brain instance (express_opinion_async).
            reflector_brain: Reflector brain instance (predict_consequence_async).
            consensus_consultant: Consensus consultant wrapping the
                ConsensusEngine (exposes _consensus for voting).
        """
        self.strategist_brain = strategist_brain
        self.executor_brain = executor_brain
        self.reflector_brain = reflector_brain
        self._consensus_consultant = consensus_consultant

    def is_critical_decision_point(self, context: Any, step: Any = None) -> bool:
        """Determine whether the current step is a critical decision point.

        Critical decision points trigger parallel consensus voting.
        Simple-route contexts and non-critical skills/actions skip voting.
        """
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

    async def parallel_consensus(
        self, context: Any, decision_point: str, step: Any = None
    ) -> Any:
        """Three-sage parallel voting decision.

        Falls back to serial_consensus_fallback when PARALLEL_VOTE_ENABLED is
        False or parallel voting raises an exception.
        """
        if not PARALLEL_VOTE_ENABLED:
            return await self.serial_consensus_fallback(context, decision_point, step)
        # Extract coroutines to locals so they can be closed on error
        # (prevents RuntimeWarning: coroutine was never awaited when
        # collect_opinions_async raises before awaiting all arguments)
        strategist_coro = None
        executor_coro = None
        reflector_coro = None
        try:
            context_dict = context_to_dict(context)
            planned_action = extract_planned_action(context, step)

            strategist_coro = self._strategist_opinion_async(
                context_dict, decision_point
            )
            executor_coro = self.executor_brain.express_opinion_async(
                context_dict, decision_point
            )
            reflector_coro = self.reflector_brain.predict_consequence_async(
                context_dict, planned_action
            )

            decision = await asyncio.wait_for(
                self._consensus_consultant._consensus.collect_opinions_async(
                    strategist_coro,
                    executor_coro,
                    reflector_coro,
                ),
                timeout=PARALLEL_VOTE_TIMEOUT,
            )
            return decision
        except Exception as e:
            # Close un-awaited coroutines to prevent RuntimeWarning
            for coro in (strategist_coro, executor_coro, reflector_coro):
                if coro is not None and asyncio.iscoroutine(coro):
                    coro.close()
            logger.warning("并行投票失败，降级到串行: %s", e)
            return await self.serial_consensus_fallback(context, decision_point, step)

    async def _strategist_opinion_async(
        self, context_dict: Any, decision_point: str
    ) -> Any:
        """Strategist brain async opinion (delegates via asyncio.to_thread)."""
        result = await asyncio.to_thread(
            self.strategist_brain.express_opinion, context_dict, decision_point
        )
        return dict_to_opinion(result, brain_type="strategist")

    async def serial_consensus_fallback(
        self, context: Any, decision_point: str, step: Any = None
    ) -> Any:
        """Serial fallback path when parallel voting is disabled or fails.

        Runs each brain sequentially with SERIAL_OP_TIMEOUT per brain.
        On aggregate timeout, returns an ESCALATED fail-closed Decision
        (hard constraint: consensus gate must fail-closed, never fail-open).
        """
        context_dict = context_to_dict(context)
        planned_action = extract_planned_action(context, step)

        try:
            from .consensus_engine import Decision

            s_op = dict_to_opinion(
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
            from .consensus_engine import Decision, DecisionType

            return Decision(
                decision_type=DecisionType.ESCALATED,
                approved=False,
                reasoning=f"serial_consensus_timeout: 串行降级共识超时（>{SERIAL_OP_TIMEOUT * 3}s）",
                confidence=0.0,
            )
