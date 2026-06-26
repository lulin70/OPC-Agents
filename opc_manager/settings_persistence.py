"""
Settings Persistence Mixin — extracted from SettingsManager (God Class refactor).

Contains the JSON disk persistence layer for user settings:
- Loading from ``data/settings.json`` with per-category fault isolation
- Atomic writes (temp file + os.replace)
- Sensitive-field decryption after load
- One-time plaintext -> encrypted migration
- Environment-variable fallback for LLM config
- SecureKeyStore bridge for sensitive keys

=== Design Notes ===
Implemented as a mixin class to preserve all method signatures.
``SettingsManager`` inherits from this mixin, so all external callers see no
change. Cross-mixin dependencies are resolved at runtime via the composed
``SettingsManager`` instance:
- ``self._llm`` / ``self._smtp`` / ``self._security`` / ``self._profile``
  / ``self._settings_file`` / ``self._fernet`` (set in SettingsManager.__init__)
- ``self._encrypt_value`` / ``self._decrypt_value`` / ``self._looks_like_encrypted``
  / ``self._looks_like_base64`` (SettingsEncryptionMixin)

Circular-import avoidance: this mixin references no facade-level names
(dataclasses/enums/SMTP_PRESETS). ``SecureKeyStore`` is imported lazily inside
the methods that use it, and ``LLM_PROVIDERS`` comes from ``opc_manager.config``
(not the facade), so there is no import cycle.
"""

import json
import logging
import os
from typing import Optional

from opc_manager.config import LLM_PROVIDERS

logger = logging.getLogger(__name__)


class SettingsPersistenceMixin:
    """Mixin providing JSON disk persistence and SecureKeyStore integration."""

    def _load_from_disk(self) -> None:
        """Load settings from JSON file if exists.

        Silently handles missing/corrupt files by using defaults.
        Each category is loaded independently to prevent cascading failures.
        Sensitive fields (api_key, password) are decrypted after loading.
        Auto-migration: Detects plaintext keys and re-encrypts them.
        """
        if not self._settings_file.exists():
            logger.debug(
                "Settings file not found at %s, using defaults", self._settings_file
            )
            return

        try:
            with open(self._settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            category_map = {
                "llm": self._llm,
                "smtp": self._smtp,
                "security": self._security,
                "profile": self._profile,
            }

            for category, obj in category_map.items():
                cat_data = data.get(category, {})
                for k, v in cat_data.items():
                    if hasattr(obj, k):
                        if category == "security" and k == "encryption_key":
                            continue
                        setattr(obj, k, v)

            self._decrypt_sensitive_fields()
            self._migrate_plaintext_to_encrypted()
            self._fallback_to_env_vars()

            logger.info("Settings loaded from %s", self._settings_file)

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in settings file %s: %s", self._settings_file, e)
        except Exception as e:
            logger.error("Failed to load settings: %s", e)

    def _save_to_disk(self) -> None:
        """Persist current settings to JSON file with atomic write.

        Uses write-to-temp + rename pattern to prevent corruption
        if process crashes during write.
        Sensitive fields (api_key, password) are encrypted before saving.
        """
        try:
            self._settings_file.parent.mkdir(parents=True, exist_ok=True)

            llm_dict = self._llm.__dict__.copy()
            smtp_dict = self._smtp.__dict__.copy()

            llm_dict["api_key"] = self._encrypt_value(llm_dict.get("api_key", ""))
            smtp_dict["password"] = self._encrypt_value(smtp_dict.get("password", ""))

            data = {
                "llm": llm_dict,
                "smtp": smtp_dict,
                "security": {
                    "auto_generated": self._security.auto_generated,
                },
                "profile": self._profile.__dict__.copy(),
            }

            tmp_path = self._settings_file.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self._settings_file)
            logger.debug("Settings saved to %s", self._settings_file)

        except Exception as e:
            logger.error("Failed to save settings: %s", e)

    def _decrypt_sensitive_fields(self) -> None:
        """Decrypt sensitive fields after loading from disk.

        Attempts to decrypt api_key and password fields.
        - If value looks like valid Fernet token: try to decrypt
        - If value looks like base64 (potentially corrupt): try decrypt, fail → empty string
        - If value looks like plaintext: keep as-is (migration will handle)
        - If Fernet unavailable: keep original value
        """
        try:
            if self._llm.api_key:
                if self._fernet:
                    if self._looks_like_encrypted(
                        self._llm.api_key
                    ) or self._looks_like_base64(self._llm.api_key):
                        decrypted = self._decrypt_value(self._llm.api_key)
                        if decrypted is not None:
                            self._llm.api_key = decrypted
                        else:
                            logger.warning(
                                "[SettingsManager] Failed to decrypt LLM api_key, "
                                "setting to empty string"
                            )
                            self._llm.api_key = ""

            if self._smtp.password:
                if self._fernet:
                    if self._looks_like_encrypted(
                        self._smtp.password
                    ) or self._looks_like_base64(self._smtp.password):
                        decrypted = self._decrypt_value(self._smtp.password)
                        if decrypted is not None:
                            self._smtp.password = decrypted
                        else:
                            logger.warning(
                                "[SettingsManager] Failed to decrypt SMTP password, "
                                "setting to empty string"
                            )
                            self._smtp.password = ""

        except Exception as e:
            logger.error("[SettingsManager] Error decrypting sensitive fields: %s", e)

    def _migrate_plaintext_to_encrypted(self) -> None:
        """Auto-migrate plaintext sensitive fields to encrypted format.

        After loading, checks if sensitive fields appear to be plaintext
        (not valid Fernet tokens). If so, re-encrypts and saves to disk.
        This ensures one-time migration from v0.1.x (plaintext) to v0.2.0+ (encrypted).

        After migration, in-memory values are kept as plaintext for application use.
        Only the on-disk representation is encrypted.
        """
        if not self._fernet:
            return

        migrated = False
        llm_plaintext = None
        smtp_plaintext = None

        try:
            if self._llm.api_key and not self._looks_like_encrypted(self._llm.api_key):
                llm_plaintext = self._llm.api_key
                self._llm.api_key = self._encrypt_value(llm_plaintext)
                migrated = True
                logger.info(
                    "[SettingsManager] Migrating LLM api_key to encrypted storage"
                )

            if self._smtp.password and not self._looks_like_encrypted(
                self._smtp.password
            ):
                smtp_plaintext = self._smtp.password
                self._smtp.password = self._encrypt_value(smtp_plaintext)
                migrated = True
                logger.info(
                    "[SettingsManager] Migrating SMTP password to encrypted storage"
                )

            if migrated:
                self._save_to_disk()

            if llm_plaintext is not None:
                self._llm.api_key = llm_plaintext
            if smtp_plaintext is not None:
                self._smtp.password = smtp_plaintext

        except Exception as e:
            logger.error("[SettingsManager] Failed to migrate plaintext keys: %s", e)

    def _fallback_to_env_vars(self) -> None:
        """Fill empty LLM settings from environment variables.

        When settings.json has no api_key/provider/base_url/model,
        fall back to environment variables so that keys configured via
        .env or SecureKeyStore are visible in the Settings page.
        """
        if not self._llm.api_key:
            for env_key in ("MOKA_API_KEY", "GLM_API_KEY", "OPENAI_API_KEY"):
                val = os.environ.get(env_key, "").strip()
                if val:
                    self._llm.api_key = val
                    if env_key == "MOKA_API_KEY":
                        self._llm.provider = self._llm.provider or "moka"
                        self._llm.base_url = self._llm.base_url or os.environ.get(
                            "MOKA_API_BASE", LLM_PROVIDERS["moka"]
                        )
                        self._llm.model = self._llm.model or os.environ.get(
                            "MOKA_MODEL", "moka/claude-sonnet-4-6"
                        )
                    elif env_key == "GLM_API_KEY":
                        self._llm.provider = self._llm.provider or "glm"
                        self._llm.base_url = (
                            self._llm.base_url or LLM_PROVIDERS["zhipu"]
                        )
                        self._llm.model = self._llm.model or "glm-4"
                    elif env_key == "OPENAI_API_KEY":
                        self._llm.provider = self._llm.provider or "openai"
                        self._llm.base_url = self._llm.base_url or os.environ.get(
                            "OPENAI_API_BASE", LLM_PROVIDERS["openai"]
                        )
                        self._llm.model = self._llm.model or "gpt-4"
                    break

        if not self._llm.provider:
            self._llm.provider = "moka"

    def _store_sensitive_key(self, name: str, value: str) -> None:
        """安全存储敏感密钥到 SecureKeyStore，不写入 os.environ。

        Args:
            name: 密钥名称（如 MOKA_API_KEY）
            value: 密钥值
        """
        try:
            from opc_manager.secure_storage import SecureKeyStore

            store = SecureKeyStore()
            if store.is_available:
                store.set_key(name, value)
            else:
                logger.warning(
                    "[SettingsManager] SecureKeyStore 不可用，敏感密钥 %s 仅存储在内存中",
                    name,
                )
        except Exception as e:
            logger.warning(
                "[SettingsManager] 存储密钥 %s 到 SecureKeyStore 失败: %s", name, e
            )

    def _retrieve_sensitive_key(self, name: str) -> Optional[str]:
        """从 SecureKeyStore 安全获取敏感密钥。

        Args:
            name: 密钥名称

        Returns:
            密钥值，如果未找到返回 None
        """
        try:
            from opc_manager.secure_storage import SecureKeyStore

            store = SecureKeyStore()
            if store.is_available:
                return store.get_key(name)
        except Exception as e:
            logger.warning(
                "[SettingsManager] 从 SecureKeyStore 获取密钥 %s 失败: %s", name, e
            )
        return None
