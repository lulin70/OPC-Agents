import base64
import hashlib
import logging
import os
import re
import sqlite3
import stat
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = os.environ.get(
    "OPC_DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
)
DB_PATH = os.path.join(DATA_DIR, "opc_data.db")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

_db_lock = threading.RLock()
_local = threading.local()
_db_version = 6
_db_initialized = False
_db_init_lock = threading.Lock()

_ENCRYPTION_KEY_ENV = "OPC_ENCRYPTION_KEY"
_fallback_key = None


def _get_encryption_key() -> Optional[bytes]:
    global _fallback_key

    # 优先通过 SettingsManager 获取（不通过 os.environ）
    # ARCHITECTURE NOTE: This is a delayed import to avoid circular dependency.
    # Dependency direction: data_manager → settings (one-way only).
    # settings.py must NEVER import from data_manager.
    try:
        from opc_manager.settings import get_settings

        settings = get_settings()
        key_str = settings.get_encryption_key()
        if key_str:
            return hashlib.sha256(key_str.encode()).digest()
    except Exception as e:
        logger.warning("[DataManager] SHA256 key derivation failed: %s", e)

    # 回退到 os.environ（兼容外部设置的环境变量）
    key_str = os.environ.get(_ENCRYPTION_KEY_ENV, "")
    if key_str:
        return hashlib.sha256(key_str.encode()).digest()

    # 无显式密钥时，自动派生基于机器特征的密钥
    # 保证数据至少是加密存储的，而非明文
    if _fallback_key is None:
        machine_id = _derive_machine_key()
        _fallback_key = hashlib.sha256(
            f"opc-agents-auto-{machine_id}".encode()
        ).digest()
        logger.info(
            "[SECURITY] OPC_ENCRYPTION_KEY not set. Using auto-derived key "
            "from machine identity. Set OPC_ENCRYPTION_KEY explicitly for "
            "portable encrypted data."
        )
    return _fallback_key


def _derive_machine_key() -> str:
    """Derive a machine-specific key from stable system identifiers."""
    components = []
    for attr in ("node", "machine", "system"):
        val = getattr(os, attr, None)
        if val:
            components.append(str(val))
    # Add username as additional entropy
    try:
        import getpass

        components.append(getpass.getuser())
    except Exception:
        pass
    # Add home directory path as machine-specific entropy
    home = os.path.expanduser("~")
    if home:
        components.append(home)
    return ":".join(components) if components else "default-opc-key"


def encrypt_field(plaintext: str) -> str:
    if not plaintext:
        return ""
    key = _get_encryption_key()
    if key is None:
        # 与三语 README 文档一致：未设置 OPC_ENCRYPTION_KEY 时抛 RuntimeError（fail-closed）
        # _get_encryption_key() 有机器特征 fallback，正常情况不会返回 None；
        # 此分支为防御性编程，确保密钥派生彻底失败时拒绝明文落库
        raise RuntimeError(
            "OPC_ENCRYPTION_KEY is not set. encrypt_field() refuses to "
            "store plaintext. Set OPC_ENCRYPTION_KEY in .env or via "
            "SettingsManager.get_encryption_key()."
        )
    try:
        from cryptography.fernet import Fernet

        fernet_key = base64.urlsafe_b64encode(key)
        f = Fernet(fernet_key)
        return f.encrypt(plaintext.encode()).decode()
    except Exception as e:
        # [SECURITY] Fail-closed (P0-1 sibling fix, 2026-06-27):
        # 与 key is None 分支一致，加密失败时拒绝明文落库，
        # 避免 Fernet 内部异常导致敏感数据静默降级为明文存储。
        logger.error("[SECURITY] [DataManager] Encryption failed, refusing to store plaintext: %s", e)
        raise RuntimeError(
            f"encrypt_field() encryption failed: {e}. Refusing to store plaintext. "
            f"Check OPC_ENCRYPTION_KEY and cryptography package installation."
        ) from e


def decrypt_field(ciphertext: str) -> Optional[str]:
    if not ciphertext:
        return ""
    key = _get_encryption_key()
    if key is None:
        # 无密钥时返回原文（可能已经是明文）
        return ciphertext
    try:
        from cryptography.fernet import Fernet, InvalidToken

        fernet_key = base64.urlsafe_b64encode(key)
        f = Fernet(fernet_key)
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        # Heuristic: Fernet ciphertext always starts with 'gAAAA' (base64 of version byte 0x80).
        # If the value looks like a Fernet token (starts with gAAAA), it's a genuine
        # decryption failure (wrong key). Otherwise, it was likely stored as plaintext
        # before the encryption key was set — return as-is to avoid data loss.
        if ciphertext.startswith("gAAAA"):
            logger.error(
                "[SECURITY] Decryption failed for Fernet token — wrong encryption key?"
            )
            return None
        # Not a Fernet token — but could be garbage or old plaintext.
        # Only return as plaintext if it looks like readable text (no special chars).
        import unicodedata

        printable_ratio = sum(
            1
            for c in ciphertext[:50]
            if unicodedata.category(c).startswith(("L", "N", "P", "Zs")) or c in " \t\n"
        ) / min(len(ciphertext), 50)
        if printable_ratio > 0.8:
            logger.warning(
                "[SECURITY] Value is not a Fernet token — likely stored before "
                "encryption key was set. Returning raw value."
            )
            return ciphertext
        logger.error("[SECURITY] Decryption failed for non-printable value")
        return None
    except Exception as e:
        logger.error("[SECURITY] Decryption failed: %s", e)
        return None


def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        # Busy timeout is bounded to avoid cascading hangs when multiple
        # background writer threads (e.g. AuditLog) contend for the same DB.
        conn = sqlite3.connect(
            DB_PATH,
            timeout=5.0,
            check_same_thread=False,
        )
        conn.execute("PRAGMA busy_timeout = 5000")
        mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        if mode.lower() != "wal":
            logger.warning("[DataManager] journal_mode=%s, WAL not active", mode)
        # NORMAL synchronous with WAL provides durability without the
        # full performance penalty of FULL, reducing writer contention.
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        _local.conn = conn
        try:
            os.chmod(DB_PATH, stat.S_IRUSR | stat.S_IWUSR)
        except OSError as e:
            logger.debug("[DataManager] chmod failed: %s", e)
    return _local.conn


import functools


def _ensure_db(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not _db_initialized:
            init_db()
        return func(*args, **kwargs)

    return wrapper


def init_db() -> None:
    global _db_initialized
    with _db_init_lock:
        if _db_initialized:
            return
        conn = _get_conn()
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS _meta (key TEXT PRIMARY KEY, value TEXT);

        CREATE TABLE IF NOT EXISTS finance_records (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            source TEXT DEFAULT '',
            date TEXT NOT NULL,
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS finance_categories (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
            name TEXT NOT NULL,
            icon TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            priority INTEGER NOT NULL DEFAULT 2 CHECK(priority BETWEEN 0 AND 3),
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','in_progress','done','cancelled')),
            due_date TEXT,
            tags TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            company TEXT DEFAULT '',
            title TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            source TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'potential' CHECK(status IN ('potential','first_deal','active','silent','lost')),
            created_at TEXT NOT NULL,
            last_contact TEXT
        );

        CREATE TABLE IF NOT EXISTS deals (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT DEFAULT '',
            amount REAL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'negotiating' CHECK(status IN ('negotiating','closed_won','closed_lost')),
            created_at TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS email_history (
            id TEXT PRIMARY KEY,
            to_addr TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'sent' CHECK(status IN ('sent','failed','draft')),
            template_name TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS email_templates (
            name TEXT PRIMARY KEY,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            variables TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS social_content (
            id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            topic TEXT DEFAULT '',
            title TEXT DEFAULT '',
            body TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','published')),
            published_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS proposals (
            id TEXT PRIMARY KEY,
            client_name TEXT NOT NULL,
            service_type TEXT DEFAULT '通用',
            items TEXT DEFAULT '',
            total REAL DEFAULT 0,
            valid_days INTEGER DEFAULT 30,
            valid_until TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','sent','accepted','rejected','expired')),
            markdown TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS invoices (
            id TEXT PRIMARY KEY,
            invoice_no TEXT NOT NULL UNIQUE,
            client_name TEXT NOT NULL,
            amount REAL NOT NULL,
            item TEXT DEFAULT '',
            tax_rate REAL DEFAULT 0.06,
            tax_amount REAL DEFAULT 0,
            total_with_tax REAL DEFAULT 0,
            proposal_id TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','paid','cancelled')),
            markdown TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS follow_ups (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            content TEXT DEFAULT '',
            follow_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS calendar_events (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            event_date TEXT NOT NULL,
            event_time TEXT DEFAULT '',
            reminder_min INTEGER DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','cancelled')),
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS competitors (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            url TEXT DEFAULT '',
            keywords TEXT DEFAULT '',
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS competitor_snapshots (
            id TEXT PRIMARY KEY,
            competitor_id TEXT NOT NULL,
            changes TEXT DEFAULT '',
            source TEXT DEFAULT '手动记录',
            created_at TEXT NOT NULL,
            FOREIGN KEY (competitor_id) REFERENCES competitors(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS pricing_records (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            method TEXT DEFAULT '',
            price REAL DEFAULT 0,
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tax_reminders (
            id TEXT PRIMARY KEY,
            task TEXT NOT NULL,
            deadline TEXT NOT NULL,
            tax_type TEXT DEFAULT '增值税',
            amount_estimate REAL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','completed')),
            completed_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS knowledge_articles (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            category TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','published','archived')),
            word_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_preferences (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS external_skills (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            source TEXT DEFAULT '',
            version TEXT DEFAULT '',
            skill_config TEXT DEFAULT '',
            trust_level TEXT DEFAULT 'unverified',
            installed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS interaction_log (
            id TEXT PRIMARY KEY,
            intent_type TEXT NOT NULL,
            goal TEXT DEFAULT '',
            skill_used TEXT NOT NULL,
            success INTEGER DEFAULT 0,
            user_feedback TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS consensus_decisions (
            id TEXT PRIMARY KEY,
            timestamp REAL NOT NULL,
            opinion_count INTEGER DEFAULT 0,
            decision_type TEXT NOT NULL,
            approved INTEGER DEFAULT 0,
            confidence REAL DEFAULT 0.0,
            detail TEXT DEFAULT ''
        );
    """)
        _run_migrations(conn)
        _seed_categories(conn)
        _seed_templates(conn)
        conn.commit()
        _db_initialized = True
        logger.info("[DataManager] Database initialized (v%d)", _db_version)


def _run_migrations(conn: sqlite3.Connection) -> None:
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
        conn.execute(
            "INSERT OR REPLACE INTO _meta (key, value) VALUES ('db_version', ?)",
            (str(_db_version),),
        )
        logger.info("[DataManager] Migrated DB from v%d to v%d", current, _db_version)


def _migrate_v2_to_v3(conn: sqlite3.Connection) -> None:
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
    _add_column_if_not_exists(
        conn, "calendar_events", "duration_min", "INTEGER DEFAULT 60"
    )
    _add_column_if_not_exists(conn, "calendar_events", "description", "TEXT DEFAULT ''")
    _add_column_if_not_exists(conn, "calendar_events", "repeat", "TEXT DEFAULT ''")


def _migrate_v4_to_v5(conn: sqlite3.Connection) -> None:
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
    """)


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# SQL that must use parameterized queries (? placeholders).
# Detects common injection patterns: string concatenation with quotes,
# semicolons in values, and f-string interpolation markers.
_UNSAFE_SQL_RE = re.compile(
    r"(?:'\s*\+\s*|;\s*(?:DROP|ALTER|CREATE|DELETE|INSERT|UPDATE)|\{.*\})"
)


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


def _seed_categories(conn: sqlite3.Connection) -> None:
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
            (gen_id(), "income", name, icon),
        )
    for name, icon in expense_cats:
        conn.execute(
            "INSERT OR IGNORE INTO finance_categories (id,type,name,icon) VALUES (?,?,?,?)",
            (gen_id(), "expense", name, icon),
        )


def _seed_templates(conn: sqlite3.Connection) -> None:
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


@_ensure_db
def execute_query(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    _validate_sql(sql)
    with _db_lock:
        conn = _get_conn()
        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


@_ensure_db
def execute_write(sql: str, params: tuple = (), many: bool = False) -> int:
    _validate_sql(sql)
    with _db_lock:
        conn = _get_conn()
        if many:
            conn.executemany(sql, params)
        else:
            conn.execute(sql, params)
        conn.commit()
        return conn.total_changes


@_ensure_db
def execute_transaction(statements: List[tuple]) -> bool:
    with _db_lock:
        conn = _get_conn()
        try:
            for sql, params in statements:
                _validate_sql(sql)
                conn.execute(sql, params)
            conn.commit()
            return True
        except sqlite3.Error as e:
            conn.rollback()
            logger.warning("[DataManager] Transaction failed: %s", e)
            return False


@_ensure_db
def execute_write_returning(sql: str, params: tuple = ()) -> str:
    _validate_sql(sql)
    with _db_lock:
        conn = _get_conn()
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid


def backup_db() -> Optional[str]:
    backup_count = int(os.environ.get("OPC_BACKUP_COUNT", "7"))
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"opc_data_{ts}.db")
    try:
        import shutil

        shutil.copy2(DB_PATH, backup_path)
        for old in sorted(Path(BACKUP_DIR).glob("opc_data_*.db"))[:-backup_count]:
            old.unlink()
        logger.info("[DataManager] Backup created: %s", backup_path)
        return backup_path
    except OSError as e:
        logger.warning("[DataManager] Backup failed: %s", e)
        return None


def gen_id() -> str:
    return uuid.uuid4().hex[:16]


def get_preference(key: str, default: str = "") -> str:
    rows = execute_query("SELECT value FROM user_preferences WHERE key=?", (key,))
    return rows[0]["value"] if rows else default


def set_preference(key: str, value: str) -> None:
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    execute_write(
        "INSERT OR REPLACE INTO user_preferences (key, value, updated_at) VALUES (?,?,?)",
        (key, value, now),
    )


class DataManager:
    """Object-oriented wrapper around data_manager global functions.

    Provides dependency injection support while maintaining backward compatibility
    with the existing module-level function API.
    """

    def __init__(self, db_path: Optional[str] = None):
        global DB_PATH, _db_initialized
        if db_path:
            DB_PATH = db_path
            _db_initialized = False
            # Reset thread-local connection so _get_conn() opens the new path
            if hasattr(_local, "conn") and _local.conn is not None:
                try:
                    _local.conn.close()
                except Exception:
                    pass
                _local.conn = None
        init_db()

    def query(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        return execute_query(sql, params)

    def write(self, sql: str, params: tuple = (), many: bool = False) -> int:
        return execute_write(sql, params, many)

    def transaction(self, statements: List[tuple]) -> bool:
        return execute_transaction(statements)

    def write_returning(self, sql: str, params: tuple = ()) -> str:
        return execute_write_returning(sql, params)
