class PDFExporter:
    def export(self, data, template=None, **opts) -> bytes:
        try:
            from weasyprint import HTML, CSS

            html_content = self._md_to_html(data, template)
            css_str = opts.get("css", self._get_default_css())
            pdf_bytes = HTML(string=html_content).write_pdf(stylesheets=[CSS(string=css_str)])
            return pdf_bytes
        except (ImportError, OSError):
            return self._fallback_pdf(data)

    def _md_to_html(self, data, template):
        if template:
            from jinja2 import Template
            return Template(template).render(content=data.content, meta=data.metadata)
        try:
            import markdown
            return markdown.markdown(data.content, extensions=['tables', 'fenced_code'])
        except ImportError:
            return self._simple_md_to_html(data.content)

    def _simple_md_to_html(self, md_text):
        html = md_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        lines = html.split('\n')
        out = []
        in_code = False
        for line in lines:
            if line.startswith('```'):
                in_code = not in_code
                continue
            if in_code:
                out.append(f'<code>{line}</code><br>')
            elif line.startswith('# '):
                out.append(f'<h1>{line[2:]}</h1>')
            elif line.startswith('## '):
                out.append(f'<h2>{line[3:]}</h2>')
            elif line.startswith('### '):
                out.append(f'<h3>{line[4:]}</h3>')
            elif line.strip() == '':
                out.append('<br>')
            elif line.startswith('- '):
                out.append(f'<li>{line[2:]}</li>')
            elif line.startswith('|'):
                cells = [c.strip() for c in line.split('|') if c.strip()]
                if cells:
                    out.append('<tr>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>')
            else:
                out.append(f'<p>{line}</p>')
        return '\n'.join(out)

    def _get_default_css(self):
        return """
        body { font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif; margin: 40px; line-height: 1.6; }
        h1, h2, h3 { color: #1a1a1a; border-bottom: 1px solid #eee; padding-bottom: 8px; }
        table { border-collapse: collapse; width: 100%; margin: 16px 0; }
        th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
        th { background-color: #f5f5f5; font-weight: bold; }
        code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }
        li { margin: 4px 0; }
        """

    def _fallback_pdf(self, data):
        html = f"<html><body><pre>{data.content}</pre></body></html>"
        return html.encode('utf-8')
