"""Plaid client tests.

REQ: FUNC-ACCT-001, FUNC-ACCT-002, SEC-CRY-002
"""

import io
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib import error as urllib_error

from godzilla_core.integrations.plaid_client import (
    PlaidApiError,
    PlaidClient,
    PlaidConfig,
    PlaidConfigError,
    link_sandbox_item,
    store_access_token,
)
from godzilla_core.security.secrets import SecretStore

_URLOPEN = "godzilla_core.integrations.plaid_client.request.urlopen"


class PlaidConfigTests(unittest.TestCase):
    """Tests for Plaid environment configuration loading.

    REQ: FUNC-ACCT-001
    """

    def test_from_env_requires_credentials(self) -> None:
        """Ensure missing credentials raise a configuration error.

        REQ: FUNC-ACCT-001
        """
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
        """Verify sandbox defaults are applied when optional values are unset.

        REQ: FUNC-ACCT-001
        """
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

    def test_from_env_invalid_env_raises(self) -> None:
        """PLAID_ENV set to an unsupported value raises PlaidConfigError.

        REQ: FUNC-ACCT-001
        """
        saved_env = os.environ.get("PLAID_ENV")
        os.environ["PLAID_CLIENT_ID"] = "cid"
        os.environ["PLAID_SECRET"] = "sec"
        os.environ["PLAID_ENV"] = "not_a_real_env"
        try:
            with self.assertRaises(PlaidConfigError):
                PlaidConfig.from_env()
        finally:
            if saved_env is None:
                os.environ.pop("PLAID_ENV", None)
            else:
                os.environ["PLAID_ENV"] = saved_env

    def test_from_env_all_envs(self) -> None:
        """Verify all supported PLAID_ENV values resolve to correct base URLs.

        REQ: FUNC-ACCT-001
        """
        expected_urls = {
            "sandbox": "https://sandbox.plaid.com",
            "development": "https://development.plaid.com",
            "production": "https://production.plaid.com",
        }
        saved_env = os.environ.get("PLAID_ENV")
        os.environ["PLAID_CLIENT_ID"] = "cid"
        os.environ["PLAID_SECRET"] = "sec"
        try:
            for env_name, expected_url in expected_urls.items():
                os.environ["PLAID_ENV"] = env_name
                config = PlaidConfig.from_env()
                self.assertEqual(config.base_url, expected_url)
        finally:
            if saved_env is None:
                os.environ.pop("PLAID_ENV", None)
            else:
                os.environ["PLAID_ENV"] = saved_env


class PlaidClientPostTests(unittest.TestCase):
    """Tests for PlaidClient HTTP request behavior using mocked responses.

    REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-SYNC-001, FUNC-ACCT-003
    """

    def _make_config(self) -> PlaidConfig:
        """Return a minimal sandbox PlaidConfig for testing.

        REQ: FUNC-ACCT-001
        """
        return PlaidConfig(
            client_id="cid",
            secret="sec",
            env="sandbox",
            base_url="https://sandbox.plaid.com",
            sandbox_institution_id="ins_109508",
        )

    def _mock_response(self, body: dict) -> MagicMock:
        """Build a mock HTTP response context manager.

        REQ: FUNC-ACCT-001
        """
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(body).encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_post_success(self) -> None:
        """_post returns parsed JSON on a successful HTTP response.

        REQ: FUNC-ACCT-001
        """
        client = PlaidClient(self._make_config())
        mock_resp = self._mock_response({"result": "ok"})
        with patch(_URLOPEN, return_value=mock_resp):
            result = client._post("/some/path", {"key": "val"})
        self.assertEqual(result, {"result": "ok"})

    def test_post_http_error_raises_plaid_api_error(self) -> None:
        """_post raises PlaidApiError with status code on HTTP errors.

        REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-SYNC-001, FUNC-ACCT-003
        """
        client = PlaidClient(self._make_config())
        http_err = urllib_error.HTTPError(
            url="https://sandbox.plaid.com/some/path",
            code=400,
            msg="Bad Request",
            hdrs=MagicMock(),  # type: ignore[arg-type]
            fp=io.BytesIO(b'{"error":"bad"}'),
        )
        with patch(_URLOPEN, side_effect=http_err):
            with self.assertRaises(PlaidApiError) as ctx:
                client._post("/some/path", {})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_post_url_error_raises_plaid_api_error(self) -> None:
        """_post raises PlaidApiError on network-level URLError.

        REQ: FUNC-ACCT-001
        """
        client = PlaidClient(self._make_config())
        url_err = urllib_error.URLError("connection refused")
        with patch(_URLOPEN, side_effect=url_err):
            with self.assertRaises(PlaidApiError):
                client._post("/some/path", {})

    def test_create_sandbox_public_token(self) -> None:
        """create_sandbox_public_token returns the public_token from the response.

        REQ: FUNC-ACCT-001
        """
        client = PlaidClient(self._make_config())
        mock_resp = self._mock_response({"public_token": "pt-abc"})
        with patch(_URLOPEN, return_value=mock_resp):
            token = client.create_sandbox_public_token("ins_109508", ["transactions"])
        self.assertEqual(token, "pt-abc")

    def test_create_sandbox_public_token_missing_raises(self) -> None:
        """create_sandbox_public_token raises PlaidApiError if public_token absent.

        REQ: FUNC-ACCT-001
        """
        client = PlaidClient(self._make_config())
        mock_resp = self._mock_response({})
        with patch(_URLOPEN, return_value=mock_resp):
            with self.assertRaises(PlaidApiError):
                client.create_sandbox_public_token("ins_109508", ["transactions"])

    def test_exchange_public_token(self) -> None:
        """exchange_public_token returns access_token and item_id.

        REQ: FUNC-ACCT-002
        """
        client = PlaidClient(self._make_config())
        mock_resp = self._mock_response({"access_token": "at-xyz", "item_id": "item-1"})
        with patch(_URLOPEN, return_value=mock_resp):
            result = client.exchange_public_token("pt-abc")
        self.assertEqual(result["access_token"], "at-xyz")
        self.assertEqual(result["item_id"], "item-1")

    def test_exchange_public_token_missing_raises(self) -> None:
        """exchange_public_token raises PlaidApiError when response is incomplete.

        REQ: FUNC-ACCT-002
        """
        client = PlaidClient(self._make_config())
        mock_resp = self._mock_response({"access_token": "at-xyz"})  # missing item_id
        with patch(_URLOPEN, return_value=mock_resp):
            with self.assertRaises(PlaidApiError):
                client.exchange_public_token("pt-abc")

    def test_transactions_sync_without_cursor(self) -> None:
        """transactions_sync omits cursor key from payload when not provided.

        REQ: FUNC-SYNC-001
        """
        client = PlaidClient(self._make_config())
        sync_body = {
            "added": [],
            "modified": [],
            "removed": [],
            "has_more": False,
            "next_cursor": "c1",
        }
        mock_resp = self._mock_response(sync_body)
        captured: dict = {}

        def fake_urlopen(req, timeout):
            captured["body"] = json.loads(req.data.decode())
            return mock_resp

        with patch(_URLOPEN, side_effect=fake_urlopen):
            result = client.transactions_sync("at-xyz")

        self.assertNotIn("cursor", captured["body"])
        self.assertEqual(result["next_cursor"], "c1")

    def test_transactions_sync_with_cursor(self) -> None:
        """transactions_sync includes cursor in the payload when provided.

        REQ: FUNC-SYNC-001
        """
        client = PlaidClient(self._make_config())
        mock_resp = self._mock_response({"added": [], "has_more": False, "next_cursor": "c2"})
        captured: dict = {}

        def fake_urlopen(req, timeout):
            captured["body"] = json.loads(req.data.decode())
            return mock_resp

        with patch(_URLOPEN, side_effect=fake_urlopen):
            client.transactions_sync("at-xyz", cursor="c1")

        self.assertEqual(captured["body"]["cursor"], "c1")

    def test_accounts_balance_get(self) -> None:
        """accounts_balance_get returns the accounts list from the response.

        REQ: FUNC-ACCT-003
        """
        client = PlaidClient(self._make_config())
        accounts_payload = {"accounts": [{"account_id": "acct-1", "balances": {"current": 100.0}}]}
        mock_resp = self._mock_response(accounts_payload)
        with patch(_URLOPEN, return_value=mock_resp):
            result = client.accounts_balance_get("at-xyz")
        self.assertEqual(result["accounts"][0]["account_id"], "acct-1")


class PlaidSandboxFlowTests(unittest.TestCase):
    """Tests for sandbox linking and token persistence helpers.

    REQ: FUNC-ACCT-001, FUNC-ACCT-002, SEC-CRY-002
    """

    @unittest.skip("SKIP: TODO(TASK-PLAID-SANDBOX) requires sandbox credentials and network")
    def test_link_sandbox_item(self) -> None:
        """Track skipped end-to-end sandbox link coverage.

        REQ: FUNC-ACCT-001, FUNC-ACCT-002
        """
        config = PlaidConfig.from_env()
        client = PlaidClient(config)
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = SecretStore(db_path=os.path.join(tmp_dir, "secrets.db"), db_key="test")
            result = link_sandbox_item(client, store)
            self.assertIn("access_token", result)
            self.assertIn("item_id", result)

    def test_store_access_token_roundtrip(self) -> None:
        """Ensure access tokens are encrypted and retrievable by derived key.

        REQ: FUNC-ACCT-002, SEC-CRY-002
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = SecretStore(db_path=os.path.join(tmp_dir, "secrets.db"), db_key="test")
            key = store_access_token(store, "item123", "token123")
            self.assertEqual(key, "plaid_access_token:item123")
            self.assertEqual(store.get_secret(key), "token123")

    def test_link_sandbox_item_stores_token(self) -> None:
        """link_sandbox_item exchanges a public token and stores the access token.

        REQ: FUNC-ACCT-001, FUNC-ACCT-002, SEC-CRY-002
        """
        config = PlaidConfig(
            client_id="cid",
            secret="sec",
            env="sandbox",
            base_url="https://sandbox.plaid.com",
            sandbox_institution_id="ins_109508",
        )
        client = PlaidClient(config)
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = SecretStore(db_path=os.path.join(tmp_dir, "secrets.db"), db_key="test")
            with (
                patch.object(client, "create_sandbox_public_token", return_value="pt-test"),
                patch.object(
                    client,
                    "exchange_public_token",
                    return_value={"access_token": "at-test", "item_id": "item-test"},
                ),
            ):
                result = link_sandbox_item(client, store)

            self.assertEqual(result["item_id"], "item-test")
            self.assertEqual(store.get_secret("plaid_access_token:item-test"), "at-test")
