"""Plaid sync ingestion tests.

REQ: FUNC-ACCT-003, FUNC-REP-006, FUNC-SYNC-001, FUNC-SYNC-002, FUNC-SYNC-003,
REQ: FUNC-CAT-003, FUNC-SYNC-004, FUNC-SYNC-005, FUNC-SYNC-006, FUNC-ACCT-008
"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlcipher3 import dbapi2 as sqlcipher

from godzilla_core.db.migrations import run_migrations
from godzilla_core.integrations.plaid_client import PlaidConfig
from godzilla_core.integrations.plaid_sync import (
    SyncError,
    _apply_removed,
    _apply_transaction,
    _detect_and_queue_conflict,
    _fallback_transaction_id,
    _find_account_id,
    _get_plaid_institution_id_for_item,
    _get_sync_cursor,
    _insert_balance_snapshot,
    _resolve_category_id,
    _retention_enabled,
    _update_sync_state,
    _upsert_account,
    _upsert_institution,
    _upsert_item,
    sync_item_transactions_and_balances,
)
from godzilla_core.security.secrets import SecretStore
from godzilla_core.util.time import local_date


class PlaidSyncIngestionTests(unittest.TestCase):
    """Component tests for Plaid sync ingestion behavior.

    REQ: FUNC-ACCT-003, FUNC-REP-006, FUNC-SYNC-001, FUNC-SYNC-002, FUNC-SYNC-003
    """

    def setUp(self) -> None:
        """Create an encrypted test database seeded with one linked account.

        REQ: FUNC-SYNC-001
        """
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test.db")
        self.db_key = "test-key"
        run_migrations(db_path=self.db_path, db_key=self.db_key)

        self.conn = sqlcipher.connect(self.db_path)
        self.conn.execute("PRAGMA key = 'test-key';")
        self.conn.execute("PRAGMA foreign_keys = ON;")

        self.account_id = "acc-1"
        self.conn.execute(
            "INSERT INTO institution ("
            "id, name, plaid_institution_id, created_at_utc, created_at_tz, "
            "created_at_offset_minutes"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            ("inst-1", "inst-1", "inst-1", "2026-01-01T00:00:00", "UTC", 0),
        )
        self.conn.execute(
            "INSERT INTO plaid_item ("
            "id, provider_item_id, institution_id, access_token_ref, status, "
            "last_sync_at_utc, last_sync_at_tz, last_sync_at_offset_minutes, "
            "created_at_utc, created_at_tz, created_at_offset_minutes"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "item-1",
                "item-1",
                "inst-1",
                "token-ref",
                "linked",
                None,
                None,
                None,
                "2026-01-01T00:00:00",
                "UTC",
                0,
            ),
        )
        self.conn.execute(
            "INSERT INTO account ("
            "id, item_id, provider_account_id, name, type, subtype, mask, balance, currency, "
            "owner_names, created_at_utc, created_at_tz, created_at_offset_minutes"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                self.account_id,
                "item-1",
                "acct-1",
                "Checking",
                "depository",
                "checking",
                "1111",
                100.0,
                "USD",
                None,
                "2026-01-01T00:00:00",
                "UTC",
                0,
            ),
        )
        self.conn.commit()

    def tearDown(self) -> None:
        """Release database resources allocated by each test.

        REQ: FUNC-SYNC-001
        """
        self.conn.close()
        self.tmp_dir.cleanup()

    # ── existing tests ──────────────────────────────────────────────────────

    def test_pending_to_posted_updates_record(self) -> None:
        """Verify pending transactions are reconciled to posted transactions.

        REQ: FUNC-SYNC-002
        """
        pending_txn = {
            "transaction_id": "pending-1",
            "pending": True,
            "pending_transaction_id": None,
            "account_id": "acct-1",
            "date": "2026-01-02",
            "amount": 10.0,
            "iso_currency_code": "USD",
            "name": "Pending purchase",
        }
        _apply_transaction(self.conn, self.account_id, pending_txn, retention_enabled=False)

        posted_txn = {
            "transaction_id": "posted-1",
            "pending": False,
            "pending_transaction_id": "pending-1",
            "account_id": "acct-1",
            "date": "2026-01-03",
            "amount": 10.0,
            "iso_currency_code": "USD",
            "name": "Posted purchase",
        }
        _apply_transaction(self.conn, self.account_id, posted_txn, retention_enabled=False)

        rows = self.conn.execute(
            "SELECT provider_transaction_id, status FROM transaction_record"
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "posted-1")
        self.assertEqual(rows[0][1], "posted")

    def test_idempotent_ingestion_does_not_duplicate(self) -> None:
        """Verify repeated sync payloads update existing rows instead of duplicating.

        REQ: FUNC-SYNC-002
        """
        txn = {
            "transaction_id": "tx-1",
            "pending": False,
            "pending_transaction_id": None,
            "account_id": "acct-1",
            "date": "2026-01-02",
            "amount": 10.0,
            "iso_currency_code": "USD",
            "name": "Coffee",
        }
        _apply_transaction(self.conn, self.account_id, txn, retention_enabled=False)

        txn_update = dict(txn)
        txn_update["amount"] = 11.0
        _apply_transaction(self.conn, self.account_id, txn_update, retention_enabled=False)

        rows = self.conn.execute(
            "SELECT provider_transaction_id, amount FROM transaction_record"
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "tx-1")
        self.assertEqual(rows[0][1], 11.0)

    def test_balance_snapshot_upserts_per_day(self) -> None:
        """Verify balance snapshots upsert by account and local date.

        REQ: FUNC-REP-006
        """
        _insert_balance_snapshot(self.conn, self.account_id, 100.0)
        _insert_balance_snapshot(self.conn, self.account_id, 150.0)

        snapshot_date = local_date()
        rows = self.conn.execute(
            "SELECT balance FROM balance_snapshot WHERE account_id = ? AND date = ?",
            (self.account_id, snapshot_date),
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], 150.0)

    def test_account_metadata_upsert(self) -> None:
        """Verify account metadata is inserted with provider details.

        REQ: FUNC-ACCT-003
        """
        payload = {
            "account_id": "acct-2",
            "name": "Savings",
            "official_name": None,
            "type": "depository",
            "subtype": "savings",
            "mask": "2222",
            "balances": {"current": 250.0, "iso_currency_code": "USD"},
            "owners": [{"names": ["Alex Example"]}],
        }
        account_id = _upsert_account(self.conn, "item-1", payload)
        row = self.conn.execute(
            "SELECT provider_account_id, name, type, subtype, mask, balance, currency, owner_names "
            "FROM account WHERE id = ?",
            (account_id,),
        ).fetchone()
        self.assertEqual(row[0], "acct-2")
        self.assertEqual(row[1], "Savings")
        self.assertEqual(row[2], "depository")
        self.assertEqual(row[3], "savings")
        self.assertEqual(row[4], "2222")
        self.assertEqual(row[5], 250.0)
        self.assertEqual(row[6], "USD")
        self.assertEqual(row[7], json.dumps(payload["owners"]))

    def test_cursor_persistence_roundtrip(self) -> None:
        """Verify sync cursor persistence for incremental sync resumes.

        REQ: FUNC-SYNC-001
        """
        _update_sync_state(self.conn, "item-1", "cursor-1", "success")
        cursor = _get_sync_cursor(self.conn, "item-1")
        self.assertEqual(cursor, "cursor-1")

    # ── new tests ───────────────────────────────────────────────────────────

    def test_fallback_transaction_id_is_deterministic(self) -> None:
        """_fallback_transaction_id produces the same ID for identical inputs.

        REQ: FUNC-SYNC-002
        """
        payload = {"date": "2026-01-02", "amount": 15.0, "name": "Grocery", "merchant_name": None}
        id1 = _fallback_transaction_id("acc-1", payload)
        id2 = _fallback_transaction_id("acc-1", payload)
        self.assertEqual(id1, id2)

    def test_fallback_transaction_id_differs_by_account(self) -> None:
        """_fallback_transaction_id produces different IDs for different accounts.

        REQ: FUNC-SYNC-002
        """
        payload = {"date": "2026-01-02", "amount": 15.0, "name": "Grocery"}
        id1 = _fallback_transaction_id("acc-1", payload)
        id2 = _fallback_transaction_id("acc-2", payload)
        self.assertNotEqual(id1, id2)

    def test_apply_removed_deletes_transaction(self) -> None:
        """_apply_removed deletes the matching transaction_record rows.

        REQ: FUNC-SYNC-001
        """
        txn = {
            "transaction_id": "tx-del",
            "pending": False,
            "pending_transaction_id": None,
            "date": "2026-01-02",
            "amount": 5.0,
            "iso_currency_code": "USD",
            "name": "Delete me",
        }
        _apply_transaction(self.conn, self.account_id, txn, retention_enabled=False)
        count_before = self.conn.execute("SELECT COUNT(*) FROM transaction_record").fetchone()[0]
        self.assertEqual(count_before, 1)

        removed_count = _apply_removed(self.conn, [{"transaction_id": "tx-del"}])
        self.assertEqual(removed_count, 1)
        count_after = self.conn.execute("SELECT COUNT(*) FROM transaction_record").fetchone()[0]
        self.assertEqual(count_after, 0)

    def test_apply_removed_skips_missing_id(self) -> None:
        """_apply_removed with no transaction_id in payload is a no-op.

        REQ: FUNC-SYNC-001
        """
        removed = _apply_removed(self.conn, [{}])
        self.assertEqual(removed, 0)

    def test_insert_balance_snapshot_skips_none(self) -> None:
        """_insert_balance_snapshot does not write a row when balance is None.

        REQ: FUNC-REP-006
        """
        _insert_balance_snapshot(self.conn, self.account_id, None)
        count = self.conn.execute("SELECT COUNT(*) FROM balance_snapshot").fetchone()[0]
        self.assertEqual(count, 0)

    def test_upsert_institution_creates_and_is_idempotent(self) -> None:
        """_upsert_institution returns the same ID on repeated calls.

        REQ: FUNC-ACCT-003, FUNC-SYNC-001
        """
        id1 = _upsert_institution(self.conn, "ins_new")
        id2 = _upsert_institution(self.conn, "ins_new")
        self.assertEqual(id1, id2)
        self.assertIsNotNone(id1)

    def test_upsert_item_creates_then_updates(self) -> None:
        """_upsert_item returns the same internal ID on update calls.

        REQ: FUNC-SYNC-001, FUNC-SYNC-002
        """
        item_id = _upsert_item(self.conn, "inst-1", "provider-item-new", "tok-ref", "linked")
        item_id_again = _upsert_item(
            self.conn, "inst-1", "provider-item-new", "tok-ref-2", "linked"
        )
        self.assertEqual(item_id, item_id_again)

        row = self.conn.execute(
            "SELECT access_token_ref FROM plaid_item WHERE id = ?", (item_id,)
        ).fetchone()
        self.assertEqual(row[0], "tok-ref-2")

    def test_retention_enabled_defaults_true_when_no_policy(self) -> None:
        """_retention_enabled returns True when no retention_policy row exists.

        REQ: FUNC-SYNC-003
        """
        self.assertTrue(_retention_enabled(self.conn))

    def test_retention_enabled_reads_policy(self) -> None:
        """_retention_enabled reflects the retain_raw_payloads column value.

        REQ: FUNC-SYNC-003
        """
        self.conn.execute(
            "INSERT INTO retention_policy ("
            "id, retain_raw_payloads, retain_logs_days, "
            "created_at_utc, created_at_tz, created_at_offset_minutes, "
            "updated_at_utc, updated_at_tz, updated_at_offset_minutes"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid4()),
                0,
                90,
                "2026-01-01T00:00:00",
                "UTC",
                0,
                "2026-01-01T00:00:00",
                "UTC",
                0,
            ),
        )
        self.conn.commit()
        self.assertFalse(_retention_enabled(self.conn))

    def test_retention_enabled_prefers_most_recent_policy_row(self) -> None:
        """_retention_enabled uses the most recently updated policy row.

        REQ: FUNC-SYNC-003
        """
        self.conn.execute(
            "INSERT INTO retention_policy ("
            "id, retain_raw_payloads, retain_logs_days, "
            "created_at_utc, created_at_tz, created_at_offset_minutes, "
            "updated_at_utc, updated_at_tz, updated_at_offset_minutes"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "retain-old",
                0,
                90,
                "2026-01-01T00:00:00",
                "UTC",
                0,
                "2026-01-01T00:00:00",
                "UTC",
                0,
            ),
        )
        self.conn.execute(
            "INSERT INTO retention_policy ("
            "id, retain_raw_payloads, retain_logs_days, "
            "created_at_utc, created_at_tz, created_at_offset_minutes, "
            "updated_at_utc, updated_at_tz, updated_at_offset_minutes"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "retain-new",
                1,
                90,
                "2026-02-01T00:00:00",
                "UTC",
                0,
                "2026-02-01T00:00:00",
                "UTC",
                0,
            ),
        )
        self.conn.commit()
        self.assertTrue(_retention_enabled(self.conn))

    def test_apply_transaction_stores_raw_payload_when_enabled(self) -> None:
        """_apply_transaction persists provider_raw when retention is enabled.

        REQ: FUNC-SYNC-003
        """
        txn = {
            "transaction_id": "tx-retain",
            "pending": False,
            "pending_transaction_id": None,
            "date": "2026-01-05",
            "amount": 20.0,
            "iso_currency_code": "USD",
            "name": "Retained",
        }
        _apply_transaction(self.conn, self.account_id, txn, retention_enabled=True)
        count = self.conn.execute("SELECT COUNT(*) FROM provider_raw").fetchone()[0]
        self.assertEqual(count, 1)

    def test_apply_transaction_no_raw_payload_when_disabled(self) -> None:
        """_apply_transaction skips provider_raw when retention is disabled.

        REQ: FUNC-SYNC-003
        """
        txn = {
            "transaction_id": "tx-no-retain",
            "pending": False,
            "pending_transaction_id": None,
            "date": "2026-01-06",
            "amount": 25.0,
            "iso_currency_code": "USD",
            "name": "Not retained",
        }
        _apply_transaction(self.conn, self.account_id, txn, retention_enabled=False)
        count = self.conn.execute("SELECT COUNT(*) FROM provider_raw").fetchone()[0]
        self.assertEqual(count, 0)

    def test_apply_transaction_fallback_id_no_provider_id(self) -> None:
        """_apply_transaction uses fallback heuristic ID when no provider ID present.

        REQ: FUNC-SYNC-002
        """
        txn = {
            "date": "2026-01-07",
            "amount": 9.99,
            "iso_currency_code": "USD",
            "name": "Anonymous",
        }
        _apply_transaction(self.conn, self.account_id, txn, retention_enabled=False)
        count = self.conn.execute("SELECT COUNT(*) FROM transaction_record").fetchone()[0]
        self.assertEqual(count, 1)
        row = self.conn.execute("SELECT provider_transaction_id FROM transaction_record").fetchone()
        self.assertIsNone(row[0])

    def test_get_plaid_institution_id_for_item(self) -> None:
        """_get_plaid_institution_id_for_item resolves the institution ID for a known item.

        REQ: FUNC-ACCT-003, FUNC-SYNC-001
        """
        result = _get_plaid_institution_id_for_item(self.conn, "item-1")
        self.assertEqual(result, "inst-1")

    def test_get_plaid_institution_id_for_item_missing(self) -> None:
        """_get_plaid_institution_id_for_item returns None for an unknown item.

        REQ: FUNC-ACCT-003, FUNC-SYNC-001
        """
        result = _get_plaid_institution_id_for_item(self.conn, "no-such-item")
        self.assertIsNone(result)

    def test_sync_cursor_update_is_idempotent(self) -> None:
        """Calling _update_sync_state twice updates the cursor in place.

        REQ: FUNC-SYNC-001
        """
        _update_sync_state(self.conn, "item-1", "cursor-a", "success")
        _update_sync_state(self.conn, "item-1", "cursor-b", "success")
        cursor = _get_sync_cursor(self.conn, "item-1")
        self.assertEqual(cursor, "cursor-b")
        count = self.conn.execute(
            "SELECT COUNT(*) FROM sync_state WHERE item_id = 'item-1'"
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_upsert_account_updates_existing(self) -> None:
        """_upsert_account updates metadata when the same provider_account_id is seen again.

        REQ: FUNC-ACCT-003, FUNC-SYNC-001
        """
        payload = {
            "account_id": "acct-1",
            "name": "Checking Updated",
            "official_name": None,
            "type": "depository",
            "subtype": "checking",
            "mask": "1112",
            "balances": {"current": 200.0, "iso_currency_code": "USD"},
        }
        returned_id = _upsert_account(self.conn, "item-1", payload)
        self.assertEqual(returned_id, self.account_id)
        row = self.conn.execute(
            "SELECT name, balance, mask FROM account WHERE id = ?", (self.account_id,)
        ).fetchone()
        self.assertEqual(row[0], "Checking Updated")
        self.assertEqual(row[1], 200.0)
        self.assertEqual(row[2], "1112")
        count = self.conn.execute("SELECT COUNT(*) FROM account").fetchone()[0]
        self.assertEqual(count, 1)

    def test_pending_to_posted_stores_raw_when_retention_enabled(self) -> None:
        """pending→posted reconciliation writes a provider_raw row when retention is on.

        REQ: FUNC-SYNC-002, FUNC-SYNC-003
        """
        pending_txn = {
            "transaction_id": "pending-2",
            "pending": True,
            "pending_transaction_id": None,
            "date": "2026-01-08",
            "amount": 30.0,
            "iso_currency_code": "USD",
            "name": "Pending coffee",
        }
        _apply_transaction(self.conn, self.account_id, pending_txn, retention_enabled=False)

        posted_txn = {
            "transaction_id": "posted-2",
            "pending": False,
            "pending_transaction_id": "pending-2",
            "date": "2026-01-09",
            "amount": 30.0,
            "iso_currency_code": "USD",
            "name": "Posted coffee",
        }
        _apply_transaction(self.conn, self.account_id, posted_txn, retention_enabled=True)

        raw_count = self.conn.execute("SELECT COUNT(*) FROM provider_raw").fetchone()[0]
        self.assertEqual(raw_count, 1)

    def test_update_existing_transaction_stores_raw_when_retention_enabled(self) -> None:
        """Updating an existing transaction writes a provider_raw row when retention is on.

        REQ: FUNC-SYNC-002, FUNC-SYNC-003
        """
        txn = {
            "transaction_id": "tx-update-retain",
            "pending": False,
            "pending_transaction_id": None,
            "date": "2026-01-10",
            "amount": 50.0,
            "iso_currency_code": "USD",
            "name": "Original",
        }
        _apply_transaction(self.conn, self.account_id, txn, retention_enabled=False)

        txn_updated = dict(txn)
        txn_updated["amount"] = 55.0
        txn_updated["name"] = "Updated"
        _apply_transaction(self.conn, self.account_id, txn_updated, retention_enabled=True)

        raw_count = self.conn.execute("SELECT COUNT(*) FROM provider_raw").fetchone()[0]
        self.assertEqual(raw_count, 1)

    def test_apply_transaction_fallback_stores_raw_when_retention_enabled(self) -> None:
        """Fallback-ID insert writes a provider_raw row when retention is enabled.

        REQ: FUNC-SYNC-002, FUNC-SYNC-003
        """
        txn = {
            "date": "2026-01-11",
            "amount": 7.50,
            "iso_currency_code": "USD",
            "name": "No ID merchant",
        }
        _apply_transaction(self.conn, self.account_id, txn, retention_enabled=True)

        raw_count = self.conn.execute("SELECT COUNT(*) FROM provider_raw").fetchone()[0]
        self.assertEqual(raw_count, 1)

    def test_find_account_id_returns_none_for_falsy_provider_id(self) -> None:
        """_find_account_id returns None when provider_account_id is None or empty.

        REQ: FUNC-ACCT-003, FUNC-SYNC-001
        """
        self.assertIsNone(_find_account_id(self.conn, None))
        self.assertIsNone(_find_account_id(self.conn, ""))


class SyncItemFullFlowTests(unittest.TestCase):
    """Integration tests for sync_item_transactions_and_balances with mocked Plaid.

    REQ: FUNC-ACCT-003, FUNC-SYNC-001, FUNC-SYNC-002, FUNC-SYNC-003, FUNC-REP-006
    """

    def setUp(self) -> None:
        """Create encrypted DBs and set up env vars for a full-flow mock.

        REQ: FUNC-SYNC-001
        """
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test.db")
        self.secrets_path = os.path.join(self.tmp_dir.name, "secrets.db")
        self.db_key = "test-key"

        run_migrations(db_path=self.db_path, db_key=self.db_key)

        store = SecretStore(db_path=self.secrets_path, db_key=self.db_key)
        store.set_secret("plaid_access_token:provider-item-1", "at-mock")

        self._env_patch = {
            "GODZILLA_DB_PATH": self.db_path,
            "GODZILLA_DB_KEY": self.db_key,
            "GODZILLA_SECRETS_PATH": self.secrets_path,
            "GODZILLA_SECRETS_KEY": self.db_key,
            "PLAID_CLIENT_ID": "cid",
            "PLAID_SECRET": "sec",
            "PLAID_ENV": "sandbox",
        }
        self._saved_env = {k: os.environ.get(k) for k in self._env_patch}
        os.environ.update(self._env_patch)

    def tearDown(self) -> None:
        """Restore env vars and clean up temp files.

        REQ: FUNC-SYNC-001
        """
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp_dir.cleanup()

    def test_sync_persists_account_transaction_and_balance(self) -> None:
        """sync_item_transactions_and_balances persists accounts, txns, and balances.

        REQ: FUNC-ACCT-003, FUNC-SYNC-001, FUNC-SYNC-002, FUNC-REP-006
        """
        mock_balance_response = {
            "accounts": [
                {
                    "account_id": "acct-mock-1",
                    "name": "Mock Checking",
                    "official_name": None,
                    "type": "depository",
                    "subtype": "checking",
                    "mask": "0000",
                    "balances": {"current": 500.0, "iso_currency_code": "USD"},
                }
            ]
        }
        mock_sync_response = {
            "added": [
                {
                    "transaction_id": "txn-mock-1",
                    "account_id": "acct-mock-1",
                    "pending": False,
                    "pending_transaction_id": None,
                    "date": "2026-01-10",
                    "amount": 42.0,
                    "iso_currency_code": "USD",
                    "name": "Mock Merchant",
                }
            ],
            "modified": [],
            "removed": [],
            "has_more": False,
            "next_cursor": "cursor-end",
        }

        with (
            patch(
                "godzilla_core.integrations.plaid_sync.PlaidClient.accounts_balance_get",
                return_value=mock_balance_response,
            ),
            patch(
                "godzilla_core.integrations.plaid_sync.PlaidClient.transactions_sync",
                return_value=mock_sync_response,
            ),
        ):
            result = sync_item_transactions_and_balances(
                provider_item_id="provider-item-1",
                plaid_institution_id="ins_109508",
            )

        self.assertEqual(result.item_id, "provider-item-1")
        self.assertEqual(result.added, 1)
        self.assertEqual(result.modified, 0)
        self.assertEqual(result.removed, 0)
        self.assertEqual(result.balance_accounts, 1)
        self.assertEqual(result.cursor, "cursor-end")

        conn = sqlcipher.connect(self.db_path)
        conn.execute(f"PRAGMA key = '{self.db_key}';")
        txn_count = conn.execute("SELECT COUNT(*) FROM transaction_record").fetchone()[0]
        snap_count = conn.execute("SELECT COUNT(*) FROM balance_snapshot").fetchone()[0]
        conn.close()

        self.assertEqual(txn_count, 1)
        self.assertEqual(snap_count, 1)

    def test_sync_raises_on_missing_access_token(self) -> None:
        """sync_item_transactions_and_balances raises SyncError for unknown item.

        REQ: FUNC-SYNC-001
        """
        with self.assertRaises(SyncError):
            sync_item_transactions_and_balances(
                provider_item_id="no-such-item",
                plaid_institution_id="ins_109508",
            )

    def test_sync_raises_for_unlinked_item(self) -> None:
        """sync_item_transactions_and_balances rejects items marked unlinked.

        REQ: FUNC-ACCT-008
        """
        conn = sqlcipher.connect(self.db_path)
        conn.execute(f"PRAGMA key = '{self.db_key}';")
        conn.execute(
            "INSERT INTO institution ("
            "id, name, plaid_institution_id, "
            "created_at_utc, created_at_tz, created_at_offset_minutes"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            ("inst-u1", "inst-u1", "ins_109508", "2026-01-01T00:00:00", "UTC", 0),
        )
        conn.execute(
            "INSERT INTO plaid_item ("
            "id, provider_item_id, institution_id, access_token_ref, status, is_unlinked, "
            "last_sync_at_utc, last_sync_at_tz, last_sync_at_offset_minutes, "
            "created_at_utc, created_at_tz, created_at_offset_minutes"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "item-unlinked",
                "provider-item-unlinked",
                "inst-u1",
                "plaid_access_token:provider-item-unlinked",
                "requires_reauth",
                1,
                None,
                None,
                None,
                "2026-01-01T00:00:00",
                "UTC",
                0,
            ),
        )
        conn.commit()
        conn.close()

        store = SecretStore(db_path=self.secrets_path, db_key=self.db_key)
        store.set_secret("plaid_access_token:provider-item-unlinked", "at-unlinked")

        with self.assertRaisesRegex(SyncError, "unlinked"):
            sync_item_transactions_and_balances(
                provider_item_id="provider-item-unlinked",
                plaid_institution_id="ins_109508",
            )

    def test_sync_raises_when_db_path_missing(self) -> None:
        """sync_item_transactions_and_balances raises SyncError when db_path is unavailable.

        REQ: FUNC-SYNC-001
        """
        saved_path = os.environ.pop("GODZILLA_DB_PATH")
        saved_key = os.environ.pop("GODZILLA_DB_KEY")
        try:
            with self.assertRaises(SyncError):
                sync_item_transactions_and_balances(
                    provider_item_id="provider-item-1",
                    plaid_institution_id="ins_109508",
                    db_path=None,
                    db_key=None,
                )
        finally:
            os.environ["GODZILLA_DB_PATH"] = saved_path
            os.environ["GODZILLA_DB_KEY"] = saved_key

    def test_sync_uses_sandbox_institution_fallback_when_item_not_in_db(self) -> None:
        """sync uses sandbox_institution_id when plaid_institution_id is omitted and not in DB.

        REQ: FUNC-ACCT-003, FUNC-SYNC-001
        """
        mock_balance_response = {"accounts": []}
        mock_sync_response = {
            "added": [],
            "modified": [],
            "removed": [],
            "has_more": False,
            "next_cursor": "cursor-sandbox",
        }
        with (
            patch(
                "godzilla_core.integrations.plaid_sync.PlaidClient.accounts_balance_get",
                return_value=mock_balance_response,
            ),
            patch(
                "godzilla_core.integrations.plaid_sync.PlaidClient.transactions_sync",
                return_value=mock_sync_response,
            ),
        ):
            result = sync_item_transactions_and_balances(
                provider_item_id="provider-item-1",
                plaid_institution_id=None,
            )
        self.assertEqual(result.cursor, "cursor-sandbox")

    def test_sync_raises_when_institution_missing_outside_sandbox(self) -> None:
        """sync_item_transactions_and_balances raises SyncError in non-sandbox without institution.

        REQ: FUNC-ACCT-003, FUNC-SYNC-001
        """
        non_sandbox_config = PlaidConfig(
            client_id="cid",
            secret="sec",
            env="production",
            base_url="https://production.plaid.com",
            sandbox_institution_id="ins_109508",
        )
        with patch(
            "godzilla_core.integrations.plaid_sync.PlaidConfig.from_env",
            return_value=non_sandbox_config,
        ):
            with self.assertRaises(SyncError):
                sync_item_transactions_and_balances(
                    provider_item_id="provider-item-1",
                    plaid_institution_id=None,
                )

    def test_sync_processes_modified_transactions(self) -> None:
        """sync_item_transactions_and_balances applies modified transaction payloads.

        REQ: FUNC-SYNC-001, FUNC-SYNC-002
        """
        mock_balance_response = {
            "accounts": [
                {
                    "account_id": "acct-mod-1",
                    "name": "Mock Savings",
                    "official_name": None,
                    "type": "depository",
                    "subtype": "savings",
                    "mask": "0001",
                    "balances": {"current": 1000.0, "iso_currency_code": "USD"},
                }
            ]
        }
        first_sync = {
            "added": [
                {
                    "transaction_id": "txn-mod-1",
                    "account_id": "acct-mod-1",
                    "pending": False,
                    "pending_transaction_id": None,
                    "date": "2026-01-15",
                    "amount": 100.0,
                    "iso_currency_code": "USD",
                    "name": "Original",
                }
            ],
            "modified": [],
            "removed": [],
            "has_more": False,
            "next_cursor": "cursor-1",
        }
        second_sync = {
            "added": [],
            "modified": [
                {
                    "transaction_id": "txn-mod-1",
                    "account_id": "acct-mod-1",
                    "pending": False,
                    "pending_transaction_id": None,
                    "date": "2026-01-15",
                    "amount": 105.0,
                    "iso_currency_code": "USD",
                    "name": "Modified",
                }
            ],
            "removed": [],
            "has_more": False,
            "next_cursor": "cursor-2",
        }
        with (
            patch(
                "godzilla_core.integrations.plaid_sync.PlaidClient.accounts_balance_get",
                return_value=mock_balance_response,
            ),
            patch(
                "godzilla_core.integrations.plaid_sync.PlaidClient.transactions_sync",
                side_effect=[first_sync, second_sync],
            ),
        ):
            result1 = sync_item_transactions_and_balances(
                provider_item_id="provider-item-1",
                plaid_institution_id="ins_109508",
            )
            result2 = sync_item_transactions_and_balances(
                provider_item_id="provider-item-1",
                plaid_institution_id="ins_109508",
            )

        self.assertEqual(result1.added, 1)
        self.assertEqual(result2.modified, 1)

        conn = sqlcipher.connect(self.db_path)
        conn.execute(f"PRAGMA key = '{self.db_key}';")
        row = conn.execute(
            "SELECT amount, display_name FROM transaction_record "
            "WHERE provider_transaction_id = ?",
            ("txn-mod-1",),
        ).fetchone()
        conn.close()

        self.assertEqual(row[0], 105.0)
        self.assertEqual(row[1], "Modified")


class CategoryMappingTests(unittest.TestCase):
    """Tests for Plaid personal_finance_category mapping on sync.

    REQ: FUNC-CAT-003, FUNC-SYNC-004
    """

    def setUp(self) -> None:
        """Create test database with seeded categories.

        REQ: FUNC-CAT-003
        """
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test.db")
        self.db_key = "test-key"
        run_migrations(db_path=self.db_path, db_key=self.db_key)

        self.conn = sqlcipher.connect(self.db_path)
        self.conn.execute("PRAGMA key = 'test-key';")
        self.conn.execute("PRAGMA foreign_keys = ON;")

        self.conn.execute(
            "INSERT INTO institution (id, name, plaid_institution_id, "
            "created_at_utc, created_at_tz, created_at_offset_minutes) "
            "VALUES ('inst-1', 'Bank', 'ins_1', '2026-01-01T00:00:00', 'UTC', 0)"
        )
        self.conn.execute(
            "INSERT INTO plaid_item (id, provider_item_id, institution_id, access_token_ref, "
            "status, created_at_utc, created_at_tz, created_at_offset_minutes) "
            "VALUES ('item-1', 'pitem-1', 'inst-1', 'ref', 'linked', "
            "'2026-01-01T00:00:00', 'UTC', 0)"
        )
        self.conn.execute(
            "INSERT INTO account (id, item_id, provider_account_id, name, type, currency, "
            "created_at_utc, created_at_tz, created_at_offset_minutes) "
            "VALUES ('acc-1', 'item-1', 'provider-acc-1', 'Checking', 'depository', 'USD', "
            "'2026-01-01T00:00:00', 'UTC', 0)"
        )
        self.conn.commit()

    def tearDown(self) -> None:
        """Close connection and cleanup.

        REQ: FUNC-CAT-003
        """
        self.conn.close()
        self.tmp_dir.cleanup()

    def test_resolve_category_id_uses_detailed_key(self) -> None:
        """_resolve_category_id returns the detailed Plaid category ID when available.

        REQ: FUNC-CAT-003
        """
        pfc = {"primary": "FOOD_AND_DRINK", "detailed": "FOOD_AND_DRINK_COFFEE"}
        result = _resolve_category_id(self.conn, pfc)
        self.assertEqual(result, "food_and_drink_coffee")

    def test_resolve_category_id_falls_back_to_primary(self) -> None:
        """_resolve_category_id falls back to primary when detailed key is not in DB.

        REQ: FUNC-CAT-003
        """
        pfc = {"primary": "FOOD_AND_DRINK", "detailed": "FOOD_AND_DRINK_UNKNOWN_SUBCAT"}
        result = _resolve_category_id(self.conn, pfc)
        self.assertEqual(result, "food_and_drink")

    def test_resolve_category_id_returns_none_for_unknown(self) -> None:
        """_resolve_category_id returns None when neither key maps to a category.

        REQ: FUNC-CAT-003
        """
        pfc = {"primary": "UNKNOWN_PRIMARY", "detailed": "UNKNOWN_DETAILED"}
        result = _resolve_category_id(self.conn, pfc)
        self.assertIsNone(result)

    def test_resolve_category_id_handles_empty_pfc(self) -> None:
        """_resolve_category_id returns None for empty or None payload.

        REQ: FUNC-CAT-003
        """
        self.assertIsNone(_resolve_category_id(self.conn, {}))
        self.assertIsNone(_resolve_category_id(self.conn, None))

    def test_apply_transaction_sets_category_from_pfc(self) -> None:
        """INSERT path maps personal_finance_category to category_id on the record.

        REQ: FUNC-CAT-003, FUNC-SYNC-004
        """
        payload = {
            "transaction_id": "txn-pfc-1",
            "date": "2026-01-05",
            "amount": 4.50,
            "iso_currency_code": "USD",
            "pending": False,
            "name": "Blue Bottle",
            "merchant_name": "Blue Bottle Coffee",
            "personal_finance_category": {
                "primary": "FOOD_AND_DRINK",
                "detailed": "FOOD_AND_DRINK_COFFEE",
            },
        }
        _apply_transaction(self.conn, "acc-1", payload, retention_enabled=False)
        self.conn.commit()

        row = self.conn.execute(
            "SELECT category_id FROM transaction_record WHERE provider_transaction_id = ?",
            ("txn-pfc-1",),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "food_and_drink_coffee")

    def test_apply_transaction_writes_provider_override(self) -> None:
        """INSERT path writes a provider-sourced override for category_id.

        REQ: FUNC-SYNC-004
        """
        payload = {
            "transaction_id": "txn-ov-1",
            "date": "2026-01-05",
            "amount": 9.99,
            "iso_currency_code": "USD",
            "pending": False,
            "name": "Netflix",
            "personal_finance_category": {
                "primary": "ENTERTAINMENT",
                "detailed": "ENTERTAINMENT_TV_AND_MOVIES",
            },
        }
        _apply_transaction(self.conn, "acc-1", payload, retention_enabled=False)
        self.conn.commit()

        row = self.conn.execute(
            "SELECT source, provider_value FROM transaction_override "
            "JOIN transaction_record"
            " ON transaction_record.id = transaction_override.transaction_id "
            "WHERE transaction_record.provider_transaction_id = ?"
            " AND field_name = 'category_id'",
            ("txn-ov-1",),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "provider")
        self.assertEqual(row[1], "entertainment_tv_and_movies")


class ConflictDetectionTests(unittest.TestCase):
    """Tests for conflict detection during sync update path.

    REQ: FUNC-SYNC-005, FUNC-SYNC-006
    """

    def setUp(self) -> None:
        """Create test database with a pre-existing transaction and user override.

        REQ: FUNC-SYNC-005
        """
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test.db")
        self.db_key = "test-key"
        run_migrations(db_path=self.db_path, db_key=self.db_key)

        self.conn = sqlcipher.connect(self.db_path)
        self.conn.execute("PRAGMA key = 'test-key';")
        self.conn.execute("PRAGMA foreign_keys = ON;")

        self.conn.execute(
            "INSERT INTO institution (id, name, plaid_institution_id, "
            "created_at_utc, created_at_tz, created_at_offset_minutes) "
            "VALUES ('inst-1', 'Bank', 'ins_1', '2026-01-01T00:00:00', 'UTC', 0)"
        )
        self.conn.execute(
            "INSERT INTO plaid_item (id, provider_item_id, institution_id, access_token_ref, "
            "status, created_at_utc, created_at_tz, created_at_offset_minutes) "
            "VALUES ('item-1', 'pitem-1', 'inst-1', 'ref', 'linked', "
            "'2026-01-01T00:00:00', 'UTC', 0)"
        )
        self.conn.execute(
            "INSERT INTO account (id, item_id, provider_account_id, name, type, currency, "
            "created_at_utc, created_at_tz, created_at_offset_minutes) "
            "VALUES ('acc-1', 'item-1', 'provider-acc-1', 'Checking', 'depository', 'USD', "
            "'2026-01-01T00:00:00', 'UTC', 0)"
        )
        self.conn.execute(
            "INSERT INTO transaction_record ("
            "id, account_id, provider_transaction_id, date, amount, currency, status, "
            "display_name, is_transfer, is_excluded, "
            "created_at_utc, created_at_tz, created_at_offset_minutes, "
            "updated_at_utc, updated_at_tz, updated_at_offset_minutes"
            ") VALUES ('txn-c1', 'acc-1', 'provider-c1', '2026-01-05', 20.0, 'USD', 'posted', "
            "'User Name', 0, 0, '2026-01-05T10:00:00', 'UTC', 0, '2026-01-05T10:00:00', 'UTC', 0)"
        )
        # Simulate existing user override for display_name
        self.conn.execute(
            "INSERT INTO transaction_override ("
            "id, transaction_id, field_name, source, provider_value, user_value, "
            "updated_at_utc, updated_at_tz, updated_at_offset_minutes"
            ") VALUES ('ov-1', 'txn-c1', 'display_name', 'user', 'Original Name', 'User Name', "
            "'2026-01-05T10:00:00', 'UTC', 0)"
        )
        self.conn.commit()

    def tearDown(self) -> None:
        """Close connection and cleanup.

        REQ: FUNC-SYNC-005
        """
        self.conn.close()
        self.tmp_dir.cleanup()

    def test_detect_conflict_creates_open_conflict_row(self) -> None:
        """Conflict is written when provider value differs from user override.

        REQ: FUNC-SYNC-005, FUNC-SYNC-006
        """
        _detect_and_queue_conflict(self.conn, "txn-c1", "display_name", "Provider Changed Name")
        self.conn.commit()

        row = self.conn.execute(
            "SELECT field_name, local_value, provider_value, status "
            "FROM conflict WHERE entity_id = 'txn-c1'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "display_name")
        self.assertEqual(row[1], "User Name")
        self.assertEqual(row[2], "Provider Changed Name")
        self.assertEqual(row[3], "open")

    def test_detect_conflict_no_conflict_when_values_match(self) -> None:
        """No conflict is written when provider value matches user override value.

        REQ: FUNC-SYNC-005
        """
        _detect_and_queue_conflict(self.conn, "txn-c1", "display_name", "User Name")
        self.conn.commit()

        count = self.conn.execute("SELECT COUNT(*) FROM conflict").fetchone()[0]
        self.assertEqual(count, 0)

    def test_detect_conflict_no_conflict_without_user_override(self) -> None:
        """No conflict is written when no user override exists for the field.

        REQ: FUNC-SYNC-005
        """
        _detect_and_queue_conflict(self.conn, "txn-c1", "merchant_name", "New Merchant")
        self.conn.commit()

        count = self.conn.execute("SELECT COUNT(*) FROM conflict").fetchone()[0]
        self.assertEqual(count, 0)

    def test_detect_conflict_deduplicates_open_conflicts(self) -> None:
        """Second call with same entity+field does not create a duplicate open conflict.

        REQ: FUNC-SYNC-006
        """
        _detect_and_queue_conflict(self.conn, "txn-c1", "display_name", "Name A")
        _detect_and_queue_conflict(self.conn, "txn-c1", "display_name", "Name B")
        self.conn.commit()

        count = self.conn.execute(
            "SELECT COUNT(*) FROM conflict WHERE entity_id = 'txn-c1' AND status = 'open'"
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_apply_transaction_update_preserves_user_override_on_conflict(self) -> None:
        """On UPDATE, a conflicted field is not overwritten in transaction_record.

        REQ: FUNC-SYNC-005, FUNC-SYNC-006
        """
        payload = {
            "transaction_id": "provider-c1",
            "date": "2026-01-05",
            "amount": 20.0,
            "iso_currency_code": "USD",
            "pending": False,
            "name": "Provider Changed Name",
        }
        _apply_transaction(self.conn, "acc-1", payload, retention_enabled=False)
        self.conn.commit()

        # display_name in transaction_record should still be the user's value
        row = self.conn.execute(
            "SELECT display_name FROM transaction_record WHERE id = 'txn-c1'"
        ).fetchone()
        self.assertEqual(row[0], "User Name")

        # A conflict should have been written
        conflict_row = self.conn.execute(
            "SELECT status FROM conflict WHERE entity_id = 'txn-c1' AND field_name = 'display_name'"
        ).fetchone()
        self.assertIsNotNone(conflict_row)
        self.assertEqual(conflict_row[0], "open")
