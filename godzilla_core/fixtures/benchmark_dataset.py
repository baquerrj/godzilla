"""Deterministic benchmark dataset generator for responsiveness verification.

REQ: ACC-UX-001, ACC-UX-002, ACC-UX-003, ACC-UX-004
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from sqlcipher3 import dbapi2 as sqlcipher

from godzilla_core.db.migrations import run_migrations
from godzilla_core.security.secrets import SecretStore

REFERENCE_SEED = 20260403
REFERENCE_ACCOUNT_COUNT = 10
REFERENCE_TRANSACTION_COUNT = 15000


@dataclass(frozen=True)
class BenchmarkDatasetSummary:
    """Row counts and identifiers for a seeded benchmark profile.

    REQ: ACC-UX-001, ACC-UX-002, ACC-UX-003, ACC-UX-004
    """

    accounts: int
    transactions: int
    budgets: int
    conflicts: int
    linked_items: int


def _connect(path: str, key: str) -> sqlcipher.Connection:
    conn = sqlcipher.connect(path)
    escaped_key = key.replace("'", "''")
    conn.execute(f"PRAGMA key = '{escaped_key}';")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def seed_reference_dataset(  # noqa: PLR0915
    *,
    db_path: str,
    db_key: str,
    secrets_path: str,
    secrets_key: str,
) -> BenchmarkDatasetSummary:
    """Create a deterministic local benchmark profile.

    REQ: ACC-UX-001, ACC-UX-002, ACC-UX-003, ACC-UX-004
    """
    Path(db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    Path(secrets_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    run_migrations(db_path=db_path, db_key=db_key)
    conn = _connect(db_path, db_key)
    rng = random.Random(REFERENCE_SEED)
    try:
        conn.execute("DELETE FROM transaction_tag")
        conn.execute("DELETE FROM transaction_split")
        conn.execute("DELETE FROM provider_raw")
        conn.execute("DELETE FROM conflict_resolution")
        conn.execute("DELETE FROM conflict")
        conn.execute("DELETE FROM transaction_override")
        conn.execute("DELETE FROM transaction_record")
        conn.execute("DELETE FROM balance_snapshot")
        conn.execute("DELETE FROM budget")
        conn.execute("DELETE FROM tag")
        conn.execute("DELETE FROM account")
        conn.execute("DELETE FROM sync_state")
        conn.execute("DELETE FROM plaid_item")
        conn.execute("DELETE FROM institution")
        conn.execute("DELETE FROM settings")
        conn.execute("DELETE FROM retention_policy")
        conn.execute("DELETE FROM export_defaults")
        conn.execute("DELETE FROM audit_log")

        conn.execute(
            "INSERT INTO settings ("
            "id, timezone, currency, auto_lock_minutes, "
            "sync_schedule_enabled, sync_frequency_minutes, "
            "backup_schedule_enabled, backup_frequency_minutes, "
            "backup_retention_count, backup_directory, "
            "created_at_utc, created_at_tz, created_at_offset_minutes, "
            "updated_at_utc, updated_at_tz, updated_at_offset_minutes"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "settings-default",
                "America/Denver",
                "USD",
                15,
                1,
                360,
                1,
                1440,
                7,
                str(Path(db_path).expanduser().parent / "scheduled-backups"),
                "2026-04-01T00:00:00",
                "America/Denver",
                -360,
                "2026-04-01T00:00:00",
                "America/Denver",
                -360,
            ),
        )
        conn.execute(
            "INSERT INTO retention_policy ("
            "id, retain_raw_payloads, retain_logs_days, created_at_utc, created_at_tz, "
            "created_at_offset_minutes, updated_at_utc, updated_at_tz, updated_at_offset_minutes"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "retention-default",
                0,
                90,
                "2026-04-01T00:00:00",
                "America/Denver",
                -360,
                "2026-04-01T00:00:00",
                "America/Denver",
                -360,
            ),
        )
        conn.execute(
            "INSERT INTO export_defaults ("
            "id, include_raw_payloads, created_at_utc, created_at_tz, created_at_offset_minutes, "
            "updated_at_utc, updated_at_tz, updated_at_offset_minutes"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "export-default",
                0,
                "2026-04-01T00:00:00",
                "America/Denver",
                -360,
                "2026-04-01T00:00:00",
                "America/Denver",
                -360,
            ),
        )

        category_ids = [
            row[0]
            for row in conn.execute(
                "SELECT id FROM category WHERE parent_id IS NOT NULL ORDER BY id ASC LIMIT 12"
            ).fetchall()
        ]
        for idx in range(2):
            institution_id = f"inst-{idx + 1}"
            item_id = f"item-{idx + 1}"
            provider_item_id = f"provider-item-{idx + 1}"
            conn.execute(
                "INSERT INTO institution ("
                "id, name, plaid_institution_id, created_at_utc, "
                "created_at_tz, created_at_offset_minutes"
                ") "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    institution_id,
                    f"Benchmark Bank {idx + 1}",
                    f"ins_benchmark_{idx + 1}",
                    "2026-04-01T00:00:00",
                    "America/Denver",
                    -360,
                ),
            )
            conn.execute(
                "INSERT INTO plaid_item ("
                "id, provider_item_id, institution_id, access_token_ref, status, is_unlinked, "
                "last_sync_at_utc, last_sync_at_tz, last_sync_at_offset_minutes, "
                "created_at_utc, created_at_tz, created_at_offset_minutes"
                ") VALUES (?, ?, ?, ?, 'linked', 0, ?, ?, ?, ?, ?, ?)",
                (
                    item_id,
                    provider_item_id,
                    institution_id,
                    f"plaid_access_token:{provider_item_id}",
                    "2026-04-01T10:00:00",
                    "America/Denver",
                    -360,
                    "2026-04-01T00:00:00",
                    "America/Denver",
                    -360,
                ),
            )
            conn.execute(
                "INSERT INTO sync_state ("
                "id, item_id, plaid_cursor, last_sync_at_utc, last_sync_at_tz, "
                "last_sync_at_offset_minutes, last_sync_status"
                ") VALUES (?, ?, ?, ?, ?, ?, 'success')",
                (
                    f"sync-state-{idx + 1}",
                    item_id,
                    f"cursor-{idx + 1}",
                    "2026-04-01T10:00:00",
                    "America/Denver",
                    -360,
                ),
            )

        account_types = [
            ("depository", "checking"),
            ("depository", "savings"),
            ("credit", "credit card"),
            ("loan", "student"),
            ("loan", "mortgage"),
        ]
        for idx in range(REFERENCE_ACCOUNT_COUNT):
            item_id = f"item-{(idx % 2) + 1}"
            account_type, subtype = account_types[idx % len(account_types)]
            owners = [{"names": ["Alex Example"]}] if idx == 0 else [{"names": [f"Owner {idx}"]}]
            conn.execute(
                "INSERT INTO account ("
                "id, item_id, provider_account_id, name, type, subtype, mask, balance, currency, "
                "owner_names, created_at_utc, created_at_tz, created_at_offset_minutes"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"acc-{idx + 1}",
                    item_id,
                    f"provider-acc-{idx + 1}",
                    f"Benchmark Account {idx + 1}",
                    account_type,
                    subtype,
                    f"{1000 + idx:04d}"[-4:],
                    round(2500 - idx * 41.5, 2),
                    "USD",
                    json.dumps(owners),
                    "2026-04-01T00:00:00",
                    "America/Denver",
                    -360,
                ),
            )

        base_date = date(2025, 1, 1)
        for txn_idx in range(REFERENCE_TRANSACTION_COUNT):
            account_index = txn_idx % REFERENCE_ACCOUNT_COUNT
            account_id = f"acc-{account_index + 1}"
            txn_date = base_date + timedelta(days=txn_idx % 365)
            amount = round(((txn_idx % 17) - 8) * 6.75, 2)
            category_id = category_ids[txn_idx % len(category_ids)]
            transaction_id = f"txn-{txn_idx + 1}"
            display_name = f"Benchmark Merchant {txn_idx % 40:02d}"
            provider_transaction_id = None if txn_idx % 53 == 0 else f"provider-txn-{txn_idx + 1}"
            provider_fingerprint = f"fp-{txn_idx + 1}" if provider_transaction_id is None else None
            conn.execute(
                "INSERT INTO transaction_record ("
                "id, account_id, provider_transaction_id, date, amount, currency, status, "
                "merchant_name, display_name, category_id, is_transfer, is_excluded, notes, "
                "provider_fingerprint, created_at_utc, created_at_tz, created_at_offset_minutes, "
                "updated_at_utc, updated_at_tz, updated_at_offset_minutes"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    transaction_id,
                    account_id,
                    provider_transaction_id,
                    txn_date.isoformat(),
                    amount,
                    "USD",
                    "posted",
                    display_name,
                    display_name,
                    category_id,
                    1 if txn_idx % 27 == 0 else 0,
                    1 if txn_idx % 31 == 0 else 0,
                    None,
                    provider_fingerprint,
                    f"{txn_date.isoformat()}T09:00:00",
                    "America/Denver",
                    -360,
                    f"{txn_date.isoformat()}T09:00:00",
                    "America/Denver",
                    -360,
                ),
            )
            if txn_idx % 3 == 0:
                conn.execute(
                    "INSERT INTO balance_snapshot (id, account_id, date, balance) "
                    "VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(account_id, date) DO UPDATE SET balance = excluded.balance",
                    (
                        f"snap-{txn_idx + 1}",
                        account_id,
                        txn_date.isoformat(),
                        round(3200 + rng.random() * 500 - txn_idx * 0.01, 2),
                    ),
                )
            if txn_idx % 250 == 0:
                conn.execute(
                    "INSERT INTO transaction_split ("
                    "id, transaction_id, amount, category_id, notes"
                    ") VALUES (?, ?, ?, ?, ?)",
                    (
                        f"split-{txn_idx + 1}",
                        transaction_id,
                        round(amount / 2, 2),
                        category_ids[(txn_idx + 1) % len(category_ids)],
                        "Benchmark split",
                    ),
                )

        tags = ["needs-review", "tax", "travel", "subscription"]
        for idx, tag_name in enumerate(tags, start=1):
            conn.execute(
                "INSERT INTO tag (id, name, active) VALUES (?, ?, 1)", (f"tag-{idx}", tag_name)
            )
            conn.execute(
                "INSERT INTO transaction_tag (transaction_id, tag_id) VALUES (?, ?)",
                (f"txn-{idx}", f"tag-{idx}"),
            )

        budget_categories = category_ids[:6]
        for month_offset in range(3):
            month = f"2026-0{month_offset + 1}"
            for idx, category_id in enumerate(budget_categories, start=1):
                conn.execute(
                    "INSERT INTO budget (id, month, category_id, amount) VALUES (?, ?, ?, ?)",
                    (f"budget-{month}-{idx}", month, category_id, float(200 + idx * 25)),
                )

        conn.execute(
            "INSERT INTO conflict ("
            "conflict_id, entity_type, entity_id, field_name, local_value, provider_value, "
            "local_updated_at_utc, local_updated_at_tz, local_updated_at_offset_minutes, "
            "provider_updated_at_utc, provider_updated_at_tz, provider_updated_at_offset_minutes, "
            "status, resolution_choice"
            ") VALUES ("
            "?, 'transaction', ?, 'dedup_identity', ?, ?, ?, ?, ?, ?, ?, ?, 'open', NULL"
            ")",
            (
                "conflict-benchmark-1",
                "txn-53",
                "fp-53",
                "fp-reingested-53",
                "2026-04-01T10:00:00",
                "America/Denver",
                -360,
                "2026-04-01T11:00:00",
                "America/Denver",
                -360,
            ),
        )

        conn.commit()
    finally:
        conn.close()

    secrets = SecretStore(db_path=secrets_path, db_key=secrets_key)
    for idx in range(2):
        secrets.set_secret(f"plaid_access_token:provider-item-{idx + 1}", f"token-{idx + 1}")
    secrets.set_secret("scheduled_backup_passphrase", "benchmark-passphrase")

    return BenchmarkDatasetSummary(
        accounts=REFERENCE_ACCOUNT_COUNT,
        transactions=REFERENCE_TRANSACTION_COUNT,
        budgets=len(budget_categories) * 3,
        conflicts=1,
        linked_items=2,
    )
