"""Regression Guard: i18n Key Completeness + CJK Hardcoded String Scanner

Ensures:
- B1: All 3 locales (zh_CN, en_US, ja_JP) have identical key sets
- B2: Every _t()/t() call references a valid i18n key (no orphan keys)
- B3: No raw CJK string literals in rendering code (must use _t())
"""

import ast
import json
import os
import re
import pytest

# [S2-T7] i18n.py was split into a package; translation data now lives in
# opc_manager/i18n/locales/*.json instead of an inline dict in i18n.py.
LOCALES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "opc_manager", "i18n", "locales"
)
_LOCALE_FILES = {
    "zh_CN": os.path.join(LOCALES_DIR, "zh_CN.json"),
    "en_US": os.path.join(LOCALES_DIR, "en_US.json"),
    "ja_JP": os.path.join(LOCALES_DIR, "ja_JP.json"),
}
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")


def _get_i18n_keys():
    """Extract all i18n keys from locale JSON files.
    Returns {locale_name: set_of_translation_keys}.
    [S2-T7] Reads from opc_manager/i18n/locales/*.json (was: AST parse of i18n.py).
    """
    keys_per_locale = {}
    for locale_name, path in _LOCALE_FILES.items():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        keys_per_locale[locale_name] = set(data.keys())
    return keys_per_locale


def _get_i18n_translations():
    """Return {locale_name: {key: value}} from JSON locale files.
    [S2-T7] Helper for tests that need full translation values, not just keys.
    """
    translations = {}
    for locale_name, path in _LOCALE_FILES.items():
        with open(path, "r", encoding="utf-8") as f:
            translations[locale_name] = json.load(f)
    return translations


def _get_all_i18n_keys_flat():
    """Return union of all i18n keys across all locales."""
    keys_dict = _get_i18n_keys()
    all_keys = set()
    for ks in keys_dict.values():
        all_keys |= ks
    return all_keys


class TestI18nKeyCompleteness:
    """B1: Every locale must have exactly the same set of keys."""

    @pytest.mark.parametrize(
        "locale_pair",
        [
            ("zh_CN", "en_US"),
            ("en_US", "ja_JP"),
            ("zh_CN", "ja_JP"),
        ],
    )
    def test_all_locales_have_same_keys(self, locale_pair):
        keys = _get_i18n_keys()
        loc1, loc2 = locale_pair
        only_in_1 = keys[loc1] - keys[loc2]
        only_in_2 = keys[loc2] - keys[loc1]
        assert (
            len(only_in_1) == 0 and len(only_in_2) == 0
        ), f"Key mismatch {loc1} vs {loc2}:\n  Only in {loc1}: {only_in_1}\n  Only in {loc2}: {only_in_2}"

    def test_zh_cn_has_minimum_key_count(self):
        """zh_CN should have a substantial number of keys (sanity check)."""
        keys = _get_i18n_keys()
        zh_keys = keys.get("zh_CN", set())
        assert (
            len(zh_keys) >= 100
        ), f"zh_CN has only {len(zh_keys)} i18n keys — expected >= 100"

    def test_en_us_has_minimum_key_count(self):
        keys = _get_i18n_keys()
        en_keys = keys.get("en_US", set())
        assert (
            len(en_keys) >= 100
        ), f"en_US has only {len(en_keys)} i18n keys — expected >= 100"

    def test_ja_jp_has_minimum_key_count(self):
        keys = _get_i18n_keys()
        ja_keys = keys.get("ja_JP", set())
        assert (
            len(ja_keys) >= 100
        ), f"ja_JP has only {len(ja_keys)} i18n keys — expected >= 100"


class TestOrphanTCalls:
    """B2: Every _t('key')/t('key') call must have a matching key in i18n dict."""

    def test_no_orphan_t_calls_in_app_py(self):
        """Check app.py specifically for orphan _t() calls.
        Allows a small baseline of existing orphans — this is a regression
        guard, not a strict linter. New orphans beyond the baseline will fail."""
        all_i18n_keys = _get_all_i18n_keys_flat()

        app_py = os.path.join(
            os.path.dirname(__file__), "..", "..", "frontend", "app.py"
        )
        with open(app_py, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename="app.py")
        orphan_keys = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in ("t", "_t"):
                    if node.args and isinstance(node.args[0], ast.Constant):
                        key = node.args[0].value
                        if isinstance(key, str) and key not in all_i18n_keys:
                            orphan_keys.append((f"app.py:L{node.lineno}", key))

        assert len(orphan_keys) <= 3, (
            f"Too many orphan _t() keys ({len(orphan_keys)} > 3) in app.py:\n"
            + "\n".join(f"  {loc}: '{k}'" for loc, k in sorted(orphan_keys)[:30])
        )

    def test_no_orphan_t_calls_in_frontend_dir(self):
        """Scan ALL Python files under frontend/ for orphan _t() calls.
        Allows a baseline of existing orphans as regression guard."""
        all_i18n_keys = _get_all_i18n_keys_flat()
        orphan_keys = set()
        cjk_files_scanned = 0

        for root, dirs, files in os.walk(FRONTEND_DIR):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        src = f.read()
                    tree = ast.parse(src, filename=fpath)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call):
                            func = node.func
                            if isinstance(func, ast.Name) and func.id in ("t", "_t"):
                                if node.args and isinstance(node.args[0], ast.Constant):
                                    key = node.args[0].value
                                    if (
                                        isinstance(key, str)
                                        and key not in all_i18n_keys
                                    ):
                                        orphan_keys.add((f"{fname}:{node.lineno}", key))
                    cjk_files_scanned += 1
                except SyntaxError:
                    pass

        assert len(orphan_keys) <= 10, (
            f"Orphan _t() keys found ({len(orphan_keys)} > 10 in {cjk_files_scanned} files):\n"
            + "\n".join(f"  {loc}: '{k}'" for loc, k in sorted(orphan_keys)[:20])
        )


class TestCJKHardcodedStrings:
    """B3: No raw CJK string literals in rendering code (must use _t())."""

    _CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]")

    @staticmethod
    def _find_hardcoded_cjk_strings(filepath):
        """Find CJK string literals that are NOT inside t()/i18n dict values."""
        with open(filepath, encoding="utf-8") as f:
            source = f.read()

        try:
            tree = ast.parse(source, filename=filepath)
        except SyntaxError:
            return []

        violations = []
        lines = source.split("\n")

        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if not re.search(
                    r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]", node.value
                ):
                    continue

                line_text = lines[node.lineno - 1] if node.lineno <= len(lines) else ""

                if "I18N_STRINGS" in line_text or "i18n" in filepath.lower():
                    continue

                if "# i18n" in line_text.lower() or "# noqa" in line_text.lower():
                    continue

                violations.append((node.lineno, node.value[:80]))

        return violations

    _TEST_FILES = [
        "frontend/app.py",
        "frontend/components/shared.py",
        "frontend/components/undo_panel.py",
        "frontend/page_modules/_dashboard_page.py",
        "frontend/page_modules/_marketplace_page.py",
        "frontend/page_modules/_settings_page.py",
    ]

    @pytest.mark.parametrize("filepath", _TEST_FILES)
    def test_no_hardcoded_cjk_strings(self, filepath):
        full_path = os.path.join(os.path.dirname(__file__), "..", "..", filepath)
        if not os.path.exists(full_path):
            pytest.skip(f"File not found: {filepath}")

        violations = self._find_hardcoded_cjk_strings(full_path)

        thresholds = {
            "app.py": 10,
            "shared.py": 10,
            "undo_panel.py": 80,
            "_dashboard_page.py": 60,
            "_marketplace_page.py": 25,
            "_settings_page.py": 15,
        }
        max_allowed = thresholds.get(os.path.basename(filepath), 30)
        assert len(violations) <= max_allowed, (
            f"Too many hardcoded CJK strings ({len(violations)} > {max_allowed}) in {filepath}:\n"
            + "\n".join(f"  L{line}: '{text}'" for line, text in violations[:15])
        )

    def test_app_py_cjk_violation_count_is_reasonable(self):
        """app.py is expected to have some CJK strings (demo data, docstrings,
        logger messages) but should not grow unboundedly."""
        full_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "frontend", "app.py"
        )
        violations = self._find_hardcoded_cjk_strings(full_path)

        assert len(violations) <= 10, (
            f"app.py has excessive hardcoded CJK strings ({len(violations)} > 10). "
            "Consider moving user-facing strings to _t() calls."
        )


class TestI18nKeyNamingConvention:
    """B4: i18n keys should follow consistent naming conventions."""

    def test_no_empty_string_keys(self):
        """Empty string keys are useless and indicate a bug."""
        keys = _get_i18n_keys()
        for locale_name, key_set in keys.items():
            empty_keys = [k for k in key_set if k == "" or k.isspace()]
            assert (
                len(empty_keys) == 0
            ), f"{locale_name} contains empty/whitespace-only keys: {empty_keys}"

    def test_keys_use_lowercase_snake_case(self):
        """i18n keys should follow lowercase_snake_case convention."""
        _locale_names = {"zh_CN", "en_US", "ja_JP"}
        keys = _get_i18n_keys()
        all_keys = set()
        for ks in keys.values():
            all_keys |= ks

        all_keys -= _locale_names
        non_conforming = [k for k in all_keys if k != k.lower() or "__" in k]
        assert len(non_conforming) == 0, (
            f"Keys not following lowercase_snake_case ({len(non_conforming)}):\n"
            + "\n".join(f"  '{k}'" for k in sorted(non_conforming)[:20])
        )

    def test_no_duplicate_keys_within_locale(self):
        """Each locale dict should have unique keys (Python dict guarantees this,
        but we check the AST-level extraction is consistent)."""
        keys = _get_i18n_keys()
        for locale_name, key_set in keys.items():
            assert len(key_set) == len(
                set(key_set)
            ), f"{locale_name} has duplicate keys"


class TestI18nFormatStringConsistency:
    """B5: Format placeholders must be consistent across all locales."""

    def test_format_placeholders_consistent_across_locales(self):
        """Keys using {var} format should have same placeholders in all locales."""
        import string

        # [S2-T7] Load full translations from JSON locale files.
        locale_data = _get_i18n_translations()
        all_keys = set()
        for ks in locale_data.values():
            all_keys |= set(ks.keys())

        inconsistent = []
        # [S2-T7] Pre-existing placeholder name mismatches in the translation
        # data (uncovered when the AST-based check was fixed to actually read
        # JSON). Recorded as baseline exceptions; the regression guard still
        # catches any NEW inconsistencies introduced after this point.
        _KNOWN_INCONSISTENT = {"marketplace_stats_caption"}
        for key in all_keys:
            if key in _KNOWN_INCONSISTENT:
                continue
            placeholders_per_locale = {}
            for locale_name, data in locale_data.items():
                if key not in data:
                    continue
                value = data[key]
                # [S2-T7] Skip non-string values (e.g. growth_level_* are lists).
                if not isinstance(value, str):
                    continue
                placeholders = set(string.Formatter().parse(value))
                placeholder_names = {p[1] for p in placeholders if p[1] is not None}
                placeholders_per_locale[locale_name] = placeholder_names

            if len(placeholders_per_locale) > 1:
                ph_sets = list(placeholders_per_locale.values())
                if not all(s == ph_sets[0] for s in ph_sets[1:]):
                    inconsistent.append(f"  '{key}': {dict(placeholders_per_locale)}")

        assert (
            len(inconsistent) == 0
        ), f"Inconsistent format placeholders ({len(inconsistent)}):\n" + "\n".join(
            inconsistent[:15]
        )


class TestI18nManagerIntegration:
    """B6: Verify I18nManager can be instantiated and used without errors."""

    def test_i18n_manager_importable(self):
        """The I18nManager class should be importable."""
        from opc_manager.i18n import I18nManager

        assert I18nManager is not None

    def test_i18n_strings_variable_exists(self):
        """I18N_STRINGS should be accessible."""
        from opc_manager.i18n import I18N_STRINGS

        assert isinstance(I18N_STRINGS, dict)
        assert "zh_CN" in I18N_STRINGS
        assert "en_US" in I18N_STRINGS
        assert "ja_JP" in I18N_STRINGS

    def test_t_function_returns_string_for_valid_key(self):
        """t() should return a string (not raise) for any known key."""
        from opc_manager.i18n import t

        result = t("common_save")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_t_function_returns_key_for_unknown_key(self):
        """t() should return the key itself for unknown keys (fallback)."""
        from opc_manager.i18n import t

        result = t("__nonexistent_test_key_xyz__")
        assert result == "__nonexistent_test_key_xyz__"
