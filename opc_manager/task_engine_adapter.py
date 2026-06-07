"""
DEPRECATED: TaskEngineAdapter is deprecated since v0.2.5.
AgentLoop now uses TaskEngineV3 directly via ExecutorBrain.
This module is kept for backward compatibility only.

TaskEngineAdapter — ExecutorBrain与TaskEngineV3之间的适配器

将三贤者架构的skill_id映射到TaskEngineV3的执行方法，
实现编排层（AgentLoop）与执行层（TaskEngineV3）的解耦。

架构位置：
  AgentLoop → ExecutorBrain → TaskEngineAdapter → TaskEngineV3
                                   ↑
                          skill_id → TaskType → _execute_*()

设计决策：
  - 适配器模式，不修改TaskEngineV3内部代码
  - IntentType→TaskType映射表确保策略脑意图能路由到正确方法
  - 保留mock降级路径，TaskEngineV3不可用时回退
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any

from .strategist_brain import IntentType
from .task_engine_v3 import TaskEngineV3, TaskType, TaskResult

logger = logging.getLogger(__name__)

AGENT_LOOP_TIMEOUT_SECONDS = 60

INTENT_TO_TASK_MAP: Dict[IntentType, TaskType] = {
    IntentType.SEARCH: TaskType.INFO_COLLECTION,
    IntentType.ANALYSIS: TaskType.DATA_ANALYSIS,
    IntentType.CREATION: TaskType.CONTENT_GENERATION,
    IntentType.OPERATION: TaskType.BUSINESS_OPERATION,
    IntentType.NOTIFICATION: TaskType.GENERAL_CHAT,
    IntentType.COMBINED: TaskType.CONTENT_GENERATION,
    IntentType.UNKNOWN: TaskType.GENERAL_CHAT,
    IntentType.EMAIL: TaskType.BUSINESS_OPERATION,
    IntentType.FINANCE: TaskType.BUSINESS_OPERATION,
    IntentType.TASK: TaskType.BUSINESS_OPERATION,
    IntentType.CRM: TaskType.BUSINESS_OPERATION,
    IntentType.SOCIAL: TaskType.CONTENT_GENERATION,
    IntentType.PROPOSAL: TaskType.CONTENT_GENERATION,
    IntentType.INVOICE: TaskType.BUSINESS_OPERATION,
    IntentType.REPORT: TaskType.CONTENT_GENERATION,
    IntentType.CALENDAR: TaskType.BUSINESS_OPERATION,
    IntentType.COMPETITOR: TaskType.DATA_ANALYSIS,
    IntentType.PRICING: TaskType.DATA_ANALYSIS,
    IntentType.TAX_REMINDER: TaskType.BUSINESS_OPERATION,
    IntentType.DASHBOARD: TaskType.DATA_ANALYSIS,
    IntentType.KNOWLEDGE: TaskType.INFO_COLLECTION,
    IntentType.EXTENDED_SKILL: TaskType.BUSINESS_OPERATION,
}

SKILL_TO_TASK_MAP: Dict[str, TaskType] = {
    "search": TaskType.INFO_COLLECTION,
    "analysis": TaskType.DATA_ANALYSIS,
    "content_generation": TaskType.CONTENT_GENERATION,
    "execute_operation": TaskType.BUSINESS_OPERATION,
    "send_notification": TaskType.GENERAL_CHAT,
    "intent_analysis": TaskType.INFO_COLLECTION,
    "output_result": TaskType.CONTENT_GENERATION,
    "email": TaskType.BUSINESS_OPERATION,
    "finance": TaskType.BUSINESS_OPERATION,
    "task_manager": TaskType.BUSINESS_OPERATION,
    "crm": TaskType.BUSINESS_OPERATION,
    "social_publish": TaskType.CONTENT_GENERATION,
    "proposal": TaskType.CONTENT_GENERATION,
    "invoice": TaskType.BUSINESS_OPERATION,
    "report": TaskType.CONTENT_GENERATION,
    "calendar": TaskType.BUSINESS_OPERATION,
    "competitor_watch": TaskType.DATA_ANALYSIS,
    "pricing": TaskType.DATA_ANALYSIS,
    "tax_reminder": TaskType.BUSINESS_OPERATION,
    "dashboard": TaskType.DATA_ANALYSIS,
    "knowledge_mgmt": TaskType.INFO_COLLECTION,
    "ext_skill": TaskType.BUSINESS_OPERATION,
}


class TaskEngineAdapter:

    def __init__(self, task_engine: Optional[TaskEngineV3] = None):
        self.task_engine = task_engine or TaskEngineV3()
        self._execution_count = 0

    def execute_skill(
        self,
        skill_id: str,
        parameters: Dict[str, Any],
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        self._execution_count += 1
        logger.info(
            f"[TaskEngineAdapter] Executing skill: {skill_id} (execution #{self._execution_count})"
        )

        task_type = SKILL_TO_TASK_MAP.get(skill_id)
        if task_type is None:
            logger.warning(
                f"[TaskEngineAdapter] Unknown skill_id: {skill_id}, defaulting to GENERAL_CHAT"
            )
            task_type = TaskType.GENERAL_CHAT

        user_input = parameters.get("query", parameters.get("goal", ""))
        if not user_input:
            user_input = parameters.get("user_input", "")
        if not user_input:
            user_input = parameters.get("input", "")
        if not user_input:
            user_input = parameters.get("content", "")

        if not user_input:
            return {
                "success": False,
                "error": f"No input provided for skill: {skill_id}",
                "data": {},
            }

        business_type = parameters.get("business_type")
        session_ctx = parameters.get("session_ctx")

        try:
            result = self.task_engine.execute(
                user_input=user_input,
                session_ctx=session_ctx,
                business_type=business_type,
                task_type_hint=task_type,
            )
            return self._task_result_to_dict(result, skill_id)
        except Exception as e:
            logger.error(f"[TaskEngineAdapter] TaskEngineV3 execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": {},
            }

    async def execute_skill_async(
        self,
        skill_id: str,
        parameters: Dict[str, Any],
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self.execute_skill, skill_id, parameters, context
        )

    def execute_by_intent(
        self,
        intent_type: IntentType,
        user_input: str,
        business_type: Optional[str] = None,
        session_ctx=None,
    ) -> Dict[str, Any]:
        task_type = INTENT_TO_TASK_MAP.get(intent_type, TaskType.GENERAL_CHAT)
        logger.info(
            f"[TaskEngineAdapter] Intent {intent_type.name} → TaskType {task_type.value}"
        )

        try:
            result = self.task_engine.execute(
                user_input=user_input,
                session_ctx=session_ctx,
                business_type=business_type,
                task_type_hint=task_type,
            )
            return self._task_result_to_dict(result, intent_type.value)
        except Exception as e:
            logger.error(f"[TaskEngineAdapter] execute_by_intent failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": {},
            }

    def _task_result_to_dict(self, result: TaskResult, skill_id: str) -> Dict[str, Any]:
        return {
            "success": result.success,
            "data": {
                "content": result.content,
                "sources": result.sources or [],
                "task_type": result.task_type.value if result.task_type else None,
                "search_results": result.search_results or [],
                "deliverable_format": result.deliverable_format,
            },
            "error": result.error,
            "execution_time": (
                result.execution_time_ms / 1000.0 if result.execution_time_ms else 0
            ),
            "skill_id": skill_id,
        }

    @staticmethod
    def dict_to_task_result(data: Dict[str, Any]) -> TaskResult:
        inner = data.get("data", {})
        content = ""
        if isinstance(inner, dict):
            content = inner.get("content", "")
        elif isinstance(inner, str):
            content = inner

        task_type_str = ""
        if isinstance(inner, dict):
            task_type_str = inner.get("task_type", "general_chat")

        task_type = TaskType.GENERAL_CHAT
        for tt in TaskType:
            if tt.value == task_type_str:
                task_type = tt
                break

        sources = []
        if isinstance(inner, dict):
            sources = inner.get("sources", [])

        return TaskResult(
            success=data.get("success", False),
            content=content,
            task_type=task_type,
            sources=sources,
            execution_time_ms=data.get("execution_time", 0) * 1000,
            error=data.get("error"),
        )

    def get_stats(self) -> Dict[str, Any]:
        return {
            "execution_count": self._execution_count,
            "task_engine_initialized": self.task_engine._initialized,
        }
