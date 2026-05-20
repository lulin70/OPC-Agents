"""Page routing system for OPC-Agents frontend."""

from enum import Enum


class PageKey(Enum):
    CHAT = "chat"
    DELIVERABLES = "deliverables"
    DASHBOARD = "dashboard"
    GROWTH = "growth"
    MARKETPLACE = "marketplace"
    SETTINGS = "settings"


PAGE_LABELS = {
    PageKey.CHAT: None,
    PageKey.DELIVERABLES: None,
    PageKey.DASHBOARD: None,
    PageKey.GROWTH: None,
    PageKey.MARKETPLACE: None,
    PageKey.SETTINGS: None,
}


def get_page_label(key: PageKey, t_func=None):
    """Get display label for a page key, using i18n if available."""
    label = PAGE_LABELS.get(key)
    if label is not None:
        return label
    key_map = {
        PageKey.CHAT: "nav_chat",
        PageKey.DELIVERABLES: "nav_deliverables",
        PageKey.DASHBOARD: "nav_dashboard_label",
        PageKey.GROWTH: "nav_growth",
        PageKey.MARKETPLACE: "nav_marketplace",
        PageKey.SETTINGS: "nav_settings",
    }
    i18n_key = key_map.get(key)
    if i18n_key and t_func:
        return t_func(i18n_key)
    return f"page_{key.value}"


def navigate(page_key: PageKey):
    """Dispatch to the correct page renderer."""
    if page_key == PageKey.CHAT:
        from .chat_router import render_chat_page

        render_chat_page()
    elif page_key == PageKey.DELIVERABLES:
        from .deliverables_router import render_deliverables_page

        render_deliverables_page()
    elif page_key == PageKey.DASHBOARD:
        from .dashboard_router import render_dashboard_page

        render_dashboard_page()
    elif page_key == PageKey.GROWTH:
        from .growth_router import render_growth_page

        render_growth_page()
    elif page_key == PageKey.MARKETPLACE:
        from .marketplace_router import render_marketplace_page

        render_marketplace_page()
    elif page_key == PageKey.SETTINGS:
        from .settings_router import render_settings_page

        render_settings_page()
