"""Optimized installation guide for non-technical users.

Implements UI_DESIGN_v0.5.0.md §5 (Prototype 2: Installation Guide).
5-step guide with copy-paste commands and Morandi colors.

Target audience: non-technical users who do not know what an API Key is.
Provides 3 AI backend options (Ollama / Moka / OpenAI) where the first two
require no API Key, lowering the install barrier.
"""

import logging

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
INSTALL_COMMANDS = {
    "download_curl": "curl -fsSL https://promiselink.cn/install.sh | bash",
    "download_pip": "pip install opc-agents",
    "download_docker": "docker run -p 8000:8000 opc-agents",
    "start_cmd": "opc-agents start",
    "start_url": "http://localhost:8000",
}

# 3 个 AI 后端选项（其中 Ollama 与 Moka 均无需 API Key）
AI_BACKENDS = ["ollama", "moka", "openai"]


def render_install_guide() -> None:
    """Render the 5-step installation guide.

    Each step is rendered as an expandable section (``st.expander``).
    Step 1 is expanded by default; the rest are collapsed.
    Uses i18n keys with the ``install.`` namespace per UI_DESIGN_v0.5.0.md §7.2.
    """
    st.markdown(f"### {_t('install.title')}")

    # Step 1: 下载安装
    with st.expander(_t("install.step1_title"), expanded=True):
        st.markdown(_t("install.step1_desc"))
        st.code(INSTALL_COMMANDS["download_curl"], language="bash")
        st.markdown(f"**{_t('install.or')}**")
        st.code(INSTALL_COMMANDS["download_pip"], language="bash")
        st.markdown(f"**{_t('install.or')}**")
        st.code(INSTALL_COMMANDS["download_docker"], language="bash")

    # Step 2: 启动应用
    with st.expander(_t("install.step2_title")):
        st.markdown(_t("install.step2_desc"))
        st.code(INSTALL_COMMANDS["start_cmd"], language="bash")
        st.markdown(
            f"{_t('install.step2_visit')}: {INSTALL_COMMANDS['start_url']}"
        )

    # Step 3: 配置 AI 后端（3 选 1，可跳过；默认 Moka 网关零成本）
    with st.expander(_t("install.step3_title")):
        st.markdown(_t("install.step3_desc"))
        option = st.radio(
            _t("install.step3_option_label"),
            options=AI_BACKENDS,
            format_func=lambda x: _t(f"install.step3_option_{x}"),
            index=1,  # 默认 Moka 网关（零成本、无需 API Key）
            key="install_ai_backend",
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
                logger.info("[InstallGuide] OpenAI API key entered (length=%d)", len(api_key))
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
        st.markdown(
            f"""
            - {_t('install.step5_example_email')}
            - {_t('install.step5_example_finance')}
            - {_t('install.step5_example_report')}
            """
        )
