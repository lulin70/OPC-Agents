"""
Internationalization (i18n) Manager — v0.2.0

Lightweight, self-built i18n system for OPC-Agents.
Supports Chinese (zh_CN) and English (en_US), with Japanese extension point.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

I18N_STRINGS: Dict[str, Dict[str, str]] = {
    "zh_CN": {
        "nav_chat": "💬 对话",
        "nav_deliverables": "📁 成果物",
        "nav_growth": "📊 成长",
        "nav_marketplace": "🏪 技能市场",
        "nav_settings": "⚙️ 设置",
        "settings_llm": "🧠 LLM 配置",
        "settings_smtp": "📧 SMTP 配置",
        "settings_api_keys": "🔑 API 密钥",
        "settings_security": "🔒 安全设置",
        "settings_profile": "👤 个人信息",
        "settings_backup": "💾 数据备份",
        "llm_provider": "LLM 提供商",
        "llm_api_key": "API 密钥",
        "llm_base_url": "Base URL",
        "llm_model": "模型名称",
        "llm_test_connection": "测试连接",
        "llm_save": "保存配置",
        "smtp_host": "SMTP 服务器",
        "smtp_port": "端口",
        "smtp_username": "用户名",
        "smtp_password": "密码",
        "smtp_test": "测试连接",
        "profile_name": "用户名",
        "profile_company": "公司名称",
        "profile_timezone": "时区",
        "profile_language": "语言",
        "onboarding_welcome_title": "👋 欢迎使用 OPC-Agents",
        "onboarding_welcome_desc": "一人公司智能任务执行系统",
        "onboarding_llm_title": "🧠 配置 AI 大脑",
        "onboarding_sample_title": "🎯 试试第一个任务",
        "onboarding_complete_title": "🎉 准备就绪！",
        "onboarding_next": "下一步 →",
        "onboarding_skip": "跳过引导",
        "onboarding_start": "开始使用",
        "dashboard_income_trend": "📈 收入趋势图",
        "dashboard_client_health": "👥 客户健康度",
        "dashboard_task_completion": "✅ 任务完成率",
        "dashboard_monthly_finance": "💰 月度财务汇总",
        "dashboard_activity_timeline": "📅 近期活动时间线",
        "dashboard_skill_stats": "⏱️ 技能使用统计",
        "error_network": "网络连接失败，请检查网络后重试",
        "error_permission": "权限不足，无法完成此操作",
        "error_config": "配置信息不完整或有误",
        "error_unknown": "操作出现意外错误",
        "common_save": "保存",
        "common_cancel": "取消",
        "common_confirm": "确认",
        "common_delete": "删除",
        "common_search": "搜索...",
        "common_loading": "加载中...",
        "common_no_data": "暂无数据",
        "common_success": "操作成功",
        "common_failed": "操作失败",
    },
    "en_US": {
        "nav_chat": "💬 Chat",
        "nav_deliverables": "📁 Deliverables",
        "nav_growth": "📊 Growth",
        "nav_marketplace": "🏪 Skills",
        "nav_settings": "⚙️ Settings",
        "settings_llm": "🧠 LLM Config",
        "settings_smtp": "📧 SMTP Config",
        "settings_api_keys": "🔑 API Keys",
        "settings_security": "🔒 Security",
        "settings_profile": "👤 Profile",
        "settings_backup": "💾 Data Backup",
        "llm_provider": "LLM Provider",
        "llm_api_key": "API Key",
        "llm_base_url": "Base URL",
        "llm_model": "Model Name",
        "llm_test_connection": "Test Connection",
        "llm_save": "Save Config",
        "smtp_host": "SMTP Host",
        "smtp_port": "Port",
        "smtp_username": "Username",
        "smtp_password": "Password",
        "smtp_test": "Test Connection",
        "profile_name": "Name",
        "profile_company": "Company",
        "profile_timezone": "Timezone",
        "profile_language": "Language",
        "onboarding_welcome_title": "👋 Welcome to OPC-Agents",
        "onboarding_welcome_desc": "AI Task Executor for One-Person Companies",
        "onboarding_llm_title": "🧠 Configure AI Brain",
        "onboarding_sample_title": "🎯 Try Your First Task",
        "onboarding_complete_title": "🎉 All Set!",
        "onboarding_next": "Next →",
        "onboarding_skip": "Skip Guide",
        "onboarding_start": "Get Started",
        "dashboard_income_trend": "📈 Income Trend",
        "dashboard_client_health": "👥 Client Health",
        "dashboard_task_completion": "✅ Task Completion",
        "dashboard_monthly_finance": "💰 Monthly Finance",
        "dashboard_activity_timeline": "📅 Recent Activity",
        "dashboard_skill_stats": "⏱️ Skill Usage Stats",
        "error_network": "Network connection failed, please check and retry",
        "error_permission": "Permission denied for this operation",
        "error_config": "Configuration incomplete or invalid",
        "error_unknown": "An unexpected error occurred",
        "common_save": "Save",
        "common_cancel": "Cancel",
        "common_confirm": "Confirm",
        "common_delete": "Delete",
        "common_search": "Search...",
        "common_loading": "Loading...",
        "common_no_data": "No data available",
        "common_success": "Success",
        "common_failed": "Failed",
    },
}


class I18nManager:
    """Lightweight internationalization manager."""

    SUPPORTED_LOCALES = ["zh_CN", "en_US"]
    DEFAULT_LOCALE = "zh_CN"

    def __init__(self):
        self._locale = self.DEFAULT_LOCALE

    @property
    def locale(self) -> str:
        return self._locale

    @locale.setter
    def locale(self, value: str):
        if value in self.SUPPORTED_LOCALES:
            self._locale = value
        else:
            logger.warning("Unsupported locale: %s, falling back to %s", value, self.DEFAULT_LOCALE)
            self._locale = self.DEFAULT_LOCALE

    def t(self, key: str, **kwargs) -> str:
        strings = I18N_STRINGS.get(self._locale, I18N_STRINGS[self.DEFAULT_LOCALE])
        text = strings.get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError:
                pass
        return text

    def get_available_locales(self) -> list:
        return [
            {"code": "zh_CN", "name": "中文 🇨🇳"},
            {"code": "en_US", "name": "English 🇺🇸"},
        ]


_i18n_instance: Optional[I18nManager] = None


def get_i18n() -> I18nManager:
    global _i18n_instance
    if _i18n_instance is None:
        _i18n_instance = I18nManager()
    return _i18n_instance


def t(key: str, **kwargs) -> str:
    return get_i18n().t(key, **kwargs)
