"""Optimized installation guide for non-technical users.

Implements UI_DESIGN_v0.5.0.md §5 (Prototype 2: Installation Guide).
5-step guide with copy-paste commands and Morandi colors.

Target audience: non-technical users who do not know what an API Key is.
Provides 3 AI backend options (Ollama / Moka / OpenAI) where the first two
require no API Key, lowering the install barrier.
"""

import logging
from pathlib import Path

import streamlit as st

from opc_manager.i18n import t as _t

logger = logging.getLogger(__name__)

__all__ = [
    "render_install_guide",
    "INSTALL_STEPS",
    "INSTALL_COMMANDS",
    "AI_BACKENDS",
]

# 5 步安装流程标识（与 UI_DESIGN_v0.5.0.md §5.2 对齐）
INSTALL_STEPS = ["download", "start", "llm_config", "license", "done"]

# 各步骤的可复制命令（与 UI_DESIGN_v0.5.0.md §5.2 ASCII 线框图对齐）
# OPC-Agents 是 PyPI 开源包，推荐 pip 安装（无需 curl 脚本）
INSTALL_COMMANDS = {
    "download_curl": "pip install opc-agents && opc-agents start",
    "download_pip": "pip install opc-agents",
    "download_docker": "docker run -p 8000:8000 opc-agents",
    "start_cmd": "opc-agents start",
    "start_url": "http://localhost:8000",
}

# 3 个 AI 后端选项（其中 Ollama 与 Moka 均无需 API Key）
AI_BACKENDS = ["ollama", "moka", "openai"]

# Path to Morandi design tokens CSS (single source of truth for component colors)
_MORANDI_TOKENS_PATH = (
    Path(__file__).resolve().parent.parent / "styles" / "morandi_tokens.css"
)


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
            "[InstallGuide] Failed to inject morandi_tokens.css from %s: %s",
            _MORANDI_TOKENS_PATH,
            exc,
        )


def _render_progress_dots(current_idx: int) -> None:
    """Render Morandi-colored progress dots for the 5-step install flow.

    Uses CSS variables from morandi_tokens.css so the dot palette adapts to
    the active theme (light/dark). Adds an ARIA label per UI_DESIGN_v0.5.1.md
    §5.1 so screen readers announce current step / total.

    Args:
        current_idx: Zero-based index of the current step (0..len(INSTALL_STEPS)-1)
    """
    total = len(INSTALL_STEPS)
    dots_html_parts = []
    for i in range(total):
        if i == current_idx:
            color = "var(--morandi-progress-current)"
            symbol = "●"
        elif i < current_idx:
            color = "var(--morandi-progress-done)"
            symbol = "●"
        else:
            color = "var(--morandi-progress-todo)"
            symbol = "○"
        dots_html_parts.append(
            f'<span style="color: {color}; font-size: 18px; margin-right: 8px;">'
            f"{symbol}</span>"
        )
    dots_html = "".join(dots_html_parts)
    st.markdown(
        f'<div style="margin: 8px 0 16px 0;" '
        f'aria-label="步骤 {current_idx + 1} / {total}">'
        f"{dots_html}</div>",
        unsafe_allow_html=True,
    )


def _render_copyable_command(command: str) -> None:
    """Render a copyable shell command using st.code's native copy button.

    Replaces the previous unsafe_allow_html ``<div>`` + ``<script>`` injection
    pattern with Streamlit ≥ 1.35 native copy support (per ROADMAP_v0.5.1.md
    §1.4 / OKR-4 KR4.1 — XSS hardening). The CSS variables --morandi-bg and
    --morandi-blue are not needed here because st.code provides its own
    accessible theming; kept referenced in the docstring for traceability
    with UI_DESIGN_v0.5.1.md §4.3.

    Args:
        command: Shell command string to render with copy button
    """
    st.code(command, language="bash")


def render_install_guide() -> None:
    """Render the 5-step installation guide.

    Each step is rendered as an expandable section (``st.expander``).
    Step 1 is expanded by default; the rest are collapsed.
    Uses i18n keys with the ``install.`` namespace per UI_DESIGN_v0.5.0.md §7.2.
    """
    # Inject Morandi tokens once so var(--morandi-progress-*) resolves in CSS
    _inject_morandi_tokens()

    st.markdown(f"### {_t('install.title')}")

    # Progress dots: anchor visual indicator at the top of the guide.
    # current_idx=0 because the all-expanders layout lets the user browse
    # every step freely; the dots still convey the 5-step structure.
    _render_progress_dots(0)

    # Step 1: 下载安装
    with st.expander(_t("install.step1_title"), expanded=True):
        st.markdown(_t("install.step1_desc"))
        _render_copyable_command(INSTALL_COMMANDS["download_curl"])
        st.markdown(f"**{_t('install.or')}**")
        _render_copyable_command(INSTALL_COMMANDS["download_pip"])
        st.markdown(f"**{_t('install.or')}**")
        _render_copyable_command(INSTALL_COMMANDS["download_docker"])

    # Step 2: 启动应用
    with st.expander(_t("install.step2_title")):
        st.markdown(_t("install.step2_desc"))
        _render_copyable_command(INSTALL_COMMANDS["start_cmd"])
        st.markdown(f"{_t('install.step2_visit')}: {INSTALL_COMMANDS['start_url']}")

    # Step 3: 配置 AI 后端（3 选 1，可跳过；默认 Moka 网关零成本）
    with st.expander(_t("install.step3_title")):
        st.markdown(_t("install.step3_desc"))
        option = st.radio(
            _t("install.step3_option_label"),
            options=AI_BACKENDS,
            format_func=lambda x: _t(f"install.step3_option_{x}"),
            index=1,  # 默认 Moka 网关（零成本、无需 API Key）
            key="install_ai_backend",
            help=_t("install.step3_option_label"),
        )
        if option == "openai":
            api_key = st.text_input(
                _t("install.step3_apikey_label"),
                type="password",
                placeholder="sk-...",
                key="install_openai_key",
            )
            with st.expander(_t("install.step3_what_is_apikey"), expanded=False):
                st.info(_t("install.step3_apikey_explain"))
            if api_key:
                logger.info(
                    "[InstallGuide] OpenAI API key entered (length=%d)", len(api_key)
                )
        elif option == "ollama":
            st.info(_t("install.step3_ollama_help"))

    # Step 4: 激活专业版（可选）
    with st.expander(_t("install.step4_title")):
        st.markdown(_t("install.step4_desc"))
        license_key = st.text_input(
            _t("install.step4_license_label"),
            placeholder="PL-PRO-xxxx-xxxx-xxxx",
            key="install_license_key",
        )
        if st.button(
            _t("install.step4_activate"),
            key="install_activate_btn",
            type="secondary",
        ):
            if license_key:
                st.info(_t("install.step4_activating"))
                logger.info(
                    "[InstallGuide] License activation requested (key prefix=%s)",
                    license_key[:8] + "..." if len(license_key) > 8 else "***",
                )
            else:
                st.warning(_t("install.step4_license_required"))

    # Step 5: 完成
    with st.expander(_t("install.step5_title")):
        st.markdown(_t("install.step5_desc"))
        st.markdown(f"""
            - {_t('install.step5_example_email')}
            - {_t('install.step5_example_finance')}
            - {_t('install.step5_example_report')}
            """)
