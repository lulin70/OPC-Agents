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
    # Morandi themes — aligned with UI_DESIGN_v0.5.1.md §2.1
    "morandi_light": {
        "backgroundColor": "#F5F2EE",           # Morandi warm off-white
        "secondaryBackgroundColor": "#EBE5DD",  # Morandi beige deepened
        "textColor": "#3A3A3A",                  # Morandi dark gray
        "font": "sans-serif",
        "primaryColor": "#6B7B8C",               # Morandi gray-blue
    },
    "morandi_dark": {
        "backgroundColor": "#1F1B16",            # Warm dark brown
        "secondaryBackgroundColor": "#2A2520",   # Warm dark brown deepened
        "textColor": "#E8E0D5",                  # Warm white
        "font": "sans-serif",
        "primaryColor": "#6B7B8C",               # Morandi gray-blue (brand consistency)
    },
}


def apply_theme(theme_name: str):
    """Apply complete theme via Streamlit config."""
    config = THEME_CONFIGS.get(theme_name, THEME_CONFIGS["light"])

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
        # Anti-duplicate injection: skip CSS re-injection for the same theme
        # on Streamlit reruns. Flag is per-theme so theme switches still inject.
        injection_flag = f"theme_css_injected_{theme_name}"
        if not st.session_state.get(injection_flag):
            st.markdown(css, unsafe_allow_html=True)
            st.session_state[injection_flag] = True


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
        # Morandi Dark theme — aligned with UI_DESIGN_v0.5.1.md §3.3
        "morandi_dark": """
            /* morandi_dark theme — warm dark brown palette (#1F1B16 bg + #E8E0D5 text) */
            .stApp { background-color: #1F1B16 !important; }
            .stMarkdown { color: #E8E0D5 !important; }
            .stDataFrame { background-color: #2A2520 !important; }
            [data-testid="stMetric"] { background-color: #2A2520 !important; }
            [data-testid="stCheckbox"] label { color: #E8E0D5 !important; }
            .stSelectbox > div > div { background-color: #2A2520 !important; color: #E8E0D5 !important; }
            .stTextInput > div > div { background-color: #2A2520 !important; color: #E8E0D5 !important; }
            .stTextArea > div > div { background-color: #2A2520 !important; color: #E8E0D5 !important; }
            /* Morandi semantic colors preserved for brand recognition */
            .stSuccess { border-left: 3px solid #8FAB8B !important; }
            .stWarning { border-left: 3px solid #D9BC85 !important; }
            .stError { border-left: 3px solid #C89595 !important; }
            .stInfo { border-left: 3px solid #9AAEC0 !important; }
            """,
        # Morandi Light theme — warm Morandi palette
        "morandi_light": """
            .stApp { background-color: #F5F2EE !important; }
            .stMarkdown { color: #3A3A3A !important; }
            .stDataFrame { background-color: #EBE5DD !important; }
            [data-testid="stMetric"] { background-color: #EBE5DD !important; }
            [data-testid="stCheckbox"] label { color: #3A3A3A !important; }
            .stSelectbox > div > div { background-color: #EBE5DD !important; color: #3A3A3A !important; }
            .stTextInput > div > div { background-color: #EBE5DD !important; color: #3A3A3A !important; }
            .stTextArea > div > div { background-color: #EBE5DD !important; color: #3A3A3A !important; }
            /* Morandi semantic colors preserved for brand recognition */
            .stSuccess { border-left: 3px solid #7A9B76 !important; }
            .stWarning { border-left: 3px solid #C9A96E !important; }
            .stError { border-left: 3px solid #B07C7C !important; }
            .stInfo { border-left: 3px solid #7B8FA1 !important; }
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
        [data-testid="collapsedControl"] {
            display: flex !important;
        }
        /* Metric 卡片适配 */
        [data-testid="stMetric"] {
            padding: 8px !important;
        }
        [data-testid="stMetricContainer"] {
            width: 100% !important;
        }
        /* 减少内边距节省空间 */
        .block-container {
            padding-top: 2rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        /* Dashboard / 场景按钮在小屏幕单列显示 */
        [data-testid="stHorizontalBlock"] > div {
            flex-direction: column !important;
            width: 100% !important;
        }
        /* 输入框区域增加触摸友好的间距 */
        [data-testid="stChatInput"] {
            padding: 12px 8px !important;
        }
        [data-testid="stChatInput"] textarea {
            min-height: 48px !important;
            font-size: 16px !important;
        }
        /* 聊天消息区域增加间距 */
        [data-testid="stChatMessage"] {
            padding: 8px 4px !important;
        }
        /* 表格横向滚动 */
        .stDataFrame, [data-testid="stTable"] {
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch !important;
        }
        /* Tab 触摸目标增大 */
        .stTabs [role="tab"] {
            min-height: 44px !important;
            padding: 8px 12px !important;
            font-size: 14px !important;
        }
        /* Selectbox 触摸友好 */
        [data-testid="stSelectbox"] {
            min-height: 44px !important;
        }
        /* 防止文字溢出 */
        .stMarkdown, .stText {
            word-break: break-word !important;
            overflow-wrap: break-word !important;
        }
    }
    /* 平板适配 (768px-1024px) */
    @media (min-width: 769px) and (max-width: 1024px) {
        [data-testid="stSidebar"] {
            width: 240px !important;
            min-width: 240px !important;
        }
        .block-container {
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
    }
    """
    return base_css + mobile_css
