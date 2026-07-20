"""Data collection consent dialog component.

Implements UI_DESIGN_v0.5.0.md §6 (Prototype 3: Data Collection Consent Dialog).
Shows on first launch, asks user to consent to data collection.
Uses Morandi color palette (no harsh emojis) per user preference.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import streamlit as st

from opc_manager.i18n import t as _t

logger = logging.getLogger(__name__)

__all__ = [
    "render_consent_dialog",
    "save_consent",
    "load_consent",
    "has_user_consented",
    "DEFAULT_CONSENT",
    "CONSENT_VERSION",
    "PRIVACY_POLICY_URL",
]

# 同意记录版本（用于未来 schema 升级时的迁移判断）
CONSENT_VERSION = "1.0"

# 隐私政策与数据处理协议链接（与 UI_DESIGN_v0.5.0.md §6.3 对齐）
PRIVACY_POLICY_URL = "https://promiselink.cn/privacy"
DPA_URL = "https://promiselink.cn/dpa"

# Path to Morandi design tokens CSS (single source of truth for component colors)
_MORANDI_TOKENS_PATH = Path(__file__).resolve().parent.parent / "styles" / "morandi_tokens.css"

# 默认同意配置：前 3 项默认勾选（仅本地存储），最后一项（反馈内容）默认不勾选，
# 上报开关默认关闭（脱敏上报需用户主动同意）。与 ADR-004 §3.4 + HARD_CONSTRAINTS S4 对齐。
DEFAULT_CONSENT = {
    "usage_stats": True,
    "perf_metrics": True,
    "satisfaction": True,
    "feedback_content": False,
    "consented_at": None,
    "consent_version": CONSENT_VERSION,
}

# 4 个复选框配置：(key, default_value)
_CONSENT_CHECKBOXES = [
    ("usage_stats", True),
    ("perf_metrics", True),
    ("satisfaction", True),
    ("feedback_content", False),
]


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
            "[ConsentDialog] Failed to inject morandi_tokens.css from %s: %s",
            _MORANDI_TOKENS_PATH,
            exc,
        )


def render_consent_dialog(config_path: Path) -> Optional[dict]:
    """Render consent dialog on first launch.

    Args:
        config_path: Path to save consent config
            (e.g., ``~/.opc-agents/data/consent.json``)

    Returns:
        Consent data dict if user made a choice (clicked agree or disagree),
        None if dialog dismissed without choice.
    """
    # Inject Morandi tokens once so var(--morandi-blue) resolves in link styles
    _inject_morandi_tokens()

    # 1. 标题
    st.markdown(f"### {_t('consent.title')}")

    # 2. 说明
    st.markdown(_t("consent.description"))

    # 3. 4 个复选框（前 3 个默认勾选，最后一个默认不勾选）
    # Accessibility: Streamlit st.checkbox does not natively support aria-label,
    # so we inject a hidden ARIA annotation before each control (per
    # UI_DESIGN_v0.5.1.md §5.1) and keep the help param for aria-describedby.
    choices = {}
    for key, default in _CONSENT_CHECKBOXES:
        label_text = _t(f"consent.{key}")
        state_text = "checked" if default else "unchecked"
        st.markdown(
            f'<div role="checkbox" aria-label="{label_text}, {state_text}" '
            f'aria-checked="{"true" if default else "false"}" '
            f'style="position:absolute;width:1px;height:1px;overflow:hidden;'
            f'clip:rect(0 0 0 0);white-space:nowrap;"></div>',
            unsafe_allow_html=True,
        )
        choices[key] = st.checkbox(
            _t(f"consent.{key}"),
            value=default,
            key=f"consent_{key}",
            help=_t(f"consent.{key}_help"),
        )

    # 4. 隐私承诺（用 | 分隔的多条文案）
    st.markdown(f"**{_t('consent.privacy_promise_title')}**")
    for promise in _t("consent.privacy_promise").split("|"):
        promise_text = promise.strip()
        if promise_text:
            st.markdown(f"- {promise_text}")

    # 5. 隐私政策与数据处理协议链接
    # Use var(--morandi-blue) so links adapt to active theme (light/dark).
    st.markdown(
        f'<span style="color: var(--morandi-blue);">'
        f'<a href="{PRIVACY_POLICY_URL}" style="color: var(--morandi-blue);">'
        f"{_t('consent.privacy_policy')}</a> | "
        f'<a href="{DPA_URL}" style="color: var(--morandi-blue);">'
        f"{_t('consent.dpa')}</a>"
        f"</span>",
        unsafe_allow_html=True,
    )

    # 6. 按钮区：[不同意] [同意并继续]
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button(
            _t("consent.disagree"),
            key="consent_disagree_btn",
            type="secondary",
        ):
            consent_data = DEFAULT_CONSENT.copy()
            for key in ["usage_stats", "perf_metrics", "satisfaction", "feedback_content"]:
                consent_data[key] = False
            consent_data["consented_at"] = datetime.now(timezone.utc).isoformat()
            consent_data["consent_version"] = CONSENT_VERSION
            save_consent(config_path, consent_data)
            return consent_data
    with col2:
        if st.button(
            _t("consent.agree"),
            key="consent_agree_btn",
            type="primary",
        ):
            consent_data = {
                "usage_stats": choices["usage_stats"],
                "perf_metrics": choices["perf_metrics"],
                "satisfaction": choices["satisfaction"],
                "feedback_content": choices["feedback_content"],
                "consented_at": datetime.now(timezone.utc).isoformat(),
                "consent_version": CONSENT_VERSION,
            }
            save_consent(config_path, consent_data)
            return consent_data
    return None


def save_consent(config_path: Path, consent_data: dict) -> None:
    """Save consent data to config file.

    Creates parent directories if missing, and sets 0o600 permissions on
    the consent file to protect user privacy (only the owner can read/write).

    Args:
        config_path: Path to config file
        consent_data: Consent data dict
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(consent_data, f, ensure_ascii=False, indent=2)
    # 0o600 权限保护用户隐私（仅所有者可读写），与 HARD_CONSTRAINTS S4 对齐
    try:
        config_path.chmod(0o600)
    except OSError as exc:
        # Windows 等系统可能不支持 chmod，仅记录日志不抛出
        logger.warning("[ConsentDialog] chmod 0o600 failed for %s: %s", config_path, exc)


def load_consent(config_path: Path) -> Optional[dict]:
    """Load consent data from config file.

    Args:
        config_path: Path to config file

    Returns:
        Consent data dict if exists, None otherwise.
    """
    if not config_path.exists():
        return None
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("[ConsentDialog] Failed to load consent from %s: %s", config_path, exc)
        return None


def has_user_consented(config_path: Path) -> bool:
    """Check if user has already consented.

    A user is considered to have consented if the consent file exists
    (regardless of agree/disagree choice — both write the file).

    Args:
        config_path: Path to config file

    Returns:
        True if consent file exists, False otherwise.
    """
    return config_path.exists()


def _get_default_consent_path() -> Path:
    """Return the default consent config path.

    Default: ``~/.opc-agents/data/consent.json`` per HARD_CONSTRAINTS S4
    (data local storage).
    """
    return Path.home() / ".opc-agents" / "data" / "consent.json"
