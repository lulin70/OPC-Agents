"""
Settings Operations Mixin — extracted from SettingsManager (God Class refactor).

Contains the user-facing operations on settings:
- SMTP connection testing
- ``is_configured`` category status checks
- Callback registration/notification for live updates
- Masked export (safe for logging/UI)
- Reset-to-defaults

=== Design Notes ===
Implemented as a mixin class to preserve all method signatures.
``SettingsManager`` inherits from this mixin, so all external callers see no
change. Cross-mixin dependencies are resolved at runtime via the composed
``SettingsManager`` instance:
- ``self._smtp`` / ``self._llm`` / ``self._security`` / ``self._profile``
  / ``self._callbacks`` / ``self._data_lock`` (set in SettingsManager.__init__)
- ``self._save_to_disk`` (SettingsPersistenceMixin)
- ``self.SENSITIVE_FIELDS`` (class attribute on the facade)

Circular-import avoidance: ``is_configured`` and ``reset_to_defaults`` need the
facade-level names (``SettingsCategory`` enum and the ``LLMSettings`` /
``SMTPSettings`` / ``ProfileSettings`` dataclasses) at *runtime* — to compare
enum members and to construct fresh default instances. Importing those names at
module level would create a cycle (facade -> this mixin -> facade). Instead:

1. ``from __future__ import annotations`` makes every annotation a lazy string
   (PEP 563), so the ``SettingsCategory`` / ``Optional[SettingsCategory]``
   annotations do not require the names to exist at module load time.
2. The two methods that need the names at runtime import them lazily inside the
   method body. Python caches modules in ``sys.modules``, so the per-call cost
   is a dict lookup and there is no memory growth (relevant to the
   ``test_settings_manager_singleton_no_growth`` flaky test, which does not
   exercise these two methods anyway).
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

if TYPE_CHECKING:
    # Import only for static type checkers / pyflakes name resolution. This
    # block does NOT execute at runtime (TYPE_CHECKING is False), so there is
    # no circular import with the facade. The runtime usages in
    # ``is_configured`` and ``reset_to_defaults`` import the same names lazily
    # inside the method bodies.
    from opc_manager.settings import SettingsCategory

logger = logging.getLogger(__name__)


class SettingsOperationsMixin:
    """Mixin providing user-facing settings operations and callbacks."""

    def test_smtp_connection(self) -> Dict[str, Any]:
        """Test SMTP connection with current settings.

        Attempts to connect and authenticate with configured SMTP server.
        Uses 5-second timeout to avoid blocking UI on unreachable servers.

        Returns:
            dict with keys:
                - success (bool): Whether connection succeeded
                - message (str): Human-readable result description
                - latency_ms (int): Round-trip time in milliseconds
        """
        start = time.time()

        try:
            if not self._smtp.host or not self._smtp.username:
                return {
                    "success": False,
                    "message": "SMTP host or username not configured",
                    "latency_ms": 0,
                }

            import smtplib

            server = smtplib.SMTP(self._smtp.host, self._smtp.port, timeout=5)

            if self._smtp.tls:
                server.starttls()

            server.login(self._smtp.username, self._smtp.password)
            server.quit()

            latency = int((time.time() - start) * 1000)
            return {
                "success": True,
                "message": f"Connected successfully to {self._smtp.host}",
                "latency_ms": latency,
            }

        except smtplib.SMTPAuthenticationError:
            return {
                "success": False,
                "message": "Authentication failed - check username/password",
                "latency_ms": int((time.time() - start) * 1000),
            }
        except smtplib.SMTPConnectError as e:
            return {
                "success": False,
                "message": f"Connection failed: {e}",
                "latency_ms": int((time.time() - start) * 1000),
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error: {e}",
                "latency_ms": int((time.time() - start) * 1000),
            }

    def is_configured(self, category: SettingsCategory) -> bool:
        """Check if a settings category has been minimally configured.

        Args:
            category: SettingsCategory enum value to check

        Returns:
            True if category has required fields set, False otherwise
        """
        # Lazy import: SettingsCategory is defined in the facade (opc_manager.settings).
        # Importing it at module level would create a circular import.
        from opc_manager.settings import SettingsCategory

        if category == SettingsCategory.LLM:
            return bool(self._llm.api_key or self._llm.provider == "ollama")
        elif category == SettingsCategory.SMTP:
            return bool(self._smtp.host and self._smtp.username)
        elif category == SettingsCategory.SECURITY:
            return bool(self._security.encryption_key)
        elif category == SettingsCategory.PROFILE:
            return bool(self._profile.user_name)
        return False

    def register_callback(self, callback: Callable[[str], None]) -> None:
        """Register a callback for settings changes.

        Callback will be invoked with category name string when any
        setting in that category is modified.

        Args:
            callback: Function accepting single str argument (category name)
        """
        with self._data_lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[str], None]) -> None:
        """Remove a previously registered callback.

        Args:
            callback: The exact function object to remove
        """
        with self._data_lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def _notify_callbacks(self, category: str) -> None:
        """Notify all registered callbacks of a change.

        Errors in individual callbacks are caught and logged to prevent
        one faulty callback from blocking others.
        """
        with self._data_lock:
            for cb in self._callbacks:
                try:
                    cb(category)
                except Exception as e:
                    logger.warning("Settings callback error for %s: %s", category, e)

    def export_settings(self) -> Dict[str, Any]:
        """Export all settings with sensitive fields masked.

        Safe for logging, display, or export to non-secure contexts.
        Actual sensitive values are replaced with "***" mask.

        Returns:
            Nested dict with all settings categories and masked values
        """
        return {
            "llm": {
                k: ("***" if k in self.SENSITIVE_FIELDS else v)
                for k, v in self._llm.__dict__.items()
            },
            "smtp": {
                k: ("***" if k in self.SENSITIVE_FIELDS else v)
                for k, v in self._smtp.__dict__.items()
            },
            "security": {
                "has_key": bool(self._security.encryption_key),
                "auto_generated": self._security.auto_generated,
            },
            "profile": self._profile.__dict__.copy(),
        }

    def reset_to_defaults(self, category: Optional[SettingsCategory] = None) -> bool:
        """Reset settings to default values.

        Args:
            category: Specific category to reset, or None for all categories

        Returns:
            True after reset completes (always succeeds)
        """
        # Lazy import: the dataclasses and enum are defined in the facade
        # (opc_manager.settings). Importing them at module level would create a
        # circular import; they are needed here only to construct fresh
        # default instances and to compare enum members.
        from opc_manager.settings import (
            LLMSettings,
            SMTPSettings,
            ProfileSettings,
            SettingsCategory,
        )

        if category is None or category == SettingsCategory.LLM:
            self._llm = LLMSettings()
        if category is None or category == SettingsCategory.SMTP:
            self._smtp = SMTPSettings()
        if category is None or category == SettingsCategory.PROFILE:
            self._profile = ProfileSettings()

        self._save_to_disk()
        return True
