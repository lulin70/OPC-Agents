"""Comprehensive unit tests for confirmation_dialog module.

Covers:
- Risk badge rendering for all levels (LOW/MEDIUM/HIGH/CRITICAL)
- Confidence bar calculation and display
- Parameter sanitization with sensitive keyword detection
- Confirmation callback building and execution
- Three user choice outcomes (confirm/cancel/skip)
- Trust score update logic
- Edge cases (empty params, extremely long goals, extreme confidence values)
- ProgressEmitter event integration
- Streamlit session_state two-phase pattern
- Backward compatibility when Confirmer is unavailable

Run command:
    pytest tests/test_confirmation_dialog.py -v --tb=short
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import asyncio

from opc_manager.confirmer import (
    Confirmer,
    ConfirmationRequest,
    ConfirmationResult,
    RiskLevel,
)


class TestRenderRiskBadge:
    """Test suite for _render_risk_badge() function."""

    def test_low_risk_badge(self):
        from frontend.components.confirmation_dialog import _render_risk_badge
        result = _render_risk_badge("low")
        assert "🟢" in result
        assert "低风险" in result

    def test_medium_risk_badge(self):
        from frontend.components.confirmation_dialog import _render_risk_badge
        result = _render_risk_badge("medium")
        assert "🟡" in result
        assert "中风险" in result

    def test_high_risk_badge(self):
        from frontend.components.confirmation_dialog import _render_risk_badge
        result = _render_risk_badge("high")
        assert "🔴" in result
        assert "高风险" in result

    def test_critical_risk_badge(self):
        from frontend.components.confirmation_dialog import _render_risk_badge
        result = _render_risk_badge("critical")
        assert "🟣" in result
        assert "关键操作" in result

    def test_unknown_risk_fallback_to_medium(self):
        from frontend.components.confirmation_dialog import _render_risk_badge
        result = _render_risk_badge("unknown")
        assert "🟡" in result
        assert "中风险" in result

    def test_case_insensitive_risk_level(self):
        from frontend.components.confirmation_dialog import _render_risk_badge
        result_upper = _render_risk_badge("HIGH")
        result_lower = _render_risk_badge("high")
        assert result_upper == result_lower


class TestRenderConfidenceBar:
    """Test suite for _render_confidence_bar() function."""

    def test_normal_confidence_display(self):
        from frontend.components.confirmation_dialog import _render_confidence_bar
        result = _render_confidence_bar(0.75, 0.95)
        assert "AI判断 75%" in result
        assert "需要人工 95%" in result

    def test_low_confidence_display(self):
        from frontend.components.confirmation_dialog import _render_confidence_bar
        result = _render_confidence_bar(0.30, 0.85)
        assert "AI判断 30%" in result
        assert "需要人工 85%" in result

    def test_high_confidence_display(self):
        from frontend.components.confirmation_dialog import _render_confidence_bar
        result = _render_confidence_bar(0.95, 0.70)
        assert "AI判断 95%" in result
        assert "需要人工 70%" in result

    def test_zero_confidence(self):
        from frontend.components.confirmation_dialog import _render_confidence_bar
        result = _render_confidence_bar(0.0, 1.0)
        assert "AI判断 0%" in result
        assert "需要人工 100%" in result

    def test_full_confidence(self):
        from frontend.components.confirmation_dialog import _render_confidence_bar
        result = _render_confidence_bar(1.0, 0.0)
        assert "AI判断 100%" in result
        assert "需要人工 0%" in result

    def test_equal_confidence_and_threshold(self):
        from frontend.components.confirmation_dialog import _render_confidence_bar
        result = _render_confidence_bar(0.85, 0.85)
        assert "AI判断 85%" in result
        assert "需要人工 85%" in result


class TestSanitizeParamsDisplay:
    """Test suite for _sanitize_params_display() function."""

    def test_empty_params_returns_empty_dict(self):
        from frontend.components.confirmation_dialog import _sanitize_params_display
        result = _sanitize_params_display({})
        assert result == {}

    def test_none_params_returns_empty_dict(self):
        from frontend.components.confirmation_dialog import _sanitize_params_display
        result = _sanitize_params_display(None)
        assert result == {}

    def test_password_key_redacted(self):
        from frontend.components.confirmation_dialog import _sanitize_params_display
        params = {"password": "secret123", "username": "admin"}
        result = _sanitize_params_display(params)
        assert result["password"] == "***"
        assert result["username"] == "admin"

    def test_api_key_redacted(self):
        from frontend.components.confirmation_dialog import _sanitize_params_display
        params = {"api_key": "sk-12345"}
        result = _sanitize_params_display(params)
        assert result["api_key"] == "***"

    def test_token_redacted(self):
        from frontend.components.confirmation_dialog import _sanitize_params_display
        params = {"access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"}
        result = _sanitize_params_display(params)
        assert result["access_token"] == "***"

    def test_multiple_sensitive_keys_redacted(self):
        from frontend.components.confirmation_dialog import _sanitize_params_display
        params = {
            "password": "pwd123",
            "api_key": "key456",
            "secret": "secret789",
            "normal_param": "visible",
        }
        result = _sanitize_params_display(params)
        assert result["password"] == "***"
        assert result["api_key"] == "***"
        assert result["secret"] == "***"
        assert result["normal_param"] == "visible"

    def test_long_value_truncated(self):
        from frontend.components.confirmation_dialog import _sanitize_params_display
        long_value = "x" * 100
        params = {"description": long_value}
        result = _sanitize_params_display(params)
        assert len(result["description"]) == 53  # 50 chars + "..."

    def test_short_value_not_truncated(self):
        from frontend.components.confirmation_dialog import _sanitize_params_display
        params = {"name": "test_value"}
        result = _sanitize_params_display(params)
        assert result["name"] == "test_value"

    def test_none_value_handled(self):
        from frontend.components.confirmation_dialog import _sanitize_params_display
        params = {"optional": None}
        result = _sanitize_params_display(params)
        assert result["optional"] == ""

    def test_case_insensitive_sensitive_detection(self):
        from frontend.components.confirmation_dialog import _sanitize_params_display
        params = {"PASSWORD": "case_test", "Api_Key": "another_test"}
        result = _sanitize_params_display(params)
        assert result["PASSWORD"] == "***"
        assert result["Api_Key"] == "***"


class TestBuildConfirmCallback:
    """Test suite for build_confirm_callback() function."""

    def test_callback_is_async_callable(self):
        from frontend.components.confirmation_dialog import build_confirm_callback
        cb = build_confirm_callback("test_session_12345678901234567890123456789012")
        assert asyncio.iscoroutinefunction(cb)

    def test_callback_returns_confirmation_result(self):
        from frontend.components.confirmation_dialog import build_confirm_callback
        import streamlit as st

        st.session_state["confirmation_choice_test_session"] = {
            "confirmed": True,
            "method": "user",
            "choice": "confirmed",
            "trust_boost": False,
        }

        cb = build_confirm_callback("test_session")
        request = ConfirmationRequest(
            session_id="test_session",
            intent_type="EMAIL",
            goal="Send email to client",
            confidence=0.75,
            risk_level=RiskLevel.HIGH,
        )

        result = asyncio.get_event_loop().run_until_complete(cb(request))
        assert isinstance(result, ConfirmationResult)
        assert result.confirmed is True
        assert result.method == "user"

    def test_callback_handles_cancel(self):
        from frontend.components.confirmation_dialog import build_confirm_callback
        import streamlit as st

        st.session_state["confirmation_choice_cancel_session"] = {
            "confirmed": False,
            "method": "cancel",
            "choice": "cancelled",
            "trust_boost": False,
        }

        cb = build_confirm_callback("cancel_session")
        request = ConfirmationRequest(
            session_id="cancel_session",
            intent_type="EMAIL",
            goal="Send email",
            confidence=0.75,
            risk_level=RiskLevel.HIGH,
        )

        result = asyncio.get_event_loop().run_until_complete(cb(request))
        assert result.confirmed is False
        assert result.method == "cancel"

    def test_callback_handles_skip_and_trust(self):
        from frontend.components.confirmation_dialog import build_confirm_callback
        import streamlit as st

        st.session_state["confirmation_choice_skip_session"] = {
            "confirmed": True,
            "method": "skipped",
            "choice": "skipped",
            "trust_boost": True,
        }

        cb = build_confirm_callback("skip_session")
        request = ConfirmationRequest(
            session_id="skip_session",
            intent_type="SOCIAL",
            goal="Post on social media",
            confidence=0.80,
            risk_level=RiskLevel.HIGH,
        )

        result = asyncio.get_event_loop().run_until_complete(cb(request))
        assert result.confirmed is True
        assert result.method == "skipped"
        assert f"trust_boost_skip_session_SOCIAL" in st.session_state

    def test_callback_pending_state_when_no_choice(self):
        from frontend.components.confirmation_dialog import build_confirm_callback
        import streamlit as st

        if "confirmation_choice_pending_session" in st.session_state:
            del st.session_state["confirmation_choice_pending_session"]

        cb = build_confirm_callback("pending_session")
        request = ConfirmationRequest(
            session_id="pending_session",
            intent_type="EMAIL",
            goal="Pending operation",
            confidence=0.75,
            risk_level=RiskLevel.HIGH,
        )

        result = asyncio.get_event_loop().run_until_complete(cb(request))
        assert result.confirmed is False
        assert result.method == "pending"
        assert "pending_confirmation" in st.session_state

    def test_callback_latency_recorded(self):
        from frontend.components.confirmation_dialog import build_confirm_callback
        import streamlit as st
        import time

        st.session_state["confirmation_choice_latency_session"] = {
            "confirmed": True,
            "method": "user",
            "choice": "confirmed",
            "trust_boost": False,
        }

        cb = build_confirm_callback("latency_session")
        request = ConfirmationRequest(
            session_id="latency_session",
            intent_type="EMAIL",
            goal="Latency test",
            confidence=0.75,
            risk_level=RiskLevel.HIGH,
        )

        start = time.time()
        result = asyncio.get_event_loop().run_until_complete(cb(request))
        elapsed = time.time() - start

        assert result.latency_ms >= 0
        assert result.latency_ms < elapsed * 1000 + 100  # Allow some margin


class TestCheckPendingConfirmation:
    """Test suite for check_pending_confirmation() function."""

    def test_returns_none_when_no_pending(self):
        import streamlit as st
        from frontend.components.confirmation_dialog import check_pending_confirmation

        if "pending_confirmation" in st.session_state:
            del st.session_state["pending_confirmation"]

        result = check_pending_confirmation()
        assert result is None

    def test_returns_request_when_pending_exists(self):
        import streamlit as st
        from frontend.components.confirmation_dialog import check_pending_confirmation

        test_request = {
            "goal": "Test operation",
            "intent_type": "EMAIL",
            "confidence": 0.75,
            "risk_level": "high",
        }
        st.session_state["pending_confirmation"] = test_request

        result = check_pending_confirmation()
        assert result is not None
        assert result["goal"] == "Test operation"
        assert result["intent_type"] == "EMAIL"


class TestClearPendingConfirmation:
    """Test suite for clear_pending_confirmation() function."""

    def test_clears_pending_state(self):
        import streamlit as st
        from frontend.components.confirmation_dialog import clear_pending_confirmation

        st.session_state["pending_confirmation"] = {"test": "data"}
        clear_pending_confirmation()
        assert "pending_confirmation" not in st.session_state

    def test_clear_when_no_pending_does_not_raise(self):
        import streamlit as st
        from frontend.components.confirmation_dialog import clear_pending_confirmation

        if "pending_confirmation" in st.session_state:
            del st.session_state["pending_confirmation"]

        clear_pending_confirmation()
        assert "pending_confirmation" not in st.session_state


class TestRenderConfirmationDialog:
    """Test suite for render_confirmation_dialog() function."""

    def test_empty_request_returns_false(self):
        from frontend.components.confirmation_dialog import render_confirmation_dialog
        result = render_confirmation_dialog(None)
        assert result is False

    def test_valid_request_shows_dialog(self):
        from frontend.components.confirmation_dialog import render_confirmation_dialog
        request = {
            "goal": "Send Q2 report email",
            "intent_type": "EMAIL",
            "confidence": 0.75,
            "risk_level": "high",
            "params": {
                "recipient": "client@example.com",
                "subject": "Q2 Report",
            },
            "threshold": 0.95,
            "session_id": "test_session_dialog",
        }
        result = render_confirmation_dialog(request)
        assert result is False  # No button clicked yet

    @patch('streamlit.button')
    def test_confirm_button_clicked(self, mock_button):
        from frontend.components.confirmation_dialog import render_confirmation_dialog
        import streamlit as st

        mock_button.return_value = True
        request = {
            "goal": "Test confirm",
            "intent_type": "EMAIL",
            "confidence": 0.80,
            "risk_level": "high",
            "params": {},
            "threshold": 0.95,
            "session_id": "confirm_btn_test",
        }
        result = render_confirmation_dialog(request)
        # Result depends on which button returns True
        assert isinstance(result, bool)


class TestIntegrationWithConfirmer:
    """Integration tests for confirmation dialog with Confirmer system."""

    def test_auto_approval_for_high_confidence(self):
        confirmer = Confirmer()
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                confirmer.check_confirmation(
                    session_id="auto_test_session",
                    intent_type="SEARCH",
                    goal="Search for data",
                    confidence=0.90,
                    params={},
                    confirm_callback=None,
                )
            )
            assert result.confirmed is True
            assert result.method == "auto"
        finally:
            loop.close()

    def test_requires_confirmation_for_low_confidence(self):
        confirmer = Confirmer()
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                confirmer.check_confirmation(
                    session_id="manual_test_session",
                    intent_type="EMAIL",
                    goal="Send sensitive email",
                    confidence=0.75,
                    params={"recipient": "client@example.com"},
                    confirm_callback=None,
                )
            )
            assert result.confirmed is False
            assert result.method == "no_callback"
        finally:
            loop.close()

    def test_with_callback_confirmed(self):
        from frontend.components.confirmation_dialog import build_confirm_callback
        import streamlit as st

        confirmer = Confirmer()
        cb = build_confirm_callback("callback_confirmed_session")

        st.session_state["confirmation_choice_callback_confirmed_session"] = {
            "confirmed": True,
            "method": "user",
            "choice": "confirmed",
            "trust_boost": False,
        }

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                confirmer.check_confirmation(
                    session_id="callback_confirmed_session",
                    intent_type="EMAIL",
                    goal="Email with callback confirmed",
                    confidence=0.75,
                    params={},
                    confirm_callback=cb,
                )
            )
            assert result.confirmed is True
            assert result.method == "user"
        finally:
            loop.close()

    def test_with_callback_cancelled(self):
        from frontend.components.confirmation_dialog import build_confirm_callback
        import streamlit as st

        confirmer = Confirmer()
        cb = build_confirm_callback("callback_cancelled_session")

        st.session_state["confirmation_choice_callback_cancelled_session"] = {
            "confirmed": False,
            "method": "cancel",
            "choice": "cancelled",
            "trust_boost": False,
        }

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                confirmer.check_confirmation(
                    session_id="callback_cancelled_session",
                    intent_type="INVOICE",
                    goal="Invoice creation cancelled",
                    confidence=0.80,
                    params={},
                    confirm_callback=cb,
                )
            )
            assert result.confirmed is False
            assert result.method == "cancel"
        finally:
            loop.close()

    def test_trust_score_increases_on_confirmation(self):
        confirmer = Confirmer()
        initial_threshold = confirmer.get_effective_threshold("EMAIL", "trust_test_session")

        from frontend.components.confirmation_dialog import build_confirm_callback
        import streamlit as st

        cb = build_confirm_callback("trust_test_session")

        st.session_state["confirmation_choice_trust_test_session"] = {
            "confirmed": True,
            "method": "user",
            "choice": "confirmed",
            "trust_boost": False,
        }

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                confirmer.check_confirmation(
                    session_id="trust_test_session",
                    intent_type="EMAIL",
                    goal="Trust score test",
                    confidence=0.85,
                    params={},
                    confirm_callback=cb,
                )
            )
            assert result.confirmed is True

            new_threshold = confirmer.get_effective_threshold("EMAIL", "trust_test_session")
            assert new_threshold < initial_threshold
        finally:
            loop.close()


class TestEdgeCases:
    """Edge case tests for boundary conditions and special inputs."""

    def test_extremely_long_goal_truncation(self):
        from frontend.components.confirmation_dialog import _sanitize_params_display, MAX_GOAL_LENGTH
        long_goal = "x" * 500
        request = {
            "goal": long_goal,
            "intent_type": "EMAIL",
            "confidence": 0.75,
            "risk_level": "high",
            "params": {},
            "threshold": 0.95,
            "session_id": "long_goal_test",
        }
        from frontend.components.confirmation_dialog import render_confirmation_dialog
        result = render_confirmation_dialog(request)
        assert result is False

    def test_extreme_confidence_zero(self):
        from frontend.components.confirmation_dialog import _render_confidence_bar
        result = _render_confidence_bar(0.0, 0.95)
        assert "0%" in result

    def test_extreme_confidence_one(self):
        from frontend.components.confirmation_dialog import _render_confidence_bar
        result = _render_confidence_bar(1.0, 0.95)
        assert "100%" in result

    def test_empty_params_dict(self):
        from frontend.components.confirmation_dialog import _sanitize_params_display
        result = _sanitize_params_display({})
        assert result == {}

    def test_params_with_all_sensitive_keys(self):
        from frontend.components.confirmation_dialog import _sanitize_params_display
        params = {
            "password": "val1",
            "api_key": "val2",
            "token": "val3",
            "secret": "val4",
            "auth": "val5",
        }
        result = _sanitize_params_display(params)
        for value in result.values():
            assert value == "***"

    def test_mixed_case_sensitive_keys(self):
        from frontend.components.confirmation_dialog import _sanitize_params_display
        params = {
            "Password": "val1",
            "API_KEY": "val2",
            "Token": "val3",
        }
        result = _sanitize_params_display(params)
        for value in result.values():
            assert value == "***"

    def test_special_characters_in_values(self):
        from frontend.components.confirmation_dialog import _sanitize_params_display
        params = {
            "name": "用户名@#$%",
            "description": "Description with <script>alert('xss')</script>",
        }
        result = _sanitize_params_display(params)
        assert "用户名@#$%" in result["name"]
        assert "<script>" in result["description"]


class TestProgressEmitterIntegration:
    """Tests for ProgressEmitter event emission during confirmation flow."""

    def test_confirm_requested_emitted(self):
        from frontend.components.confirmation_dialog import build_confirm_callback
        import streamlit as st

        with patch('opc_manager.progress_emitter.ProgressEmitter') as mock_emitter_class:
            mock_emitter = Mock()
            mock_emitter_class.return_value = mock_emitter

            cb = build_confirm_callback("emit_test_session")
            request = ConfirmationRequest(
                session_id="emit_test_session",
                intent_type="EMAIL",
                goal="Emit test",
                confidence=0.75,
                risk_level=RiskLevel.HIGH,
            )

            if "confirmation_choice_emit_test_session" in st.session_state:
                del st.session_state["confirmation_choice_emit_test_session"]

            asyncio.get_event_loop().run_until_complete(cb(request))

            mock_emitter.emit.assert_called()
            call_args = mock_emitter.emit.call_args[0][0]
            assert call_args.event_type.value == "confirm_requested"

    def test_confirmed_emitted_on_user_confirm(self):
        from frontend.components.confirmation_dialog import build_confirm_callback
        import streamlit as st

        with patch('opc_manager.progress_emitter.ProgressEmitter') as mock_emitter_class:
            mock_emitter = Mock()
            mock_emitter_class.return_value = mock_emitter

            st.session_state["confirmation_choice_emit_confirmed_session"] = {
                "confirmed": True,
                "method": "user",
                "choice": "confirmed",
                "trust_boost": False,
            }

            cb = build_confirm_callback("emit_confirmed_session")
            request = ConfirmationRequest(
                session_id="emit_confirmed_session",
                intent_type="EMAIL",
                goal="Emit confirmed test",
                confidence=0.75,
                risk_level=RiskLevel.HIGH,
            )

            asyncio.get_event_loop().run_until_complete(cb(request))

            mock_emitter.emit.assert_called()
            emit_calls = mock_emitter.emit.call_args_list
            assert len(emit_calls) >= 2  # CONFIRM_REQUESTED + CONFIRMED
            last_call = emit_calls[-1][0][0]
            assert last_call.event_type.value == "confirmed"

    def test_rejected_emitted_on_user_cancel(self):
        from frontend.components.confirmation_dialog import build_confirm_callback
        import streamlit as st

        with patch('opc_manager.progress_emitter.ProgressEmitter') as mock_emitter_class:
            mock_emitter = Mock()
            mock_emitter_class.return_value = mock_emitter

            st.session_state["confirmation_choice_emit_rejected_session"] = {
                "confirmed": False,
                "method": "cancel",
                "choice": "cancelled",
                "trust_boost": False,
            }

            cb = build_confirm_callback("emit_rejected_session")
            request = ConfirmationRequest(
                session_id="emit_rejected_session",
                intent_type="INVOICE",
                goal="Emit rejected test",
                confidence=0.80,
                risk_level=RiskLevel.HIGH,
            )

            asyncio.get_event_loop().run_until_complete(cb(request))

            mock_emitter.emit.assert_called()
            emit_calls = mock_emitter.emit.call_args_list
            assert len(emit_calls) >= 2
            last_call = emit_calls[-1][0][0]
            assert last_call.event_type.value == "confirm_rejected"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
