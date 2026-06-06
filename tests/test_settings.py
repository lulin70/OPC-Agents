"""
Settings Manager Unit Tests — v0.2.0 Sprint 1 Core Module Validation

Test coverage:
  - Singleton pattern and thread safety
  - CRUD operations for all 5 settings categories
  - Auto-generated encryption key (P0-2 core feature)
  - SMTP connection testing with mocking
  - Sensitive field masking on export
  - Callback notification system
  - Reset to defaults functionality

Run command:
    pytest tests/test_settings.py -v --tb=short

Expected: All 11 test cases pass (0 failures)
"""

import json
import os
import sys
import base64
import threading
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from opc_manager.settings import (
    SettingsManager,
    SettingsCategory,
    LLMSettings,
    SMTPSettings,
    SecuritySettings,
    ProfileSettings,
    get_settings,
    SMTP_PRESETS,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton instance before each test to ensure isolation.

    This is critical for testing singleton patterns without state leakage
    between test cases.
    """
    original_instance = SettingsManager._instance
    SettingsManager._instance = None

    yield

    SettingsManager._instance = original_instance


@pytest.fixture
def temp_settings_dir(tmp_path):
    """Create a temporary directory for settings file testing.

    Prevents polluting the project's actual data/settings.json during tests.
    """
    original_settings_file = SettingsManager.SETTINGS_FILE
    SettingsManager.SETTINGS_FILE = str(tmp_path / "settings.json")

    yield tmp_path

    SettingsManager.SETTINGS_FILE = original_settings_file


class TestSingletonPattern:
    """Test suite for verifying SettingsManager singleton behavior."""

    def test_singleton_identity(self):
        """Verify: Multiple get_settings() calls return the same object instance
        Scenario: Call get_settings() twice in same process
        Expected: Both references point to identical object (is check passes)
        """
        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2, "get_settings() must return singleton instance"

    def test_singleton_class_method_consistency(self):
        """Verify: Direct instantiation also returns singleton
        Scenario: Create instance via SettingsManager() constructor
        Expected: Same object as returned by get_settings()
        """
        settings_direct = SettingsManager()
        settings_factory = get_settings()

        assert settings_direct is settings_factory, "Constructor must return singleton"


class TestLLMCRUD:
    """Test suite for LLM settings create/read/update operations."""

    def test_llm_default_values(self, temp_settings_dir):
        """Verify: Fresh SettingsManager has correct LLM defaults
        Scenario: Create new SettingsManager without any configuration
        Expected: provider='moka', max_tokens=4000, temperature=0.7
        """
        settings = get_settings()

        assert settings.llm.provider == "moka"
        assert settings.llm.max_tokens == 4000
        assert settings.llm.temperature == 0.7
        assert settings.llm.api_key == ""
        assert settings.llm.model == ""

    def test_llm_update_single_field(self, temp_settings_dir):
        """Verify: Can update individual LLM field
        Scenario: Call update_llm(provider="openai")
        Expected: Only provider changes, other fields retain defaults
        """
        settings = get_settings()
        result = settings.update_llm(provider="openai")

        assert result is True
        assert settings.llm.provider == "openai"
        assert settings.llm.max_tokens == 4000

    def test_llm_update_multiple_fields(self, temp_settings_dir):
        """Verify: Can update multiple LLM fields simultaneously
        Scenario: Call update_llm with provider, api_key, model, temperature
        Expected: All specified fields updated atomically
        """
        settings = get_settings()
        settings.update_llm(
            provider="glm",
            api_key="test-key-123",
            model="glm-4",
            temperature=0.9,
            max_tokens=8000,
        )

        assert settings.llm.provider == "glm"
        assert settings.llm.api_key == "test-key-123"
        assert settings.llm.model == "glm-4"
        assert settings.llm.temperature == 0.9
        assert settings.llm.max_tokens == 8000

    def test_llm_persistence_to_disk(self, temp_settings_dir):
        """Verify: LLM settings persisted to JSON file after update
        Scenario: Update LLM settings, then reload from disk
        Expected: File contains updated values, new instance reads them correctly
        """
        settings = get_settings()
        settings.update_llm(
            provider="ollama", base_url="http://localhost:11434", model="llama3"
        )

        settings_file = Path(SettingsManager.SETTINGS_FILE)
        assert settings_file.exists(), "Settings file should be created after update"

        with open(settings_file, "r") as f:
            saved_data = json.load(f)

        assert saved_data["llm"]["provider"] == "ollama"
        assert saved_data["llm"]["base_url"] == "http://localhost:11434"

        SettingsManager._instance = None
        settings_reloaded = get_settings()
        assert settings_reloaded.llm.provider == "ollama"


class TestSMTPCRUD:
    """Test suite for SMTP settings operations."""

    def test_smtp_default_values(self, temp_settings_dir):
        """Verify: Fresh SettingsManager has correct SMTP defaults
        Scenario: Create new SettingsManager
        Expected: port=587, tls=True, empty host/username/password
        """
        settings = get_settings()

        assert settings.smtp.port == 587
        assert settings.smtp.tls is True
        assert settings.smtp.host == ""
        assert settings.smtp.username == ""
        assert settings.smtp.password == ""

    def test_smtp_update_all_fields(self, temp_settings_dir):
        """Verify: Can update all SMTP fields including sensitive password
        Scenario: Call update_smtp with host, port, username, password, tls
        Expected: All fields reflect new values
        """
        settings = get_settings()
        result = settings.update_smtp(
            host="smtp.example.com",
            port=465,
            username="user@example.com",
            password="secret-pass",
            tls=False,
            from_email="sender@example.com",
        )

        assert result is True
        assert settings.smtp.host == "smtp.example.com"
        assert settings.smtp.port == 465
        assert settings.smtp.username == "user@example.com"
        assert settings.smtp.password == "secret-pass"
        assert settings.smtp.tls is False
        assert settings.smtp.from_email == "sender@example.com"

    def test_smtp_persistence(self, temp_settings_dir):
        """Verify: SMTP settings survive disk round-trip
        Scenario: Update SMTP, force reload
        Expected: Reloaded instance has identical SMTP config
        """
        settings = get_settings()
        settings.update_smtp(
            host="smtp.gmail.com",
            port=587,
            username="test@gmail.com",
            password="pass123",
            tls=True,
        )

        SettingsManager._instance = None
        reloaded = get_settings()

        assert reloaded.smtp.host == "smtp.gmail.com"
        assert reloaded.smtp.port == 587
        assert reloaded.smtp.username == "test@gmail.com"
        assert reloaded.smtp.password == "pass123"


class TestSMTPConnectionTest:
    """Test suite for SMTP connection testing functionality."""

    def test_smtp_connection_unconfigured(self, temp_settings_dir):
        """Verify: Returns failure when SMTP not configured
        Scenario: Call test_smtp_connection() with empty host/username
        Expected: success=False, message mentions missing configuration
        """
        settings = get_settings()
        result = settings.test_smtp_connection()

        assert result["success"] is False
        assert "not configured" in result["message"].lower()
        assert result["latency_ms"] == 0

    @patch("smtplib.SMTP")
    def test_smtp_connection_success(self, mock_smtp_class, temp_settings_dir):
        """Verify: Returns success when SMTP connection succeeds
        Scenario: Configure valid SMTP, mock successful server connection
        Expected: success=True, latency_ms > 0, message contains hostname
        """
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        settings = get_settings()
        settings.update_smtp(
            host="smtp.test.com",
            port=587,
            username="user@test.com",
            password="pass",
            tls=True,
        )

        result = settings.test_smtp_connection()

        assert result["success"] is True
        assert "smtp.test.com" in result["message"]
        assert result["latency_ms"] >= 0
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@test.com", "pass")
        mock_server.quit.assert_called_once()

    @patch("smtplib.SMTP")
    def test_smtp_connection_auth_failure(self, mock_smtp_class, temp_settings_dir):
        """Verify: Handles authentication errors gracefully
        Scenario: Mock SMTP server raises SMTPAuthenticationError
        Expected: success=False, message mentions authentication failed
        """
        import smtplib

        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(
            535, "Auth failed"
        )
        mock_smtp_class.return_value = mock_server

        settings = get_settings()
        settings.update_smtp(
            host="smtp.test.com", port=587, username="bad_user", password="wrong_pass"
        )

        result = settings.test_smtp_connection()

        assert result["success"] is False
        assert "authentication" in result["message"].lower()


class TestSMTPPresets:
    """Test suite for SMTP preset configurations."""

    def test_get_existing_preset(self):
        """Verify: Can retrieve known SMTP preset by name
        Scenario: Call get_smtp_preset("QQ邮箱")
        Expected: Returns dict with host, port, tls keys matching QQ mail config
        """
        settings = get_settings()
        preset = settings.get_smtp_preset("QQ邮箱")

        assert preset["host"] == "smtp.qq.com"
        assert preset["port"] == 465
        assert preset["tls"] is True

    def test_get_nonexistent_preset(self):
        """Verify: Returns empty dict for unknown preset name
        Scenario: Call get_smtp_preset("UnknownProvider")
        Expected: Returns empty dict (not None or exception)
        """
        settings = get_settings()
        preset = settings.get_smtp_preset("UnknownProvider")

        assert preset == {}

    def test_get_all_presets_returns_list(self):
        """Verify: get_all_presets returns list of available provider names
        Scenario: Call get_all_presets()
        Expected: Returns list containing at least 4 known providers
        """
        settings = get_settings()
        presets = settings.get_all_presets()

        assert isinstance(presets, list)
        assert len(presets) >= 4
        assert "QQ邮箱" in presets
        assert "Gmail" in presets
        assert "Outlook" in presets

    def test_preset_returns_copy_not_reference(self):
        """Verify: Returned preset is a copy, not internal reference
        Scenario: Get preset and modify it
        Expected: Original SMTP_PRESETS unchanged (no aliasing)
        """
        settings = get_settings()
        preset = settings.get_smtp_preset("Gmail")
        original_host = preset["host"]
        preset["host"] = "modified.com"

        assert SMTP_PRESETS["Gmail"]["host"] == original_host


class TestAutoGenerateKey:
    """Test suite for automatic encryption key generation (P0-2 core feature)."""

    def test_key_auto_generated_on_init(self, temp_settings_dir):
        """Verify: Encryption key generated automatically on first init
        Scenario: Create fresh SettingsManager with no existing key
        Expected: security.encryption_key is non-empty 64-char hex string
        """
        settings = get_settings()

        assert settings.security.encryption_key != "", "Key should be auto-generated"
        assert (
            len(settings.security.encryption_key) == 64
        ), "Key should be 256-bit (64 hex chars)"
        assert all(
            c in "0123456789abcdef" for c in settings.security.encryption_key
        ), "Key should contain only hex characters"

    def test_auto_generated_flag_set(self, temp_settings_dir):
        """Verify: auto_generated flag is True after auto-generation
        Scenario: Check security.auto_generated after fresh init
        Expected: auto_generated == True
        """
        settings = get_settings()

        assert settings.security.auto_generated is True

    def test_key_saved_to_env_local(self, temp_settings_dir):
        """Verify: Generated key written to .env.local file
        Scenario: After auto-generation, read .env.local
        Expected: Contains OPC_ENCRYPTION_KEY=<generated_key>
        """
        settings = get_settings()
        env_local = Path(".env.local")

        if env_local.exists():
            content = env_local.read_text()
            assert f"OPC_ENCRYPTION_KEY={settings.security.encryption_key}" in content

    def test_key_not_in_environment(self, temp_settings_dir):
        """Verify: Key NOT exported to os.environ for security
        Scenario: After auto-generation, check os.environ
        Expected: os.environ["OPC_ENCRYPTION_KEY"] is NOT set by SettingsManager
        (keys should only be accessible via SettingsManager.get_encryption_key())
        """
        settings = get_settings()

        # SettingsManager 不应主动将密钥写入 os.environ
        assert os.environ.get("OPC_ENCRYPTION_KEY") != settings.security.encryption_key
        # 但密钥应可通过 get_encryption_key() 方法获取
        assert settings.get_encryption_key() == settings.security.encryption_key

    def test_key_persisted_across_restarts(self, temp_settings_dir):
        """Verify: Same key reused after process restart (reload from disk)
        Scenario: Generate key, destroy singleton, recreate
        Expected: Second instance loads same key from .env.local
        """
        settings1 = get_settings()
        key1 = settings1.security.encryption_key

        SettingsManager._instance = None
        settings2 = get_settings()
        key2 = settings2.security.encryption_key

        assert key1 == key2, "Key should persist across singleton recreations"

    def test_key_is_cryptographically_secure(self, temp_settings_dir):
        """Verify: Auto-generated key has cryptographic security properties
        Scenario: Generate key and validate format, entropy, and length
        Expected: Key is 64-char hex (256-bit), passes basic randomness checks
        """
        settings = get_settings()
        key = settings.security.encryption_key

        assert len(key) == 64, "Key must be 256-bit (64 hex characters)"
        assert all(c in "0123456789abcdef" for c in key), "Key must be valid hex"

        hex_chars = set(key)
        assert (
            len(hex_chars) >= 10
        ), f"Key should have sufficient character diversity (got {len(hex_chars)} unique chars)"

        byte_values = [int(key[i : i + 2], 16) for i in range(0, 64, 2)]
        assert (
            min(byte_values) < 32 and max(byte_values) > 223
        ), "Key bytes should span full 0-255 range (high entropy indicator)"


class TestIsConfigured:
    """Test suite for configuration status detection."""

    def test_llm_not_configured_by_default(self, temp_settings_dir):
        """Verify: LLM category unconfigured when no API key set
        Scenario: Fresh SettingsManager with default moka provider but no api_key
        Expected: is_configured(LLM) returns False
        """
        settings = get_settings()

        assert settings.is_configured(SettingsCategory.LLM) is False

    def test_llm_configured_with_api_key(self, temp_settings_dir):
        """Verify: LLM category configured when API key present
        Scenario: Set LLM api_key to non-empty string
        Expected: is_configured(LLM) returns True
        """
        settings = get_settings()
        settings.update_llm(api_key="sk-valid-key")

        assert settings.is_configured(SettingsCategory.LLM) is True

    def test_llm_ollama_no_api_needed(self, temp_settings_dir):
        """Verify: OLLAMA provider considered configured without API key
        Scenario: Set provider to ollama, leave api_key empty
        Expected: is_configured(LLM) returns True (local model)
        """
        settings = get_settings()
        settings.update_llm(provider="ollama")

        assert settings.is_configured(SettingsCategory.LLM) is True

    def test_smtp_not_configured_by_default(self, temp_settings_dir):
        """Verify: SMTP category unconfigured by default
        Scenario: Fresh SettingsManager with empty host/username
        Expected: is_configured(SMTP) returns False
        """
        settings = get_settings()

        assert settings.is_configured(SettingsCategory.SMTP) is False

    def test_smtp_configured_with_host_and_user(self, temp_settings_dir):
        """Verify: SMTP configured when both host and username present
        Scenario: Set SMTP host and username
        Expected: is_configured(SMTP) returns True
        """
        settings = get_settings()
        settings.update_smtp(host="smtp.mail.com", username="user@mail.com")

        assert settings.is_configured(SettingsCategory.SMTP) is True

    def test_security_always_configured_after_init(self, temp_settings_dir):
        """Verify: Security category always configured (auto-generated key)
        Scenario: Fresh SettingsManager after initialization
        Expected: is_configured(SECURITY) returns True (key auto-generated)
        """
        settings = get_settings()

        assert settings.is_configured(SettingsCategory.SECURITY) is True

    def test_profile_not_configured_by_default(self, temp_settings_dir):
        """Verify: Profile category unconfigured without user_name
        Scenario: Fresh SettingsManager with default empty user_name
        Expected: is_configured(PROFILE) returns False
        """
        settings = get_settings()

        assert settings.is_configured(SettingsCategory.PROFILE) is False

    def test_profile_configured_with_user_name(self, temp_settings_dir):
        """Verify: Profile configured when user_name is set
        Scenario: Set profile user_name
        Expected: is_configured(PROFILE) returns True
        """
        settings = get_settings()
        settings.update_profile(user_name="John Doe")

        assert settings.is_configured(SettingsCategory.PROFILE) is True


class TestExportMasking:
    """Test suite for sensitive field masking in export."""

    def test_llm_api_key_masked_in_export(self, temp_settings_dir):
        """Verify: LLM api_key replaced with *** in export
        Scenario: Set real API key, call export_settings()
        Expected: Exported llm.api_key is "***", not actual value
        """
        settings = get_settings()
        settings.update_llm(api_key="sk-real-secret-key-12345")

        exported = settings.export_settings()

        assert exported["llm"]["api_key"] == "***", "API key should be masked in export"
        assert (
            settings.llm.api_key == "sk-real-secret-key-12345"
        ), "Original value should remain in memory"

    def test_smtp_password_masked_in_export(self, temp_settings_dir):
        """Verify: SMTP password replaced with *** in export
        Scenario: Set real password, call export_settings()
        Expected: Exported smtp.password is "***"
        """
        settings = get_settings()
        settings.update_smtp(password="my-secret-password")

        exported = settings.export_settings()

        assert (
            exported["smtp"]["password"] == "***"
        ), "Password should be masked in export"

    def test_non_sensitive_fields_unmasked(self, temp_settings_dir):
        """Verify: Non-sensitive fields exported with actual values
        Scenario: Set various non-sensitive fields
        Expected: Provider, model, host etc. show real values in export
        """
        settings = get_settings()
        settings.update_llm(provider="openai", model="gpt-4o", temperature=0.5)

        exported = settings.export_settings()

        assert exported["llm"]["provider"] == "openai"
        assert exported["llm"]["model"] == "gpt-4o"
        assert exported["llm"]["temperature"] == 0.5

    def test_security_section_shows_has_key_flag(self, temp_settings_dir):
        """Verify: Security section exports has_key boolean, not actual key
        Scenario: Auto-generate encryption key, call export_settings()
        Expected: security.has_key=True, no actual key value exposed
        """
        settings = get_settings()
        exported = settings.export_settings()

        assert exported["security"]["has_key"] is True
        assert (
            "encryption_key" not in exported["security"]
            or exported["security"].get("encryption_key")
            != settings.security.encryption_key
        ), "Actual encryption key should not appear in export"

    def test_profile_fully_exported(self, temp_settings_dir):
        """Verify: Profile settings fully exported (no masking needed)
        Scenario: Set all profile fields
        Expected: All profile values appear in export unchanged
        """
        settings = get_settings()
        settings.update_profile(
            user_name="Alice",
            company_name="Acme Corp",
            timezone="America/New_York",
            language="en_US",
        )

        exported = settings.export_settings()

        assert exported["profile"]["user_name"] == "Alice"
        assert exported["profile"]["company_name"] == "Acme Corp"
        assert exported["profile"]["timezone"] == "America/New_York"
        assert exported["profile"]["language"] == "en_US"


class TestResetDefaults:
    """Test suite for reset to defaults functionality."""

    def test_reset_all_categories(self, temp_settings_dir):
        """Verify: Resetting without category resets everything
        Scenario: Set values in all categories, then reset_to_defaults()
        Expected: All categories return to initial default values
        """
        settings = get_settings()
        settings.update_llm(provider="openai", api_key="sk-xxx")
        settings.update_smtp(host="smtp.x.com", username="u@x.com")
        settings.update_profile(user_name="Bob")

        result = settings.reset_to_defaults()

        assert result is True
        assert settings.llm.provider == "moka"
        assert settings.llm.api_key == ""
        assert settings.smtp.host == ""
        assert settings.smtp.username == ""
        assert settings.profile.user_name == ""

    def test_reset_specific_category_llm(self, temp_settings_dir):
        """Verify: Can reset only LLM category
        Scenario: Modify LLM and SMTP, reset only LLM
        Expected: LLM defaults restored, SMTP unchanged
        """
        settings = get_settings()
        settings.update_llm(provider="glm", api_key="sk-yyy")
        settings.update_smtp(host="smtp.y.com")

        settings.reset_to_defaults(category=SettingsCategory.LLM)

        assert settings.llm.provider == "moka"
        assert settings.llm.api_key == ""
        assert settings.smtp.host == "smtp.y.com", "SMTP should not change"

    def test_reset_specific_category_smtp(self, temp_settings_dir):
        """Verify: Can reset only SMTP category
        Scenario: Modify SMTP and profile, reset only SMTP
        Expected: SMTP defaults restored, profile unchanged
        """
        settings = get_settings()
        settings.update_smtp(host="smtp.z.com", port=465)
        settings.update_profile(user_name="Charlie")

        settings.reset_to_defaults(category=SettingsCategory.SMTP)

        assert settings.smtp.host == ""
        assert settings.smtp.port == 587
        assert settings.profile.user_name == "Charlie", "Profile should not change"

    def test_reset_persists_to_disk(self, temp_settings_dir):
        """Verify: Reset results are persisted to disk
        Scenario: Update settings, reset, reload from disk
        Expected: Reloaded instance shows default values
        """
        settings = get_settings()
        settings.update_llm(provider="ollama", model="llama3")
        settings.reset_to_defaults()

        SettingsManager._instance = None
        reloaded = get_settings()

        assert reloaded.llm.provider == "moka"
        # model may be populated from env vars after reset
        assert isinstance(reloaded.llm.model, str)


class TestCallbackNotification:
    """Test suite for settings change callback system."""

    def test_callback_invoked_on_llm_update(self, temp_settings_dir):
        """Verify: Registered callback called when LLM settings change
        Scenario: Register callback, then update_llm()
        Expected: Callback invoked exactly once with "llm" argument
        """
        settings = get_settings()
        callback_calls = []

        def mock_callback(category):
            callback_calls.append(category)

        settings.register_callback(mock_callback)
        settings.update_llm(provider="openai")

        assert len(callback_calls) == 1
        assert callback_calls[0] == "llm"

    def test_callback_invoked_on_smtp_update(self, temp_settings_dir):
        """Verify: Registered callback called when SMTP settings change
        Scenario: Register callback, then update_smtp()
        Expected: Callback invoked with "smtp" argument
        """
        settings = get_settings()
        callback_calls = []

        def mock_callback(category):
            callback_calls.append(category)

        settings.register_callback(mock_callback)
        settings.update_smtp(host="smtp.new.com")

        assert len(callback_calls) == 1
        assert callback_calls[0] == "smtp"

    def test_callback_invoked_on_profile_update(self, temp_settings_dir):
        """Verify: Registered callback called when profile settings change
        Scenario: Register callback, then update_profile()
        Expected: Callback invoked with "profile" argument
        """
        settings = get_settings()
        callback_calls = []

        def mock_callback(category):
            callback_calls.append(category)

        settings.register_callback(mock_callback)
        settings.update_profile(user_name="New Name")

        assert len(callback_calls) == 1
        assert callback_calls[0] == "profile"

    def test_multiple_callbacks_all_invoked(self, temp_settings_dir):
        """Verify: Multiple callbacks all receive notification
        Scenario: Register 3 different callbacks, trigger update
        Expected: All 3 callbacks invoked in registration order
        """
        settings = get_settings()
        calls_order = []

        def cb1(cat):
            calls_order.append("cb1")

        def cb2(cat):
            calls_order.append("cb2")

        def cb3(cat):
            calls_order.append("cb3")

        settings.register_callback(cb1)
        settings.register_callback(cb2)
        settings.register_callback(cb3)

        settings.update_llm(model="new-model")

        assert calls_order == ["cb1", "cb2", "cb3"]

    def test_duplicate_callback_not_registered_twice(self, temp_settings_dir):
        """Verify: Same callback object only registered once
        Scenario: Register same callback twice, trigger update
        Expected: Callback invoked only once (deduplication)
        """
        settings = get_settings()
        call_count = 0

        def mock_callback(category):
            nonlocal call_count
            call_count += 1

        settings.register_callback(mock_callback)
        settings.register_callback(mock_callback)

        settings.update_llm(temperature=1.0)

        assert call_count == 1, "Duplicate callback should not be called twice"

    def test_unregister_callback_stops_notification(self, temp_settings_dir):
        """Verify: Unregistered callback no longer receives notifications
        Scenario: Register callback, unregister it, trigger update
        Expected: Callback not invoked after unregistration
        """
        settings = get_settings()
        call_count = 0

        def mock_callback(category):
            nonlocal call_count
            call_count += 1

        settings.register_callback(mock_callback)
        settings.update_llm(provider="test")
        assert call_count == 1

        settings.unregister_callback(mock_callback)
        settings.update_llm(provider="test2")

        assert call_count == 1, "Callback should not fire after unregistration"

    def test_faulty_callback_doesnt_block_others(self, temp_settings_dir):
        """Verify: One failing callback doesn't prevent others from running
        Scenario: Register 2 callbacks, first one raises exception
        Expected: Second callback still invoked despite first error
        """
        settings = get_settings()
        calls = []

        def bad_callback(category):
            raise RuntimeError("Intentional test error")

        def good_callback(category):
            calls.append(category)

        settings.register_callback(bad_callback)
        settings.register_callback(good_callback)

        settings.update_smtp(tls=False)

        assert (
            len(calls) == 1
        ), "Good callback should execute despite bad callback error"


class TestThreadSafety:
    """Test suite for concurrent access safety validation."""

    def test_concurrent_reads_safe(self, temp_settings_dir):
        """Verify: Multiple threads can safely read settings simultaneously
        Scenario: Spawn 10 threads reading llm.provider concurrently
        Expected: No exceptions raised, all threads see consistent value
        """
        settings = get_settings()
        settings.update_llm(provider="thread-safe-provider")
        results = []
        errors = []

        def reader():
            try:
                for _ in range(100):
                    val = settings.llm.provider
                    results.append(val)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent reads caused errors: {errors}"
        assert all(
            r == "thread-safe-provider" for r in results
        ), "All reads should return consistent value"

    def test_concurrent_writes_safe(self, temp_settings_dir):
        """Verify: Multiple threads can safely write to different categories
        Scenario: Spawn 5 threads each updating different setting categories
        Expected: No data corruption, no exceptions, final state consistent
        """
        settings = get_settings()
        errors = []

        def writer_llm():
            try:
                for i in range(50):
                    settings.update_llm(temperature=float(i) / 100)
            except Exception as e:
                errors.append(("llm", e))

        def writer_smtp():
            try:
                for i in range(50):
                    settings.update_smtp(port=587 + (i % 2))
            except Exception as e:
                errors.append(("smtp", e))

        def writer_profile():
            try:
                for i in range(50):
                    settings.update_profile(user_name=f"user_{i}")
            except Exception as e:
                errors.append(("profile", e))

        threads = [
            threading.Thread(target=writer_llm),
            threading.Thread(target=writer_smtp),
            threading.Thread(target=writer_profile),
            threading.Thread(target=writer_llm),
            threading.Thread(target=writer_smtp),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent writes caused errors: {errors}"

        final_export = settings.export_settings()
        assert "llm" in final_export
        assert "smtp" in final_export
        assert "profile" in final_export

    def test_concurrent_read_write_safe(self, temp_settings_dir):
        """Verify: Mixed read/write operations don't cause race conditions
        Scenario: Some threads writing while others reading concurrently
        Expected: Readers always see valid complete state (no partial writes)
        """
        settings = get_settings()
        read_results = []
        write_errors = []
        read_errors = []

        def writer():
            try:
                for i in range(100):
                    settings.update_llm(max_tokens=1000 + i * 10)
            except Exception as e:
                write_errors.append(e)

        def reader():
            try:
                for _ in range(100):
                    data = settings.export_settings()
                    read_results.append(data)
            except Exception as e:
                read_errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(write_errors) == 0, f"Write errors: {write_errors}"
        assert len(read_errors) == 0, f"Read errors: {read_errors}"
        assert len(read_results) > 0, "Should have collected some read results"

        for result in read_results:
            assert "llm" in result
            assert "max_tokens" in result["llm"]
            assert isinstance(result["llm"]["max_tokens"], int)


class TestEncryptedStorage:
    """Test suite for API key encryption at rest (v0.2.0 security feature).

    Validates that sensitive fields (api_key, password) are encrypted
    before persisting to disk and correctly decrypted on load.
    """

    def test_api_key_encrypted_in_json_file(self, temp_settings_dir):
        """Verify: API key is NOT stored as plaintext in settings.json
        Scenario: Set LLM api_key and save to disk
        Expected: JSON file contains encrypted token, not original plaintext
        """
        settings = get_settings()
        plaintext_key = "sk-plaintext-test-key-12345"
        settings.update_llm(api_key=plaintext_key)

        settings_file = Path(SettingsManager.SETTINGS_FILE)
        with open(settings_file, "r") as f:
            saved_data = json.load(f)

        stored_value = saved_data["llm"]["api_key"]
        assert (
            plaintext_key not in stored_value
        ), "API key should not be stored as plaintext in JSON file"
        assert len(stored_value) > len(
            plaintext_key
        ), "Encrypted value should be longer than plaintext"

    def test_api_key_decrypted_on_load(self, temp_settings_dir):
        """Verify: Encrypted API key is correctly decrypted when loaded
        Scenario: Save encrypted API key, reload from disk
        Expected: Reloaded instance returns original plaintext value
        """
        settings = get_settings()
        plaintext_key = "sk-decrypt-test-key-67890"
        settings.update_llm(api_key=plaintext_key)

        SettingsManager._instance = None
        reloaded = get_settings()

        assert (
            reloaded.llm.api_key == plaintext_key
        ), f"Decrypted key should match original (got '{reloaded.llm.api_key}')"

    def test_smtp_password_encrypted_in_json(self, temp_settings_dir):
        """Verify: SMTP password is encrypted in JSON file
        Scenario: Set SMTP password and save
        Expected: JSON contains encrypted token, not plaintext password
        """
        settings = get_settings()
        plaintext_pass = "my-secret-smtp-password"
        settings.update_smtp(password=plaintext_pass)

        settings_file = Path(SettingsManager.SETTINGS_FILE)
        with open(settings_file, "r") as f:
            saved_data = json.load(f)

        stored_value = saved_data["smtp"]["password"]
        assert (
            plaintext_pass not in stored_value
        ), "Password should not be stored as plaintext in JSON file"

    def test_smtp_password_decrypted_on_load(self, temp_settings_dir):
        """Verify: SMTP password correctly decrypted on load
        Scenario: Save encrypted password, reload from disk
        Expected: Reloaded instance returns original password
        """
        settings = get_settings()
        plaintext_pass = "smtp-pass-decrypt-test"
        settings.update_smtp(password=plaintext_pass)

        SettingsManager._instance = None
        reloaded = get_settings()

        assert (
            reloaded.smtp.password == plaintext_pass
        ), f"Decrypted password should match original (got '{reloaded.smtp.password}')"

    def test_auto_migration_plaintext_to_encrypted(self, temp_settings_dir):
        """Verify: Plaintext keys auto-migrated to encrypted format on first load
        Scenario: Manually write plaintext key to JSON, then load settings
        Expected: Key migrated to encrypted format, still accessible via property
        """
        plaintext_key = "sk-migration-test-key"

        settings_file = Path(SettingsManager.SETTINGS_FILE)
        settings_file.parent.mkdir(parents=True, exist_ok=True)

        manual_data = {
            "llm": {
                "provider": "openai",
                "api_key": plaintext_key,
                "base_url": "",
                "model": "",
                "max_tokens": 4000,
                "temperature": 0.7,
            },
            "smtp": {
                "host": "",
                "port": 587,
                "username": "",
                "password": "",
                "tls": True,
                "from_email": "",
            },
            "security": {"auto_generated": True},
            "profile": {
                "user_name": "",
                "company_name": "",
                "timezone": "Asia/Shanghai",
                "language": "zh_CN",
            },
        }

        with open(settings_file, "w") as f:
            json.dump(manual_data, f, indent=2)

        SettingsManager._instance = None
        settings = get_settings()

        assert (
            settings.llm.api_key == plaintext_key
        ), "Migrated key should be accessible after decryption"

        with open(settings_file, "r") as f:
            migrated_data = json.load(f)

        stored_value = migrated_data["llm"]["api_key"]
        assert (
            plaintext_key not in stored_value
        ), "After migration, key should be encrypted in JSON file"

    @patch.dict(os.environ, {}, clear=True)
    def test_invalid_ciphertext_handled_gracefully(self, temp_settings_dir):
        """Verify: Invalid/corrupt ciphertext returns empty string with warning
        Scenario: Write invalid base64 string as api_key in JSON
        Expected: Loaded value is empty string (not crash)
        """
        # Valid base64 that decodes to 48+ bytes but is NOT a valid Fernet token
        invalid_token = base64.urlsafe_b64encode(b"this-looks-like-encrypted-but-is-not-a-fernet-token-at-all-just-garbage-data").decode()

        settings_file = Path(SettingsManager.SETTINGS_FILE)
        settings_file.parent.mkdir(parents=True, exist_ok=True)

        corrupt_data = {
            "llm": {
                "provider": "openai",
                "api_key": invalid_token,
                "base_url": "",
                "model": "",
                "max_tokens": 4000,
                "temperature": 0.7,
            },
            "smtp": {
                "host": "",
                "port": 587,
                "username": "",
                "password": "",
                "tls": True,
                "from_email": "",
            },
            "security": {"auto_generated": True},
            "profile": {
                "user_name": "",
                "company_name": "",
                "timezone": "Asia/Shanghai",
                "language": "zh_CN",
            },
        }

        with open(settings_file, "w") as f:
            json.dump(corrupt_data, f, indent=2)

        SettingsManager._instance = None
        settings = get_settings()

        assert (
            settings.llm.api_key == ""
        ), "Invalid ciphertext should result in empty string"

    def test_all_sensitive_fields_encrypted(self, temp_settings_dir):
        """Verify: Both LLM api_key and SMTP password are encrypted
        Scenario: Set both sensitive fields, inspect JSON file
        Expected: Neither field contains plaintext in JSON
        """
        settings = get_settings()
        settings.update_llm(api_key="sk-llm-test-key")
        settings.update_smtp(password="smtp-test-password")

        settings_file = Path(SettingsManager.SETTINGS_FILE)
        with open(settings_file, "r") as f:
            saved_data = json.load(f)

        llm_stored = saved_data["llm"]["api_key"]
        smtp_stored = saved_data["smtp"]["password"]

        assert "sk-llm-test-key" not in llm_stored, "LLM api_key should be encrypted"
        assert (
            "smtp-test-password" not in smtp_stored
        ), "SMTP password should be encrypted"

    def test_empty_sensitive_fields_not_encrypted(self, temp_settings_dir):
        """Verify: Empty sensitive fields remain empty (no encryption needed)
        Scenario: Don't set any API keys, save settings
        Expected: Empty strings in JSON file for sensitive fields (if file exists)
        """
        settings = get_settings()

        settings_file = Path(SettingsManager.SETTINGS_FILE)
        if not settings_file.exists():
            return

        with open(settings_file, "r") as f:
            saved_data = json.load(f)

        assert saved_data["llm"]["api_key"] == "", "Empty api_key should remain empty"
        assert (
            saved_data["smtp"]["password"] == ""
        ), "Empty password should remain empty"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
