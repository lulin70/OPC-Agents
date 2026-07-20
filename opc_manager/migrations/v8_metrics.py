"""DB migration v8: metrics collection schema (5 tables + indexes + trigger + views).

Implements ADR-004 §3.5 / DDL_metrics_v8.md §3-§5.

Migration steps:
1. Check current db_version (must be 7 or fresh; raise otherwise).
2. Backup DB file to ``<db_path>.v7.bak.<timestamp>``.
3. Execute all DDL within a single BEGIN/COMMIT transaction.
4. Update ``_meta.db_version=8`` and append to ``schema_version``.
5. On failure: ROLLBACK + restore backup + re-raise.

Idempotency: every CREATE statement uses IF NOT EXISTS, so re-running
migrate_v8 on an already-migrated DB is a no-op (early return when
db_version == 8).

Entry point: ``opc_manager.data_manager._run_migrations`` delegates here
when ``current < 8``. ``MetricsCollector._ensure_tables`` reuses the DDL
constants to create tables on a standalone metrics.db without the full
migration chain.
"""

import logging
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from typing import List

logger = logging.getLogger(__name__)

V8_VERSION = 8
V8_DESCRIPTION = "metrics"
V8_APPLIED_AT = "2026-07-19"

# ---------------------------------------------------------------------------
# DDL statements (each entry is one executable SQL string)
# ---------------------------------------------------------------------------
# Source: DDL_metrics_v8.md §3 (tables), §4 (trigger), §5 (views).
# Statements are stored as a list (not a single script) so migrate_v8 can
# run them inside an explicit BEGIN/COMMIT transaction and have ROLLBACK
# actually undo partial work (executescript() implicitly commits first).

DDL_TABLES: List[str] = [
    # §3.1 metrics_activation
    """
    CREATE TABLE IF NOT EXISTS metrics_activation (
        id                        TEXT PRIMARY KEY,
        user_id                   TEXT NOT NULL,
        onboarding_completed_at   TEXT NOT NULL,
        first_use_at              TEXT NOT NULL,
        activation_criteria_met   INTEGER DEFAULT 0,
        activation_met_at         TEXT,
        days_to_activate          INTEGER,
        metadata                  TEXT,
        created_at                TEXT NOT NULL,
        updated_at                TEXT NOT NULL
    )
    """,
    # §3.2 metrics_upgrade
    """
    CREATE TABLE IF NOT EXISTS metrics_upgrade (
        id            TEXT PRIMARY KEY,
        user_id       TEXT NOT NULL,
        from_version  TEXT,
        to_version    TEXT NOT NULL,
        upgrade_at    TEXT NOT NULL,
        license_key   TEXT,
        metadata      TEXT,
        created_at    TEXT NOT NULL
    )
    """,
    # §3.3 metrics_flywheel
    """
    CREATE TABLE IF NOT EXISTS metrics_flywheel (
        id              TEXT PRIMARY KEY,
        user_id         TEXT NOT NULL,
        flywheel_level  INTEGER NOT NULL,
        previous_level  INTEGER,
        level_up_at     TEXT NOT NULL,
        skills_used     TEXT,
        metadata        TEXT,
        created_at      TEXT NOT NULL
    )
    """,
    # §3.4 metrics_payment
    """
    CREATE TABLE IF NOT EXISTS metrics_payment (
        id             TEXT PRIMARY KEY,
        user_id        TEXT NOT NULL,
        payment_status TEXT NOT NULL,
        amount         REAL,
        currency       TEXT DEFAULT 'CNY',
        paid_at        TEXT,
        metadata       TEXT,
        created_at     TEXT NOT NULL
    )
    """,
    # §3.5 metrics_experience (3 experience metrics + NPS)
    """
    CREATE TABLE IF NOT EXISTS metrics_experience (
        id           TEXT PRIMARY KEY,
        user_id      TEXT NOT NULL,
        metric_type  TEXT NOT NULL,
        score        REAL NOT NULL,
        skill_id     TEXT,
        session_id   TEXT,
        comment      TEXT,
        timestamp    TEXT NOT NULL,
        metadata     TEXT,
        created_at   TEXT NOT NULL
    )
    """,
]

DDL_INDEXES: List[str] = [
    # metrics_activation indexes
    "CREATE INDEX IF NOT EXISTS idx_activation_user_id     ON metrics_activation(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_activation_created_at  ON metrics_activation(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_activation_user_created ON metrics_activation(user_id, created_at DESC)",
    # metrics_upgrade indexes
    "CREATE INDEX IF NOT EXISTS idx_upgrade_user_id    ON metrics_upgrade(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_upgrade_upgrade_at ON metrics_upgrade(upgrade_at)",
    "CREATE INDEX IF NOT EXISTS idx_upgrade_from_to    ON metrics_upgrade(from_version, to_version)",
    # metrics_flywheel indexes
    "CREATE INDEX IF NOT EXISTS idx_flywheel_user_id         ON metrics_flywheel(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_flywheel_level           ON metrics_flywheel(flywheel_level)",
    "CREATE INDEX IF NOT EXISTS idx_flywheel_level_up_at     ON metrics_flywheel(level_up_at)",
    "CREATE INDEX IF NOT EXISTS idx_flywheel_user_level_time ON metrics_flywheel(user_id, flywheel_level, level_up_at DESC)",
    # metrics_payment indexes
    "CREATE INDEX IF NOT EXISTS idx_payment_user_id        ON metrics_payment(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_payment_status         ON metrics_payment(payment_status)",
    "CREATE INDEX IF NOT EXISTS idx_payment_paid_at        ON metrics_payment(paid_at)",
    "CREATE INDEX IF NOT EXISTS idx_payment_status_paid_at ON metrics_payment(payment_status, paid_at)",
    # metrics_experience indexes
    "CREATE INDEX IF NOT EXISTS idx_experience_user_id     ON metrics_experience(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_experience_metric_type ON metrics_experience(metric_type)",
    "CREATE INDEX IF NOT EXISTS idx_experience_timestamp   ON metrics_experience(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_experience_skill_id    ON metrics_experience(skill_id)",
    "CREATE INDEX IF NOT EXISTS idx_experience_type_time   ON metrics_experience(metric_type, timestamp DESC)",
    "CREATE INDEX IF NOT EXISTS idx_experience_user_type   ON metrics_experience(user_id, metric_type)",
]

DDL_TRIGGERS: List[str] = [
    # §4.1 trg_activation_updated_at
    # WHEN NEW.updated_at = OLD.updated_at prevents infinite recursion:
    # the trigger's own UPDATE changes updated_at, so next fire skips.
    """
    CREATE TRIGGER IF NOT EXISTS trg_activation_updated_at
        AFTER UPDATE ON metrics_activation
        FOR EACH ROW
        WHEN NEW.updated_at = OLD.updated_at
    BEGIN
        UPDATE metrics_activation
        SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = NEW.id;
    END
    """,
]

DDL_VIEWS: List[str] = [
    # §5.1 view_activation_rate
    """
    CREATE VIEW IF NOT EXISTS view_activation_rate AS
    SELECT
        COUNT(DISTINCT user_id) AS total_onboarded,
        COUNT(DISTINCT CASE WHEN activation_criteria_met = 1 THEN user_id END) AS activated_users,
        ROUND(
            CAST(COUNT(DISTINCT CASE WHEN activation_criteria_met = 1 THEN user_id END) AS REAL)
            / MAX(COUNT(DISTINCT user_id), 1) * 100, 2
        ) AS activation_rate_pct,
        ROUND(AVG(days_to_activate), 2) AS avg_days_to_activate
    FROM metrics_activation
    """,
    # §5.2 view_upgrade_rate
    """
    CREATE VIEW IF NOT EXISTS view_upgrade_rate AS
    SELECT
        (SELECT COUNT(DISTINCT user_id) FROM metrics_activation WHERE activation_criteria_met = 1)
            AS activated_users,
        COUNT(DISTINCT u.user_id) AS upgraded_users,
        ROUND(
            CAST(COUNT(DISTINCT u.user_id) AS REAL)
            / MAX((SELECT COUNT(DISTINCT user_id) FROM metrics_activation WHERE activation_criteria_met = 1), 1)
            * 100, 2
        ) AS upgrade_rate_pct,
        COUNT(DISTINCT CASE WHEN u.from_version = 'basic' THEN u.user_id END) AS from_basic_count,
        COUNT(DISTINCT CASE WHEN u.from_version = 'pro_trial' THEN u.user_id END) AS from_trial_count
    FROM metrics_upgrade u
    """,
    # §5.3 view_flywheel_rate
    """
    CREATE VIEW IF NOT EXISTS view_flywheel_rate AS
    WITH latest_flywheel AS (
        SELECT user_id, flywheel_level
        FROM (
            SELECT user_id, flywheel_level, level_up_at,
                   ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY level_up_at DESC) AS rn
            FROM metrics_flywheel
        )
        WHERE rn = 1
    )
    SELECT
        (SELECT COUNT(DISTINCT user_id) FROM metrics_activation WHERE activation_criteria_met = 1)
            AS activated_users,
        COUNT(DISTINCT CASE WHEN flywheel_level >= 2 THEN user_id END) AS flywheel_users,
        ROUND(
            CAST(COUNT(DISTINCT CASE WHEN flywheel_level >= 2 THEN user_id END) AS REAL)
            / MAX((SELECT COUNT(DISTINCT user_id) FROM metrics_activation WHERE activation_criteria_met = 1), 1)
            * 100, 2
        ) AS flywheel_rate_pct,
        COUNT(DISTINCT CASE WHEN flywheel_level = 1 THEN user_id END) AS level_1_count,
        COUNT(DISTINCT CASE WHEN flywheel_level = 2 THEN user_id END) AS level_2_count,
        COUNT(DISTINCT CASE WHEN flywheel_level = 3 THEN user_id END) AS level_3_count,
        COUNT(DISTINCT CASE WHEN flywheel_level = 4 THEN user_id END) AS level_4_count
    FROM latest_flywheel
    """,
    # §5.4 view_payment_rate
    """
    CREATE VIEW IF NOT EXISTS view_payment_rate AS
    SELECT
        (SELECT COUNT(DISTINCT user_id) FROM metrics_activation WHERE activation_criteria_met = 1)
            AS activated_users,
        COUNT(DISTINCT CASE WHEN payment_status = 'paid' THEN user_id END) AS paid_users,
        ROUND(
            CAST(COUNT(DISTINCT CASE WHEN payment_status = 'paid' THEN user_id END) AS REAL)
            / MAX((SELECT COUNT(DISTINCT user_id) FROM metrics_activation WHERE activation_criteria_met = 1), 1)
            * 100, 2
        ) AS payment_rate_pct,
        COUNT(DISTINCT CASE WHEN payment_status = 'trial' THEN user_id END) AS trial_count,
        COUNT(DISTINCT CASE WHEN payment_status = 'cancelled' THEN user_id END) AS cancelled_count,
        COUNT(DISTINCT CASE WHEN payment_status = 'refunded' THEN user_id END) AS refunded_count,
        ROUND(SUM(CASE WHEN payment_status = 'paid' THEN amount ELSE 0 END), 2) AS total_paid_amount
    FROM metrics_payment
    """,
    # §5.5 view_nps_score
    """
    CREATE VIEW IF NOT EXISTS view_nps_score AS
    SELECT
        COUNT(*) AS total_responses,
        SUM(CASE WHEN score >= 9 THEN 1 ELSE 0 END) AS promoters,
        SUM(CASE WHEN score BETWEEN 7 AND 8 THEN 1 ELSE 0 END) AS passives,
        SUM(CASE WHEN score <= 6 THEN 1 ELSE 0 END) AS detractors,
        ROUND(CAST(SUM(CASE WHEN score >= 9 THEN 1 ELSE 0 END) AS REAL) / MAX(COUNT(*), 1) * 100, 2) AS promoter_pct,
        ROUND(CAST(SUM(CASE WHEN score <= 6 THEN 1 ELSE 0 END) AS REAL) / MAX(COUNT(*), 1) * 100, 2) AS detractor_pct,
        ROUND(
            (CAST(SUM(CASE WHEN score >= 9 THEN 1 ELSE 0 END) AS REAL)
             - CAST(SUM(CASE WHEN score <= 6 THEN 1 ELSE 0 END) AS REAL))
            / MAX(COUNT(*), 1) * 100, 2
        ) AS nps_score
    FROM metrics_experience WHERE metric_type = 'nps'
    """,
    # §5.6 view_experience_avg
    """
    CREATE VIEW IF NOT EXISTS view_experience_avg AS
    SELECT
        metric_type,
        ROUND(AVG(score), 2) AS avg_score,
        COUNT(*) AS response_count,
        ROUND(SUM(CASE WHEN score >= 4 THEN 1 ELSE 0 END) * 100.0 / MAX(COUNT(*), 1), 2) AS satisfied_pct,
        ROUND(MIN(score), 2) AS min_score,
        ROUND(MAX(score), 2) AS max_score
    FROM metrics_experience
    WHERE metric_type IN ('dialogue_naturalness', 'result_satisfaction', 'proactive_service')
    GROUP BY metric_type
    """,
]

# Combined list for MetricsCollector._ensure_tables (standalone init).
ALL_DDL: List[str] = DDL_TABLES + DDL_INDEXES + DDL_TRIGGERS + DDL_VIEWS

# schema_version table DDL (separate; created in migrate_v8 only)
_DDL_SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at  TEXT NOT NULL
)
"""


def _read_db_version(conn: sqlite3.Connection) -> int:
    """Return current db_version from ``_meta`` table, or 0 if not initialized."""
    try:
        row = conn.execute("SELECT value FROM _meta WHERE key='db_version'").fetchone()
        if row is None:
            return 0
        return int(row[0]) if row[0] is not None else 0
    except sqlite3.Error:
        # _meta table doesn't exist yet (fresh DB)
        return 0


def _ensure_meta_table(conn: sqlite3.Connection) -> None:
    """Create ``_meta`` table if missing (standalone metrics.db use case)."""
    conn.execute("CREATE TABLE IF NOT EXISTS _meta (key TEXT PRIMARY KEY, value TEXT)")


def _get_db_path(conn: sqlite3.Connection) -> str:
    """Return the on-disk path of the connection's main database."""
    row = conn.execute("PRAGMA database_list").fetchone()
    if row and row[2]:
        return row[2]
    return ""


def _create_backup(db_path: str) -> str:
    """Copy ``db_path`` to ``<db_path>.v7.bak.<timestamp>`` and return backup path."""
    backup_dir = os.path.join(os.path.dirname(db_path) or ".", "backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = os.path.join(backup_dir, f"opc_data.db.v7.bak.{ts}")
    shutil.copy2(db_path, backup_path)
    logger.info("[migrate_v8] Backup created: %s", backup_path)
    return backup_path


def _restore_backup(backup_path: str, db_path: str) -> None:
    """Restore ``db_path`` from ``backup_path`` (best-effort)."""
    if not backup_path or not os.path.exists(backup_path):
        return
    try:
        shutil.copy2(backup_path, db_path)
        logger.info("[migrate_v8] Backup restored: %s", backup_path)
    except OSError as e:
        logger.error("[migrate_v8] Backup restore failed: %s", e)


def migrate_v8(conn: sqlite3.Connection) -> None:
    """v7 → v8 migration: create metrics schema (5 tables + 20 indexes +
    1 trigger + 6 views).

    Idempotent: re-running on a v8 DB is a no-op.
    Transactional: all DDL runs inside BEGIN/COMMIT; on failure ROLLBACK
    undoes partial work and the v7 backup is restored.

    Args:
        conn: open sqlite3.Connection to the main DB.

    Raises:
        RuntimeError: if current db_version is neither 7 nor 0 nor 8
            (must run prior migrations first), or if the migration fails
            (already rolled back + backup restored).
    """
    _ensure_meta_table(conn)
    current = _read_db_version(conn)

    # Idempotent: already at v8, nothing to do.
    if current == V8_VERSION:
        logger.info("[migrate_v8] Already at v%d, skipping.", V8_VERSION)
        return

    # Version guard: only allow upgrading from v7 or fresh DB (v0).
    if current != 7 and current != 0:
        raise RuntimeError(
            f"[migrate_v8] expected db_version=7 (or fresh 0), got v{current}. "
            f"Run prior migrations first."
        )

    logger.info("[migrate_v8] Current version: v%d, target: v%d", current, V8_VERSION)

    # Step 2: backup DB file before touching schema.
    db_path = _get_db_path(conn)
    backup_path = ""
    if db_path and os.path.exists(db_path):
        backup_path = _create_backup(db_path)

    # Step 3-7: execute all DDL inside a single transaction.
    try:
        conn.execute("BEGIN")
        # Tables
        for stmt in DDL_TABLES:
            conn.execute(stmt)
        # Indexes
        for stmt in DDL_INDEXES:
            conn.execute(stmt)
        # Triggers
        for stmt in DDL_TRIGGERS:
            conn.execute(stmt)
        # Views
        for stmt in DDL_VIEWS:
            conn.execute(stmt)
        # schema_version table
        conn.execute(_DDL_SCHEMA_VERSION_TABLE)
        # Update _meta.db_version
        conn.execute(
            "INSERT OR REPLACE INTO _meta (key, value) VALUES ('db_version', ?)",
            (str(V8_VERSION),),
        )
        # Append migration record
        conn.execute(
            "INSERT OR REPLACE INTO schema_version "
            "(version, description, applied_at) VALUES (?, ?, ?)",
            (V8_VERSION, V8_DESCRIPTION, V8_APPLIED_AT),
        )
        conn.commit()
        logger.info("[migrate_v8] Migration v%d → v%d completed", current, V8_VERSION)
    except Exception as exc:
        # Step 8: failure path — rollback transaction + restore backup.
        logger.error("[migrate_v8] Migration failed: %s. Rolling back...", exc)
        try:
            conn.rollback()
        except sqlite3.Error as rollback_err:
            logger.error("[migrate_v8] Rollback failed: %s", rollback_err)
        if backup_path:
            _restore_backup(backup_path, db_path)
        raise RuntimeError(f"migrate_v8 failed and rolled back: {exc}") from exc


__all__ = [
    "V8_VERSION",
    "V8_DESCRIPTION",
    "V8_APPLIED_AT",
    "DDL_TABLES",
    "DDL_INDEXES",
    "DDL_TRIGGERS",
    "DDL_VIEWS",
    "ALL_DDL",
    "migrate_v8",
]
