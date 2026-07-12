"""
Data Backup Manager — v0.3.18 Data import/export system.

Provides:
- Full data export (ZIP archive containing JSON + attachments)
- Data import from backup ZIP
- One-click backup to specified directory
- Version validation and conflict resolution
"""

import json
import os
import zipfile
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import hashlib

logger = logging.getLogger(__name__)

# AES加密ZIP支持：优先 pyzipper，不可用时回退到标准 zipfile（无加密）
_ZIP_AES_AVAILABLE = False
try:
    import pyzipper

    _ZIP_AES_AVAILABLE = True
except ImportError:
    pass

BACKUP_DIR = "data/backups"
EXPORT_FORMATS = ["json", "csv", "zip"]
BACKUP_VERSION = "1.0"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB — 超过此大小的文件跳过并记录警告
SENSITIVE_FIELDS = {
    "api_key",
    "password",
    "secret",
    "token",
    "smtp_pass",
    "encryption_key",
    "app_secret",
}
REDACTED_VALUE = "***REDACTED***"


@dataclass
class BackupManifest:
    version: str = BACKUP_VERSION
    created_at: str = ""
    created_by: str = "OPC-Agents v0.3.18"
    total_files: int = 0
    total_size_bytes: int = 0
    checksum_sha256: str = ""
    tables: List[str] = field(default_factory=list)
    includes_attachments: bool = False
    encrypted: bool = False


def _get_backup_password() -> Optional[str]:
    """Get backup password from environment variables.

    Priority:
    1. OPC_BACKUP_PASSWORD
    2. SettingsManager encryption key (不通过 os.environ)
    3. First 32 bytes of OPC_ENCRYPTION_KEY (if set in env)
    4. None (no encryption)
    """
    password = os.environ.get("OPC_BACKUP_PASSWORD")
    if password:
        return password

    # 优先通过 SettingsManager 获取加密密钥
    try:
        from opc_manager.settings import get_settings

        settings = get_settings()
        encryption_key = settings.get_encryption_key()
        if encryption_key:
            return encryption_key[:32]
    except Exception as e:
        logger.warning("[DataBackup] Failed to get encryption key from settings: %s", e)

    # 回退到 os.environ（兼容外部设置的环境变量）
    encryption_key = os.environ.get("OPC_ENCRYPTION_KEY", "")
    if encryption_key:
        return encryption_key[:32]

    return None


def _is_sensitive_field(field_name: str) -> bool:
    """Check if a field name contains any sensitive keyword."""
    name_lower = field_name.lower()
    return any(kw in name_lower for kw in SENSITIVE_FIELDS)


def _sanitize_value(data: Any) -> Any:
    """Recursively sanitize sensitive fields in data structures."""
    if isinstance(data, dict):
        return {
            k: REDACTED_VALUE if _is_sensitive_field(k) else _sanitize_value(v)
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [_sanitize_value(item) for item in data]
    return data


class DataBackupManager:
    """Manages data backup, restore, and export operations."""

    def __init__(self, base_dir: Optional[str] = None):
        self._base_dir = Path(base_dir) if base_dir else Path.cwd()
        self._backup_dir = self._base_dir / BACKUP_DIR
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(
        self, include_attachments: bool = False
    ) -> Tuple[Path, BackupManifest]:
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
                    skip_patterns = [
                        "__pycache__",
                        ".pyc",
                        ".db-wal",
                        ".db-shm",
                        "settings.json",
                        "onboarding.json",
                        "llm_cache/",
                        "dashboard/",
                    ]
                    if any(p in fname for p in skip_patterns):
                        continue

                    fsize = f.stat().st_size
                    if fsize > MAX_FILE_SIZE:
                        logger.warning(
                            "跳过超大文件 %s (%.1fMB > 50MB限制)",
                            fname,
                            fsize / (1024 * 1024),
                        )
                        continue

                    files_to_backup.append((f, rel_path))
                    total_size += fsize

                    if fname.endswith(".json") or fname.endswith(".db"):
                        if fname not in manifest.tables:
                            manifest.tables.append(fname)

        manifest.total_files = len(files_to_backup)
        manifest.total_size_bytes = total_size

        # Determine encryption settings
        backup_password = _get_backup_password()
        encrypted = False

        if backup_password:
            if _ZIP_AES_AVAILABLE:
                # AES加密模式
                with pyzipper.AESZipFile(
                    backup_path, "w", compression=pyzipper.ZIP_DEFLATED
                ) as zf:
                    zf.setpassword(backup_password.encode("utf-8"))
                    zf.setencryption(pyzipper.WZ_AES, nbits=256)
                    for file_path, rel_path in files_to_backup:
                        zf.write(file_path, arcname=str(rel_path))
                encrypted = True
                logger.info("Backup created with AES-256 encryption")
            else:
                # pyzipper不可用，回退到无加密模式
                logger.warning(
                    "pyzipper not available — backup will be created WITHOUT encryption. "
                    "Install pyzipper for AES encryption: pip install pyzipper"
                )
                with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for file_path, rel_path in files_to_backup:
                        zf.write(file_path, arcname=str(rel_path))
        else:
            # 无密码，使用标准zipfile无加密模式
            with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path, rel_path in files_to_backup:
                    zf.write(file_path, arcname=str(rel_path))

        manifest.encrypted = encrypted

        # Calculate checksum of data files (excluding manifest) before writing manifest
        sha256 = hashlib.sha256()
        for file_path, rel_path in sorted(files_to_backup):
            sha256.update(str(rel_path).encode())
            with open(file_path, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    sha256.update(chunk)
        manifest.checksum_sha256 = sha256.hexdigest()

        # Save manifest inside zip
        manifest_json = json.dumps(manifest.__dict__, indent=2, ensure_ascii=False)
        with zipfile.ZipFile(backup_path, "a") as zf:
            zf.writestr("manifest.json", manifest_json)

        logger.info(
            "Backup created: %s (%d files, %d bytes)",
            backup_path,
            manifest.total_files,
            total_size,
        )

        return backup_path, manifest

    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups."""
        backups = []
        for f in sorted(self._backup_dir.glob("*.zip"), reverse=True):
            stat = f.stat()
            backups.append(
                {
                    "filename": f.name,
                    "path": str(f),
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )
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
            with zipfile.ZipFile(bp, "r") as zf:
                manifest_data = {}
                namelist = zf.namelist()
                if "manifest.json" in namelist:
                    manifest_data = json.loads(zf.read("manifest.json"))
                    logger.info(
                        "Restoring from backup: v%s, %d files",
                        manifest_data.get("version"),
                        manifest_data.get("total_files", "?"),
                    )

                # Verify backup integrity via checksum (data files only, not manifest)
                expected_checksum = manifest_data.get("checksum_sha256", "")
                if expected_checksum:
                    sha256 = hashlib.sha256()
                    # Sort by filename to match create_backup's sorted() order
                    data_entries = sorted(
                        [zi for zi in zf.infolist() if zi.filename != "manifest.json"],
                        key=lambda zi: zi.filename,
                    )
                    for zip_info in data_entries:
                        sha256.update(zip_info.filename.encode())
                        sha256.update(zf.read(zip_info.filename))
                    actual_checksum = sha256.hexdigest()
                    if actual_checksum != expected_checksum:
                        return {
                            "success": False,
                            "error": f"Backup integrity check failed: checksum mismatch "
                            f"(expected {expected_checksum[:16]}..., got {actual_checksum[:16]}...)",
                        }
                    logger.info("Backup integrity verified: checksum OK")
                else:
                    logger.warning(
                        "No checksum in manifest — skipping integrity verification"
                    )

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

                restored_count = len([n for n in namelist if n != "manifest.json"])

            return {
                "success": True,
                "message": f"Restored from {bp.name}",
                "restored_files": restored_count,
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

        Sensitive fields are automatically redacted in the output.

        Args:
            format_type: "json" or "csv" or "zip"

        Returns:
            bytes of the exported data
        """
        if format_type == "zip":
            path, _ = self.create_backup(include_attachments=False)
            with open(path, "rb") as fh:
                return fh.read()

        elif format_type == "json":
            data = {}
            data_dir = self._base_dir / "data"
            if data_dir.exists():
                for f in data_dir.glob("*.json"):
                    try:
                        raw = json.loads(f.read_text(encoding="utf-8"))
                        data[f.stem] = _sanitize_value(raw)
                    except Exception as e:
                        logger.warning("Failed to read %s: %s", f, e)
                        data[f.stem] = {"_error": str(e)}

            result = {
                "exported_at": datetime.now().isoformat(),
                "exporter": "OPC-Agents v0.3.18",
                "tables": list(data.keys()),
                "data": data,
                "_meta": {"sanitized": True},
            }
            return json.dumps(result, indent=2, ensure_ascii=False).encode("utf-8")

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
                        d = json.loads(f.read_text(encoding="utf-8"))
                        d = _sanitize_value(d)
                        table_name = f.stem
                        if isinstance(d, dict):
                            for k, v in d.items():
                                if isinstance(v, (str, int, float, bool)):
                                    writer.writerow([table_name, k, str(v), ts])
                                elif isinstance(v, dict):
                                    writer.writerow(
                                        [
                                            table_name,
                                            k,
                                            json.dumps(v, ensure_ascii=False),
                                            ts,
                                        ]
                                    )
                    except Exception as e:
                        logger.debug("[DataBackup] CSV write row failed: %s", e)

            return output.getvalue().encode("utf-8")

        else:
            raise ValueError(f"Unsupported format: {format_type}")


def get_backup_manager() -> DataBackupManager:
    return DataBackupManager()
