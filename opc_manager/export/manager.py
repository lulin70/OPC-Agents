import asyncio
import os
import threading
from typing import Optional, Dict

from .models import ResultData, ExportFormat, SKILL_EXPORT_CAPABILITIES


class MarkdownExporter:
    """Simple pass-through exporter that returns content as UTF-8 bytes."""

    def export(self, data, template=None, **opts) -> bytes:
        return data.content.encode("utf-8")


class ExportManager:
    _instance = None
    _lock = threading.Lock()
    _exporters: Dict[ExportFormat, object] = {}

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._register_builtin_exporters()
        return cls._instance

    def __init__(self):
        pass

    def register_exporter(self, format: ExportFormat, exporter):
        self._exporters[format] = exporter

    def get_supported_formats(self, skill_id: str) -> list:
        caps = SKILL_EXPORT_CAPABILITIES.get(skill_id)
        if caps is None:
            # Unknown skill_id: return all registered formats as fallback
            return list(self._exporters.keys())
        return [f for f in caps if f in self._exporters]

    def can_export(self, skill_id: str, fmt: ExportFormat) -> bool:
        return fmt in self.get_supported_formats(skill_id)

    def export_sync(
        self,
        data: ResultData,
        fmt: ExportFormat,
        template_id: Optional[str] = None,
        **opts,
    ) -> bytes:
        exporter = self._exporters.get(fmt)
        if not exporter:
            raise ValueError(f"Unsupported format: {fmt}")
        template = self._load_template(template_id, fmt) if template_id else None
        return exporter.export(data, template=template, **opts)

    async def export_async(
        self,
        data: ResultData,
        fmt: ExportFormat,
        template_id: Optional[str] = None,
        **opts,
    ) -> bytes:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self.export_sync, data, fmt, template_id, opts
        )

    def _load_template(self, template_id: str, fmt: ExportFormat) -> str:
        safe_template_id = os.path.basename(template_id)
        template_dir = os.path.join(
            os.path.dirname(__file__), "..", "data", "templates", fmt.value
        )
        path = os.path.join(template_dir, f"{safe_template_id}.j2")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def _register_builtin_exporters(self):
        from .exporters.pdf_exporter import PDFExporter
        from .exporters.excel_exporter import ExcelExporter
        from .exporters.word_exporter import WordExporter
        from .exporters.image_exporter import ImageExporter

        self.register_exporter(ExportFormat.MARKDOWN, MarkdownExporter())
        self.register_exporter(ExportFormat.PDF, PDFExporter())
        self.register_exporter(ExportFormat.EXCEL, ExcelExporter())
        self.register_exporter(ExportFormat.WORD, WordExporter())
        self.register_exporter(ExportFormat.IMAGE, ImageExporter())
