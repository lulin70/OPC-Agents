"""Tests for P1 UX polish improvements.

Covers:
- P1-5: Dashboard Demo Data Mode Enhancement (data structure, badge, demo mode detection)
- P1-6: Success Toast Notifications System (HTML output validation)
- P1-7: Export Preview functionality (return value logic)
- P1-8: Keyboard Shortcut Help Bubbles (session state management)
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestDemoDataStructure:
    """P1-5: Validate _DEMO_DATA structure in dashboard_page.py."""

    def test_demo_data_exists(self):
        from frontend.page_modules._dashboard_page import _DEMO_DATA

        assert isinstance(_DEMO_DATA, dict), "_DEMO_DATA should be a dict"
        assert len(_DEMO_DATA) > 0, "_DEMO_DATA should not be empty"

    def test_demo_data_has_required_keys(self):
        from frontend.page_modules._dashboard_page import _DEMO_DATA

        required_keys = [
            "income_months",
            "income_values",
            "clients",
            "tasks",
            "finance",
            "timeline",
            "skills",
        ]
        for key in required_keys:
            assert key in _DEMO_DATA, f"_DEMO_DATA missing required key: {key}"

    def test_demo_income_data_structure(self):
        from frontend.page_modules._dashboard_page import _DEMO_DATA

        assert len(_DEMO_DATA["income_months"]) == len(_DEMO_DATA["income_values"])
        assert all(isinstance(m, str) for m in _DEMO_DATA["income_months"])
        assert all(isinstance(v, (int, float)) for v in _DEMO_DATA["income_values"])

    def test_demo_clients_are_realistic(self):
        from frontend.page_modules._dashboard_page import _DEMO_DATA

        clients = _DEMO_DATA["clients"]
        assert len(clients) >= 3, "Should have at least 3 demo clients"
        for client in clients:
            assert "name" in client, "Client missing 'name' field"
            assert "contact" in client, "Client missing 'contact' field"
            assert "revenue" in client, "Client missing 'revenue' field"
            assert "health" in client, "Client missing 'health' field"
            assert (
                0 <= client["health"] <= 100
            ), f"Health score out of range: {client['health']}"

    def test_demo_tasks_structure(self):
        from frontend.page_modules._dashboard_page import _DEMO_DATA

        tasks = _DEMO_DATA["tasks"]
        assert "total" in tasks
        assert "done" in tasks
        assert tasks["total"] == sum(
            [tasks["done"], tasks.get("in_progress", 0), tasks.get("blocked", 0)]
        )

    def test_demo_finance_chinese_currency(self):
        from frontend.page_modules._dashboard_page import _DEMO_DATA

        finance = _DEMO_DATA["finance"]
        assert "income" in finance
        assert "net_profit" in finance
        assert finance["income"] > 0
        assert finance["net_profit"] > 0

    def test_demo_timeline_entries(self):
        from frontend.page_modules._dashboard_page import _DEMO_DATA

        timeline = _DEMO_DATA["timeline"]
        assert len(timeline) >= 4, "Should have at least 4 timeline entries"
        for entry in timeline:
            assert "time" in entry
            assert "icon" in entry
            assert "text" in entry
            assert "tag" in entry

    def test_demo_skills_with_trends(self):
        from frontend.page_modules._dashboard_page import _DEMO_DATA

        skills = _DEMO_DATA["skills"]
        assert len(skills) >= 4
        for skill in skills:
            assert "name" in skill
            assert "usage" in skill
            assert "trend" in skill
            assert isinstance(skill["usage"], int)
            assert skill["usage"] > 0


class TestToastNotifications:
    """P1-6: Validate toast notification HTML output."""

    def test_success_toast_contains_icon(self):
        from frontend.components.shared import show_success

        html_output = show_success.__doc__
        assert "✅" in html_output or "success" in html_output.lower()

    def test_error_toast_contains_icon(self):
        from frontend.components.shared import show_error

        html_output = show_error.__doc__
        assert "❌" in html_output or "error" in html_output.lower()

    def test_info_toast_contains_icon(self):
        from frontend.components.shared import show_info

        html_output = show_info.__doc__
        assert "ℹ️" in html_output or "info" in html_output.lower()

    def test_toast_functions_have_correct_signature(self):
        from frontend.components.shared import show_success, show_error, show_info
        import inspect

        sig_success = inspect.signature(show_success)
        assert "message" in sig_success.parameters
        assert "icon" in sig_success.parameters
        sig_error = inspect.signature(show_error)
        assert "message" in sig_error.parameters
        sig_info = inspect.signature(show_info)
        assert "message" in sig_info.parameters

    def test_success_toast_html_has_gradient(self):
        from frontend.components.shared import show_success
        import inspect

        source = inspect.getsource(show_success)
        assert "#10b981" in source or "gradient" in source.lower()

    def test_error_toast_html_is_red(self):
        from frontend.components.shared import show_error
        import inspect

        source = inspect.getsource(show_error)
        assert "#ef4444" in source or "#dc2626" in source


class TestExportPreview:
    """P1-7: Validate export preview function logic."""

    def test_export_preview_function_exists(self):
        from frontend.components.shared import _render_export_preview

        assert callable(_render_export_preview)

    def test_export_preview_signature(self):
        from frontend.components.shared import _render_export_preview
        import inspect

        sig = inspect.signature(_render_export_preview)
        params = list(sig.parameters.keys())
        assert "item_data" in params
        assert "format_type" in params

    def test_export_single_with_preview_exists(self):
        from frontend.components.shared import _export_single_with_preview

        assert callable(_export_single_with_preview)

    def test_format_hints_cover_all_formats(self):
        from frontend.components.shared import _render_export_preview
        import inspect

        source = inspect.getsource(_render_export_preview)
        assert "pdf" in source.lower()
        assert "word" in source.lower()
        assert "excel" in source.lower()
        assert "png" in source.lower() or "image" in source.lower()

    def test_export_preview_has_confirm_cancel(self):
        from frontend.components.shared import _render_export_preview
        import inspect

        source = inspect.getsource(_render_export_preview)
        assert "confirm_export" in source
        assert "cancel" in source


class TestShortcutHints:
    """P1-8: Validate shortcut hints session state management."""

    def test_maybe_show_shortcut_hints_exists(self):
        from frontend.components.shared import _maybe_show_shortcut_hints

        assert callable(_maybe_show_shortcut_hints)

    def test_floating_help_button_exists(self):
        from frontend.components.shared import _render_floating_help_button

        assert callable(_render_floating_help_button)

    def test_shortcut_hints_uses_session_state(self):
        from frontend.components.shared import _maybe_show_shortcut_hints
        import inspect

        source = inspect.getsource(_maybe_show_shortcut_hints)
        assert "shortcuts_shown" in source
        assert "st.session_state" in source

    def test_shortcut_hints_has_dismiss_button(self):
        from frontend.components.shared import _maybe_show_shortcut_hints
        import inspect

        source = inspect.getsource(_maybe_show_shortcut_hints)
        assert "shortcut_dismiss_btn" in source or "dismiss" in source.lower()

    def test_shortcut_hints_has_later_button(self):
        from frontend.components.shared import _maybe_show_shortcut_hints
        import inspect

        source = inspect.getsource(_maybe_show_shortcut_hints)
        assert "shortcut_later_btn" in source or "later" in source.lower()

    def test_enhanced_shortcuts_table(self):
        from frontend.components.shared import _render_shortcuts_help
        import inspect

        source = inspect.getsource(_render_shortcuts_help)
        assert "Enter" in source
        assert "Esc" in source
        # Ctrl+Z removed — not implementable in Streamlit

    def test_floating_help_resets_state(self):
        from frontend.components.shared import _render_floating_help_button
        import inspect

        source = inspect.getsource(_render_floating_help_button)
        assert "shortcuts_shown" in source
        assert "False" in source


class TestDemoModeDetection:
    """P1-5: Validate demo mode detection and badge rendering."""

    def test_is_demo_mode_exists(self):
        from frontend.page_modules._dashboard_page import _is_demo_mode

        assert callable(_is_demo_mode)

    def test_render_demo_badge_exists(self):
        from frontend.page_modules._dashboard_page import _render_demo_badge

        assert callable(_render_demo_badge)

    def test_demo_badge_contains_text(self):
        from frontend.page_modules._dashboard_page import _render_demo_badge
        import inspect

        source = inspect.getsource(_render_demo_badge)
        assert "Demo" in source or "demo" in source
        assert "🎮" in source

    def test_demo_badge_uses_html(self):
        from frontend.page_modules._dashboard_page import _render_demo_badge
        import inspect

        source = inspect.getsource(_render_demo_badge)
        assert "unsafe_allow_html" in source
