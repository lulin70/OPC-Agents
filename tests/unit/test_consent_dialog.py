"""Unit tests for consent_dialog component.

Implements UI_DESIGN_v0.5.0.md §6 (Prototype 3: Data Collection Consent Dialog) tests.

Test strategy:
- Mock Streamlit (st) module to test render_consent_dialog
- Use real filesystem (tmp_path fixture) for save_consent / load_consent / has_user_consented
- Coverage targets: Happy ≥50% / Error ≥15% / Boundary ≥10%

Run command:
    pytest tests/unit/test_consent_dialog.py -v --tb=short
"""

import json
import os
import stat
from unittest.mock import MagicMock, patch

import pytest

from frontend.components.consent_dialog import (
    CONSENT_VERSION,
    DEFAULT_CONSENT,
    PRIVACY_POLICY_URL,
    has_user_consented,
    load_consent,
    render_consent_dialog,
    save_consent,
)


@pytest.fixture
def mock_streamlit():
    """Patch the streamlit module imported by consent_dialog.

    Yields a MagicMock that replaces ``frontend.components.consent_dialog.st``.
    """
    with patch("frontend.components.consent_dialog.st") as mock_st:
        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        yield mock_st


# ============================================================
# DEFAULT_CONSENT — Tests
# ============================================================


class TestDefaultConsent:
    """Tests for DEFAULT_CONSENT module constant."""

    def test_default_consent_values(self):
        """DEFAULT_CONSENT has correct default values per ADR-004 §3.4.

        - First 3 options default True (local storage only)
        - feedback_content defaults False (requires explicit consent)
        - consented_at is None until user makes a choice
        - consent_version matches CONSENT_VERSION
        """
        assert DEFAULT_CONSENT["usage_stats"] is True
        assert DEFAULT_CONSENT["perf_metrics"] is True
        assert DEFAULT_CONSENT["satisfaction"] is True
        assert DEFAULT_CONSENT["feedback_content"] is False
        assert DEFAULT_CONSENT["consented_at"] is None
        assert DEFAULT_CONSENT["consent_version"] == CONSENT_VERSION

    def test_default_consent_has_six_keys(self):
        """DEFAULT_CONSENT has exactly 6 keys."""
        expected_keys = {
            "usage_stats",
            "perf_metrics",
            "satisfaction",
            "feedback_content",
            "consented_at",
            "consent_version",
        }
        assert set(DEFAULT_CONSENT.keys()) == expected_keys

    def test_consent_version_is_string(self):
        """CONSENT_VERSION is a string starting with major.minor."""
        assert isinstance(CONSENT_VERSION, str)
        assert "." in CONSENT_VERSION

    def test_privacy_policy_url_is_https(self):
        """PRIVACY_POLICY_URL uses HTTPS (security best practice)."""
        assert PRIVACY_POLICY_URL.startswith("https://")


# ============================================================
# save_consent — Happy path tests
# ============================================================


class TestSaveConsent:
    """Tests for save_consent function."""

    def test_save_consent_creates_file(self, tmp_path):
        """save_consent creates a JSON file at the specified path."""
        consent_path = tmp_path / "consent.json"
        consent_data = {
            "usage_stats": True,
            "perf_metrics": False,
            "satisfaction": True,
            "feedback_content": False,
            "consented_at": "2026-07-19T10:00:00+00:00",
            "consent_version": "1.0",
        }

        save_consent(consent_path, consent_data)

        assert consent_path.exists()
        loaded = json.loads(consent_path.read_text(encoding="utf-8"))
        assert loaded == consent_data

    def test_save_consent_creates_file_with_0600_permissions(self, tmp_path):
        """save_consent sets 0o600 permissions on the consent file.

        On POSIX systems, this protects user privacy by restricting
        read/write to the owner only (per HARD_CONSTRAINTS S4).
        """
        consent_path = tmp_path / "subdir" / "consent.json"
        consent_data = DEFAULT_CONSENT.copy()

        save_consent(consent_path, consent_data)

        assert consent_path.exists()
        file_mode = stat.S_IMODE(os.stat(consent_path).st_mode)
        assert file_mode == 0o600, f"Expected 0o600, got {oct(file_mode)}"

    def test_save_consent_creates_parent_directory(self, tmp_path):
        """save_consent creates parent directories if missing."""
        # Use a deeply nested path that doesn't exist yet
        deep_path = tmp_path / "a" / "b" / "c" / "d" / "consent.json"
        assert not deep_path.parent.exists()

        save_consent(deep_path, DEFAULT_CONSENT.copy())

        assert deep_path.exists()
        assert deep_path.parent.exists()

    def test_save_consent_overwrites_existing_file(self, tmp_path):
        """save_consent overwrites an existing file with new data."""
        consent_path = tmp_path / "consent.json"
        old_data = DEFAULT_CONSENT.copy()
        old_data["usage_stats"] = True
        save_consent(consent_path, old_data)

        new_data = DEFAULT_CONSENT.copy()
        new_data["usage_stats"] = False
        new_data["consented_at"] = "2026-07-19T11:00:00+00:00"
        save_consent(consent_path, new_data)

        loaded = json.loads(consent_path.read_text(encoding="utf-8"))
        assert loaded["usage_stats"] is False
        assert loaded["consented_at"] == "2026-07-19T11:00:00+00:00"

    def test_save_consent_writes_utf8(self, tmp_path):
        """save_consent writes UTF-8 encoded JSON (preserves Chinese text)."""
        consent_path = tmp_path / "consent.json"
        consent_data = {
            "usage_stats": True,
            "perf_metrics": True,
            "satisfaction": True,
            "feedback_content": False,
            "consented_at": "2026-07-19T10:00:00+00:00",
            "consent_version": "1.0",
            "note": "用户同意数据采集",
        }

        save_consent(consent_path, consent_data)

        raw_bytes = consent_path.read_bytes()
        # UTF-8 encoded Chinese chars should be readable
        assert "用户同意数据采集".encode("utf-8") in raw_bytes


# ============================================================
# load_consent — Tests
# ============================================================


class TestLoadConsent:
    """Tests for load_consent function."""

    def test_load_consent_returns_none_when_not_exists(self, tmp_path):
        """load_consent returns None when the consent file does not exist."""
        consent_path = tmp_path / "nonexistent.json"
        assert not consent_path.exists()

        result = load_consent(consent_path)

        assert result is None

    def test_load_consent_returns_data_when_exists(self, tmp_path):
        """load_consent returns the parsed dict when the file exists."""
        consent_path = tmp_path / "consent.json"
        consent_data = {
            "usage_stats": True,
            "perf_metrics": False,
            "satisfaction": True,
            "feedback_content": True,
            "consented_at": "2026-07-19T10:00:00+00:00",
            "consent_version": "1.0",
        }
        save_consent(consent_path, consent_data)

        result = load_consent(consent_path)

        assert result is not None
        assert result == consent_data
        assert result["usage_stats"] is True
        assert result["feedback_content"] is True

    def test_load_consent_handles_corrupt_json(self, tmp_path):
        """load_consent returns None when JSON is malformed (error path)."""
        consent_path = tmp_path / "corrupt.json"
        consent_path.write_text("{ not valid json ]", encoding="utf-8")

        result = load_consent(consent_path)

        assert result is None

    def test_load_consent_preserves_chinese_text(self, tmp_path):
        """load_consent correctly reads UTF-8 Chinese text back."""
        consent_path = tmp_path / "consent.json"
        original_note = "用户同意数据采集"
        consent_data = {
            "usage_stats": True,
            "perf_metrics": True,
            "satisfaction": True,
            "feedback_content": False,
            "consented_at": "2026-07-19T10:00:00+00:00",
            "consent_version": "1.0",
            "note": original_note,
        }
        save_consent(consent_path, consent_data)

        result = load_consent(consent_path)

        assert result is not None
        assert result["note"] == original_note


# ============================================================
# has_user_consented — Tests
# ============================================================


class TestHasUserConsented:
    """Tests for has_user_consented function."""

    def test_has_user_consented_false_when_no_file(self, tmp_path):
        """has_user_consented returns False when no consent file exists."""
        consent_path = tmp_path / "consent.json"
        assert not consent_path.exists()

        assert has_user_consented(consent_path) is False

    def test_has_user_consented_true_when_file_exists(self, tmp_path):
        """has_user_consented returns True when consent file exists.

        This is true regardless of whether the user agreed or disagreed —
        both choices write the file (the file existence indicates the
        user has been asked and made a choice).
        """
        consent_path = tmp_path / "consent.json"
        save_consent(consent_path, DEFAULT_CONSENT.copy())

        assert has_user_consented(consent_path) is True

    def test_has_user_consented_true_even_if_disagreed(self, tmp_path):
        """has_user_consented returns True even when user disagreed.

        The disagreement also writes a consent file (with all flags False),
        marking that the user has been asked.
        """
        consent_path = tmp_path / "consent.json"
        disagree_data = {
            "usage_stats": False,
            "perf_metrics": False,
            "satisfaction": False,
            "feedback_content": False,
            "consented_at": "2026-07-19T10:00:00+00:00",
            "consent_version": "1.0",
        }
        save_consent(consent_path, disagree_data)

        assert has_user_consented(consent_path) is True


# ============================================================
# render_consent_dialog — Happy path tests
# ============================================================


class TestRenderConsentDialogHappy:
    """Happy-path tests for render_consent_dialog."""

    def test_render_consent_dialog_returns_none_initially(
        self, mock_streamlit, tmp_path
    ):
        """When no button is clicked, returns None (dialog still open)."""
        mock_streamlit.checkbox.side_effect = [True, True, True, False]
        # Both buttons return False (no choice made yet)
        mock_streamlit.button.side_effect = [False, False]

        consent_path = tmp_path / "consent.json"
        result = render_consent_dialog(consent_path)

        assert result is None
        # File should NOT be created (no choice made)
        assert not consent_path.exists()

    def test_render_consent_dialog_agree_preserves_choices(
        self, mock_streamlit, tmp_path
    ):
        """Clicking 'agree' saves user's checkbox choices."""
        # 4 checkboxes: usage=True, perf=False, sat=True, feedback=True
        mock_streamlit.checkbox.side_effect = [True, False, True, True]
        # Disagree button=False, Agree button=True
        mock_streamlit.button.side_effect = [False, True]

        consent_path = tmp_path / "consent.json"
        result = render_consent_dialog(consent_path)

        assert result is not None
        assert result["usage_stats"] is True
        assert result["perf_metrics"] is False
        assert result["satisfaction"] is True
        assert result["feedback_content"] is True
        assert result["consented_at"] is not None
        assert result["consent_version"] == CONSENT_VERSION
        # File should be created
        assert consent_path.exists()
        # File content should match
        loaded = load_consent(consent_path)
        assert loaded == result

    def test_render_consent_dialog_disagree_sets_all_false(
        self, mock_streamlit, tmp_path
    ):
        """Clicking 'disagree' sets all 4 flags to False regardless of
        checkbox state."""
        # Checkboxes have some True values, but disagree should override
        mock_streamlit.checkbox.side_effect = [True, True, True, True]
        # Disagree button=True, Agree button=False
        mock_streamlit.button.side_effect = [True, False]

        consent_path = tmp_path / "consent.json"
        result = render_consent_dialog(consent_path)

        assert result is not None
        assert result["usage_stats"] is False
        assert result["perf_metrics"] is False
        assert result["satisfaction"] is False
        assert result["feedback_content"] is False
        assert result["consented_at"] is not None
        assert result["consent_version"] == CONSENT_VERSION
        # File should be created
        assert consent_path.exists()


# ============================================================
# render_consent_dialog — Boundary tests
# ============================================================


class TestRenderConsentDialogBoundary:
    """Boundary tests for render_consent_dialog."""

    def test_render_consent_dialog_all_checkboxes_off_then_agree(
        self, mock_streamlit, tmp_path
    ):
        """User unchecks all boxes then agrees — all flags should be False."""
        mock_streamlit.checkbox.side_effect = [False, False, False, False]
        mock_streamlit.button.side_effect = [False, True]

        consent_path = tmp_path / "consent.json"
        result = render_consent_dialog(consent_path)

        assert result is not None
        assert result["usage_stats"] is False
        assert result["perf_metrics"] is False
        assert result["satisfaction"] is False
        assert result["feedback_content"] is False

    def test_render_consent_dialog_all_checkboxes_on_then_agree(
        self, mock_streamlit, tmp_path
    ):
        """User checks all boxes (including feedback_content) then agrees."""
        mock_streamlit.checkbox.side_effect = [True, True, True, True]
        mock_streamlit.button.side_effect = [False, True]

        consent_path = tmp_path / "consent.json"
        result = render_consent_dialog(consent_path)

        assert result is not None
        assert result["usage_stats"] is True
        assert result["perf_metrics"] is True
        assert result["satisfaction"] is True
        assert result["feedback_content"] is True

    def test_render_consent_dialog_creates_parent_dir_on_agree(
        self, mock_streamlit, tmp_path
    ):
        """Agreeing with a nested path creates parent directories."""
        mock_streamlit.checkbox.side_effect = [True, True, True, False]
        mock_streamlit.button.side_effect = [False, True]

        nested_path = tmp_path / "deep" / "nest" / "consent.json"
        assert not nested_path.parent.exists()

        render_consent_dialog(nested_path)

        assert nested_path.exists()
        assert nested_path.parent.exists()
