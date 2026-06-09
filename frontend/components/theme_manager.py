"""Theme management components for OPC-Agents frontend.

Provides theme configuration and application extracted from shared.py:
- THEME_CONFIGS: Theme color/font configuration dictionary
- apply_theme: Apply a theme via Streamlit config
- _get_theme_css: Generate custom CSS for enhanced theme support
"""

import streamlit as st
import logging

__all__ = ["THEME_CONFIGS", "apply_theme", "_get_theme_css"]

logger = logging.getLogger(__name__)


THEME_CONFIGS = {
    "light": {
        "backgroundColor": "#FFFFFF",
        "secondaryBackgroundColor": "#F0F2F6",
        "textColor": "#1F2937",
        "font": "sans-serif",
        "primaryColor": "#3B82F6",
    },
    "dark": {
        "backgroundColor": "#111827",
        "secondaryBackgroundColor": "#1F2937",
        "textColor": "#F9FAFB",
        "font": "sans-serif",
        "primaryColor": "#60A5FA",
    },
    "sunset": {
        "backgroundColor": "#1a1423",
        "secondaryBackgroundColor": "#261a2e",
        "textColor": "#fef3c7",
        "font": "sans-serif",
        "primaryColor": "#F59E0B",
    },
    "forest": {
        "backgroundColor": "#0d1f17",
        "secondaryBackgroundColor": "#152920",
        "textColor": "#D1FAE5",
        "font": "sans-serif",
        "primaryColor": "#34D399",
    },
    "ocean": {
        "backgroundColor": "#0c1929",
        "secondaryBackgroundColor": "#162d4a",
        "textColor": "#E0F2FE",
        "font": "sans-serif",
        "primaryColor": "#38BDF8",
    },
}


def apply_theme(theme_name: str):
    """Apply complete theme via Streamlit config."""
    config = THEME_CONFIGS.get(theme_name, THEME_CONFIGS["light"])
    import streamlit as st

    try:
        st.config.set_option("theme.primaryColor", config["primaryColor"])
        st.config.set_option("theme.backgroundColor", config["backgroundColor"])
        st.config.set_option(
            "theme.secondaryBackgroundColor", config["secondaryBackgroundColor"]
        )
        st.config.set_option("theme.textColor", config["textColor"])
        st.config.set_option("theme.font", config["font"])
        if theme_name == "dark":
            st.config.set_option("theme.base", "dark")
        elif theme_name == "light":
            st.config.set_option("theme.base", "light")
    except Exception as e:
        logger.warning("[ThemeManager] Theme setting failed: %s", e)

    css = _get_theme_css(theme_name)
    if css:
        st.markdown(css, unsafe_allow_html=True)


def _get_theme_css(theme_name: str) -> str:
    """Return custom CSS for enhanced theme support."""
    themes = {
        "dark": """
            .stApp { background-color: #111827 !important; }
            .stMarkdown { color: #F9FAFB !important; }
            .stDataFrame { background-color: #1F2937 !important; }
            [data-testid="stMetric"] { background-color: #1F2937 !important; }
            [data-testid="stCheckbox"] label { color: #F9FAFB !important; }
            .stSelectbox > div > div { background-color: #1F2937 !important; }
            .stTextInput > div > div { background-color: #1F2937 !important; }
            """,
        "sunset": """
            .stApp { background-color: #1a1423 !important; }
            .stMarkdown { color: #fef3c7 !important; }
            [data-testid="stMetric"] { background-color: #261a2e !important; }
            """,
        "forest": """
            .stApp { background-color: #0d1f17 !important; }
            .stMarkdown { color: #D1FAE5 !important; }
            [data-testid="stMetric"] { background-color: #152920 !important; }
            """,
        "ocean": """
            .stApp { background-color: #0c1929 !important; }
            .stMarkdown { color: #E0F2FE !important; }
            [data-testid="stMetric"] { background-color: #162d4a !important; }
            """,
    }
    base_css = themes.get(theme_name, "")

    mobile_css = """
    /* 移动端响应式规则 */
    @media (max-width: 768px) {
        /* 按钮在小屏幕全宽显示 */
        .stButton > button {
            width: 100% !important;
            min-height: 44px !important;
        }
        /* 侧边栏在小屏幕自动收起 */
        [data-testid="stSidebar"] {
            width: 0px !important;
            min-width: 0px !important;
            overflow: hidden;
        }
        [data-testid="stSidebar"][aria-expanded="true"] {
            width: 280px !important;
            min-width: 280px !important;
        }
        /* Metric 卡片适配 */
        [data-testid="stMetric"] {
            padding: 8px !important;
        }
        /* 减少内边距节省空间 */
        .block-container {
            padding-top: 2rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
    }
    """
    return base_css + mobile_css
