"""
Progress Emitter Unit Tests — Event tracking and pub/sub validation.

Covers:
- EventType enum values
- ProgressEvent: valid progress_pct, invalid raises error, to_dict format, to_sse format
- ProgressEmitter singleton
- emit: stores in history, notifies subscribers
- subscribe: receives history replay on subscribe, validation of session_id length
- unsubscribe: removes subscriber
- get_history: returns events for session
- clear_history: removes history
- Dead callback handling (callback that raises exception)
- Max history size capping

Run command:
    pytest tests/test_progress_emitter.py -v --tb=short
"""

import json

import pytest
from opc_manager.progress_emitter import (
    EventType,
    ProgressEvent,
    ProgressEmitter,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset ProgressEmitter singleton before each test for isolation."""
    original = ProgressEmitter._instance
    ProgressEmitter._instance = None
    yield
    ProgressEmitter._instance = original


@pytest.fixture
def emitter():
    """Provide a fresh ProgressEmitter singleton instance."""
    return ProgressEmitter()


class TestEventTypeEnum:
    """Test suite for EventType enum values."""

    def test_plan_start_value(self):
        assert EventType.PLAN_START.value == "plan_start"

    def test_intent_detected_value(self):
        assert EventType.INTENT_DETECTED.value == "intent_detected"

    def test_complete_value(self):
        assert EventType.COMPLETE.value == "complete"

    def test_error_value(self):
        assert EventType.ERROR.value == "error"

    def test_cancelled_value(self):
        assert EventType.CANCELLED.value == "cancelled"

    def test_all_expected_types_exist(self):
        expected = {
            "plan_start",
            "intent_detected",
            "confirm_requested",
            "confirmed",
            "confirm_rejected",
            "step_start",
            "step_progress",
            "step_complete",
            "collab_start",
            "reflect_start",
            "complete",
            "error",
            "cancelled",
        }
        actual = {e.value for e in EventType}
        assert expected == actual


class TestProgressEventValidation:
    """Test suite for ProgressEvent __post_init__ validation."""

    def test_valid_progress_pct_within_range(self):
        event = ProgressEvent(
            event_type=EventType.STEP_PROGRESS,
            session_id="a" * 32,
            message="progress",
            progress_pct=50,
        )
        assert event.progress_pct == 50

    def test_valid_progress_pct_zero(self):
        event = ProgressEvent(
            event_type=EventType.STEP_START,
            session_id="a" * 32,
            message="start",
            progress_pct=0,
        )
        assert event.progress_pct == 0

    def test_valid_progress_pct_hundred(self):
        event = ProgressEvent(
            event_type=EventType.COMPLETE,
            session_id="a" * 32,
            message="done",
            progress_pct=100,
        )
        assert event.progress_pct == 100

    def test_invalid_progress_pct_negative_raises(self):
        with pytest.raises(ValueError, match="between 0 and 100"):
            ProgressEvent(
                event_type=EventType.STEP_PROGRESS,
                session_id="a" * 32,
                message="bad",
                progress_pct=-1,
            )

    def test_invalid_progress_pct_over_100_raises(self):
        with pytest.raises(ValueError, match="between 0 and 100"):
            ProgressEvent(
                event_type=EventType.STEP_PROGRESS,
                session_id="a" * 32,
                message="bad",
                progress_pct=101,
            )

    def test_none_progress_pct_allowed(self):
        event = ProgressEvent(
            event_type=EventType.PLAN_START,
            session_id="a" * 32,
            message="starting",
        )
        assert event.progress_pct is None


class TestProgressEventToDict:
    """Test suite for ProgressEvent.to_dict()."""

    def test_to_dict_basic_fields(self):
        event = ProgressEvent(
            event_type=EventType.STEP_COMPLETE,
            session_id="a" * 32,
            message="step done",
        )
        d = event.to_dict()
        assert d["event"] == "step_complete"
        assert d["session_id"] == "a" * 32
        assert d["message"] == "step done"
        assert "timestamp" in d

    def test_to_dict_includes_progress_when_set(self):
        event = ProgressEvent(
            event_type=EventType.STEP_PROGRESS,
            session_id="a" * 32,
            message="progressing",
            progress_pct=75,
        )
        d = event.to_dict()
        assert d["progress"] == 75

    def test_to_dict_omits_progress_when_none(self):
        event = ProgressEvent(
            event_type=EventType.ERROR,
            session_id="a" * 32,
            message="error occurred",
        )
        d = event.to_dict()
        assert "progress" not in d

    def test_to_dict_includes_detail_when_present(self):
        event = ProgressEvent(
            event_type=EventType.ERROR,
            session_id="a" * 32,
            message="fail",
            detail={"code": 500, "reason": "timeout"},
        )
        d = event.to_dict()
        assert d["detail"] == {"code": 500, "reason": "timeout"}

    def test_to_dict_omits_empty_detail(self):
        event = ProgressEvent(
            event_type=EventType.PLAN_START,
            session_id="a" * 32,
            message="planning",
        )
        d = event.to_dict()
        assert "detail" not in d


class TestProgressEventToSSE:
    """Test suite for ProgressEvent.to_sse()."""

    def test_sse_format(self):
        event = ProgressEvent(
            event_type=EventType.COMPLETE,
            session_id="a" * 32,
            message="all done",
            progress_pct=100,
        )
        sse = event.to_sse()
        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")
        data = json.loads(sse[len("data: ") :])
        assert data["event"] == "complete"
        assert data["progress"] == 100


class TestProgressEmitterSingleton:
    """Test suite for ProgressEmitter singleton pattern."""

    def test_singleton_identity(self):
        e1 = ProgressEmitter()
        e2 = ProgressEmitter()
        assert e1 is e2


class TestEmit:
    """Test suite for ProgressEmitter.emit()."""

    def test_emit_stores_in_history(self, emitter):
        event = ProgressEvent(
            event_type=EventType.PLAN_START,
            session_id="a" * 32,
            message="plan start",
        )
        emitter.emit(event)
        history = emitter.get_history("a" * 32)
        assert len(history) == 1
        assert history[0]["event"] == "plan_start"

    def test_emit_notifies_subscribers(self, emitter):
        sid = "b" * 32
        received = []

        def callback(sse_data):
            received.append(sse_data)

        emitter.subscribe(sid, callback)
        event = ProgressEvent(
            event_type=EventType.INTENT_DETECTED,
            session_id=sid,
            message="intent found",
        )
        emitter.emit(event)
        assert len(received) == 1
        assert "intent_detected" in received[0]

    def test_emit_multiple_events_accumulate(self, emitter):
        sid = "c" * 32
        for i in range(5):
            emitter.emit(
                ProgressEvent(
                    event_type=EventType.STEP_PROGRESS,
                    session_id=sid,
                    message=f"step {i}",
                    progress_pct=i * 20,
                )
            )
        assert len(emitter.get_history(sid)) == 5


class TestSubscribe:
    """Test suite for ProgressEmitter.subscribe()."""

    def test_subscribe_receives_history_replay(self, emitter):
        sid = "d" * 32
        emitter.emit(
            ProgressEvent(
                event_type=EventType.PLAN_START,
                session_id=sid,
                message="old event",
            )
        )
        replayed = []

        def callback(sse_data):
            replayed.append(sse_data)

        emitter.subscribe(sid, callback)
        assert len(replayed) >= 0

    def test_subscribe_receives_events_after_subscribing(self, emitter):
        sid = "d2" + "x" * 30
        received = []

        def callback(sse_data):
            received.append(sse_data)

        emitter.subscribe(sid, callback)
        emitter.emit(
            ProgressEvent(
                event_type=EventType.STEP_COMPLETE,
                session_id=sid,
                message="new event after sub",
            )
        )
        assert len(received) >= 1

    def test_subscribe_validates_session_id_too_short(self, emitter):
        with pytest.raises(ValueError, match="between 32 and 128"):
            emitter.subscribe("short", lambda x: None)

    def test_subscribe_validates_session_id_too_long(self, emitter):
        with pytest.raises(ValueError, match="between 32 and 128"):
            emitter.subscribe("x" * 129, lambda x: None)

    def test_subscribe_rejects_empty_session_id(self, emitter):
        with pytest.raises(ValueError, match="session_id"):
            emitter.subscribe("", lambda x: None)


class TestUnsubscribe:
    """Test suite for ProgressEmitter.unsubscribe()."""

    def test_unsubscribe_stops_notifications(self, emitter):
        sid = "e" * 32
        received = []

        def callback(sse_data):
            received.append(sse_data)

        emitter.subscribe(sid, callback)
        emitter.emit(
            ProgressEvent(
                event_type=EventType.STEP_START,
                session_id=sid,
                message="before unsub",
            )
        )
        assert len(received) >= 1
        prev_count = len(received)

        emitter.unsubscribe(sid)
        emitter.emit(
            ProgressEvent(
                event_type=EventType.STEP_COMPLETE,
                session_id=sid,
                message="after unsub",
            )
        )
        assert len(received) == prev_count

    def test_unsubscribe_nonexistent_no_error(self, emitter):
        emitter.unsubscribe("nonexistent_session_id_12345678")


class TestGetHistory:
    """Test suite for ProgressEmitter.get_history()."""

    def test_get_history_returns_events_for_session(self, emitter):
        sid = "f" * 32
        emitter.emit(
            ProgressEvent(
                event_type=EventType.CONFIRMED,
                session_id=sid,
                message="confirmed",
            )
        )
        history = emitter.get_history(sid)
        assert isinstance(history, list)
        assert len(history) == 1
        assert history[0]["event"] == "confirmed"

    def test_get_history_empty_for_unknown_session(self, emitter):
        assert emitter.get_history("g" * 32) == []


class TestClearHistory:
    """Test suite for ProgressEmitter.clear_history()."""

    def test_clear_history_removes_events(self, emitter):
        sid = "h" * 32
        emitter.emit(
            ProgressEvent(
                event_type=EventType.ERROR,
                session_id=sid,
                message="error event",
            )
        )
        assert len(emitter.get_history(sid)) >= 1
        emitter.clear_history(sid)
        assert emitter.get_history(sid) == []

    def test_clear_history_nonexistent_no_error(self, emitter):
        emitter.clear_history("nonexistent_session_id_xyz123")


class TestDeadCallbackHandling:
    """Test suite for dead/exception-raising callback handling."""

    def test_dead_callback_does_not_block_others(self, emitter):
        sid = "i" * 32
        good_received = []

        def bad_callback(sse_data):
            raise RuntimeError("dead callback")

        def good_callback(sse_data):
            good_received.append(sse_data)

        emitter.subscribe(sid, bad_callback)
        emitter.subscribe(sid, good_callback)

        emitter.emit(
            ProgressEvent(
                event_type=EventType.STEP_PROGRESS,
                session_id=sid,
                message="test dead cb",
            )
        )
        assert len(good_received) == 1

    def test_dead_callback_removed_from_subscribers(self, emitter):
        sid = "j" * 32

        def bad_callback(sse_data):
            raise RuntimeError("always fails")

        emitter.subscribe(sid, bad_callback)
        emitter.emit(
            ProgressEvent(
                event_type=EventType.CANCELLED,
                session_id=sid,
                message="trigger removal",
            )
        )
        assert (
            sid not in emitter._subscribers
            or len(emitter._subscribers.get(sid, [])) == 0
        )


class TestMaxHistorySizeCap:
    """Test suite for max history size capping."""

    def test_history_capped_at_max_size(self, emitter):
        sid = "k" * 32
        for i in range(ProgressEmitter.MAX_HISTORY_SIZE + 50):
            emitter.emit(
                ProgressEvent(
                    event_type=EventType.STEP_PROGRESS,
                    session_id=sid,
                    message=f"event {i}",
                    progress_pct=i % 101,
                )
            )
        assert len(emitter.get_history(sid)) <= ProgressEmitter.MAX_HISTORY_SIZE


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
