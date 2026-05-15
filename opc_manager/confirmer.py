"""Confirmation system for OPC-Agents.

Provides risk assessment and user confirmation workflow for sensitive operations.
Implements confidence-based auto-approval with trust score tracking.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable, Optional

import logging
import time


logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk levels for operation classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ConfirmationRequest:
    """Represents a confirmation request for an operation.

    Attributes:
        session_id: Unique session identifier.
        intent_type: Type of the intended operation.
        goal: Description of the operation goal.
        confidence: AI confidence level (0.0-1.0).
        risk_level: Assessed risk level for this operation.
        extracted_params: Extracted parameters from user input.
        created_at: Timestamp when request was created.
    """
    session_id: str
    intent_type: str
    goal: str
    confidence: float
    risk_level: RiskLevel
    extracted_params: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class ConfirmationResult:
    confirmed: bool
    method: str
    user_choice: Optional[str] = None
    latency_ms: int = 0


RISK_LEVEL_MAP = {
    "SEARCH": RiskLevel.LOW,
    "DASHBOARD": RiskLevel.LOW,
    "REPORT": RiskLevel.LOW,
    "CALENDAR": RiskLevel.MEDIUM,
    "TASK": RiskLevel.MEDIUM,
    "FINANCE": RiskLevel.MEDIUM,
    "KNOWLEDGE": RiskLevel.MEDIUM,
    "CRM": RiskLevel.MEDIUM,
    "SOCIAL": RiskLevel.HIGH,
    "EMAIL": RiskLevel.HIGH,
    "PROPOSAL": RiskLevel.HIGH,
    "INVOICE": RiskLevel.HIGH,
}

THRESHOLDS = {
    RiskLevel.LOW: 0.70,
    RiskLevel.MEDIUM: 0.85,
    RiskLevel.HIGH: 0.95,
    RiskLevel.CRITICAL: 1.00,
}

TRUST_BONUS_PER_CONFIRMATION = 0.02
TRUST_MIN_THRESHOLD = 0.60
CONFIRMATION_HISTORY_SIZE = 50
MAX_GOAL_DISPLAY_CHARS = 100
MAX_PARAM_VALUE_LENGTH = 50
MAX_TRUST_SCORE = 10

SENSITIVE_PATTERNS = [
    'password', 'passwd', 'pwd', 'secret', 'api_key', 'apikey',
    'token', 'auth', 'credential', 'private_key', 'access_key',
]


class Confirmer:
    """Manages operation confirmation with risk-based auto-approval.

    Tracks trust scores per session/intent combination to reduce
    confirmation prompts for trusted operations over time.

    Attributes:
        _confirmation_history: Dictionary of past confirmations.
        _trust_scores: Trust scores for (session_id, intent_type) pairs.
    """

    def __init__(self):
        """Initialize Confirmer with empty history and trust scores."""
        self._confirmation_history: Dict[str, ConfirmationRequest] = {}
        self._trust_scores: Dict[Tuple[str, str], int] = {}

    @staticmethod
    def _sanitize_sensitive_info(text: str, max_length: int = 100) -> str:
        text_lower = text.lower()
        for pattern in SENSITIVE_PATTERNS:
            if pattern in text_lower:
                return "***REDACTED***"
        return text[:max_length]

    def assess_risk(self, intent_type: str) -> RiskLevel:
        return RISK_LEVEL_MAP.get(intent_type, RiskLevel.MEDIUM)

    def get_effective_threshold(self, intent_type: str, session_id: str) -> float:
        base = THRESHOLDS.get(self.assess_risk(intent_type), 0.85)
        key = (session_id, intent_type)
        bonus = self._trust_scores.get(key, 0) * TRUST_BONUS_PER_CONFIRMATION
        return max(base - bonus, TRUST_MIN_THRESHOLD)

    async def check_confirmation(self, session_id: str, intent_type: str,
                                  goal: str, confidence: float,
                                  params: dict = None,
                                  confirm_callback: Callable[[ConfirmationRequest], Awaitable[ConfirmationResult]] = None) -> ConfirmationResult:
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")
        if not intent_type or not isinstance(intent_type, str):
            raise ValueError("intent_type must be a non-empty string")
        if not goal or not isinstance(goal, str):
            raise ValueError("goal must be a non-empty string")
        if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
            raise ValueError("confidence must be a number between 0.0 and 1.0")
        if confirm_callback is not None and not callable(confirm_callback):
            raise TypeError("confirm_callback must be callable or None")

        risk = self.assess_risk(intent_type)
        threshold = self.get_effective_threshold(intent_type, session_id)

        if confidence >= threshold:
            return ConfirmationResult(confirmed=True, method="auto")

        request = ConfirmationRequest(
            session_id=session_id,
            intent_type=intent_type,
            goal=goal,
            confidence=confidence,
            risk_level=risk,
            extracted_params=params or {},
        )

        if confirm_callback:
            result = await confirm_callback(request)
            if result.confirmed:
                self._record_success(session_id, intent_type)
            return result

        return ConfirmationResult(confirmed=False, method="no_callback")

    def _record_success(self, session_id: str, intent_type: str):
        key = (session_id, intent_type)
        self._trust_scores[key] = min(self._trust_scores.get(key, 0) + 1, MAX_TRUST_SCORE)

    def get_confirmation_card(self, request: ConfirmationRequest) -> dict:
        return {
            "intent_type": request.intent_type,
            "goal": request.goal[:MAX_GOAL_DISPLAY_CHARS],
            "confidence": f"{request.confidence:.0%}",
            "risk_level": request.risk_level.value,
            "params": {k: str(v)[:MAX_PARAM_VALUE_LENGTH] for k, v in request.extracted_params.items() if v},
            "threshold": f"{self.get_effective_threshold(request.intent_type, request.session_id):.0%}",
        }
