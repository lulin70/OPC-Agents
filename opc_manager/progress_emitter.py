import json
import logging
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Callable, Optional

logger = logging.getLogger(__name__)

"""Progress event system for OPC-Agents.

Provides real-time progress tracking with SSE (Server-Sent Events) support.
Implements pub/sub pattern for progress event distribution.
"""


class EventType(Enum):
    """Types of progress events in the system."""

    PLAN_START = "plan_start"
    INTENT_DETECTED = "intent_detected"
    CONFIRM_REQUESTED = "confirm_requested"
    CONFIRMED = "confirmed"
    CONFIRM_REJECTED = "confirm_rejected"
    STEP_START = "step_start"
    STEP_PROGRESS = "step_progress"
    STEP_COMPLETE = "step_complete"
    COLLAB_START = "collab_start"
    REFLECT_START = "reflect_start"
    COMPLETE = "complete"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class ProgressEvent:
    """Represents a progress event with optional percentage.

    Attributes:
        event_type: Type of the progress event.
        session_id: Session this event belongs to.
        message: Human-readable progress message.
        progress_pct: Progress percentage (0-100), None if not applicable.
        detail: Additional event-specific data.
        timestamp: Unix timestamp when event was created.
        unified_category: Optional UnifiedTaskCategory for dual-engine system (v0.2.1+).
    """

    event_type: EventType
    session_id: str
    message: str
    progress_pct: Optional[int] = None
    detail: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: time.time())
    unified_category: Optional[str] = None

    def __post_init__(self):
        if self.progress_pct is not None:
            if not isinstance(self.progress_pct, (int, float)):
                raise TypeError("progress_pct must be an integer or None")
            if not (0 <= self.progress_pct <= 100):
                raise ValueError("progress_pct must be between 0 and 100")

    @property
    def extracted_unified_category(self) -> Optional[str]:
        """Extract unified category from detail or unified_category field.

        Priority:
        1. Direct unified_category field (new style)
        2. detail['unified_category'] (compatibility mode)
        3. None if not found

        Returns:
            UnifiedTaskCategory value string or None
        """
        if self.unified_category:
            return self.unified_category
        return self.detail.get("unified_category")

    def with_category(self, category) -> "ProgressEvent":
        """Return new event with unified category set (immutable pattern).

        This method creates a new ProgressEvent with the unified_category field set,
        leaving the original event unchanged. This follows the immutable pattern
        for safer concurrent access in async environments.

        Args:
            category: UnifiedTaskCategory enum value or string value

        Returns:
            New ProgressEvent instance with unified_category set
        """
        cat_value = category.value if hasattr(category, "value") else str(category)
        return ProgressEvent(
            event_type=self.event_type,
            session_id=self.session_id,
            message=self.message,
            progress_pct=self.progress_pct,
            detail={**self.detail, "unified_category": cat_value},
            timestamp=self.timestamp,
            unified_category=cat_value,
        )

    def to_dict(self) -> dict:
        d: Dict[str, Any] = {
            "event": self.event_type.value,
            "session_id": self.session_id,
            "message": self.message,
            "timestamp": self.timestamp,
        }
        if self.progress_pct is not None:
            d["progress"] = self.progress_pct
        if self.detail:
            d["detail"] = self.detail
        # Include unified_category at top level for easy frontend access
        if self.unified_category:
            d["unified_category"] = self.unified_category
        return d

    def to_sse(self) -> str:
        d = self.to_dict()
        return f"data: {json.dumps(d, ensure_ascii=False)}\n\n"


class ProgressEmitter:
    """Singleton progress event emitter with pub/sub support.

    Thread-safe implementation supporting real-time event distribution
    to multiple subscribers per session, with history replay for
    late-joining subscribers.

    Attributes:
        _instance: Singleton instance.
        _lock: Threading lock for thread safety.
        _subscribers: Dict mapping session_id to list of callbacks.
        _history: Dict mapping session_id to event history.
        _max_history: Maximum events kept in history (default: 200).
    """

    _instance: Optional["ProgressEmitter"] = None
    _lock = threading.Lock()
    MAX_HISTORY_SIZE = 200
    MAX_SESSIONS = 50  # Maximum number of sessions to keep history for

    # Instance attributes (initialized in __new__ for singleton pattern)
    _subscribers: Dict[str, List[Callable[[str], None]]]
    _history: Dict[str, List[dict]]
    _max_history: int

    def __new__(cls):
        """Create or return singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._subscribers = {}
                    cls._instance._history = {}
                    cls._instance._max_history = cls.MAX_HISTORY_SIZE
        return cls._instance

    def _prune_old_sessions(self):
        """Remove history for oldest sessions when MAX_SESSIONS is exceeded."""
        if len(self._history) <= self.MAX_SESSIONS:
            return
        # Sort by last event timestamp, remove oldest
        sessions = sorted(
            self._history.items(),
            key=lambda kv: kv[1][-1].get("timestamp", 0) if kv[1] else 0,
        )
        excess = len(self._history) - self.MAX_SESSIONS
        for session_id, _ in sessions[:excess]:
            self._history.pop(session_id, None)
            self._subscribers.pop(session_id, None)

    def emit(self, event: ProgressEvent):
        sse_data = event.to_sse()
        callbacks = self._subscribers.get(event.session_id, [])
        dead = []
        for cb in callbacks:
            try:
                cb(sse_data)
            except Exception as e:
                logger.debug("[ProgressEmitter] Callback error: %s", e)
                dead.append(cb)
        if dead:
            self._subscribers[event.session_id] = [
                cb for cb in callbacks if cb not in dead
            ]

        history = self._history.setdefault(event.session_id, [])
        history.append(event.to_dict())
        if len(history) > self._max_history:
            history[:] = history[-self._max_history :]
        self._prune_old_sessions()

    def subscribe(self, session_id: str, callback: Callable[[str], None]):
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")
        if len(session_id) < 32 or len(session_id) > 128:
            raise ValueError("session_id must be between 32 and 128 characters")
        self._subscribers.setdefault(session_id, []).append(callback)
        for event in self._history.get(session_id, []):
            try:
                callback(
                    ProgressEvent(
                        **{**event, "event_type": EventType(event["event"])}
                    ).to_sse()
                )
            except Exception as e:
                logger.debug("[ProgressEmitter] Subscribe replay error: %s", e)

    def unsubscribe(self, session_id: str):
        self._subscribers.pop(session_id, None)

    def get_history(self, session_id: str) -> List[dict]:
        return list(self._history.get(session_id, []))

    def clear_history(self, session_id: str):
        self._history.pop(session_id, None)
