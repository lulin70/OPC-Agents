"""Session utility functions for OPC-Agents frontend.

Provides shared session-level helpers used across multiple components:
- _get_undo_manager: Safe wrapper to get UndoManager instance
- _get_current_session_id: Get current session ID from session context

These functions were previously duplicated in shared.py and undo_panel.py.
"""

import logging
import streamlit as st

logger = logging.getLogger(__name__)

__all__ = ["_get_undo_manager", "_get_current_session_id"]


def _get_undo_manager():
    """Safe wrapper to get UndoManager instance."""
    try:
        from opc_manager.undo_manager import get_undo_manager

        return get_undo_manager()
    except ImportError:
        return None
    except Exception as e:
        logger.warning("[session_utils] UndoManager init failed: %s", e)
        return None


def _get_current_session_id() -> str:
    """Get current session ID from session context.

    Returns:
        Session ID string or 'default' fallback
    """
    try:
        session_ctx = st.session_state.get("session_ctx")
        if session_ctx and hasattr(session_ctx, "_session_id"):
            return session_ctx._session_id
        elif session_ctx and hasattr(session_ctx, "session_id"):
            return session_ctx.session_id
    except Exception as e:
        logger.warning("[SessionUtils] Session ID retrieval failed: %s", e)

    return st.session_state.get("session_id", "default")
