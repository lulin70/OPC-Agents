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


# 深色主题集合：这些主题需要设置 theme.base="dark" 让 Streamlit 使用
# 深色主题的默认组件样式（sidebar 文本、tab 标签等），否则深色背景上
# 会渲染浅色主题的深色文本，导致对比度极低（ratio ≈ 1.05）。
_DARK_THEMES = {"dark", "morandi_dark", "sunset", "forest", "ocean"}


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
        "backgroundColor": "#F5F2EE",  # Morandi warm off-white
        "secondaryBackgroundColor": "#EBE5DD",  # Morandi beige deepened
        "textColor": "#3A3A3A",  # Morandi dark gray
        "font": "sans-serif",
        # Sprint 4.3 a11y: #6B7B8C 白文 ratio 4.34 < 4.5 (WCAG AA fail).
        # 深化为 #5A6A7B (ratio 5.50) 确保所有 primary 元素达标.
        "primaryColor": "#5A6A7B",  # Morandi gray-blue (deepened for WCAG AA)
    },
    "morandi_dark": {
        "backgroundColor": "#1F1B16",  # Warm dark brown
        "secondaryBackgroundColor": "#2A2520",  # Warm dark brown deepened
        "textColor": "#E8E0D5",  # Warm white
        "font": "sans-serif",
        "primaryColor": "#5A6A7B",  # Morandi gray-blue (deepened for WCAG AA)
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
        # Sprint 4.3 a11y fix: 所有深色主题必须设置 base="dark"，否则
        # Streamlit 使用 light 主题默认样式，导致 sidebar 文本、tab 标签
        # 等组件在深色背景上渲染深色文本（对比度 ≈ 1.05，几乎不可见）。
        if theme_name in _DARK_THEMES:
            st.config.set_option("theme.base", "dark")
        else:
            st.config.set_option("theme.base", "light")
    except Exception as e:
        logger.warning("[ThemeManager] Theme setting failed: %s", e)

    css = _get_theme_css(theme_name)
    if css:
        # Inject CSS on every rerun. Streamlit reruns clear previously injected
        # HTML, so CSS must be re-injected to remain effective. Using <style>
        # tag wrapper ensures browser applies the styles correctly.
        # NOTE: Previous injection_flag optimization caused CSS to disappear
        # after rerun, breaking WCAG AA contrast compliance (Sprint 4.3 fix).
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def _wcag_aa_fixes(text_color: str, secondary_bg: str) -> str:
    """生成 WCAG AA 对比度修复 CSS（>= 4.5:1）.

    Sprint 4.3 a11y remediation. 每个主题都需要这些修复，因为 Streamlit
    默认组件样式在半透明背景层叠下常导致对比度不足：
      - st.caption: 默认使用 rgba(text, 0.6) → ratio ≈ 3.36
      - st.slider thumb value: primaryColor 文本在 primaryColor 背景上 → ratio 1
      - st.metric value: primaryColor 文本在浅背景上 → ratio ≈ 2.1
      - st.button primary: 白文在 primaryColor 上 → ratio ≈ 4.34
      - st.markdown h3/h4: primaryColor 文本 → ratio ≈ 3.89
      - st.tabs label: primaryColor 文本 → ratio ≈ 3.89
      - stSidebar: theme.base 运行时不生效，sidebar 背景仍为浅色 → 深色文本
        在浅色 sidebar 上几乎不可见（ratio ≈ 1.05）

    Args:
        text_color: 主题 textColor（不透明，如 "#3A3A3A" 或 "#E8E0D5"）
        secondary_bg: 主题 secondaryBackgroundColor（不透明，如 "#EBE5DD"）
    """
    # slider thumb 背景：统一用 Morandi 灰蓝 #4A5A6B，白文 ratio 7.09
    thumb_bg = "#4A5A6B"
    thumb_text = "#FFFFFF"

    return f"""
        /* WCAG AA contrast fixes (>= 4.5:1) — Sprint 4.3 a11y remediation */
        /* theme.base 运行时不生效: stApp color 和 stSidebar bgColor 仍为 light
           主题默认值。强制覆盖确保深色主题的 sidebar 背景和文本色正确. */
        .stApp {{ color: {text_color} !important; }}
        [data-testid="stSidebar"] {{ background-color: {secondary_bg} !important; color: {text_color} !important; }}
        [data-testid="stSidebarContent"] {{ background-color: {secondary_bg} !important; color: {text_color} !important; }}
        [data-testid="stSidebarUserContent"] {{ color: {text_color} !important; }}
        /* st.caption default uses rgba(text, 0.6) → ratio 3.36; force opaque */
        [data-testid="stCaptionContainer"] {{ color: {text_color} !important; opacity: 1 !important; }}
        /* stAlert (st.info/st.warning/st.error): '未配置 LLM API Key' 等消息文本默认半透明 → ratio 3.88.
           Sprint 4.3 fix: 通配符覆盖 alert 内所有子元素，强制不透明 textColor. */
        [data-testid="stAlert"] * {{ color: {text_color} !important; opacity: 1 !important; }}
        /* st.slider: thumb value + min/max labels ('1000'/'16000'/'0.00'/'2.00') 默认半透明 → ratio 3.36.
           Sprint 4.3 fix: 通配符覆盖 slider 内所有文本子元素，强制不透明.
           注意 1: thumb value 文本必须是白色（在深色 thumb_bg 上），不能用 textColor.
           注意 2: [stSlider] span 特异性 (0,1,1) 会覆盖 [stSliderThumbValue] * (0,1,0)，
           必须用 [stSlider] [stSliderThumbValue] * (0,2,0) 确保白文优先. */
        [data-testid="stSliderThumbValue"] > div {{ background-color: {thumb_bg} !important; }}
        [data-testid="stSlider"] [data-testid="stSliderThumbValue"] * {{ color: {thumb_text} !important; opacity: 1 !important; }}
        [data-testid="stSlider"] p,
        [data-testid="stSlider"] span,
        [data-testid="stSlider"] label {{ color: {text_color} !important; opacity: 1 !important; }}
        /* st.metric: primaryColor 文本在浅背景上 → ratio ≈ 2.1; 半透明 delta → ratio 3.36.
           Sprint 4.3 fix: 通配符覆盖 metric 内所有子元素，强制不透明 textColor. */
        [data-testid="stMetric"] * {{ color: {text_color} !important; opacity: 1 !important; }}
        [data-testid="stMetricValue"],
        [data-testid="stMetricDelta"] {{ color: {text_color} !important; }}
        /* st.button primary + st.form_submit_button: white text on primaryColor → ratio 4.34;
           deepen bg to #5A6A7B (ratio 5.56). 覆盖常规 primary 和 form submit 按钮.
           Sprint 4.3 fix: Streamlit 1.58.0 form submit 按钮可能使用不同 testid，
           用 button[kind="primary"] 通配符确保所有 primary 按钮都被覆盖. */
        [data-testid="stBaseButton-primary"],
        [data-testid="stFormSubmitButton"] button[kind="primary"],
        button[kind="primary"] {{ background-color: #5A6A7B !important; border-color: #5A6A7B !important; }}
        /* st.button secondary: theme.base 不生效时默认浅色背景 (#F0EBE5)，深色主题下
           亮色文本在浅色 button 上 ratio ≈ 1.1。强制使用 secondaryBackgroundColor. */
        [data-testid="stBaseButton-secondary"] {{ background-color: {secondary_bg} !important; border-color: {secondary_bg} !important; }}
        /* st.markdown h3/h4 using primaryColor → ratio 3.89; force textColor */
        [data-testid="stMarkdownContainer"] h3,
        [data-testid="stMarkdownContainer"] h4 {{ color: {text_color} !important; }}
        /* st.tabs label: 默认使用 primaryColor → ratio ≈ 3.89; force textColor.
           覆盖选中/未选中 tab 的文字颜色，确保所有状态达标. */
        [data-testid="stTab"][role="tab"] p {{ color: {text_color} !important; }}
        [data-testid="stTab"][role="tab"][aria-selected="true"] p {{ color: {text_color} !important; }}
        /* stRadio label: theme.base 不生效时文本色仍为 light 主题默认深色 (#3A3A3A)，
           在深色 sidebar 上 ratio ≈ 1.33。强制使用主题 textColor. */
        [data-testid="stRadio"] label,
        [data-testid="stRadio"] label p,
        [data-testid="stRadio"] label div {{ color: {text_color} !important; }}
        /* stSelectbox/stMultiSelect: placeholder 'Choose options' 默认半透明 → ratio 3.21.
           Sprint 4.3 fix: 通配符覆盖 selectbox 和 multiselect 所有子元素. */
        [data-testid="stSelectbox"] *,
        [data-testid="stMultiSelect"] * {{ color: {text_color} !important; opacity: 1 !important; }}
        [data-testid="stSelectbox"] > div > div,
        [data-testid="stMultiSelect"] > div > div {{ background-color: {secondary_bg} !important; }}
        /* stExpander: theme.base 不生效时 summary 文本/背景仍为 light 主题默认值.
           Sprint 4.3 fix: Streamlit 1.58.0 的 expander summary 是 <summary> HTML 元素，
           没有 data-testid="stExpanderSummary" 属性。必须直接 targeting summary 元素.
           否则 <summary> 自带浅色背景 (#F0ECE6) 导致深色主题下 ratio ≈ 1.1. */
        [data-testid="stExpander"] {{ background-color: {secondary_bg} !important; }}
        [data-testid="stExpander"] summary,
        [data-testid="stExpanderSummary"] {{ background-color: {secondary_bg} !important; color: {text_color} !important; }}
        [data-testid="stExpander"] summary *,
        [data-testid="stExpanderSummary"] * {{ color: {text_color} !important; }}
        /* stCodeBlock: 设置页 '200MB per file' / '• ZIP' 等文本在 code block 中
           默认使用半透明色 → ratio 3.21. 强制不透明. */
        [data-testid="stCodeBlock"] code,
        [data-testid="stCodeBlock"] pre,
        [data-testid="stCodeBlock"] span {{ color: {text_color} !important; opacity: 1 !important; }}
        /* stFileUploader: 设置页 '200MB per file' help text 默认半透明 → ratio 3.21.
           Sprint 4.3 fix: 通配符覆盖 file uploader 所有子元素. */
        [data-testid="stFileUploader"] *,
        [data-testid="stFileUploaderDropzone"] *,
        [data-testid="stFileUploaderDropzoneInstructions"] * {{ color: {text_color} !important; opacity: 1 !important; }}
        /* code block operator token default #ED6F13 on light bg → ratio 2.9; deepen to #C05508.
           深色主题代码块背景已深，operator token 保持橙色但加深确保可读. */
        .token.operator {{ color: #C05508 !important; }}
        /* Sprint 4.3 fix: Streamlit :green[]/:blue[]/:orange[]/:red[]/:violet[] 彩色文本
           在 Morandi 浅色背景上对比度不足. 深化颜色确保 WCAG AA 达标 (>= 4.5:1).
           Streamlit 1.58.0 实际渲染的 RGB 值（通过 Playwright 探测得到）:
             :green[]   → rgb(21, 130, 55)   ratio 4.40 ❌ → #1A7A3C ratio 4.82 ✓
             :blue[]    → rgb(0, 84, 163)    ratio 6.92 ✓ (无需加深，仅防御未来版本变化)
             :orange[]  → rgb(226, 102, 12)  ratio 3.05 ❌ → #B04500 ratio 5.02 ✓
             :red[]     → rgb(189, 64, 67)   ratio 4.91 ✓ (无需加深)
             :violet[]  → rgb(88, 63, 132)   ratio 7.41 ✓ (无需加深)
           使用 .stMarkdownColoredText 类名（稳定）+ style 子串匹配（区分具体颜色）.
           内联样式优先级高，必须用 !important 覆盖.
           覆盖策略: 不破坏语义颜色（green=正常/blue=信息/orange=警告），只加深色调.
           维护提示: Streamlit 升级后如测试失败，用 /tmp/probe_colors.py 重新探测 RGB 值. */
        .stMarkdownColoredText[style*="21, 130, 55"] {{ color: #1A7A3C !important; }}
        .stMarkdownColoredText[style*="226, 102, 12"] {{ color: #B04500 !important; }}
        /* 兼容旧 Streamlit 版本的 RGB 值（防御性 fallback） */
        .stMarkdownColoredText[style*="28, 131, 63"] {{ color: #1A7A3C !important; }}
        .stMarkdownColoredText[style*="255, 133, 51"] {{ color: #B04500 !important; }}
    """


def _get_theme_css(theme_name: str) -> str:
    """Return custom CSS for enhanced theme support."""
    config = THEME_CONFIGS.get(theme_name, THEME_CONFIGS["light"])
    text_color = config["textColor"]
    secondary_bg = config["secondaryBackgroundColor"]

    # 通用 WCAG AA 修复（所有主题共用）
    aa_fixes = _wcag_aa_fixes(text_color, secondary_bg)

    themes = {
        "dark": f"""
            .stApp {{ background-color: #111827 !important; }}
            .stMarkdown {{ color: #F9FAFB !important; }}
            .stDataFrame {{ background-color: #1F2937 !important; }}
            [data-testid="stMetric"] {{ background-color: #1F2937 !important; }}
            [data-testid="stCheckbox"] label {{ color: #F9FAFB !important; }}
            .stSelectbox > div > div {{ background-color: #1F2937 !important; }}
            .stTextInput > div > div {{ background-color: #1F2937 !important; }}
            {aa_fixes}
            """,
        "sunset": f"""
            .stApp {{ background-color: #1a1423 !important; }}
            .stMarkdown {{ color: #fef3c7 !important; }}
            [data-testid="stMetric"] {{ background-color: #261a2e !important; }}
            {aa_fixes}
            """,
        "forest": f"""
            .stApp {{ background-color: #0d1f17 !important; }}
            .stMarkdown {{ color: #D1FAE5 !important; }}
            [data-testid="stMetric"] {{ background-color: #152920 !important; }}
            {aa_fixes}
            """,
        "ocean": f"""
            .stApp {{ background-color: #0c1929 !important; }}
            .stMarkdown {{ color: #E0F2FE !important; }}
            [data-testid="stMetric"] {{ background-color: #162d4a !important; }}
            {aa_fixes}
            """,
        # Morandi Dark theme — aligned with UI_DESIGN_v0.5.1.md §3.3
        "morandi_dark": f"""
            /* morandi_dark theme — warm dark brown palette (#1F1B16 bg + #E8E0D5 text) */
            .stApp {{ background-color: #1F1B16 !important; }}
            .stMarkdown {{ color: #E8E0D5 !important; }}
            .stDataFrame {{ background-color: #2A2520 !important; }}
            [data-testid="stMetric"] {{ background-color: #2A2520 !important; }}
            [data-testid="stCheckbox"] label {{ color: #E8E0D5 !important; }}
            .stSelectbox > div > div {{ background-color: #2A2520 !important; color: #E8E0D5 !important; }}
            .stTextInput > div > div {{ background-color: #2A2520 !important; color: #E8E0D5 !important; }}
            .stTextArea > div > div {{ background-color: #2A2520 !important; color: #E8E0D5 !important; }}
            /* Morandi semantic colors preserved for brand recognition */
            .stSuccess {{ border-left: 3px solid #8FAB8B !important; }}
            .stWarning {{ border-left: 3px solid #D9BC85 !important; }}
            .stError {{ border-left: 3px solid #C89595 !important; }}
            .stInfo {{ border-left: 3px solid #9AAEC0 !important; }}
            {aa_fixes}
            """,
        # Morandi Light theme — warm Morandi palette
        "morandi_light": f"""
            .stApp {{ background-color: #F5F2EE !important; }}
            .stMarkdown {{ color: #3A3A3A !important; }}
            .stDataFrame {{ background-color: #EBE5DD !important; }}
            [data-testid="stMetric"] {{ background-color: #EBE5DD !important; }}
            [data-testid="stCheckbox"] label {{ color: #3A3A3A !important; }}
            .stSelectbox > div > div {{ background-color: #EBE5DD !important; color: #3A3A3A !important; }}
            .stTextInput > div > div {{ background-color: #EBE5DD !important; color: #3A3A3A !important; }}
            .stTextArea > div > div {{ background-color: #EBE5DD !important; color: #3A3A3A !important; }}
            /* Morandi semantic colors preserved for brand recognition */
            .stSuccess {{ border-left: 3px solid #7A9B76 !important; }}
            .stWarning {{ border-left: 3px solid #C9A96E !important; }}
            .stError {{ border-left: 3px solid #B07C7C !important; }}
            .stInfo {{ border-left: 3px solid #7B8FA1 !important; }}
            {aa_fixes}
            """,
        # Light theme (legacy)
        "light": aa_fixes,
    }
    base_css = themes.get(theme_name, aa_fixes)

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
