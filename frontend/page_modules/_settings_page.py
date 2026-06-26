"""Settings page module for OPC-Agents frontend.

Contains all settings-related UI rendering functions:
- LLM configuration
- SMTP configuration
- API keys management
- Security settings
- Profile settings
- Data backup/restore functionality
"""

import streamlit as st
import os
import re
import logging
from datetime import datetime
from pathlib import Path

from opc_manager.i18n import t as _t

logger = logging.getLogger(__name__)

_WORKSPACE_DIR = os.environ.get("OPC_WORKSPACE", os.getcwd())


def _create_settings_page():
    """Create the unified Settings page with 5 tabs.

    Tabs:
    1.  LLM Configuration — Provider selection, API key input, connection test
    2.  SMTP Configuration — Email server setup, preset provider, test connection
    3.  API Keys — All API keys management with masking
    4.  Security — Encryption key status, regenerate option
    5.  Profile — User info, company, timezone, language
    """
    try:
        from opc_manager.settings import get_settings

        settings = get_settings()
    except ImportError:
        st.error(_t("settings_module_not_ready"))
        return

    st.markdown(f"## {_t('settings_page_title')}")
    settings_tabs = st.tabs(
        [
            _t("settings_llm"),
            _t("settings_smtp"),
            _t("settings_api_keys"),
            _t("settings_security"),
            _t("settings_profile"),
            _t("settings_backup"),
        ]
    )

    with settings_tabs[0]:
        _render_llm_settings(settings)

    with settings_tabs[1]:
        _render_smtp_settings(settings)

    with settings_tabs[2]:
        _render_api_keys_settings(settings)

    with settings_tabs[3]:
        _render_security_settings(settings)

    with settings_tabs[4]:
        _render_profile_settings(settings)

    with settings_tabs[5]:
        _render_data_backup_settings()


def _render_llm_settings(settings):
    """Render LLM configuration tab"""

    st.markdown(f"### {_t('settings_llm')}")

    llm_config = settings.llm.__dict__

    with st.form("llm_config_form"):
        provider = st.radio(
            _t("llm_provider"),
            ["MokaAI", "OpenAI", "智谱GLM", "Ollama"],
            index=(
                ["MokaAI", "OpenAI", "智谱GLM", "Ollama"].index(
                    llm_config.get("provider", "MokaAI")
                )
                if llm_config.get("provider", "MokaAI")
                in ["MokaAI", "OpenAI", "智谱GLM", "Ollama"]
                else 0
            ),
            help=_t("settings_llm_provider_help"),
        )

        col_key, col_url = st.columns(2)
        with col_key:
            api_key = st.text_input(
                _t("llm_api_key"),
                value=llm_config.get("api_key", ""),
                type="password",
                help=_t("settings_llm_apikey_help"),
                placeholder="sk-...",
            )
        with col_url:
            base_url = st.text_input(
                _t("llm_base_url"),
                value=llm_config.get("base_url", ""),
                help=_t("settings_llm_baseurl_help"),
                placeholder="https://api.example.com/v1",
            )

        model = st.text_input(
            _t("llm_model"),
            value=llm_config.get("model", ""),
            help=_t("settings_llm_model_help"),
            placeholder=_t("llm_model_placeholder"),
        )

        col_tokens, col_temp = st.columns(2)
        with col_tokens:
            max_tokens = st.slider(
                _t("settings_max_tokens"),
                min_value=1000,
                max_value=16000,
                value=int(llm_config.get("max_tokens", 4000)),
                step=1000,
                help=_t("settings_max_tokens_help"),
            )
        with col_temp:
            temperature = st.slider(
                _t("settings_temperature"),
                min_value=0.0,
                max_value=2.0,
                value=float(llm_config.get("temperature", 0.7)),
                step=0.1,
                help=_t("settings_temperature_help"),
            )

        col_test, col_save = st.columns([1, 1])
        with col_test:
            test_clicked = st.form_submit_button(
                _t("llm_test_connection"), type="secondary"
            )
        with col_save:
            save_clicked = st.form_submit_button(_t("llm_save"), type="primary")

        if test_clicked:
            if not api_key or not api_key.strip():
                st.error(_t("settings_llm_key_required"))
            else:
                # Real LLM connection test — sends a minimal request
                with st.spinner(_t("llm_testing")):
                    try:
                        import requests

                        headers = {
                            "Authorization": f"Bearer {api_key.strip()}",
                            "Content-Type": "application/json",
                        }
                        payload = {
                            "model": model,
                            "messages": [{"role": "user", "content": "Hi"}],
                            "max_tokens": 5,
                        }
                        resp = requests.post(
                            f"{base_url.rstrip('/')}/chat/completions",
                            headers=headers,
                            json=payload,
                            timeout=15,
                        )
                        if resp.status_code == 200:
                            st.success(f" {_t('llm_test_success')}")
                        else:
                            detail = resp.text[:200]
                            st.error(
                                f" {_t('llm_test_failed')} "
                                f"(HTTP {resp.status_code}): {detail}"
                            )
                    except requests.exceptions.Timeout:
                        st.error(f" {_t('llm_test_timeout')}")
                    except requests.exceptions.ConnectionError:
                        st.error(f" {_t('llm_test_connection_error')}")
                    except Exception as e:
                        st.error(f" {_t('llm_test_failed')}: {e}")

        if save_clicked:
            new_config = {
                "provider": provider,
                "api_key": api_key,
                "base_url": base_url,
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if settings.update_llm(**new_config):
                st.toast(f" {_t('settings_llm_saved')}", icon="")
                st.success(f" {_t('settings_llm_saved')}")
                st.rerun()
            else:
                st.error(_t("settings_save_failed"))


def _render_smtp_settings(settings):
    """Render SMTP configuration tab"""

    st.markdown(f"### {_t('settings_smtp_heading')}")

    smtp_config = settings.smtp.__dict__

    SMTP_PRESETS = {
        _t("settings_smtp_preset_custom"): {},
        _t("settings_smtp_preset_qq"): {
            "host": "smtp.qq.com",
            "port": 587,
            "tls": True,
        },
        _t("settings_smtp_preset_163"): {
            "host": "smtp.163.com",
            "port": 465,
            "tls": True,
        },
        _t("settings_smtp_preset_gmail"): {
            "host": "smtp.gmail.com",
            "port": 587,
            "tls": True,
        },
        _t("settings_smtp_preset_outlook"): {
            "host": "smtp.office365.com",
            "port": 587,
            "tls": True,
        },
    }

    with st.form("smtp_config_form"):
        preset = st.selectbox(
            _t("settings_smtp_preset_label"),
            list(SMTP_PRESETS.keys()),
            help=_t("settings_smtp_preset_help"),
        )

        preset_config = SMTP_PRESETS.get(preset, {})

        host = st.text_input(
            _t("smtp_host"),
            value=preset_config.get("host", smtp_config.get("host", "")),
            help=_t("settings_smtp_host_help"),
            placeholder="smtp.example.com",
        )

        port = st.number_input(
            _t("smtp_port"),
            min_value=1,
            max_value=65535,
            value=int(preset_config.get("port", smtp_config.get("port", 587))),
            help=_t("settings_smtp_port_help"),
        )

        col_user, col_pass = st.columns(2)
        with col_user:
            username = st.text_input(
                _t("smtp_username"),
                value=smtp_config.get("username", ""),
                help=_t("settings_smtp_username_help"),
                placeholder="your@email.com",
            )
        with col_pass:
            password = st.text_input(
                _t("smtp_password"),
                value=smtp_config.get("password", ""),
                type="password",
                help=_t("settings_smtp_password_help"),
                placeholder="••••••••",
            )

        tls_enabled = st.checkbox(
            _t("settings_smtp_tls"),
            value=bool(preset_config.get("tls", smtp_config.get("tls", True))),
            help=_t("settings_smtp_tls_help"),
        )

        from_email = st.text_input(
            _t("settings_smtp_from_email"),
            value=smtp_config.get("from_email", ""),
            help=_t("settings_smtp_from_help"),
            placeholder="noreply@example.com",
        )

        col_test, col_save = st.columns([1, 1])
        with col_test:
            test_clicked = st.form_submit_button(_t("smtp_test"), type="secondary")
        with col_save:
            save_clicked = st.form_submit_button(_t("llm_save"), type="primary")

        if test_clicked:
            new_config = {
                "host": host,
                "port": port,
                "username": username,
                "password": password,
                "tls": tls_enabled,
                "from_email": from_email,
            }
            settings.update_smtp(**new_config)
            with st.spinner(_t("settings_smtp_testing")):
                test_result = settings.test_smtp_connection()
                if test_result["success"]:
                    st.success(
                        f" {_t('settings_smtp_success', latency=test_result['latency_ms'])}"
                    )
                    st.info(
                        f"{_t('settings_smtp_server_response')}: {test_result['message']}"
                    )
                else:
                    st.error(
                        f" {_t('settings_smtp_failed', msg=test_result['message'])}"
                    )

        if save_clicked:
            new_config = {
                "host": host,
                "port": port,
                "username": username,
                "password": password,
                "tls": tls_enabled,
                "from_email": from_email,
            }
            if settings.update_smtp(**new_config):
                st.toast(f" {_t('settings_smtp_saved')}", icon="")
                st.success(f" {_t('settings_smtp_saved')}")
                st.rerun()
            else:
                st.error(_t("settings_save_failed"))


def _render_api_keys_settings(settings):
    """Render API Keys management tab"""

    st.info(_t("settings_apikeys_info"))

    st.markdown(f"**{_t('settings_apikeys_configured')}**")

    llm_key = settings.llm.api_key
    smtp_pass = settings.smtp.password

    with st.expander(f" {_t('settings_apikeys_llm_key')}", expanded=bool(llm_key)):
        if llm_key:
            masked = "****" + llm_key[-4:] if len(llm_key) > 4 else "****"
            col_val, col_copy = st.columns([3, 1])
            with col_val:
                st.text_input(
                    _t("settings_apikeys_masked"), value=masked, disabled=True
                )
                st.caption(
                    f"{_t('settings_apikeys_last4')}: `{llm_key[-4:]}`"
                    if len(llm_key) >= 4
                    else _t("settings_apikeys_not_shown")
                )
            with col_copy:
                if st.button(_t("settings_apikeys_copy_key"), key="copy_llm_key"):
                    st.code(llm_key, language=None)
                    st.success(_t("settings_apikeys_copied"))
        else:
            st.warning(_t("settings_apikeys_no_llm"))
            st.caption(_t("settings_apikeys_goto_llm"))

    with st.expander(f" {_t('settings_apikeys_smtp_pass')}", expanded=bool(smtp_pass)):
        if smtp_pass:
            masked = "****" + smtp_pass[-4:] if len(smtp_pass) > 4 else "****"
            col_val, col_copy = st.columns([3, 1])
            with col_val:
                st.text_input(
                    _t("settings_apikeys_pass_masked"), value=masked, disabled=True
                )
                st.caption(
                    f"{_t('settings_apikeys_last4')}: `{smtp_pass[-4:]}`"
                    if len(smtp_pass) >= 4
                    else _t("settings_apikeys_not_shown")
                )
            with col_copy:
                if st.button(_t("settings_apikeys_copy_pass"), key="copy_smtp_pass"):
                    st.code(smtp_pass, language=None)
                    st.success(_t("settings_apikeys_copied"))
        else:
            st.warning(_t("settings_apikeys_no_smtp"))
            st.caption(_t("settings_apikeys_goto_smtp"))

    st.divider()

    st.markdown(f"**{_t('settings_apikeys_add_new')}**")
    st.info(_t("settings_apikeys_coming_soon"))
    st.caption(_t("settings_apikeys_config_in_tab"))


def _render_security_settings(settings):
    """Render Security settings tab"""

    st.markdown(f"### {_t('settings_security_heading')}")

    security = settings.security

    if security.encryption_key:
        if security.auto_generated:
            status_text = _t("settings_security_auto_generated")
            status_color = "green"
        else:
            status_text = _t("settings_security_manual")
            status_color = "blue"
    else:
        status_text = _t("settings_security_not_set")
        status_color = "orange"

    st.markdown(_t("settings_encryption_status"))
    st.markdown(f"- {_t('settings_status_label')}: :{status_color}[{status_text}]")
    if security.auto_generated:
        st.markdown(
            f"- {_t('settings_gen_method')}: {_t('settings_gen_method_csprng')}"
        )
    st.markdown(
        f"- {_t('settings_storage_location')}: `.env.local` {_t('settings_storage_ignored')}"
    )
    st.markdown(
        f"- {_t('settings_key_length')}: 256{_t('settings_bits')} (64{_t('settings_hex_chars')})"
    )

    st.divider()

    st.info(_t("settings_security_tips_label"))
    st.caption(f"• {_t('settings_security_tip1')}")
    st.caption(f"• {_t('settings_security_tip2')}")
    st.caption(f"• {_t('settings_security_tip3')}")

    st.divider()

    st.caption(f" {_t('settings_regenerate_warning')}")


def _render_profile_settings(settings):
    """Render Profile settings tab"""

    st.markdown(f"### {_t('settings_profile_heading')}")

    profile = settings.profile.__dict__

    TIMEZONES = [
        "Asia/Shanghai",
        "Asia/Tokyo",
        "Asia/Singapore",
        "Asia/Dubai",
        "Europe/London",
        "Europe/Berlin",
        "Europe/Paris",
        "America/New_York",
        "America/Los_Angeles",
        "America/Chicago",
        "Pacific/Auckland",
        "Australia/Sydney",
    ]

    with st.form("profile_form"):
        username = st.text_input(
            _t("profile_name"),
            value=profile.get("user_name", ""),
            placeholder=_t("settings_profile_name_placeholder"),
            help=_t("settings_profile_name_help"),
        )

        company = st.text_input(
            _t("profile_company"),
            value=profile.get("company_name", ""),
            placeholder=_t("settings_profile_company_placeholder"),
            help=_t("settings_profile_company_help"),
        )

        col_tz, col_lang = st.columns(2)
        with col_tz:
            timezone = st.selectbox(
                _t("profile_timezone"),
                TIMEZONES,
                index=(
                    TIMEZONES.index(profile.get("timezone", "Asia/Shanghai"))
                    if profile.get("timezone", "Asia/Shanghai") in TIMEZONES
                    else 0
                ),
                help=_t("settings_profile_tz_help"),
            )
        with col_lang:
            current_locale = profile.get("language", "zh_CN")
            locale_names = {
                "zh_CN": "中文",
                "en_US": "English",
                "ja_JP": "日本語",
            }
            display_language = locale_names.get(current_locale, current_locale)
            st.text_input(
                _t("profile_language"),
                value=display_language,
                disabled=True,
                help=_t("settings_profile_lang_help"),
            )

        submitted = st.form_submit_button(_t("settings_profile_save_btn"))
        if submitted:
            new_profile = {
                "user_name": username,
                "company_name": company,
                "timezone": timezone,
            }
            if settings.update_profile(**new_profile):
                st.toast(f" {_t('settings_profile_saved')}", icon="")
                st.success(f" {_t('settings_profile_saved')}")
                st.rerun()
            else:
                st.error(_t("settings_save_failed"))


def _render_data_backup_settings():
    """Render Data Backup settings tab.

    Features:
    - Create backup button with progress indicator
    - List existing backups with download/delete options
    - Restore from backup with confirmation
    - Export data in JSON/CSV/ZIP formats
    """

    st.markdown(f"### {_t('settings_backup_heading')}")

    st.info(_t("settings_backup_info"))

    backup_tabs = st.tabs(
        [
            _t("settings_backup_tab_create"),
            _t("settings_backup_tab_list"),
            _t("settings_backup_tab_export"),
            _t("settings_backup_tab_restore"),
        ]
    )

    with backup_tabs[0]:
        _render_create_backup_tab()

    with backup_tabs[1]:
        _render_backup_list_tab()

    with backup_tabs[2]:
        _render_export_data_tab()

    with backup_tabs[3]:
        _render_restore_data_tab()


def _render_create_backup_tab():
    """Render the create backup tab."""
    st.markdown(f"#### {_t('settings_backup_create_heading')}")

    include_attachments = st.checkbox(
        _t("settings_backup_include_attachments"),
        value=False,
        help=_t("settings_backup_attachments_help"),
    )

    col_create, _ = st.columns([1, 2])
    with col_create:
        if st.button(
            _t("settings_backup_create_btn"), type="primary", use_container_width=True
        ):
            with st.spinner(_t("settings_backup_creating")):
                try:
                    from opc_manager.data_backup import get_backup_manager

                    manager = get_backup_manager()
                    backup_path, manifest = manager.create_backup(
                        include_attachments=include_attachments
                    )

                    st.success(
                        f" {_t('settings_backup_created', name=backup_path.name)}"
                    )
                    st.json(
                        {
                            _t("settings_backup_json_filename"): backup_path.name,
                            _t(
                                "settings_backup_json_size"
                            ): f"{manifest.total_size_bytes / (1024*1024):.2f} MB",
                            _t("settings_backup_json_files"): manifest.total_files,
                            _t("settings_backup_json_version"): manifest.version,
                            _t(
                                "settings_backup_json_checksum"
                            ): f"{manifest.checksum_sha256[:16]}...",
                            _t("settings_backup_json_time"): manifest.created_at,
                        }
                    )
                    st.balloons()
                except Exception as e:
                    logger.error("[frontend] Create backup error: %s", e)
                    st.error(f" {_t('settings_backup_create_failed', error=str(e))}")


def _render_backup_list_tab():
    """Render the backup list tab."""
    st.markdown(f"#### {_t('settings_backup_list_heading')}")

    try:
        from opc_manager.data_backup import get_backup_manager

        manager = get_backup_manager()
        backups = manager.list_backups()

        if not backups:
            st.info(_t("settings_backup_empty"))
            return

        st.caption(_t("settings_backup_count", count=len(backups)))

        for idx, backup in enumerate(backups):
            with st.expander(
                f" {backup['filename']} — {backup['size_mb']} MB ({backup['created_at'][:10]})",
                expanded=(idx == 0),
            ):
                col_dl, col_del, _ = st.columns([1, 1, 2])

                with col_dl:
                    backup_file_path = Path(backup["path"])
                    if backup_file_path.exists():
                        with open(backup_file_path, "rb") as f:
                            zip_bytes = f.read()
                        st.download_button(
                            label=_t("settings_backup_download"),
                            data=zip_bytes,
                            file_name=backup["filename"],
                            mime="application/zip",
                            key=f"dl_backup_{idx}",
                            use_container_width=True,
                        )

                with col_del:
                    if st.button(
                        _t("settings_backup_delete"),
                        key=f"del_backup_{idx}",
                        use_container_width=True,
                    ):
                        if manager.delete_backup(backup["path"]):
                            st.success(_t("settings_backup_deleted"))
                            st.rerun()
                        else:
                            st.error(_t("settings_backup_delete_failed"))

                st.caption(f"{_t('settings_backup_full_path')}: `{backup['path']}`")

    except ImportError:
        st.warning(_t("settings_backup_module_not_ready"))
    except Exception as e:
        logger.error("[frontend] Backup list error: %s", e)
        st.error(f" {_t('settings_backup_list_failed', error=str(e))}")


def _render_export_column(
    fmt: str,
    btn_label_key: str,
    btn_help_key: str,
    dl_label_key: str,
    done_key: str,
    mime: str,
    file_ext: str,
    filename_prefix: str,
    dl_key: str,
):
    """Render a single export format column (JSON/CSV/ZIP)."""
    if st.button(
        _t(btn_label_key),
        use_container_width=True,
        help=_t(btn_help_key),
    ):
        with st.spinner(_t("settings_exporting")):
            try:
                from opc_manager.data_backup import get_backup_manager

                manager = get_backup_manager()
                data = manager.export_data(format_type=fmt)
                st.download_button(
                    label=_t(dl_label_key),
                    data=data,
                    file_name=f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_ext}",
                    mime=mime,
                    key=dl_key,
                    use_container_width=True,
                )
                st.success(_t(done_key))
            except Exception as e:
                logger.error("[frontend] Export %s error: %s", fmt.upper(), e)
                st.error(
                    f" {_t('settings_export_failed', fmt=fmt.upper(), error=str(e))}"
                )


def _render_export_data_tab():
    """Render the export data tab."""
    st.markdown(f"#### {_t('settings_backup_export_heading')}")

    st.markdown(f"**{_t('settings_backup_export_format')}**")

    format_col1, format_col2, format_col3 = st.columns(3)

    with format_col1:
        _render_export_column(
            fmt="json",
            btn_label_key="settings_export_json",
            btn_help_key="settings_export_json_help",
            dl_label_key="settings_download_json",
            done_key="settings_export_json_done",
            mime="application/json",
            file_ext="json",
            filename_prefix="opc_agents_export",
            dl_key="dl_export_json",
        )

    with format_col2:
        _render_export_column(
            fmt="csv",
            btn_label_key="settings_export_csv",
            btn_help_key="settings_export_csv_help",
            dl_label_key="settings_download_csv",
            done_key="settings_export_csv_done",
            mime="text/csv",
            file_ext="csv",
            filename_prefix="opc_agents_export",
            dl_key="dl_export_csv",
        )

    with format_col3:
        _render_export_column(
            fmt="zip",
            btn_label_key="settings_export_zip",
            btn_help_key="settings_export_zip_help",
            dl_label_key="settings_download_zip",
            done_key="settings_export_zip_done",
            mime="application/zip",
            file_ext="zip",
            filename_prefix="opc_agents_backup",
            dl_key="dl_export_zip",
        )

    st.divider()
    st.caption(_t("settings_export_format_hint"))


def _render_restore_data_tab():
    st.markdown(f"#### {_t('settings_backup_restore_heading')}")

    st.warning(_t("settings_backup_restore_warning"))

    uploaded_file = st.file_uploader(
        _t("settings_backup_upload_label"),
        type=["zip"],
        help=_t("settings_backup_upload_help"),
    )

    if uploaded_file:
        _size_kb = uploaded_file.size / 1024
        st.info(
            f" {_t('settings_backup_file_selected', name=uploaded_file.name, size=f'{_size_kb:.1f}')}"
        )

        # Save uploaded file to temp location (sanitize filename)
        safe_name = re.sub(r"[^\w\-.]", "_", uploaded_file.name)[:100]
        temp_dir = Path(_WORKSPACE_DIR) / "data" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / f"restore_{safe_name}"

        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        confirm_restore = st.checkbox(
            _t("settings_backup_confirm_restore"),
            key="confirm_restore_checkbox",
        )

        col_restore, _ = st.columns([1, 2])
        with col_restore:
            if st.button(
                _t("settings_backup_start_restore"),
                type="primary",
                use_container_width=True,
                disabled=not confirm_restore,
                help=_t("settings_backup_restore_help"),
            ):
                with st.spinner(_t("settings_backup_restoring")):
                    try:
                        from opc_manager.data_backup import get_backup_manager

                        manager = get_backup_manager()
                        result = manager.restore_backup(str(temp_path), confirm=True)

                        if result["success"]:
                            st.success(
                                f" {_t('settings_backup_restore_success', files=result.get('restored_files', 0))}"
                            )
                            st.json(
                                {
                                    _t("settings_backup_restored_files"): result.get(
                                        "restored_files", 0
                                    ),
                                }
                            )
                            st.balloons()
                            st.warning(_t("settings_backup_refresh_hint"))
                        else:
                            st.error(
                                f" {_t('settings_backup_restore_failed', error=result.get('error', _t('settings_unknown_error')))}"
                            )

                        # Cleanup temp file
                        if temp_path.exists():
                            temp_path.unlink()

                    except Exception as e:
                        logger.error("[frontend] Restore error: %s", e)
                        st.error(
                            f" {_t('settings_backup_restore_error', error=str(e))}"
                        )
