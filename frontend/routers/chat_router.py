"""Chat page router — main interaction interface with scenario buttons, input, execution, results."""

import streamlit as st
import os
import re
import html
import time
import json
import logging

from opc_manager.i18n import t as _t
from opc_manager.monitoring import track_event, track_error

from frontend.routers.base_router import (
    DEMO_MODE,
    _is_demo_mode,
    _has_api_key,
    _get_demo_dashboard_data,
    PERSONA_MAP,
    SCENARIOS_CORE,
    SCENARIOS_MORE,
    safe_detect,
    safe_get_persona,
    safe_track_flywheel,
    _save_chat_history,
    _sync_execute_task,
    _WORKSPACE_DIR,
)
from frontend.components.shared import (
    _maybe_show_shortcut_hints,
    _get_current_session_id,
    _get_phase_from_event,
    _render_progress_indicator,
    _render_quick_undo_button,
    show_success,
    show_error,
)
from frontend.components.input_autocomplete import render_autocomplete_input
from frontend.components.confirmation_dialog import (
    render_confirmation_dialog,
    check_pending_confirmation,
    clear_pending_confirmation,
)
from frontend.components.undo_panel import render_mini_undo_hint

logger = logging.getLogger(__name__)


def _save_feedback(task_id, feedback_type):
    """Save user feedback for a task to JSON file and session state."""
    feedback_key = f"fb_{task_id}"
    st.session_state.quality_feedback[feedback_key] = feedback_type
    safe_task_id = re.sub(r"[^\w-]", "", task_id)
    try:
        os.makedirs(
            os.path.join(_WORKSPACE_DIR, "data", "feedback"),
            exist_ok=True,
        )
        with open(
            os.path.join(
                _WORKSPACE_DIR, "data", "feedback", f"{safe_task_id}.json"
            ),
            "w",
        ) as f:
            json.dump(
                {
                    "task_id": task_id,
                    "feedback": feedback_type,
                    "timestamp": time.time(),
                },
                f,
            )
    except Exception as e:
        logger.warning("[ChatRouter] Save feedback failed: %s", e)


def _render_chat_history():
    """Render chat message history with deliverable downloads."""
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("deliverable_path"):
                real_path = os.path.realpath(msg["deliverable_path"])
                from frontend.routers.base_router import DELIVERABLES_DIR

                if not real_path.startswith(os.path.realpath(DELIVERABLES_DIR)):
                    st.warning(
                        f"⚠️ File path security check failed: {msg['deliverable_path']}"
                    )
                    continue
                file_content = None
                if os.path.exists(real_path):
                    col_dl, col_info = st.columns([1, 3])
                    with col_dl:
                        with open(real_path, "r", encoding="utf-8") as f:
                            file_content = f.read()
                    st.download_button(
                        label=_t("download_file"),
                        data=file_content,
                        file_name=os.path.basename(msg["deliverable_path"]),
                        mime="text/markdown",
                        key=f"dl_{msg.get('deliverable_id', id(msg))}",
                        use_container_width=True,
                    )
                if file_content is not None:
                    with col_info:
                        size_kb = round(len(file_content.encode("utf-8")) / 1024, 1)
                        st.caption(
                            f"📄 {os.path.basename(msg['deliverable_path'])} ({size_kb}KB)"
                        )


def _render_chat_input():
    """Render chat input area and return the user prompt, or None."""
    pending = st.session_state.pop("pending_prompt", None)
    if pending:
        prompt = pending
        st.session_state.messages.append({"role": "user", "content": prompt})
        _save_chat_history()
        with st.chat_message("user"):
            st.markdown(prompt)
    elif prompt := render_autocomplete_input(
        label=_t("chat_input_placeholder"),
        key="user_input_main",
        session_history=st.session_state.get("messages", []),
    ):
        st.session_state.messages.append({"role": "user", "content": prompt})
        _save_chat_history()
        with st.chat_message("user"):
            st.markdown(prompt)
    else:
        prompt = None
    return prompt


def _handle_task_result(task_id, task_status, prompt, status_container):
    """Handle task completion: display results, feedback, and suggestions."""
    status_container.update(label=_t("chat_task_done"), state="complete")

    track_event(
        "task_completed",
        {
            "mode": "async",
            "latency_ms": round(task_status.get("elapsed", 0) * 1000),
        },
    )

    result_content = task_status.get("result_content")
    result_filepath = task_status.get("result_filepath")
    result_deliverable_record = task_status.get("result_deliverable_record")

    if result_deliverable_record:
        st.session_state.deliverables.insert(0, result_deliverable_record)

    if result_content:
        from frontend.components.result_cards import render_result_card

        render_result_card(
            content=result_content,
            task_type=task_status.get("task_type"),
            deliverable_record=result_deliverable_record,
            filepath=result_filepath,
        )
        show_success(
            f"{_t('chat_deliverable_created')}: {os.path.basename(result_filepath) if result_filepath else _t('chat_task_complete')}"
        )

        feedback_key = f"fb_{task_id}"
        if feedback_key not in st.session_state.quality_feedback:
            fb_cols = st.columns([1, 1, 6])
            with fb_cols[0]:
                if st.button(
                    _t("chat_feedback_good"), key=f"good_{task_id}"
                ):
                    _save_feedback(task_id, "good")
                    st.success(_t("chat_feedback_thanks"))
                    st.rerun()
            with fb_cols[1]:
                if st.button(
                    _t("chat_feedback_bad"), key=f"bad_{task_id}"
                ):
                    _save_feedback(task_id, "bad")
                    st.info(_t("chat_feedback_improve"))
                    st.rerun()
        elif (
            st.session_state.quality_feedback.get(feedback_key)
            == "good"
        ):
            st.caption(_t("chat_feedback_good_caption"))
        elif (
            st.session_state.quality_feedback.get(feedback_key) == "bad"
        ):
            st.caption(_t("chat_feedback_bad_caption"))

        _render_quick_undo_button(
            task_id,
            (
                result_deliverable_record.get("task_type")
                if result_deliverable_record
                else None
            ),
        )

        session_id = _get_current_session_id()
        render_mini_undo_hint(session_id, task_id=task_id)

        if result_filepath and os.path.exists(result_filepath):
            col_dl, col_info = st.columns([1, 3])
            with col_dl:
                with open(result_filepath, "r", encoding="utf-8") as f:
                    file_content = f.read()
                st.download_button(
                    label=_t("chat_download_deliverable"),
                    data=file_content,
                    file_name=os.path.basename(result_filepath),
                    mime="text/markdown",
                    key=f"dl_async_{int(time.time()*1000)}",
                    use_container_width=True,
                    type="primary",
                )
            with col_info:
                size_kb = round(
                    len(file_content.encode("utf-8")) / 1024, 1
                )
                st.success(
                    f"✅ {_t('chat_file_generated')}: {os.path.basename(result_filepath)} ({size_kb}KB)"
                )
                show_success(
                    f"{_t('chat_deliverable_generated')}: {os.path.basename(result_filepath)}"
                )

        msg_record = {
            "role": "assistant",
            "content": result_content,
            "deliverable_id": f"{int(time.time()*1000)}",
        }
        if result_filepath and os.path.exists(result_filepath):
            msg_record["deliverable_path"] = result_filepath
        st.session_state.messages.append(msg_record)
        _save_chat_history()

        from frontend.components.smart_suggestions import (
            build_context_from_session,
            generate_suggestions,
            render_suggestion_panel,
        )

        suggestion_context = build_context_from_session(
            last_task_type=task_status.get("task_type", "")
            or result_deliverable_record.get("task_type", ""),
            last_result={
                "execution_time_ms": (
                    result_deliverable_record.get(
                        "execution_time_ms", 0
                    )
                    if result_deliverable_record
                    else 0
                ),
                "sources_count": (
                    result_deliverable_record.get("sources_count", 0)
                    if result_deliverable_record
                    else 0
                ),
            },
            deliverables=st.session_state.get("deliverables", []),
            feedback_history=list(
                st.session_state.get("quality_feedback", {}).items()
            ),
        )

        suggestion_context["session_id"] = session_id

        suggestions = generate_suggestions(suggestion_context)
        if suggestions:
            render_suggestion_panel(suggestions, max_show=3)


def render_chat_page():
    """Main chat page — core user interaction interface."""
    # 移动端响应式 CSS 已由 theme_manager 统一注入

    _maybe_show_shortcut_hints()
    if DEMO_MODE:
        st.markdown(f"## {_t('chat_demo_mode')}")
        st.info(
            f"""**{_t('chat_demo_mode_title')}** — {_t('chat_demo_mode_desc')}

| {_t('chat_demo_feature')} | {_t('chat_demo_status')} |
|------|------|
| 📈 {_t('nav_dashboard')} | ✅ {_t('chat_demo_available')} |
| ⚙️ {_t('nav_settings')} | ✅ {_t('chat_demo_available')} |
| 🏪 {_t('nav_marketplace')} | ✅ {_t('chat_demo_available')} |
| 💬 {_t('nav_chat')} / {_t('chat_task_exec')} | 🔒 {_t('chat_demo_need_key')}

👉 **{_t('chat_demo_goto_settings')}**
"""
        )
        st.markdown(f"### {_t('chat_demo_data_preview')}")
        demo = _get_demo_dashboard_data()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                _t("chat_demo_monthly_income"),
                f"¥{demo['financial_summary']['income']:,}",
            )
        with col2:
            st.metric(_t("chat_demo_task_rate"), demo["task_completion"]["rate"])
        with col3:
            st.metric(_t("chat_demo_income_growth"), demo["income_trend"]["growth"])
        st.markdown("---")
        st.caption(f"💡 {_t('chat_demo_api_hint')}")
        st.stop()
    if len(st.session_state.messages) > 0:
        st.caption(f"💡 {_t('chat_history_saved')}")
    if len(st.session_state.messages) == 0:
        st.markdown(f"## {_t('chat_welcome_title')}")
        st.markdown(
            f"{_t('chat_welcome_desc_1')}**{_t('chat_welcome_desc_2')}**"
            f"**{_t('chat_welcome_desc_3')}** — {_t('chat_welcome_desc_4')}"
        )

        st.markdown(f"**{_t('chat_usage_steps')}**")

        has_api_key = _has_api_key()
        if not has_api_key:
            st.warning(
                f"⚠️ **{_t('chat_template_mode')}** — {_t('chat_template_mode_desc')}"
            )
            with st.expander(f"📖 {_t('chat_how_to_get_key')}", expanded=True):
                st.markdown(
                    f"""
**{_t('chat_3step_config')}:**

1. {_t('chat_step1_visit')}
2. {_t('chat_step2_create_env')}
3. {_t('chat_step3_fill_key')}

{_t('chat_config_note')}
"""
                )
        else:
            st.success(f"✅ {_t('chat_ai_ready')}")

        st.markdown(f"### {_t('chat_scenario_title')}")

        st.markdown(f"**{_t('chat_core_scenarios')}**")
        core_cols = st.columns(2)
        for i, sc in enumerate(SCENARIOS_CORE):
            with core_cols[i % 2]:
                if st.button(
                    f"{sc['icon']} **{_t(sc['title'])}**\n\n📌 {_t(sc['desc'])}\n\n{_t('scenario_coverage_label')} {', '.join([_t(c) for c in sc['coverage']])}",
                    key=f"core_{sc['id']}",
                    use_container_width=True,
                ):
                    st.session_state.pending_prompt = sc.get(
                        "prompt", _t("scenario_execute_core", name=_t(sc["title"]))
                    )
                    st.rerun()

        st.divider()
        st.caption(f"💡 {_t('chat_input_execute_hint')}")

    with st.expander(f"🔍 {_t('chat_more_scenarios')}", expanded=False):
        st.markdown(f"**{_t('chat_select_scenario')}**")
        more_cols = st.columns(2)
        for i, sc in enumerate(SCENARIOS_MORE):
            with more_cols[i % 2]:
                if st.button(
                    f"{sc['icon']} {_t(sc['title'])}\n{_t(sc['desc'])}",
                    key=f"more_{sc['id']}",
                    use_container_width=True,
                ):
                    st.session_state.pending_prompt = sc.get(
                        "prompt", _t("scenario_execute_more", name=_t(sc["title"]))
                    )
                    st.rerun()

    _render_chat_history()

    if len(st.session_state.messages) == 0:
        with st.container():
            st.markdown(f"### {_t('chat_try_ask')}")
            example_cols = st.columns(2)
            EXAMPLE_QUERIES = [
                (_t("chat_example_comp"), _t("chat_example_comp_query")),
                (_t("chat_example_marketing"), _t("chat_example_marketing_query")),
                (_t("chat_example_trend"), _t("chat_example_trend_query")),
            ]
            for i, (title, query) in enumerate(EXAMPLE_QUERIES):
                with example_cols[i % 2]:
                    if st.button(title, key=f"example_{i}", use_container_width=True):
                        st.session_state.pending_prompt = query
                        st.rerun()

    prompt = _render_chat_input()

    if prompt:

        pending_confirm = check_pending_confirmation()
        if pending_confirm:
            with st.container():
                st.warning(_t("chat_risk_confirm_warning"))
                confirmed = render_confirmation_dialog(pending_confirm)

                if not confirmed:
                    clear_pending_confirmation()
                    st.stop()

        executor = st.session_state.async_executor
        session_ctx = st.session_state.get("session_ctx")

        is_follow_up = False
        if session_ctx and session_ctx.get_turn_count() > 0:
            from opc_manager.task_engine_v3 import IntentClassifier

            is_follow_up = IntentClassifier.is_follow_up(prompt)
            if is_follow_up:
                st.info(_t("chat_followup_detected"))

        detected_type, confidence, method = safe_detect(prompt)
        st.session_state.detected_type = detected_type
        persona_name, persona_tone = safe_get_persona(detected_type)
        st.session_state.detected_name = persona_name
        safe_track_flywheel(detected_type)

        task_id = executor.submit(
            prompt,
            execute_func=_sync_execute_task,
            session_ctx=st.session_state.get("session_ctx"),
            business_type=detected_type,
        )

        if not task_id:
            st.error(_t("chat_system_busy"))
            st.stop()

        logger.debug(
            "[frontend] 任务已提交: %s (异步模式%s)",
            task_id,
            "，追问模式" if is_follow_up else "",
        )

        with st.chat_message("assistant"):
            status_container = st.status(_t("chat_task_submitted"), expanded=True)

            cancel_col, _ = st.columns([1, 4])
            with cancel_col:
                if st.button(
                    _t("chat_cancel_task"),
                    key=f"cancel_{task_id}",
                    use_container_width=True,
                ):
                    if executor.cancel(task_id):
                        st.warning(_t("chat_task_cancelled"))
                        st.stop()
                    else:
                        st.error(_t("chat_cancel_failed"))

            EXECUTION_PHASES = [
                (0, 3, _t("chat_phase_launch"), _t("chat_phase_launch_hint")),
                (3, 8, _t("chat_phase_search"), _t("chat_phase_search_hint")),
                (8, 25, _t("chat_phase_llm"), _t("chat_phase_llm_hint")),
                (25, 50, _t("chat_phase_polish"), _t("chat_phase_polish_hint")),
                (50, 60, _t("chat_phase_deliver"), _t("chat_phase_deliver_hint")),
            ]

            max_polls = 60
            poll_interval = 1.0
            start_time = time.time()
            progress_placeholder = st.empty()

            for poll_count in range(max_polls):
                task_status = executor.get_status(task_id)
                current_status = task_status.get("status", "unknown")
                elapsed = task_status.get("elapsed", 0)

                if current_status == "pending":
                    if poll_count < 3:
                        status_container.update(label=_t("chat_status_queuing"))
                    time.sleep(poll_interval)
                    continue

                elif current_status == "retrying":
                    retry_count = task_status.get("retry_count", 0)
                    max_retries = task_status.get("max_retries", 2)
                    status_container.update(
                        label=f"🔄 {_t('chat_status_retrying', count=retry_count, max=max_retries)}"
                    )
                    max_polls += 10
                    time.sleep(poll_interval)
                    continue

                elif current_status == "running":
                    session_id = _get_current_session_id()

                    real_progress = None
                    real_message = None
                    real_event_type = None
                    phase_hint = ""

                    if session_id and session_id != "default":
                        try:
                            from opc_manager.progress_emitter import ProgressEmitter

                            emitter = ProgressEmitter()
                            history = emitter.get_history(session_id)
                            if history:
                                latest = history[-1]
                                real_progress = latest.get(
                                    "progress", latest.get("progress_pct")
                                )
                                real_message = latest.get("message", "")
                                real_event_type = latest.get(
                                    "event", latest.get("event_type", "")
                                )
                        except Exception as e:
                            logger.debug(
                                "[frontend] 读取真实进度失败，回退到估算: %s", e
                            )

                    if real_progress is not None:
                        progress_pct = min(real_progress, 100)
                        phase_hint = real_message or phase_hint
                        if real_event_type:
                            phase_icon, phase_name = _get_phase_from_event(
                                real_event_type
                            )
                    else:
                        phase_icon, phase_name, phase_hint = (
                            "⚡",
                            _t("chat_status_executing"),
                            _t("chat_status_processing"),
                        )
                        for phase_start, phase_end, icon, hint in EXECUTION_PHASES:
                            if phase_start <= elapsed < phase_end:
                                phase_icon, phase_name, phase_hint = (
                                    icon,
                                    hint.split("...")[0],
                                    hint,
                                )
                                break
                        if elapsed >= 60:
                            phase_icon, phase_name, phase_hint = (
                                "🔄",
                                _t("chat_status_deep"),
                                _t("chat_status_deep_hint"),
                            )

                        estimated_total = (
                            max(30, elapsed * 1.5)
                            if elapsed < 10
                            else max(30, elapsed / 0.7)
                        )
                        remaining = max(0, estimated_total - elapsed)
                        progress_pct = min(int((elapsed / estimated_total) * 100), 95)

                    status_container.update(
                        label=(
                            f"{phase_icon} {phase_name} ({elapsed:.0f}s / {_t('chat_estimated_remaining')}{remaining:.0f}s)"
                            if real_progress is None
                            else f"{phase_icon} {phase_name}"
                        ),
                        state="running",
                    )
                    progress_placeholder.progress(
                        progress_pct / 100.0,
                        text=f"{_t('chat_real' if real_progress is not None else 'chat_estimated')} {progress_pct}% — {phase_hint} — {_t('chat_elapsed')} {elapsed:.0f}s",
                    )

                    if session_id and session_id != "default":
                        with st.expander(_t("chat_exec_detail"), expanded=False):
                            _render_progress_indicator(session_id)

                    time.sleep(poll_interval)
                    continue

                elif current_status == "done":
                    _handle_task_result(task_id, task_status, prompt, status_container)
                    break

                elif current_status == "failed":
                    error_msg = task_status.get("error_message", _t("error_unknown"))

                    if task_status.get("_cancelled_by_user"):
                        status_container.update(
                            label=_t("chat_status_cancelled"), state="complete"
                        )
                        st.info(_t("chat_cancelled_by_user"))
                        clear_pending_confirmation()
                        break

                    status_container.update(label=_t("chat_task_failed"), state="error")

                    track_error(Exception(error_msg), {"mode": "async"})

                    FRIENDLY_ERRORS = {
                        "timeout": (
                            _t("chat_err_timeout_title"),
                            _t("chat_err_timeout_hint"),
                        ),
                        "connection": (
                            _t("chat_err_network_title"),
                            _t("chat_err_network_hint"),
                        ),
                        "api_key": (
                            _t("chat_err_apikey_title"),
                            _t("chat_err_apikey_hint"),
                        ),
                        "incorrect api key": (
                            _t("chat_err_apikey_title"),
                            _t("chat_err_apikey_hint"),
                        ),
                        "authentication": (
                            _t("chat_err_auth_title"),
                            _t("chat_err_auth_hint"),
                        ),
                        "rate_limit": (
                            _t("chat_err_ratelimit_title"),
                            _t("chat_err_ratelimit_hint"),
                        ),
                        "rate limit": (
                            _t("chat_err_ratelimit_title"),
                            _t("chat_err_ratelimit_hint"),
                        ),
                        "429": (
                            _t("chat_err_ratelimit_title"),
                            _t("chat_err_ratelimit_hint"),
                        ),
                        "server_error": (
                            _t("chat_err_server_title"),
                            _t("chat_err_server_hint"),
                        ),
                        "500": (
                            _t("chat_err_server_title"),
                            _t("chat_err_server_hint"),
                        ),
                        "502": (
                            _t("chat_err_server_title"),
                            _t("chat_err_server_hint"),
                        ),
                        "503": (
                            _t("chat_err_server_title"),
                            _t("chat_err_server_hint"),
                        ),
                    }

                    error_lower = error_msg.lower()
                    friendly_title = _t("chat_err_generic_title")
                    friendly_hint = _t("chat_err_generic_hint")

                    for kw, (title, hint) in FRIENDLY_ERRORS.items():
                        if kw in error_lower:
                            friendly_title = title
                            friendly_hint = hint
                            break

                    prompt_short = html.escape(
                        prompt[:40] + ("..." if len(prompt) > 40 else "")
                    )
                    safe_error = html.escape(error_msg[:300])

                    st.error(friendly_title)
                    show_error(f"{_t('chat_op_failed')}: {friendly_title}")
                    st.caption(f"{_t('chat_about_prompt')}「{prompt_short}」")
                    st.info(friendly_hint)
                    with st.expander(_t("chat_tech_details")):
                        st.code(safe_error)

                    fallback = (
                        f"{friendly_title}\n\n"
                        f"{_t('chat_about_prompt')}**{prompt_short}**\n\n"
                        f"{friendly_hint}\n\n"
                        f"<details><summary>{_t('chat_tech_details')}</summary>\n\n`{safe_error}`\n</details>"
                    )
                    st.session_state.messages.append(
                        {"role": "assistant", "content": fallback}
                    )
                    _save_chat_history()
                    st.session_state.last_failed_prompt = prompt
                    break

                elif current_status == "cancelled":
                    status_container.update(
                        label=_t("chat_status_cancelled"), state="complete"
                    )
                    st.info(_t("chat_cancelled_by_user"))
                    break

                else:
                    time.sleep(poll_interval)
                    continue

            else:
                status_container.update(label=_t("chat_status_timeout"), state="error")
                st.warning(_t("chat_timeout_hint"))

    failed_prompt = st.session_state.pop("last_failed_prompt", None)
    if failed_prompt:
        if st.button(f"🔄 {_t('chat_retry')}", key=f"retry_{int(time.time()*1000)}"):
            st.session_state.pending_prompt = failed_prompt
            st.rerun()
