"""
Settings Encryption Mixin — extracted from SettingsManager (God Class refactor).

Contains all Fernet-based encryption/decryption helpers used to protect
sensitive fields (api_key, password) at rest.

=== Design Notes ===
Implemented as a mixin class to preserve all method signatures.
``SettingsManager`` inherits from this mixin, so all external callers see no
change. Cross-mixin dependencies are resolved at runtime via the composed
``SettingsManager`` instance:
- ``self._security`` / ``self._fernet`` (set in SettingsManager.__init__)
- ``self._save_to_disk`` (SettingsPersistenceMixin)
- ``self.SETTINGS_FILE`` (class attribute on the facade)

Circular-import avoidance: this mixin references no facade-level names
(dataclasses/enums/SMTP_PRESETS), so it can be imported freely.
"""

import base64
import hashlib
import logging
import os
import secrets
from pathlib import Path
from typing import TYPE_CHECKING, Optional

# PBKDF2 key derivation constants (硬约束: 禁止裸 SHA-256, 必须用 PBKDF2-HMAC-SHA256 + salt)
_KEY_DERIVATION_SALT = b"opc-agents-settings-v0.4.0"
_KEY_DERIVATION_ITERATIONS = 100000

if TYPE_CHECKING:
    from cryptography.fernet import Fernet
    from opc_manager.settings import SecuritySettings

logger = logging.getLogger(__name__)


class SettingsEncryptionMixin:
    """Mixin providing Fernet encryption/decryption for sensitive settings.

    Key derivation uses SHA-256 (unified with data_manager.py). Supports
    one-time migration from the old truncate+pad derivation to SHA-256.
    """

    # Type declarations for cross-mixin attributes (provided by SettingsManager facade).
    # These exist only during type checking; at runtime they are set by the facade.
    if TYPE_CHECKING:
        _security: "SecuritySettings"
        _fernet: "Optional[Fernet]"
        SETTINGS_FILE: str

        def _save_to_disk(self) -> None: ...

    def _init_fernet(self) -> None:
        """Initialize Fernet cipher using encryption key.

        Uses the encryption key from security settings (in-memory).
        Falls back to os.environ only for externally-set env vars (e.g., docker-compose).
        If key is unavailable, encryption is disabled (plaintext mode).

        Key derivation: SHA-256 hash (unified with data_manager.py).
        Migration: If old-derivation encrypted data is found, re-encrypt with new key.

        Security posture (TD-066 fix, 2026-06-28):
        - SE-1 (no key): fail-open + [SECURITY] warning (defensive; _ensure_encryption_key
          auto-generates a key in normal flow, so this branch is rarely reached).
        - SE-2 (ImportError): fail-closed — cryptography is a hard dependency.
        - SE-3 (broad except): fail-closed — initialization failure must not silently
          degrade to plaintext mode.
        """
        try:
            from cryptography.fernet import Fernet

            # 优先使用进程内存储的密钥，不主动从 os.environ 读取
            key = self._security.encryption_key
            if not key:
                # 仅回退读取外部设置的环境变量（兼容 docker/start.sh 部署）
                key = os.environ.get("OPC_ENCRYPTION_KEY", "")
            if not key:
                # [SECURITY] SE-1 fail-open (TD-066): no key available.
                # _ensure_encryption_key() auto-generates a key in normal flow,
                # so this branch is defensive only. Keep plaintext mode to avoid
                # blocking startup when auto-generation is intentionally disabled.
                logger.warning(
                    "[SECURITY] [SettingsManager] No encryption key available, "
                    "sensitive fields stored as plaintext"
                )
                return

            # PBKDF2-HMAC-SHA256 with salt + 100000 iterations (硬约束: 禁止裸 SHA-256).
            # BREAKING CHANGE (v0.4.0): 之前使用裸 hashlib.sha256 派生密钥，违反硬约束。
            # 已加密的旧数据需用旧密钥派生方式解密后重新加密，或重置 OPC_ENCRYPTION_KEY。
            # Salt 为项目级常量，与 data_manager.py 的 _KEY_DERIVATION_SALT 保持一致。
            key_bytes = hashlib.pbkdf2_hmac(
                "sha256",
                key.encode(),
                _KEY_DERIVATION_SALT,
                _KEY_DERIVATION_ITERATIONS,
            )
            fernet_key = base64.urlsafe_b64encode(key_bytes)
            self._fernet = Fernet(fernet_key)
            logger.debug("[SettingsManager] Fernet cipher initialized successfully")

        except ImportError:
            # [SECURITY] SE-2 fail-closed (TD-066): cryptography is a hard dependency
            # declared in requirements.txt. Silent degradation to plaintext mode
            # would mask a broken environment and leak sensitive fields to disk.
            logger.error(
                "[SECURITY] [SettingsManager] cryptography package not installed. "
                "Install with: pip install cryptography. "
                "Refusing to degrade to plaintext mode."
            )
            raise RuntimeError(
                "cryptography package is not installed. SettingsEncryptionMixin "
                "refuses to degrade to plaintext mode. Install with: "
                "pip install cryptography"
            )
        except Exception as e:
            # [SECURITY] SE-3 fail-closed (TD-066): initialization failure must not
            # silently degrade to plaintext mode (symmetric with SE-2).
            logger.error(
                "[SECURITY] [SettingsManager] Failed to initialize Fernet: %s. "
                "Refusing to degrade to plaintext mode.",
                e,
            )
            raise RuntimeError(
                f"_init_fernet() failed: {e}. Refusing to degrade to plaintext mode. "
                f"Check OPC_ENCRYPTION_KEY and cryptography package installation."
            ) from e

    def _decrypt_with_old_key(self, ciphertext: str) -> Optional[str]:
        """Try to decrypt using the old key derivation method (truncate+pad).

        This is used for migration: data encrypted with the old method
        (key.encode()[:32].ljust(32, b"\\0")) can still be decrypted
        and then re-encrypted with the new SHA-256 method.
        """
        try:
            from cryptography.fernet import Fernet

            key = self._security.encryption_key
            if not key:
                key = os.environ.get("OPC_ENCRYPTION_KEY", "")
            if not key:
                return None

            old_key_bytes = key.encode()[:32].ljust(32, b"\0")
            old_fernet_key = base64.urlsafe_b64encode(old_key_bytes)
            old_fernet = Fernet(old_fernet_key)
            return old_fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except Exception:
            logger.debug(
                "[SettingsManager] Decryption failed for value, returning None"
            )
            return None

    def _encrypt_value(self, plaintext: str) -> str:
        """Encrypt a sensitive value using Fernet.

        Args:
            plaintext: Plain text value to encrypt (e.g., API key, password)

        Returns:
            Encrypted string (base64-encoded), or original plaintext if empty.

        Security posture (TD-066 fix, 2026-06-28):
        - SE-4 (_fernet is None): fail-open + [SECURITY] warning (symmetric with SE-1;
          _fernet is None only when _init_fernet decided to keep plaintext mode).
        - SE-5 (encrypt exception): fail-closed — refuse to store plaintext on
          internal Fernet failures (symmetric with data_manager.py DM-2 fix).
        """
        if not plaintext:
            return plaintext
        if not self._fernet:
            # [SECURITY] SE-4 fail-open (TD-066): _fernet is None means _init_fernet
            # decided to keep plaintext mode (SE-1 branch). Keep existing behavior
            # to avoid blocking startup, but record a warning.
            logger.warning(
                "[SECURITY] [SettingsManager] Fernet unavailable, storing value as plaintext"
            )
            return plaintext

        try:
            encrypted = self._fernet.encrypt(plaintext.encode("utf-8"))
            return encrypted.decode("utf-8")
        except Exception as e:
            # [SECURITY] SE-5 fail-closed (TD-066): encryption failure must not
            # silently store plaintext (symmetric with data_manager.py DM-2 fix,
            # 2026-06-27). Refuse to store plaintext on internal Fernet failures.
            logger.error(
                "[SECURITY] [SettingsManager] Failed to encrypt value: %s. "
                "Refusing to store plaintext.",
                e,
            )
            raise RuntimeError(
                f"_encrypt_value() failed: {e}. Refusing to store plaintext. "
                f"Check Fernet key and cryptography package installation."
            ) from e

    def _decrypt_value(self, ciphertext: str) -> Optional[str]:
        """Decrypt a previously encrypted value.

        Args:
            ciphertext: Encrypted string (base64-encoded Fernet token)

        Returns:
            Decrypted plain text, None if decryption fails (corrupt/invalid token)

        Security posture (TD-066 fix, 2026-06-28):
        - SE-6 (_fernet is None): fail-open + [SECURITY] warning (symmetric with
          data_manager.py decrypt_field — return original value to avoid data loss
          when the value may already be plaintext from a legacy install).
        """
        if not ciphertext:
            return None
        if not self._fernet:
            # [SECURITY] SE-6 fail-open (TD-066): Fernet unavailable.
            # Return original ciphertext (which may be plaintext from a legacy
            # install) to avoid data loss. Symmetric with data_manager.py
            # decrypt_field() which returns ciphertext when key is None.
            logger.warning(
                "[SECURITY] [SettingsManager] Fernet unavailable, returning original value as-is"
            )
            return ciphertext

        try:
            decrypted = self._fernet.decrypt(ciphertext.encode("utf-8"))
            return decrypted.decode("utf-8")
        except Exception:
            logger.debug(
                "[SettingsManager] New-key decryption failed, trying old-key migration"
            )
            # 新方式解密失败，尝试旧方式（truncate+pad 派生）进行迁移
            old_decrypted = self._decrypt_with_old_key(ciphertext)
            if old_decrypted is not None:
                logger.info(
                    "[SettingsManager] Migrated data from old key derivation to SHA-256"
                )
                return old_decrypted
            logger.debug(
                "[SettingsManager] Decryption failed with both new and old key"
            )
            return None

    def _ensure_encryption_key(self) -> None:
        """Auto-generate encryption key if not present (P0-2 core feature).

        Generates a cryptographically secure 256-bit (64 hex chars) key using
        secrets.token_hex(). Stores in both memory and .env.local file.

        Key reuse strategy:
        1. Check if already in memory (previous session)
        2. Check .env.local file (persisted from earlier run)
        3. Check os.environ (set by external process)
        4. If none found, generate new key

        Security considerations:
        - Key generated via secrets module (CSPRNG)
        - Stored in .env.local (gitignored by default)
        - Kept in process memory only, NOT written to os.environ
        - Auto-generated flag prevents overwriting user-provided keys
        """
        if self._security.encryption_key and self._security.auto_generated:
            return

        existing_key = (
            self._security.encryption_key
            or os.environ.get("OPC_ENCRYPTION_KEY", "")
            or self._read_key_from_env_local()
        )

        if existing_key:
            self._security.encryption_key = existing_key
            self._security.auto_generated = True
            logger.info("Reused existing encryption key from .env.local")
            return

        key = secrets.token_hex(32)
        self._security.encryption_key = key
        self._security.auto_generated = True

        env_local = Path(self.SETTINGS_FILE).parent / ".env.local"
        lines = []
        if env_local.exists():
            lines = env_local.read_text(encoding="utf-8").splitlines()

        found = False
        new_line = f"OPC_ENCRYPTION_KEY={key}"
        for i, line in enumerate(lines):
            if line.startswith("OPC_ENCRYPTION_KEY="):
                lines[i] = new_line
                found = True
                break

        if not found:
            lines.append(new_line)
            lines.append("")

        env_local.write_text("\n".join(lines), encoding="utf-8")
        os.chmod(str(env_local), 0o600)  # 仅文件所有者可读写

        logger.info("Auto-generated encryption key and saved to .env.local")

    def _read_key_from_env_local(self) -> str:
        """Read existing encryption key from .env.local file.

        Reads from the same directory as SETTINGS_FILE (consistent with the
        write path in ``_ensure_encryption_key``). Falls back to CWD for
        backward compatibility with deployments that have .env.local in the
        project root.

        Returns:
            Key string if found, empty string otherwise
        """
        try:
            candidates = [
                Path(self.SETTINGS_FILE).parent / ".env.local",
                Path(".env.local"),
            ]
            for env_local in candidates:
                if not env_local.exists():
                    continue
                for line in env_local.read_text(encoding="utf-8").splitlines():
                    if line.startswith("OPC_ENCRYPTION_KEY="):
                        return line.split("=", 1)[1].strip()
            return ""
        except Exception as e:
            logger.warning("Failed to read key from .env.local: %s", e)
            return ""

    def _looks_like_encrypted(self, value: str) -> bool:
        """Check if a value appears to be a Fernet-encrypted token.

        Fernet tokens are base64-encoded and typically 44+ characters long
        (for short plaintext inputs). This is a heuristic check.

        Args:
            value: String to check

        Returns:
            True if value looks like encrypted token, False otherwise
        """
        if not value or len(value) < 44:
            return False

        try:
            decoded = base64.urlsafe_b64decode(value)
            return len(decoded) >= 32
        except Exception as e:
            logger.debug("[SettingsManager] is_valid_base64_token check failed: %s", e)
            return False

    def _looks_like_base64(self, value: str) -> bool:
        """Check if a value appears to be base64-encoded (potential corrupt token).

        Used to distinguish between obvious plaintext and potentially
        corrupted encrypted tokens that should result in empty string.

        Args:
            value: String to check

        Returns:
            True if value looks like base64, False otherwise
        """
        if not value or len(value) < 20:
            return False

        try:
            decoded = base64.urlsafe_b64decode(value)
            return len(decoded) >= 16
        except Exception as e:
            logger.debug("[SettingsManager] looks_like_base64 check failed: %s", e)
            return False
