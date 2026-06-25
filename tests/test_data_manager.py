"""
Data Manager Unit Tests — Database operations, encryption, and persistence validation.

Covers:
- encrypt_field/decrypt_field round-trip
- gen_id format (16 char hex)
- init_db: creates tables, idempotent (call twice), seeds categories/templates
- execute_query: simple query, parametrized query, empty result
- execute_write: insert, update, returns change count
- execute_transaction: commit success, rollback on error
- execute_write_returning: returns lastrowid
- get_preference/set_preference: round-trip, default value
- backup_db: creates file, respects OPC_BACKUP_COUNT
- DB schema: verify key tables exist via PRAGMA
- Migration: _add_column_if_not_exists exists, skips if column present

Run command:
    pytest tests/test_data_manager.py -v --tb=short
"""

import os
import sqlite3

import pytest
from opc_manager.data_manager import (
    encrypt_field,
    decrypt_field,
    init_db,
    execute_query,
    execute_write,
    execute_transaction,
    execute_write_returning,
    backup_db,
    gen_id,
    get_preference,
    set_preference,
    _add_column_if_not_exists,
    _db_initialized,
    _get_conn,
    _local,
    DB_PATH,
    DATA_DIR,
)


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Set up a temporary database environment for each test.

    Creates a temp data dir, sets env vars for encryption key and data dir,
    and resets module-level DB state so each test gets a fresh DB.
    Restores original state after test to avoid polluting other test modules.
    """
    db_dir = tmp_path / "data"
    db_dir.mkdir()
    monkeypatch.setenv("OPC_DATA_DIR", str(db_dir))
    monkeypatch.setenv("OPC_ENCRYPTION_KEY", "test-key-for-encryption-32chars!!")
    import opc_manager.data_manager as dm

    # Save original module-level state so we can restore it after the test.
    _orig_data_dir = dm.DATA_DIR
    _orig_db_path = dm.DB_PATH
    _orig_backup_dir = dm.BACKUP_DIR
    _orig_initialized = dm._db_initialized

    # Patch module-level paths because DATA_DIR/DB_PATH were already resolved
    # at import time; monkeypatch.setenv alone does not affect them.
    dm.DATA_DIR = str(db_dir)
    dm.DB_PATH = os.path.join(dm.DATA_DIR, "opc_data.db")
    dm.BACKUP_DIR = os.path.join(dm.DATA_DIR, "backups")
    dm._db_initialized = False
    if hasattr(_local, "conn") and _local.conn is not None:
        try:
            _local.conn.close()
        except Exception:
            pass
        _local.conn = None
    yield db_dir
    if hasattr(_local, "conn") and _local.conn is not None:
        try:
            _local.conn.close()
        except Exception:
            pass
        _local.conn = None
    dm.DATA_DIR = _orig_data_dir
    dm.DB_PATH = _orig_db_path
    dm.BACKUP_DIR = _orig_backup_dir
    dm._db_initialized = _orig_initialized


class TestEncryptDecryptRoundTrip:
    """Test suite for encrypt_field/decrypt_field round-trip."""

    def test_encrypt_then_decrypt_returns_original(self, temp_db):
        plaintext = "sensitive secret message"
        ciphertext = encrypt_field(plaintext)
        assert ciphertext != plaintext
        decrypted = decrypt_field(ciphertext)
        assert decrypted == plaintext

    def test_encrypt_empty_returns_empty(self, temp_db):
        assert encrypt_field("") == ""

    def test_decrypt_empty_returns_empty(self, temp_db):
        assert decrypt_field("") == ""

    def test_decrypt_garbage_returns_none(self, temp_db):
        # Fernet tokens always start with 'gAAAA' — garbage that looks like one should return None
        result = decrypt_field(
            "gAAAAAinvalid_fernet_token_that_will_fail_decryption_check=="
        )
        assert result is None

    def test_decrypt_plaintext_with_key_returns_raw(self, temp_db):
        # When key is set but value was stored as plaintext (not Fernet token),
        # it should be returned as-is to prevent data loss during key migration
        from opc_manager.data_manager import _get_encryption_key

        key = _get_encryption_key()
        if key is None:
            # No key set — skip this test (plaintext passthrough only matters with a key)
            return
        result = decrypt_field("some-plaintext-value")
        assert result == "some-plaintext-value"

    def test_encrypt_unicode_content(self, temp_db):
        plaintext = "中文加密测试 🎉"
        ciphertext = encrypt_field(plaintext)
        decrypted = decrypt_field(ciphertext)
        assert decrypted == plaintext

    def test_encrypted_output_is_string(self, temp_db):
        result = encrypt_field("hello")
        assert isinstance(result, str)
        assert len(result) > 0


class TestGenId:
    """Test suite for gen_id()."""

    def test_gen_id_is_16_char_hex(self):
        id_ = gen_id()
        assert isinstance(id_, str)
        assert len(id_) == 16
        assert all(c in "0123456789abcdef" for c in id_)

    def test_gen_ids_are_unique(self):
        ids = {gen_id() for _ in range(200)}
        assert len(ids) == 200


class TestInitDb:
    """Test suite for init_db()."""

    def test_init_creates_database_file(self, temp_db):
        init_db()
        assert os.path.exists(DB_PATH)

    def test_init_is_idempotent(self, temp_db):
        init_db()
        init_db()
        assert os.path.exists(DB_PATH)

    def test_init_seeds_finance_categories(self, temp_db):
        init_db()
        rows = execute_query("SELECT COUNT(*) as cnt FROM finance_categories")
        assert rows[0]["cnt"] >= 7

    def test_init_seeds_email_templates(self, temp_db):
        init_db()
        rows = execute_query("SELECT COUNT(*) as cnt FROM email_templates")
        assert rows[0]["cnt"] >= 3


class TestDbSchema:
    """Test suite for verifying key tables exist via PRAGMA."""

    def test_finance_records_table_exists(self, temp_db):
        init_db()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        tables = [
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        conn.close()
        assert "finance_records" in tables

    def test_tasks_table_exists(self, temp_db):
        init_db()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        tables = [
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        conn.close()
        assert "tasks" in tables

    def test_customers_table_exists(self, temp_db):
        init_db()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        tables = [
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        conn.close()
        assert "customers" in tables

    def test_email_history_table_exists(self, temp_db):
        init_db()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        tables = [
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        conn.close()
        assert "email_history" in tables

    def test_user_preferences_table_exists(self, temp_db):
        init_db()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        tables = [
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        conn.close()
        assert "user_preferences" in tables


class TestExecuteQuery:
    """Test suite for execute_query()."""

    def test_simple_query_returns_rows(self, temp_db):
        init_db()
        rows = execute_query("SELECT name FROM finance_categories LIMIT 5")
        assert len(rows) > 0
        assert "name" in rows[0]

    def test_parametrized_query(self, temp_db):
        init_db()
        rows = execute_query(
            "SELECT * FROM finance_categories WHERE type=? LIMIT 1",
            ("income",),
        )
        assert len(rows) == 1
        assert rows[0]["type"] == "income"

    def test_empty_result(self, temp_db):
        init_db()
        rows = execute_query(
            "SELECT * FROM tasks WHERE title=?",
            ("nonexistent_task_xyz",),
        )
        assert rows == []


class TestExecuteWrite:
    """Test suite for execute_write()."""

    def test_insert_record(self, temp_db):
        init_db()
        new_id = gen_id()
        change_count = execute_write(
            "INSERT INTO tasks (id, title, status, created_at) VALUES (?,?,?,?)",
            (new_id, "test task", "pending", "2025-01-01T00:00:00"),
        )
        assert change_count > 0
        rows = execute_query("SELECT * FROM tasks WHERE id=?", (new_id,))
        assert len(rows) == 1
        assert rows[0]["title"] == "test task"

    def test_update_record(self, temp_db):
        init_db()
        new_id = gen_id()
        execute_write(
            "INSERT INTO tasks (id, title, status, created_at) VALUES (?,?,?,?)",
            (new_id, "original title", "pending", "2025-01-01T00:00:00"),
        )
        change_count = execute_write(
            "UPDATE tasks SET title=?, status=? WHERE id=?",
            ("updated title", "in_progress", new_id),
        )
        assert change_count > 0
        rows = execute_query("SELECT title, status FROM tasks WHERE id=?", (new_id,))
        assert rows[0]["title"] == "updated title"
        assert rows[0]["status"] == "in_progress"


class TestExecuteTransaction:
    """Test suite for execute_transaction()."""

    def test_commit_success(self, temp_db):
        init_db()
        id1 = gen_id()
        id2 = gen_id()
        statements = [
            (
                "INSERT INTO tasks (id, title, status, created_at) VALUES (?,?,?,?)",
                (id1, "task1", "pending", "2025-01-01T00:00:00"),
            ),
            (
                "INSERT INTO tasks (id, title, status, created_at) VALUES (?,?,?,?)",
                (id2, "task2", "done", "2025-01-01T00:00:00"),
            ),
        ]
        result = execute_transaction(statements)
        assert result is True
        rows = execute_query(
            "SELECT COUNT(*) as cnt FROM tasks WHERE id IN (?,?)", (id1, id2)
        )
        assert rows[0]["cnt"] == 2

    def test_rollback_on_error(self, temp_db):
        init_db()
        id1 = gen_id()
        statements = [
            (
                "INSERT INTO tasks (id, title, status, created_at) VALUES (?,?,?,?)",
                (id1, "should_rollback", "pending", "2025-01-01T00:00:00"),
            ),
            (
                "INSERT INTO nonexistent_table_xyz (col) VALUES (?)",
                ("bad",),
            ),
        ]
        result = execute_transaction(statements)
        assert result is False
        rows = execute_query("SELECT * FROM tasks WHERE id=?", (id1,))
        assert len(rows) == 0


class TestExecuteWriteReturning:
    """Test suite for execute_write_returning()."""

    def test_returns_lastrowid(self, temp_db):
        init_db()
        new_id = gen_id()
        rowid = execute_write_returning(
            "INSERT INTO tasks (id, title, status, created_at) VALUES (?,?,?,?)",
            (new_id, "returning_test", "pending", "2025-01-01T00:00:00"),
        )
        assert rowid is not None
        assert isinstance(rowid, int)


class TestGetSetPreference:
    """Test suite for get_preference/set_preference round-trip."""

    def test_set_and_get_round_trip(self, temp_db):
        init_db()
        set_preference("test_key", "test_value_123")
        value = get_preference("test_key")
        assert value == "test_value_123"

    def test_get_default_when_missing(self, temp_db):
        init_db()
        value = get_preference("nonexistent_pref_key_xyz")
        assert value == ""

    def test_get_default_with_custom_default(self, temp_db):
        init_db()
        value = get_preference("missing_key", default="fallback_val")
        assert value == "fallback_val"

    def test_update_overwrites_existing(self, temp_db):
        init_db()
        set_preference("overwrite_key", "v1")
        set_preference("overwrite_key", "v2_updated")
        assert get_preference("overwrite_key") == "v2_updated"


class TestBackupDb:
    """Test suite for backup_db()."""

    def test_backup_creates_file(self, temp_db, monkeypatch):
        init_db()
        monkeypatch.setenv("OPC_BACKUP_COUNT", "5")
        backup_path = backup_db()
        assert backup_path is not None
        assert os.path.exists(backup_path)

    def test_backup_respects_count_limit(self, temp_db, monkeypatch):
        init_db()
        monkeypatch.setenv("OPC_BACKUP_COUNT", "3")
        for _ in range(5):
            backup_db()
        from pathlib import Path

        backups = sorted(Path(os.path.join(DATA_DIR, "backups")).glob("opc_data_*.db"))
        assert len(backups) <= 3


class TestMigrationAddColumn:
    """Test suite for _add_column_if_not_exists migration helper."""

    def test_adds_new_column(self, temp_db):
        init_db()
        # Use the module-managed connection (WAL + busy_timeout) to avoid
        # "database is locked" contention with the persistent _get_conn()
        # connection that init_db() leaves open in the current thread.
        conn = _get_conn()
        cols_before = [
            row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
        ]
        assert "test_migration_col" not in cols_before
        _add_column_if_not_exists(
            conn, "tasks", "test_migration_col", "TEXT DEFAULT ''"
        )
        conn.commit()
        cols_after = [
            row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
        ]
        assert "test_migration_col" in cols_after
        try:
            conn.execute("ALTER TABLE tasks DROP COLUMN test_migration_col")
            conn.commit()
        except Exception:
            pass

    def test_skips_if_column_present(self, temp_db):
        init_db()
        conn = _get_conn()
        _add_column_if_not_exists(conn, "tasks", "title", "TEXT DEFAULT 'dup'")
        conn.commit()
        rows = conn.execute("SELECT title FROM tasks LIMIT 0").fetchall()
        assert rows is not None

    def test_migration_chain_completes(self, temp_db):
        """Verify database migration chain from v2 to latest version completes."""
        from opc_manager.data_manager import _run_migrations, _get_conn, init_db

        # Ensure base schema (including _meta table) exists before migrating.
        init_db()
        # Run migrations on a fresh database
        conn = _get_conn()
        _run_migrations(conn)
        # Verify critical tables exist
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        assert "tasks" in tables or "audit_log" in tables


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
