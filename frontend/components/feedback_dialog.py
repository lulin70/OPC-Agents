"""Feedback dialog component for user rating after task completion.

Implements UI_DESIGN_v0.5.0.md §4 (Prototype 1: Feedback Rating UI).
Uses Morandi color palette (no harsh emojis) per user preference.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
import streamlit as st

from opc_manager.i18n import t as _t

logger = logging.getLogger(__name__)

__all__ = [
    "render_feedback_dialog",
    "render_feedback_toast",
    "submit_feedback_to_api",
    "FEEDBACK_CATEGORIES",
    "TOAST_COLORS",
    "DEFAULT_API_ENDPOINT",
]

# 5 个反馈分类（v0.5.1: "unspecified" placed first as the optional default per
# ROADMAP_v0.5.1.md §1.2 / OKR-4 KR4.4 — boosts feedback completion rate）
FEEDBACK_CATEGORIES = ["unspecified", "bug", "suggestion", "praise", "question"]

# Path to Morandi design tokens CSS (single source of truth for component colors)
_MORANDI_TOKENS_PATH = (
    Path(__file__).resolve().parent.parent / "styles" / "morandi_tokens.css"
)

# Morandi 配色（与 UI_DESIGN_v0.5.0.md §3.2 语义色板对齐，不使用刺眼 emoji）
TOAST_COLORS = {
    "success": "#7A9B76",  # Morandi 成功绿（柔化）
    "error": "#B07C7C",  # Morandi 危险红（柔化）
    "info": "#7B8FA1",  # Morandi 信息蓝（柔化）
}

# 默认 API 端点（与 API_DESIGN_feedback_and_metrics.md §3.1 对齐）
DEFAULT_API_ENDPOINT = "http://localhost:8000/api/v1/feedback"

# 评分范围常量（与 UI_DESIGN_v0.5.0.md §4.3 对齐）
MIN_RATING = 1
MAX_RATING = 5
DEFAULT_RATING = 5
MAX_COMMENT_LENGTH = 500


def _inject_morandi_tokens() -> None:
    """Inject morandi_tokens.css once per session so var() works in HTML.

    Reads the shared Morandi design tokens stylesheet and embeds it via a
    ``<style>`` tag. Uses ``session_state["morandi_tokens_injected"]`` to
    avoid duplicate injection across reruns (per ROADMAP_v0.5.1.md §1.3).
    Silently warns on missing file — components fall back to inline styles.
    """
    if st.session_state.get("morandi_tokens_injected"):
        return
    try:
        css_content = _MORANDI_TOKENS_PATH.read_text(encoding="utf-8")
        st.markdown(f"<style>\n{css_content}\n</style>", unsafe_allow_html=True)
        st.session_state["morandi_tokens_injected"] = True
    except OSError as exc:
        logger.warning(
            "[FeedbackDialog] Failed to inject morandi_tokens.css from %s: %s",
            _MORANDI_TOKENS_PATH,
            exc,
        )


def render_feedback_dialog(skill_id: str, session_id: str) -> Optional[dict]:
    """Render feedback dialog after task completion.

    Args:
        skill_id: The skill that was just executed
        session_id: The session ID for tracking

    Returns:
        Feedback data dict if submitted, None if cancelled or not submitted.
        Dict shape::

            {
                "rating": int (1-5),
                "category": Optional[str] ("bug"|"suggestion"|"praise"|"question"
                                           |None when "unspecified"),
                "comment": Optional[str],
                "skill_id": str,
                "session_id": str,
                "timestamp": str  # ISO 8601 UTC
            }
    """
    # Inject Morandi tokens once so var(--morandi-star-*) resolves in CSS
    _inject_morandi_tokens()

    # 1. 标题（i18n，缺失键时回退到 key 本身）
    st.markdown(f"### {_t('feedback.title')}")

    # 2. 5 星评分（使用滑块，避免 emoji；Morandi 暖金视觉另渲染）
    rating = st.slider(
        _t("feedback.rating_label"),
        min_value=MIN_RATING,
        max_value=MAX_RATING,
        value=DEFAULT_RATING,
        key=f"rating_{skill_id}_{session_id}",
        help=_t("feedback.rating_help"),
    )
    _render_star_visual(rating)

    # 3. 分类单选（v0.5.1: "unspecified" 默认可选，不阻断提交）
    category = st.selectbox(
        _t("feedback.category_label"),
        options=FEEDBACK_CATEGORIES,
        index=0,  # default to "unspecified" (optional category)
        format_func=lambda x: _t(f"feedback.category.{x}"),
        key=f"category_{skill_id}_{session_id}",
    )

    # 4. 反馈内容（最多 500 字，前端限制）
    comment = st.text_area(
        _t("feedback.comment_label"),
        max_chars=MAX_COMMENT_LENGTH,
        key=f"comment_{skill_id}_{session_id}",
        help=_t("feedback.comment_help"),
    )
    st.caption(f"{len(comment)} / {MAX_COMMENT_LENGTH}")

    # 5. 按钮区：[取消] [提交反馈]
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button(
            _t("feedback.cancel"),
            key=f"cancel_{skill_id}_{session_id}",
            type="secondary",
        ):
            return None
    with col2:
        if st.button(
            _t("feedback.submit"),
            key=f"submit_{skill_id}_{session_id}",
            type="primary",
        ):
            # v0.5.1: "unspecified" is optional — pass None to API so the
            # category field is not required (per ROADMAP_v0.5.1.md KR4.4)
            resolved_category = None if category == "unspecified" else category
            return {
                "rating": rating,
                "category": resolved_category,
                "comment": comment if comment else None,
                "skill_id": skill_id,
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
    return None


def _render_star_visual(rating: int) -> None:
    """Render star visual using Morandi warm-gold CSS (no emoji).

    Uses CSS variables from morandi_tokens.css so the star palette adapts
    to the active theme (light/dark). Adds ARIA slider semantics per
    UI_DESIGN_v0.5.1.md §5.1 for screen reader accessibility.

    Args:
        rating: Star rating from 1 to 5
    """
    star_full = '<span style="color:var(--morandi-star-full);">★</span>'
    star_empty = '<span style="color:var(--morandi-star-empty);">☆</span>'
    stars = star_full * rating + star_empty * (MAX_RATING - rating)
    st.markdown(
        f'<div style="font-size:24px; letter-spacing:4px;" '
        f'role="slider" '
        f'aria-label="评分，1 到 5 星，当前 {rating} 星" '
        f'aria-valuemin="1" aria-valuemax="5" aria-valuenow="{rating}">'
        f"{stars}</div>",
        unsafe_allow_html=True,
    )


def render_feedback_toast(message: str, type_: str = "info") -> None:
    """Render toast notification after feedback submission.

    Uses Morandi color palette (no harsh emojis) per user preference.
    Unknown type falls back to "info" color.

    Args:
        message: Toast message text
        type_: "success" | "error" | "info"; unknown values default to "info"
    """
    color = TOAST_COLORS.get(type_, TOAST_COLORS["info"])
    st.markdown(
        f"""
        <div style="
            background-color: {color};
            color: #FFFFFF;
            padding: 10px 20px;
            border-radius: 5px;
            margin: 10px 0;
            font-size: 14px;
        ">
            {message}
        </div>
        """,
        unsafe_allow_html=True,
    )


def submit_feedback_to_api(
    feedback_data: dict,
    endpoint: str = DEFAULT_API_ENDPOINT,
    timeout: float = 5.0,
) -> bool:
    """Submit feedback to API endpoint.

    Implements the POST /api/v1/feedback call described in
    API_DESIGN_feedback_and_metrics.md §3.1.

    Args:
        feedback_data: Feedback data dict from :func:`render_feedback_dialog`
        endpoint: API endpoint URL (default: local dev server)
        timeout: Request timeout in seconds

    Returns:
        True if submitted successfully (HTTP 2xx), False otherwise.
    """
    if not feedback_data:
        logger.warning("[FeedbackDialog] Empty feedback_data, aborting submit")
        return False

    try:
        response = requests.post(
            endpoint,
            json=feedback_data,
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )
        if 200 <= response.status_code < 300:
            logger.info(
                "[FeedbackDialog] Feedback submitted successfully (HTTP %s)",
                response.status_code,
            )
            return True
        logger.warning(
            "[FeedbackDialog] Feedback submit failed: HTTP %s, body=%s",
            response.status_code,
            response.text[:200],
        )
        return False
    except requests.RequestException as exc:
        logger.error("[FeedbackDialog] Feedback submit network error: %s", exc)
        return False
