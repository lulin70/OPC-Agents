import base64
import functools
import hashlib
import logging
import os
import sqlite3
import stat
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Migrations, SQL validation, and seed data live in data_manager_migrations.
# Re-exported here so existing imports (152 call sites) and unittest.mock.patch
# paths (e.g. `patch("opc_manager.data_manager._validate_sql")`) keep working.
from opc_manager.data_manager_migrations import (  # noqa: F401
    _IDENTIFIER_RE,
    _UNSAFE_SQL_RE,
    _add_column_if_not_exists,
    _db_version,
    _run_migrations,
    _seed_categories,
    _seed_templates,
    _validate_identifier,
    _validate_sql,
    gen_id,
)

logger = logging.getLogger(__name__)

DATA_DIR = os.environ.get(
    "OPC_DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
)
DB_PATH = os.path.join(DATA_DIR, "opc_data.db")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

_db_lock = threading.RLock()
_local = threading.local()
_db_initialized = False
_db_init_lock = threading.Lock()

_ENCRYPTION_KEY_ENV = "OPC_ENCRYPTION_KEY"
_fallback_key = None

# PBKDF2 key derivation constants (硬约束: 禁止裸 SHA-256, 必须用 PBKDF2-HMAC-SHA256 + salt)
# BREAKING CHANGE (v0.4.0): 之前使用裸 hashlib.sha256 派生密钥，违反硬约束。
# 已加密的旧数据需用旧密钥派生方式解密后重新加密，或重置 OPC_ENCRYPTION_KEY。
_KEY_DERIVATION_SALT = b"opc-agents-settings-v0.4.0"
_KEY_DERIVATION_ITERATIONS = 100000


def _derive_key_pbkdf2(key_str: str) -> bytes:
    """Derive a Fernet-compatible key from a password string using PBKDF2.

    Uses PBKDF2-HMAC-SHA256 with a project-level salt and 100000 iterations
    to satisfy the hard constraint: 禁止裸 SHA-256.
    """
    return hashlib.pbkdf2_hmac(
        "sha256",
        key_str.encode(),
        _KEY_DERIVATION_SALT,
        _KEY_DERIVATION_ITERATIONS,
    )


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
            return _derive_key_pbkdf2(key_str)
    except Exception as e:
        logger.warning("[DataManager] PBKDF2 key derivation failed: %s", e)

    # 回退到 os.environ（兼容外部设置的环境变量）
    key_str = os.environ.get(_ENCRYPTION_KEY_ENV, "")
    if key_str:
        return _derive_key_pbkdf2(key_str)

    # 无显式密钥时，自动派生基于机器特征的密钥
    # 保证数据至少是加密存储的，而非明文
    if _fallback_key is None:
        machine_id = _derive_machine_key()
        _fallback_key = _derive_key_pbkdf2(f"opc-agents-auto-{machine_id}")
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
    except (ImportError, OSError):
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
        logger.error(
            "[SECURITY] [DataManager] Encryption failed, refusing to store plaintext: %s",
            e,
        )
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


def _ensure_db(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
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
            status TEXT NOT NULL DEFAULT 'potential'
                CHECK(status IN ('potential','first_deal','active','silent','lost')),
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
        _seed_categories(conn, gen_id)
        _seed_templates(conn)
        conn.commit()
        _db_initialized = True
        logger.info("[DataManager] Database initialized (v%d)", _db_version)


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
def execute_write_returning(sql: str, params: tuple = ()) -> Optional[int]:
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

    def write_returning(self, sql: str, params: tuple = ()) -> Optional[int]:
        return execute_write_returning(sql, params)
