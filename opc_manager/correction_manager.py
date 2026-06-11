"""Correction Manager — Handles strategy correction and skill fallback logic."""

import logging
from typing import Dict, Any, Optional

from .reflector_brain import CorrectionStrategy

logger = logging.getLogger(__name__)

SKILL_FALLBACK_MAP = {
    "analysis": "content_generation",
    "content_generation": "analysis",
    "search": "analysis",
    "email": "send_notification",
    "send_notification": "email",
    "crm": "search",
    "finance": "analysis",
    "calendar": "task_manager",
    "task_manager": "calendar",
    "social_publish": "content_generation",
    "proposal": "content_generation",
    "invoice": "finance",
    "report": "content_generation",
    "competitor_watch": "search",
    "pricing": "analysis",
    "tax_reminder": "send_notification",
    "dashboard": "analysis",
    "knowledge_mgmt": "search",
    "ext_skill": "output_result",
}


class CorrectionManager:
    """Manages correction strategies for failed execution steps."""

    def __init__(self, skill_registry=None, executor_brain=None):
        self.skill_registry = skill_registry
        self.executor_brain = executor_brain

    async def apply_correction(self, context, strategy: CorrectionStrategy) -> bool:
        """Apply correction strategy based on error type."""
        if not context.plan or not context.plan.steps:
            return False

        handler = {
            CorrectionStrategy.RETRY: self.correct_retry,
            CorrectionStrategy.SEARCH_AND_RETRY: self.correct_search_and_retry,
            CorrectionStrategy.SWITCH_SKILL: self.correct_switch_skill,
            CorrectionStrategy.DEGRADE: self.correct_degrade,
        }.get(strategy)

        if handler is None:
            return False
        return await handler(context)

    async def correct_retry(self, context) -> bool:
        last_step = context.plan.steps[-1]
        result = await self.executor_brain.execute_step(
            step_id=last_step.id,
            skill_id=last_step.skill_id,
            parameters=last_step.parameters,
            context={"task_id": context.task_id},
        )
        if context.execution_results:
            context.execution_results[-1] = self._make_step_result(
                last_step, result, " (修正-重试)", "retry"
            )
        return result.success

    async def correct_search_and_retry(self, context) -> bool:
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
            context={"task_id": context.task_id},
        )
        if context.execution_results:
            context.execution_results[-1] = self._make_step_result(
                last_step, result, " (修正-补充搜索)", "search_and_retry"
            )
        return result.success

    async def correct_switch_skill(self, context) -> bool:
        last_step = context.plan.steps[-1]
        new_skill = SKILL_FALLBACK_MAP.get(last_step.skill_id)
        if not new_skill:
            return False
        result = await self.executor_brain.execute_step(
            step_id=last_step.id,
            skill_id=new_skill,
            parameters=last_step.parameters,
            context={"task_id": context.task_id},
        )
        if context.execution_results:
            step_result = self._make_step_result(
                last_step, result, " (修正-换技能)", "switch_skill"
            )
            step_result["skill_id"] = new_skill
            context.execution_results[-1] = step_result
        return result.success

    async def correct_degrade(self, context) -> bool:
        last_step = context.plan.steps[-1]
        result = await self.executor_brain.execute_step(
            step_id=last_step.id,
            skill_id=last_step.skill_id,
            parameters=last_step.parameters,
            context={"task_id": context.task_id, "degrade": True},
        )
        if context.execution_results:
            context.execution_results[-1] = self._make_step_result(
                last_step, result, " (修正-降级)", "degrade"
            )
        return result.success

    @staticmethod
    def _make_step_result(
        step,
        result,
        description_suffix: str = "",
        correction_tag: str = "",
    ) -> Dict[str, Any]:
        return {
            "step_id": step.id,
            "skill_id": (
                result.data.get("skill_id", step.skill_id)
                if isinstance(result.data, dict) and "skill_id" in result.data
                else step.skill_id
            ),
            "description": f"{step.description}{description_suffix}",
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "execution_time": result.execution_time,
            **({"correction": correction_tag} if correction_tag else {}),
        }
