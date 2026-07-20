"""Unit tests for feedback_dialog component.

Implements UI_DESIGN_v0.5.0.md §4 (Prototype 1: Feedback Rating UI) tests.

Test strategy:
- Mock Streamlit (st) module to test render functions without a running app
- Use real requests.post mocking for API submission tests
- Coverage targets: Happy ≥50% / Error ≥15% / Boundary ≥10%

Run command:
    pytest tests/unit/test_feedback_dialog.py -v --tb=short
"""

from unittest.mock import MagicMock, patch

import pytest

from frontend.components.feedback_dialog import (
    DEFAULT_API_ENDPOINT,
    DEFAULT_RATING,
    FEEDBACK_CATEGORIES,
    MAX_COMMENT_LENGTH,
    MAX_RATING,
    MIN_RATING,
    TOAST_COLORS,
    render_feedback_dialog,
    render_feedback_toast,
    submit_feedback_to_api,
)


@pytest.fixture
def mock_streamlit():
    """Patch the streamlit module imported by feedback_dialog.

    Yields a MagicMock that replaces ``frontend.components.feedback_dialog.st``.
    The mock supports ``with`` statements (via MagicMock magic methods),
    enabling ``st.columns([...])`` to be used in ``with col:`` blocks.
    """
    with patch("frontend.components.feedback_dialog.st") as mock_st:
        # columns returns two MagicMock columns that support `with` syntax
        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        yield mock_st


# ============================================================
# render_feedback_dialog — Happy path tests (>= 50%)
# ============================================================


class TestRenderFeedbackDialogHappy:
    """Happy-path tests for render_feedback_dialog."""

    def test_render_feedback_dialog_returns_data_when_submit(self, mock_streamlit):
        """Submitting returns a complete feedback dict with all fields."""
        mock_streamlit.slider.return_value = 5
        mock_streamlit.selectbox.return_value = "praise"
        mock_streamlit.text_area.return_value = "Great work!"
        # Cancel button returns False, Submit button returns True
        mock_streamlit.button.side_effect = [False, True]

        result = render_feedback_dialog("skill_001", "sess_abc")

        assert result is not None
        assert result["rating"] == 5
        assert result["category"] == "praise"
        assert result["comment"] == "Great work!"
        assert result["skill_id"] == "skill_001"
        assert result["session_id"] == "sess_abc"
        assert "timestamp" in result
        # timestamp should be ISO 8601 with timezone info
        assert "T" in result["timestamp"]

    def test_render_feedback_dialog_with_comment(self, mock_streamlit):
        """Submitting with a non-empty comment preserves the comment string."""
        comment_text = "这次任务执行得非常准确，感谢！"
        mock_streamlit.slider.return_value = 4
        mock_streamlit.selectbox.return_value = "suggestion"
        mock_streamlit.text_area.return_value = comment_text
        mock_streamlit.button.side_effect = [False, True]

        result = render_feedback_dialog("skill_002", "sess_def")

        assert result is not None
        assert result["comment"] == comment_text
        assert result["rating"] == 4
        assert result["category"] == "suggestion"

    def test_render_feedback_dialog_without_comment(self, mock_streamlit):
        """Submitting with an empty comment sets comment to None."""
        mock_streamlit.slider.return_value = 3
        mock_streamlit.selectbox.return_value = "bug"
        mock_streamlit.text_area.return_value = ""
        mock_streamlit.button.side_effect = [False, True]

        result = render_feedback_dialog("skill_003", "sess_ghi")

        assert result is not None
        assert result["comment"] is None
        assert result["rating"] == 3
        assert result["category"] == "bug"

    def test_render_feedback_dialog_includes_all_categories(self, mock_streamlit):
        """All 4 categories are passed as options to st.selectbox."""
        mock_streamlit.slider.return_value = 5
        mock_streamlit.selectbox.return_value = "question"
        mock_streamlit.text_area.return_value = ""
        mock_streamlit.button.side_effect = [False, True]

        render_feedback_dialog("skill_004", "sess_jkl")

        # Verify selectbox was called with the correct options
        selectbox_kwargs = mock_streamlit.selectbox.call_args
        assert (
            selectbox_kwargs.kwargs.get("options") == FEEDBACK_CATEGORIES
            or selectbox_kwargs.args[1] == FEEDBACK_CATEGORIES
        )

    def test_render_feedback_dialog_keys_are_unique_per_session(self, mock_streamlit):
        """Widget keys include skill_id and session_id for state isolation."""
        mock_streamlit.slider.return_value = 5
        mock_streamlit.selectbox.return_value = "praise"
        mock_streamlit.text_area.return_value = ""
        mock_streamlit.button.side_effect = [False, True]

        render_feedback_dialog("skillA", "sessB")

        # All widget keys should contain both skill_id and session_id
        slider_key = mock_streamlit.slider.call_args.kwargs.get("key", "")
        selectbox_key = mock_streamlit.selectbox.call_args.kwargs.get("key", "")
        text_area_key = mock_streamlit.text_area.call_args.kwargs.get("key", "")

        assert "skillA" in slider_key and "sessB" in slider_key
        assert "skillA" in selectbox_key and "sessB" in selectbox_key
        assert "skillA" in text_area_key and "sessB" in text_area_key


# ============================================================
# render_feedback_dialog — Cancel/Error path tests (>= 15%)
# ============================================================


class TestRenderFeedbackDialogCancel:
    """Cancel/error path tests for render_feedback_dialog."""

    def test_render_feedback_dialog_returns_none_when_cancel(self, mock_streamlit):
        """Clicking cancel returns None (no submission)."""
        mock_streamlit.slider.return_value = 5
        mock_streamlit.selectbox.return_value = "bug"
        mock_streamlit.text_area.return_value = "Some text"
        # Cancel button returns True, Submit button returns False
        mock_streamlit.button.side_effect = [True, False]

        result = render_feedback_dialog("skill_005", "sess_mno")

        assert result is None

    def test_render_feedback_dialog_returns_none_when_no_button_clicked(
        self, mock_streamlit
    ):
        """When neither button is clicked, returns None (dialog still open)."""
        mock_streamlit.slider.return_value = 5
        mock_streamlit.selectbox.return_value = "praise"
        mock_streamlit.text_area.return_value = ""
        # Both buttons return False
        mock_streamlit.button.side_effect = [False, False]

        result = render_feedback_dialog("skill_006", "sess_pqr")

        assert result is None


# ============================================================
# render_feedback_dialog — Boundary tests (>= 10%)
# ============================================================


class TestRenderFeedbackDialogBoundary:
    """Boundary tests for render_feedback_dialog."""

    def test_render_feedback_dialog_min_rating(self, mock_streamlit):
        """Minimum rating (1 star) is accepted."""
        mock_streamlit.slider.return_value = MIN_RATING
        mock_streamlit.selectbox.return_value = "bug"
        mock_streamlit.text_area.return_value = ""
        mock_streamlit.button.side_effect = [False, True]

        result = render_feedback_dialog("skill_min", "sess_min")

        assert result is not None
        assert result["rating"] == MIN_RATING

    def test_render_feedback_dialog_max_rating(self, mock_streamlit):
        """Maximum rating (5 stars) is accepted."""
        mock_streamlit.slider.return_value = MAX_RATING
        mock_streamlit.selectbox.return_value = "praise"
        mock_streamlit.text_area.return_value = ""
        mock_streamlit.button.side_effect = [False, True]

        result = render_feedback_dialog("skill_max", "sess_max")

        assert result is not None
        assert result["rating"] == MAX_RATING

    def test_render_feedback_dialog_default_rating_is_max(self, mock_streamlit):
        """Slider default value is MAX_RATING (5 stars)."""
        mock_streamlit.slider.return_value = 5
        mock_streamlit.selectbox.return_value = "praise"
        mock_streamlit.text_area.return_value = ""
        mock_streamlit.button.side_effect = [False, True]

        render_feedback_dialog("skill_def", "sess_def")

        # Verify slider was called with value=MAX_RATING as default
        slider_call = mock_streamlit.slider.call_args
        # value may be passed as positional or keyword arg
        value = (
            slider_call.kwargs.get("value") if "value" in slider_call.kwargs else None
        )
        if value is None and len(slider_call.args) >= 4:
            value = slider_call.args[3]
        assert value == MAX_RATING


# ============================================================
# render_feedback_toast — Tests
# ============================================================


class TestRenderFeedbackToast:
    """Tests for render_feedback_toast."""

    def test_render_feedback_toast_success(self, mock_streamlit):
        """Success toast uses Morandi success color."""
        render_feedback_toast("Thanks!", type_="success")

        markdown_call = mock_streamlit.markdown.call_args
        markdown_text = markdown_call.args[0]
        assert TOAST_COLORS["success"] in markdown_text
        assert "Thanks!" in markdown_text

    def test_render_feedback_toast_error(self, mock_streamlit):
        """Error toast uses Morandi error color."""
        render_feedback_toast("Failed!", type_="error")

        markdown_call = mock_streamlit.markdown.call_args
        markdown_text = markdown_call.args[0]
        assert TOAST_COLORS["error"] in markdown_text
        assert "Failed!" in markdown_text

    def test_render_feedback_toast_info(self, mock_streamlit):
        """Info toast uses Morandi info color."""
        render_feedback_toast("Note", type_="info")

        markdown_call = mock_streamlit.markdown.call_args
        markdown_text = markdown_call.args[0]
        assert TOAST_COLORS["info"] in markdown_text
        assert "Note" in markdown_text

    def test_render_feedback_toast_invalid_type(self, mock_streamlit):
        """Invalid type falls back to info color (no crash)."""
        render_feedback_toast("Fallback", type_="invalid_type_xyz")

        markdown_call = mock_streamlit.markdown.call_args
        markdown_text = markdown_call.args[0]
        # Should fall back to info color
        assert TOAST_COLORS["info"] in markdown_text
        assert "Fallback" in markdown_text

    def test_render_feedback_toast_default_to_info(self, mock_streamlit):
        """Default type_ is 'info' (no type_ argument)."""
        # Call without type_ argument to test default
        render_feedback_toast("Default msg")

        markdown_call = mock_streamlit.markdown.call_args
        markdown_text = markdown_call.args[0]
        assert TOAST_COLORS["info"] in markdown_text
        assert "Default msg" in markdown_text


# ============================================================
# submit_feedback_to_api — Tests
# ============================================================


class TestSubmitFeedbackToApi:
    """Tests for submit_feedback_to_api."""

    def test_submit_feedback_to_api_success(self):
        """Successful HTTP 2xx response returns True."""
        feedback_data = {
            "rating": 5,
            "category": "praise",
            "comment": "Great!",
            "skill_id": "skill_001",
            "session_id": "sess_001",
            "timestamp": "2026-07-19T10:00:00+00:00",
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status":"ok"}'

        with patch(
            "frontend.components.feedback_dialog.requests.post",
            return_value=mock_response,
        ) as mock_post:
            result = submit_feedback_to_api(feedback_data)

        assert result is True
        mock_post.assert_called_once()
        # Verify the call passed the feedback_data as JSON
        call_kwargs = mock_post.call_args
        assert (
            call_kwargs.kwargs.get("json") == feedback_data
            or call_kwargs.args[1] == feedback_data
        )

    def test_submit_feedback_to_api_success_201(self):
        """HTTP 201 Created is also considered success."""
        feedback_data = {"rating": 4, "category": "bug"}
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.text = ""

        with patch(
            "frontend.components.feedback_dialog.requests.post",
            return_value=mock_response,
        ):
            result = submit_feedback_to_api(feedback_data)

        assert result is True

    def test_submit_feedback_to_api_failure(self):
        """HTTP 500 response returns False."""
        feedback_data = {
            "rating": 3,
            "category": "bug",
            "comment": "Something wrong",
            "skill_id": "skill_002",
            "session_id": "sess_002",
        }
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = '{"error":"internal"}'

        with patch(
            "frontend.components.feedback_dialog.requests.post",
            return_value=mock_response,
        ):
            result = submit_feedback_to_api(feedback_data)

        assert result is False

    def test_submit_feedback_to_api_failure_404(self):
        """HTTP 404 response returns False."""
        feedback_data = {"rating": 5, "category": "praise"}
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch(
            "frontend.components.feedback_dialog.requests.post",
            return_value=mock_response,
        ):
            result = submit_feedback_to_api(feedback_data)

        assert result is False

    def test_submit_feedback_to_api_network_error(self):
        """Network exception (RequestException) returns False, not raise."""
        import requests as real_requests

        feedback_data = {"rating": 5, "category": "praise"}

        with patch(
            "frontend.components.feedback_dialog.requests.post",
            side_effect=real_requests.ConnectionError("connection refused"),
        ):
            result = submit_feedback_to_api(feedback_data)

        assert result is False

    def test_submit_feedback_to_api_timeout_error(self):
        """Timeout exception returns False."""
        import requests as real_requests

        feedback_data = {"rating": 5, "category": "praise"}

        with patch(
            "frontend.components.feedback_dialog.requests.post",
            side_effect=real_requests.Timeout("timed out"),
        ):
            result = submit_feedback_to_api(feedback_data)

        assert result is False

    def test_submit_feedback_to_api_empty_data(self):
        """Empty feedback_data returns False without making HTTP call."""
        with patch("frontend.components.feedback_dialog.requests.post") as mock_post:
            result = submit_feedback_to_api({})

        assert result is False
        mock_post.assert_not_called()

    def test_submit_feedback_to_api_none_data(self):
        """None feedback_data returns False without making HTTP call."""
        with patch("frontend.components.feedback_dialog.requests.post") as mock_post:
            # None is falsy, should be rejected by the empty check
            result = submit_feedback_to_api(None)  # type: ignore[arg-type]

        assert result is False
        mock_post.assert_not_called()

    def test_submit_feedback_to_api_uses_default_endpoint(self):
        """When no endpoint provided, uses DEFAULT_API_ENDPOINT."""
        feedback_data = {"rating": 5, "category": "praise"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""

        with patch(
            "frontend.components.feedback_dialog.requests.post",
            return_value=mock_response,
        ) as mock_post:
            submit_feedback_to_api(feedback_data)

        call_args = mock_post.call_args
        # First positional arg should be the default endpoint
        assert call_args.args[0] == DEFAULT_API_ENDPOINT


# ============================================================
# Module constants — Tests
# ============================================================


class TestModuleConstants:
    """Tests for module-level constants (boundary/contract checks)."""

    def test_feedback_categories_has_five_options(self):
        """FEEDBACK_CATEGORIES must contain 5 categories (v0.5.1: +unspecified)."""
        assert len(FEEDBACK_CATEGORIES) == 5

    def test_feedback_categories_contains_expected_values(self):
        """Categories match API contract: unspecified/bug/suggestion/praise/question.

        v0.5.1 (P2-A): "unspecified" added as default option to allow users to
        skip category selection without blocking feedback submission.
        """
        assert set(FEEDBACK_CATEGORIES) == {
            "unspecified",
            "bug",
            "suggestion",
            "praise",
            "question",
        }

    def test_toast_colors_has_three_types(self):
        """TOAST_COLORS has success/error/info keys."""
        assert set(TOAST_COLORS.keys()) == {"success", "error", "info"}

    def test_rating_range_constants(self):
        """Rating constants match UI_DESIGN_v0.5.0.md §4.3."""
        assert MIN_RATING == 1
        assert MAX_RATING == 5
        assert DEFAULT_RATING == 5
        assert MAX_COMMENT_LENGTH == 500

    def test_toast_colors_are_morandi_hex(self):
        """Toast colors are valid Morandi hex strings."""
        for color in TOAST_COLORS.values():
            assert color.startswith("#")
            assert len(color) == 7  # #RRGGBB
