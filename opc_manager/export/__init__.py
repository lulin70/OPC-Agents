from .manager import ExportManager
from .models import ResultData, ExportFormat, SKILL_EXPORT_CAPABILITIES


def get_export_manager() -> ExportManager:
    return ExportManager()


export_manager = get_export_manager()
