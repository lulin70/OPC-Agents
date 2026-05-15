from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable
import time

import logging

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ConfirmationRequest:
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


class Confirmer:
    def __init__(self):
        self._confirmation_history: dict = {}
        self._trust_scores: dict = {}

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
        self._trust_scores[key] = self._trust_scores.get(key, 0) + 1

    def get_confirmation_card(self, request: ConfirmationRequest) -> dict:
        return {
            "intent_type": request.intent_type,
            "goal": request.goal[:100],
            "confidence": f"{request.confidence:.0%}",
            "risk_level": request.risk_level.value,
            "params": {k: str(v)[:50] for k, v in request.extracted_params.items() if v},
            "threshold": f"{self.get_effective_threshold(request.intent_type, request.session_id):.0%}",
        }
