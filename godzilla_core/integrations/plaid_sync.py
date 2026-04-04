"""Plaid sync ingestion for transactions and balances.

REQ: ACC-ACCT-003, ACC-ACCT-009, TECH-ACCT-009-INGEST, TECH-ACCT-009-API,
REQ: ACC-SYNC-001, ACC-SYNC-002, ACC-SYNC-003,
REQ: ACC-TXN-009, TECH-TXN-009-FALLBACK, TECH-TXN-009-CONFLICT, ACC-REP-006,
REQ: ACC-CAT-003, ACC-SYNC-004, ACC-SYNC-005,
REQ: ACC-SYNC-006, ACC-ACCT-008, TECH-SEC-DATA-005, TECH-SEC-DATA-007
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from uuid import uuid4

from sqlcipher3 import dbapi2 as sqlcipher

from godzilla_core.integrations.plaid_client import PlaidClient, PlaidConfig
from godzilla_core.security.secrets import store_from_env
from godzilla_core.util.time import local_date, local_timestamp_metadata


@dataclass(frozen=True)
class SyncResult:
    """Summary of a completed sync run.

    REQ: ACC-SYNC-001, ACC-SYNC-002, ACC-SYNC-003
    """

    item_id: str
    added: int
    modified: int
    removed: int
    balance_accounts: int
    cursor: str


class SyncError(RuntimeError):
    """Raised when sync preconditions or processing fail.

    REQ: ACC-SYNC-001
    """

    pass


def _escape_key(db_key: str) -> str:
    """Escape a SQLCipher key for use in PRAGMA statements.

    REQ: ACC-SYNC-001
    """
    return db_key.replace("'", "''")


def _expand_path(path_value: str) -> Path:
    """Expand environment variables and user-home references in a path.

    REQ: ACC-SYNC-001
    """
    expanded = os.path.expandvars(path_value)
    return Path(expanded).expanduser()


def _connect(db_path: str, db_key: str) -> sqlcipher.Connection:
    """Create an encrypted SQLCipher connection for sync operations.

    REQ: ACC-SYNC-001
    """
    path = _expand_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlcipher.connect(str(path))
    escaped_key = _escape_key(db_key)
    conn.execute(f"PRAGMA key = '{escaped_key}';")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _timestamp_meta(prefix: str) -> Dict[str, Any]:
    """Build timestamp metadata field names and values.

    REQ: ACC-SYNC-001, ACC-SYNC-002, ACC-SYNC-003
    """
    utc, tz, offset = local_timestamp_metadata()
    return {
        f"{prefix}_utc": utc,
        f"{prefix}_tz": tz,
        f"{prefix}_offset_minutes": offset,
    }


def _retention_enabled(conn: sqlcipher.Connection) -> bool:
    """Return whether raw provider payload retention is enabled.

    REQ: ACC-SYNC-003, TECH-SEC-DATA-005
    """
    row = conn.execute(
        "SELECT retain_raw_payloads FROM retention_policy "
        "ORDER BY updated_at_utc DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return True
    return bool(row[0])


def _get_institution_id(conn: sqlcipher.Connection, plaid_institution_id: str) -> Optional[str]:
    """Lookup an internal institution ID by Plaid institution identifier.

    REQ: ACC-ACCT-003
    """
    row = conn.execute(
        "SELECT id FROM institution WHERE plaid_institution_id = ?",
        (plaid_institution_id,),
    ).fetchone()
    return row[0] if row else None


def _get_plaid_institution_id_for_item(
    conn: sqlcipher.Connection,
    provider_item_id: str,
) -> Optional[str]:
    """Resolve Plaid institution ID for an existing linked Plaid item.

    REQ: ACC-ACCT-003, ACC-SYNC-001
    """
    row = conn.execute(
        "SELECT institution.plaid_institution_id "
        "FROM plaid_item "
        "JOIN institution ON institution.id = plaid_item.institution_id "
        "WHERE plaid_item.provider_item_id = ?",
        (provider_item_id,),
    ).fetchone()
    return row[0] if row else None


def _upsert_institution(conn: sqlcipher.Connection, plaid_institution_id: str) -> str:
    """Create or return an institution record for a Plaid institution ID.

    REQ: ACC-ACCT-003, ACC-SYNC-001
    """
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
    """Lookup an internal item ID by provider item ID.

    REQ: ACC-SYNC-001
    """
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
    """Create or update a linked Plaid item record.

    REQ: ACC-SYNC-001, ACC-SYNC-002, ACC-ACCT-008
    """
    item_id = _get_item_id(conn, provider_item_id)
    meta = _timestamp_meta("created_at")

    if item_id is None:
        item_id = str(uuid4())
        conn.execute(
            "INSERT INTO plaid_item ("
            "id, provider_item_id, institution_id, access_token_ref, status, "
            "is_unlinked, "
            "last_sync_at_utc, last_sync_at_tz, last_sync_at_offset_minutes, "
            "created_at_utc, created_at_tz, created_at_offset_minutes"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item_id,
                provider_item_id,
                institution_id,
                access_token_ref,
                status,
                0,
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
        "institution_id = ?, access_token_ref = ?, status = ?, is_unlinked = 0 "
        "WHERE id = ?",
        (institution_id, access_token_ref, status, item_id),
    )
    return item_id


def _item_is_unlinked(conn: sqlcipher.Connection, provider_item_id: str) -> bool:
    """Return whether a Plaid item is locally marked as unlinked.

    REQ: ACC-ACCT-008
    """
    row = conn.execute(
        "SELECT is_unlinked FROM plaid_item WHERE provider_item_id = ?",
        (provider_item_id,),
    ).fetchone()
    return bool(row[0]) if row else False


def _set_item_last_sync(conn: sqlcipher.Connection, item_id: str) -> None:
    """Update a Plaid item's last sync timestamp metadata.

    REQ: ACC-SYNC-001, ACC-SYNC-002
    """
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
    """Create or update an account record from provider payload.

    REQ: ACC-ACCT-003, ACC-ACCT-009, TECH-ACCT-009-INGEST
    """
    provider_account_id = payload["account_id"]
    name = payload.get("official_name") or payload.get("name") or provider_account_id
    balances = payload.get("balances", {})
    currency = (
        balances.get("iso_currency_code") or balances.get("unofficial_currency_code") or "USD"
    )
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


def _insert_balance_snapshot(
    conn: sqlcipher.Connection,
    account_id: str,
    balance: Optional[float],
) -> None:
    """Insert or update the daily balance snapshot for an account.

    REQ: ACC-REP-006
    """
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
    """Generate a deterministic fallback transaction ID.

    REQ: ACC-SYNC-002, ACC-TXN-009, TECH-TXN-009-FALLBACK
    """
    key = "|".join(
        [
            account_id,
            str(payload.get("date") or ""),
            str(payload.get("amount") or ""),
            payload.get("name") or payload.get("merchant_name") or "",
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _apply_transaction(  # noqa: PLR0912
    conn: sqlcipher.Connection,
    account_id: str,
    payload: Dict[str, Any],
    retention_enabled: bool,
) -> None:
    """Insert or update one transaction record from sync payload data.

    On INSERT: maps Plaid personal_finance_category to category_id and records a
    provider-sourced override in transaction_override.

    On UPDATE: runs conflict detection for category_id, display_name, and
    merchant_name against any existing user overrides before applying provider values.

    REQ: ACC-SYNC-001, ACC-SYNC-002, ACC-SYNC-003, ACC-CAT-003, ACC-SYNC-004,
    REQ: ACC-SYNC-005, ACC-SYNC-006, ACC-TXN-009, TECH-TXN-009-FALLBACK,
    REQ: TECH-TXN-009-CONFLICT, TECH-SEC-DATA-005, TECH-SEC-DATA-007
    """
    provider_transaction_id = payload.get("transaction_id")
    pending_transaction_id = payload.get("pending_transaction_id")
    status = "pending" if payload.get("pending") else "posted"
    currency = payload.get("iso_currency_code") or payload.get("unofficial_currency_code") or "USD"
    meta_created = _timestamp_meta("created_at")
    meta_updated = _timestamp_meta("updated_at")

    display_name = payload.get("name") or payload.get("merchant_name") or "Unknown"
    pfc = payload.get("personal_finance_category") or {}
    category_id = _resolve_category_id(conn, pfc)

    _conflict_fields = {
        "category_id": category_id,
        "display_name": display_name,
        "merchant_name": payload.get("merchant_name"),
    }

    if pending_transaction_id:
        row = conn.execute(
            "SELECT id FROM transaction_record WHERE provider_transaction_id = ?",
            (pending_transaction_id,),
        ).fetchone()
        if row:
            record_id = row[0]
            for field, prov_val in _conflict_fields.items():
                if prov_val is not None:
                    _detect_and_queue_conflict(conn, record_id, field, str(prov_val))
            eff_display_name = _preserved_value(conn, record_id, "display_name", display_name)
            eff_merchant_name = _preserved_value(
                conn, record_id, "merchant_name", payload.get("merchant_name")
            )
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
                    eff_merchant_name,
                    eff_display_name,
                    meta_updated["updated_at_utc"],
                    meta_updated["updated_at_tz"],
                    meta_updated["updated_at_offset_minutes"],
                    record_id,
                ),
            )
            if retention_enabled:
                _insert_raw_payload(conn, record_id, payload)
            return

    if provider_transaction_id:
        row = conn.execute(
            "SELECT id FROM transaction_record WHERE provider_transaction_id = ?",
            (provider_transaction_id,),
        ).fetchone()
        if row:
            record_id = row[0]
            for field, prov_val in _conflict_fields.items():
                if prov_val is not None:
                    _detect_and_queue_conflict(conn, record_id, field, str(prov_val))
            eff_display_name = _preserved_value(conn, record_id, "display_name", display_name)
            eff_merchant_name = _preserved_value(
                conn, record_id, "merchant_name", payload.get("merchant_name")
            )
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
                    eff_merchant_name,
                    eff_display_name,
                    meta_updated["updated_at_utc"],
                    meta_updated["updated_at_tz"],
                    meta_updated["updated_at_offset_minutes"],
                    record_id,
                ),
            )
            if retention_enabled:
                _insert_raw_payload(conn, record_id, payload)
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
                category_id,
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
        if category_id:
            _upsert_provider_override(conn, record_id, "category_id", category_id)
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
        "currency = excluded.currency, status = excluded.status, "
        "merchant_name = excluded.merchant_name, "
        "display_name = excluded.display_name, updated_at_utc = excluded.updated_at_utc, "
        "updated_at_tz = excluded.updated_at_tz, "
        "updated_at_offset_minutes = excluded.updated_at_offset_minutes",
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
            category_id,
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
    if category_id:
        _upsert_provider_override(conn, record_id, "category_id", category_id)
    if retention_enabled:
        _insert_raw_payload(conn, record_id, payload)


def _insert_raw_payload(
    conn: sqlcipher.Connection,
    transaction_id: str,
    payload: Dict[str, Any],
) -> None:
    """Persist a raw provider payload linked to a transaction.

    REQ: ACC-SYNC-003
    """
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


def _resolve_category_id(
    conn: sqlcipher.Connection,
    personal_finance_category: Optional[Dict[str, Any]],
) -> Optional[str]:
    """Map a Plaid personal_finance_category payload to a local category ID.

    Tries the detailed key first, then falls back to the primary key.
    Returns None when neither key is found in the local category table.

    REQ: ACC-CAT-003

    Args:
        conn: Open database connection.
        personal_finance_category: Plaid ``personal_finance_category`` dict or None.

    Returns:
        Local category ID string, or None if no mapping exists.
    """
    if not personal_finance_category:
        return None

    detailed = personal_finance_category.get("detailed") or ""
    primary = personal_finance_category.get("primary") or ""

    for candidate in (detailed.lower(), primary.lower()):
        if not candidate:
            continue
        row = conn.execute(
            "SELECT id FROM category WHERE id = ?",
            (candidate,),
        ).fetchone()
        if row:
            return row[0]
    return None


def _upsert_provider_override(
    conn: sqlcipher.Connection,
    transaction_id: str,
    field_name: str,
    provider_value: str,
) -> None:
    """Record a provider-sourced field value in transaction_override.

    Only writes if no user override already exists for this field.

    REQ: ACC-SYNC-004

    Args:
        conn: Open database connection.
        transaction_id: Internal transaction ID.
        field_name: Name of the overridden field.
        provider_value: Value supplied by the provider.
    """
    meta = _timestamp_meta("updated_at")
    utc = meta["updated_at_utc"]
    tz = meta["updated_at_tz"]
    offset = meta["updated_at_offset_minutes"]
    conn.execute(
        "INSERT INTO transaction_override ("
        "id, transaction_id, field_name, source, provider_value, user_value, "
        "updated_at_utc, updated_at_tz, updated_at_offset_minutes"
        ") VALUES (?, ?, ?, 'provider', ?, NULL, ?, ?, ?) "
        "ON CONFLICT(transaction_id, field_name) DO UPDATE SET "
        "provider_value = excluded.provider_value, "
        "updated_at_utc = excluded.updated_at_utc, "
        "updated_at_tz = excluded.updated_at_tz, "
        "updated_at_offset_minutes = excluded.updated_at_offset_minutes "
        "WHERE transaction_override.source = 'provider'",
        (
            str(uuid4()),
            transaction_id,
            field_name,
            provider_value,
            utc,
            tz,
            offset,
        ),
    )


def _preserved_value(
    conn: sqlcipher.Connection,
    transaction_id: str,
    field_name: str,
    provider_value: Optional[str],
) -> Optional[str]:
    """Return the user override value for a field if one exists, else the provider value.

    Used during sync UPDATE to prevent overwriting user-set field values when a
    user override is in place.

    REQ: ACC-SYNC-005, ACC-SYNC-006, TECH-TXN-009-CONFLICT, TECH-SEC-DATA-007

    Args:
        conn: Open database connection.
        transaction_id: Internal transaction ID.
        field_name: Field to check for a user override.
        provider_value: Incoming provider value to use as fallback.

    Returns:
        User's stored value if a user override exists, otherwise ``provider_value``.
    """
    row = conn.execute(
        "SELECT user_value FROM transaction_override "
        "WHERE transaction_id = ? AND field_name = ? AND source = 'user'",
        (transaction_id, field_name),
    ).fetchone()
    return row[0] if row is not None else provider_value


def _detect_and_queue_conflict(
    conn: sqlcipher.Connection,
    transaction_id: str,
    field_name: str,
    provider_value: str,
) -> None:
    """Detect a field-level conflict between a user override and incoming provider value.

    A conflict is raised when:
    - A user override exists for ``field_name`` on this transaction
    - The incoming ``provider_value`` differs from the user's stored value

    The field in ``transaction_record`` is NOT updated; the user's value is preserved.
    An 'open' conflict row is upserted into the ``conflict`` table.

    REQ: ACC-SYNC-005, ACC-SYNC-006, TECH-SEC-DATA-007

    Args:
        conn: Open database connection.
        transaction_id: Internal transaction ID.
        field_name: Field being examined for conflicts.
        provider_value: Incoming value from the provider sync payload.
    """
    override_row = conn.execute(
        "SELECT user_value, updated_at_utc, updated_at_tz, updated_at_offset_minutes "
        "FROM transaction_override "
        "WHERE transaction_id = ? AND field_name = ? AND source = 'user'",
        (transaction_id, field_name),
    ).fetchone()
    if override_row is None:
        return

    user_value = override_row[0]
    if user_value == provider_value:
        return

    local_utc = override_row[1]
    local_tz = override_row[2]
    local_offset = override_row[3]
    existing = conn.execute(
        "SELECT conflict_id FROM conflict"
        " WHERE entity_id = ? AND field_name = ? AND status = 'open'",
        (transaction_id, field_name),
    ).fetchone()
    if existing:
        return

    provider_meta = _timestamp_meta("provider_updated_at")
    conn.execute(
        "INSERT INTO conflict ("
        "conflict_id, entity_type, entity_id, field_name, "
        "local_value, provider_value, "
        "local_updated_at_utc, local_updated_at_tz, local_updated_at_offset_minutes, "
        "provider_updated_at_utc, provider_updated_at_tz, provider_updated_at_offset_minutes, "
        "status"
        ") VALUES (?, 'transaction', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')",
        (
            str(uuid4()),
            transaction_id,
            field_name,
            user_value,
            provider_value,
            local_utc,
            local_tz,
            local_offset,
            provider_meta["provider_updated_at_utc"],
            provider_meta["provider_updated_at_tz"],
            provider_meta["provider_updated_at_offset_minutes"],
        ),
    )


def _apply_removed(conn: sqlcipher.Connection, removed: Iterable[Dict[str, Any]]) -> int:
    """Delete removed transactions from the local store.

    REQ: ACC-SYNC-001
    """
    removed_count = 0
    for payload in removed:
        transaction_id = payload.get("transaction_id")
        if not transaction_id:
            continue
        cur = conn.execute(
            "DELETE FROM transaction_record " "WHERE provider_transaction_id = ? OR id = ?",
            (transaction_id, transaction_id),
        )
        removed_count += cur.rowcount
    return removed_count


def _update_sync_state(conn: sqlcipher.Connection, item_id: str, cursor: str, status: str) -> None:
    """Persist sync cursor and status for a linked item.

    REQ: ACC-SYNC-001, ACC-SYNC-002
    """
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
    """Load the saved Plaid cursor for a linked item.

    REQ: ACC-SYNC-001
    """
    row = conn.execute(
        "SELECT plaid_cursor FROM sync_state WHERE item_id = ?",
        (item_id,),
    ).fetchone()
    return row[0] if row else None


def sync_item_transactions_and_balances(  # noqa: PLR0912, PLR0915
    provider_item_id: str,
    plaid_institution_id: Optional[str] = None,
    db_path: Optional[str] = None,
    db_key: Optional[str] = None,
) -> SyncResult:
    """Sync transactions and balances for a Plaid item.

    REQ: ACC-ACCT-003, ACC-SYNC-001, ACC-SYNC-002, ACC-SYNC-003, ACC-REP-006,
    REQ: ACC-ACCT-008
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
        if _item_is_unlinked(conn, provider_item_id):
            raise SyncError("Item is unlinked and cannot be synced")

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


def _find_account_id(
    conn: sqlcipher.Connection,
    provider_account_id: Optional[str],
) -> Optional[str]:
    """Resolve internal account ID from a provider account ID.

    REQ: ACC-ACCT-003, ACC-SYNC-001
    """
    if not provider_account_id:
        return None
    row = conn.execute(
        "SELECT id FROM account WHERE provider_account_id = ?",
        (provider_account_id,),
    ).fetchone()
    return row[0] if row else None
