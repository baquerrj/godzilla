"""Secrets store tests.

REQ: SEC-CRY-002, SYS-004
"""

import os
import tempfile
import unittest

from app.security.secrets import SecretStore
from sqlcipher3 import dbapi2 as sqlcipher


class SecretStoreTests(unittest.TestCase):
    def test_set_get_delete_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "secrets.db")
            store = SecretStore(db_path=db_path, db_key="test-key")

            original_tz = os.environ.get("GODZILLA_LOCAL_TZ")
            os.environ["GODZILLA_LOCAL_TZ"] = "UTC"
            try:
                store.set_secret("plaid_access_token", "token123")
                self.assertEqual(store.get_secret("plaid_access_token"), "token123")

                conn = sqlcipher.connect(db_path)
                conn.execute("PRAGMA key = 'test-key';")
                row = conn.execute(
                    "SELECT updated_at_tz, updated_at_offset_minutes "
                    "FROM secrets WHERE key = ?",
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
