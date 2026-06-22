"""ErrorHandler — Agent错误处理组件

从AgentLoop提取的错误处理职责，负责：
- 输入验证
- 错误分类和处理
- 异常包装和转换
- 错误指标记录

重构目标：将错误处理逻辑集中管理，提高代码可维护性和一致性。
"""

import logging
from dataclasses import dataclass
from typing import Optional

from .task_engine_v3 import TaskType, TaskResult

logger = logging.getLogger(__name__)

MAX_USER_INPUT_LENGTH = 10000


@dataclass
class ValidationResult:
    """输入验证结果。"""

    is_valid: bool
    error: Optional[str] = None


class ErrorHandler:
    """统一的错误处理器。

    职责：
    - 验证用户输入
    - 处理执行异常
    - 构建错误结果
    - 记录错误日志

    设计原则：
    - 所有错误处理逻辑集中在一处
    - 提供统一的错误结果构建接口
    - 支持不同类型的错误分类
    """

    @staticmethod
    def validate_input(user_input: str) -> ValidationResult:
        """验证用户输入。

        Args:
            user_input: 用户输入文本

        Returns:
            ValidationResult: 验证结果
        """
        if not user_input or not user_input.strip():
            return ValidationResult(is_valid=False, error="用户输入不能为空")

        if len(user_input) > MAX_USER_INPUT_LENGTH:
            return ValidationResult(
                is_valid=False,
                error=f"用户输入超过最大长度限制({MAX_USER_INPUT_LENGTH}字符)",
            )

        return ValidationResult(is_valid=True)

    @staticmethod
    def build_error_result(
        error: str,
        task_type: TaskType = TaskType.GENERAL_CHAT,
        content: str = "",
        metadata: Optional[dict] = None,
    ) -> TaskResult:
        """构建错误结果。

        Args:
            error: 错误消息
            task_type: 任务类型
            content: 内容（可选）
            metadata: 元数据（可选）

        Returns:
            TaskResult: 错误结果对象
        """
        return TaskResult(
            success=False,
            content=content,
            task_type=task_type,
            error=error,
            metadata=metadata or {},
        )

    @staticmethod
    def build_validation_error_result(error: str) -> TaskResult:
        """构建验证错误结果。

        Args:
            error: 验证错误消息

        Returns:
            TaskResult: 验证错误结果
        """
        return ErrorHandler.build_error_result(
            error=error,
            content="",
        )

    @staticmethod
    def handle_execution_exception(
        error: Exception, task_id: str
    ) -> TaskResult:
        """处理执行异常。

        Args:
            error: 异常对象
            task_id: 任务ID

        Returns:
            TaskResult: 错误结果
        """
        error_msg = str(error)
        logger.error("AgentLoop 执行失败 (task_id=%s): %s", task_id, error_msg)
        return ErrorHandler.build_error_result(error=error_msg)

    @staticmethod
    def build_confirmation_needed_result(
        confirmation_message: str = "",
    ) -> TaskResult:
        """构建需要确认的结果。

        Args:
            confirmation_message: 确认消息

        Returns:
            TaskResult: 需要确认的结果
        """
        return TaskResult(
            success=False,
            content="",
            task_type=TaskType.GENERAL_CHAT,
            error="需要用户确认后才能执行",
            metadata={
                "needs_confirmation": True,
                "confirmation_message": confirmation_message,
            },
        )
