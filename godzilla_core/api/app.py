"""FastAPI application layer for UI integration.

REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-003, FUNC-ACCT-004,
REQ: FUNC-ACCT-005, FUNC-ACCT-007, FUNC-SYNC-001, FUNC-TXN-001,
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

from fastapi import Depends, FastAPI, Header, HTTPException, Query
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

logger = logging.getLogger(__name__)
_MAX_PAGE_SIZE = 200
_SORT_FIELDS = {
    "date": "transaction_record.date",
    "amount": "transaction_record.amount",
}


class PlaidLinkRequest(BaseModel):
    """Request body for creating a sandbox Plaid item."""

    institution_id: str | None = Field(default=None, min_length=3, max_length=64)
    products: list[str] | None = Field(default=None, min_length=1, max_length=10)

    @field_validator("products")
    @classmethod
    def _normalize_products(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [item.strip() for item in value if item.strip()]
        if not normalized:
            raise ValueError("products must contain at least one value")
        return normalized


class PlaidLinkResponse(BaseModel):
    """Response payload for successful link creation."""

    item_id: str
    institution_id: str
    env: str


class PlaidSyncRequest(BaseModel):
    """Request body for triggering a manual sync."""

    item_id: str = Field(min_length=1, max_length=128)
    institution_id: str | None = Field(default=None, min_length=3, max_length=64)


class PlaidSyncResponse(BaseModel):
    """Response payload describing sync changes."""

    item_id: str
    added: int
    modified: int
    removed: int
    balance_accounts: int
    cursor: str


class AccountResponse(BaseModel):
    """Account read model for UI listing."""

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
    """Transaction read model for list views."""

    transaction_id: str
    account_id: str
    provider_account_id: str
    date: str
    amount: float
    currency: str
    status: str
    merchant_name: str | None
    display_name: str
    is_transfer: bool
    is_excluded: bool


class BalanceResponse(BaseModel):
    """Balance snapshot read model."""

    snapshot_id: str
    account_id: str
    provider_account_id: str
    date: str
    balance: float
    currency: str


class SyncStateResponse(BaseModel):
    """Per-item sync state read model."""

    item_id: str
    institution_id: str
    status: str
    last_sync_at_utc: str | None
    last_sync_at_tz: str | None
    last_sync_at_offset_minutes: int | None
    last_sync_status: str | None
    cursor: str | None


def _log_event(level: int, event: str, payload: dict[str, Any]) -> None:
    redacted_payload = redact_sensitive(payload)
    entry = {"event": event, **redacted_payload}
    logger.log(level, json.dumps(entry, sort_keys=True, default=str))


def _expand_path(path_value: str) -> Path:
    expanded = os.path.expandvars(path_value)
    return Path(expanded).expanduser()


def _read_database_settings() -> tuple[str, str]:
    db_path = os.environ.get("GODZILLA_DB_PATH")
    db_key = os.environ.get("GODZILLA_DB_KEY")
    if not db_path or not db_key:
        raise HTTPException(status_code=500, detail="Database is not configured")
    return db_path, db_key


def _connect_encrypted_db() -> sqlcipher.Connection:
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
    conn = _connect_encrypted_db()
    try:
        yield conn
    finally:
        conn.close()


def _parse_owner_names(value: str | None) -> list[Any]:
    if not value:
        return []
    return json.loads(value)


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
    @app.post(
        "/plaid/link",
        response_model=PlaidLinkResponse,
        dependencies=[Depends(require_api_key)],
    )
    async def plaid_link(request: PlaidLinkRequest) -> PlaidLinkResponse:
        """Create a sandbox Plaid item and persist its token.

        REQ: FUNC-ACCT-001, FUNC-ACCT-002
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


def _register_read_routes(app: FastAPI) -> None:
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
    async def get_transactions(
        account_id: str | None = Query(default=None, min_length=1),
        limit: int = Query(default=50, ge=1, le=_MAX_PAGE_SIZE),
        offset: int = Query(default=0, ge=0),
        sort_by: Literal["date", "amount"] = Query(default="date"),
        sort_order: Literal["asc", "desc"] = Query(default="desc"),
    ) -> list[TransactionResponse]:
        """List transactions with pagination and sorting.

        REQ: FUNC-TXN-001
        """
        sort_direction = "ASC" if sort_order == "asc" else "DESC"
        sort_field = _SORT_FIELDS[sort_by]
        where_clause = ""
        params: list[Any] = []

        if account_id:
            where_clause = " WHERE transaction_record.account_id = ?"
            params.append(account_id)

        query = (
            "SELECT "
            "transaction_record.id, transaction_record.account_id, account.provider_account_id, "
            "transaction_record.date, transaction_record.amount, transaction_record.currency, "
            "transaction_record.status, transaction_record.merchant_name, "
            "transaction_record.display_name, transaction_record.is_transfer, "
            "transaction_record.is_excluded "
            "FROM transaction_record "
            "JOIN account ON account.id = transaction_record.account_id"
            f"{where_clause} "
            f"ORDER BY {sort_field} {sort_direction}, transaction_record.id ASC "
            "LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])

        with _db_connection() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            TransactionResponse(
                transaction_id=row[0],
                account_id=row[1],
                provider_account_id=row[2],
                date=row[3],
                amount=float(row[4]),
                currency=row[5],
                status=row[6],
                merchant_name=row[7],
                display_name=row[8],
                is_transfer=bool(row[9]),
                is_excluded=bool(row[10]),
            )
            for row in rows
        ]

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


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    app = FastAPI(title="Godzilla Core API", version="0.1.0")
    _register_plaid_routes(app)
    _register_read_routes(app)
    return app


app = create_app()
