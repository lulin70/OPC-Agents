"""Risk operation confirmation dialog for OPC-Agents frontend.

Implements a modal confirmation UI for high-risk operations with:
- Risk level visualization (LOW/MEDIUM/HIGH/CRITICAL)
- Confidence bar with threshold comparison
- Parameter sanitization for sensitive data
- Two-phase Streamlit-compatible async pattern
- ProgressEmitter integration for event tracking
"""

import streamlit as st
import logging
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass

from opc_manager.i18n import t as _t

logger = logging.getLogger(__name__)

RISK_BADGE_CONFIG = {
    "low": {"emoji": "🟢", "i18n_key": "confirm_risk_low", "color": "#4CAF50"},
    "medium": {"emoji": "🟡", "i18n_key": "confirm_risk_medium", "color": "#FF9800"},
    "high": {"emoji": "🔴", "i18n_key": "confirm_risk_high", "color": "#F44336"},
    "critical": {"emoji": "🟣", "i18n_key": "confirm_risk_critical", "color": "#9C27B0"},
}

SENSITIVE_KEYWORDS = [
    'password', 'passwd', 'pwd', 'secret', 'api_key', 'apikey',
    'token', 'auth', 'credential', 'private_key', 'access_key',
]

MAX_GOAL_LENGTH = 100
MAX_PARAM_VALUE_LENGTH = 50


def _render_risk_badge(risk_level: str) -> str:
    """Render risk level badge with emoji and color.

    Args:
        risk_level: One of 'low', 'medium', 'high', 'critical'

    Returns:
        Formatted badge string like "🔴 高风险"
    """
    config = RISK_BADGE_CONFIG.get(risk_level.lower(), RISK_BADGE_CONFIG["medium"])
    return f"{config['emoji']} {_t(config['i18n_key'])}"


def _render_confidence_bar(confidence: float, threshold: float) -> str:
    """Render confidence comparison bar as text representation.

    Args:
        confidence: AI confidence level (0.0-1.0)
        threshold: Required threshold for auto-approval (0.0-1.0)

    Returns:
        Text description of confidence vs threshold
    """
    conf_pct = int(confidence * 100)
    thresh_pct = int(threshold * 100)
    return _t("confirm_confidence_bar", conf_pct=conf_pct, thresh_pct=thresh_pct)


def _sanitize_params_display(params: Dict[str, Any]) -> Dict[str, str]:
    """Sanitize parameter display by redacting sensitive values.

    Detects sensitive key names and replaces values with "***".
    Truncates long values to MAX_PARAM_VALUE_LENGTH characters.

    Args:
        params: Dictionary of operation parameters

    Returns:
        Sanitized dictionary with sensitive values redacted
    """
    if not params:
        return {}

    sanitized = {}
    for key, value in params.items():
        key_lower = key.lower()
        is_sensitive = any(kw in key_lower for kw in SENSITIVE_KEYWORDS)

        if is_sensitive:
            sanitized[key] = "***"
        else:
            value_str = str(value) if value is not None else ""
            if len(value_str) > MAX_PARAM_VALUE_LENGTH:
                value_str = value_str[:MAX_PARAM_VALUE_LENGTH] + "..."
            sanitized[key] = value_str

    return sanitized


def render_confirmation_dialog(request: dict) -> bool:
    """Render modal confirmation dialog for risky operations.

    Displays a comprehensive dialog showing:
    - Operation goal (truncated to 100 chars)
    - Risk assessment table (type, confidence, risk level)
    - Execution parameters (sanitized)
    - Confidence comparison bar
    - Three action buttons: Confirm / Cancel / Skip & Trust
    - Trust boost checkbox

    Uses two-phase Streamlit pattern:
    Phase 1: Set pending_confirmation in session_state
    Phase 2: On next rerun, detect pending state and show dialog

    Args:
        request: Confirmation request dict with keys:
            - goal: Operation description
            - intent_type: Type of operation (EMAIL, SOCIAL, etc.)
            - confidence: AI confidence (0.0-1.0)
            - risk_level: Risk level string ('low', 'medium', 'high', 'critical')
            - params: Dict of execution parameters
            - threshold: Required confidence threshold
            - session_id: Session identifier

    Returns:
        True if user confirmed, False otherwise
    """
    if not request:
        return False

    goal = request.get("goal", "")
    intent_type = request.get("intent_type", "UNKNOWN")
    confidence = request.get("confidence", 0.0)
    risk_level = request.get("risk_level", "medium")
    params = request.get("params", {})
    threshold = request.get("threshold", 0.85)
    session_id = request.get("session_id", "")

    st.markdown("""
    <style>
    .confirmation-dialog {
        border: 2px solid #F44336;
        border-radius: 12px;
        padding: 24px;
        background: linear-gradient(135deg, #FFF5F5 0%, #FFFFFF 100%);
        box-shadow: 0 8px 24px rgba(244, 67, 54, 0.15);
    }
    .confirmation-title {
        font-size: 20px;
        font-weight: bold;
        color: #F44336;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .confirmation-section {
        margin: 16px 0;
        padding: 12px;
        background: white;
        border-radius: 8px;
        border-left: 4px solid #FF9800;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="confirmation-dialog">', unsafe_allow_html=True)

    col_title = st.columns([1])
    with col_title[0]:
        st.markdown(f'<div class="confirmation-title">{_t("confirm_risk_title")}</div>', unsafe_allow_html=True)

    st.divider()

    goal_display = goal[:MAX_GOAL_LENGTH]
    if len(goal) > MAX_GOAL_LENGTH:
        goal_display += "..."

    st.markdown(f"**{_t('confirm_operation_target')}:** `{goal_display}`")

    st.markdown(f"**{_t('confirm_risk_assessment')}:**")

    risk_badge = _render_risk_badge(risk_level)
    conf_text = _render_confidence_bar(confidence, threshold)

    col_type, col_conf, col_risk = st.columns(3)
    with col_type:
        st.metric(_t("confirm_operation_type"), intent_type)
    with col_conf:
        st.metric(_t("confirm_confidence"), f"{int(confidence*100)}%")
    with col_risk:
        st.markdown(f"**{_t('confirm_risk_level')}:** {risk_badge}")

    if params:
        st.markdown(f"**{_t('confirm_exec_params')}:**")
        sanitized_params = _sanitize_params_display(params)
        for param_key, param_value in sanitized_params.items():
            st.caption(f"- {param_key}: `{param_value}`")

    st.markdown(f"**{_t('confirm_ai_confidence')}:** {conf_text}")

    st.divider()

    btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 1.2])

    confirmed = False
    cancelled = False
    skipped = False

    with btn_col1:
        if st.button(_t("confirm_btn_confirm"), type="primary", key=f"confirm_{session_id}", use_container_width=True):
            confirmed = True
            logger.info("[ConfirmationDialog] User confirmed operation: %s", intent_type)

    with btn_col2:
        if st.button(_t("confirm_btn_cancel"), key=f"cancel_{session_id}", use_container_width=True):
            cancelled = True
            logger.info("[ConfirmationDialog] User cancelled operation: %s", intent_type)

    with btn_col3:
        if st.button(_t("confirm_btn_skip_trust"), key=f"skip_{session_id}", use_container_width=True):
            skipped = True
            logger.info("[ConfirmationDialog] User skipped and trusted operation: %s", intent_type)

    trust_boost = st.checkbox(_t("confirm_trust_boost"), key=f"trust_{session_id}")

    st.markdown('</div>', unsafe_allow_html=True)

    if confirmed or cancelled or skipped:
        choice = "confirmed" if confirmed else ("cancelled" if cancelled else "skipped")
        st.session_state[f"confirmation_choice_{session_id}"] = {
            "confirmed": confirmed or skipped,
            "method": "user" if confirmed else ("cancel" if cancelled else "skipped"),
            "choice": choice,
            "trust_boost": trust_boost,
        }

    return confirmed or skipped


def build_confirm_callback(session_id: str):
    """Build async callback function for Confirmer.check_confirmation().

    Creates a callback that integrates with Streamlit's execution model
    using the two-phase pattern:

    Phase 1: When called, stores request in session_state and returns pending
    Phase 2: On next rerun, detects pending state and renders dialog

    Also emits ProgressEmitter events for tracking:
    - CONFIRM_REQUESTED when dialog is shown
    - CONFIRMED when user confirms
    - CONFIRM_REJECTED when user cancels
    - CONFIRMED + trust_score update when user skips & trusts

    Args:
        session_id: Current session identifier

    Returns:
        Async callable that accepts ConfirmationRequest and returns ConfirmationResult
    """
    from opc_manager.confirmer import ConfirmationRequest, ConfirmationResult

    async def confirm_callback(request: ConfirmationRequest) -> ConfirmationResult:
        import time

        start_time = time.time()

        try:
            from opc_manager.progress_emitter import ProgressEmitter, EventType, ProgressEvent

            emitter = ProgressEmitter()

            emitter.emit(ProgressEvent(
                event_type=EventType.CONFIRM_REQUESTED,
                session_id=session_id,
                message=_t("confirm_need_confirm_op", intent_type=request.intent_type),
                progress_pct=0,
                detail={
                    "intent_type": request.intent_type,
                    "confidence": request.confidence,
                    "risk_level": request.risk_level.value,
                },
            ))
        except Exception as e:
            logger.debug("[ConfirmationDialog] Failed to emit CONFIRM_REQUESTED: %s", e)

        request_dict = {
            "goal": request.goal,
            "intent_type": request.intent_type,
            "confidence": request.confidence,
            "risk_level": request.risk_level.value,
            "params": request.extracted_params,
            "threshold": 0.85,
            "session_id": session_id,
        }

        st.session_state["pending_confirmation"] = request_dict

        choice_key = f"confirmation_choice_{session_id}"
        if choice_key not in st.session_state:
            return ConfirmationResult(
                confirmed=False,
                method="pending",
                user_choice="waiting_for_input",
                latency_ms=int((time.time() - start_time) * 1000),
            )

        choice_data = st.session_state.pop(choice_key, {})
        confirmed = choice_data.get("confirmed", False)
        method = choice_data.get("method", "cancel")
        user_choice = choice_data.get("choice", "unknown")
        trust_boost = choice_data.get("trust_boost", False)

        latency_ms = int((time.time() - start_time) * 1000)

        if "pending_confirmation" in st.session_state:
            del st.session_state["pending_confirmation"]

        try:
            from opc_manager.progress_emitter import ProgressEmitter, EventType, ProgressEvent

            emitter = ProgressEmitter()

            if confirmed:
                event_type = EventType.CONFIRMED
                progress_pct = 50
                message = _t("confirm_user_confirmed_op", intent_type=request.intent_type)

                if trust_boost:
                    message += _t("confirm_trust_boosted")
                    st.session_state[f"trust_boost_{session_id}_{request.intent_type}"] = True
            else:
                event_type = EventType.CONFIRM_REJECTED
                progress_pct = 0
                message = _t("confirm_user_cancelled_op", intent_type=request.intent_type)

            emitter.emit(ProgressEvent(
                event_type=event_type,
                session_id=session_id,
                message=message,
                progress_pct=progress_pct,
                detail={
                    "method": method,
                    "user_choice": user_choice,
                    "trust_boost": trust_boost,
                },
            ))
        except Exception as e:
            logger.debug("[ConfirmationDialog] Failed to emit result event: %s", e)

        return ConfirmationResult(
            confirmed=confirmed,
            method=method,
            user_choice=user_choice,
            latency_ms=latency_ms,
        )

    return confirm_callback


def check_pending_confirmation() -> Optional[dict]:
    """Check if there's a pending confirmation waiting for user input.

    Should be called at the start of each Streamlit rerun to detect
    if a confirmation dialog needs to be displayed.

    Returns:
        Pending confirmation request dict, or None if no pending confirmation
    """
    return st.session_state.get("pending_confirmation")


def clear_pending_confirmation():
    """Clear any pending confirmation state from session_state."""
    if "pending_confirmation" in st.session_state:
        del st.session_state["pending_confirmation"]
