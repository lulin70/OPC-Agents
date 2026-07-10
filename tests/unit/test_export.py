"""
Export 模块单元测试

覆盖 ExportManager / MarkdownExporter / PDFExporter / WordExporter / ExcelExporter
以及 ResultData / ExportFormat / SKILL_EXPORT_CAPABILITIES 数据模型
"""

import pytest

from opc_manager.export import (
    ExportManager,
    ExportFormat,
    ResultData,
    SKILL_EXPORT_CAPABILITIES,
)
from opc_manager.export.manager import MarkdownExporter
from opc_manager.export.exporters.pdf_exporter import PDFExporter
from opc_manager.export.exporters.word_exporter import WordExporter
from opc_manager.export.exporters.excel_exporter import ExcelExporter


class TestResultData:
    """ResultData 数据模型测试"""

    def test_creation_with_defaults(self):
        data = ResultData(content="# Hello")
        assert data.content == "# Hello"
        assert data.metadata == {}
        assert data.attachments is None

    def test_creation_with_metadata(self):
        data = ResultData(content="test", metadata={"title": "Report"})
        assert data.metadata["title"] == "Report"

    def test_creation_with_attachments(self):
        data = ResultData(content="test", attachments=[b"img1", b"img2"])
        assert len(data.attachments) == 2


class TestExportFormat:
    """ExportFormat 枚举测试"""

    def test_format_values(self):
        assert ExportFormat.MARKDOWN.value == "md"
        assert ExportFormat.PDF.value == "pdf"
        assert ExportFormat.WORD.value == "docx"
        assert ExportFormat.EXCEL.value == "xlsx"
        assert ExportFormat.IMAGE.value == "png"
        assert ExportFormat.HTML.value == "html"

    def test_skill_export_capabilities(self):
        assert ExportFormat.PDF in SKILL_EXPORT_CAPABILITIES["report_skill"]
        assert ExportFormat.MARKDOWN in SKILL_EXPORT_CAPABILITIES["email_skill"]
        assert ExportFormat.EXCEL in SKILL_EXPORT_CAPABILITIES["finance_skill"]


class TestMarkdownExporter:
    """MarkdownExporter 测试"""

    def test_export_returns_utf8_bytes(self):
        exporter = MarkdownExporter()
        data = ResultData(content="# Hello World")
        result = exporter.export(data)
        assert isinstance(result, bytes)
        assert result == "# Hello World".encode("utf-8")

    def test_export_with_multiline_content(self):
        exporter = MarkdownExporter()
        content = "# Title\n\nParagraph text\n- item 1\n- item 2"
        data = ResultData(content=content)
        result = exporter.export(data)
        assert content.encode("utf-8") == result


class TestPDFExporter:
    """PDFExporter 测试

    WeasyPrint 在 CI 环境可能未安装，测试覆盖 fallback 路径和 HTML 转换逻辑
    """

    def test_simple_md_to_html_headings(self):
        exporter = PDFExporter()
        html = exporter._simple_md_to_html("# Title\n## Subtitle\n### Section")
        assert "<h1>Title</h1>" in html
        assert "<h2>Subtitle</h2>" in html
        assert "<h3>Section</h3>" in html

    def test_simple_md_to_html_paragraph(self):
        exporter = PDFExporter()
        html = exporter._simple_md_to_html("Hello paragraph")
        assert "<p>Hello paragraph</p>" in html

    def test_simple_md_to_html_list(self):
        exporter = PDFExporter()
        html = exporter._simple_md_to_html("- item 1\n- item 2")
        assert "<li>item 1</li>" in html
        assert "<li>item 2</li>" in html

    def test_simple_md_to_html_table(self):
        exporter = PDFExporter()
        html = exporter._simple_md_to_html("| Col1 | Col2 |\n| val1 | val2 |")
        assert "<tr>" in html
        assert "<td>Col1</td>" in html
        assert "<td>val2</td>" in html

    def test_simple_md_to_html_code_block(self):
        exporter = PDFExporter()
        html = exporter._simple_md_to_html("```\ncode line\n```")
        assert "<code>code line</code>" in html

    def test_simple_md_to_html_escapes_html(self):
        exporter = PDFExporter()
        html = exporter._simple_md_to_html("<script>alert('xss')</script>")
        assert "&lt;script&gt;" in html
        assert "<script>" not in html

    def test_get_default_css_contains_body(self):
        exporter = PDFExporter()
        css = exporter._get_default_css()
        assert "body" in css
        assert "font-family" in css

    def test_md_to_html_without_template(self):
        exporter = PDFExporter()
        data = ResultData(content="# Hello")
        html = exporter._md_to_html(data, None)
        assert "<h1>Hello</h1>" in html

    def test_md_to_html_with_template(self):
        exporter = PDFExporter()
        data = ResultData(content="Content here", metadata={"title": "Test"})
        template = "<div>{{ content }}</div>"
        html = exporter._md_to_html(data, template)
        assert "Content here" in html

    def test_export_returns_bytes(self):
        exporter = PDFExporter()
        data = ResultData(content="# Test Document")
        result = exporter.export(data)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_fallback_pdf_contains_html(self):
        exporter = PDFExporter()
        data = ResultData(content="# Fallback Test")
        result = exporter._fallback_pdf(data)
        assert isinstance(result, bytes)
        assert b"<!DOCTYPE html>" in result
        assert b"<h1>Fallback Test</h1>" in result


class TestWordExporter:
    """WordExporter 测试"""

    def test_export_returns_valid_docx(self):
        exporter = WordExporter()
        data = ResultData(
            content="# Title\n\nParagraph\n- item 1\n- item 2",
            metadata={"title": "My Document"},
        )
        result = exporter.export(data)
        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result[:2] == b"PK"

    def test_export_with_headings(self):
        exporter = WordExporter()
        data = ResultData(
            content="# H1\n## H2\n### H3",
            metadata={"title": "Doc"},
        )
        result = exporter.export(data)
        assert isinstance(result, bytes)

    def test_export_with_table(self):
        exporter = WordExporter()
        data = ResultData(
            content="| Col1 | Col2 |\n|------|------|\n| val1 | val2 |",
            metadata={"title": "Doc"},
        )
        result = exporter.export(data)
        assert isinstance(result, bytes)

    def test_export_empty_content(self):
        exporter = WordExporter()
        data = ResultData(content="", metadata={"title": "Empty"})
        result = exporter.export(data)
        assert isinstance(result, bytes)


class TestExcelExporter:
    """ExcelExporter 测试"""

    def test_export_returns_valid_xlsx(self):
        exporter = ExcelExporter()
        data = ResultData(
            content="| Name | Value |\n|------|-------|\n| A | 100 |\n| B | 200 |",
            metadata={"title": "Report"},
        )
        result = exporter.export(data)
        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result[:2] == b"PK"

    def test_parse_markdown_table(self):
        exporter = ExcelExporter()
        content = "| Col1 | Col2 |\n|------|------|\n| val1 | val2 |"
        rows = exporter._parse_markdown_table(content)
        assert len(rows) == 2
        assert rows[0] == ["Col1", "Col2"]
        assert rows[1] == ["val1", "val2"]

    def test_parse_markdown_table_with_separator(self):
        exporter = ExcelExporter()
        content = "| A | B |\n|---|---|\n| 1 | 2 |"
        rows = exporter._parse_markdown_table(content)
        assert len(rows) == 2
        assert rows[0] == ["A", "B"]

    def test_parse_markdown_table_no_table(self):
        exporter = ExcelExporter()
        content = "Just some text\nNo table here"
        rows = exporter._parse_markdown_table(content)
        assert len(rows) >= 1

    def test_export_with_sheet_name(self):
        exporter = ExcelExporter()
        data = ResultData(
            content="| A | B |\n|---|---|\n| 1 | 2 |",
            metadata={"title": "Test"},
        )
        result = exporter.export(data, sheet_name="CustomSheet")
        assert isinstance(result, bytes)


class TestExportManager:
    """ExportManager 单例测试"""

    def test_singleton(self):
        m1 = ExportManager()
        m2 = ExportManager()
        assert m1 is m2

    def test_register_exporter(self):
        manager = ExportManager()
        custom = MarkdownExporter()
        manager.register_exporter(ExportFormat.HTML, custom)
        assert ExportFormat.HTML in manager._exporters
        # 清理：恢复原始状态（HTML 原本未注册）
        del manager._exporters[ExportFormat.HTML]

    def test_get_supported_formats_known_skill(self):
        manager = ExportManager()
        formats = manager.get_supported_formats("report_skill")
        assert ExportFormat.PDF in formats
        assert ExportFormat.MARKDOWN in formats

    def test_get_supported_formats_unknown_skill(self):
        manager = ExportManager()
        formats = manager.get_supported_formats("unknown_skill")
        assert len(formats) > 0

    def test_can_export_true(self):
        manager = ExportManager()
        assert manager.can_export("report_skill", ExportFormat.PDF) is True

    def test_can_export_false(self):
        manager = ExportManager()
        assert manager.can_export("report_skill", ExportFormat.IMAGE) is False

    def test_export_sync_markdown(self):
        manager = ExportManager()
        data = ResultData(content="# Hello")
        result = manager.export_sync(data, ExportFormat.MARKDOWN)
        assert result == "# Hello".encode("utf-8")

    def test_export_sync_unsupported_format_raises(self):
        manager = ExportManager()
        data = ResultData(content="test")
        with pytest.raises(ValueError, match="Unsupported format"):
            manager.export_sync(data, ExportFormat.HTML)

    @pytest.mark.asyncio
    async def test_export_async_markdown(self):
        manager = ExportManager()
        data = ResultData(content="# Async Test")
        result = await manager.export_async(data, ExportFormat.MARKDOWN)
        assert result == "# Async Test".encode("utf-8")

    def test_export_sync_with_template(self):
        manager = ExportManager()
        data = ResultData(content="test", metadata={"title": "T"})
        result = manager.export_sync(data, ExportFormat.PDF, template_id="nonexistent")
        assert isinstance(result, bytes)
