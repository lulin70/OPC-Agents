"""Deliverables page router — historical file management + audit log viewer."""
import streamlit as st

from opc_manager.i18n import t as _t
from frontend.renderers.deliverables_renderer import _render_deliverables_list
from frontend.renderers.audit_log_renderer import _render_audit_log_page


def render_deliverables_page():
    """Deliverables library page — historical file management center + audit log viewer."""
    st.markdown(_t("del_title"))

    deliverable_tabs = st.tabs([_t("del_tab_files"), _t("del_tab_log")])

    with deliverable_tabs[0]:
        _render_deliverables_list()

    with deliverable_tabs[1]:
        _render_audit_log_page()
