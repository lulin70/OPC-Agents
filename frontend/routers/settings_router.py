"""Settings page router — thin wrapper around _settings_page module."""


def render_settings_page():
    from frontend.page_modules._settings_page import _create_settings_page

    _create_settings_page()
