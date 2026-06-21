"""i18n 国际化包 [S2-T7] - 从原 ``i18n.py`` 拆分为包结构.

Backward-compatible public API. Existing imports continue to work::

    from opc_manager.i18n import I18nManager, I18N_STRINGS, get_i18n, t

Translation data lives in ``locales/{zh_CN,en_US,ja_JP}.json`` and is
loaded by :mod:`loader`; management logic lives in :mod:`manager`.
"""

from .loader import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    load_locale,
    load_translations,
)
from .manager import I18N_STRINGS, I18nManager, get_i18n, t

__all__ = [
    "I18nManager",
    "I18N_STRINGS",
    "get_i18n",
    "t",
    "load_translations",
    "load_locale",
    "SUPPORTED_LOCALES",
    "DEFAULT_LOCALE",
]
