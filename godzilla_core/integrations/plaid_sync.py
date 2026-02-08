"""Plaid sync ingestion for transactions and balances.

REQ: FUNC-ACCT-003, FUNC-SYNC-001, FUNC-SYNC-002, FUNC-SYNC-003, FUNC-REP-006
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from uuid import uuid4

from sqlcipher3 import dbapi2 as sqlcipher

from godzilla_core.integrations.plaid_client import PlaidClient, PlaidConfig
from godzilla_core.security.secrets import store_from_env
from godzilla_core.util.time import local_date, local_timestamp_metadata


@dataclass(frozen=True)
class SyncResult:
    item_id: str
    added: int
    modified: int
    removed: int
    balance_accounts: int
    cursor: str


class SyncError(RuntimeError):
    pass


def _escape_key(db_key: str) -> str:
    return db_key.replace("'", "''")


def _expand_path(path_value: str) -> Path:
    expanded = os.path.expandvars(path_value)
    return Path(expanded).expanduser()


def _connect(db_path: str, db_key: str) -> sqlcipher.Connection:
    path = _expand_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlcipher.connect(str(path))
    escaped_key = _escape_key(db_key)
    conn.execute(f"PRAGMA key = '{escaped_key}';")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _timestamp_meta(prefix: str) -> Dict[str, Any]:
    utc, tz, offset = local_timestamp_metadata()
    return {
        f"{prefix}_utc": utc,
        f"{prefix}_tz": tz,
        f"{prefix}_offset_minutes": offset,
    }


def _retention_enabled(conn: sqlcipher.Connection) -> bool:
    row = conn.execute(
        "SELECT retain_raw_payloads FROM retention_policy LIMIT 1"
    ).fetchone()
    if row is None:
        return True
    return bool(row[0])


def _get_institution_id(conn: sqlcipher.Connection, plaid_institution_id: str) -> Optional[str]:
    row = conn.execute(
        "SELECT id FROM institution WHERE plaid_institution_id = ?",
        (plaid_institution_id,),
    ).fetchone()
    return row[0] if row else None


def _get_plaid_institution_id_for_item(
    conn: sqlcipher.Connection,
    provider_item_id: str,
) -> Optional[str]:
    row = conn.execute(
        "SELECT institution.plaid_institution_id "
        "FROM plaid_item "
        "JOIN institution ON institution.id = plaid_item.institution_id "
        "WHERE plaid_item.provider_item_id = ?",
        (provider_item_id,),
    ).fetchone()
    return row[0] if row else None


def _upsert_institution(conn: sqlcipher.Connection, plaid_institution_id: str) -> str:
    institution_id = _get_institution_id(conn, plaid_institution_id)
    if institution_id:
        return institution_id

    institution_id = str(uuid4())
    meta = _timestamp_meta("created_at")
    conn.execute(
        "INSERT INTO institution ("
        "id, name, plaid_institution_id, created_at_utc, created_at_tz, created_at_offset_minutes"
        ") VALUES (?, ?, ?, ?, ?, ?)",
        (
            institution_id,
            plaid_institution_id,
            plaid_institution_id,
            meta["created_at_utc"],
            meta["created_at_tz"],
            meta["created_at_offset_minutes"],
        ),
    )
    return institution_id


def _get_item_id(conn: sqlcipher.Connection, provider_item_id: str) -> Optional[str]:
    row = conn.execute(
        "SELECT id FROM plaid_item WHERE provider_item_id = ?",
        (provider_item_id,),
    ).fetchone()
    return row[0] if row else None


def _upsert_item(
    conn: sqlcipher.Connection,
    institution_id: str,
    provider_item_id: str,
    access_token_ref: str,
    status: str,
) -> str:
    item_id = _get_item_id(conn, provider_item_id)
    meta = _timestamp_meta("created_at")

    if item_id is None:
        item_id = str(uuid4())
        conn.execute(
            "INSERT INTO plaid_item ("
            "id, provider_item_id, institution_id, access_token_ref, status, "
            "last_sync_at_utc, last_sync_at_tz, last_sync_at_offset_minutes, "
            "created_at_utc, created_at_tz, created_at_offset_minutes"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item_id,
                provider_item_id,
                institution_id,
                access_token_ref,
                status,
                None,
                None,
                None,
                meta["created_at_utc"],
                meta["created_at_tz"],
                meta["created_at_offset_minutes"],
            ),
        )
        return item_id

    conn.execute(
        "UPDATE plaid_item SET "
        "institution_id = ?, access_token_ref = ?, status = ? "
        "WHERE id = ?",
        (institution_id, access_token_ref, status, item_id),
    )
    return item_id


def _set_item_last_sync(conn: sqlcipher.Connection, item_id: str) -> None:
    meta = _timestamp_meta("last_sync_at")
    conn.execute(
        "UPDATE plaid_item SET "
        "last_sync_at_utc = ?, last_sync_at_tz = ?, last_sync_at_offset_minutes = ? "
        "WHERE id = ?",
        (
            meta["last_sync_at_utc"],
            meta["last_sync_at_tz"],
            meta["last_sync_at_offset_minutes"],
            item_id,
        ),
    )


def _upsert_account(conn: sqlcipher.Connection, item_id: str, payload: Dict[str, Any]) -> str:
    provider_account_id = payload["account_id"]
    name = payload.get("official_name") or payload.get("name") or provider_account_id
    balances = payload.get("balances", {})
    currency = balances.get("iso_currency_code") or balances.get("unofficial_currency_code") or "USD"
    balance = balances.get("current")

    row = conn.execute(
        "SELECT id FROM account WHERE provider_account_id = ?",
        (provider_account_id,),
    ).fetchone()
    existing_id = row[0] if row else None

    if existing_id is None:
        account_id = str(uuid4())
        meta = _timestamp_meta("created_at")
        conn.execute(
            "INSERT INTO account ("
            "id, item_id, provider_account_id, name, type, subtype, mask, balance, currency, "
            "owner_names, created_at_utc, created_at_tz, created_at_offset_minutes"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                account_id,
                item_id,
                provider_account_id,
                name,
                payload.get("type") or "unknown",
                payload.get("subtype"),
                payload.get("mask"),
                balance,
                currency,
                json.dumps(payload.get("owners")) if payload.get("owners") else None,
                meta["created_at_utc"],
                meta["created_at_tz"],
                meta["created_at_offset_minutes"],
            ),
        )
        return account_id

    conn.execute(
        "UPDATE account SET "
        "item_id = ?, name = ?, type = ?, subtype = ?, mask = ?, balance = ?, currency = ?, "
        "owner_names = ? "
        "WHERE id = ?",
        (
            item_id,
            name,
            payload.get("type") or "unknown",
            payload.get("subtype"),
            payload.get("mask"),
            balance,
            currency,
            json.dumps(payload.get("owners")) if payload.get("owners") else None,
            existing_id,
        ),
    )
    return existing_id


def _insert_balance_snapshot(conn: sqlcipher.Connection, account_id: str, balance: Optional[float]) -> None:
    if balance is None:
        return
    snapshot_date = local_date()
    conn.execute(
        "INSERT INTO balance_snapshot (id, account_id, date, balance) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(account_id, date) DO UPDATE SET balance=excluded.balance",
        (str(uuid4()), account_id, snapshot_date, balance),
    )


def _fallback_transaction_id(account_id: str, payload: Dict[str, Any]) -> str:
    key = "|".join(
        [
            account_id,
            str(payload.get("date") or ""),
            str(payload.get("amount") or ""),
            payload.get("name") or payload.get("merchant_name") or "",
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _apply_transaction(
    conn: sqlcipher.Connection,
    account_id: str,
    payload: Dict[str, Any],
    retention_enabled: bool,
) -> None:
    provider_transaction_id = payload.get("transaction_id")
    pending_transaction_id = payload.get("pending_transaction_id")
    status = "pending" if payload.get("pending") else "posted"
    currency = payload.get("iso_currency_code") or payload.get("unofficial_currency_code") or "USD"
    meta_created = _timestamp_meta("created_at")
    meta_updated = _timestamp_meta("updated_at")

    display_name = payload.get("name") or payload.get("merchant_name") or "Unknown"

    if pending_transaction_id:
        row = conn.execute(
            "SELECT id FROM transaction_record WHERE provider_transaction_id = ?",
            (pending_transaction_id,),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE transaction_record SET "
                "provider_transaction_id = ?, date = ?, amount = ?, currency = ?, status = ?, "
                "merchant_name = ?, display_name = ?, updated_at_utc = ?, updated_at_tz = ?, "
                "updated_at_offset_minutes = ? "
                "WHERE id = ?",
                (
                    provider_transaction_id,
                    payload.get("date"),
                    payload.get("amount"),
                    currency,
                    status,
                    payload.get("merchant_name"),
                    display_name,
                    meta_updated["updated_at_utc"],
                    meta_updated["updated_at_tz"],
                    meta_updated["updated_at_offset_minutes"],
                    row[0],
                ),
            )
            if retention_enabled:
                _insert_raw_payload(conn, row[0], payload)
            return

    if provider_transaction_id:
        row = conn.execute(
            "SELECT id FROM transaction_record WHERE provider_transaction_id = ?",
            (provider_transaction_id,),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE transaction_record SET "
                "account_id = ?, date = ?, amount = ?, currency = ?, status = ?, "
                "merchant_name = ?, display_name = ?, updated_at_utc = ?, updated_at_tz = ?, "
                "updated_at_offset_minutes = ? "
                "WHERE id = ?",
                (
                    account_id,
                    payload.get("date"),
                    payload.get("amount"),
                    currency,
                    status,
                    payload.get("merchant_name"),
                    display_name,
                    meta_updated["updated_at_utc"],
                    meta_updated["updated_at_tz"],
                    meta_updated["updated_at_offset_minutes"],
                    row[0],
                ),
            )
            if retention_enabled:
                _insert_raw_payload(conn, row[0], payload)
            return

        record_id = str(uuid4())
        conn.execute(
            "INSERT INTO transaction_record ("
            "id, account_id, provider_transaction_id, date, amount, currency, status, "
            "merchant_name, display_name, category_id, is_transfer, is_excluded, notes, "
            "created_at_utc, created_at_tz, created_at_offset_minutes, "
            "updated_at_utc, updated_at_tz, updated_at_offset_minutes"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record_id,
                account_id,
                provider_transaction_id,
                payload.get("date"),
                payload.get("amount"),
                currency,
                status,
                payload.get("merchant_name"),
                display_name,
                None,
                0,
                0,
                None,
                meta_created["created_at_utc"],
                meta_created["created_at_tz"],
                meta_created["created_at_offset_minutes"],
                meta_updated["updated_at_utc"],
                meta_updated["updated_at_tz"],
                meta_updated["updated_at_offset_minutes"],
            ),
        )
        if retention_enabled:
            _insert_raw_payload(conn, record_id, payload)
        return

    record_id = _fallback_transaction_id(account_id, payload)
    conn.execute(
        "INSERT INTO transaction_record ("
        "id, account_id, provider_transaction_id, date, amount, currency, status, "
        "merchant_name, display_name, category_id, is_transfer, is_excluded, notes, "
        "created_at_utc, created_at_tz, created_at_offset_minutes, "
        "updated_at_utc, updated_at_tz, updated_at_offset_minutes"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET "
        "account_id = excluded.account_id, date = excluded.date, amount = excluded.amount, "
        "currency = excluded.currency, status = excluded.status, merchant_name = excluded.merchant_name, "
        "display_name = excluded.display_name, updated_at_utc = excluded.updated_at_utc, "
        "updated_at_tz = excluded.updated_at_tz, updated_at_offset_minutes = excluded.updated_at_offset_minutes",
        (
            record_id,
            account_id,
            None,
            payload.get("date"),
            payload.get("amount"),
            currency,
            status,
            payload.get("merchant_name"),
            display_name,
            None,
            0,
            0,
            None,
            meta_created["created_at_utc"],
            meta_created["created_at_tz"],
            meta_created["created_at_offset_minutes"],
            meta_updated["updated_at_utc"],
            meta_updated["updated_at_tz"],
            meta_updated["updated_at_offset_minutes"],
        ),
    )
    if retention_enabled:
        _insert_raw_payload(conn, record_id, payload)


def _insert_raw_payload(conn: sqlcipher.Connection, transaction_id: str, payload: Dict[str, Any]) -> None:
    meta = _timestamp_meta("created_at")
    conn.execute(
        "INSERT INTO provider_raw ("
        "id, transaction_id, raw_payload, created_at_utc, created_at_tz, created_at_offset_minutes"
        ") VALUES (?, ?, ?, ?, ?, ?)",
        (
            str(uuid4()),
            transaction_id,
            json.dumps(payload),
            meta["created_at_utc"],
            meta["created_at_tz"],
            meta["created_at_offset_minutes"],
        ),
    )


def _apply_removed(conn: sqlcipher.Connection, removed: Iterable[Dict[str, Any]]) -> int:
    removed_count = 0
    for payload in removed:
        transaction_id = payload.get("transaction_id")
        if not transaction_id:
            continue
        cur = conn.execute(
            "DELETE FROM transaction_record "
            "WHERE provider_transaction_id = ? OR id = ?",
            (transaction_id, transaction_id),
        )
        removed_count += cur.rowcount
    return removed_count


def _update_sync_state(conn: sqlcipher.Connection, item_id: str, cursor: str, status: str) -> None:
    meta = _timestamp_meta("last_sync_at")
    row = conn.execute(
        "SELECT id FROM sync_state WHERE item_id = ?",
        (item_id,),
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO sync_state ("
            "id, item_id, plaid_cursor, last_sync_at_utc, last_sync_at_tz, "
            "last_sync_at_offset_minutes, last_sync_status"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid4()),
                item_id,
                cursor,
                meta["last_sync_at_utc"],
                meta["last_sync_at_tz"],
                meta["last_sync_at_offset_minutes"],
                status,
            ),
        )
        return

    conn.execute(
        "UPDATE sync_state SET "
        "plaid_cursor = ?, last_sync_at_utc = ?, last_sync_at_tz = ?, "
        "last_sync_at_offset_minutes = ?, last_sync_status = ? "
        "WHERE item_id = ?",
        (
            cursor,
            meta["last_sync_at_utc"],
            meta["last_sync_at_tz"],
            meta["last_sync_at_offset_minutes"],
            status,
            item_id,
        ),
    )


def _get_sync_cursor(conn: sqlcipher.Connection, item_id: str) -> Optional[str]:
    row = conn.execute(
        "SELECT plaid_cursor FROM sync_state WHERE item_id = ?",
        (item_id,),
    ).fetchone()
    return row[0] if row else None


def sync_item_transactions_and_balances(
    provider_item_id: str,
    plaid_institution_id: Optional[str] = None,
    db_path: Optional[str] = None,
    db_key: Optional[str] = None,
) -> SyncResult:
    """Sync transactions and balances for a Plaid item.

    REQ: FUNC-ACCT-003, FUNC-SYNC-001, FUNC-SYNC-002, FUNC-SYNC-003, FUNC-REP-006
    """
    config = PlaidConfig.from_env()
    client = PlaidClient(config)
    secrets = store_from_env()

    access_token_key = f"plaid_access_token:{provider_item_id}"
    access_token = secrets.get_secret(access_token_key)
    if not access_token:
        raise SyncError("Missing access token in secrets store")

    db_path = db_path or os.environ.get("GODZILLA_DB_PATH")
    db_key = db_key or os.environ.get("GODZILLA_DB_KEY")
    if not db_path or not db_key:
        raise SyncError("GODZILLA_DB_PATH and GODZILLA_DB_KEY are required")

    conn = _connect(db_path, db_key)
    try:
        retention_enabled = _retention_enabled(conn)

        if not plaid_institution_id:
            plaid_institution_id = _get_plaid_institution_id_for_item(conn, provider_item_id)
            if not plaid_institution_id:
                if config.env == "sandbox":
                    plaid_institution_id = config.sandbox_institution_id
                else:
                    raise SyncError("plaid_institution_id is required outside sandbox")

        institution_uuid = _upsert_institution(conn, plaid_institution_id)
        item_uuid = _upsert_item(
            conn,
            institution_uuid,
            provider_item_id,
            access_token_key,
            status="linked",
        )

        balance_response = client.accounts_balance_get(access_token)
        accounts = balance_response.get("accounts", [])
        for account_payload in accounts:
            account_id = _upsert_account(conn, item_uuid, account_payload)
            balances = account_payload.get("balances", {})
            _insert_balance_snapshot(conn, account_id, balances.get("current"))

        cursor = _get_sync_cursor(conn, item_uuid)
        added_count = modified_count = removed_count = 0

        while True:
            response = client.transactions_sync(access_token, cursor=cursor)
            added = response.get("added", [])
            modified = response.get("modified", [])
            removed = response.get("removed", [])
            has_more = response.get("has_more", False)
            cursor = response.get("next_cursor")

            for payload in added:
                account_id = _find_account_id(conn, payload.get("account_id"))
                if account_id:
                    _apply_transaction(conn, account_id, payload, retention_enabled)
            for payload in modified:
                account_id = _find_account_id(conn, payload.get("account_id"))
                if account_id:
                    _apply_transaction(conn, account_id, payload, retention_enabled)

            removed_count += _apply_removed(conn, removed)
            added_count += len(added)
            modified_count += len(modified)

            if not has_more:
                break

        if cursor:
            _update_sync_state(conn, item_uuid, cursor, "success")
        _set_item_last_sync(conn, item_uuid)

        conn.commit()
        return SyncResult(
            item_id=provider_item_id,
            added=added_count,
            modified=modified_count,
            removed=removed_count,
            balance_accounts=len(accounts),
            cursor=cursor or "",
        )
    finally:
        conn.close()


def _find_account_id(conn: sqlcipher.Connection, provider_account_id: Optional[str]) -> Optional[str]:
    if not provider_account_id:
        return None
    row = conn.execute(
        "SELECT id FROM account WHERE provider_account_id = ?",
        (provider_account_id,),
    ).fetchone()
    return row[0] if row else None
