"""StateManager — Agent状态管理组件

从AgentLoop提取的状态管理职责，负责：
- 创建和管理AgentContext
- 处理状态转换逻辑
- 记录状态变更历史
- 提供状态查询接口

重构目标：将状态管理从核心执行循环中分离，提高可测试性和可维护性。
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from .agent_context import AgentContext, AgentState
from .utils import BoundedDict

logger = logging.getLogger(__name__)

MAX_CONTEXT_HISTORY = int(
    __import__("os").environ.get("OPC_MAX_CONTEXT_HISTORY", "100")
)


class StateManager:
    """管理Agent的状态转换和生命周期。

    职责：
    - 创建新的AgentContext
    - 管理状态转换（带历史记录）
    - 提供状态查询接口
    - 支持状态变更监听器

    设计原则：
    - 状态转换逻辑集中管理，避免散落在各处
    - 所有状态变更都有记录，便于调试和审计
    - 支持监听器模式，实现松耦合的事件通知
    """

    def __init__(self, max_context_history: int = MAX_CONTEXT_HISTORY):
        """初始化状态管理器。

        Args:
            max_context_history: 最大上下文历史数量
        """
        self._contexts: BoundedDict = BoundedDict(max_size=max_context_history)
        self._state_history: List[Dict[str, Any]] = []
        self._state_listeners: List[Any] = []

    @property
    def contexts(self) -> BoundedDict:
        """获取上下文字典（供其他组件共享访问）"""
        return self._contexts

    def create_context(
        self, user_input: str, session_id: Optional[str] = None
    ) -> AgentContext:
        """创建新的Agent上下文。

        Args:
            user_input: 用户输入文本
            session_id: 会话ID（可选，自动生成如果未提供）

        Returns:
            AgentContext: 新创建的上下文对象
        """
        task_id = f"agent_task_{uuid.uuid4().hex[:8]}"
        context = AgentContext(
            task_id=task_id,
            user_input=user_input.strip(),
            session_id=session_id or str(uuid.uuid4()),
        )
        self._contexts[task_id] = context
        logger.debug("创建新上下文: task_id=%s", task_id)
        return context

    def set_state(self, context: AgentContext, new_state: AgentState) -> None:
        """设置Agent状态并记录变更。

        Args:
            context: Agent上下文
            new_state: 新状态
        """
        old_state = context.state
        context.set_state(new_state)
        self._record_state_change(context.task_id, old_state, new_state)
        self._notify_state_listeners(context.task_id, old_state, new_state)

    def get_context(self, task_id: str) -> Optional[AgentContext]:
        """获取指定任务的上下文。

        Args:
            task_id: 任务ID

        Returns:
            AgentContext或None（如果不存在）
        """
        return self._contexts.get(task_id)

    def get_state(self, task_id: str) -> Optional[AgentState]:
        """获取指定任务的当前状态。

        Args:
            task_id: 任务ID

        Returns:
            AgentState或None（如果任务不存在）
        """
        context = self._contexts.get(task_id)
        return context.state if context else None

    def get_state_history(self, task_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取状态变更历史。

        Args:
            task_id: 可选的任务ID过滤

        Returns:
            状态变更记录列表
        """
        if task_id:
            return [h for h in self._state_history if h.get("task_id") == task_id]
        return list(self._state_history)

    def add_state_listener(self, listener: Any) -> None:
        """添加状态变更监听器。

        监听器需要实现 on_state_changed(task_id, old_state, new_state) 方法。

        Args:
            listener: 监听器对象
        """
        self._state_listeners.append(listener)

    def remove_state_listener(self, listener: Any) -> None:
        """移除状态变更监听器。

        Args:
            listener: 要移除的监听器对象
        """
        if listener in self._state_listeners:
            self._state_listeners.remove(listener)

    def _record_state_change(
        self, task_id: str, old_state: AgentState, new_state: AgentState
    ) -> None:
        """记录状态变更历史。"""
        self._state_history.append(
            {
                "task_id": task_id,
                "timestamp": time.time(),
                "old_state": old_state.value,
                "new_state": new_state.value,
            }
        )
        # 限制历史记录大小，避免内存泄漏
        if len(self._state_history) > 1000:
            self._state_history = self._state_history[-500:]

    def _notify_state_listeners(
        self, task_id: str, old_state: AgentState, new_state: AgentState
    ) -> None:
        """通知状态监听器。"""
        for listener in self._state_listeners:
            try:
                if hasattr(listener, "on_state_changed"):
                    listener.on_state_changed(task_id, old_state, new_state)
            except Exception as e:
                logger.warning("状态监听器通知失败: %s", e)
