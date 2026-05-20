"""Growth/Flywheel page router — gamified user motivation system."""

import streamlit as st

from opc_manager.i18n import t as _t


def render_growth_page():
    """Growth flywheel page — gamified user motivation system."""
    st.markdown(_t("growth_title"))
    scores = st.session_state.flywheel_scores
    level = st.session_state.flywheel_level
    count = st.session_state.scenario_count

    _raw = _t("growth_level_1")
    lv_name = _t("growth_level_1_name")
    lv_desc = _t("growth_level_1_desc")

    col_level, col_count = st.columns([2, 1])
    with col_level:
        st.subheader(lv_name)
        st.caption(lv_desc)
    with col_count:
        st.metric(_t("growth_interactions"), count)
    if count > 0:
        st.metric(_t("growth_current_level"), f"Lv.{level}")

    st.divider()
    st.markdown(f"### {_t('growth_5d_health')}")
    dims = [
        ("📝", "content_quality", _t("growth_metric_content")),
        ("👥", "audience_growth", _t("growth_metric_audience")),
        ("💰", "monetization", _t("growth_metric_monetization")),
        ("🔗", "cross_promotion", _t("growth_metric_cross_promo")),
        ("🌍", "ecosystem_synergy", _t("growth_metric_ecosystem")),
    ]
    for icon, dim_key, dim_label in dims:
        score = scores.get(dim_key, 0)
        c1, c2, c3 = st.columns([1.5, 6, 1])
        with c1:
            st.markdown(f"{icon} **{dim_label}**")
        with c2:
            st.progress(score / 100)
        with c3:
            color = "#4CAF50" if score >= 60 else ("#FF9800" if score >= 30 else "#ccc")
            st.metric(label=dim_label, value=score)

    if count == 0:
        st.info(f"💡 {_t('growth_empty_hint')}")
    elif level < 3:
        st.success(
            f"🎯 {_t('growth_upgrade_hint', level_name=_t('growth_upgrade_target'))}"
        )
