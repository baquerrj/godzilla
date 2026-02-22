"""CLI script tests for link_sandbox_item and sync_plaid_item.

REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-003, FUNC-SYNC-001, SEC-CRY-002
"""

import json
import os
import sys
import tempfile
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

from godzilla_core.integrations.plaid_client import PlaidConfigError
from godzilla_core.integrations.plaid_sync import SyncResult
from godzilla_core.scripts.link_sandbox_item import _parse_products
from godzilla_core.scripts.link_sandbox_item import main as link_main
from godzilla_core.scripts.sync_plaid_item import main as sync_main


class ParseProductsTests(unittest.TestCase):
    """Tests for the _parse_products helper in link_sandbox_item.

    REQ: FUNC-ACCT-001
    """

    def test_none_returns_none(self) -> None:
        """_parse_products(None) returns None.

        REQ: FUNC-ACCT-001
        """
        self.assertIsNone(_parse_products(None))

    def test_empty_string_returns_none(self) -> None:
        """_parse_products('') returns None.

        REQ: FUNC-ACCT-001
        """
        self.assertIsNone(_parse_products(""))

    def test_single_product(self) -> None:
        """_parse_products returns a single-element list for one product.

        REQ: FUNC-ACCT-001
        """
        self.assertEqual(_parse_products("transactions"), ["transactions"])

    def test_multiple_products(self) -> None:
        """_parse_products splits on commas and strips whitespace.

        REQ: FUNC-ACCT-001
        """
        result = _parse_products("transactions, identity , balance")
        self.assertEqual(result, ["transactions", "identity", "balance"])

    def test_strips_blank_entries(self) -> None:
        """_parse_products filters out blank entries from the list.

        REQ: FUNC-ACCT-001
        """
        result = _parse_products("transactions,,identity")
        self.assertEqual(result, ["transactions", "identity"])


class LinkSandboxItemMainTests(unittest.TestCase):
    """Tests for the link_sandbox_item CLI entry point.

    REQ: FUNC-ACCT-001, FUNC-ACCT-002, SEC-CRY-002
    """

    def test_main_prints_json_result(self) -> None:
        """main() prints a JSON object containing item_id and secret_key.

        REQ: FUNC-ACCT-001, FUNC-ACCT-002, SEC-CRY-002
        """
        mock_config = MagicMock()
        mock_config.env = "sandbox"
        mock_config.sandbox_institution_id = "ins_109508"

        mock_link_result = {"access_token": "at-test", "item_id": "item-test"}

        with tempfile.TemporaryDirectory() as tmp_dir:
            secrets_path = os.path.join(tmp_dir, "secrets.db")
            saved = {
                "GODZILLA_SECRETS_PATH": os.environ.get("GODZILLA_SECRETS_PATH"),
                "GODZILLA_SECRETS_KEY": os.environ.get("GODZILLA_SECRETS_KEY"),
            }
            os.environ["GODZILLA_SECRETS_PATH"] = secrets_path
            os.environ["GODZILLA_SECRETS_KEY"] = "test-key"
            try:
                with (
                    patch(
                        "godzilla_core.scripts.link_sandbox_item.PlaidConfig.from_env",
                        return_value=mock_config,
                    ),
                    patch("godzilla_core.scripts.link_sandbox_item.PlaidClient") as MockClient,
                    patch(
                        "godzilla_core.scripts.link_sandbox_item.link_sandbox_item",
                        return_value=mock_link_result,
                    ),
                    patch.object(sys, "argv", ["link-sandbox-item"]),
                ):
                    MockClient.return_value = MagicMock()
                    captured = StringIO()
                    with patch("sys.stdout", captured):
                        exit_code = link_main()

                output = json.loads(captured.getvalue())
                self.assertEqual(exit_code, 0)
                self.assertEqual(output["item_id"], "item-test")
                self.assertEqual(output["secret_key"], "plaid_access_token:item-test")
                self.assertEqual(output["env"], "sandbox")
            finally:
                for k, v in saved.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v

    def test_main_propagates_plaid_config_error(self) -> None:
        """main() surfaces PlaidConfigError when credentials are missing.

        REQ: FUNC-ACCT-001
        """
        with (
            patch(
                "godzilla_core.scripts.link_sandbox_item.PlaidConfig.from_env",
                side_effect=PlaidConfigError("missing creds"),
            ),
            patch.object(sys, "argv", ["link-sandbox-item"]),
        ):
            with self.assertRaises(PlaidConfigError):
                link_main()


class SyncPlaidItemMainTests(unittest.TestCase):
    """Tests for the sync_plaid_item CLI entry point.

    REQ: FUNC-ACCT-003, FUNC-SYNC-001, FUNC-SYNC-002, FUNC-SYNC-003, FUNC-REP-006
    """

    def test_main_prints_json_result(self) -> None:
        """main() prints a JSON sync summary for the given item.

        REQ: FUNC-ACCT-003, FUNC-SYNC-001, FUNC-REP-006
        """
        mock_result = SyncResult(
            item_id="item-1",
            added=3,
            modified=1,
            removed=0,
            balance_accounts=2,
            cursor="cursor-end",
        )

        with (
            patch(
                "godzilla_core.scripts.sync_plaid_item.sync_item_transactions_and_balances",
                return_value=mock_result,
            ),
            patch.object(sys, "argv", ["sync-plaid-item", "--item-id", "item-1"]),
        ):
            captured = StringIO()
            with patch("sys.stdout", captured):
                exit_code = sync_main()

        output = json.loads(captured.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(output["item_id"], "item-1")
        self.assertEqual(output["added"], 3)
        self.assertEqual(output["modified"], 1)
        self.assertEqual(output["removed"], 0)
        self.assertEqual(output["balance_accounts"], 2)
        self.assertEqual(output["cursor"], "cursor-end")

    def test_main_requires_item_id(self) -> None:
        """main() exits with an error when --item-id is not provided.

        REQ: FUNC-SYNC-001
        """
        with patch.object(sys, "argv", ["sync-plaid-item"]):
            with self.assertRaises(SystemExit) as ctx:
                sync_main()
        self.assertNotEqual(ctx.exception.code, 0)
