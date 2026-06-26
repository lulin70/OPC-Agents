"""I18n manager logic [S2-T7].

Holds the :class:`I18nManager` class plus the module-level ``get_i18n`` /
``t`` helpers. Translation data is loaded from JSON via :mod:`loader`.
"""

import logging
from typing import Dict, Optional

from .loader import DEFAULT_LOCALE, SUPPORTED_LOCALES, load_translations

logger = logging.getLogger(__name__)

# Load translations once at module import (replaces the old inline dict).
I18N_STRINGS: Dict[str, Dict[str, str]] = load_translations()


class I18nManager:
    """Lightweight internationalization manager."""

    SUPPORTED_LOCALES = SUPPORTED_LOCALES
    DEFAULT_LOCALE = DEFAULT_LOCALE

    # Map short locale codes to full codes
    _LOCALE_ALIASES = {
        "zh": "zh_CN",
        "cn": "zh_CN",
        "chinese": "zh_CN",
        "en": "en_US",
        "us": "en_US",
        "english": "en_US",
        "ja": "ja_JP",
        "jp": "ja_JP",
        "japanese": "ja_JP",
    }

    def __init__(self):
        self._locale = self.DEFAULT_LOCALE

    @property
    def locale(self) -> str:
        return self._locale

    @locale.setter
    def locale(self, value: str):
        resolved = self._LOCALE_ALIASES.get(value, value)
        if resolved in self.SUPPORTED_LOCALES:
            self._locale = resolved
        else:
            logger.warning(
                "Unsupported locale: %s, falling back to %s",
                value,
                self.DEFAULT_LOCALE,
            )
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
            {"code": "zh_CN", "name": "中文"},
            {"code": "en_US", "name": "English"},
            {"code": "ja_JP", "name": "日本語"},
        ]


_i18n_instance: Optional[I18nManager] = None


def get_i18n() -> I18nManager:
    """Return the singleton :class:`I18nManager` instance."""
    global _i18n_instance
    if _i18n_instance is None:
        _i18n_instance = I18nManager()
    return _i18n_instance


def t(key: str, **kwargs) -> str:
    """Shorthand translation helper using the singleton manager."""
    return get_i18n().t(key, **kwargs)
