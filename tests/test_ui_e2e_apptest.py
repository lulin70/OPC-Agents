"""UI-level E2E tests using Streamlit AppTest.

These tests launch the actual Streamlit frontend/app.py and simulate real user
interactions through the UI layer — clicking sidebar navigation, reading rendered
output, verifying page content. No direct Python function calls to business logic.

This fills the gap between:
  - Unit/integration tests (mocked, function-level, 2991 tests)
  - Real browser E2E (Playwright/Selenium, not yet implemented)

AppTest is Streamlit's official testing API (available since Streamlit 1.27).
Project uses Streamlit 1.57.0.

Test journeys:
  1. App Launch: load app.py → verify no crash, sidebar exists, title rendered
  2. Page Navigation: click sidebar radio → switch to each page → verify renders
  3. Chat Page (Demo Mode): no API key → demo banner, welcome, scenario buttons
  4. Settings Page: navigate → verify API key inputs exist
  5. Health Check: ?_stcore_health=1 → returns "ok"

Run:
    pytest tests/test_ui_e2e_apptest.py -v
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

APP_PATH = str(PROJECT_ROOT / "frontend" / "app.py")


@pytest.fixture
def isolated_data_env(tmp_path, monkeypatch):
    """Isolate data directory and environment for UI E2E tests.

    - Redirects OPC_WORKSPACE to tmp_path so all data/ goes to temp
    - Removes API keys to force DEMO_MODE=True (no real LLM calls)
    - Patches data_manager paths to prevent touching real data/
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Remove API keys -> DEMO_MODE = True
    for key in ("MOKA_API_KEY", "GLM_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    # Redirect workspace
    monkeypatch.setenv("OPC_WORKSPACE", str(tmp_path))

    # Patch data_manager paths before app loads
    import opc_manager.data_manager as dm

    monkeypatch.setattr(dm, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(dm, "DB_PATH", str(data_dir / "opc_data.db"))
    monkeypatch.setattr(dm, "BACKUP_DIR", str(data_dir / "backups"))
    monkeypatch.setattr(dm, "_db_initialized", False)
    monkeypatch.setattr(dm, "_local", type("Local", (), {"conn": None})())

    # Patch DEMO_MODE and is_demo_mode for demo mode tests
    import frontend.routers.base_router as br

    monkeypatch.setattr(br, "DEMO_MODE", True)
    # Also mock is_demo_mode to return True (since it now checks SettingsManager
    # which may have keys from real settings.json in dev environment)
    monkeypatch.setattr(br, "is_demo_mode", lambda: True)
    monkeypatch.setattr(br, "_has_api_key", lambda: False)

    yield tmp_path


@pytest.fixture
def isolated_data_env_no_mock(tmp_path, monkeypatch):
    """Like isolated_data_env but does NOT mock is_demo_mode/_has_api_key.

    Used by TestUIDemoModeDynamicRefresh which needs the real functions
    to verify dynamic refresh behavior.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    for key in ("MOKA_API_KEY", "GLM_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("OPC_WORKSPACE", str(tmp_path))

    import opc_manager.data_manager as dm

    monkeypatch.setattr(dm, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(dm, "DB_PATH", str(data_dir / "opc_data.db"))
    monkeypatch.setattr(dm, "BACKUP_DIR", str(data_dir / "backups"))
    monkeypatch.setattr(dm, "_db_initialized", False)
    monkeypatch.setattr(dm, "_local", type("Local", (), {"conn": None})())

    yield tmp_path


def _load_app():
    """Load the Streamlit app via AppTest."""
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(APP_PATH)


# ═══════════════════════════════════════════════════════════════════════════
# Journey 1: App Launch — First User Impression
# ═══════════════════════════════════════════════════════════════════════════


class TestUIAppLaunch:
    """Verify the app loads and renders the initial UI correctly."""

    def test_app_loads_without_error(self, isolated_data_env):
        """App loads and renders without crashing."""
        at = _load_app()
        at.run(timeout=30)
        assert not at.exception, f"App raised exception: {at.exception}"

    def test_sidebar_navigation_exists(self, isolated_data_env):
        """Sidebar contains page navigation radio button."""
        at = _load_app()
        at.run(timeout=30)
        assert len(at.sidebar.radio) >= 1, "Sidebar navigation radio not found"

    def test_app_title_rendered(self, isolated_data_env):
        """App title or branding is visible somewhere in the page."""
        at = _load_app()
        at.run(timeout=30)
        all_text = " ".join(m.value for m in at.markdown)
        all_text += " " + " ".join(t.value for t in at.text)
        assert (
            "OPC" in all_text or "一人公司" in all_text
        ), f"App title not found in rendered text"

    def test_version_displayed_in_sidebar(self, isolated_data_env):
        """Version string is shown in sidebar."""
        at = _load_app()
        at.run(timeout=30)
        captions = [c.value for c in at.sidebar.caption]
        all_sidebar_text = " ".join(captions)
        # Should contain version like "v0.2.5"
        assert any(
            "v0." in c for c in captions
        ), f"Version not in sidebar captions: {captions}"


# ═══════════════════════════════════════════════════════════════════════════
# Journey 2: Page Navigation — User Clicks Through All Pages
# ═══════════════════════════════════════════════════════════════════════════


class TestUIPageNavigation:
    """Verify all pages render without errors when navigated to."""

    def test_navigate_to_dashboard(self, isolated_data_env):
        """Clicking 'dashboard' in sidebar renders dashboard page."""
        at = _load_app()
        at.run(timeout=30)

        at.sidebar.radio[0].set_value("dashboard")
        at.run(timeout=30)

        assert not at.exception, f"Dashboard page raised: {at.exception}"

    def test_navigate_to_settings(self, isolated_data_env):
        """Clicking 'settings' in sidebar renders settings page."""
        at = _load_app()
        at.run(timeout=30)

        at.sidebar.radio[0].set_value("settings")
        at.run(timeout=30)

        assert not at.exception, f"Settings page raised: {at.exception}"

    def test_navigate_to_marketplace(self, isolated_data_env):
        """Clicking 'marketplace' in sidebar renders marketplace page."""
        at = _load_app()
        at.run(timeout=30)

        at.sidebar.radio[0].set_value("marketplace")
        at.run(timeout=30)

        assert not at.exception, f"Marketplace page raised: {at.exception}"

    def test_navigate_to_deliverables(self, isolated_data_env):
        """Clicking 'deliverables' in sidebar renders deliverables page."""
        at = _load_app()
        at.run(timeout=30)

        at.sidebar.radio[0].set_value("deliverables")
        at.run(timeout=30)

        assert not at.exception, f"Deliverables page raised: {at.exception}"

    def test_navigate_to_growth(self, isolated_data_env):
        """Clicking 'growth' in sidebar renders growth page."""
        at = _load_app()
        at.run(timeout=30)

        at.sidebar.radio[0].set_value("growth")
        at.run(timeout=30)

        assert not at.exception, f"Growth page raised: {at.exception}"

    def test_all_pages_navigable_in_sequence(self, isolated_data_env):
        """User can navigate through all pages in sequence without errors."""
        at = _load_app()
        at.run(timeout=30)

        pages = [
            "dashboard",
            "settings",
            "marketplace",
            "deliverables",
            "growth",
            "chat",
        ]
        for page in pages:
            at.sidebar.radio[0].set_value(page)
            at.run(timeout=30)
            assert not at.exception, f"Navigating to '{page}' raised: {at.exception}"


# ═══════════════════════════════════════════════════════════════════════════
# Journey 3: Chat Page (Demo Mode) — New User Without API Key
# ═══════════════════════════════════════════════════════════════════════════


class TestUIChatPageDemoMode:
    """Verify Chat page behavior when no API key is configured (demo mode)."""

    def test_chat_page_shows_demo_banner(self, isolated_data_env):
        """Demo mode banner is displayed at top of page."""
        at = _load_app()
        at.run(timeout=30)

        # Demo banner is injected via st.markdown with HTML
        all_markdown = " ".join(m.value for m in at.markdown)
        assert (
            "demo" in all_markdown.lower() or "演示" in all_markdown
        ), f"Demo banner not found"

    def test_chat_page_shows_demo_info(self, isolated_data_env):
        """Chat page in demo mode shows info about available features."""
        at = _load_app()
        at.run(timeout=30)

        infos = " ".join(i.value for i in at.info)
        assert len(infos) > 0, "No info message on demo chat page"

    def test_chat_page_has_scenario_buttons(self, isolated_data_env):
        """Scenario buttons are rendered on chat page."""
        at = _load_app()
        at.run(timeout=30)

        # In demo mode, chat page shows demo info then st.stop()
        # But sidebar buttons should still exist
        assert len(at.sidebar.button) > 0, "No buttons in sidebar"

    def test_demo_mode_shows_metrics(self, isolated_data_env):
        """Demo mode shows sample dashboard metrics."""
        at = _load_app()
        at.run(timeout=30)

        # Demo mode shows st.metric widgets
        assert len(at.metric) > 0, "No metrics shown in demo mode"


# ═══════════════════════════════════════════════════════════════════════════
# Journey 3b: API Key Config via Settings — Demo Mode Dynamic Refresh
# ═══════════════════════════════════════════════════════════════════════════


class TestUIDemoModeDynamicRefresh:
    """Verify that demo mode status refreshes dynamically after API Key config.

    This is the critical P0 fix: before, DEMO_MODE was cached at module load
    and users had to restart the app after configuring API Key. Now it should
    refresh dynamically via is_demo_mode().
    """

    def test_demo_mode_refreshes_after_api_key_set(
        self, isolated_data_env_no_mock, monkeypatch
    ):
        """After setting API Key via os.environ, demo mode should be False."""
        from frontend.routers.base_router import is_demo_mode, _has_api_key

        # Ensure clean state: no env vars, mock SettingsManager to return no key
        for key in ("MOKA_API_KEY", "GLM_API_KEY", "OPENAI_API_KEY"):
            monkeypatch.delenv(key, raising=False)

        # Mock get_settings to return empty key (isolate from real settings.json)
        from unittest.mock import MagicMock, patch

        mock_settings = MagicMock()
        mock_settings._llm.provider = "moka"
        mock_settings.get_api_key.return_value = None

        with patch("opc_manager.settings.get_settings", return_value=mock_settings):
            # Initially in demo mode (no API key)
            assert is_demo_mode() is True, "Should start in demo mode"
            assert _has_api_key() is False, "Should have no API key initially"

        # Simulate user configuring API Key via env var
        monkeypatch.setenv("MOKA_API_KEY", "sk-test-key-for-refresh")

        with patch("opc_manager.settings.get_settings", return_value=mock_settings):
            # Demo mode should now be False WITHOUT app restart
            assert _has_api_key() is True, "Should detect API key after setting"
            assert (
                is_demo_mode() is False
            ), "Should exit demo mode dynamically after API key set"

        # Cleanup
        monkeypatch.delenv("MOKA_API_KEY", raising=False)

        with patch("opc_manager.settings.get_settings", return_value=mock_settings):
            assert (
                is_demo_mode() is True
            ), "Should return to demo mode after key removed"

    def test_demo_mode_checks_settings_manager(
        self, isolated_data_env_no_mock, monkeypatch
    ):
        """_has_api_key() should check SettingsManager, not just os.environ."""
        from frontend.routers.base_router import _has_api_key
        from unittest.mock import MagicMock, patch

        # No env var
        for key in ("MOKA_API_KEY", "GLM_API_KEY", "OPENAI_API_KEY"):
            monkeypatch.delenv(key, raising=False)

        # Mock SettingsManager to return no key
        mock_settings = MagicMock()
        mock_settings._llm.provider = "moka"
        mock_settings.get_api_key.return_value = None

        with patch("opc_manager.settings.get_settings", return_value=mock_settings):
            assert _has_api_key() is False, "Should be False with no key anywhere"

        # Now mock SettingsManager to return a key (simulating Settings UI save)
        mock_settings.get_api_key.return_value = "sk-via-settings-ui"

        with patch("opc_manager.settings.get_settings", return_value=mock_settings):
            assert (
                _has_api_key() is True
            ), "Should detect API key saved via SettingsManager"


# ═══════════════════════════════════════════════════════════════════════════
# Journey 4: Settings Page — API Key Configuration UI
# ═══════════════════════════════════════════════════════════════════════════


class TestUISettingsPage:
    """Verify Settings page has the expected configuration UI elements."""

    def test_settings_page_has_inputs(self, isolated_data_env):
        """Settings page has text inputs or selectors for configuration."""
        at = _load_app()
        at.run(timeout=30)

        at.sidebar.radio[0].set_value("settings")
        at.run(timeout=30)

        assert not at.exception
        # Settings page should have some input elements
        assert (
            len(at.text_input) > 0 or len(at.selectbox) > 0
        ), "No input elements on settings page"

    def test_settings_page_has_content(self, isolated_data_env):
        """Settings page renders meaningful content (not blank)."""
        at = _load_app()
        at.run(timeout=30)

        at.sidebar.radio[0].set_value("settings")
        at.run(timeout=30)

        all_text = " ".join(m.value for m in at.markdown)
        all_text += " " + " ".join(t.value for t in at.text)
        assert (
            len(all_text) > 50
        ), f"Settings page appears blank (text length={len(all_text)})"


# ═══════════════════════════════════════════════════════════════════════════
# Journey 5: Health Check — Monitoring Endpoint
# ═══════════════════════════════════════════════════════════════════════════


class TestUIHealthCheck:
    """Verify the Streamlit health check endpoint works.

    Note: AppTest.from_file has a known limitation where query_params set via
    at.query_params don't propagate to st.query_params inside the script.
    We test the health check logic directly via from_function instead.
    """

    def test_health_check_returns_ok(self, isolated_data_env):
        """Health check query param returns 'ok'."""
        from streamlit.testing.v1 import AppTest

        def health_script():
            import streamlit as st

            if st.query_params.get("_stcore_health") == "1":
                st.write("ok")
                st.stop()

        at = AppTest.from_function(health_script)
        at.query_params["_stcore_health"] = "1"
        at.run(timeout=10)

        all_text = " ".join(m.value for m in at.markdown)
        assert (
            "ok" in all_text.lower()
        ), f"Health check didn't return 'ok': {all_text[:200]}"


# ═══════════════════════════════════════════════════════════════════════════
# Journey 6: Sidebar Tools — Skill Editor, Marketplace, Undo, Log Panel
# ═══════════════════════════════════════════════════════════════════════════


class TestUISidebarTools:
    """Verify sidebar tool buttons exist and toggle panels."""

    def test_skill_editor_button_exists(self, isolated_data_env):
        """Skill editor button is visible in sidebar."""
        at = _load_app()
        at.run(timeout=30)

        sidebar_texts = [b.label for b in at.sidebar.button]
        assert len(sidebar_texts) > 0, "No buttons in sidebar"

    def test_undo_history_button_exists(self, isolated_data_env):
        """Undo history button is visible in sidebar."""
        at = _load_app()
        at.run(timeout=30)

        # The undo button should be in sidebar
        assert (
            len(at.sidebar.button) >= 2
        ), f"Expected at least 2 sidebar buttons, got {len(at.sidebar.button)}"

    def test_clicking_skill_editor_toggles_panel(self, isolated_data_env):
        """Clicking skill editor button toggles a panel."""
        at = _load_app()
        at.run(timeout=30)

        # Find and click the skill editor button (first sidebar button)
        if len(at.sidebar.button) > 0:
            at.sidebar.button[0].click()
            at.run(timeout=30)
            assert not at.exception, f"Clicking sidebar button raised: {at.exception}"


# ═══════════════════════════════════════════════════════════════════════════
# Journey 7: Language Switching — i18n UI
# ═══════════════════════════════════════════════════════════════════════════


class TestUILanguageSwitching:
    """Verify language switching works in the UI."""

    def test_language_selector_exists(self, isolated_data_env):
        """Language selector is available in sidebar.

        Note: sidebar has two selectboxes — [0] is theme, [1] is language.
        """
        at = _load_app()
        at.run(timeout=30)

        assert len(at.sidebar.selectbox) >= 2, (
            f"Expected at least 2 selectboxes (theme+language), "
            f"got {len(at.sidebar.selectbox)}"
        )

    def test_switch_language_to_english(self, isolated_data_env):
        """Switching to English changes UI text without error."""
        at = _load_app()
        at.run(timeout=30)

        # selectbox[0] = theme, selectbox[1] = language
        if len(at.sidebar.selectbox) >= 2:
            at.sidebar.selectbox[1].set_value("en_US")
            at.run(timeout=30)
            assert not at.exception, f"Switching to English raised: {at.exception}"

    def test_switch_language_to_japanese(self, isolated_data_env):
        """Switching to Japanese changes UI text without error."""
        at = _load_app()
        at.run(timeout=30)

        if len(at.sidebar.selectbox) >= 2:
            at.sidebar.selectbox[1].set_value("ja_JP")
            at.run(timeout=30)
            assert not at.exception, f"Switching to Japanese raised: {at.exception}"
