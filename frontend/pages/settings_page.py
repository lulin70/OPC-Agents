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

logger = logging.getLogger(__name__)

_WORKSPACE_DIR = os.environ.get("OPC_WORKSPACE", os.getcwd())


def _create_settings_page():
    """Create the unified Settings page with 5 tabs.

    Tabs:
    1. 🧠 LLM Configuration — Provider selection, API key input, connection test
    2. 📧 SMTP Configuration — Email server setup, preset providers, test connection
    3. 🔑 API Keys — All API keys management with masking
    4. 🔒 Security — Encryption key status, regenerate option
    5. 👤 Profile — User info, company, timezone, language
    """
    try:
        from opc_manager.settings import get_settings
        settings = get_settings()
    except ImportError:
        st.error("⚠️ 设置模块未就绪，请稍后再试")
        return

    st.markdown("## ⚙️ 系统设置")

    from opc_manager.i18n import t as _t
    settings_tabs = st.tabs([_t("settings_llm"), _t("settings_smtp"), _t("settings_api_keys"), _t("settings_security"), _t("settings_profile"), _t("settings_backup")])

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
    from opc_manager.i18n import t as _t
    st.markdown("### 🧠 LLM 配置")

    llm_config = settings.llm.__dict__

    with st.form("llm_config_form"):
        provider = st.radio(
            _t("llm_provider"),
            ["MokaAI", "OpenAI", "智谱GLM", "Ollama"],
            index=["MokaAI", "OpenAI", "智谱GLM", "Ollama"].index(llm_config.get("provider", "MokaAI")) if llm_config.get("provider", "MokaAI") in ["MokaAI", "OpenAI", "智谱GLM", "Ollama"] else 0,
            help="选择你要使用的LLM服务提供商",
        )

        col_key, col_url = st.columns(2)
        with col_key:
            api_key = st.text_input(
                _t("llm_api_key"),
                value=llm_config.get("api_key", ""),
                type="password",
                help="输入你的API密钥",
                placeholder="sk-...",
            )
        with col_url:
            base_url = st.text_input(
                _t("llm_base_url"),
                value=llm_config.get("base_url", ""),
                help="API端点地址（可选，留空使用默认值）",
                placeholder="https://api.example.com/v1",
            )

        model = st.text_input(
            _t("llm_model"),
            value=llm_config.get("model", ""),
            help="指定使用的模型名称（可选）",
            placeholder="gpt-4 / chatglm-turbo 等",
        )

        col_tokens, col_temp = st.columns(2)
        with col_tokens:
            max_tokens = st.slider(
                "Max Tokens",
                min_value=1000,
                max_value=16000,
                value=int(llm_config.get("max_tokens", 4000)),
                step=1000,
                help="最大生成token数",
            )
        with col_temp:
            temperature = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=2.0,
                value=float(llm_config.get("temperature", 0.7)),
                step=0.1,
                help="控制输出的随机性（越高越随机）",
            )

        col_test, col_save = st.columns([1, 1])
        with col_test:
            test_clicked = st.form_submit_button("🔗 测试连接", type="secondary")
        with col_save:
            save_clicked = st.form_submit_button("💾 保存配置", type="primary")

        if test_clicked:
            if api_key and api_key.strip():
                st.success("✅ API Key 已配置（实际连接将在使用时验证）")
            else:
                st.error("❌ 请先输入有效的 API Key")

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
                st.success("✅ LLM配置已保存")
                st.rerun()
            else:
                st.error("❌ 保存失败，请重试")


def _render_smtp_settings(settings):
    """Render SMTP configuration tab"""
    st.markdown("### 📧 SMTP 邮件配置")

    smtp_config = settings.smtp.__dict__

    SMTP_PRESETS = {
        "自定义": {},
        "QQ邮箱": {"host": "smtp.qq.com", "port": 587, "tls": True},
        "163邮箱": {"host": "smtp.163.com", "port": 465, "tls": True},
        "Gmail": {"host": "smtp.gmail.com", "port": 587, "tls": True},
        "Outlook": {"host": "smtp.office365.com", "port": 587, "tls": True},
    }

    with st.form("smtp_config_form"):
        preset = st.selectbox(
            "预设服务商",
            list(SMTP_PRESETS.keys()),
            help="选择邮件服务商后自动填充常用配置",
        )

        preset_config = SMTP_PRESETS.get(preset, {})

        host = st.text_input(
            "SMTP 服务器",
            value=preset_config.get("host", smtp_config.get("host", "")),
            help="邮件服务器地址",
            placeholder="smtp.example.com",
        )

        port = st.number_input(
            "端口",
            min_value=1,
            max_value=65535,
            value=int(preset_config.get("port", smtp_config.get("port", 587))),
            help="常用端口: 25(普通), 465(SSL), 587(TLS)",
        )

        col_user, col_pass = st.columns(2)
        with col_user:
            username = st.text_input(
                "用户名",
                value=smtp_config.get("username", ""),
                help="邮箱登录用户名",
                placeholder="your@email.com",
            )
        with col_pass:
            password = st.text_input(
                "密码/授权码",
                value=smtp_config.get("password", ""),
                type="password",
                help="邮箱密码或应用专用授权码",
                placeholder="••••••••",
            )

        tls_enabled = st.checkbox(
            "启用 TLS 加密",
            value=bool(preset_config.get("tls", smtp_config.get("tls", True))),
            help="推荐开启TLS加密保护邮件传输安全",
        )

        from_email = st.text_input(
            "发件人邮箱",
            value=smtp_config.get("from_email", ""),
            help="发送邮件时显示的发件人地址",
            placeholder="noreply@example.com",
        )

        col_test, col_save = st.columns([1, 1])
        with col_test:
            test_clicked = st.form_submit_button("🔗 测试连接", type="secondary")
        with col_save:
            save_clicked = st.form_submit_button("💾 保存配置", type="primary")

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
            with st.spinner("正在测试SMTP连接..."):
                test_result = settings.test_smtp_connection()
                if test_result["success"]:
                    st.success(f"✅ SMTP连接成功！延迟: {test_result['latency_ms']}ms")
                    st.info(f"服务器响应: {test_result['message']}")
                else:
                    st.error(f"❌ 连接失败: {test_result['message']}")

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
                st.success("✅ SMTP配置已保存")
                st.rerun()
            else:
                st.error("❌ 保存失败，请重试")


def _render_api_keys_settings(settings):
    """Render API Keys management tab"""
    st.markdown("### 🔑 API 密钥管理")

    st.info("💡 当前显示已配置的服务密钥。完整的API密钥管理功能即将支持。")

    st.markdown("**已配置的密钥：**")

    llm_key = settings.llm.api_key
    smtp_pass = settings.smtp.password

    with st.expander("🧠 LLM API Key", expanded=bool(llm_key)):
        if llm_key:
            masked = "****" + llm_key[-4:] if len(llm_key) > 4 else "****"
            col_val, col_copy = st.columns([3, 1])
            with col_val:
                st.text_input("密钥值（掩码）", value=masked, disabled=True)
                st.caption(f"最后4位: `{llm_key[-4:]}`" if len(llm_key) >= 4 else "未显示")
            with col_copy:
                if st.button("📋 复制完整密钥", key="copy_llm_key"):
                    st.clipboard_text(llm_key)
                    st.success("✅ 已复制到剪贴板")
        else:
            st.warning("⚠️ 未配置 LLM API Key")
            st.caption("请前往「LLM 配置」标签页设置")

    with st.expander("📧 SMTP 密码/授权码", expanded=bool(smtp_pass)):
        if smtp_pass:
            masked = "****" + smtp_pass[-4:] if len(smtp_pass) > 4 else "****"
            col_val, col_copy = st.columns([3, 1])
            with col_val:
                st.text_input("密码值（掩码）", value=masked, disabled=True)
                st.caption(f"最后4位: `{smtp_pass[-4:]}`" if len(smtp_pass) >= 4 else "未显示")
            with col_copy:
                if st.button("📋 复制完整密码", key="copy_smtp_pass"):
                    st.clipboard_text(smtp_pass)
                    st.success("✅ 已复制到剪贴板")
        else:
            st.warning("⚠️ 未配置 SMTP 密码")
            st.caption("请前往「SMTP 邮件配置」标签页设置")

    st.divider()

    st.markdown("**➕ 添加新密钥**")
    st.info("🚧 即将支持：多API密钥管理、自动轮换、权限控制等功能")
    st.caption("当前版本请在对应的配置标签页中直接输入密钥")


def _render_security_settings(settings):
    """Render Security settings tab"""
    st.markdown("### 🔒 安全设置")

    security = settings.security

    if security.encryption_key:
        if security.auto_generated:
            status_text = "✅ 已自动生成"
            status_color = "green"
        else:
            status_text = "🔐 手动设置"
            status_color = "blue"
    else:
        status_text = "⚠️ 未设置"
        status_color = "orange"

    st.markdown("**加密密钥状态**")
    st.markdown(f"- 状态: :{status_color}[{status_text}]")
    if security.auto_generated:
        st.markdown("- 生成方式: 系统自动生成（CSPRNG安全随机数）")
    st.markdown(f"- 存储位置: `.env.local` 文件（已加入 .gitignore）")
    st.markdown("- 密钥长度: 256位（64个十六进制字符）")

    st.divider()

    st.info("💡 **安全提示：**")
    st.caption("• 加密密钥用于保护敏感配置数据（API密钥、密码等）")
    st.caption("• 密钥丢失将导致无法解密已加密的数据")
    st.caption("• 请定期备份 `.env.local` 文件到安全位置")

    st.divider()

    col_regenerate, _ = st.columns([1, 3])
    with col_regenerate:
        if st.button("🔄 重新生成密钥", type="secondary", disabled=True):
            pass
    st.caption("⚠️ 重新生成功能为高级操作，请联系管理员执行（需手动删除 .env.local 后重启系统）")


def _render_profile_settings(settings):
    """Render Profile settings tab"""
    st.markdown("### 👤 个人信息")

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

    LANGUAGES = ["中文", "English"]

    with st.form("profile_form"):
        username = st.text_input(
            "用户名",
            value=profile.get("user_name", ""),
            placeholder="输入你的名字",
            help="用于个性化显示",
        )

        company = st.text_input(
            "公司名称",
            value=profile.get("company_name", ""),
            placeholder="输入公司或组织名称（可选）",
            help="用于生成文档的公司信息",
        )

        col_tz, col_lang = st.columns(2)
        with col_tz:
            timezone = st.selectbox(
                "时区",
                TIMEZONES,
                index=TIMEZONES.index(profile.get("timezone", "Asia/Shanghai")) if profile.get("timezone", "Asia/Shanghai") in TIMEZONES else 0,
                help="选择你所在的时区",
            )
        with col_lang:
            language = st.selectbox(
                "语言",
                LANGUAGES,
                index=LANGUAGES.index(profile.get("language", "zh_CN")) if profile.get("language", "zh_CN") in ["中文", "English"] else 0,
                help="界面语言设置（即将支持多语言切换）",
            )

        submitted = st.form_submit_button("💾 保存个人信息")
        if submitted:
            new_profile = {
                "user_name": username,
                "company_name": company,
                "timezone": timezone,
                "language": language,
            }
            if settings.update_profile(**new_profile):
                st.success("✅ 个人信息已保存")
                st.rerun()
            else:
                st.error("❌ 保存失败，请重试")


def _render_data_backup_settings():
    """Render Data Backup settings tab.

    Features:
    - Create backup button with progress indicator
    - List existing backups with download/delete options
    - Restore from backup with confirmation
    - Export data in JSON/CSV/ZIP formats
    """
    st.markdown("### 💾 数据备份与恢复")

    st.info("💡 **数据安全提示：** 定期备份你的数据，防止意外丢失。备份文件包含所有客户记录、财务数据和任务信息。")

    backup_tabs = st.tabs(["📦 创建备份", "📋 备份列表", "📥 导出数据", "🔄 恢复数据"])

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
    st.markdown("#### 📦 创建新备份")

    include_attachments = st.checkbox(
        "包含附件文件",
        value=False,
        help="勾选后备份将包含附件（会增大备份文件大小）",
    )

    col_create, _ = st.columns([1, 2])
    with col_create:
        if st.button("🚀 立即创建备份", type="primary", use_container_width=True):
            with st.spinner("正在创建备份，请稍候..."):
                try:
                    from opc_manager.data_backup import get_backup_manager
                    manager = get_backup_manager()
                    backup_path, manifest = manager.create_backup(
                        include_attachments=include_attachments
                    )

                    st.success(f"✅ 备份创建成功！")
                    st.json({
                        "文件名": backup_path.name,
                        "大小": f"{manifest.total_size_bytes / (1024*1024):.2f} MB",
                        "文件数": manifest.total_files,
                        "版本": manifest.version,
                        "校验和": f"{manifest.checksum_sha256[:16]}...",
                        "创建时间": manifest.created_at,
                    })
                    st.balloons()
                except Exception as e:
                    logger.error("[frontend] Create backup error: %s", e)
                    st.error(f"❌ 备份创建失败: {str(e)}")


def _render_backup_list_tab():
    """Render the backup list tab."""
    st.markdown("#### 📋 已有备份")

    try:
        from opc_manager.data_backup import get_backup_manager
        manager = get_backup_manager()
        backups = manager.list_backups()

        if not backups:
            st.info("💡 暂无备份。点击「创建备份」生成第一个备份")
            return

        st.caption(f"共 {len(backups)} 个备份")

        for idx, backup in enumerate(backups):
            with st.expander(
                f"📄 {backup['filename']} — {backup['size_mb']} MB ({backup['created_at'][:10]})",
                expanded=(idx == 0)
            ):
                col_dl, col_del, _ = st.columns([1, 1, 2])

                with col_dl:
                    backup_file_path = Path(backup["path"])
                    if backup_file_path.exists():
                        with open(backup_file_path, "rb") as f:
                            zip_bytes = f.read()
                        st.download_button(
                            label="⬇️ 下载",
                            data=zip_bytes,
                            file_name=backup["filename"],
                            mime="application/zip",
                            key=f"dl_backup_{idx}",
                            use_container_width=True,
                        )

                with col_del:
                    if st.button("🗑️ 删除", key=f"del_backup_{idx}", use_container_width=True):
                        if manager.delete_backup(backup["path"]):
                            st.success("✅ 已删除")
                            st.rerun()
                        else:
                            st.error("❌ 删除失败")

                st.caption(f"完整路径: `{backup['path']}`")

    except ImportError:
        st.warning("⚠️ 备份模块未就绪")
    except Exception as e:
        logger.error("[frontend] Backup list error: %s", e)
        st.error(f"⚠️ 加载备份列表失败: {str(e)}")


def _render_export_data_tab():
    """Render the export data tab."""
    st.markdown("#### 📥 导出数据")

    st.markdown("**选择导出格式：**")

    format_col1, format_col2, format_col3 = st.columns(3)

    with format_col1:
        if st.button("📄 导出为 JSON", use_container_width=True, help="结构化JSON格式，适合程序处理"):
            with st.spinner("正在导出..."):
                try:
                    from opc_manager.data_backup import get_backup_manager
                    manager = get_backup_manager()
                    json_data = manager.export_data(format_type="json")
                    st.download_button(
                        label="⬇️ 下载 JSON 文件",
                        data=json_data,
                        file_name=f"opc_agents_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        key="dl_export_json",
                        use_container_width=True,
                    )
                    st.success("✅ JSON导出完成")
                except Exception as e:
                    logger.error("[frontend] Export JSON error: %s", e)
                    st.error(f"❌ 导出失败: {str(e)}")

    with format_col2:
        if st.button("📊 导出为 CSV", use_container_width=True, help="表格格式，适合Excel打开"):
            with st.spinner("正在导出..."):
                try:
                    from opc_manager.data_backup import get_backup_manager
                    manager = get_backup_manager()
                    csv_data = manager.export_data(format_type="csv")
                    st.download_button(
                        label="⬇️ 下载 CSV 文件",
                        data=csv_data,
                        file_name=f"opc_agents_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        key="dl_export_csv",
                        use_container_width=True,
                    )
                    st.success("✅ CSV导出完成")
                except Exception as e:
                    logger.error("[frontend] Export CSV error: %s", e)
                    st.error(f"❌ 导出失败: {str(e)}")

    with format_col3:
        if st.button("📦 导出为 ZIP", use_container_width=True, help="完整备份包（含清单文件）"):
            with st.spinner("正在导出..."):
                try:
                    from opc_manager.data_backup import get_backup_manager
                    manager = get_backup_manager()
                    zip_data = manager.export_data(format_type="zip")
                    st.download_button(
                        label="⬇️ 下载 ZIP 文件",
                        data=zip_data,
                        file_name=f"opc_agents_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                        mime="application/zip",
                        key="dl_export_zip",
                        use_container_width=True,
                    )
                    st.success("✅ ZIP导出完成")
                except Exception as e:
                    logger.error("[frontend] Export ZIP error: %s", e)
                    st.error(f"❌ 导出失败: {str(e)}")

    st.divider()
    st.caption("💡 提示：JSON格式适合数据迁移，CSV适合表格分析，ZIP是完整备份")


def _render_restore_data_tab():
    """Render the restore data tab."""
    st.markdown("#### 🔄 从备份恢复")

    st.warning("⚠️ **注意：** 恢复操作将覆盖当前所有数据，请确保已做好当前数据的备份！")

    uploaded_file = st.file_uploader(
        "选择备份文件 (ZIP格式)",
        type=["zip"],
        help="选择之前下载的 .zip 备份文件",
    )

    if uploaded_file:
        st.info(f"📄 已选择文件: {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")

        # Save uploaded file to temp location (sanitize filename)
        safe_name = re.sub(r'[^\w\-.]', '_', uploaded_file.name)[:100]
        temp_dir = Path(_WORKSPACE_DIR) / "data" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / f"restore_{safe_name}"

        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        confirm_restore = st.checkbox(
            "✅ 我确认要从此备份恢复数据（这将覆盖当前数据）",
            key="confirm_restore_checkbox",
        )

        col_restore, _ = st.columns([1, 2])
        with col_restore:
            if st.button(
                "🔄 开始恢复",
                type="primary",
                use_container_width=True,
                disabled=not confirm_restore,
                help="必须先勾选确认框才能执行恢复操作"
            ):
                with st.spinner("正在从备份恢复数据，请勿关闭页面..."):
                    try:
                        from opc_manager.data_backup import get_backup_manager
                        manager = get_backup_manager()
                        result = manager.restore_backup(str(temp_path), confirm=True)

                        if result["success"]:
                            st.success(f"✅ {result.get('message', '恢复成功')}")
                            st.json({
                                "恢复文件数": result.get("restored_files", 0),
                            })
                            st.balloons()
                            st.warning("⚠️ 建议刷新页面以确保所有数据正确加载")
                        else:
                            st.error(f"❌ 恢复失败: {result.get('error', '未知错误')}")

                        # Cleanup temp file
                        if temp_path.exists():
                            temp_path.unlink()

                    except Exception as e:
                        logger.error("[frontend] Restore error: %s", e)
                        st.error(f"❌ 恢复过程出错: {str(e)}")
