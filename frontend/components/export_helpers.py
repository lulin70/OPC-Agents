"""Export helper functions for OPC-Agents frontend.

Provides export-related utilities extracted from shared.py for modularity:
- _get_export_bytes: Safe export with error handling
- _do_get_export_bytes: Core export logic
- _get_mime_type: MIME type lookup by file extension
- _render_batch_export_section: Batch export UI
- _execute_batch_export: Batch export execution
- _render_single_export_buttons: Single item export buttons
- _render_export_preview: Export preview dialog
- _export_single_with_preview: Export with preview flow
- _export_single: Single item export
- _render_export_buttons: Generic export button row
"""

import streamlit as st
import os
import logging

from opc_manager.i18n import t as _t
from opc_manager.error_handler import ErrorHandler, UserFriendlyError

logger = logging.getLogger(__name__)

MIME_MAP = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "png": "image/png",
    "html": "text/html",
    "md": "text/markdown",
    "txt": "text/plain",
    "csv": "text/csv",
    "json": "application/json",
}

EXT_MAP = {
    "pdf": "pdf",
    "docx": "docx",
    "xlsx": "xlsx",
    "png": "png",
    "html": "html",
    "md": "md",
    "txt": "txt",
    "csv": "csv",
    "json": "json",
}

__all__ = [
    "_get_export_bytes",
    "_do_get_export_bytes",
    "_get_mime_type",
    "_render_batch_export_section",
    "_execute_batch_export",
    "_render_single_export_buttons",
    "_render_export_preview",
    "_export_single_with_preview",
    "_export_single",
    "_render_export_buttons",
]


def _get_export_bytes(content: str, fmt: str) -> tuple:
    try:
        return ErrorHandler.safe_execute(
            _do_get_export_bytes,
            content,
            fmt,
            context=_t("export_fmt_context", fmt=fmt),
        )
    except UserFriendlyError as e:
        logger.warning(
            "[frontend] %s: %s", _t("export_failed_log", fmt=fmt), e.user_message
        )
        return None, None, None


def _do_get_export_bytes(content: str, fmt: str) -> tuple:
    from opc_manager.export import ExportManager
    from opc_manager.export.models import ResultData, ExportFormat

    # Check if WeasyPrint is available for PDF export
    actual_fmt = fmt
    if fmt == "pdf":
        try:
            import weasyprint  # noqa: F401
        except ImportError:
            actual_fmt = "html"
            import streamlit as st

            st.info("PDF 导出需要 WeasyPrint，当前已降级为 HTML 格式导出")

    manager = ExportManager()
    format_enum = ExportFormat(actual_fmt)
    data = ResultData(content=content, metadata={"title": "Export"})
    file_bytes = manager.export_sync(data, format_enum)
    return (
        file_bytes,
        MIME_MAP.get(actual_fmt, "application/octet-stream"),
        EXT_MAP.get(actual_fmt, "bin"),
    )


def _get_mime_type(filepath: str) -> str:
    """根据文件扩展名获取MIME类型"""
    ext = os.path.splitext(filepath)[1].lower().lstrip(".")
    return MIME_MAP.get(ext, "application/octet-stream")


def _render_batch_export_section(DELIVERABLES_DIR):
    st.markdown(f"### 📤 {_t('export_batch_title')}")

    col_fmt, col_btn = st.columns([3, 1])
    with col_fmt:
        export_format = st.selectbox(
            _t("export_select_format"),
            options=[
                _t("export_pdf_pack"),
                _t("export_word_pack"),
                _t("export_excel"),
                _t("export_md_archive"),
            ],
            help=_t("export_format_help"),
        )
    with col_btn:
        if st.button(_t("export_batch_btn"), type="primary", use_container_width=True):
            _execute_batch_export(export_format, DELIVERABLES_DIR)


def _execute_batch_export(format_name: str, DELIVERABLES_DIR):
    from opc_manager.export.manager import ExportManager
    from opc_manager.export.models import ResultData, ExportFormat

    em = ExportManager()

    progress_bar = st.progress(0, text=_t("export_preparing"))

    deliverables = st.session_state.get("deliverables", [])

    if not deliverables:
        st.warning(_t("export_no_deliverables"))
        return

    fmt_map = {
        _t("export_pdf_pack"): ExportFormat.PDF,
        _t("export_word_pack"): ExportFormat.WORD,
        _t("export_excel"): ExportFormat.EXCEL,
        _t("export_md_archive"): ExportFormat.MARKDOWN,
    }

    target_fmt = fmt_map.get(format_name, ExportFormat.MARKDOWN)
    results = []

    for i, item in enumerate(deliverables):
        progress = int((i + 1) / len(deliverables) * 100)
        progress_bar.progress(
            progress, text=_t("export_progress", current=i + 1, total=len(deliverables))
        )

        try:
            filepath = item.get("filepath", "")
            if not filepath or not os.path.exists(filepath):
                continue

            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            rd = ResultData(
                content=content,
                metadata=item.get("metadata", item.get("meta", {})),
                attachments=item.get("attachments", []),
            )
            file_bytes = em.export_sync(rd, target_fmt)

            if file_bytes:
                ext = target_fmt.value
                output_filename = f"batch_{os.path.splitext(item.get('filename', f'item_{i}'))[0]}.{ext}"
                output_path = os.path.join(
                    DELIVERABLES_DIR, f"batch_export_{output_filename}"
                )
                with open(output_path, "wb") as f:
                    f.write(file_bytes)
                results.append(output_path)
        except Exception as e:
            st.warning(_t("export_item_failed", index=i + 1, error=e))

    progress_bar.progress(100, text=_t("export_complete"))

    if results:
        st.success(_t("export_success_count", count=len(results)))
        for fp in results:
            if os.path.exists(fp):
                with open(fp, "rb") as f:
                    st.download_button(
                        label=f"⬇️ {_t('download')} {os.path.basename(fp)}",
                        data=f,
                        file_name=os.path.basename(fp),
                        mime=_get_mime_type(fp),
                        key=f"dl_{fp}",
                    )


def _render_single_export_buttons(item: dict, item_id: str):
    col_pdf, col_word, col_excel, col_png = st.columns(4)
    with col_pdf:
        if st.button(
            "📄 PDF", key=f"pdf_{item_id}", help=_t("export_as_format", fmt="PDF")
        ):
            _export_single_with_preview(item, "pdf", item_id)
    with col_word:
        if st.button(
            "📝 Word", key=f"word_{item_id}", help=_t("export_as_format", fmt="Word")
        ):
            _export_single_with_preview(item, "word", item_id)
    with col_excel:
        if st.button(
            "📊 Excel", key=f"excel_{item_id}", help=_t("export_as_format", fmt="Excel")
        ):
            _export_single_with_preview(item, "excel", item_id)
    with col_png:
        if st.button("🖼️ 图片", key=f"png_{item_id}", help=_t("export_as_png")):
            _export_single_with_preview(item, "png", item_id)


def _render_export_preview(item_data: dict, format_type: str, item_id: str = ""):
    st.subheader(_t("export_preview_title"))

    col_info, col_preview = st.columns([1, 2])
    with col_info:
        st.markdown(f"**{_t('format')}**: `{format_type.upper()}`")
        content_str = str(item_data) if not isinstance(item_data, str) else item_data
        size_kb = len(content_str.encode("utf-8")) // 1024
        st.markdown(f"**{_t('size')}**: ~{size_kb} KB ({_t('size_estimated')})")
        keys = list(item_data.keys()) if isinstance(item_data, dict) else []
        st.markdown(
            f"**{_t('included_fields')}**: {', '.join(keys[:5])}{'...' if len(keys) > 5 else ''}"
            if keys
            else f"**{_t('content_type')}**: {_t('text_type')}"
        )

        format_hints = {
            "pdf": "📄 PDF {_t('format_pdf_desc')}",
            "word": "📝 Word {_t('format_word_desc')}",
            "excel": "📊 Excel {_t('format_excel_desc')}",
            "image": "🖼️ PNG {_t('format_png_desc')}",
            "png": "🖼️ PNG {_t('format_png_desc')}",
        }
        st.caption(
            format_hints.get(
                format_type.lower(), _t("export_as_format2", fmt=format_type.upper())
            )
        )

    with col_preview:
        content_preview = str(item_data)[:500] + (
            "..." if len(str(item_data)) > 500 else ""
        )
        st.text_area(
            _t("content_preview"), value=content_preview, height=200, disabled=True
        )

    preview_key = f"preview_{format_type}_{item_id}"
    col_confirm, col_cancel = st.columns([1, 1])
    with col_confirm:
        if st.button(
            "✅ " + _t("confirm_export"),
            type="primary",
            key=f"confirm_export_{format_type}_{item_id}",
        ):
            st.session_state[f"preview_confirmed_{format_type}_{item_id}"] = True
    with col_cancel:
        if st.button(_t("cancel"), key=f"cancel_export_{format_type}_{item_id}"):
            st.session_state[f"preview_confirmed_{format_type}_{item_id}"] = False


def _export_single_with_preview(item: dict, fmt: str, item_id: str):
    filepath = item.get("filepath", "")
    if not filepath or not os.path.exists(filepath):
        st.error(_t("file_not_exists"))
        return

    confirm_key = f"preview_confirmed_{fmt}_{item_id}"
    if st.session_state.get(confirm_key, False):
        st.session_state[confirm_key] = False
        _export_single(item, fmt)
        return

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        item_data = {
            "content": content[:2000],
            "filename": item.get("filename", ""),
            "metadata": item.get("metadata", item.get("meta", {})),
        }

        _render_export_preview(item_data, fmt, item_id)

        if st.session_state.get(confirm_key) is False:
            st.session_state[confirm_key] = None
            st.info(_t("export_cancelled"))
    except Exception as e:
        st.error(_t("preview_failed", error=e))


def _export_single(item: dict, fmt: str):
    from opc_manager.export.manager import ExportManager
    from opc_manager.export.models import ResultData, ExportFormat

    filepath = item.get("filepath", "")
    if not filepath or not os.path.exists(filepath):
        st.error(_t("file_not_exists"))
        return

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        em = ExportManager()
        fmt_map = {
            "pdf": ExportFormat.PDF,
            "word": ExportFormat.WORD,
            "excel": ExportFormat.EXCEL,
            "png": ExportFormat.IMAGE,
        }
        target_fmt = fmt_map.get(fmt, ExportFormat.MARKDOWN)

        rd = ResultData(
            content=content,
            metadata=item.get("metadata", item.get("meta", {})),
            attachments=item.get("attachments", []),
        )
        file_bytes = em.export_sync(rd, target_fmt)

        if file_bytes:
            ext = target_fmt.value
            filename = f"{os.path.splitext(item.get('filename', 'export'))[0]}.{ext}"
            st.download_button(
                label=f"⬇️ {_t('download')} {filename}",
                data=file_bytes,
                file_name=filename,
                mime=_get_mime_type(f".{ext}"),
                key=f"dl_single_{fmt}_{item.get('id', id(item))}",
            )
        else:
            st.warning(_t("export_format_failed", fmt=fmt.upper()))
    except Exception as e:
        st.error(_t("export_failed", error=e))


def _render_export_buttons(content: str, formats: list, key_prefix: str):
    if not formats:
        return
    FORMAT_LABELS = {
        "pdf": "📄 PDF",
        "docx": "📝 Word",
        "xlsx": "📊 Excel",
        "png": "🖼️ 图片",
        "html": "🌐 HTML",
        "md": "📑 Markdown",
    }
    st.markdown(f"**{_t('export_as_other_formats')}:**")
    btn_cols = st.columns(min(len(formats), 4))
    for i, fmt in enumerate(formats):
        label = FORMAT_LABELS.get(fmt, fmt.upper())
        with btn_cols[i % len(btn_cols)]:
            file_bytes, mime, ext = _get_export_bytes(content, fmt)
            if file_bytes:
                st.download_button(
                    label=label,
                    data=file_bytes,
                    file_name=f"export_{key_prefix}.{ext}",
                    mime=mime,
                    key=f"export_{fmt}_{key_prefix}",
                    use_container_width=True,
                )
            else:
                st.button(
                    label,
                    key=f"export_fail_{fmt}_{key_prefix}",
                    disabled=True,
                    help="导出依赖未安装",
                )
