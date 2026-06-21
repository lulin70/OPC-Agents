"""JSON translation loader [S2-T7].

Loads translation data from ``locales/*.json`` files next to this module.
Extracted from the original monolithic ``i18n.py`` during S2-T7.
"""

import json
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

_LOCALES_DIR = Path(__file__).parent / "locales"

SUPPORTED_LOCALES = ["zh_CN", "en_US", "ja_JP"]
DEFAULT_LOCALE = "zh_CN"


def load_translations() -> Dict[str, Dict[str, str]]:
    """Load all locale JSON files from the ``locales/`` directory.

    Returns a dict mapping locale code -> dict of (key -> translation).
    Missing or malformed files yield an empty dict with a warning.
    """
    translations: Dict[str, Dict[str, str]] = {}
    for locale in SUPPORTED_LOCALES:
        path = _LOCALES_DIR / f"{locale}.json"
        try:
            with open(path, "r", encoding="utf-8") as f:
                translations[locale] = json.load(f)
        except FileNotFoundError:
            logger.warning("Locale file missing: %s", path)
            translations[locale] = {}
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON in %s: %s", path, exc)
            translations[locale] = {}
    return translations


def load_locale(locale: str) -> Dict[str, str]:
    """Load a single locale's translations from its JSON file."""
    path = _LOCALES_DIR / f"{locale}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
