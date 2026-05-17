"""
Real Progress Integration Tests — End-to-end progress event system validation.

Covers:
- TaskEngineV3 emits correct event sequence during execute()
- Frontend reads real progress from ProgressEmitter history
- Error state handling and propagation
- Session isolation (events don't leak between sessions)
- Backward compatibility (graceful degradation when unavailable)
- Phase icon mapping correctness
- Timeline visualization logic
- _get_phase_from_event() utility function
- Edge cases: empty history, missing fields, invalid session IDs

Run command:
    pytest tests/test_real_progress.py -v --tb=short
"""

import time
import pytest
from unittest.mock import Mock, patch, MagicMock

from opc_manager.progress_emitter import (
    EventType,
    ProgressEvent,
    ProgressEmitter,
)
from opc_manager.task_engine_v3 import TaskEngineV3


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


@pytest.fixture
def engine():
    """Provide a fresh TaskEngineV3 instance."""
    return TaskEngineV3()


class TestTaskEngineEventSequence:
    """Test suite for TaskEngineV3.execute() event emission sequence."""

    def test_execute_emits_plan_start(self, engine):
        """execute() should emit PLAN_START at the beginning."""
        sid = "a" * 32
        mock_ctx = Mock()
        mock_ctx._session_id = sid
        mock_ctx.get_turn_count.return_value = 0

        with patch.object(engine, '_execute_general_chat') as mock_exec:
            mock_exec.return_value = Mock(
                success=True,
                content="test",
                task_type=Mock(value="general_chat"),
                sources=[],
            )
            engine.execute("hello", session_ctx=mock_ctx)

        emitter = ProgressEmitter()
        history = emitter.get_history(sid)
        assert len(history) >= 1
        assert history[0]["event"] == "plan_start"
        assert history[0]["progress"] == 0

    def test_execute_emits_intent_detected(self, engine):
        """execute() should emit INTENT_DETECTED after intent classification."""
        sid = "b" * 32
        mock_ctx = Mock()
        mock_ctx._session_id = sid
        mock_ctx.get_turn_count.return_value = 0

        with patch.object(engine, '_execute_general_chat') as mock_exec:
            mock_exec.return_value = Mock(
                success=True,
                content="test",
                task_type=Mock(value="general_chat"),
                sources=[],
            )
            engine.execute("hello", session_ctx=mock_ctx)

        emitter = ProgressEmitter()
        history = emitter.get_history(sid)
        intent_events = [e for e in history if e["event"] == "intent_detected"]
        assert len(intent_events) >= 1
        assert "意图识别" in intent_events[0]["message"]

    def test_execute_emits_step_start_and_complete(self, engine):
        """execute() should emit STEP_START and STEP_COMPLETE around execution."""
        sid = "c" * 32
        mock_ctx = Mock()
        mock_ctx._session_id = sid
        mock_ctx.get_turn_count.return_value = 0

        with patch.object(engine, '_execute_general_chat') as mock_exec:
            mock_exec.return_value = Mock(
                success=True,
                content="test",
                task_type=Mock(value="general_chat"),
                sources=[],
            )
            engine.execute("hello", session_ctx=mock_ctx)

        emitter = ProgressEmitter()
        history = emitter.get_history(sid)
        step_starts = [e for e in history if e["event"] == "step_start"]
        step_completes = [e for e in history if e["event"] == "step_complete"]
        assert len(step_starts) >= 1
        assert len(step_completes) >= 1

    def test_execute_emits_complete_on_success(self, engine):
        """execute() should emit COMPLETE with 100% on success."""
        sid = "d" * 32
        mock_ctx = Mock()
        mock_ctx._session_id = sid
        mock_ctx.get_turn_count.return_value = 0

        with patch.object(engine, '_execute_general_chat') as mock_exec:
            mock_exec.return_value = Mock(
                success=True,
                content="test",
                task_type=Mock(value="general_chat"),
                sources=[],
            )
            engine.execute("hello", session_ctx=mock_ctx)

        emitter = ProgressEmitter()
        history = emitter.get_history(sid)
        complete_events = [e for e in history if e["event"] == "complete"]
        assert len(complete_events) >= 1
        assert complete_events[-1]["progress"] == 100

    def test_execute_emits_error_on_exception(self, engine):
        """execute() should emit ERROR when exception occurs."""
        sid = "e" * 32
        mock_ctx = Mock()
        mock_ctx._session_id = sid
        mock_ctx.get_turn_count.return_value = 0

        with patch.object(engine, '_execute_general_chat') as mock_exec:
            mock_exec.side_effect = RuntimeError("test error")
            result = engine.execute("hello", session_ctx=mock_ctx)

        assert result.success is False

        emitter = ProgressEmitter()
        history = emitter.get_history(sid)
        error_events = [e for e in history if e["event"] == "error"]
        assert len(error_events) >= 1
        assert "test error" in error_events[0]["message"]

    def test_execute_emits_error_on_validation_failure(self, engine):
        """execute() should emit ERROR on input validation failure."""
        sid = "f" * 32
        mock_ctx = Mock()
        mock_ctx._session_id = sid
        mock_ctx.get_turn_count.return_value = 0

        with patch('opc_manager.task_engine_v3.InputValidator.sanitize') as mock_sanitize:
            mock_sanitize.return_value = (None, "validation failed")
            engine.execute("", session_ctx=mock_ctx)

        emitter = ProgressEmitter()
        history = emitter.get_history(sid)
        error_events = [e for e in history if e["event"] == "error"]
        assert len(error_events) >= 1
        assert "输入校验失败" in error_events[0]["message"]

    def test_execute_event_order_is_correct(self, engine):
        """Events should be emitted in correct order: plan -> intent -> step -> complete."""
        sid = "g" * 32
        mock_ctx = Mock()
        mock_ctx._session_id = sid
        mock_ctx.get_turn_count.return_value = 0

        with patch.object(engine, '_execute_general_chat') as mock_exec:
            mock_exec.return_value = Mock(
                success=True,
                content="test",
                task_type=Mock(value="general_chat"),
                sources=[],
            )
            engine.execute("hello", session_ctx=mock_ctx)

        emitter = ProgressEmitter()
        history = emitter.get_history(sid)
        event_types = [e["event"] for e in history]

        assert event_types[0] == "plan_start"
        assert "intent_detected" in event_types
        assert "step_start" in event_types
        assert "step_complete" in event_types
        assert event_types[-1] == "complete"

        plan_idx = event_types.index("plan_start")
        intent_idx = event_types.index("intent_detected")
        step_start_idx = event_types.index("step_start")
        step_complete_idx = event_types.index("step_complete")
        complete_idx = event_types.index("complete")

        assert plan_idx < intent_idx < step_start_idx < step_complete_idx < complete_idx


class TestFrontendHistoryReading:
    """Test suite for frontend reading real progress from ProgressEmitter."""

    def test_frontend_reads_latest_event(self, emitter):
        """Frontend should read latest event from history."""
        sid = "h" * 32
        emitter.emit(ProgressEvent(
            event_type=EventType.PLAN_START,
            session_id=sid,
            message="start",
            progress_pct=0,
        ))
        emitter.emit(ProgressEvent(
            event_type=EventType.STEP_PROGRESS,
            session_id=sid,
            message="progressing",
            progress_pct=50,
        ))

        history = emitter.get_history(sid)
        latest = history[-1]
        assert latest["event"] == "step_progress"
        assert latest["progress"] == 50
        assert latest["message"] == "progressing"

    def test_frontend_handles_empty_history(self, emitter):
        """Frontend should handle empty history gracefully."""
        sid = "i" * 32
        history = emitter.get_history(sid)
        assert history == []

    def test_frontend_extracts_progress_pct(self, emitter):
        """Frontend should extract progress_pct from event."""
        sid = "j" * 32
        emitter.emit(ProgressEvent(
            event_type=EventType.STEP_PROGRESS,
            session_id=sid,
            message="75%",
            progress_pct=75,
        ))

        history = emitter.get_history(sid)
        latest = history[-1]
        progress = latest.get("progress", latest.get("progress_pct"))
        assert progress == 75

    def test_frontend_handles_missing_progress(self, emitter):
        """Frontend should handle events without progress_pct."""
        sid = "k" * 32
        emitter.emit(ProgressEvent(
            event_type=EventType.PLAN_START,
            session_id=sid,
            message="starting",
        ))

        history = emitter.get_history(sid)
        latest = history[-1]
        progress = latest.get("progress", latest.get("progress_pct"))
        assert progress is None

    def test_frontend_gets_event_message(self, emitter):
        """Frontend should get message from latest event."""
        sid = "l" * 32
        test_msg = "🔍 意图识别: content_generation"
        emitter.emit(ProgressEvent(
            event_type=EventType.INTENT_DETECTED,
            session_id=sid,
            message=test_msg,
            progress_pct=10,
        ))

        history = emitter.get_history(sid)
        latest = history[-1]
        assert latest["message"] == test_msg


class TestErrorStateHandling:
    """Test suite for error state handling and display."""

    def test_error_event_has_correct_format(self, emitter):
        """Error event should have proper format."""
        sid = "m" * 32
        emitter.emit(ProgressEvent(
            event_type=EventType.ERROR,
            session_id=sid,
            message="❌ 执行异常: RuntimeError",
        ))

        history = emitter.get_history(sid)
        error_event = history[-1]
        assert error_event["event"] == "error"
        assert "❌" in error_event["message"]
        assert "RuntimeError" in error_event["message"]

    def test_error_does_not_have_progress(self, emitter):
        """Error events typically don't have progress percentage."""
        sid = "n" * 32
        emitter.emit(ProgressEvent(
            event_type=EventType.ERROR,
            session_id=sid,
            message="error occurred",
        ))

        history = emitter.get_history(sid)
        error_event = history[-1]
        assert "progress" not in error_event or error_event.get("progress") is None

    def test_multiple_errors_accumulate(self, emitter):
        """Multiple errors should all be recorded."""
        sid = "o" * 32
        emitter.emit(ProgressEvent(
            event_type=EventType.ERROR,
            session_id=sid,
            message="error 1",
        ))
        emitter.emit(ProgressEvent(
            event_type=EventType.ERROR,
            session_id=sid,
            message="error 2",
        ))

        history = emitter.get_history(sid)
        errors = [e for e in history if e["event"] == "error"]
        assert len(errors) == 2

    def test_error_after_complete_is_recorded(self, emitter):
        """Error emitted after complete should still be recorded."""
        sid = "p" * 32
        emitter.emit(ProgressEvent(
            event_type=EventType.COMPLETE,
            session_id=sid,
            message="done",
            progress_pct=100,
        ))
        emitter.emit(ProgressEvent(
            event_type=EventType.ERROR,
            session_id=sid,
            message="post-error",
        ))

        history = emitter.get_history(sid)
        assert len(history) == 2
        assert history[-1]["event"] == "error"


class TestSessionIsolation:
    """Test suite for session isolation - events don't leak between sessions."""

    def test_events_isolated_between_sessions(self, emitter):
        """Events from one session should not appear in another."""
        sid1 = "q" * 32
        sid2 = "r" * 32

        emitter.emit(ProgressEvent(
            event_type=EventType.PLAN_START,
            session_id=sid1,
            message="session 1 start",
        ))
        emitter.emit(ProgressEvent(
            event_type=EventType.PLAN_START,
            session_id=sid2,
            message="session 2 start",
        ))

        history1 = emitter.get_history(sid1)
        history2 = emitter.get_history(sid2)

        assert len(history1) == 1
        assert len(history2) == 1
        assert history1[0]["session_id"] == sid1
        assert history2[0]["session_id"] == sid2
        assert "session 1" in history1[0]["message"]
        assert "session 2" in history2[0]["message"]

    def test_clear_history_only_affects_one_session(self, emitter):
        """clear_history() should only affect specified session."""
        sid1 = "s" * 32
        sid2 = "t" * 32

        emitter.emit(ProgressEvent(
            event_type=EventType.STEP_PROGRESS,
            session_id=sid1,
            message="progress 1",
        ))
        emitter.emit(ProgressEvent(
            event_type=EventType.STEP_PROGRESS,
            session_id=sid2,
            message="progress 2",
        ))

        emitter.clear_history(sid1)

        assert emitter.get_history(sid1) == []
        assert len(emitter.get_history(sid2)) == 1

    def test_different_sessions_can_have_different_progress(self, emitter):
        """Different sessions can be at different progress levels."""
        sid1 = "u" * 32
        sid2 = "v" * 32

        emitter.emit(ProgressEvent(
            event_type=EventType.STEP_PROGRESS,
            session_id=sid1,
            message="25%",
            progress_pct=25,
        ))
        emitter.emit(ProgressEvent(
            event_type=EventType.STEP_PROGRESS,
            session_id=sid2,
            message="75%",
            progress_pct=75,
        ))

        history1 = emitter.get_history(sid1)
        history2 = emitter.get_history(sid2)

        assert history1[-1]["progress"] == 25
        assert history2[-1]["progress"] == 75


class TestBackwardCompatibility:
    """Test suite for backward compatibility and graceful degradation."""

    def test_emit_progress_with_none_session_id(self, engine):
        """_emit_progress should handle None session_id gracefully."""
        engine._emit_progress(None, EventType.PLAN_START, "test")

    def test_emit_progress_with_empty_session_id(self, engine):
        """_emit_progress should handle empty session_id gracefully."""
        engine._emit_progress("", EventType.PLAN_START, "test")

    def test_emit_progress_without_progress_emitter(self, engine):
        """_emit_progress should work even if ProgressEmitter is unavailable."""
        original_available = engine.__class__.__module__._PROGRESS_EMITTER_AVAILABLE if hasattr(engine.__class__, '_PROGRESS_EMITTER_AVAILABLE') else True
        try:
            with patch.dict('sys.modules', {'opc_manager.progress_emitter': None}):
                engine._emit_progress("x" * 32, EventType.PLAN_START, "test")
        except Exception:
            pass

    def test_execute_without_session_ctx_still_works(self, engine):
        """execute() should work without session_ctx (no events emitted)."""
        with patch.object(engine, '_execute_general_chat') as mock_exec:
            mock_exec.return_value = Mock(
                success=True,
                content="test",
                task_type=Mock(value="general_chat"),
                sources=[],
            )
            result = engine.execute("hello")

        assert result.success is True

    def test_execute_with_session_ctx_without_session_id(self, engine):
        """execute() should work with session_ctx that has no session_id."""
        mock_ctx = Mock()
        mock_ctx.get_turn_count.return_value = 0
        if hasattr(mock_ctx, '_session_id'):
            delattr(mock_ctx, '_session_id')
        if hasattr(mock_ctx, 'session_id'):
            delattr(mock_ctx, 'session_id')

        with patch.object(engine, '_execute_general_chat') as mock_exec:
            mock_exec.return_value = Mock(
                success=True,
                content="test",
                task_type=Mock(value="general_chat"),
                sources=[],
            )
            result = engine.execute("hello", session_ctx=mock_ctx)

        assert result.success is True


class TestPhaseIconMapping:
    """Test suite for phase icon mapping functions."""

    def test_plan_start_icon(self):
        """PLAN_START should map to 🚀 icon."""
        from frontend.components.shared import _get_phase_icon
        assert _get_phase_icon("plan_start") == "🚀"

    def test_intent_detected_icon(self):
        """INTENT_DETECTED should map to 🔍 icon."""
        from frontend.components.shared import _get_phase_icon
        assert _get_phase_icon("intent_detected") == "🔍"

    def test_step_progress_icon(self):
        """STEP_PROGRESS should map to ⚡ icon."""
        from frontend.components.shared import _get_phase_icon
        assert _get_phase_icon("step_progress") == "⚡"

    def test_complete_icon(self):
        """COMPLETE should map to ✅ icon."""
        from frontend.components.shared import _get_phase_icon
        assert _get_phase_icon("complete") == "✅"

    def test_error_icon(self):
        """ERROR should map to ❌ icon."""
        from frontend.components.shared import _get_phase_icon
        assert _get_phase_icon("error") == "❌"

    def test_unknown_event_returns_default_icon(self):
        """Unknown event type should return default 📌 icon."""
        from frontend.components.shared import _get_phase_icon
        assert _get_phase_icon("unknown_event") == "📌"


class TestGetPhaseFromEvent:
    """Test suite for _get_phase_from_event() utility function."""

    def test_plan_start_phase(self):
        """PLAN_START should return (🚀, 任务启动)."""
        from frontend.components.shared import _get_phase_from_event
        icon, name = _get_phase_from_event("plan_start")
        assert icon == "🚀"
        assert name == "任务启动"

    def test_intent_detected_phase(self):
        """INTENT_DETECTED should return (🔍, 意图识别)."""
        from frontend.components.shared import _get_phase_from_event
        icon, name = _get_phase_from_event("intent_detected")
        assert icon == "🔍"
        assert name == "意图识别"

    def test_step_start_phase(self):
        """STEP_START should return (⚡, 执行中)."""
        from frontend.components.shared import _get_phase_from_event
        icon, name = _get_phase_from_event("step_start")
        assert icon == "⚡"
        assert name == "执行中"

    def test_complete_phase(self):
        """COMPLETE should return (✅, 任务完成)."""
        from frontend.components.shared import _get_phase_from_event
        icon, name = _get_phase_from_event("complete")
        assert icon == "✅"
        assert name == "任务完成"

    def test_error_phase(self):
        """ERROR should return (❌, 执行错误)."""
        from frontend.components.shared import _get_phase_from_event
        icon, name = _get_phase_from_event("error")
        assert icon == "❌"
        assert name == "执行错误"

    def test_unknown_event_returns_default(self):
        """Unknown event should return default (⚡, 执行中)."""
        from frontend.components.shared import _get_phase_from_event
        icon, name = _get_phase_from_event("unknown")
        assert icon == "⚡"
        assert name == "执行中"

    def test_case_insensitive_matching(self):
        """Should match case-insensitively."""
        from frontend.components.shared import _get_phase_from_event
        icon1, name1 = _get_phase_from_event("PLAN_START")
        icon2, name2 = _get_phase_from_event("plan_start")
        assert icon1 == icon2
        assert name1 == name2

    def test_hyphen_to_underscore_conversion(self):
        """Should convert hyphens to underscores."""
        from frontend.components.shared import _get_phase_from_event
        icon1, name1 = _get_phase_from_event("step-start")
        icon2, name2 = _get_phase_from_event("step_start")
        assert icon1 == icon2
        assert name1 == name2


class TestTimelineVisualization:
    """Test suite for timeline visualization logic."""

    def test_timeline_shows_completed_phases(self, emitter):
        """Timeline should show completed phases as success."""
        sid = "w" * 32
        emitter.emit(ProgressEvent(
            event_type=EventType.PLAN_START,
            session_id=sid,
            message="start",
            progress_pct=0,
        ))
        emitter.emit(ProgressEvent(
            event_type=EventType.INTENT_DETECTED,
            session_id=sid,
            message="intent",
            progress_pct=10,
        ))

        history = emitter.get_history(sid)
        completed = {evt["event"] for evt in history}
        assert "plan_start" in completed
        assert "intent_detected" in completed

    def test_timeline_identifies_current_phase(self, emitter):
        """Timeline should identify current phase correctly."""
        sid = "x" * 32
        emitter.emit(ProgressEvent(
            event_type=EventType.PLAN_START,
            session_id=sid,
            message="start",
        ))
        emitter.emit(ProgressEvent(
            event_type=EventType.STEP_START,
            session_id=sid,
            message="executing",
            progress_pct=50,
        ))

        history = emitter.get_history(sid)
        assert history[-1]["event"] == "step_start"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
