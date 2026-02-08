"""Plaid sync ingestion tests.

REQ: FUNC-ACCT-003, FUNC-REP-006, FUNC-SYNC-001, FUNC-SYNC-002, FUNC-SYNC-003
"""

import json
import os
import tempfile
import unittest

from sqlcipher3 import dbapi2 as sqlcipher

from godzilla_core.db.migrations import run_migrations
from godzilla_core.integrations.plaid_sync import (
    _apply_transaction,
    _get_sync_cursor,
    _insert_balance_snapshot,
    _update_sync_state,
    _upsert_account,
)
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
