"""Undo action execution and query functions for OPC-Agents frontend.

Provides the action layer for undo operations, extracted from undo_panel.py:
- execute_undo: Execute undo with ProgressEmitter integration
- calculate_undo_stats: Calculate statistics without UI rendering
- check_has_active_undo_records: Check for active undoable records
- get_latest_undo_record_info: Get info about most recent undo record
"""

import time
import logging
from typing import Optional

from frontend.components.session_utils import _get_undo_manager
from frontend.components.undo_display import OPERATION_TYPE_CONFIG

logger = logging.getLogger(__name__)

__all__ = [
    "execute_undo",
    "calculate_undo_stats",
    "check_has_active_undo_records",
    "get_latest_undo_record_info",
]


def execute_undo(session_id: str, operation_id: str) -> dict:
    """Execute undo operation with ProgressEmitter integration.

    Flow:
    1. Emit STEP_START event via ProgressEmitter
    2. Call UndoManager.undo()
    3. Emit STEP_COMPLETE or ERROR based on result
    4. Return standardized result dict

    Args:
        session_id: Session identifier
        operation_id: Operation to undo

    Returns:
        Dict with 'success' bool and 'message' str
    """
    um = _get_undo_manager()
    if not um:
        return {"success": False, "message": "UndoManager未初始化"}

    try:
        try:
            from opc_manager.progress_emitter import ProgressEmitter, EventType

            emitter = ProgressEmitter()
            emitter.emit(
                session_id=session_id,
                event_type=EventType.STEP_START,
                message=f"正在撤销操作: {operation_id[:8]}...",
                progress=0,
            )
        except ImportError:
            logger.debug("[undo_actions] ProgressEmitter not available")
        except Exception as e:
            logger.warning("[undo_actions] Emit STEP_START failed: %s", e)

        can_undo, reason = um.can_undo(session_id, operation_id)
        if not can_undo:
            return {"success": False, "message": f"无法撤销: {reason}"}

        result = um.undo(session_id, operation_id)

        if result.get("success"):
            try:
                from opc_manager.progress_emitter import ProgressEmitter, EventType

                emitter = ProgressEmitter()
                emitter.emit(
                    session_id=session_id,
                    event_type=EventType.STEP_COMPLETE,
                    message=f"撤销成功: {operation_id[:8]}",
                    progress=100,
                )
            except ImportError:
                pass
            except Exception as e:
                logger.warning("[undo_actions] Emit STEP_COMPLETE failed: %s", e)

            return {
                "success": True,
                "message": "撤销成功！已执行逆操作恢复数据",
                "operation_id": operation_id,
            }
        else:
            error_msg = result.get("error", "未知错误")
            try:
                from opc_manager.progress_emitter import ProgressEmitter, EventType

                emitter = ProgressEmitter()
                emitter.emit(
                    session_id=session_id,
                    event_type=EventType.ERROR,
                    message=f"撤销失败: {error_msg}",
                    progress=0,
                )
            except ImportError:
                pass
            except Exception as e:
                logger.warning("[undo_actions] Emit ERROR failed: %s", e)

            return {"success": False, "message": f"撤销失败: {error_msg}"}

    except ValueError as e:
        return {"success": False, "message": f"参数错误: {str(e)}"}
    except Exception as e:
        logger.error("[undo_actions] execute_undo exception: %s", e)
        return {"success": False, "message": f"系统错误: {str(e)}"}


def calculate_undo_stats(session_id: str) -> dict:
    """Calculate undo statistics without UI rendering.

    Args:
        session_id: Session identifier

    Returns:
        Dict with statistics: {active: int, undone: int, expired: int, total: int}
    """
    um = _get_undo_manager()
    if not um:
        return {"active": 0, "undone": 0, "expired": 0, "total": 0}

    stats = {"active": 0, "undone": 0, "expired": 0, "total": 0}

    try:
        all_records = um.get_session_records(session_id)
        stats["total"] = len(all_records)

        now = time.time()
        for r in all_records:
            if r.status == "active":
                if r.expires_at > now:
                    stats["active"] += 1
                else:
                    stats["expired"] += 1
            elif r.status == "undone":
                stats["undone"] += 1
            else:
                stats["expired"] += 1
    except Exception as e:
        logger.warning("[undo_actions] Stats calculation error: %s", e)

    return stats


def check_has_active_undo_records(session_id: str) -> bool:
    """Check if session has any active (undoable) records.

    Used by smart_suggestions system to determine whether
    to suggest undo action.

    Args:
        session_id: Session identifier

    Returns:
        True if there are active undo records
    """
    um = _get_undo_manager()
    if not um:
        return False

    try:
        undoable = um.list_undoable(session_id)
        return len(undoable) > 0
    except Exception as e:
        logger.warning("[UndoActions] Has undoable check failed: %s", e)
        return False


def get_latest_undo_record_info(session_id: str) -> Optional[dict]:
    """Get information about the most recent active undo record.

    Used by smart_suggestions to generate contextual undo suggestion.

    Args:
        session_id: Session identifier

    Returns:
        Dict with record info or None if no active records
    """
    um = _get_undo_manager()
    if not um:
        return None

    try:
        undoable = um.list_undoable(session_id)
        if not undoable:
            return None

        latest = undoable[0]
        op_type = latest.get("type", "unknown")
        op_config = OPERATION_TYPE_CONFIG.get(op_type, {})

        return {
            "operation_id": latest.get("operation_id", ""),
            "operation_type": op_type,
            "label": op_config.get("label", "操作"),
            "icon": op_config.get("icon", "📝"),
            "remaining_seconds": latest.get("remaining_seconds", 0),
            "description": latest.get("original_summary", ""),
        }
    except Exception as e:
        logger.warning("[UndoActions] Get undo info failed: %s", e)
        return None
