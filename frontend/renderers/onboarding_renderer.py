"""Onboarding overlay renderer — extracted from app.py to fix NameError ordering bugs."""

import streamlit as st
import logging

from opc_manager.i18n import t as _t
from opc_manager.config import LLM_PROVIDERS

logger = logging.getLogger(__name__)


def _show_onboarding_overlay():
    """Show onboarding overlay for first-time users."""
    try:
        from opc_manager.onboarding import get_onboarding, OnboardingStep

        onboard = get_onboarding()

        current = onboard.get_current_step()
        step_content = onboard.get_step_content(current)
        total_steps = onboard.TOTAL_STEPS

        st.markdown(
            """
        <style>
        .onboarding-overlay {
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background-color: rgba(0, 0, 0, 0.7);
            z-index: 99999;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .onboarding-card {
            background: white;
            padding: 40px;
            border-radius: 12px;
            max-width: 600px;
            width: 90%;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
        }
        </style>
        """,
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.markdown(
            f"# {step_content.get('icon', '🎉')} {step_content.get('title', _t('chat_onboard_welcome'))}"
        )

        step_order = [
            OnboardingStep.WELCOME,
            OnboardingStep.LLM_CONFIG,
            OnboardingStep.SAMPLE_TASK,
        ]
        try:
            current_index = step_order.index(current)
            progress_dots = " ".join(
                ["●" if i == current_index else "○" for i in range(total_steps)]
            )
        except ValueError:
            progress_dots = "●" + " ○" * (total_steps - 1)
        st.markdown(f"<center>{progress_dots}</center>", unsafe_allow_html=True)

        if step_content.get("description"):
            st.markdown(f"\n{step_content['description']}\n")

        # LLM_CONFIG 步骤：提供 API Key 输入入口
        if current == OnboardingStep.LLM_CONFIG:
            from frontend.routers.base_router import _has_api_key

            if _has_api_key():
                st.success(_t("onboard_llm_configured"))
            else:
                st.warning(_t("onboard_llm_not_configured"))

                with st.form("onboard_llm_form"):
                    provider = st.selectbox(
                        _t("onboard_llm_provider"),
                        ["moka", "openai", "glm"],
                        format_func=lambda x: {
                            "moka": "MokaAI (推荐)",
                            "openai": "OpenAI",
                            "glm": "智谱GLM-4",
                        }.get(x, x),
                    )
                    api_key = st.text_input(
                        _t("onboard_llm_api_key"),
                        type="password",
                        placeholder="sk-...",
                    )
                    if st.form_submit_button(
                        _t("onboard_llm_save"), type="primary"
                    ):
                        if api_key and api_key.strip():
                            try:
                                from opc_manager.settings import get_settings

                                settings = get_settings()
                                provider_config = {
                                    "moka": (
                                        LLM_PROVIDERS["moka"],
                                        "moka/claude-sonnet-4-6",
                                    ),
                                    "openai": (
                                        LLM_PROVIDERS["openai"],
                                        "gpt-4o",
                                    ),
                                    "glm": (
                                        LLM_PROVIDERS["zhipu"],
                                        "glm-4",
                                    ),
                                }
                                base_url, model = provider_config.get(
                                    provider, provider_config["moka"]
                                )
                                settings.update_llm(
                                    provider=provider,
                                    api_key=api_key.strip(),
                                    base_url=base_url,
                                    model=model,
                                )
                                st.success(_t("onboard_llm_saved"))
                                st.rerun()
                            except Exception as e:
                                logger.error(
                                    "[Onboarding] LLM config save failed: %s", e
                                )
                                st.error(_t("onboard_llm_save_failed"))
                        else:
                            st.error(_t("onboard_llm_key_required"))

                st.caption(_t("onboard_llm_skip_hint"))

        col_prev, col_next, col_skip = st.columns([1, 1, 1])

        with col_prev:
            if current != OnboardingStep.WELCOME:
                if st.button(_t("onboard_prev")):
                    try:
                        prev_index = step_order.index(current) - 1
                        if prev_index >= 0:
                            onboard.advance_to_step(step_order[prev_index])
                            st.rerun()
                    except ValueError:
                        pass

        with col_next:
            is_last = current == OnboardingStep.SAMPLE_TASK
            btn_label = _t("onboard_done") if is_last else _t("onboard_next")
            if st.button(btn_label, type="primary", use_container_width=True):
                if is_last:
                    onboard.complete_onboarding()
                    st.success(_t("onboard_welcome_msg"))
                    st.rerun()
                else:
                    try:
                        next_index = step_order.index(current) + 1
                        if next_index < len(step_order):
                            onboard.advance_to_step(step_order[next_index])
                            st.rerun()
                    except ValueError:
                        pass

        with col_skip:
            if st.button(_t("onboard_skip")):
                onboard.skip_onboarding()
                st.info(_t("onboard_skipped_msg"))
                st.rerun()

    except ImportError:
        st.warning(_t("onboard_load_failed"))
    except Exception as e:
        logger.error("[frontend] Onboarding error: %s", e)
        st.error(_t("onboard_error_msg"))
