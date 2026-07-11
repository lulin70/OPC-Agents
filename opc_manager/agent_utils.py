"""Utility functions for AgentLoop and TaskOrchestrator.

Extracted from agent_loop.py to eliminate circular dependency.
These are stateless helper functions used by both modules.
"""

from typing import Any, Dict, Optional

from .consensus_engine import Opinion, OpinionType


def context_to_dict(context: Any) -> Dict[str, Any]:
    """Convert AgentContext to dict for three-sage voting [S2-T2].

    Args:
        context: AgentContext object or dict

    Returns:
        Dict representation of the context
    """
    if isinstance(context, dict):
        return context
    return {
        "user_input": getattr(context, "user_input", ""),
        "intent": getattr(context, "intent", None),
        "plan": getattr(context, "plan", None),
        "retry_count": getattr(context, "retry_count", 0),
        "current_step": getattr(context, "current_step", 0),
        "execution_results": getattr(context, "execution_results", []),
    }


def extract_planned_action(context: Any, step: Optional[Any] = None) -> Dict[str, Any]:
    """Extract planned action info for ReflectorBrain prediction [S2-T2].

    Args:
        context: AgentContext object or dict
        step: Optional step object. If None, extracts from context.current_step

    Returns:
        Dict with skill_id, action, parameters
    """
    if step is None:
        if not isinstance(context, dict):
            current_step_idx = getattr(context, "current_step", 0)
            plan = getattr(context, "plan", None)
            steps = getattr(plan, "steps", None) if plan else None
            if steps and 0 < current_step_idx <= len(steps):
                step = steps[current_step_idx - 1]
    if step:
        return {
            "skill_id": getattr(step, "skill_id", "") or "",
            "action": getattr(step, "action", "") or "",
            "parameters": getattr(step, "parameters", {}) or {},
        }
    return {"skill_id": "", "action": "", "parameters": {}}


def dict_to_opinion(result: Dict, brain_type: str) -> Opinion:
    """Convert Brain.express_opinion return Dict to Opinion object [S2-T2].

    Args:
        result: Dict from Brain.express_opinion or non-dict value
        brain_type: "strategist", "executor", or "reflector"

    Returns:
        Opinion object
    """
    if not isinstance(result, dict):
        return Opinion(
            brain_type=brain_type,
            opinion_type=OpinionType.ABSTAIN,
            reasoning=f"Brain returned non-dict: {type(result).__name__}",
            confidence=0.0,
        )
    opinion_type_str = str(result.get("opinion_type", "AGREE")).upper()
    try:
        opinion_type = OpinionType[opinion_type_str]
    except KeyError:
        opinion_type = OpinionType.ABSTAIN
    return Opinion(
        brain_type=brain_type,
        opinion_type=opinion_type,
        reasoning=result.get("reasoning", ""),
        confidence=result.get("confidence", 0.5),
        alternative=result.get("alternative"),
    )
