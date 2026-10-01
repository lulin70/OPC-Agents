"""CRM page router."""


def render_crm_page():
    """Render the customer-management page."""
    from frontend.page_modules._crm_page import render_crm_page as _render_crm_page

    _render_crm_page()
