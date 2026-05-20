"""Deliverables list renderer — extracted from app.py to fix NameError ordering bugs."""

import streamlit as st
import os
import logging

from opc_manager.i18n import t as _t
from frontend.routers.base_router import DELIVERABLES_DIR

logger = logging.getLogger(__name__)


def _read_file(filepath: str) -> bytes:
    """Read file contents for download."""
    with open(filepath, "rb") as f:
        return f.read()


def _render_deliverables_list():
    """Render the deliverables file list (original functionality)."""
    from frontend.components.shared import (
        _render_batch_export_section,
    )

    if not st.session_state.deliverables:
        st.info(_t("del_empty"))
    else:
        st.caption(_t("del_count", count=len(st.session_state.deliverables)))

        st.divider()

        _render_batch_export_section(DELIVERABLES_DIR)

        st.divider()

        search_query = st.text_input(
            _t("del_search"),
            placeholder=_t("del_search_placeholder"),
            key="deliverable_search",
        )

        filtered_deliverables = st.session_state.deliverables
        if search_query:
            search_lower = search_query.lower()
            filtered_deliverables = [
                d
                for d in st.session_state.deliverables
                if search_lower in d.get("prompt", "").lower()
                or search_lower in d.get("filename", "").lower()
                or search_lower in d.get("task_type", "").lower()
            ]
        match_suffix = (
            _t("del_match_count", count=len(filtered_deliverables))
            if search_query
            else ""
        )
        st.caption(
            _t("del_count", count=len(st.session_state.deliverables)) + match_suffix
        )

        for i, d in enumerate(filtered_deliverables):
            with st.expander(f"📄 {d['filename']}", expanded=(i == 0)):
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.markdown(f"**{_t('del_task_label')}**: `{d['prompt']}`")
                    st.markdown(f"**{_t('del_type_label')}**: {d['task_type']}")
                    st.markdown(f"**{_t('del_time_label')}**: {d['created_at']}")
                with col2:
                    st.metric(_t("del_size_label"), f"{d['size_kb']} KB")
                with col3:
                    real_fp = os.path.realpath(d["filepath"])
                    if not real_fp.startswith(os.path.realpath(DELIVERABLES_DIR)):
                        continue
                    if os.path.exists(real_fp):
                        st.download_button(
                            label=_t("dl_download"),
                            data=_read_file(real_fp),
                            file_name=d["filename"],
                            mime="application/octet-stream",
                            key=f"dl_{i}",
                            use_container_width=True,
                        )
