"""FastAPI application layer for UI integration.

REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-003, FUNC-ACCT-004,
REQ: FUNC-ACCT-005, FUNC-ACCT-007, FUNC-SYNC-001, FUNC-TXN-001,
REQ: FUNC-TXN-002, FUNC-TXN-003, FUNC-TXN-004, FUNC-TXN-005,
REQ: FUNC-TXN-006, FUNC-TXN-007, FUNC-TXN-008,
REQ: FUNC-CAT-001, FUNC-CAT-002,
REQ: FUNC-SYNC-005, FUNC-SYNC-006, FUNC-SYNC-007,
REQ: FUNC-REP-006, SEC-ACC-004, SEC-DATA-003
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from hmac import compare_digest
from pathlib import Path
from typing import Any, Iterator, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi import Path as FastAPIPath
from pydantic import BaseModel, Field, field_validator
from sqlcipher3 import dbapi2 as sqlcipher

from godzilla_core.integrations.plaid_client import (
    PlaidApiError,
    PlaidClient,
    PlaidConfig,
    PlaidConfigError,
    link_sandbox_item,
)
from godzilla_core.integrations.plaid_sync import SyncError, sync_item_transactions_and_balances
from godzilla_core.security.redaction import redact_sensitive
from godzilla_core.security.secrets import SecretStoreError, store_from_env
from godzilla_core.util.time import local_timestamp_metadata

logger = logging.getLogger(__name__)
_MAX_PAGE_SIZE = 200
_SORT_FIELDS = {
    "date": "transaction_record.date",
    "amount": "transaction_record.amount",
}
_DISALLOWED_PLAID_LINK_PRODUCTS = {"balance"}


class PlaidLinkRequest(BaseModel):
    """Request body for creating a sandbox Plaid item.

    REQ: FUNC-ACCT-001, FUNC-ACCT-002
    """

    institution_id: str | None = Field(default=None, min_length=3, max_length=64)
    products: list[str] | None = Field(default=None, min_length=1, max_length=10)

    @field_validator("products")
    @classmethod
    def _normalize_products(cls, value: list[str] | None) -> list[str] | None:
        """Normalize and validate requested Plaid products.

        REQ: FUNC-ACCT-001
        """
        if value is None:
            return None
        normalized = [item.strip().lower() for item in value if item.strip()]
        if not normalized:
            raise ValueError("products must contain at least one value")
        disallowed = sorted(
            {item for item in normalized if item in _DISALLOWED_PLAID_LINK_PRODUCTS}
        )
        if disallowed:
            raise ValueError(
                "products contains unsupported Plaid Link initial_products: "
                + ", ".join(disallowed)
            )
        return normalized


class PlaidLinkResponse(BaseModel):
    """Response payload for successful link creation.

    REQ: FUNC-ACCT-001, FUNC-ACCT-002
    """

    item_id: str
    institution_id: str
    env: str


class PlaidSyncRequest(BaseModel):
    """Request body for triggering a manual sync.

    REQ: FUNC-ACCT-005, FUNC-SYNC-001
    """

    item_id: str = Field(min_length=1, max_length=128)
    institution_id: str | None = Field(default=None, min_length=3, max_length=64)


class PlaidSyncResponse(BaseModel):
    """Response payload describing sync changes.

    REQ: FUNC-ACCT-005, FUNC-SYNC-001
    """

    item_id: str
    added: int
    modified: int
    removed: int
    balance_accounts: int
    cursor: str


class AccountResponse(BaseModel):
    """Account read model for UI listing.

    REQ: FUNC-ACCT-003
    """

    account_id: str
    provider_account_id: str
    item_id: str
    institution_id: str
    name: str
    account_type: str
    subtype: str | None
    mask: str | None
    balance: float | None
    currency: str
    owner_names: list[Any]


class TransactionResponse(BaseModel):
    """Transaction read model for list views.

    REQ: FUNC-TXN-001, FUNC-TXN-002
    """

    transaction_id: str
    account_id: str
    provider_account_id: str
    date: str
    amount: float
    currency: str
    status: str
    merchant_name: str | None
    display_name: str
    category_id: str | None
    notes: str | None
    is_transfer: bool
    is_excluded: bool


class TransactionSplitResponse(BaseModel):
    """Split portion of a transaction.

    REQ: FUNC-TXN-008
    """

    split_id: str
    amount: float
    category_id: str | None
    notes: str | None


class TransactionDetailResponse(BaseModel):
    """Full transaction detail including tags, splits, and raw provider payload.

    REQ: FUNC-TXN-003
    """

    transaction_id: str
    account_id: str
    provider_account_id: str
    date: str
    amount: float
    currency: str
    status: str
    merchant_name: str | None
    display_name: str
    category_id: str | None
    notes: str | None
    is_transfer: bool
    is_excluded: bool
    tags: list[str]
    splits: list[TransactionSplitResponse]
    raw_provider_payloads: list[dict[str, Any]]


class CategoryResponse(BaseModel):
    """Category read model.

    REQ: FUNC-CAT-001, FUNC-CAT-002
    """

    category_id: str
    name: str
    parent_id: str | None
    active: bool


class CreateCategoryRequest(BaseModel):
    """Request body for creating a category.

    REQ: FUNC-CAT-002
    """

    name: str = Field(min_length=1, max_length=128)
    parent_id: str | None = Field(default=None)


class PatchCategoryRequest(BaseModel):
    """Request body for updating a category.

    REQ: FUNC-CAT-002
    """

    name: str | None = Field(default=None, min_length=1, max_length=128)
    active: bool | None = Field(default=None)


class PatchTransactionRequest(BaseModel):
    """Request body for user overrides on a transaction.

    REQ: FUNC-TXN-004, FUNC-TXN-005, FUNC-TXN-006, FUNC-TXN-007
    """

    category_id: str | None = Field(default=None)
    display_name: str | None = Field(default=None, min_length=1, max_length=256)
    notes: str | None = Field(default=None, max_length=2048)
    is_transfer: bool | None = Field(default=None)
    is_excluded: bool | None = Field(default=None)
    add_tags: list[str] | None = Field(default=None)
    remove_tags: list[str] | None = Field(default=None)


class SplitItem(BaseModel):
    """One portion of a transaction split.

    REQ: FUNC-TXN-008
    """

    amount: float
    category_id: str | None = Field(default=None)
    notes: str | None = Field(default=None, max_length=2048)


class ConflictResponse(BaseModel):
    """Conflict read model for resolution queue.

    REQ: FUNC-SYNC-006, FUNC-SYNC-007
    """

    conflict_id: str
    entity_type: str
    entity_id: str
    field_name: str
    local_value: str
    provider_value: str
    status: str
    resolution_choice: str | None


class ResolveConflictRequest(BaseModel):
    """Request body for resolving a conflict.

    REQ: FUNC-SYNC-007
    """

    resolution_choice: Literal["local", "provider"]


class BalanceResponse(BaseModel):
    """Balance snapshot read model.

    REQ: FUNC-REP-006
    """

    snapshot_id: str
    account_id: str
    provider_account_id: str
    date: str
    balance: float
    currency: str


class SyncStateResponse(BaseModel):
    """Per-item sync state read model.

    REQ: FUNC-ACCT-004
    """

    item_id: str
    institution_id: str
    status: str
    last_sync_at_utc: str | None
    last_sync_at_tz: str | None
    last_sync_at_offset_minutes: int | None
    last_sync_status: str | None
    cursor: str | None


def _log_event(level: int, event: str, payload: dict[str, Any]) -> None:
    """Write a structured log event after redacting sensitive content.

    REQ: FUNC-AUD-002, SEC-DATA-002

    Args:
        level: Logging level to emit.
        event: Stable event name.
        payload: Event payload before redaction.
    """
    redacted_payload = redact_sensitive(payload)
    entry = {"event": event, **redacted_payload}
    logger.log(level, json.dumps(entry, sort_keys=True, default=str))


def _expand_path(path_value: str) -> Path:
    """Expand environment variables and user-home references in a path string.

    REQ: SEC-DATA-003

    Args:
        path_value: Raw path value from environment.

    Returns:
        Expanded filesystem path.
    """
    expanded = os.path.expandvars(path_value)
    return Path(expanded).expanduser()


def _read_database_settings() -> tuple[str, str]:
    """Read encrypted database settings from environment variables.

    REQ: SEC-DATA-003

    Returns:
        Tuple of database path and encryption key.
    """
    db_path = os.environ.get("GODZILLA_DB_PATH")
    db_key = os.environ.get("GODZILLA_DB_KEY")
    if not db_path or not db_key:
        raise HTTPException(status_code=500, detail="Database is not configured")
    return db_path, db_key


def _connect_encrypted_db() -> sqlcipher.Connection:
    """Open an encrypted SQLCipher database connection.

    REQ: SEC-DATA-003

    Returns:
        SQLCipher connection with foreign keys enabled.
    """
    db_path, db_key = _read_database_settings()
    expanded = _expand_path(db_path)
    expanded.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlcipher.connect(str(expanded))
    escaped_key = db_key.replace("'", "''")
    conn.execute(f"PRAGMA key = '{escaped_key}';")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def _db_connection() -> Iterator[sqlcipher.Connection]:
    """Yield a managed encrypted database connection.

    REQ: SEC-DATA-003

    Yields:
        Open SQLCipher connection.
    """
    conn = _connect_encrypted_db()
    try:
        yield conn
    finally:
        conn.close()


def _parse_owner_names(value: str | None) -> list[Any]:
    """Deserialize owner metadata JSON from persisted account rows.

    REQ: FUNC-ACCT-003

    Args:
        value: Serialized owner payload string.

    Returns:
        Parsed owner payload list or an empty list when unset.
    """
    if not value:
        return []
    return json.loads(value)


def _upsert_linked_item_metadata(
    conn: sqlcipher.Connection,
    provider_item_id: str,
    plaid_institution_id: str,
) -> None:
    """Persist linked item/institution metadata in the main DB.

    REQ: FUNC-ACCT-004

    Args:
        conn: Open encrypted database connection.
        provider_item_id: Plaid provider item identifier.
        plaid_institution_id: Plaid institution identifier.
    """
    row = conn.execute(
        "SELECT id FROM institution WHERE plaid_institution_id = ?",
        (plaid_institution_id,),
    ).fetchone()
    if row is None:
        institution_id = str(uuid4())
        utc, tz, offset = local_timestamp_metadata()
        conn.execute(
            "INSERT INTO institution ("
            "id, name, plaid_institution_id, created_at_utc, created_at_tz, "
            "created_at_offset_minutes"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            (institution_id, plaid_institution_id, plaid_institution_id, utc, tz, offset),
        )
    else:
        institution_id = row[0]

    access_token_ref = f"plaid_access_token:{provider_item_id}"
    item_row = conn.execute(
        "SELECT id FROM plaid_item WHERE provider_item_id = ?",
        (provider_item_id,),
    ).fetchone()
    if item_row is None:
        item_id = str(uuid4())
        utc, tz, offset = local_timestamp_metadata()
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
                "linked",
                None,
                None,
                None,
                utc,
                tz,
                offset,
            ),
        )
        return

    conn.execute(
        "UPDATE plaid_item SET institution_id = ?, access_token_ref = ?, status = ? WHERE id = ?",
        (institution_id, access_token_ref, "linked", item_row[0]),
    )


async def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Validate API caller credentials.

    REQ: SEC-ACC-004
    """
    expected = os.environ.get("GODZILLA_API_TOKEN")
    if not expected:
        raise HTTPException(status_code=500, detail="API auth is not configured")

    if not x_api_key or not compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _register_plaid_routes(app: FastAPI) -> None:
    """Register Plaid endpoints on the FastAPI application.

    REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-004, FUNC-ACCT-005,
    REQ: FUNC-SYNC-001, SEC-ACC-004

    Args:
        app: FastAPI app instance to attach routes to.
    """

    @app.post(
        "/plaid/link",
        response_model=PlaidLinkResponse,
        dependencies=[Depends(require_api_key)],
    )
    async def plaid_link(request: PlaidLinkRequest) -> PlaidLinkResponse:
        """Create a sandbox Plaid item and persist its token.

        REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-004
        """
        try:
            config = PlaidConfig.from_env()
            if config.env != "sandbox":
                raise HTTPException(
                    status_code=400,
                    detail="Only PLAID_ENV=sandbox is supported by this endpoint",
                )

            client = PlaidClient(config)
            secret_store = store_from_env()
            link_result = link_sandbox_item(
                client=client,
                secret_store=secret_store,
                institution_id=request.institution_id,
                products=request.products,
            )
            institution_id = request.institution_id or config.sandbox_institution_id
            with _db_connection() as conn:
                _upsert_linked_item_metadata(
                    conn=conn,
                    provider_item_id=link_result["item_id"],
                    plaid_institution_id=institution_id,
                )
                conn.commit()
            return PlaidLinkResponse(
                item_id=link_result["item_id"],
                institution_id=institution_id,
                env=config.env,
            )
        except HTTPException:
            raise
        except (PlaidConfigError, SecretStoreError) as exc:
            _log_event(
                logging.ERROR,
                "plaid_link_config_error",
                {"error": str(exc)},
            )
            raise HTTPException(
                status_code=500,
                detail="Plaid link service is not configured",
            ) from exc
        except PlaidApiError as exc:
            _log_event(
                logging.ERROR,
                "plaid_link_failed",
                {
                    "status_code": exc.status_code,
                    "error": str(exc),
                    "institution_id": request.institution_id,
                },
            )
            raise HTTPException(status_code=502, detail="Plaid link request failed") from exc

    @app.post(
        "/plaid/sync",
        response_model=PlaidSyncResponse,
        dependencies=[Depends(require_api_key)],
    )
    async def plaid_sync(request: PlaidSyncRequest) -> PlaidSyncResponse:
        """Run manual incremental sync for one Plaid item.

        REQ: FUNC-ACCT-005, FUNC-SYNC-001
        """
        try:
            result = sync_item_transactions_and_balances(
                provider_item_id=request.item_id,
                plaid_institution_id=request.institution_id,
            )
            return PlaidSyncResponse(
                item_id=result.item_id,
                added=result.added,
                modified=result.modified,
                removed=result.removed,
                balance_accounts=result.balance_accounts,
                cursor=result.cursor,
            )
        except SyncError as exc:
            _log_event(
                logging.ERROR,
                "plaid_sync_failed",
                {"item_id": request.item_id, "error": str(exc)},
            )
            raise HTTPException(status_code=400, detail="Plaid sync failed") from exc


def _validate_category_assignment(conn: sqlcipher.Connection, category_id: str) -> None:
    """Validate that a category can be assigned to a transaction or split.

    Raises HTTPException(422) if the category does not exist, is not active,
    or is a parent category (leaf-only assignment enforced).

    REQ: FUNC-CAT-002, FUNC-TXN-004

    Args:
        conn: Open database connection.
        category_id: Category primary key to validate.
    """
    row = conn.execute(
        "SELECT id, active FROM category WHERE id = ?",
        (category_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=422, detail=f"Category '{category_id}' does not exist")
    if not row[1]:
        raise HTTPException(status_code=422, detail=f"Category '{category_id}' is not active")
    child_row = conn.execute(
        "SELECT id FROM category WHERE parent_id = ? LIMIT 1",
        (category_id,),
    ).fetchone()
    if child_row is not None:
        raise HTTPException(
            status_code=422,
            detail=f"Category '{category_id}' has children; only leaf categories may be assigned",
        )


def _row_to_transaction_response(row: tuple[Any, ...]) -> TransactionResponse:
    """Build a TransactionResponse from a SELECT result row.

    REQ: FUNC-TXN-001, FUNC-TXN-002

    Args:
        row: Columns: id, account_id, provider_account_id, date, amount, currency,
             status, merchant_name, display_name, category_id, notes, is_transfer,
             is_excluded.
    """
    return TransactionResponse(
        transaction_id=row[0],
        account_id=row[1],
        provider_account_id=row[2],
        date=row[3],
        amount=float(row[4]),
        currency=row[5],
        status=row[6],
        merchant_name=row[7],
        display_name=row[8],
        category_id=row[9],
        notes=row[10],
        is_transfer=bool(row[11]),
        is_excluded=bool(row[12]),
    )


_TXN_SELECT = (
    "SELECT "
    "transaction_record.id, transaction_record.account_id, account.provider_account_id, "
    "transaction_record.date, transaction_record.amount, transaction_record.currency, "
    "transaction_record.status, transaction_record.merchant_name, "
    "transaction_record.display_name, transaction_record.category_id, "
    "transaction_record.notes, transaction_record.is_transfer, "
    "transaction_record.is_excluded "
    "FROM transaction_record "
    "JOIN account ON account.id = transaction_record.account_id"
)


def _register_read_routes(app: FastAPI) -> None:  # noqa: PLR0915
    """Register read/query endpoints on the FastAPI application.

    REQ: FUNC-ACCT-003, FUNC-TXN-001, FUNC-TXN-002, FUNC-TXN-003,
    REQ: FUNC-REP-006, FUNC-ACCT-004, FUNC-CAT-001, FUNC-SYNC-006, SEC-ACC-004

    Args:
        app: FastAPI app instance to attach routes to.
    """

    @app.get(
        "/accounts",
        response_model=list[AccountResponse],
        dependencies=[Depends(require_api_key)],
    )
    async def get_accounts() -> list[AccountResponse]:
        """List linked accounts.

        REQ: FUNC-ACCT-003
        """
        with _db_connection() as conn:
            rows = conn.execute(
                "SELECT "
                "account.id, account.provider_account_id, plaid_item.provider_item_id, "
                "institution.plaid_institution_id, account.name, account.type, account.subtype, "
                "account.mask, account.balance, account.currency, account.owner_names "
                "FROM account "
                "JOIN plaid_item ON plaid_item.id = account.item_id "
                "JOIN institution ON institution.id = plaid_item.institution_id "
                "ORDER BY account.name ASC"
            ).fetchall()

        return [
            AccountResponse(
                account_id=row[0],
                provider_account_id=row[1],
                item_id=row[2],
                institution_id=row[3],
                name=row[4],
                account_type=row[5],
                subtype=row[6],
                mask=row[7],
                balance=float(row[8]) if row[8] is not None else None,
                currency=row[9],
                owner_names=_parse_owner_names(row[10]),
            )
            for row in rows
        ]

    @app.get(
        "/transactions",
        response_model=list[TransactionResponse],
        dependencies=[Depends(require_api_key)],
    )
    async def get_transactions(  # noqa: PLR0913
        account_id: str | None = Query(default=None, min_length=1),
        date_from: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
        date_to: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
        category_id: str | None = Query(default=None, min_length=1),
        merchant: str | None = Query(default=None, min_length=1, max_length=128),
        amount_min: float | None = Query(default=None),
        amount_max: float | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=_MAX_PAGE_SIZE),
        offset: int = Query(default=0, ge=0),
        sort_by: Literal["date", "amount"] = Query(default="date"),
        sort_order: Literal["asc", "desc"] = Query(default="desc"),
    ) -> list[TransactionResponse]:
        """List transactions with pagination, sorting, and optional filters.

        REQ: FUNC-TXN-001, FUNC-TXN-002
        """
        sort_direction = "ASC" if sort_order == "asc" else "DESC"
        sort_field = _SORT_FIELDS[sort_by]

        conditions: list[str] = []
        params: list[Any] = []

        if account_id:
            conditions.append("transaction_record.account_id = ?")
            params.append(account_id)
        if date_from:
            conditions.append("transaction_record.date >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("transaction_record.date <= ?")
            params.append(date_to)
        if category_id:
            conditions.append("transaction_record.category_id = ?")
            params.append(category_id)
        if merchant:
            conditions.append(
                "(transaction_record.merchant_name LIKE ?"
                " OR transaction_record.display_name LIKE ?)"
            )
            params.extend([f"%{merchant}%", f"%{merchant}%"])
        if amount_min is not None:
            conditions.append("transaction_record.amount >= ?")
            params.append(amount_min)
        if amount_max is not None:
            conditions.append("transaction_record.amount <= ?")
            params.append(amount_max)

        where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        query = (
            f"{_TXN_SELECT}"
            f"{where_clause} "
            f"ORDER BY {sort_field} {sort_direction}, transaction_record.id ASC "
            "LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])

        with _db_connection() as conn:
            rows = conn.execute(query, params).fetchall()

        return [_row_to_transaction_response(row) for row in rows]

    @app.get(
        "/transactions/{transaction_id}",
        response_model=TransactionDetailResponse,
        dependencies=[Depends(require_api_key)],
    )
    async def get_transaction(
        transaction_id: str = FastAPIPath(min_length=1),
    ) -> TransactionDetailResponse:
        """Fetch full detail for a single transaction.

        REQ: FUNC-TXN-003
        """
        with _db_connection() as conn:
            row = conn.execute(
                f"{_TXN_SELECT} WHERE transaction_record.id = ?",
                (transaction_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Transaction not found")

            tag_rows = conn.execute(
                "SELECT tag.name FROM transaction_tag "
                "JOIN tag ON tag.id = transaction_tag.tag_id "
                "WHERE transaction_tag.transaction_id = ? "
                "ORDER BY tag.name ASC",
                (transaction_id,),
            ).fetchall()

            split_rows = conn.execute(
                "SELECT id, amount, category_id, notes FROM transaction_split "
                "WHERE transaction_id = ? ORDER BY rowid ASC",
                (transaction_id,),
            ).fetchall()

            raw_rows = conn.execute(
                "SELECT raw_payload FROM provider_raw WHERE transaction_id = ? "
                "ORDER BY created_at_utc ASC",
                (transaction_id,),
            ).fetchall()

        tags = [r[0] for r in tag_rows]
        splits = [
            TransactionSplitResponse(
                split_id=r[0],
                amount=float(r[1]),
                category_id=r[2],
                notes=r[3],
            )
            for r in split_rows
        ]
        raw_payloads = []
        for r in raw_rows:
            try:
                raw_payloads.append(json.loads(r[0]))
            except (json.JSONDecodeError, TypeError):
                raw_payloads.append({"raw": r[0]})

        base = _row_to_transaction_response(row)
        return TransactionDetailResponse(
            transaction_id=base.transaction_id,
            account_id=base.account_id,
            provider_account_id=base.provider_account_id,
            date=base.date,
            amount=base.amount,
            currency=base.currency,
            status=base.status,
            merchant_name=base.merchant_name,
            display_name=base.display_name,
            category_id=base.category_id,
            notes=base.notes,
            is_transfer=base.is_transfer,
            is_excluded=base.is_excluded,
            tags=tags,
            splits=splits,
            raw_provider_payloads=raw_payloads,
        )

    @app.get(
        "/balances",
        response_model=list[BalanceResponse],
        dependencies=[Depends(require_api_key)],
    )
    async def get_balances(
        account_id: str | None = Query(default=None, min_length=1),
        limit: int = Query(default=50, ge=1, le=_MAX_PAGE_SIZE),
        offset: int = Query(default=0, ge=0),
    ) -> list[BalanceResponse]:
        """List balance snapshots for net worth views.

        REQ: FUNC-REP-006
        """
        where_clause = ""
        params: list[Any] = []
        if account_id:
            where_clause = " WHERE balance_snapshot.account_id = ?"
            params.append(account_id)

        params.extend([limit, offset])
        query = (
            "SELECT "
            "balance_snapshot.id, balance_snapshot.account_id, account.provider_account_id, "
            "balance_snapshot.date, balance_snapshot.balance, account.currency "
            "FROM balance_snapshot "
            "JOIN account ON account.id = balance_snapshot.account_id"
            f"{where_clause} "
            "ORDER BY balance_snapshot.date DESC, balance_snapshot.id DESC "
            "LIMIT ? OFFSET ?"
        )

        with _db_connection() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            BalanceResponse(
                snapshot_id=row[0],
                account_id=row[1],
                provider_account_id=row[2],
                date=row[3],
                balance=float(row[4]),
                currency=row[5],
            )
            for row in rows
        ]

    @app.get(
        "/sync-state",
        response_model=list[SyncStateResponse],
        dependencies=[Depends(require_api_key)],
    )
    async def get_sync_state() -> list[SyncStateResponse]:
        """List per-item sync status for UI refresh state.

        REQ: FUNC-ACCT-004
        """
        with _db_connection() as conn:
            rows = conn.execute(
                "SELECT "
                "plaid_item.provider_item_id, institution.plaid_institution_id, plaid_item.status, "
                "sync_state.last_sync_at_utc, sync_state.last_sync_at_tz, "
                "sync_state.last_sync_at_offset_minutes, sync_state.last_sync_status, "
                "sync_state.plaid_cursor "
                "FROM plaid_item "
                "JOIN institution ON institution.id = plaid_item.institution_id "
                "LEFT JOIN sync_state ON sync_state.item_id = plaid_item.id "
                "ORDER BY sync_state.last_sync_at_utc DESC, plaid_item.provider_item_id ASC"
            ).fetchall()

        return [
            SyncStateResponse(
                item_id=row[0],
                institution_id=row[1],
                status=row[2],
                last_sync_at_utc=row[3],
                last_sync_at_tz=row[4],
                last_sync_at_offset_minutes=row[5],
                last_sync_status=row[6],
                cursor=row[7],
            )
            for row in rows
        ]

    @app.get(
        "/categories",
        response_model=list[CategoryResponse],
        dependencies=[Depends(require_api_key)],
    )
    async def get_categories() -> list[CategoryResponse]:
        """List all categories as a flat list (client builds tree).

        REQ: FUNC-CAT-001
        """
        with _db_connection() as conn:
            rows = conn.execute(
                "SELECT id, name, parent_id, active FROM category"
                " ORDER BY parent_id NULLS FIRST, name ASC"
            ).fetchall()
        return [
            CategoryResponse(
                category_id=row[0],
                name=row[1],
                parent_id=row[2],
                active=bool(row[3]),
            )
            for row in rows
        ]

    @app.get(
        "/conflicts",
        response_model=list[ConflictResponse],
        dependencies=[Depends(require_api_key)],
    )
    async def get_conflicts(
        status: Literal["open", "resolved"] = Query(default="open"),
    ) -> list[ConflictResponse]:
        """List conflicts filtered by status.

        REQ: FUNC-SYNC-006
        """
        with _db_connection() as conn:
            rows = conn.execute(
                "SELECT conflict_id, entity_type, entity_id, field_name, "
                "local_value, provider_value, status, resolution_choice "
                "FROM conflict WHERE status = ? "
                "ORDER BY local_updated_at_utc DESC",
                (status,),
            ).fetchall()
        return [
            ConflictResponse(
                conflict_id=row[0],
                entity_type=row[1],
                entity_id=row[2],
                field_name=row[3],
                local_value=row[4],
                provider_value=row[5],
                status=row[6],
                resolution_choice=row[7],
            )
            for row in rows
        ]


def _register_write_routes(app: FastAPI) -> None:  # noqa: PLR0915
    """Register mutating endpoints for categories, transactions, and conflicts.

    REQ: FUNC-CAT-002, FUNC-TXN-004, FUNC-TXN-005, FUNC-TXN-006, FUNC-TXN-007,
    REQ: FUNC-TXN-008, FUNC-SYNC-004, FUNC-SYNC-007, SEC-ACC-004

    Args:
        app: FastAPI app instance to attach routes to.
    """

    @app.post(
        "/categories",
        response_model=CategoryResponse,
        dependencies=[Depends(require_api_key)],
        status_code=201,
    )
    async def create_category(request: CreateCategoryRequest) -> CategoryResponse:
        """Create a new category.

        REQ: FUNC-CAT-002
        """
        with _db_connection() as conn:
            if request.parent_id is not None:
                parent_row = conn.execute(
                    "SELECT id, active FROM category WHERE id = ?",
                    (request.parent_id,),
                ).fetchone()
                if parent_row is None:
                    raise HTTPException(
                        status_code=422, detail=f"Parent category '{request.parent_id}' not found"
                    )
                if not parent_row[1]:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Parent category '{request.parent_id}' is inactive",
                    )

            conflict_row = conn.execute(
                "SELECT id FROM category WHERE name = ? AND parent_id IS ?",
                (request.name, request.parent_id),
            ).fetchone()
            if conflict_row is not None:
                raise HTTPException(
                    status_code=409,
                    detail="A category with this name already exists under the same parent",
                )

            new_id = str(uuid4())
            conn.execute(
                "INSERT INTO category (id, name, parent_id, active) VALUES (?, ?, ?, 1)",
                (new_id, request.name, request.parent_id),
            )
            conn.commit()

        return CategoryResponse(
            category_id=new_id,
            name=request.name,
            parent_id=request.parent_id,
            active=True,
        )

    @app.patch(
        "/categories/{category_id}",
        response_model=CategoryResponse,
        dependencies=[Depends(require_api_key)],
    )
    async def patch_category(
        category_id: str = FastAPIPath(min_length=1),
        request: PatchCategoryRequest = ...,
    ) -> CategoryResponse:
        """Rename or deactivate a category.

        REQ: FUNC-CAT-002
        """
        with _db_connection() as conn:
            row = conn.execute(
                "SELECT id, name, parent_id, active FROM category WHERE id = ?",
                (category_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Category not found")

            name, parent_id, active = row[1], row[2], bool(row[3])

            if request.active is False:
                assigned_row = conn.execute(
                    "SELECT id FROM transaction_record WHERE category_id = ? LIMIT 1",
                    (category_id,),
                ).fetchone()
                if assigned_row is not None:
                    raise HTTPException(
                        status_code=409,
                        detail="Cannot deactivate a category that is assigned to transactions",
                    )

            if request.name is not None:
                name = request.name
            if request.active is not None:
                active = request.active

            conn.execute(
                "UPDATE category SET name = ?, active = ? WHERE id = ?",
                (name, 1 if active else 0, category_id),
            )
            conn.commit()

        return CategoryResponse(
            category_id=category_id,
            name=name,
            parent_id=parent_id,
            active=active,
        )

    @app.patch(
        "/transactions/{transaction_id}",
        response_model=TransactionDetailResponse,
        dependencies=[Depends(require_api_key)],
    )
    async def patch_transaction(
        transaction_id: str = FastAPIPath(min_length=1),
        request: PatchTransactionRequest = ...,
    ) -> TransactionDetailResponse:
        """Apply user overrides to a transaction and record provenance.

        REQ: FUNC-TXN-004, FUNC-TXN-005, FUNC-TXN-006, FUNC-TXN-007, FUNC-SYNC-004
        """
        utc, tz, offset = local_timestamp_metadata()

        with _db_connection() as conn:
            txn_row = conn.execute(
                "SELECT id, category_id, display_name, notes, is_transfer, is_excluded "
                "FROM transaction_record WHERE id = ?",
                (transaction_id,),
            ).fetchone()
            if txn_row is None:
                raise HTTPException(status_code=404, detail="Transaction not found")

            if request.category_id is not None:
                _validate_category_assignment(conn, request.category_id)

            _patchable = {
                "category_id": request.category_id,
                "display_name": request.display_name,
                "notes": request.notes,
                "is_transfer": (
                    1 if request.is_transfer else 0 if request.is_transfer is not None else None
                ),
                "is_excluded": (
                    1 if request.is_excluded else 0 if request.is_excluded is not None else None
                ),
            }
            current_values = {
                "category_id": txn_row[1],
                "display_name": txn_row[2],
                "notes": txn_row[3],
                "is_transfer": txn_row[4],
                "is_excluded": txn_row[5],
            }

            for field, new_value in _patchable.items():
                if new_value is None:
                    continue
                old_value = current_values[field]
                conn.execute(
                    "INSERT INTO transaction_override ("
                    "id, transaction_id, field_name, source, provider_value, user_value, "
                    "updated_at_utc, updated_at_tz, updated_at_offset_minutes"
                    ") VALUES (?, ?, ?, 'user', ?, ?, ?, ?, ?) "
                    "ON CONFLICT(transaction_id, field_name) DO UPDATE SET "
                    "source = 'user', provider_value = excluded.provider_value, "
                    "user_value = excluded.user_value, "
                    "updated_at_utc = excluded.updated_at_utc, "
                    "updated_at_tz = excluded.updated_at_tz, "
                    "updated_at_offset_minutes = excluded.updated_at_offset_minutes",
                    (
                        str(uuid4()),
                        transaction_id,
                        field,
                        str(old_value) if old_value is not None else None,
                        str(new_value),
                        utc,
                        tz,
                        offset,
                    ),
                )
                conn.execute(
                    f"UPDATE transaction_record SET {field} = ? WHERE id = ?",  # noqa: S608
                    (new_value, transaction_id),
                )

            if request.add_tags:
                for tag_name in request.add_tags:
                    tag_row = conn.execute(
                        "SELECT id FROM tag WHERE name = ?", (tag_name,)
                    ).fetchone()
                    if tag_row is None:
                        tag_id = str(uuid4())
                        conn.execute(
                            "INSERT INTO tag (id, name, active) VALUES (?, ?, 1)",
                            (tag_id, tag_name),
                        )
                    else:
                        tag_id = tag_row[0]
                    conn.execute(
                        "INSERT OR IGNORE INTO transaction_tag (transaction_id, tag_id) "
                        "VALUES (?, ?)",
                        (transaction_id, tag_id),
                    )

            if request.remove_tags:
                for tag_name in request.remove_tags:
                    conn.execute(
                        "DELETE FROM transaction_tag WHERE transaction_id = ? AND tag_id = ("
                        "SELECT id FROM tag WHERE name = ?)",
                        (transaction_id, tag_name),
                    )

            conn.commit()

        return await get_transaction_detail_internal(
            conn_factory=_db_connection, txn_id=transaction_id
        )

    @app.post(
        "/transactions/{transaction_id}/splits",
        response_model=TransactionDetailResponse,
        dependencies=[Depends(require_api_key)],
    )
    async def post_transaction_splits(
        transaction_id: str = FastAPIPath(min_length=1),
        splits: list[SplitItem] = ...,
    ) -> TransactionDetailResponse:
        """Replace splits for a transaction.

        REQ: FUNC-TXN-008
        """
        with _db_connection() as conn:
            txn_row = conn.execute(
                "SELECT amount FROM transaction_record WHERE id = ?",
                (transaction_id,),
            ).fetchone()
            if txn_row is None:
                raise HTTPException(status_code=404, detail="Transaction not found")

            txn_amount = float(txn_row[0])
            split_total = sum(s.amount for s in splits)
            _SPLIT_TOLERANCE = 0.005
            if splits and abs(split_total - txn_amount) > _SPLIT_TOLERANCE:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Split amounts ({split_total:.2f}) must sum to"
                        f" transaction amount ({txn_amount:.2f})"
                    ),
                )

            for split in splits:
                if split.category_id is not None:
                    _validate_category_assignment(conn, split.category_id)

            conn.execute(
                "DELETE FROM transaction_split WHERE transaction_id = ?",
                (transaction_id,),
            )
            for split in splits:
                conn.execute(
                    "INSERT INTO transaction_split"
                    " (id, transaction_id, amount, category_id, notes)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (str(uuid4()), transaction_id, split.amount, split.category_id, split.notes),
                )
            conn.commit()

        return await get_transaction_detail_internal(
            conn_factory=_db_connection, txn_id=transaction_id
        )

    @app.post(
        "/conflicts/{conflict_id}/resolve",
        response_model=ConflictResponse,
        dependencies=[Depends(require_api_key)],
    )
    async def resolve_conflict(
        conflict_id: str = FastAPIPath(min_length=1),
        request: ResolveConflictRequest = ...,
    ) -> ConflictResponse:
        """Resolve a conflict by choosing local or provider value.

        REQ: FUNC-SYNC-007
        """
        utc, tz, offset = local_timestamp_metadata()

        with _db_connection() as conn:
            c_row = conn.execute(
                "SELECT conflict_id, entity_type, entity_id, field_name, "
                "local_value, provider_value, status "
                "FROM conflict WHERE conflict_id = ?",
                (conflict_id,),
            ).fetchone()
            if c_row is None:
                raise HTTPException(status_code=404, detail="Conflict not found")
            if c_row[6] == "resolved":
                raise HTTPException(status_code=409, detail="Conflict is already resolved")

            entity_id = c_row[2]
            field_name = c_row[3]
            provider_value = c_row[5]

            if request.resolution_choice == "provider":
                conn.execute(
                    f"UPDATE transaction_record SET {field_name} = ? WHERE id = ?",  # noqa: S608
                    (provider_value, entity_id),
                )
                conn.execute(
                    "DELETE FROM transaction_override WHERE transaction_id = ? AND field_name = ?",
                    (entity_id, field_name),
                )

            conn.execute(
                "UPDATE conflict SET status = 'resolved', resolution_choice = ?, "
                "resolved_at_utc = ?, resolved_at_tz = ?, resolved_at_offset_minutes = ? "
                "WHERE conflict_id = ?",
                (request.resolution_choice, utc, tz, offset, conflict_id),
            )
            conn.execute(
                "INSERT INTO conflict_resolution (id, conflict_id, resolved_by, "
                "resolved_at_utc, resolved_at_tz, resolved_at_offset_minutes, choice) "
                "VALUES (?, ?, 'user', ?, ?, ?, ?)",
                (str(uuid4()), conflict_id, utc, tz, offset, request.resolution_choice),
            )
            conn.commit()

        return ConflictResponse(
            conflict_id=c_row[0],
            entity_type=c_row[1],
            entity_id=entity_id,
            field_name=field_name,
            local_value=c_row[4],
            provider_value=provider_value,
            status="resolved",
            resolution_choice=request.resolution_choice,
        )


async def get_transaction_detail_internal(
    conn_factory: Any,
    txn_id: str,
) -> TransactionDetailResponse:
    """Fetch a full TransactionDetailResponse by transaction ID.

    REQ: FUNC-TXN-003, FUNC-TXN-004, FUNC-TXN-008

    Args:
        conn_factory: Context manager that yields a DB connection.
        txn_id: Internal transaction primary key.
    """
    with conn_factory() as conn:
        row = conn.execute(
            f"{_TXN_SELECT} WHERE transaction_record.id = ?",
            (txn_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Transaction not found")

        tag_rows = conn.execute(
            "SELECT tag.name FROM transaction_tag "
            "JOIN tag ON tag.id = transaction_tag.tag_id "
            "WHERE transaction_tag.transaction_id = ? "
            "ORDER BY tag.name ASC",
            (txn_id,),
        ).fetchall()

        split_rows = conn.execute(
            "SELECT id, amount, category_id, notes FROM transaction_split "
            "WHERE transaction_id = ? ORDER BY rowid ASC",
            (txn_id,),
        ).fetchall()

        raw_rows = conn.execute(
            "SELECT raw_payload FROM provider_raw WHERE transaction_id = ? "
            "ORDER BY created_at_utc ASC",
            (txn_id,),
        ).fetchall()

    tags = [r[0] for r in tag_rows]
    splits = [
        TransactionSplitResponse(
            split_id=r[0],
            amount=float(r[1]),
            category_id=r[2],
            notes=r[3],
        )
        for r in split_rows
    ]
    raw_payloads = []
    for r in raw_rows:
        try:
            raw_payloads.append(json.loads(r[0]))
        except (json.JSONDecodeError, TypeError):
            raw_payloads.append({"raw": r[0]})

    base = _row_to_transaction_response(row)
    return TransactionDetailResponse(
        transaction_id=base.transaction_id,
        account_id=base.account_id,
        provider_account_id=base.provider_account_id,
        date=base.date,
        amount=base.amount,
        currency=base.currency,
        status=base.status,
        merchant_name=base.merchant_name,
        display_name=base.display_name,
        category_id=base.category_id,
        notes=base.notes,
        is_transfer=base.is_transfer,
        is_excluded=base.is_excluded,
        tags=tags,
        splits=splits,
        raw_provider_payloads=raw_payloads,
    )


def create_app() -> FastAPI:
    """Build and return the FastAPI application.

    REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-003, FUNC-ACCT-004, FUNC-ACCT-005,
    REQ: FUNC-SYNC-001, FUNC-TXN-001, FUNC-TXN-002, FUNC-TXN-003, FUNC-TXN-004,
    REQ: FUNC-TXN-005, FUNC-TXN-006, FUNC-TXN-007, FUNC-TXN-008,
    REQ: FUNC-CAT-001, FUNC-CAT-002, FUNC-SYNC-005, FUNC-SYNC-006, FUNC-SYNC-007,
    REQ: FUNC-REP-006, SEC-ACC-004
    """
    app = FastAPI(title="Godzilla Core API", version="0.1.0")
    _register_plaid_routes(app)
    _register_read_routes(app)
    _register_write_routes(app)
    return app


app = create_app()
