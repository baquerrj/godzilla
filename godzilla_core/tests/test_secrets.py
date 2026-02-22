"""Secrets store tests.

REQ: SEC-CRY-002, SYS-004
"""

import os
import tempfile
import unittest

from sqlcipher3 import dbapi2 as sqlcipher

from godzilla_core.security.secrets import SecretStore, SecretStoreError, store_from_env


class SecretStoreTests(unittest.TestCase):
    """Component tests for encrypted secret storage operations.

    REQ: SEC-CRY-002, SYS-004
    """

    def setUp(self) -> None:
        """Create a temp directory with a fresh secrets DB.

        REQ: SEC-CRY-002
        """
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "secrets.db")
        self.db_key = "test-key"

    def tearDown(self) -> None:
        """Remove temp directory.

        REQ: SEC-CRY-002
        """
        self.tmp_dir.cleanup()

    def test_set_get_delete_roundtrip(self) -> None:
        """Verify secret lifecycle operations and timezone metadata persistence.

        REQ: SEC-CRY-002, SYS-004
        """
        store = SecretStore(db_path=self.db_path, db_key=self.db_key)

        original_tz = os.environ.get("GODZILLA_LOCAL_TZ")
        os.environ["GODZILLA_LOCAL_TZ"] = "UTC"
        try:
            store.set_secret("plaid_access_token", "token123")
            self.assertEqual(store.get_secret("plaid_access_token"), "token123")

            conn = sqlcipher.connect(self.db_path)
            conn.execute("PRAGMA key = 'test-key';")
            row = conn.execute(
                "SELECT updated_at_tz, updated_at_offset_minutes FROM secrets WHERE key = ?",
                ("plaid_access_token",),
            ).fetchone()
            conn.close()
            self.assertEqual(row[0], "UTC")
            self.assertEqual(row[1], 0)

            store.delete_secret("plaid_access_token")
            self.assertIsNone(store.get_secret("plaid_access_token"))
        finally:
            if original_tz is None:
                os.environ.pop("GODZILLA_LOCAL_TZ", None)
            else:
                os.environ["GODZILLA_LOCAL_TZ"] = original_tz

    def test_get_nonexistent_key_returns_none(self) -> None:
        """get_secret for a missing key returns None without error.

        REQ: SEC-CRY-002
        """
        store = SecretStore(db_path=self.db_path, db_key=self.db_key)
        self.assertIsNone(store.get_secret("no_such_key"))

    def test_overwrite_secret(self) -> None:
        """set_secret on an existing key updates the stored value.

        REQ: SEC-CRY-002
        """
        store = SecretStore(db_path=self.db_path, db_key=self.db_key)
        store.set_secret("mykey", "first")
        store.set_secret("mykey", "second")
        self.assertEqual(store.get_secret("mykey"), "second")

    def test_set_empty_key_raises(self) -> None:
        """set_secret with an empty key raises ValueError.

        REQ: SEC-CRY-002
        """
        store = SecretStore(db_path=self.db_path, db_key=self.db_key)
        with self.assertRaises(ValueError):
            store.set_secret("", "value")

    def test_get_empty_key_raises(self) -> None:
        """get_secret with an empty key raises ValueError.

        REQ: SEC-CRY-002
        """
        store = SecretStore(db_path=self.db_path, db_key=self.db_key)
        with self.assertRaises(ValueError):
            store.get_secret("")

    def test_delete_empty_key_raises(self) -> None:
        """delete_secret with an empty key raises ValueError.

        REQ: SEC-CRY-002
        """
        store = SecretStore(db_path=self.db_path, db_key=self.db_key)
        with self.assertRaises(ValueError):
            store.delete_secret("")

    def test_empty_db_path_raises(self) -> None:
        """Constructing SecretStore with an empty db_path raises ValueError.

        REQ: SEC-CRY-002
        """
        with self.assertRaises(ValueError):
            SecretStore(db_path="", db_key="key")

    def test_empty_db_key_raises(self) -> None:
        """Constructing SecretStore with an empty db_key raises ValueError.

        REQ: SEC-CRY-002
        """
        with self.assertRaises(ValueError):
            SecretStore(db_path=self.db_path, db_key="")

    def test_delete_nonexistent_key_is_silent(self) -> None:
        """delete_secret for a key that does not exist completes without error.

        REQ: SEC-CRY-002
        """
        store = SecretStore(db_path=self.db_path, db_key=self.db_key)
        store.delete_secret("never_set")  # should not raise


class StoreFromEnvTests(unittest.TestCase):
    """Tests for environment-based SecretStore construction.

    REQ: SEC-CRY-002
    """

    def test_store_from_env_missing_vars_raises(self) -> None:
        """store_from_env raises SecretStoreError when env vars are absent.

        REQ: SEC-CRY-002
        """
        saved_path = os.environ.pop("GODZILLA_SECRETS_PATH", None)
        saved_key = os.environ.pop("GODZILLA_SECRETS_KEY", None)
        try:
            with self.assertRaises(SecretStoreError):
                store_from_env()
        finally:
            if saved_path is not None:
                os.environ["GODZILLA_SECRETS_PATH"] = saved_path
            if saved_key is not None:
                os.environ["GODZILLA_SECRETS_KEY"] = saved_key

    def test_store_from_env_creates_store(self) -> None:
        """store_from_env returns a functional SecretStore from env vars.

        REQ: SEC-CRY-002
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "secrets.db")
            saved_path = os.environ.get("GODZILLA_SECRETS_PATH")
            saved_key = os.environ.get("GODZILLA_SECRETS_KEY")
            os.environ["GODZILLA_SECRETS_PATH"] = db_path
            os.environ["GODZILLA_SECRETS_KEY"] = "envkey"
            try:
                store = store_from_env()
                store.set_secret("k", "v")
                self.assertEqual(store.get_secret("k"), "v")
            finally:
                if saved_path is None:
                    os.environ.pop("GODZILLA_SECRETS_PATH", None)
                else:
                    os.environ["GODZILLA_SECRETS_PATH"] = saved_path
                if saved_key is None:
                    os.environ.pop("GODZILLA_SECRETS_KEY", None)
                else:
                    os.environ["GODZILLA_SECRETS_KEY"] = saved_key
