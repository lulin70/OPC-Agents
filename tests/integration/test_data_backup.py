"""Tests for DataBackupManager — v0.2.0 Data import/export system.

Covers:
- Backup creation with manifest
- Backup listing and deletion
- Restore operations (with/without confirmation)
- Export in multiple formats (JSON, CSV, ZIP)
- Error handling and edge cases
"""

import json
import zipfile
import pytest

from opc_manager.data_backup import (
    DataBackupManager,
    BackupManifest,
    get_backup_manager,
    BACKUP_DIR,
    BACKUP_VERSION,
)


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace with sample data files."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create data directory structure
    data_dir = workspace / "data"
    data_dir.mkdir()

    # Create sample JSON files
    (data_dir / "customers.json").write_text(
        json.dumps(
            {
                "cust_1": {"name": "Test Customer", "status": "active"},
                "cust_2": {"name": "Another Customer", "status": "potential"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    (data_dir / "finance.json").write_text(
        json.dumps(
            {
                "income": 10000,
                "expense": 5000,
                "profit": 5000,
            }
        ),
        encoding="utf-8",
    )

    (data_dir / "tasks.json").write_text(
        json.dumps(
            [
                {"id": 1, "title": "Task 1", "status": "completed"},
                {"id": 2, "title": "Task 2", "status": "pending"},
            ]
        ),
        encoding="utf-8",
    )

    # Create a subdirectory with files
    subdir = data_dir / "subdir"
    subdir.mkdir()
    (subdir / "config.json").write_text(json.dumps({"key": "value"}), encoding="utf-8")

    # Create backup directory
    backup_dir = workspace / BACKUP_DIR
    backup_dir.mkdir(parents=True, exist_ok=True)

    return workspace


class TestCreateBackupBasic:
    """Test basic backup creation functionality."""

    def test_create_backup_basic(self, temp_workspace):
        """Test that basic backup creates a ZIP file."""
        manager = DataBackupManager(base_dir=str(temp_workspace))
        backup_path, manifest = manager.create_backup()

        assert backup_path.exists()
        assert backup_path.suffix == ".zip"
        assert backup_path.name.startswith("opc_agents_backup_")
        assert isinstance(manifest, BackupManifest)
        assert manifest.version == BACKUP_VERSION
        assert manifest.created_by == "OPC-Agents v0.3.20"
        assert manifest.created_at != ""
        assert manifest.total_files > 0

    def test_create_backup_with_manifest(self, temp_workspace):
        """Test that backup includes valid manifest with checksum."""
        manager = DataBackupManager(base_dir=str(temp_workspace))
        backup_path, manifest = manager.create_backup()

        # Verify manifest is saved inside ZIP
        with zipfile.ZipFile(backup_path, "r") as zf:
            assert "manifest.json" in zf.namelist()
            saved_manifest = json.loads(zf.read("manifest.json"))

            assert saved_manifest["version"] == BACKUP_VERSION
            assert saved_manifest["total_files"] == manifest.total_files
            assert saved_manifest["checksum_sha256"] == manifest.checksum_sha256
            assert len(saved_manifest["checksum_sha256"]) == 64  # SHA256 hex length

        # Verify tables are recorded
        assert len(manifest.tables) > 0
        assert any("customers.json" in t for t in manifest.tables)


class TestListBackups:
    """Test backup listing functionality."""

    def test_list_backups_empty(self, temp_workspace):
        """Test listing backups when none exist."""
        manager = DataBackupManager(base_dir=str(temp_workspace))
        backups = manager.list_backups()

        assert isinstance(backups, list)
        assert len(backups) == 0

    def test_list_backups_existing(self, temp_workspace):
        """Test listing existing backups."""
        manager = DataBackupManager(base_dir=str(temp_workspace))

        # Create multiple backups with small delay to ensure unique timestamps
        manager.create_backup()
        import time

        time.sleep(1.1)  # Ensure different timestamp
        manager.create_backup()

        backups = manager.list_backups()

        assert len(backups) == 2
        # Should be sorted by creation time (newest first)
        assert all("filename" in b for b in backups)
        assert all("path" in b for b in backups)
        assert all("size_mb" in b for b in backups)
        assert all("created_at" in b for b in backups)


class TestRestoreBackup:
    """Test backup restore functionality."""

    def test_restore_without_confirm_fails(self, temp_workspace):
        """Test that restore fails without explicit confirmation."""
        manager = DataBackupManager(base_dir=str(temp_workspace))
        backup_path, _ = manager.create_backup()

        result = manager.restore_backup(str(backup_path), confirm=False)

        assert result["success"] is False
        assert "confirm" in result["error"].lower()

    def test_restore_success(self, temp_workspace):
        """Test successful restore from backup."""
        manager = DataBackupManager(base_dir=str(temp_workspace))
        backup_path, _ = manager.create_backup()

        # Modify original data to verify restore works
        data_dir = temp_workspace / "data"
        original_content = (data_dir / "customers.json").read_text(encoding="utf-8")
        (data_dir / "customers.json").write_text(
            json.dumps({"modified": True}), encoding="utf-8"
        )

        # Restore from backup
        result = manager.restore_backup(str(backup_path), confirm=True)

        assert result["success"] is True
        assert result["restored_files"] > 0
        # Verify data was restored
        restored_content = (data_dir / "customers.json").read_text(encoding="utf-8")
        assert restored_content == original_content

    def test_restore_nonexistent_file(self, temp_workspace):
        """Test restoring from non-existent file fails gracefully."""
        manager = DataBackupManager(base_dir=str(temp_workspace))

        result = manager.restore_backup("/nonexistent/path.zip", confirm=True)

        assert result["success"] is False
        assert "not found" in result["error"].lower()


class TestDeleteBackup:
    """Test backup deletion functionality."""

    def test_delete_backup(self, temp_workspace):
        """Test deleting an existing backup."""
        manager = DataBackupManager(base_dir=str(temp_workspace))
        backup_path, _ = manager.create_backup()

        assert backup_path.exists()
        result = manager.delete_backup(str(backup_path))

        assert result is True
        assert not backup_path.exists()

    def test_delete_nonexistent_backup(self, temp_workspace):
        """Test deleting non-existent backup returns False."""
        manager = DataBackupManager(base_dir=str(temp_workspace))
        result = manager.delete_backup("/nonexistent/path.zip")

        assert result is False


class TestExportData:
    """Test data export in various formats."""

    def test_export_json_format(self, temp_workspace):
        """Test exporting data as JSON."""
        manager = DataBackupManager(base_dir=str(temp_workspace))
        json_bytes = manager.export_data(format_type="json")

        data = json.loads(json_bytes.decode("utf-8"))

        assert "exported_at" in data
        assert "exporter" in data
        assert data["exporter"] == "OPC-Agents v0.3.20"
        assert "tables" in data
        assert "data" in data
        assert len(data["tables"]) > 0
        assert "customers" in data["data"]

    def test_export_csv_format(self, temp_workspace):
        """Test exporting data as CSV."""
        manager = DataBackupManager(base_dir=str(temp_workspace))
        csv_bytes = manager.export_data(format_type="csv")

        csv_text = csv_bytes.decode("utf-8")
        lines = csv_text.strip().split("\n")

        # Should have header + data rows
        assert len(lines) >= 2
        # Header should contain expected columns
        assert "table" in lines[0]
        assert "key" in lines[0]
        assert "value" in lines[0]

    def test_export_zip_format(self, temp_workspace):
        """Test exporting data as ZIP."""
        manager = DataBackupManager(base_dir=str(temp_workspace))
        zip_bytes = manager.export_data(format_type="zip")

        # Verify it's a valid ZIP
        import io

        zip_buffer = io.BytesIO(zip_bytes)
        with zipfile.ZipFile(zip_buffer, "r") as zf:
            assert "manifest.json" in zf.namelist()
            filenames = zf.namelist()
            assert any("customers.json" in f for f in filenames)

    def test_invalid_format_raises(self, temp_workspace):
        """Test that invalid format raises ValueError."""
        manager = DataBackupManager(base_dir=str(temp_workspace))

        with pytest.raises(ValueError, match="Unsupported format"):
            manager.export_data(format_type="invalid_format")


class TestBackupDirectoryAutoCreated:
    """Test automatic backup directory creation."""

    def test_backup_directory_auto_created(self, tmp_path):
        """Test that backup directory is created automatically if not exists."""
        workspace = tmp_path / "new_workspace"
        workspace.mkdir()

        # Don't create backup dir manually
        manager = DataBackupManager(base_dir=str(workspace))

        backup_path, _ = manager.create_backup()

        assert backup_path.exists()
        assert (workspace / BACKUP_DIR).exists()
        assert (workspace / BACKUP_DIR).is_dir()


class TestGetBackupManager:
    """Test factory function."""

    def test_get_backup_manager_returns_instance(self):
        """Test that factory function returns DataBackupManager instance."""
        manager = get_backup_manager()

        assert isinstance(manager, DataBackupManager)

    def test_backup_manifest_defaults(self):
        """Test BackupManifest default values."""
        manifest = BackupManifest()

        assert manifest.version == BACKUP_VERSION
        assert manifest.created_at == ""
        assert manifest.created_by == "OPC-Agents v0.3.20"
        assert manifest.total_files == 0
        assert manifest.total_size_bytes == 0
        assert manifest.checksum_sha256 == ""
        assert manifest.tables == []
        assert manifest.includes_attachments is False
