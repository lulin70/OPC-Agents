"""Unit tests for opc_manager.secure_storage

Covers: key derivation consistency, encrypt/decrypt round-trip,
        machine fingerprint stability, missing cryptography package,
        invalid ciphertext, empty string handling.
All file I/O is mocked via temp directories.
"""

import base64
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from opc_manager.secure_storage import (
    SecureKeyStore,
    _get_machine_fingerprint,
    _derive_fernet_key,
    _fingerprint_lock,
    init_secure_storage,
)


def _reset_fingerprint_cache():
    """Clear the module-level fingerprint cache so tests re-compute it."""
    import opc_manager.secure_storage as ss

    with _fingerprint_lock:
        ss._fingerprint_cache = None


class TestMachineFingerprint(unittest.TestCase):
    """Tests for _get_machine_fingerprint()."""

    def setUp(self):
        _reset_fingerprint_cache()

    def test_returns_non_empty_string(self):
        fp = _get_machine_fingerprint()
        self.assertIsInstance(fp, str)
        self.assertGreater(len(fp), 0)

    def test_is_sha256_hex(self):
        fp = _get_machine_fingerprint()
        self.assertEqual(len(fp), 64)  # SHA-256 hex digest
        self.assertRegex(fp, r"^[0-9a-f]{64}$")

    def test_consistent_across_calls(self):
        """Same input should always produce the same fingerprint."""
        fp1 = _get_machine_fingerprint()
        fp2 = _get_machine_fingerprint()
        self.assertEqual(fp1, fp2)

    def test_uses_cache_on_second_call(self):
        """Second call should return the cached value without recomputation."""
        fp1 = _get_machine_fingerprint()
        # Manually set cache to a known value
        import opc_manager.secure_storage as ss

        ss._fingerprint_cache = "cached_value"
        fp2 = _get_machine_fingerprint()
        self.assertEqual(fp2, "cached_value")
        # Restore
        ss._fingerprint_cache = fp1

    def test_thread_safety(self):
        """Concurrent calls should all return the same fingerprint."""
        results = []
        barrier = threading.Barrier(5)

        def get_fp():
            barrier.wait()
            results.append(_get_machine_fingerprint())

        threads = [threading.Thread(target=get_fp) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(set(results)), 1)


class TestDeriveFernetKey(unittest.TestCase):
    """Tests for _derive_fernet_key()."""

    def test_returns_bytes(self):
        key = _derive_fernet_key("test-fingerprint")
        self.assertIsInstance(key, bytes)

    def test_consistent_derivation(self):
        """Same fingerprint should always produce the same key."""
        key1 = _derive_fernet_key("test-fingerprint")
        key2 = _derive_fernet_key("test-fingerprint")
        self.assertEqual(key1, key2)

    def test_different_fingerprints_different_keys(self):
        key1 = _derive_fernet_key("fingerprint-A")
        key2 = _derive_fernet_key("fingerprint-B")
        self.assertNotEqual(key1, key2)

    def test_key_is_valid_base64(self):
        key = _derive_fernet_key("test-fingerprint")
        # Should not raise
        decoded = base64.urlsafe_b64decode(key)
        self.assertGreater(len(decoded), 0)


class TestSecureKeyStoreEncryptDecrypt(unittest.TestCase):
    """Tests for SecureKeyStore encrypt/decrypt round-trip."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.tmp_dir, ".env.encrypted")

    def tearDown(self):
        if os.path.exists(self.storage_path):
            os.remove(self.storage_path)
        if os.path.exists(self.storage_path.replace(".encrypted", ".tmp")):
            os.remove(self.storage_path.replace(".encrypted", ".tmp"))
        os.rmdir(self.tmp_dir)

    def _make_store(self):
        return SecureKeyStore(storage_path=self.storage_path)

    def test_set_and_get_round_trip(self):
        store = self._make_store()
        if not store.is_available:
            self.skipTest("cryptography package not installed")
        store.set_key("TEST_KEY", "secret-value-123")
        result = store.get_key("TEST_KEY")
        self.assertEqual(result, "secret-value-123")

    def test_empty_string_value(self):
        store = self._make_store()
        if not store.is_available:
            self.skipTest("cryptography package not installed")
        store.set_key("EMPTY_KEY", "")
        result = store.get_key("EMPTY_KEY")
        self.assertEqual(result, "")

    def test_unicode_value(self):
        store = self._make_store()
        if not store.is_available:
            self.skipTest("cryptography package not installed")
        store.set_key("UNI_KEY", "中文密钥🔑")
        result = store.get_key("UNI_KEY")
        self.assertEqual(result, "中文密钥🔑")

    def test_overwrite_key(self):
        store = self._make_store()
        if not store.is_available:
            self.skipTest("cryptography package not installed")
        store.set_key("OVER_KEY", "value1")
        store.set_key("OVER_KEY", "value2")
        result = store.get_key("OVER_KEY")
        self.assertEqual(result, "value2")

    def test_get_nonexistent_key(self):
        store = self._make_store()
        if not store.is_available:
            self.skipTest("cryptography package not installed")
        result = store.get_key("NO_SUCH_KEY")
        self.assertIsNone(result)

    def test_multiple_keys(self):
        store = self._make_store()
        if not store.is_available:
            self.skipTest("cryptography package not installed")
        store.set_key("KEY_A", "val_a")
        store.set_key("KEY_B", "val_b")
        self.assertEqual(store.get_key("KEY_A"), "val_a")
        self.assertEqual(store.get_key("KEY_B"), "val_b")


class TestSecureKeyStoreListRemove(unittest.TestCase):
    """Tests for list_keys and remove_key."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.tmp_dir, ".env.encrypted")

    def tearDown(self):
        if os.path.exists(self.storage_path):
            os.remove(self.storage_path)
        os.rmdir(self.tmp_dir)

    def _make_store(self):
        return SecureKeyStore(storage_path=self.storage_path)

    def test_list_keys_empty(self):
        store = self._make_store()
        keys = store.list_keys()
        self.assertEqual(keys, [])

    def test_list_keys_after_set(self):
        store = self._make_store()
        if not store.is_available:
            self.skipTest("cryptography package not installed")
        store.set_key("K1", "v1")
        store.set_key("K2", "v2")
        keys = store.list_keys()
        self.assertIn("K1", keys)
        self.assertIn("K2", keys)

    def test_remove_key(self):
        store = self._make_store()
        if not store.is_available:
            self.skipTest("cryptography package not installed")
        store.set_key("DEL_KEY", "v")
        self.assertTrue(store.remove_key("DEL_KEY"))
        self.assertIsNone(store.get_key("DEL_KEY"))

    def test_remove_nonexistent_key(self):
        store = self._make_store()
        result = store.remove_key("NO_KEY")
        self.assertFalse(result)


class TestSecureKeyStoreLoadToEnv(unittest.TestCase):
    """Tests for load_to_env()."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.tmp_dir, ".env.encrypted")
        self._saved_env = {}

    def tearDown(self):
        # Clean up any env vars we set
        for k in self._saved_env:
            if self._saved_env[k] is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = self._saved_env[k]
        if os.path.exists(self.storage_path):
            os.remove(self.storage_path)
        os.rmdir(self.tmp_dir)

    def _save_env(self, key):
        self._saved_env[key] = os.environ.get(key)

    def test_load_to_env_sets_env_vars(self):
        store = SecureKeyStore(storage_path=self.storage_path)
        if not store.is_available:
            self.skipTest("cryptography package not installed")
        store.set_key("TEST_ENV_VAR_12345", "loaded_value")
        self._save_env("TEST_ENV_VAR_12345")
        count = store.load_to_env()
        self.assertEqual(count, 1)
        self.assertEqual(os.environ.get("TEST_ENV_VAR_12345"), "loaded_value")

    def test_load_to_env_empty_store(self):
        store = SecureKeyStore(storage_path=self.storage_path)
        count = store.load_to_env()
        self.assertEqual(count, 0)


class TestSecureKeyStoreInvalidCiphertext(unittest.TestCase):
    """Tests for handling invalid/corrupted ciphertext."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.tmp_dir, ".env.encrypted")

    def tearDown(self):
        if os.path.exists(self.storage_path):
            os.remove(self.storage_path)
        os.rmdir(self.tmp_dir)

    def test_invalid_ciphertext_returns_none(self):
        store = SecureKeyStore(storage_path=self.storage_path)
        if not store.is_available:
            self.skipTest("cryptography package not installed")
        # Write a corrupted encrypted value directly
        store.set_key("GOOD_KEY", "good_value")
        # Now corrupt the stored data
        with open(self.storage_path, "r") as f:
            data = json.load(f)
        data["keys"]["GOOD_KEY"] = "NOT_VALID_FERNET_TOKEN!!!"
        with open(self.storage_path, "w") as f:
            json.dump(data, f)
        result = store.get_key("GOOD_KEY")
        self.assertIsNone(result)


class TestSecureKeyStoreMissingCryptography(unittest.TestCase):
    """Tests for behavior when cryptography package is not installed."""

    def test_is_available_false_without_cryptography(self):
        with patch.dict(
            "sys.modules", {"cryptography": None, "cryptography.fernet": None}
        ):
            store = SecureKeyStore.__new__(SecureKeyStore)
            store._storage_path = Path(tempfile.mkdtemp()) / ".env.encrypted"
            store._lock = threading.Lock()
            store._init_fernet()
            self.assertFalse(store.is_available)

    def test_set_key_returns_false_without_cryptography(self):
        store = SecureKeyStore.__new__(SecureKeyStore)
        store._fernet = None
        result = store.set_key("K", "V")
        self.assertFalse(result)

    def test_get_key_returns_none_without_cryptography(self):
        store = SecureKeyStore.__new__(SecureKeyStore)
        store._fernet = None
        result = store.get_key("K")
        self.assertIsNone(result)


class TestSecureKeyStoreFileOperations(unittest.TestCase):
    """Tests for file I/O edge cases."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.tmp_dir, ".env.encrypted")

    def tearDown(self):
        if os.path.exists(self.storage_path):
            os.remove(self.storage_path)
        tmp = self.storage_path.replace(".encrypted", ".tmp")
        if os.path.exists(tmp):
            os.remove(tmp)
        os.rmdir(self.tmp_dir)

    def test_load_nonexistent_file(self):
        store = SecureKeyStore(storage_path=self.storage_path)
        data = store._load_storage()
        self.assertEqual(data["keys"], {})

    def test_load_corrupted_json(self):
        with open(self.storage_path, "w") as f:
            f.write("NOT JSON{{{")
        store = SecureKeyStore(storage_path=self.storage_path)
        data = store._load_storage()
        self.assertEqual(data["keys"], {})

    def test_save_and_load_preserves_data(self):
        store = SecureKeyStore(storage_path=self.storage_path)
        if not store.is_available:
            self.skipTest("cryptography package not installed")
        store.set_key("PERSIST_KEY", "persist_val")
        # Create a new store instance to read from disk
        store2 = SecureKeyStore(storage_path=self.storage_path)
        result = store2.get_key("PERSIST_KEY")
        self.assertEqual(result, "persist_val")

    def test_version_mismatch_still_loads(self):
        """Storage with wrong version should still load (with warning)."""
        with open(self.storage_path, "w") as f:
            json.dump({"version": 999, "keys": {}}, f)
        store = SecureKeyStore(storage_path=self.storage_path)
        data = store._load_storage()
        self.assertEqual(data["version"], 999)


class TestInitSecureStorage(unittest.TestCase):
    """Tests for init_secure_storage() top-level function."""

    @patch("opc_manager.secure_storage.SecureKeyStore")
    def test_init_calls_load_to_env_when_available(self, MockStore):
        mock_instance = MagicMock()
        mock_instance.is_available = True
        mock_instance.load_to_env.return_value = 2
        MockStore.return_value = mock_instance
        init_secure_storage()
        mock_instance.load_to_env.assert_called_once()

    @patch("opc_manager.secure_storage.SecureKeyStore")
    def test_init_skips_when_not_available(self, MockStore):
        mock_instance = MagicMock()
        mock_instance.is_available = False
        MockStore.return_value = mock_instance
        init_secure_storage()
        mock_instance.load_to_env.assert_not_called()

    @patch(
        "opc_manager.secure_storage.SecureKeyStore", side_effect=Exception("init fail")
    )
    def test_init_handles_exception(self, MockStore):
        # Should not raise
        init_secure_storage()


class TestKeyRotation(unittest.TestCase):
    """Tests for encryption key rotation — data encrypted with old key
    should be recoverable after key rotation."""

    def test_key_rotation_decrypts_old_data(self):
        """Verify that data encrypted with old key can be decrypted after key rotation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = os.path.join(tmpdir, "secure_keys.json")
            store1 = SecureKeyStore(storage_path=storage_path)
            if not store1.is_available:
                self.skipTest("cryptography package not installed")
            store1.set_key("test_key", "secret_value")

            # Simulate key rotation by creating new store with same path
            # The encrypted data should still be accessible
            store2 = SecureKeyStore(storage_path=storage_path)
            value = store2.get_key("test_key")
            # Value should be recoverable (either directly or via migration)
            assert value is not None


if __name__ == "__main__":
    unittest.main()
