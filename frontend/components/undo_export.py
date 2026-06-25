"""Undo export functionality for OPC-Agents frontend.

Provides export capabilities for undo history, extracted from undo_panel.py:
- _render_export_options: Export format selection dialog
- _generate_csv: CSV formatted export
- _generate_json: JSON formatted export
"""

import json
import csv
import io
import logging
from datetime import datetime
from typing import List

from frontend.components.undo_display import UndoRecordDisplay

logger = logging.getLogger(__name__)

__all__ = [
    "_render_export_options",
    "_generate_csv",
    "_generate_json",
]


def _render_export_options(records: List[UndoRecordDisplay]):
    """Render export format selection dialog.

    Args:
        records: List of records to export
    """
    import streamlit as st

    st.markdown("####  导出撤销历史")

    format_option = st.radio(
        "选择导出格式",
        options=["CSV表格", "JSON数据"],
        horizontal=True,
        key="undo_export_format",
    )

    if format_option == "CSV表格":
        csv_data = _generate_csv(records)
        st.download_button(
            label="️ 下载 CSV 文件",
            data=csv_data,
            file_name=f"undo_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            key="download_undo_csv",
            use_container_width=True,
            type="primary",
        )
    else:
        json_data = _generate_json(records)
        st.download_button(
            label="️ 下载 JSON 文件",
            data=json_data,
            file_name=f"undo_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            key="download_undo_json",
            use_container_width=True,
            type="primary",
        )


def _generate_csv(records: List[UndoRecordDisplay]) -> str:
    """Generate CSV formatted string from records.

    Args:
        records: List of UndoRecordDisplay objects

    Returns:
        CSV formatted string
    """
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(
        [
            "操作ID",
            "操作类型",
            "描述",
            "状态",
            "创建时间",
            "过期时间",
            "剩余秒数",
            "逆函数名",
        ]
    )

    for r in records:
        created_str = (
            datetime.fromtimestamp(r.created_at).strftime("%Y-%m-%d %H:%M:%S")
            if r.created_at > 0
            else "N/A"
        )
        expires_str = (
            datetime.fromtimestamp(r.expires_at).strftime("%Y-%m-%d %H:%M:%S")
            if r.expires_at > 0
            else "N/A"
        )

        writer.writerow(
            [
                r.operation_id,
                r.operation_type,
                r.description,
                r.status,
                created_str,
                expires_str,
                r.remaining_seconds,
                r.inverse_func_name,
            ]
        )

    return output.getvalue()


def _generate_json(records: List[UndoRecordDisplay]) -> str:
    """Generate JSON formatted string from records.

    Args:
        records: List of UndoRecordDisplay objects

    Returns:
        JSON formatted string
    """
    export_data = []

    for r in records:
        export_data.append(
            {
                "operation_id": r.operation_id,
                "operation_type": r.operation_type,
                "description": r.description,
                "status": r.status,
                "created_at": (
                    datetime.fromtimestamp(r.created_at).isoformat()
                    if r.created_at > 0
                    else "N/A"
                ),
                "expires_at": (
                    datetime.fromtimestamp(r.expires_at).isoformat()
                    if r.expires_at > 0
                    else "N/A"
                ),
                "remaining_seconds": r.remaining_seconds,
                "time_ago": r.time_ago,
                "inverse_func_name": r.inverse_func_name,
                "inverse_args": r.inverse_args,
                "original_result_summary": str(r.original_result)[:200],
            }
        )

    return json.dumps(export_data, ensure_ascii=False, indent=2)
