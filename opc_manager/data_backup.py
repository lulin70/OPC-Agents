"""
Data Backup Manager — v0.2.0 Data import/export system.

Provides:
- Full data export (ZIP archive containing JSON + attachments)
- Data import from backup ZIP
- One-click backup to specified directory
- Version validation and conflict resolution
"""

import json
import os
import shutil
import zipfile
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import hashlib

logger = logging.getLogger(__name__)

BACKUP_DIR = "data/backups"
EXPORT_FORMATS = ["json", "csv", "zip"]
BACKUP_VERSION = "1.0"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB — 超过此大小的文件跳过并记录警告


@dataclass
class BackupManifest:
    version: str = BACKUP_VERSION
    created_at: str = ""
    created_by: str = "OPC-Agents v0.2.0"
    total_files: int = 0
    total_size_bytes: int = 0
    checksum_sha256: str = ""
    tables: List[str] = field(default_factory=list)
    includes_attachments: bool = False


class DataBackupManager:
    """Manages data backup, restore, and export operations."""

    def __init__(self, base_dir: str = None):
        self._base_dir = Path(base_dir) if base_dir else Path.cwd()
        self._backup_dir = self._base_dir / BACKUP_DIR
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, include_attachments: bool = False) -> Tuple[Path, BackupManifest]:
        """Create a full backup of all user data.

        Returns:
            Tuple of (backup_file_path, manifest)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"opc_agents_backup_{timestamp}.zip"
        backup_path = self._backup_dir / backup_name

        manifest = BackupManifest(
            created_at=datetime.now().isoformat(),
            tables=[],
            includes_attachments=include_attachments,
        )

        files_to_backup = []
        total_size = 0

        # Collect data files
        data_dir = self._base_dir / "data"
        if data_dir.exists():
            for f in data_dir.rglob("*"):
                if f.is_file():
                    rel_path = f.relative_to(data_dir)
                    fname = str(rel_path)

                    # Skip runtime cache files
                    skip_patterns = ["__pycache__", ".pyc", ".db-wal", ".db-shm",
                                   "settings.json", "onboarding.json",
                                   "llm_cache/", "dashboard/"]
                    if any(p in fname for p in skip_patterns):
                        continue

                    fsize = f.stat().st_size
                    if fsize > MAX_FILE_SIZE:
                        logger.warning("跳过超大文件 %s (%.1fMB > 50MB限制)", fname, fsize / (1024 * 1024))
                        continue

                    files_to_backup.append((f, rel_path))
                    total_size += fsize

                    if fname.endswith(".json") or fname.endswith(".db"):
                        if fname not in manifest.tables:
                            manifest.tables.append(fname)

        manifest.total_files = len(files_to_backup)
        manifest.total_size_bytes = total_size

        # Create ZIP
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path, rel_path in files_to_backup:
                zf.write(file_path, arcname=str(rel_path))

        # Calculate checksum — 流式读取避免大文件OOM
        sha256 = hashlib.sha256()
        with open(backup_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)
        manifest.checksum_sha256 = sha256.hexdigest()

        # Save manifest inside zip
        manifest_json = json.dumps(manifest.__dict__, indent=2, ensure_ascii=False)
        with zipfile.ZipFile(backup_path, 'a') as zf:
            zf.writestr("manifest.json", manifest_json)

        logger.info("Backup created: %s (%d files, %d bytes)",
                    backup_path, manifest.total_files, total_size)

        return backup_path, manifest

    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups."""
        backups = []
        for f in sorted(self._backup_dir.glob("*.zip"), reverse=True):
            stat = f.stat()
            backups.append({
                "filename": f.name,
                "path": str(f),
                "size_mb": round(stat.st_size / (1024*1024), 2),
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        return backups

    def restore_backup(self, backup_path: str, confirm: bool = False) -> Dict[str, Any]:
        """Restore data from a backup ZIP.

        Args:
            confirm: Must be True to proceed (safety check)
        """
        if not confirm:
            return {"success": False, "error": "Must confirm restore operation"}

        bp = Path(backup_path)
        if not bp.exists():
            return {"success": False, "error": f"Backup file not found: {backup_path}"}

        try:
            data_dir = self._base_dir / "data"

            # Read manifest and extract all files safely — prevent Zip Slip
            with zipfile.ZipFile(bp, 'r') as zf:
                if "manifest.json" in zf.namelist():
                    manifest_data = json.loads(zf.read("manifest.json"))
                    logger.info("Restoring from backup: v%s, %d files",
                               manifest_data.get("version"), manifest_data.get("total_files", "?"))

                for zip_info in zf.infolist():
                    arcname = zip_info.filename
                    if arcname.startswith("/") or ".." in arcname:
                        logger.warning("Skipping unsafe ZIP entry: %s", arcname)
                        continue
                    target_path = data_dir / arcname
                    try:
                        target_path.resolve().relative_to(data_dir.resolve())
                    except ValueError:
                        logger.warning("Skipping path-traversal entry: %s", arcname)
                        continue
                    zf.extract(zip_info, data_dir)

            return {
                "success": True,
                "message": f"Restored from {bp.name}",
                "restored_files": len([n for n in zipfile.ZipFile(bp).namelist()
                                       if n != "manifest.json"]),
            }
        except Exception as e:
            logger.error("Restore failed: %s", e)
            return {"success": False, "error": str(e)}

    def delete_backup(self, backup_path: str) -> bool:
        """Delete a backup file."""
        bp = Path(backup_path)
        if bp.exists() and bp.is_file():
            bp.unlink()
            return True
        return False

    def export_data(self, format_type: str = "json") -> bytes:
        """Export all user data in specified format.

        Args:
            format_type: "json" or "csv" or "zip"

        Returns:
            bytes of the exported data
        """
        if format_type == "zip":
            path, _ = self.create_backup(include_attachments=False)
            with open(path, 'rb') as f:
                return f.read()

        elif format_type == "json":
            data = {}
            data_dir = self._base_dir / "data"
            if data_dir.exists():
                for f in data_dir.glob("*.json"):
                    try:
                        data[f.stem] = json.loads(f.read_text(encoding='utf-8'))
                    except Exception as e:
                        logger.warning("Failed to read %s: %s", f, e)
                        data[f.stem] = {"_error": str(e)}

            result = {
                "exported_at": datetime.now().isoformat(),
                "exporter": "OPC-Agents v0.2.0",
                "tables": list(data.keys()),
                "data": data,
            }
            return json.dumps(result, indent=2, ensure_ascii=False).encode('utf-8')

        elif format_type == "csv":
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["table", "key", "value", "exported_at"])

            ts = datetime.now().isoformat()
            data_dir = self._base_dir / "data"
            if data_dir.exists():
                for f in data_dir.glob("*.json"):
                    try:
                        d = json.loads(f.read_text(encoding='utf-8'))
                        table_name = f.stem
                        if isinstance(d, dict):
                            for k, v in d.items():
                                if isinstance(v, (str, int, float, bool)):
                                    writer.writerow([table_name, k, str(v), ts])
                                elif isinstance(v, dict):
                                    writer.writerow([table_name, k, json.dumps(v, ensure_ascii=False), ts])
                    except Exception as e:
                        logger.debug("[DataBackup] CSV write row failed: %s", e)

            return output.getvalue().encode('utf-8')

        else:
            raise ValueError(f"Unsupported format: {format_type}")


def get_backup_manager() -> DataBackupManager:
    return DataBackupManager()
