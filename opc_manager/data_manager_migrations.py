"""Database migrations, schema validation, and seed data for OPC-Agents.

Extracted from data_manager.py (v0.5.3) to clarify module boundaries while
keeping the public API intact. All functions here are re-exported by
data_manager.py, so existing imports and unittest.mock.patch paths
(e.g. `patch("opc_manager.data_manager._validate_sql")`) continue to work.

Design notes:
- `gen_id` is co-located here because `_seed_categories` depends on it.
  `data_manager.py` re-exports `gen_id` for backward compatibility.
- Migration functions receive `sqlite3.Connection` as input; they do not
  open connections themselves, keeping the connection lifecycle in
  `data_manager._get_conn()`.
- SQL validation (`_validate_sql`, `_validate_identifier`) lives here
  because migrations are the primary consumer of dynamic SQL (ALTER TABLE,
  PRAGMA table_info). `data_manager.execute_*` re-exports them.
"""

import logging
import re
import sqlite3
import time
import uuid
from typing import Callable

logger = logging.getLogger(__name__)

# Current schema version. Bump when adding new migrations.
_db_version = 7

# SQL identifier whitelist (prevents injection in dynamic SQL).
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Detects common injection patterns: string concatenation with quotes,
# semicolons in values, and f-string interpolation markers.
_UNSAFE_SQL_RE = re.compile(
    r"(?:'\s*\+\s*|;\s*(?:DROP|ALTER|CREATE|DELETE|INSERT|UPDATE)|\{.*\})"
)


def gen_id() -> str:
    """Generate a 16-char hex UUID for primary keys.

    Co-located in migrations module because `_seed_categories` depends on
    it. Re-exported by data_manager.py for backward compatibility.
    """
    return uuid.uuid4().hex[:16]


def _validate_sql(sql: str) -> None:
    """Reject SQL that appears to use string concatenation or interpolation
    instead of parameterized queries (? placeholders)."""
    if _UNSAFE_SQL_RE.search(sql):
        raise ValueError(
            "Unsafe SQL detected — use parameterized queries with '?' placeholders. "
            f"Rejected SQL: {sql[:100]}..."
        )


def _validate_identifier(name: str) -> str:
    """Validate SQL identifier to prevent injection in dynamic SQL."""
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


def _add_column_if_not_exists(
    conn: sqlite3.Connection, table: str, column: str, col_type: str
) -> None:
    """Add column to table if it does not already exist (idempotent)."""
    try:
        safe_table = _validate_identifier(table)
        safe_column = _validate_identifier(column)
        cols = [
            row[1]
            for row in conn.execute(f"PRAGMA table_info({safe_table})").fetchall()
        ]
        if safe_column not in cols:
            conn.execute(
                f"ALTER TABLE {safe_table} ADD COLUMN {safe_column} {col_type}"
            )
    except sqlite3.OperationalError as e:
        logger.warning(
            "[DataManager] Migration add column %s.%s failed: %s", table, column, e
        )


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Run pending schema migrations from current version to _db_version."""
    row = conn.execute("SELECT value FROM _meta WHERE key='db_version'").fetchone()
    current = int(row["value"]) if row else 0
    if current < _db_version:
        if current < 3:
            _migrate_v2_to_v3(conn)
        if current < 4:
            _migrate_v3_to_v4(conn)
        if current < 5:
            _migrate_v4_to_v5(conn)
        if current < 6:
            _migrate_v5_to_v6(conn)
        if current < 7:
            _migrate_v6_to_v7(conn)
        conn.execute(
            "INSERT OR REPLACE INTO _meta (key, value) VALUES ('db_version', ?)",
            (str(_db_version),),
        )
        logger.info("[DataManager] Migrated DB from v%d to v%d", current, _db_version)


def _migrate_v2_to_v3(conn: sqlite3.Connection) -> None:
    """v2→v3: external_skills metadata + interaction_log session tracking."""
    _add_column_if_not_exists(conn, "external_skills", "author", "TEXT DEFAULT ''")
    _add_column_if_not_exists(conn, "external_skills", "category", "TEXT DEFAULT ''")
    _add_column_if_not_exists(conn, "external_skills", "permissions", "TEXT DEFAULT ''")
    _add_column_if_not_exists(conn, "external_skills", "downloads", "INTEGER DEFAULT 0")
    _add_column_if_not_exists(conn, "external_skills", "rating", "REAL DEFAULT 0.0")
    _add_column_if_not_exists(conn, "interaction_log", "session_id", "TEXT DEFAULT ''")
    _add_column_if_not_exists(
        conn, "interaction_log", "duration_ms", "REAL DEFAULT 0.0"
    )
    _add_column_if_not_exists(
        conn, "interaction_log", "error_message", "TEXT DEFAULT ''"
    )


def _migrate_v3_to_v4(conn: sqlite3.Connection) -> None:
    """v3→v4: calendar_events extended attributes."""
    _add_column_if_not_exists(
        conn, "calendar_events", "duration_min", "INTEGER DEFAULT 60"
    )
    _add_column_if_not_exists(conn, "calendar_events", "description", "TEXT DEFAULT ''")
    _add_column_if_not_exists(conn, "calendar_events", "repeat", "TEXT DEFAULT ''")


def _migrate_v4_to_v5(conn: sqlite3.Connection) -> None:
    """v4→v5: invoices.proposal_id + follow_ups table."""
    _add_column_if_not_exists(conn, "invoices", "proposal_id", "TEXT DEFAULT ''")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS follow_ups (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            content TEXT DEFAULT '',
            follow_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        )
    """)


def _migrate_v5_to_v6(conn: sqlite3.Connection) -> None:
    """v5→v6: audit_log table + performance indexes."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            user_id TEXT DEFAULT 'default',
            timestamp REAL NOT NULL,
            operation_type TEXT NOT NULL,
            skill_id TEXT,
            input_hash TEXT,
            input_summary TEXT,
            output_summary TEXT,
            duration_ms INTEGER DEFAULT 0,
            status TEXT DEFAULT 'success',
            error_msg TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_log(session_id);
        CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_finance_date ON finance_records(date);
        CREATE INDEX IF NOT EXISTS idx_finance_type ON finance_records(type);
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);
    """)


def _migrate_v6_to_v7(conn: sqlite3.Connection) -> None:
    """v6→v7: audit_log chain hash columns (prev_hash, current_hash).

    Chain hash provides tamper evidence: each record's current_hash =
    sha256(prev_hash + timestamp + operation_type + input_hash), prev_hash
    = previous record's current_hash. Legacy v6 rows have empty strings
    in both columns (backward compatible).
    """
    _add_column_if_not_exists(conn, "audit_log", "prev_hash", "TEXT DEFAULT ''")
    _add_column_if_not_exists(conn, "audit_log", "current_hash", "TEXT DEFAULT ''")


def _seed_categories(conn: sqlite3.Connection, gen_id_fn: Callable[[], str]) -> None:
    """Seed default finance_categories if table is empty.

    Args:
        conn: Active sqlite3.Connection.
        gen_id_fn: Callable returning unique ID strings (decoupled from
            data_manager.gen_id to avoid circular import).
    """
    count = conn.execute("SELECT COUNT(*) FROM finance_categories").fetchone()[0]
    if count > 0:
        return
    income_cats = [
        ("咨询费", ""),
        ("培训费", ""),
        ("产品销售", ""),
        ("课程收入", ""),
        ("广告分成", ""),
        ("版税/授权", ""),
        ("其他收入", ""),
    ]
    expense_cats = [
        ("工具订阅", ""),
        ("办公设备", ""),
        ("差旅交通", ""),
        ("设计素材", ""),
        ("营销推广", ""),
        ("税费", ""),
        ("通讯网络", ""),
        ("其他支出", ""),
    ]
    for name, icon in income_cats:
        conn.execute(
            "INSERT OR IGNORE INTO finance_categories (id,type,name,icon) VALUES (?,?,?,?)",
            (gen_id_fn(), "income", name, icon),
        )
    for name, icon in expense_cats:
        conn.execute(
            "INSERT OR IGNORE INTO finance_categories (id,type,name,icon) VALUES (?,?,?,?)",
            (gen_id_fn(), "expense", name, icon),
        )


def _seed_templates(conn: sqlite3.Connection) -> None:
    """Seed default email_templates if table is empty."""
    count = conn.execute("SELECT COUNT(*) FROM email_templates").fetchone()[0]
    if count > 0:
        return
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    templates = [
        (
            "跟进邮件",
            "关于{topic}的跟进",
            "{name}您好，\n\n关于{topic}，想跟您同步一下最新进展。\n\n{content}\n\n期待您的回复。\n\n此致",
            "{name},{topic},{content}",
        ),
        (
            "感谢邮件",
            "感谢{event}",
            "{name}您好，\n\n非常感谢{event}，期待后续合作。\n\n此致",
            "{name},{event}",
        ),
        (
            "报价邮件",
            "{company} - 服务报价",
            "{name}您好，\n\n根据我们之前的沟通，以下是服务报价：\n\n{content}\n\n如有任何问题，请随时联系。\n\n此致",
            "{name},{company},{content}",
        ),
    ]
    for name, subject, body, variables in templates:
        conn.execute(
            "INSERT OR IGNORE INTO email_templates (name,subject,body,variables,created_at) VALUES (?,?,?,?,?)",
            (name, subject, body, variables, now),
        )
