"""Plaid client tests.

REQ: FUNC-ACCT-001, FUNC-ACCT-002, SEC-CRY-002
"""

import os
import tempfile
import unittest

from godzilla_core.integrations.plaid_client import (
    PlaidClient,
    PlaidConfig,
    PlaidConfigError,
    link_sandbox_item,
    store_access_token,
)
from godzilla_core.security.secrets import SecretStore


class PlaidConfigTests(unittest.TestCase):
    def test_from_env_requires_credentials(self) -> None:
        original_client_id = os.environ.pop("PLAID_CLIENT_ID", None)
        original_secret = os.environ.pop("PLAID_SECRET", None)
        try:
            with self.assertRaises(PlaidConfigError):
                PlaidConfig.from_env()
        finally:
            if original_client_id is not None:
                os.environ["PLAID_CLIENT_ID"] = original_client_id
            if original_secret is not None:
                os.environ["PLAID_SECRET"] = original_secret

    def test_from_env_defaults(self) -> None:
        original = {
            "PLAID_CLIENT_ID": os.environ.get("PLAID_CLIENT_ID"),
            "PLAID_SECRET": os.environ.get("PLAID_SECRET"),
            "PLAID_ENV": os.environ.get("PLAID_ENV"),
            "PLAID_SANDBOX_INSTITUTION_ID": os.environ.get("PLAID_SANDBOX_INSTITUTION_ID"),
        }
        os.environ["PLAID_CLIENT_ID"] = "cid"
        os.environ["PLAID_SECRET"] = "sec"
        os.environ.pop("PLAID_ENV", None)
        os.environ.pop("PLAID_SANDBOX_INSTITUTION_ID", None)
        try:
            config = PlaidConfig.from_env()
            self.assertEqual(config.env, "sandbox")
            self.assertEqual(config.base_url, "https://sandbox.plaid.com")
            self.assertEqual(config.sandbox_institution_id, "ins_109508")
        finally:
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


class PlaidSandboxFlowTests(unittest.TestCase):
    @unittest.skip("SKIP: TODO(TASK-PLAID-SANDBOX) requires sandbox credentials and network")
    def test_link_sandbox_item(self) -> None:
        config = PlaidConfig.from_env()
        client = PlaidClient(config)
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = SecretStore(db_path=os.path.join(tmp_dir, "secrets.db"), db_key="test")
            result = link_sandbox_item(client, store)
            self.assertIn("access_token", result)
            self.assertIn("item_id", result)

    def test_store_access_token_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = SecretStore(db_path=os.path.join(tmp_dir, "secrets.db"), db_key="test")
            key = store_access_token(store, "item123", "token123")
            self.assertEqual(key, "plaid_access_token:item123")
            self.assertEqual(store.get_secret(key), "token123")

