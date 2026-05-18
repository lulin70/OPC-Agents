"""Marketplace page router — thin wrapper around _marketplace_page module."""


def render_marketplace_page():
    from frontend.page_modules._marketplace_page import _render_skill_marketplace_page
    _render_skill_marketplace_page()
