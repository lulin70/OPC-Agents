"""
Confirmer Unit Tests — Risk assessment and confirmation workflow validation.

Covers:
- RiskLevel enum values and RISK_LEVEL_MAP
- ConfirmationRequest/Result dataclass defaults and behavior
- Confirmer risk assessment for known/unknown intents
- Effective threshold calculation with trust bonus
- Input validation in check_confirmation (session_id, intent_type, goal, confidence, callback)
- Auto-approval when confidence >= effective threshold
- Rejection when no callback and low confidence
- Callback invocation path with trust score accumulation
- Sensitive info sanitization (redaction + truncation)
- Confirmation card formatting

Run command:
    pytest tests/test_confirmer.py -v --tb=short
"""

import asyncio
import pytest
from opc_manager.confirmer import (
    RiskLevel,
    ConfirmationRequest,
    ConfirmationResult,
    RISK_LEVEL_MAP,
    THRESHOLDS,
    Confirmer,
)


@pytest.fixture
def confirmer():
    """Provide a fresh Confirmer instance per test."""
    return Confirmer()


class TestRiskLevelEnum:
    """Test suite for RiskLevel enum values."""

    def test_low_value(self):
        assert RiskLevel.LOW.value == "low"

    def test_medium_value(self):
        assert RiskLevel.MEDIUM.value == "medium"

    def test_high_value(self):
        assert RiskLevel.HIGH.value == "high"

    def test_critical_value(self):
        assert RiskLevel.CRITICAL.value == "critical"

    def test_all_four_levels_exist(self):
        levels = list(RiskLevel)
        assert len(levels) == 4
        assert RiskLevel.LOW in levels
        assert RiskLevel.MEDIUM in levels
        assert RiskLevel.HIGH in levels
        assert RiskLevel.CRITICAL in levels


class TestConfirmationDataclasses:
    """Test suite for ConfirmationRequest and ConfirmationResult dataclasses."""

    def test_request_defaults(self):
        req = ConfirmationRequest(
            session_id="sess1",
            intent_type="EMAIL",
            goal="send email",
            confidence=0.9,
            risk_level=RiskLevel.HIGH,
        )
        assert req.extracted_params == {}
        assert isinstance(req.created_at, float)
        assert req.created_at > 0

    def test_request_with_params(self):
        req = ConfirmationRequest(
            session_id="sess1",
            intent_type="EMAIL",
            goal="send email",
            confidence=0.9,
            risk_level=RiskLevel.HIGH,
            extracted_params={"to": "user@example.com"},
        )
        assert req.extracted_params == {"to": "user@example.com"}

    def test_result_defaults(self):
        result = ConfirmationResult(confirmed=True, method="auto")
        assert result.user_choice is None
        assert result.latency_ms == 0

    def test_result_with_choice_and_latency(self):
        result = ConfirmationResult(
            confirmed=True,
            method="callback",
            user_choice="approve",
            latency_ms=42,
        )
        assert result.user_choice == "approve"
        assert result.latency_ms == 42


class TestRiskLevelMapAndThresholds:
    """Test suite for RISK_LEVEL_MAP and THRESHOLDS constants."""

    def test_search_is_low_risk(self):
        assert RISK_LEVEL_MAP["SEARCH"] == RiskLevel.LOW

    def test_email_is_high_risk(self):
        assert RISK_LEVEL_MAP["EMAIL"] == RiskLevel.HIGH

    def test_finance_is_medium_risk(self):
        assert RISK_LEVEL_MAP["FINANCE"] == RiskLevel.MEDIUM

    def test_unknown_intent_defaults_to_medium(self):
        assert RISK_LEVEL_MAP.get("NONEXISTENT_INTENT") is None

    def test_threshold_low(self):
        assert THRESHOLDS[RiskLevel.LOW] == 0.70

    def test_threshold_medium(self):
        assert THRESHOLDS[RiskLevel.MEDIUM] == 0.85

    def test_threshold_high(self):
        assert THRESHOLDS[RiskLevel.HIGH] == 0.95

    def test_threshold_critical(self):
        assert THRESHOLDS[RiskLevel.CRITICAL] == 1.00


class TestAssessRisk:
    """Test suite for Confirmer.assess_risk()."""

    def test_known_intent_search(self, confirmer):
        assert confirmer.assess_risk("SEARCH") == RiskLevel.LOW

    def test_known_intent_email(self, confirmer):
        assert confirmer.assess_risk("EMAIL") == RiskLevel.HIGH

    def test_known_intent_invoice(self, confirmer):
        assert confirmer.assess_risk("INVOICE") == RiskLevel.HIGH

    def test_unknown_intent_falls_back_to_medium(self, confirmer):
        assert confirmer.assess_risk("UNKNOWN_OPERATION") == RiskLevel.MEDIUM


class TestGetEffectiveThreshold:
    """Test suite for Confirmer.get_effective_threshold()."""

    def test_base_threshold_no_trust(self, confirmer):
        threshold = confirmer.get_effective_threshold("SEARCH", "sess1")
        assert threshold == THRESHOLDS[RiskLevel.LOW]

    def test_trust_bonus_reduces_threshold(self, confirmer):
        key = ("sess1", "SEARCH")
        confirmer._trust_scores[key] = 5
        threshold = confirmer.get_effective_threshold("SEARCH", "sess1")
        base = THRESHOLDS[RiskLevel.LOW]
        expected = base - 5 * 0.02
        assert threshold == expected

    def test_threshold_clamped_at_minimum(self, confirmer):
        key = ("sess1", "SEARCH")
        confirmer._trust_scores[key] = 100
        threshold = confirmer.get_effective_threshold("SEARCH", "sess1")
        assert threshold >= 0.60


class TestCheckConfirmationValidation:
    """Test suite for input validation in check_confirmation()."""

    @pytest.mark.asyncio
    async def test_bad_session_id_empty(self, confirmer):
        with pytest.raises(ValueError, match="session_id"):
            await confirmer.check_confirmation("", "SEARCH", "goal", 0.8)

    @pytest.mark.asyncio
    async def test_bad_session_id_none(self, confirmer):
        with pytest.raises(ValueError, match="session_id"):
            await confirmer.check_confirmation(None, "SEARCH", "goal", 0.8)

    @pytest.mark.asyncio
    async def test_bad_session_id_non_string(self, confirmer):
        with pytest.raises(ValueError, match="session_id"):
            await confirmer.check_confirmation(123, "SEARCH", "goal", 0.8)

    @pytest.mark.asyncio
    async def test_bad_intent_type_empty(self, confirmer):
        with pytest.raises(ValueError, match="intent_type"):
            await confirmer.check_confirmation("sess1", "", "goal", 0.8)

    @pytest.mark.asyncio
    async def test_bad_goal_empty(self, confirmer):
        with pytest.raises(ValueError, match="goal"):
            await confirmer.check_confirmation("sess1", "SEARCH", "", 0.8)

    @pytest.mark.asyncio
    async def test_bad_confidence_out_of_range_high(self, confirmer):
        with pytest.raises(ValueError, match="confidence"):
            await confirmer.check_confirmation("sess1", "SEARCH", "goal", 1.5)

    @pytest.mark.asyncio
    async def test_bad_confidence_out_of_range_low(self, confirmer):
        with pytest.raises(ValueError, match="confidence"):
            await confirmer.check_confirmation("sess1", "SEARCH", "goal", -0.1)

    @pytest.mark.asyncio
    async def test_bad_callback_not_callable(self, confirmer):
        with pytest.raises(TypeError, match="confirm_callback.*callable"):
            await confirmer.check_confirmation(
                "sess1", "SEARCH", "goal", 0.5, confirm_callback="not_callable"
            )


class TestCheckConfirmationAutoApproval:
    """Test suite for auto-approval when confidence >= threshold."""

    @pytest.mark.asyncio
    async def test_auto_approve_low_risk_high_confidence(self, confirmer):
        result = await confirmer.check_confirmation(
            "sess1", "SEARCH", "search something", 0.95
        )
        assert result.confirmed is True
        assert result.method == "auto"

    @pytest.mark.asyncio
    async def test_auto_approve_at_exact_threshold(self, confirmer):
        result = await confirmer.check_confirmation("sess1", "SEARCH", "search", 0.70)
        assert result.confirmed is True
        assert result.method == "auto"


class TestCheckConfirmationRejection:
    """Test suite for rejection when no callback and low confidence."""

    @pytest.mark.asyncio
    async def test_reject_when_no_callback_low_confidence(self, confirmer):
        result = await confirmer.check_confirmation("sess1", "EMAIL", "send email", 0.5)
        assert result.confirmed is False
        assert result.method == "no_callback"


class TestCheckConfirmationCallbackPath:
    """Test suite for callback invocation path."""

    @pytest.mark.asyncio
    async def test_callback_invoked_on_low_confidence(self, confirmer):
        callback_called = []

        async def mock_callback(request):
            callback_called.append(request)
            return ConfirmationResult(
                confirmed=True, method="callback", user_choice="yes"
            )

        result = await confirmer.check_confirmation(
            "sess1", "EMAIL", "send email", 0.5, confirm_callback=mock_callback
        )
        assert len(callback_called) == 1
        assert callback_called[0].intent_type == "EMAIL"
        assert result.confirmed is True
        assert result.method == "callback"

    @pytest.mark.asyncio
    async def test_callback_rejection_propagated(self, confirmer):
        async def reject_callback(request):
            return ConfirmationResult(
                confirmed=False, method="callback", user_choice="no"
            )

        result = await confirmer.check_confirmation(
            "sess1", "EMAIL", "send email", 0.5, confirm_callback=reject_callback
        )
        assert result.confirmed is False

    @pytest.mark.asyncio
    async def test_trust_score_increases_on_confirm(self, confirmer):
        async def approve_callback(request):
            return ConfirmationResult(confirmed=True, method="callback")

        await confirmer.check_confirmation(
            "sess1", "EMAIL", "send email", 0.5, confirm_callback=approve_callback
        )
        key = ("sess1", "EMAIL")
        assert confirmer._trust_scores[key] == 1

    @pytest.mark.asyncio
    async def test_trust_score_capped_at_max(self, confirmer):
        key = ("sess1", "EMAIL")
        confirmer._trust_scores[key] = 10

        async def approve_callback(request):
            return ConfirmationResult(confirmed=True, method="callback")

        await confirmer.check_confirmation(
            "sess1", "EMAIL", "send email", 0.5, confirm_callback=approve_callback
        )
        assert confirmer._trust_scores[key] == 10


class TestSanitizeSensitiveInfo:
    """Test suite for _sanitize_sensitive_info redaction and truncation."""

    def test_redacts_password_pattern(self, confirmer):
        result = Confirmer._sanitize_sensitive_info("my password is secret123")
        assert result == "***REDACTED***"

    def test_redacts_api_key_pattern(self, confirmer):
        result = Confirmer._sanitize_sensitive_info("api_key=sk-abc123")
        assert result == "***REDACTED***"

    def test_redacts_token_pattern(self, confirmer):
        result = Confirmer._sanitize_sensitive_info("bearer token xyz789")
        assert result == "***REDACTED***"

    def test_truncates_long_safe_text(self, confirmer):
        long_text = "a" * 200
        result = Confirmer._sanitize_sensitive_info(long_text, max_length=100)
        assert len(result) == 100
        assert result == "a" * 100

    def test_short_text_unchanged(self, confirmer):
        text = "hello world"
        result = Confirmer._sanitize_sensitive_info(text)
        assert result == text


class TestGetConfirmationCard:
    """Test suite for get_confirmation_card formatting."""

    def test_card_format(self, confirmer):
        request = ConfirmationRequest(
            session_id="sess1",
            intent_type="EMAIL",
            goal="Send quarterly report to client",
            confidence=0.88,
            risk_level=RiskLevel.HIGH,
            extracted_params={"to": "client@example.com", "subject": "Q4 Report"},
        )
        card = confirmer.get_confirmation_card(request)
        assert card["intent_type"] == "EMAIL"
        assert "confidence" in card
        assert card["risk_level"] == "high"
        assert "params" in card
        assert "threshold" in card

    def test_card_goal_truncated(self, confirmer):
        long_goal = "x" * 150
        request = ConfirmationRequest(
            session_id="s",
            intent_type="EMAIL",
            goal=long_goal,
            confidence=0.9,
            risk_level=RiskLevel.HIGH,
        )
        card = confirmer.get_confirmation_card(request)
        assert len(card["goal"]) <= 100

    def test_card_confidence_formatted_as_percent(self, confirmer):
        request = ConfirmationRequest(
            session_id="s",
            intent_type="SEARCH",
            goal="find docs",
            confidence=0.856,
            risk_level=RiskLevel.LOW,
        )
        card = confirmer.get_confirmation_card(request)
        assert "%" in card["confidence"]

    def test_card_filters_empty_param_values(self, confirmer):
        request = ConfirmationRequest(
            session_id="s",
            intent_type="EMAIL",
            goal="test",
            confidence=0.9,
            risk_level=RiskLevel.HIGH,
            extracted_params={"to": "a@b.com", "cc": "", "bcc": None},
        )
        card = confirmer.get_confirmation_card(request)
        assert "to" in card["params"]
        assert "cc" not in card["params"]
        assert "bcc" not in card["params"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
