"""Dashboard page router — thin wrapper around _dashboard_page module."""


def render_dashboard_page():
    from frontend.page_modules._dashboard_page import _render_dashboard_page
    _render_dashboard_page(demo_mode=get_demo_mode())


def get_demo_mode():
    from frontend.routers.base_router import _is_demo_mode
    return _is_demo_mode()
