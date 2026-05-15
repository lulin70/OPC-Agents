from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class ExportFormat(Enum):
    MARKDOWN = "md"
    PDF = "pdf"
    WORD = "docx"
    EXCEL = "xlsx"
    IMAGE = "png"
    HTML = "html"


@dataclass
class ResultData:
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    attachments: Optional[List[bytes]] = None


SKILL_EXPORT_CAPABILITIES = {
    "proposal_skill": [ExportFormat.PDF, ExportFormat.WORD, ExportFormat.MARKDOWN],
    "report_skill": [ExportFormat.PDF, ExportFormat.EXCEL, ExportFormat.MARKDOWN],
    "invoice_skill": [ExportFormat.PDF, ExportFormat.MARKDOWN],
    "email_skill": [ExportFormat.HTML, ExportFormat.MARKDOWN],
    "social_skill": [ExportFormat.IMAGE, ExportFormat.MARKDOWN],
    "dashboard_skill": [ExportFormat.PDF, ExportFormat.EXCEL, ExportFormat.MARKDOWN],
    "finance_skill": [ExportFormat.EXCEL, ExportFormat.PDF, ExportFormat.MARKDOWN],
}
