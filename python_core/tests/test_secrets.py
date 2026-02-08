"""Secrets store tests.

REQ: SEC-CRY-002
"""

import os
import tempfile
import unittest

from app.security.secrets import SecretStore


class SecretStoreTests(unittest.TestCase):
    def test_set_get_delete_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "secrets.db")
            store = SecretStore(db_path=db_path, db_key="test-key")

            store.set_secret("plaid_access_token", "token123")
            self.assertEqual(store.get_secret("plaid_access_token"), "token123")

            store.delete_secret("plaid_access_token")
            self.assertIsNone(store.get_secret("plaid_access_token"))
