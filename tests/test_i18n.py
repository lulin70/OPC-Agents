"""Tests for i18n module — v0.2.0 Sprint 4"""

import pytest
from opc_manager.i18n import I18nManager, I18N_STRINGS, get_i18n, t


class TestI18nManagerInit:
    """Test I18nManager initialization and defaults."""

    def test_default_locale_is_zh_cn(self):
        manager = I18nManager()
        assert manager.locale == "zh_CN"

    def test_supported_locales_contains_all_three(self):
        assert "zh_CN" in I18nManager.SUPPORTED_LOCALES
        assert "en_US" in I18nManager.SUPPORTED_LOCALES
        assert "ja_JP" in I18nManager.SUPPORTED_LOCALES

    def test_default_locale_constant(self):
        assert I18nManager.DEFAULT_LOCALE == "zh_CN"


class TestLocaleSwitching:
    """Test locale switching functionality."""

    def test_switch_to_english(self):
        manager = I18nManager()
        manager.locale = "en_US"
        assert manager.locale == "en_US"

    def test_switch_to_chinese(self):
        manager = I18nManager()
        manager.locale = "en_US"
        manager.locale = "zh_CN"
        assert manager.locale == "zh_CN"

    def test_switch_to_japanese(self):
        manager = I18nManager()
        manager.locale = "ja_JP"
        assert manager.locale == "ja_JP"

    def test_unsupported_locale_falls_back(self):
        manager = I18nManager()
        manager.locale = "ko_KR"
        assert manager.locale == "zh_CN"

    def test_empty_locale_falls_back(self):
        manager = I18nManager()
        manager.locale = ""
        assert manager.locale == "zh_CN"


class TestTranslationChinese:
    """Test Chinese translations."""

    def test_nav_chat_chinese(self):
        manager = I18nManager()
        assert manager.t("nav_chat") == "💬 对话"

    def test_settings_llm_chinese(self):
        manager = I18nManager()
        assert manager.t("settings_llm") == "🧠 LLM 配置"

    def test_common_save_chinese(self):
        manager = I18nManager()
        assert manager.t("common_save") == "保存"

    def test_onboarding_welcome_title_chinese(self):
        manager = I18nManager()
        assert manager.t("onboarding_welcome_title") == "👋 欢迎使用 OPC-Agents"


class TestTranslationEnglish:
    """Test English translations."""

    def test_nav_chat_english(self):
        manager = I18nManager()
        manager.locale = "en_US"
        assert manager.t("nav_chat") == "💬 Chat"

    def test_settings_llm_english(self):
        manager = I18nManager()
        manager.locale = "en_US"
        assert manager.t("settings_llm") == "🧠 LLM Config"

    def test_common_save_english(self):
        manager = I18nManager()
        manager.locale = "en_US"
        assert manager.t("common_save") == "Save"

    def test_error_network_english(self):
        manager = I18nManager()
        manager.locale = "en_US"
        assert "Network connection failed" in manager.t("error_network")


class TestMissingKeys:
    """Test behavior with missing translation keys."""

    def test_missing_key_returns_key_itself(self):
        manager = I18nManager()
        result = manager.t("nonexistent_key")
        assert result == "nonexistent_key"

    def test_empty_key_returns_empty(self):
        manager = I18nManager()
        result = manager.t("")
        assert result == ""


class TestGetAvailableLocales:
    """Test get_available_locales method."""

    def test_returns_three_locales(self):
        manager = I18nManager()
        locales = manager.get_available_locales()
        assert len(locales) == 3

    def test_zh_cn_locale_info(self):
        manager = I18nManager()
        locales = manager.get_available_locales()
        zh = next((l for l in locales if l["code"] == "zh_CN"), None)
        assert zh is not None
        assert "中文" in zh["name"]

    def test_en_us_locale_info(self):
        manager = I18nManager()
        locales = manager.get_available_locales()
        en = next((l for l in locales if l["code"] == "en_US"), None)
        assert en is not None
        assert "English" in en["name"]

    def test_ja_jp_locale_info(self):
        manager = I18nManager()
        locales = manager.get_available_locales()
        ja = next((l for l in locales if l["code"] == "ja_JP"), None)
        assert ja is not None
        assert "日本語" in ja["name"]


class TestSingleton:
    """Test singleton pattern."""

    def test_get_i18n_returns_instance(self):
        instance = get_i18n()
        assert isinstance(instance, I18nManager)

    def test_get_i18n_same_instance(self):
        i1 = get_i18n()
        i2 = get_i18n()
        assert i1 is i2


class TestShorthandFunction:
    """Test shorthand t() function."""

    def test_t_function_works(self):
        result = t("common_save")
        assert result == "保存"

    def test_t_function_with_locale_change(self):
        i18n = get_i18n()
        i18n.locale = "en_US"
        result = t("common_save")
        assert result == "Save"
        i18n.locale = "zh_CN"


class TestI18NStringsCompleteness:
    """Test that all locales have the same keys."""

    def test_all_locales_have_same_keys(self):
        zh_keys = set(I18N_STRINGS["zh_CN"].keys())
        en_keys = set(I18N_STRINGS["en_US"].keys())
        ja_keys = set(I18N_STRINGS["ja_JP"].keys())
        assert zh_keys == en_keys == ja_keys

    def test_zh_cn_has_minimum_keys(self):
        required_keys = [
            "nav_chat",
            "nav_settings",
            "settings_llm",
            "common_save",
            "error_network",
            "onboarding_welcome_title",
        ]
        for key in required_keys:
            assert key in I18N_STRINGS["zh_CN"]


class TestTranslationJapanese:
    """Test Japanese translations."""

    def test_nav_chat_japanese(self):
        manager = I18nManager()
        manager.locale = "ja_JP"
        assert manager.t("nav_chat") == "💬 チャット"

    def test_settings_llm_japanese(self):
        manager = I18nManager()
        manager.locale = "ja_JP"
        assert manager.t("settings_llm") == "🧠 LLM設定"

    def test_common_save_japanese(self):
        manager = I18nManager()
        manager.locale = "ja_JP"
        assert manager.t("common_save") == "保存"

    def test_error_network_japanese(self):
        manager = I18nManager()
        manager.locale = "ja_JP"
        assert "ネットワーク" in manager.t("error_network")

    def test_onboarding_welcome_title_japanese(self):
        manager = I18nManager()
        manager.locale = "ja_JP"
        assert "ようこそ" in manager.t("onboarding_welcome_title")


class TestFallbackBehavior:
    """Test fallback to zh_CN when ja_JP missing a key (future-proofing)."""

    def test_fallback_for_missing_key_returns_key_itself(self):
        manager = I18nManager()
        manager.locale = "ja_JP"
        result = manager.t("totally_nonexistent_key")
        assert result == "totally_nonexistent_key"
