"""ResultBuilder — Agent结果构建组件

从AgentLoop提取的结果构建职责，负责：
- 收集执行结果
- 格式化输出内容
- 构建TaskResult对象
- 处理会话信息

重构目标：将结果构建逻辑从核心执行循环中分离，提高可维护性。
"""

import logging
from typing import Any, Dict, List, Optional

from .agent_context import AgentContext
from .task_engine_v3 import TaskType, TaskResult

logger = logging.getLogger(__name__)


class ResultBuilder:
    """结果构建器。

    职责：
    - 从AgentContext构建最终的TaskResult
    - 处理执行结果的格式化
    - 管理会话历史记录
    - 处理取消和失败场景的结果

    设计原则：
    - 结果构建逻辑集中管理
    - 支持不同场景的结果构建
    - 保持与原有行为的完全兼容
    """

    def __init__(self, session_manager=None):
        """初始化结果构建器。

        Args:
            session_manager: 会话管理器实例（可选，用于记录会话历史）
        """
        self._session_manager = session_manager

    def build_result(
        self, context: AgentContext, cancelled: bool = False
    ) -> TaskResult:
        """从AgentContext构建最终结果。

        Args:
            context: Agent上下文
            cancelled: 是否被取消

        Returns:
            TaskResult: 构建的结果对象
        """
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

        # 记录会话历史
        if context.session_id and result_summary:
            self._record_session_turn(context, result_summary)

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

    def build_greeting_result(
        self, content: str, confidence: float = 0.95
    ) -> TaskResult:
        """构建问候响应结果。

        Args:
            content: 响应内容
            confidence: 路由置信度

        Returns:
            TaskResult: 问候结果
        """
        return TaskResult(
            success=True,
            content=content,
            task_type=TaskType.GENERAL_CHAT,
            metadata={"route": "greeting", "confidence": confidence},
        )

    def build_loop_error_result(self, loop_result: Dict[str, Any]) -> TaskResult:
        """构建循环错误结果。

        Args:
            loop_result: 循环返回的结果字典

        Returns:
            TaskResult: 错误结果
        """
        loop_error = loop_result.get("error", "")
        fallback_content = loop_error or "任务执行遇到问题，请重试或换一种方式描述"
        return TaskResult(
            success=loop_result.get("success", False),
            content=fallback_content,
            task_type=TaskType.GENERAL_CHAT,
            error=loop_error,
        )

    def build_overall_result(self, context: AgentContext) -> Dict[str, Any]:
        """构建总体执行结果摘要（用于反思阶段）。

        Args:
            context: Agent上下文

        Returns:
            Dict: 总体结果字典
        """
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

    def _record_session_turn(self, context: AgentContext, result_summary: str) -> None:
        """记录会话历史。

        Args:
            context: Agent上下文
            result_summary: 结果摘要
        """
        if self._session_manager is None:
            return

        try:
            self._session_manager.add_turn(
                user_input=context.user_input,
                assistant_response=result_summary,
                task_type=context.intent.type.value if context.intent else None,
            )
        except Exception as e:
            logger.warning("会话历史记录失败: %s", e)
