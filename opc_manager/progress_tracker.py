"""ProgressTracker — Agent进度跟踪组件

从AgentLoop提取的进度跟踪职责，负责：
- 发射进度事件
- 管理进度状态
- 提供进度查询接口

重构目标：将进度跟踪逻辑从核心执行循环中分离，提高可维护性。
"""

import logging
from typing import Optional

from .progress_emitter import ProgressEmitter, ProgressEvent, EventType

logger = logging.getLogger(__name__)


class ProgressTracker:
    """进度跟踪器。

    职责：
    - 封装ProgressEmitter的进度发射逻辑
    - 提供语义化的进度更新方法
    - 管理进度百分比计算

    设计原则：
    - 进度发射逻辑集中管理
    - 提供清晰的语义化接口
    - 支持可选的进度跟踪（progress为None时静默）
    """

    def __init__(self, progress_emitter: Optional[ProgressEmitter] = None):
        """初始化进度跟踪器。

        Args:
            progress_emitter: 进度发射器实例（可选）
        """
        self._progress = progress_emitter

    @property
    def emitter(self) -> Optional[ProgressEmitter]:
        """获取底层进度发射器。"""
        return self._progress

    def emit_plan_start(self, session_id: str, message: str = "正在分析你的需求...") -> None:
        """发射规划开始事件。"""
        self._emit(
            EventType.PLAN_START, session_id, message
        )

    def emit_intent_detected(
        self,
        session_id: str,
        intent_type: str,
        goal: str,
        confidence: Optional[float] = None,
        progress_pct: int = 10,
    ) -> None:
        """发射意图识别事件。"""
        self._emit(
            EventType.INTENT_DETECTED,
            session_id,
            f"意图识别: {intent_type} - {goal[:50]}",
            detail={"intent_type": intent_type, "confidence": confidence},
            progress_pct=progress_pct,
        )

    def emit_step_start(
        self,
        session_id: str,
        step_id: str,
        skill_id: str,
        current: int,
        total: int,
    ) -> None:
        """发射步骤开始事件。"""
        progress_pct = int((current / total) * 70) + 10 if total > 0 else 10
        self._emit(
            EventType.STEP_START,
            session_id,
            f"[执行脑] 执行步骤: {skill_id}",
            detail={"step_id": step_id, "skill_id": skill_id},
            progress_pct=progress_pct,
        )

    def emit_step_complete(
        self,
        session_id: str,
        skill_id: str,
        current: int,
        total: int,
    ) -> None:
        """发射步骤完成事件。"""
        progress_pct = int(((current + 1) / total) * 70) + 10 if total > 0 else 80
        self._emit(
            EventType.STEP_COMPLETE,
            session_id,
            f"✅ 步骤完成: {skill_id}",
            progress_pct=progress_pct,
        )

    def emit_reflect_start(self, session_id: str) -> None:
        """发射反思开始事件。"""
        self._emit(
            EventType.REFLECT_START,
            session_id,
            "[反思脑] 正在评估执行结果...",
            progress_pct=85,
        )

    def emit_complete(self, session_id: str, message: str = "全部完成!") -> None:
        """发射完成事件。"""
        self._emit(
            EventType.COMPLETE,
            session_id,
            message,
            progress_pct=100,
        )

    def emit_error(
        self,
        session_id: str,
        message: str,
        detail: Optional[dict] = None,
    ) -> None:
        """发射错误事件。"""
        self._emit(
            EventType.ERROR,
            session_id,
            message,
            detail=detail or {},
        )

    def emit_cancelled(self, session_id: str, message: str = "任务已取消") -> None:
        """发射取消事件。"""
        self._emit(
            EventType.CANCELLED,
            session_id,
            message,
        )

    def _emit(
        self,
        event_type: EventType,
        session_id: str,
        message: str,
        detail: Optional[dict] = None,
        progress_pct: Optional[int] = None,
    ) -> None:
        """内部方法：发射进度事件（如果progress可用）。"""
        if self._progress is None:
            return

        try:
            event = ProgressEvent(
                event_type=event_type,
                session_id=session_id,
                message=message,
                detail=detail or {},
                progress_pct=progress_pct,
            )
            self._progress.emit(event)
        except Exception as e:
            logger.warning("进度事件发射失败: %s", e)
