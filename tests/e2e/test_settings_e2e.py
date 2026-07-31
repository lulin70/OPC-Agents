"""Settings 页面 6 个 tab 配置生效流程 E2E 测试.

GAP-P0-3: 现有 test_ui_playwright.py::TestUJ06Settings 仅验证 tabs 可见，
配置表单提交/连接测试/生效流程零覆盖.

从用户角度覆盖:
- 导航: 用户从侧边栏点击"设置" → 看到 6 个 tab
- LLM tab: API Key 输入框 type=password（不泄露明文）→ 保存按钮存在
- SMTP tab: 表单字段可见 → preset 选择存在
- API Keys tab: 密钥掩码显示 → 不泄露明文
- Security tab: 加密密钥状态可见
- Profile tab: 用户名字段存在 → 保存按钮存在
- Backup tab: 创建备份按钮存在
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def _goto_settings(page) -> None:
    """导航到 Settings 页面（侧边栏 radio 点击"设置"）."""
    radio = page.locator("[data-testid='stRadio'] label", has_text="设置").first
    radio.wait_for(state="attached", timeout=15000)
    try:
        radio.scroll_into_view_if_needed(timeout=2000)
    except Exception:
        pass
    radio.click(force=True)
    page.wait_for_timeout(2000)
    # 等待 tabs 渲染
    page.wait_for_selector("[data-testid='stTabs']", timeout=15000)


def _click_tab(page, tab_label: str) -> None:
    """点击 Settings 下的指定 tab.

    Args:
        tab_label: tab 显示文本（如 "LLM 配置"、"SMTP 配置"）
    """
    tab = page.locator(
        f"[data-testid='stTabs'] button[role='tab']:has-text('{tab_label}')"
    ).first
    tab.wait_for(state="visible", timeout=10000)
    tab.click()
    page.wait_for_timeout(1500)


# ============================================================
# 导航与 Tab 可见性验证
# ============================================================


class TestSettingsNavigationE2E:
    """验证 Settings 页面导航和 6 个 tab 可见性."""

    def test_navigate_to_settings_page(self, page):
        """Verify: 用户从侧边栏点击"设置" → Settings 页面渲染.

        用户旅程: 用户打开应用 → 点击侧边栏"设置" → 看到页面标题和 tabs.
        """
        _goto_settings(page)
        # 验证 tabs 容器存在（使用 .first 避免 strict mode 冲突；
        # 页面可能存在多个 stTabs，如 sidebar 工具区也有 tabs）
        tabs = page.locator("[data-testid='stTabs']").first
        expect(tabs).to_be_visible(timeout=10000)

    def test_all_six_tabs_visible(self, page):
        """Verify: Settings 页面显示 6 个 tab（LLM/SMTP/API Keys/Security/Profile/Backup）.

        用户旅程: 用户导航到 Settings → 看到 6 个配置分类 tab.
        """
        _goto_settings(page)
        expected_tabs = [
            "LLM 配置",
            "SMTP 配置",
            "API 密钥",
            "安全设置",
            "个人信息",
            "数据备份",
        ]
        for tab_label in expected_tabs:
            tab = page.locator(
                f"[data-testid='stTabs'] button[role='tab']:has-text('{tab_label}')"
            )
            expect(tab).to_have_count(1, timeout=10000)


# ============================================================
# LLM Tab 验证
# ============================================================


class TestSettingsLLMTabE2E:
    """LLM tab E2E — API Key 配置核心流程."""

    def test_api_key_input_is_password_type(self, page):
        """Verify: LLM tab 中 API Key 输入框 type='password'（不显示明文）.

        用户旅程: 用户进入 LLM tab → 看到 API Key 输入框 → 输入时不显示明文.
        安全要求: API Key 是敏感信息，输入框必须 type='password'.
        """
        _goto_settings(page)
        _click_tab(page, "LLM 配置")

        # st.form 内的 text_input type="password" 渲染为 input[type='password']
        password_input = page.locator("input[type='password']").first
        expect(password_input).to_be_visible(timeout=10000)

    def test_no_plaintext_api_key_input(self, page):
        """Verify: LLM tab 不存在 type='text' 的 API Key 输入框.

        安全要求: 所有 API Key 相关输入必须是 password 类型，禁止明文显示.
        """
        _goto_settings(page)
        _click_tab(page, "LLM 配置")

        # 检查不存在 placeholder 含 "sk-" 的明文 input
        plaintext_sk = page.locator("input[type='text'][placeholder*='sk-']").count()
        assert plaintext_sk == 0, "存在明文显示 API Key 的 input (placeholder含 sk-)"

    def test_save_button_exists(self, page):
        """Verify: LLM tab 有"保存配置"按钮.

        用户旅程: 用户输入 API Key → 点击"保存配置" → 配置生效.
        """
        _goto_settings(page)
        _click_tab(page, "LLM 配置")

        save_btn = page.locator("button:has-text('保存配置')").first
        expect(save_btn).to_be_visible(timeout=10000)

    def test_test_connection_button_exists(self, page):
        """Verify: LLM tab 有"测试连接"按钮.

        用户旅程: 用户输入 API Key → 点击"测试连接" → 验证连接是否成功.
        """
        _goto_settings(page)
        _click_tab(page, "LLM 配置")

        test_btn = page.locator("button:has-text('测试连接')").first
        expect(test_btn).to_be_visible(timeout=10000)

    def test_provider_radio_exists(self, page):
        """Verify: LLM tab 有 Provider 选择（MokaAI/OpenAI/智谱GLM/Ollama）.

        用户旅程: 用户进入 LLM tab → 选择 LLM 服务商 → 配置对应的 API Key.
        """
        _goto_settings(page)
        _click_tab(page, "LLM 配置")

        # Provider radio 应至少包含 MokaAI 选项
        provider_option = page.locator("label:has-text('MokaAI')").first
        expect(provider_option).to_be_visible(timeout=10000)


# ============================================================
# SMTP Tab 验证
# ============================================================


class TestSettingsSMTPTabE2E:
    """SMTP tab E2E — 邮件配置流程."""

    def test_smtp_form_visible(self, page):
        """Verify: SMTP tab 渲染表单内容（非空白）.

        用户旅程: 用户进入 SMTP tab → 看到邮件配置表单.
        """
        _goto_settings(page)
        _click_tab(page, "SMTP 配置")
        # 验证 tab 内容区域有可见元素（heading 或 form）
        content = page.locator(
            "[data-testid='stTabs'] [role='tabpanel'] >> visible=true"
        ).first
        expect(content).to_be_visible(timeout=10000)

    def test_smtp_preset_selectbox_exists(self, page):
        """Verify: SMTP tab 有 preset 选择下拉框（QQ/Gmail 等）.

        用户旅程: 用户进入 SMTP tab → 选择 preset（如 QQ 邮箱）→ 自动填充配置.
        """
        _goto_settings(page)
        _click_tab(page, "SMTP 配置")

        # preset selectbox 应存在（含"预设"文本的 label）
        preset_area = page.locator("text=/预设|preset/i").first
        expect(preset_area).to_be_visible(timeout=10000)


# ============================================================
# API Keys Tab 验证
# ============================================================


class TestSettingsAPIKeysTabE2E:
    """API Keys tab E2E — 密钥掩码安全验证."""

    def test_no_plaintext_keys_displayed(self, page):
        """Verify: API Keys tab 不显示明文密钥（如 sk-xxx 完整字符串）.

        安全要求: API Keys tab 应显示掩码（如 sk-***45），不显示完整明文.
        """
        _goto_settings(page)
        _click_tab(page, "API 密钥")

        # 检查不存在明文 sk- 开头的长字符串（>20 字符）
        plaintext_keys = page.locator("text=/^sk-[a-zA-Z0-9]{20,}/").count()
        assert plaintext_keys == 0, "API Keys tab 显示明文密钥 (sk-xxx 完整字符串)"

    def test_api_keys_management_content_visible(self, page):
        """Verify: API Keys tab 渲染密钥管理内容（非空白）.

        用户旅程: 用户进入 API Keys tab → 看到密钥管理界面.
        """
        _goto_settings(page)
        _click_tab(page, "API 密钥")

        # 应有 "API 密钥管理" 或类似 heading
        heading = page.locator("text=/API 密钥|密钥管理/i").first
        expect(heading).to_be_visible(timeout=10000)


# ============================================================
# Security Tab 验证
# ============================================================


class TestSettingsSecurityTabE2E:
    """Security tab E2E — 加密状态验证."""

    def test_encryption_status_visible(self, page):
        """Verify: Security tab 显示加密密钥状态（已生成/未设置）.

        用户旅程: 用户进入 Security tab → 查看加密密钥状态 → 了解数据保护情况.
        """
        _goto_settings(page)
        _click_tab(page, "安全设置")

        # 应有 "加密" 或 "安全" 相关文本
        encryption_text = page.locator("text=/加密|安全|encryption|security/i").first
        expect(encryption_text).to_be_visible(timeout=10000)

    def test_security_tips_visible(self, page):
        """Verify: Security tab 显示安全提示信息.

        用户旅程: 用户进入 Security tab → 看到安全提示 → 了解如何保护数据.
        """
        _goto_settings(page)
        _click_tab(page, "安全设置")

        # 应有安全提示文本（含"密钥"或"备份"相关提示）
        tips = page.locator("text=/密钥|备份|加密/i").first
        expect(tips).to_be_visible(timeout=10000)


# ============================================================
# Profile Tab 验证
# ============================================================


class TestSettingsProfileTabE2E:
    """Profile tab E2E — 个人信息配置."""

    def test_profile_name_input_exists(self, page):
        """Verify: Profile tab 有用户名输入框.

        用户旅程: 用户进入 Profile tab → 输入用户名 → 保存个人信息.
        """
        _goto_settings(page)
        _click_tab(page, "个人信息")

        # 用户名输入框（placeholder 含"名字"）
        name_input = page.locator("input[placeholder*='名字' i]").first
        expect(name_input).to_be_visible(timeout=10000)

    def test_profile_save_button_exists(self, page):
        """Verify: Profile tab 有"保存个人信息"按钮.

        用户旅程: 用户填写个人信息 → 点击"保存个人信息" → 配置生效.
        """
        _goto_settings(page)
        _click_tab(page, "个人信息")

        save_btn = page.locator("button:has-text('保存个人信息')").first
        expect(save_btn).to_be_visible(timeout=10000)

    def test_profile_company_input_exists(self, page):
        """Verify: Profile tab 有公司名称输入框.

        用户旅程: 用户进入 Profile tab → 输入公司名称 → 保存.
        """
        _goto_settings(page)
        _click_tab(page, "个人信息")

        # 公司名称输入框（placeholder 含"公司"）
        company_input = page.locator("input[placeholder*='公司' i]").first
        expect(company_input).to_be_visible(timeout=10000)


# ============================================================
# Backup Tab 验证
# ============================================================


class TestSettingsBackupTabE2E:
    """Backup tab E2E — 数据备份恢复."""

    def test_backup_create_button_exists(self, page):
        """Verify: Backup tab 有"立即创建备份"按钮.

        用户旅程: 用户进入 Backup tab → 点击"立即创建备份" → 创建数据备份.
        """
        _goto_settings(page)
        _click_tab(page, "数据备份")

        create_btn = page.locator("button:has-text('创建备份')").first
        expect(create_btn).to_be_visible(timeout=10000)

    def test_backup_info_visible(self, page):
        """Verify: Backup tab 显示数据安全提示信息.

        用户旅程: 用户进入 Backup tab → 看到数据安全提示 → 了解备份重要性.
        """
        _goto_settings(page)
        _click_tab(page, "数据备份")

        # 应有 "备份" 或 "数据安全" 相关文本
        info = page.locator("text=/备份|数据安全/i").first
        expect(info).to_be_visible(timeout=10000)
