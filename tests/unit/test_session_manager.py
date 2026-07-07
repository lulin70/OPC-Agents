"""Unit tests for SessionStateManager.

SessionStateManager is an adapter over ``st.session_state``. To test it in
isolation we swap in a lightweight fake that supports both attribute and
item access (``st.session_state.x`` and ``st.session_state["x"]``), plus
``in`` / ``pop`` / membership semantics — the subset of the real
Streamlit SessionState proxy that the manager relies on.
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _FakeSessionState:
    """Minimal stand-in for streamlit's SessionState proxy.

    Supports attribute and item access, ``in``, ``pop``, ``del``, and
    preserves insertion-order semantics for list values (which is all the
    manager needs).
    """

    def __init__(self):
        object.__setattr__(self, "_data", {})

    # Item access
    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __delitem__(self, key):
        del self._data[key]

    def __contains__(self, key):
        return key in self._data

    def pop(self, key, *default):
        if default:
            return self._data.pop(key, default[0])
        return self._data.pop(key)

    # Attribute access (st.session_state.xxx)
    def __getattr__(self, name):
        try:
            return self._data[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        if name == "_data":
            object.__setattr__(self, name, value)
        else:
            self._data[name] = value

    def get(self, key, default=None):
        return self._data.get(key, default)


@pytest.fixture
def fake_session(monkeypatch):
    """Replace streamlit.session_state with a _FakeSessionState."""
    import streamlit as st

    fake = _FakeSessionState()
    monkeypatch.setattr(st, "session_state", fake)
    return fake


@pytest.fixture
def mgr(fake_session):
    from frontend.managers.session_manager import SessionStateManager

    return SessionStateManager()


# ── Initialisation ──────────────────────────────────────────────────────


class TestInitialisation:
    def test_construction_creates_all_defaults(self, fake_session):
        from frontend.managers.session_manager import SessionStateManager

        SessionStateManager()
        assert fake_session["messages"] == []
        assert fake_session["deliverables"] == []
        assert fake_session["quality_feedback"] == {}
        assert fake_session["detected_type"] is None
        assert fake_session["detected_name"] is None
        assert fake_session["pending_prompt"] is None
        assert fake_session["last_failed_prompt"] is None

    def test_construction_preserves_existing_values(self, fake_session):
        from frontend.managers.session_manager import SessionStateManager

        fake_session["messages"] = [{"role": "user", "content": "hi"}]
        fake_session["quality_feedback"] = {"fb_1": "good"}
        SessionStateManager()
        assert fake_session["messages"] == [{"role": "user", "content": "hi"}]
        assert fake_session["quality_feedback"] == {"fb_1": "good"}

    def test_construction_idempotent(self, fake_session):
        from frontend.managers.session_manager import SessionStateManager

        mgr = SessionStateManager()
        mgr.add_message({"role": "user", "content": "first"})
        # A second construction must NOT wipe the state.
        mgr2 = SessionStateManager()
        assert mgr2.message_count() == 1


# ── Messages ────────────────────────────────────────────────────────────


class TestMessages:
    def test_add_message_appends(self, mgr, fake_session):
        mgr.add_message({"role": "user", "content": "a"})
        mgr.add_message({"role": "assistant", "content": "b"})
        assert mgr.message_count() == 2
        assert mgr.messages[0]["content"] == "a"
        assert mgr.messages[1]["content"] == "b"

    def test_add_message_enforces_limit(self, mgr):
        from frontend.managers.session_manager import MAX_CHAT_MESSAGES

        for i in range(MAX_CHAT_MESSAGES + 50):
            mgr.add_message({"role": "user", "content": str(i)})
        assert mgr.message_count() == MAX_CHAT_MESSAGES
        # Most recent messages are retained.
        assert mgr.messages[-1]["content"] == str(MAX_CHAT_MESSAGES + 49)
        assert mgr.messages[0]["content"] == str(50)

    def test_messages_property_returns_live_list(self, mgr, fake_session):
        mgr.add_message({"role": "user", "content": "x"})
        # The returned list is the same object stored in session_state, so
        # external readers (e.g. _save_chat_history) see updates.
        assert mgr.messages is fake_session["messages"]


# ── Deliverables ────────────────────────────────────────────────────────


class TestDeliverables:
    def test_add_deliverable_inserts_at_front(self, mgr):
        mgr.add_deliverable({"id": 1})
        mgr.add_deliverable({"id": 2})
        assert [d["id"] for d in mgr.deliverables] == [2, 1]

    def test_add_deliverable_enforces_limit(self, mgr):
        from frontend.managers.session_manager import MAX_DELIVERABLES

        for i in range(MAX_DELIVERABLES + 30):
            mgr.add_deliverable({"id": i})
        assert len(mgr.deliverables) == MAX_DELIVERABLES
        # Most recent inserts are retained (front of list).
        assert mgr.deliverables[0]["id"] == MAX_DELIVERABLES + 29

    def test_deliverables_property_returns_live_list(self, mgr, fake_session):
        mgr.add_deliverable({"id": 1})
        assert mgr.deliverables is fake_session["deliverables"]


# ── Quality feedback ────────────────────────────────────────────────────


class TestQualityFeedback:
    def test_set_and_get_feedback(self, mgr):
        assert mgr.get_feedback("task-1") is None
        mgr.set_feedback("task-1", "good")
        assert mgr.get_feedback("task-1") == "good"

    def test_has_feedback(self, mgr):
        assert mgr.has_feedback("task-1") is False
        mgr.set_feedback("task-1", "bad")
        assert mgr.has_feedback("task-1") is True

    def test_feedback_key_uses_fb_prefix(self, mgr, fake_session):
        mgr.set_feedback("abc", "good")
        assert fake_session["quality_feedback"] == {"fb_abc": "good"}

    def test_feedback_items_returns_tuples(self, mgr):
        mgr.set_feedback("a", "good")
        mgr.set_feedback("b", "bad")
        items = mgr.feedback_items()
        assert ("fb_a", "good") in items
        assert ("fb_b", "bad") in items

    def test_overwrite_feedback(self, mgr):
        mgr.set_feedback("t1", "good")
        mgr.set_feedback("t1", "bad")
        assert mgr.get_feedback("t1") == "bad"


# ── Detected persona ────────────────────────────────────────────────────


class TestDetectedPersona:
    def test_initially_none(self, mgr):
        assert mgr.detected_type is None
        assert mgr.detected_name is None

    def test_set_detected_updates_both(self, mgr, fake_session):
        mgr.set_detected("content_creator", "Writer")
        assert mgr.detected_type == "content_creator"
        assert mgr.detected_name == "Writer"
        assert fake_session["detected_type"] == "content_creator"
        assert fake_session["detected_name"] == "Writer"


# ── Pending / failed prompts ────────────────────────────────────────────


class TestPendingAndFailedPrompts:
    def test_set_and_pop_pending_prompt(self, mgr):
        assert mgr.pop_pending_prompt() is None
        mgr.set_pending_prompt("hello")
        assert mgr.pop_pending_prompt() == "hello"
        # pop removes the value.
        assert mgr.pop_pending_prompt() is None

    def test_set_and_pop_last_failed_prompt(self, mgr):
        assert mgr.pop_last_failed_prompt() is None
        mgr.set_last_failed_prompt("retry me")
        assert mgr.pop_last_failed_prompt() == "retry me"
        assert mgr.pop_last_failed_prompt() is None

    def test_pending_prompt_persisted_in_session(self, mgr, fake_session):
        mgr.set_pending_prompt("x")
        assert fake_session["pending_prompt"] == "x"

    def test_last_failed_prompt_persisted_in_session(self, mgr, fake_session):
        mgr.set_last_failed_prompt("y")
        assert fake_session["last_failed_prompt"] == "y"


# ── Backward compatibility with flat keys ───────────────────────────────


class TestBackwardCompatibility:
    """Other components (app.py, deliverables_renderer.py,
    base_router._save_chat_history) read st.session_state.messages /
    deliverables / quality_feedback directly. The manager must keep those
    flat keys in sync rather than moving state into a nested object."""

    def test_messages_key_remains_flat(self, mgr, fake_session):
        mgr.add_message({"role": "user", "content": "flat?"})
        assert "messages" in fake_session
        assert fake_session["messages"][0]["content"] == "flat?"

    def test_deliverables_key_remains_flat(self, mgr, fake_session):
        mgr.add_deliverable({"id": 1})
        assert "deliverables" in fake_session
        assert fake_session["deliverables"][0]["id"] == 1

    def test_quality_feedback_key_remains_flat(self, mgr, fake_session):
        mgr.set_feedback("t", "good")
        assert "quality_feedback" in fake_session
        assert "fb_t" in fake_session["quality_feedback"]


# ── Constants ───────────────────────────────────────────────────────────


class TestConstants:
    def test_max_chat_messages_value(self):
        from frontend.managers.session_manager import MAX_CHAT_MESSAGES

        assert MAX_CHAT_MESSAGES == 100

    def test_max_deliverables_value(self):
        from frontend.managers.session_manager import MAX_DELIVERABLES

        assert MAX_DELIVERABLES == 50
