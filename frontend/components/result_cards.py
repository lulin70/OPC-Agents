"""结构化结果卡片展示系统

将纯文本输出替换为视觉化的卡片组件，支持不同任务类型的差异化展示。
包含内容预览、元数据显示、操作按钮组等增强功能。
"""

import streamlit as st
import os
import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from opc_manager.i18n import t as _t

logger = logging.getLogger(__name__)

TASK_TYPE_CONFIG = {
    "content_generation": {
        "icon": "",
        "title": _t("rc_title_content_gen"),
        "gradient_start": "#667eea",
        "gradient_end": "#764ba2",
        "bg_color": "#f8f7ff",
    },
    "data_analysis": {
        "icon": "",
        "title": _t("rc_title_data_analysis"),
        "gradient_start": "#11998e",
        "gradient_end": "#38ef7d",
        "bg_color": "#f0fdf9",
    },
    "info_collection": {
        "icon": "",
        "title": _t("rc_title_info_collection"),
        "gradient_start": "#f093fb",
        "gradient_end": "#f5576c",
        "bg_color": "#fff7ed",
    },
    "scenario_based": {
        "icon": "",
        "title": _t("rc_title_scenario"),
        "gradient_start": "#fa709a",
        "gradient_end": "#fee140",
        "bg_color": "#fdf4ff",
    },
    "general_chat": {
        "icon": "",
        "title": _t("rc_title_general_chat"),
        "gradient_start": "#a8edea",
        "gradient_end": "#fed6e3",
        "bg_color": "#f8fafc",
    },
}


def render_result_card(
    content: str,
    task_type: Optional[str] = None,
    deliverable_record: Optional[Dict[str, Any]] = None,
    filepath: Optional[str] = None,
) -> None:
    """主渲染函数：根据task_type渲染不同风格的卡片

    Args:
        content: 任务结果内容（Markdown格式）
        task_type: 任务类型（TaskType枚举值）
        deliverable_record: 成果物记录字典，包含prompt, task_type, created_at, metadata等
        filepath: 成果物文件路径

    Usage:
        render_result_card(
            content=result_content,
            task_type="content_generation",
            deliverable_record=record,
            filepath="/path/to/file.md"
        )
    """
    if not content:
        st.warning(_t("rc_no_content"))
        return

    task_type = task_type or "general_chat"
    config = TASK_TYPE_CONFIG.get(task_type, TASK_TYPE_CONFIG["general_chat"])

    st.markdown(
        f"""
    <style>
    .result-card {{
        background: white;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        overflow: hidden;
        margin: 16px 0;
        border: 1px solid #e5e7eb;
    }}
    .card-header {{
        background: linear-gradient(135deg, {config['gradient_start']}, {config['gradient_end']});
        color: white;
        padding: 20px 24px;
        font-size: 18px;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 10px;
    }}
    .card-body {{
        padding: 20px 24px;
        background: {config['bg_color']};
    }}
    .metadata-bar {{
        display: flex;
        gap: 20px;
        flex-wrap: wrap;
        padding: 12px 16px;
        background: #f9fafb;
        border-radius: 8px;
        margin: 16px 0;
        font-size: 14px;
        color: #6b7280;
    }}
    .metadata-item {{
        display: flex;
        align-items: center;
        gap: 6px;
    }}
    .action-buttons {{
        display: flex;
        gap: 12px;
        margin-top: 16px;
        flex-wrap: wrap;
    }}
    .btn-primary {{
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        padding: 10px 20px;
        border: none;
        border-radius: 8px;
        cursor: pointer;
        font-weight: 500;
        transition: all 0.3s ease;
    }}
    .btn-primary:hover {{
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }}
    .btn-secondary {{
        background: white;
        color: #374151;
        padding: 10px 20px;
        border: 1px solid #d1d5db;
        border-radius: 8px;
        cursor: pointer;
        font-weight: 500;
        transition: all 0.3s ease;
    }}
    .btn-secondary:hover {{
        background: #f9fafb;
        border-color: #9ca3af;
    }}
    @media (max-width: 768px) {{
        .metadata-bar {{
            flex-direction: column;
            gap: 8px;
        }}
        .action-buttons {{
            flex-direction: column;
        }}
        .btn-primary, .btn-secondary {{
            width: 100%;
            text-align: center;
        }}
    }}
    </style>
    """,
        unsafe_allow_html=True,
    )

    with st.container():
        _render_card_header(task_type, config)

        with st.container():
            if task_type == "data_analysis":
                insights = _extract_data_insights(content)
                if insights:
                    st.markdown(_t("rc_key_insights"))
                    for insight in insights[:5]:
                        st.markdown(f"- {insight}")
                    st.divider()

            _render_content_preview(content, max_chars=200)

            metadata = (
                (deliverable_record or {}).get("meta", {}) if deliverable_record else {}
            )
            if metadata or deliverable_record:
                _render_metadata_bar(metadata, deliverable_record)

            if task_type != "general_chat" and filepath:
                formats = ["pdf", "docx", "xlsx"]
                _render_action_buttons(filepath, content, formats)

        # Always close card-body and result-card divs
        st.markdown("</div></div>", unsafe_allow_html=True)


def _render_card_header(task_type: str, config: Dict[str, str]) -> None:
    """渲染卡片头部区域

    Args:
        task_type: 当前任务类型
        config: 该任务类型的配置（图标、标题、颜色）
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    st.markdown(
        f"""
    <div class="result-card">
        <div class="card-header">
            <span style="font-size: 24px;">{config['icon']}</span>
            <span>{config['title']}</span>
            <span style="margin-left: auto; font-size: 14px; opacity: 0.9;">
                 {timestamp}
            </span>
        </div>
        <div class="card-body">
    """,
        unsafe_allow_html=True,
    )


def _render_metadata_bar(
    metadata: Dict[str, Any],
    deliverable_record: Optional[Dict[str, Any]] = None,
) -> None:
    """渲染元数据栏：使用st.columns()横向排列关键指标

    Args:
        metadata: 元数据字典（来自deliverable_record.meta）
        deliverable_record: 完整的成果物记录
    """
    items = []

    execution_time = metadata.get("execution_time_ms")
    if execution_time:
        time_sec = round(execution_time / 1000, 1)
        items.append(("", _t("rc_time_cost", sec=time_sec)))

    sources_count = metadata.get("sources_count")
    if sources_count:
        items.append(("", _t("rc_sources_count", count=sources_count)))

    file_format = metadata.get("format") or (deliverable_record or {}).get("task_type")
    if file_format:
        format_labels = {
            "content_generation": "Markdown",
            "data_analysis": _t("rc_format_analysis"),
            "info_collection": _t("rc_format_research"),
            "scenario_based": _t("rc_format_workflow"),
        }
        fmt_display = format_labels.get(file_format, file_format.capitalize())
        items.append(("", _t("rc_format_label", fmt=fmt_display)))

    size_kb = (deliverable_record or {}).get("size_kb")
    if size_kb:
        items.append(("", _t("rc_size_label", size=size_kb)))

    agent_loop = metadata.get("agent_loop")
    if agent_loop:
        items.append(("", _t("rc_ai_enhanced")))

    if not items:
        return

    num_cols = min(len(items), 4)
    cols = st.columns(num_cols)

    for i, (icon, text) in enumerate(items):
        with cols[i % num_cols]:
            st.markdown(
                f"""
            <div class="metadata-bar" style="padding: 8px 12px;">
                <div class="metadata-item">
                    <span>{icon}</span>
                    <span>{text}</span>
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )


def _render_action_buttons(
    filepath: str,
    content: str,
    formats: List[str],
) -> None:
    """渲染操作按钮组：下载、导出、复制

    Args:
        filepath: 成果物文件路径
        content: 文件内容
        formats: 支持的导出格式列表
    """
    try:
        cols = st.columns([2, 1])
        col_download, col_copy = cols[0], cols[1]
    except (ValueError, IndexError, TypeError):
        col_download = st
        col_copy = st

    with col_download:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                file_content = f.read()

            st.download_button(
                label=_t("rc_download_deliverable"),
                data=file_content,
                file_name=os.path.basename(filepath),
                mime="text/markdown",
                type="primary",
                use_container_width=True,
                key=f"dl_main_{hash(filepath)}",
            )
        else:
            st.button(
                _t("rc_download_deliverable"),
                disabled=True,
                help=_t("rc_file_not_exist"),
            )

    with col_copy:
        if st.button(
            _t("rc_copy_content"),
            key=f"copy_{hash(filepath)}",
            use_container_width=True,
        ):
            st.session_state[f"clipboard_{hash(filepath)}"] = content
            st.success(_t("rc_copied"))
            st.toast("已复制", icon="")

    if formats:
        st.markdown(_t("rc_other_formats"))
        try:
            btn_cols = st.columns(min(len(formats), 3))
            has_columns = len(btn_cols) > 0
        except (ValueError, TypeError, AttributeError):
            btn_cols = [st] * min(len(formats), 3)
            has_columns = True

        FORMAT_LABELS = {
            "pdf": " PDF",
            "docx": " Word",
            "xlsx": " Excel",
        }

        for i, fmt in enumerate(formats):
            label = FORMAT_LABELS.get(fmt, fmt.upper())
            if has_columns and len(btn_cols) > 0:
                with btn_cols[i % max(len(btn_cols), 1)]:
                    if st.button(
                        label,
                        key=f"export_{fmt}_{hash(filepath)}",
                        use_container_width=True,
                    ):
                        try:
                            from frontend.components.shared import _get_export_bytes

                            file_bytes, mime, ext = _get_export_bytes(content, fmt)
                            if file_bytes:
                                st.download_button(
                                    label=_t("rc_download_label", label=label),
                                    data=file_bytes,
                                    file_name=f"export_{ext}",
                                    mime=mime,
                                    key=f"dl_fmt_{fmt}_{hash(filepath)}",
                                )
                            else:
                                st.warning(_t("rc_export_failed", fmt=fmt.upper()))
                        except Exception as e:
                            logger.error("[result_cards] 导出失败: %s", e)
                            st.error(_t("rc_export_error", error=str(e)))
            else:
                st.button(
                    label,
                    key=f"export_{fmt}_{hash(filepath)}",
                    use_container_width=True,
                )


def _render_content_preview(content: str, max_chars: int = 200) -> None:
    """渲染内容预览区：截断长内容并提供展开/收起功能

    Args:
        content: 完整内容文本
        max_chars: 预览区最大字符数
    """
    if len(content) <= max_chars:
        st.markdown(content)
        return

    preview_key = f"expand_{hash(content[:50])}"
    is_expanded = st.session_state.get(preview_key, False)

    if not is_expanded:
        truncated = content[:max_chars] + "..."
        st.markdown(truncated)

        if st.button(
            _t("rc_expand_all"),
            key=f"btn_expand_{preview_key}",
            use_container_width=True,
        ):
            st.session_state[preview_key] = True
            st.rerun()
    else:
        st.markdown(content)

        if st.button(
            _t("rc_collapse"),
            key=f"btn_collapse_{preview_key}",
            use_container_width=True,
        ):
            st.session_state[preview_key] = False
            st.rerun()


def _extract_data_insights(content: str) -> List[str]:
    """从内容中提取数据洞察（数字、百分比、趋势词）

    使用正则表达式匹配常见的数据模式：
    - 百分比：XX.X% 或 XX%
    - 数字：金额、数量、时间等
    - 趋势词：增长、下降、上升等

    Args:
        content: 要分析的内容文本

    Returns:
        提取到的洞察列表
    """
    insights = []

    percentage_pattern = r"(\d+(?:\.\d+)?%)"
    percentages = re.findall(percentage_pattern, content)
    if percentages:
        insights.append(
            _t(
                "rc_found_pct_points",
                count=len(percentages),
                items=", ".join(percentages[:5]),
            )
        )

    number_patterns = [
        (r"(\d+(?:\.\d+)?\s*(?:万|亿|元|美元|欧元|人民币))", _t("rc_amount_data")),
        (r"(\d+(?:\,\d{3})*(?:\.\d+)?)\s*(?:人|次|个|项|家)", _t("rc_quantity_data")),
        (r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})", _t("rc_date_data")),
    ]

    for pattern, label in number_patterns:
        matches = re.findall(pattern, content)
        if matches and len(insights) < 5:
            insights.append(
                _t(
                    "rc_data_label",
                    label=label,
                    match=matches[0],
                    suffix=" 等" if len(matches) > 1 else "",
                )
            )

    trend_words = [
        "增长",
        "下降",
        "上升",
        "下滑",
        "提升",
        "降低",
        "增加",
        "减少",
        "涨幅",
        "跌幅",
    ]
    found_trends = [word for word in trend_words if word in content]
    if found_trends:
        insights.append(_t("rc_trend_keywords", words=", ".join(found_trends[:4])))

    return insights


def get_task_type_label(task_type: str) -> str:
    """获取任务类型的中文名称标签

    Args:
        task_type: 任务类型字符串

    Returns:
        中文标签
    """
    labels = {
        "content_generation": _t("rc_task_type_content_gen"),
        "data_analysis": _t("rc_task_type_data_analysis"),
        "info_collection": _t("rc_task_type_info_collection"),
        "scenario_based": _t("rc_task_type_scenario"),
        "general_chat": _t("rc_task_type_general_chat"),
        "business_operation": _t("rc_task_type_business_op"),
    }
    return labels.get(task_type, f" {task_type}")


def validate_deliverable_record(record: Dict[str, Any]) -> Tuple[bool, str]:
    """验证deliverable_record的完整性和有效性

    Args:
        record: 待验证的成果物记录

    Returns:
        (是否有效, 错误消息)
    """
    required_fields = ["filename", "filepath", "prompt", "task_type", "created_at"]

    missing = [field for field in required_fields if field not in record]
    if missing:
        return False, _t("rc_missing_fields", fields=", ".join(missing))

    if not record.get("filepath") or not os.path.exists(record["filepath"]):
        return False, _t("rc_file_not_found", path=record.get("filepath", ""))

    if not record.get("task_type"):
        return False, _t("rc_task_type_empty")

    return True, ""
