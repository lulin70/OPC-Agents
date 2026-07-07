"""Typed accessor for chat-related Streamlit session state.

SessionStateManager is an *adapter* over the existing flat ``st.session_state``
keys (``messages``, ``deliverables``, ``quality_feedback``, ``detected_type``,
``detected_name``, ``pending_prompt``, ``last_failed_prompt``). It does NOT move
state into a nested object, so other components that still read
``st.session_state.messages`` / ``deliverables`` directly (app.py,
deliverables_renderer.py, base_router._save_chat_history) keep working
unchanged.

Responsibilities:
- Ensure all chat-related keys exist with safe defaults (fixes latent KeyError
  when ``init_session_state`` hasn't initialised ``quality_feedback`` etc.).
- Centralise the message/deliverable boundary checks that were previously
  duplicated in chat_router.py.
- Provide typed, intention-revealing methods so call sites are shorter and
  harder to get wrong.
"""

from typing import Any, Dict, List, Optional

import streamlit as st

# Memory bounds — prevent unbounded list growth in long sessions.
# Kept as class attributes so tests and callers can reference them.
MAX_CHAT_MESSAGES = 100
MAX_DELIVERABLES = 50


class SessionStateManager:
    """Typed wrapper over the chat-related ``st.session_state`` keys.

    Constructing an instance is cheap and side-effect-free apart from
    ensuring the managed keys exist. Typical usage at the top of a router
    function::

        mgr = SessionStateManager()
        mgr.add_message({"role": "user", "content": prompt})
    """

    # Keys managed by this class. Public as class attributes so they can be
    # referenced/audited, but callers should normally use the typed methods.
    KEY_MESSAGES = "messages"
    KEY_DELIVERABLES = "deliverables"
    KEY_QUALITY_FEEDBACK = "quality_feedback"
    KEY_DETECTED_TYPE = "detected_type"
    KEY_DETECTED_NAME = "detected_name"
    KEY_PENDING_PROMPT = "pending_prompt"
    KEY_LAST_FAILED_PROMPT = "last_failed_prompt"

    def __init__(self) -> None:
        self._ensure_initialized()

    # ── Initialisation ────────────────────────────────────────────────────

    def _ensure_initialized(self) -> None:
        """Ensure all chat-related keys exist with safe defaults.

        ``init_session_state`` in base_router.py covers the keys it knows about,
        but ``quality_feedback`` / ``detected_type`` / ``detected_name`` /
        ``last_failed_prompt`` have historically been set lazily by app.py or
        chat_router.py, causing latent KeyErrors when accessed out of order.
        Running this on every manager construction makes those accesses safe.
        """
        defaults: Dict[str, Any] = {
            self.KEY_MESSAGES: [],
            self.KEY_DELIVERABLES: [],
            self.KEY_QUALITY_FEEDBACK: {},
            self.KEY_DETECTED_TYPE: None,
            self.KEY_DETECTED_NAME: None,
            self.KEY_PENDING_PROMPT: None,
            self.KEY_LAST_FAILED_PROMPT: None,
        }
        for key, default in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default

    # ── Messages ──────────────────────────────────────────────────────────

    @property
    def messages(self) -> List[Dict[str, Any]]:
        return st.session_state[self.KEY_MESSAGES]

    def message_count(self) -> int:
        return len(st.session_state[self.KEY_MESSAGES])

    def add_message(self, message: Dict[str, Any]) -> None:
        """Append a message record and enforce ``MAX_CHAT_MESSAGES``."""
        st.session_state[self.KEY_MESSAGES].append(message)
        self._enforce_message_limit()

    def _enforce_message_limit(self) -> None:
        msgs = st.session_state[self.KEY_MESSAGES]
        if len(msgs) > MAX_CHAT_MESSAGES:
            st.session_state[self.KEY_MESSAGES] = msgs[-MAX_CHAT_MESSAGES:]

    # ── Deliverables ──────────────────────────────────────────────────────

    @property
    def deliverables(self) -> List[Dict[str, Any]]:
        return st.session_state[self.KEY_DELIVERABLES]

    def add_deliverable(self, record: Dict[str, Any]) -> None:
        """Insert a deliverable record at the front (most-recent first) and
        enforce ``MAX_DELIVERABLES``."""
        st.session_state[self.KEY_DELIVERABLES].insert(0, record)
        self._enforce_deliverable_limit()

    def _enforce_deliverable_limit(self) -> None:
        dels = st.session_state[self.KEY_DELIVERABLES]
        if len(dels) > MAX_DELIVERABLES:
            st.session_state[self.KEY_DELIVERABLES] = dels[:MAX_DELIVERABLES]

    # ── Quality feedback ──────────────────────────────────────────────────

    @property
    def quality_feedback(self) -> Dict[str, str]:
        return st.session_state[self.KEY_QUALITY_FEEDBACK]

    def set_feedback(self, task_id: str, feedback_type: str) -> None:
        st.session_state[self.KEY_QUALITY_FEEDBACK][f"fb_{task_id}"] = feedback_type

    def get_feedback(self, task_id: str) -> Optional[str]:
        return st.session_state[self.KEY_QUALITY_FEEDBACK].get(f"fb_{task_id}")

    def has_feedback(self, task_id: str) -> bool:
        return f"fb_{task_id}" in st.session_state[self.KEY_QUALITY_FEEDBACK]

    def feedback_items(self) -> List[Any]:
        """Return feedback entries as a list of ``(key, value)`` tuples for
        consumers like ``build_context_from_session`` that expect
        ``list(quality_feedback.items())``."""
        return list(st.session_state[self.KEY_QUALITY_FEEDBACK].items())

    # ── Detected persona ──────────────────────────────────────────────────

    @property
    def detected_type(self) -> Optional[str]:
        return st.session_state[self.KEY_DETECTED_TYPE]

    @property
    def detected_name(self) -> Optional[str]:
        return st.session_state[self.KEY_DETECTED_NAME]

    def set_detected(self, detected_type: str, detected_name: str) -> None:
        st.session_state[self.KEY_DETECTED_TYPE] = detected_type
        st.session_state[self.KEY_DETECTED_NAME] = detected_name

    # ── Pending / failed prompts ──────────────────────────────────────────

    def set_pending_prompt(self, prompt: str) -> None:
        st.session_state[self.KEY_PENDING_PROMPT] = prompt

    def pop_pending_prompt(self) -> Optional[str]:
        return st.session_state.pop(self.KEY_PENDING_PROMPT, None)

    def set_last_failed_prompt(self, prompt: str) -> None:
        st.session_state[self.KEY_LAST_FAILED_PROMPT] = prompt

    def pop_last_failed_prompt(self) -> Optional[str]:
        return st.session_state.pop(self.KEY_LAST_FAILED_PROMPT, None)
