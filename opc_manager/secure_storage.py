"""
Secure API Key Storage — Fernet encryption for sensitive credentials

Security design:
- Uses Fernet (AES-128-CBC + HMAC-SHA256) symmetric encryption
- Machine-specific key derived via PBKDF2-HMAC-SHA256 from hardware fingerprint
- Encrypted keys stored in .env.encrypted (never in plain .env)
- Atomic file writes to prevent corruption on crash
- Thread-safe operations with internal lock
- CLI commands for key management: set, get, list, remove

ADR-011: Why Fernet instead of raw AES?
  1. Fernet provides authenticated encryption (encrypt+MAC in one step)
  2. Built-in timestamp for key rotation detection
  3. Python cryptography library is well-audited
  4. No IV/nonce management needed (handled internally)

Usage:
  from opc_manager.secure_storage import SecureKeyStore

  store = SecureKeyStore()
  store.set_key("MOKA_API_KEY", "sk-xxx")
  key = store.get_key("MOKA_API_KEY")  # Returns decrypted value
"""

import base64
import hashlib
import json
import os
import platform
import sys
import threading
from pathlib import Path
from typing import Optional, Dict, List

logger = None
try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

_fingerprint_cache = None
_fingerprint_lock = threading.Lock()


def _get_machine_fingerprint() -> str:
    """Generate a machine-specific fingerprint for key derivation

    Combines multiple hardware/OS identifiers to create a unique
    fingerprint per machine. This prevents encrypted keys from being
    portable across machines (security feature, not bug).

    Returns:
        SHA-256 hex digest of combined machine identifiers
    """
    global _fingerprint_cache
    if _fingerprint_cache is not None:
        return _fingerprint_cache

    with _fingerprint_lock:
        if _fingerprint_cache is not None:
            return _fingerprint_cache

        parts = [
            platform.node(),
            platform.machine(),
            platform.system(),
            platform.release(),
        ]
        try:
            uid = os.getuid() if hasattr(os, "getuid") else os.getlogin()
            parts.append(str(uid))
        except (OSError, ModuleNotFoundError):
            parts.append(str(os.environ.get("USER", "unknown")))

        combined = "|".join(parts)
        _fingerprint_cache = hashlib.sha256(combined.encode()).hexdigest()
        return _fingerprint_cache


def _derive_fernet_key(fingerprint: str) -> bytes:
    """Derive a Fernet-compatible key from machine fingerprint

    Uses PBKDF2-HMAC-SHA256 with 100,000 iterations for key stretching.
    This makes brute-force attacks on the fingerprint significantly harder
    compared to a single SHA-256 hash.

    Args:
        fingerprint: Machine fingerprint hex string

    Returns:
        44-byte base64url-encoded Fernet key
    """
    key_material = hashlib.pbkdf2_hmac(
        "sha256",
        f"opc-agents-secure-storage:{fingerprint}".encode(),
        b"opc-agents-salt-v1",
        100000,
    )
    return base64.urlsafe_b64encode(key_material)


class SecureKeyStore:
    """Encrypted API Key storage for OPC-Agents

    Stores encrypted API keys in .env.encrypted file.
    Keys are encrypted using Fernet with a machine-specific key.

    Thread safety:
    - All read-modify-write operations are protected by internal lock
    - File writes are atomic (write-to-temp + rename)

    File format (.env.encrypted):
    {
        "version": 1,
        "keys": {
            "MOKA_API_KEY": "<fernet-encrypted-value>",
            "GLM_API_KEY": "<fernet-encrypted-value>"
        }
    }
    """

    VERSION = 1

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path:
            self._storage_path = Path(storage_path)
        else:
            self._storage_path = Path(
                os.environ.get("OPC_SECURE_STORAGE", ".env.encrypted")
            )

        self._fernet = None
        self._lock = threading.Lock()
        self._init_fernet()

    def _init_fernet(self):
        try:
            from cryptography.fernet import Fernet

            fingerprint = _get_machine_fingerprint()
            key = _derive_fernet_key(fingerprint)
            self._fernet = Fernet(key)
        except ImportError:
            logger.warning(
                "[SecureKeyStore] cryptography package not installed. "
                "Install with: pip install cryptography. "
                "Encrypted key storage disabled."
            )
            self._fernet = None

    @property
    def is_available(self) -> bool:
        return self._fernet is not None

    def set_key(self, name: str, value: str) -> bool:
        if not self._fernet:
            logger.warning("[SecureKeyStore] Not available, key not stored")
            return False

        try:
            with self._lock:
                encrypted = self._fernet.encrypt(value.encode()).decode()
                data = self._load_storage()
                data["keys"][name] = encrypted
                self._save_storage(data)
            logger.info(f"[SecureKeyStore] Stored: {name}")
            return True
        except Exception as e:
            logger.error(f"[SecureKeyStore] Failed to store {name}: {e}")
            return False

    def get_key(self, name: str) -> Optional[str]:
        if not self._fernet:
            return None

        try:
            with self._lock:
                data = self._load_storage()
                encrypted = data["keys"].get(name)
            if not encrypted:
                return None
            return self._fernet.decrypt(encrypted.encode()).decode()
        except Exception as e:
            logger.error(f"[SecureKeyStore] Failed to decrypt {name}: {e}")
            return None

    def list_keys(self) -> List[str]:
        with self._lock:
            data = self._load_storage()
        return list(data.get("keys", {}).keys())

    def remove_key(self, name: str) -> bool:
        with self._lock:
            data = self._load_storage()
            if name in data.get("keys", {}):
                del data["keys"][name]
                self._save_storage(data)
                logger.info(f"[SecureKeyStore] Removed: {name}")
                return True
        return False

    def load_to_env(self) -> int:
        if not self._fernet:
            return 0

        try:
            with self._lock:
                data = self._load_storage()

            count = 0
            for name, encrypted in data.get("keys", {}).items():
                try:
                    value = self._fernet.decrypt(encrypted.encode()).decode()
                    os.environ[name] = value
                    count += 1
                except Exception as e:
                    logger.error(f"[SecureKeyStore] Failed to decrypt {name}: {e}")

            if count > 0:
                logger.info(f"[SecureKeyStore] Loaded {count} encrypted keys to env")

            return count
        except Exception as e:
            logger.error(f"[SecureKeyStore] load_to_env failed: {e}")
            return 0

    def _load_storage(self) -> Dict:
        if not self._storage_path.exists():
            return {"version": self.VERSION, "keys": {}}

        try:
            with open(self._storage_path, "r") as f:
                data = json.load(f)
            if data.get("version") != self.VERSION:
                logger.warning("[SecureKeyStore] Storage version mismatch")
            return data
        except Exception as e:
            logger.error(f"[SecureKeyStore] Failed to load storage: {e}")
            return {"version": self.VERSION, "keys": {}}

    def _save_storage(self, data: Dict):
        tmp_path = self._storage_path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        try:
            if hasattr(os, "chmod"):
                os.chmod(tmp_path, 0o600)
        except Exception:
            pass
        os.replace(tmp_path, self._storage_path)


def init_secure_storage():
    """Initialize secure storage at application startup

    Called by cli.py and app.py before ConfigManager initialization.
    Loads encrypted keys into os.environ so they appear as regular env vars.
    """
    try:
        store = SecureKeyStore()
        if store.is_available:
            store.load_to_env()
        else:
            logger.debug("[SecureKeyStore] Not available, using .env only")
    except Exception as e:
        logger.warning(f"[SecureKeyStore] Init failed, using .env only: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OPC-Agents Secure Key Manager")
    sub = parser.add_subparsers(dest="command")

    set_cmd = sub.add_parser("set", help="Store an encrypted API key")
    set_cmd.add_argument("name", help="Key name (e.g., MOKA_API_KEY)")
    set_cmd.add_argument("value", help="API key value")

    get_cmd = sub.add_parser("get", help="Retrieve an encrypted API key")
    get_cmd.add_argument("name", help="Key name")

    sub.add_parser("list", help="List stored key names")

    rm_cmd = sub.add_parser("remove", help="Remove a stored API key")
    rm_cmd.add_argument("name", help="Key name")

    args = parser.parse_args()
    store = SecureKeyStore()

    if not store.is_available:
        print("Error: cryptography package not installed.")
        print("Install with: pip install cryptography")
        sys.exit(1)

    if args.command == "set":
        if store.set_key(args.name, args.value):
            print(f"OK: {args.name} stored securely")
        else:
            print(f"FAIL: Could not store {args.name}")

    elif args.command == "get":
        value = store.get_key(args.name)
        if value:
            print(f"{args.name}={'*' * 8}...{value[-2:]}")
        else:
            print(f"Not found: {args.name}")

    elif args.command == "list":
        keys = store.list_keys()
        if keys:
            for k in keys:
                print(f"  {k}")
        else:
            print("No keys stored")

    elif args.command == "remove":
        if store.remove_key(args.name):
            print(f"OK: {args.name} removed")
        else:
            print(f"Not found: {args.name}")

    else:
        parser.print_help()
