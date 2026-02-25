"""FastAPI application layer for UI integration.

REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-003, FUNC-ACCT-004,
REQ: FUNC-ACCT-005, FUNC-ACCT-007, FUNC-SYNC-001, FUNC-TXN-001,
REQ: FUNC-TXN-002, FUNC-TXN-003, FUNC-TXN-004, FUNC-TXN-005,
REQ: FUNC-TXN-006, FUNC-TXN-007, FUNC-TXN-008,
REQ: FUNC-CAT-001, FUNC-CAT-002,
REQ: FUNC-SYNC-005, FUNC-SYNC-006, FUNC-SYNC-007,
REQ: FUNC-BUD-001, FUNC-BUD-002, FUNC-BUD-003, FUNC-BUD-004,
REQ: FUNC-REP-001, FUNC-REP-002, FUNC-REP-003, FUNC-REP-004, FUNC-REP-005,
REQ: FUNC-REP-006, FUNC-REP-007, FUNC-REP-008,
REQ: FUNC-EXP-001, FUNC-EXP-002, FUNC-EXP-003,
REQ: FUNC-BKP-001, FUNC-BKP-002, FUNC-BKP-003, FUNC-BKP-004,
REQ: FUNC-SET-001, FUNC-SET-002, FUNC-SET-003, FUNC-SET-004, FUNC-SET-005,
REQ: FUNC-AUD-001, FUNC-AUD-003, FUNC-AUD-004,
REQ: SEC-ACC-004, SEC-DATA-003
"""

from __future__ import annotations

import calendar
import csv
import io
import json
import logging
import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from hmac import compare_digest
from pathlib import Path
from typing import Annotated, Any, Iterator, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Response, UploadFile
from fastapi import Path as FastAPIPath
from pydantic import BaseModel, Field, field_validator
from sqlcipher3 import dbapi2 as sqlcipher

from godzilla_core.db.migrations import run_migrations
from godzilla_core.integrations.plaid_client import (
    PlaidApiError,
    PlaidClient,
    PlaidConfig,
    PlaidConfigError,
    link_sandbox_item,
)
from godzilla_core.integrations.plaid_sync import SyncError, sync_item_transactions_and_balances
from godzilla_core.security.backup import (
    BackupError,
    BackupFormatError,
    BackupIntegrityError,
    create_backup_blob,
    decrypt_backup_blob,
)
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
    account_name: str
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


class CreateBudgetRequest(BaseModel):
    """Request body for creating a monthly budget line.

    REQ: FUNC-BUD-001
    """

    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    category_id: str = Field(min_length=1, max_length=128)
    amount: float = Field(gt=0)


class BudgetLineResponse(BaseModel):
    """Per-category budget line with planned/actual/remaining.

    REQ: FUNC-BUD-001, FUNC-BUD-002, FUNC-BUD-003, FUNC-BUD-004
    """

    budget_id: str
    category_id: str
    month: str
    planned: float
    actual: float
    remaining: float
    is_overspent: bool


class TopSpendingCategoryResponse(BaseModel):
    """Top expense category entry for monthly overview.

    REQ: FUNC-REP-001
    """

    category_id: str
    category_name: str
    amount: float


class MonthlyOverviewResponse(BaseModel):
    """Monthly roll-up metrics and top spending categories.

    REQ: FUNC-REP-001, FUNC-REP-007, FUNC-REP-008
    """

    month: str
    start_date: str
    end_date: str
    income: float
    expenses: float
    net_savings: float
    savings_rate: float
    top_categories: list[TopSpendingCategoryResponse]
    inclusion_note: str
    includes_excluded_items: bool


class CashFlowPointResponse(BaseModel):
    """One month of cash-flow metrics.

    REQ: FUNC-REP-003
    """

    month: str
    income: float
    expenses: float
    net_savings: float
    savings_rate: float


class CashFlowReportResponse(BaseModel):
    """Cash-flow report over a custom date range.

    REQ: FUNC-REP-003, FUNC-REP-007, FUNC-REP-008
    """

    start_date: str
    end_date: str
    points: list[CashFlowPointResponse]
    inclusion_note: str
    includes_excluded_items: bool


class CategoryTrendPointResponse(BaseModel):
    """One month value in a category trend series.

    REQ: FUNC-REP-004
    """

    month: str
    amount: float


class CategoryTrendSeriesResponse(BaseModel):
    """Monthly spending trend for one category.

    REQ: FUNC-REP-004
    """

    category_id: str
    category_name: str
    points: list[CategoryTrendPointResponse]


class CategoryTrendsResponse(BaseModel):
    """Category trend report for selected categories.

    REQ: FUNC-REP-004, FUNC-REP-007, FUNC-REP-008
    """

    start_month: str
    end_month: str
    months: int
    series: list[CategoryTrendSeriesResponse]
    inclusion_note: str
    includes_excluded_items: bool


class NetWorthPointResponse(BaseModel):
    """One date point for assets, liabilities, and net worth.

    REQ: FUNC-REP-005
    """

    date: str
    assets: float
    liabilities: float
    net_worth: float


class NetWorthReportResponse(BaseModel):
    """Net-worth report over a custom date range.

    REQ: FUNC-REP-005, FUNC-REP-008
    """

    start_date: str
    end_date: str
    points: list[NetWorthPointResponse]


class BackupRequest(BaseModel):
    """Request body for encrypted backup creation.

    REQ: FUNC-BKP-001
    """

    passphrase: str = Field(min_length=1, max_length=512)
    include_secrets: bool = False


class RestoreResponse(BaseModel):
    """Restore operation result.

    REQ: FUNC-BKP-003
    """

    restored_database: bool
    restored_secrets: bool
    schema_version: int


class WipeRequest(BaseModel):
    """Request body for wipe confirmation.

    REQ: FUNC-BKP-004
    """

    confirm: str = Field(min_length=1, max_length=64)


class WipeResponse(BaseModel):
    """Wipe operation result details.

    REQ: FUNC-BKP-004
    """

    deleted_files: list[str]
    missing_files: list[str]
    failed_files: list[str]


class RetentionSettingsResponse(BaseModel):
    """Retention policy settings payload.

    REQ: FUNC-SET-002
    """

    retain_raw_payloads: bool
    retain_logs_days: int


class ExportDefaultsResponse(BaseModel):
    """Export default settings payload.

    REQ: FUNC-SET-005
    """

    include_raw_payloads: bool


class SecuritySettingsResponse(BaseModel):
    """Security settings payload persisted in M5.

    REQ: FUNC-SET-003
    """

    auto_lock_minutes: int


class SyncSettingsResponse(BaseModel):
    """Sync settings payload persisted in M5.

    REQ: FUNC-SET-004
    """

    schedule_enabled: bool
    frequency_minutes: int
    scheduler_supported: bool


class SettingsResponse(BaseModel):
    """Consolidated settings read model.

    REQ: FUNC-SET-001, FUNC-SET-002, FUNC-SET-003, FUNC-SET-004, FUNC-SET-005
    """

    timezone: str
    currency: str
    retention: RetentionSettingsResponse
    export_defaults: ExportDefaultsResponse
    security: SecuritySettingsResponse
    sync: SyncSettingsResponse


class RetentionSettingsPatch(BaseModel):
    """Partial update for retention settings.

    REQ: FUNC-SET-002
    """

    retain_raw_payloads: bool | None = None
    retain_logs_days: int | None = Field(default=None, ge=1, le=3650)


class ExportDefaultsPatch(BaseModel):
    """Partial update for export defaults.

    REQ: FUNC-SET-005
    """

    include_raw_payloads: bool | None = None


class SecuritySettingsPatch(BaseModel):
    """Partial update for security settings.

    REQ: FUNC-SET-003
    """

    auto_lock_minutes: int | None = Field(default=None, ge=1, le=1440)


class SyncSettingsPatch(BaseModel):
    """Partial update for sync settings.

    REQ: FUNC-SET-004
    """

    schedule_enabled: bool | None = None
    frequency_minutes: int | None = Field(default=None, ge=5, le=10080)


class UpdateSettingsRequest(BaseModel):
    """Partial settings update payload.

    REQ: FUNC-SET-001, FUNC-SET-002, FUNC-SET-003, FUNC-SET-004, FUNC-SET-005
    """

    timezone: str | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    retention: RetentionSettingsPatch | None = None
    export_defaults: ExportDefaultsPatch | None = None
    security: SecuritySettingsPatch | None = None
    sync: SyncSettingsPatch | None = None


class AuditLogEntryResponse(BaseModel):
    """Audit log entry payload.

    REQ: FUNC-AUD-001, FUNC-AUD-004
    """

    id: str
    event_type: str
    timestamp_utc: str
    timestamp_tz: str
    timestamp_offset_minutes: int
    redacted_payload: dict[str, Any]


class AuditLogResponse(BaseModel):
    """JSON audit log response with pagination metadata.

    REQ: FUNC-AUD-004
    """

    entries: list[AuditLogEntryResponse]
    limit: int
    offset: int


def _log_event(level: int, event: str, payload: dict[str, Any]) -> None:
    """Write a structured log event after redacting sensitive content.

    REQ: FUNC-AUD-001, FUNC-AUD-002, FUNC-AUD-003, SEC-DATA-002

    Args:
        level: Logging level to emit.
        event: Stable event name.
        payload: Event payload before redaction.
    """
    redacted_payload = redact_sensitive(payload)
    entry = {"event": event, **redacted_payload}
    logger.log(level, json.dumps(entry, sort_keys=True, default=str))
    try:
        timestamp_utc, timestamp_tz, timestamp_offset = local_timestamp_metadata()
        with _db_connection() as conn:
            conn.execute(
                "INSERT INTO audit_log ("
                "id, event_type, timestamp_utc, timestamp_tz, timestamp_offset_minutes, "
                "redacted_payload"
                ") VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(uuid4()),
                    event,
                    timestamp_utc,
                    timestamp_tz,
                    timestamp_offset,
                    json.dumps(redacted_payload, sort_keys=True, default=str),
                ),
            )
            retain_logs_days = _load_retain_logs_days(conn)
            _prune_audit_log(conn, retain_logs_days)
            conn.commit()
    except Exception:
        logger.debug("Failed to persist audit event", exc_info=True)


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
        _log_event(
            logging.INFO,
            "link_started",
            {
                "institution_id": request.institution_id,
                "products": request.products or [],
            },
        )
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
            _log_event(
                logging.INFO,
                "link_success",
                {"item_id": link_result["item_id"], "institution_id": institution_id},
            )
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
                "link_failed",
                {"error": str(exc)},
            )
            raise HTTPException(
                status_code=500,
                detail="Plaid link service is not configured",
            ) from exc
        except PlaidApiError as exc:
            _log_event(
                logging.ERROR,
                "link_failed",
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
        _log_event(
            logging.INFO,
            "sync_started",
            {"item_id": request.item_id, "institution_id": request.institution_id},
        )
        try:
            result = sync_item_transactions_and_balances(
                provider_item_id=request.item_id,
                plaid_institution_id=request.institution_id,
            )
            _log_event(
                logging.INFO,
                "sync_success",
                {
                    "item_id": result.item_id,
                    "added": result.added,
                    "modified": result.modified,
                    "removed": result.removed,
                },
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
                "sync_failed",
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


def _build_transaction_filter_clause(  # noqa: PLR0913
    *,
    table_alias: str,
    account_id: str | None,
    date_from: str | None,
    date_to: str | None,
    category_id: str | None,
    merchant: str | None,
    amount_min: float | None,
    amount_max: float | None,
) -> tuple[str, list[Any]]:
    """Build WHERE clause and bind parameters for transaction filters.

    REQ: FUNC-TXN-002, FUNC-EXP-001
    """
    conditions: list[str] = []
    params: list[Any] = []

    if account_id:
        conditions.append(f"{table_alias}.account_id = ?")
        params.append(account_id)
    if date_from:
        conditions.append(f"{table_alias}.date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append(f"{table_alias}.date <= ?")
        params.append(date_to)
    if category_id:
        conditions.append(f"{table_alias}.category_id = ?")
        params.append(category_id)
    if merchant:
        conditions.append(
            f"({table_alias}.merchant_name LIKE ?" f" OR {table_alias}.display_name LIKE ?)"
        )
        params.extend([f"%{merchant}%", f"%{merchant}%"])
    if amount_min is not None:
        conditions.append(f"{table_alias}.amount >= ?")
        params.append(amount_min)
    if amount_max is not None:
        conditions.append(f"{table_alias}.amount <= ?")
        params.append(amount_max)

    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    return where_clause, params


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

# CTE that computes per-category actual spend for a given month.
# Two bind parameters, both equal to the YYYY-MM month string.
# Inclusion rules enforced:
#   - posted only (no pending)
#   - no transfers (is_transfer = 0)
#   - no explicitly excluded transactions (is_excluded = 0)
#   - split-aware: when a transaction has splits, the parent's amount/category
#     is ignored; only split rows contribute.
# The LIKE pattern is safe because `month` is validated to ^\d{4}-\d{2}$ by Pydantic.
# REQ: FUNC-BUD-002, FUNC-BUD-004
_BUDGET_ACTUALS_CTE = """
WITH line_items AS (
  SELECT tr.category_id, tr.amount AS subtotal
  FROM transaction_record tr
  WHERE tr.date LIKE ? || '-%'
    AND tr.is_transfer = 0 AND tr.is_excluded = 0 AND tr.status = 'posted'
    AND tr.category_id IS NOT NULL
    AND NOT EXISTS (SELECT 1 FROM transaction_split WHERE transaction_id = tr.id)
  UNION ALL
  SELECT ts.category_id, ts.amount AS subtotal
  FROM transaction_split ts
  JOIN transaction_record tr ON tr.id = ts.transaction_id
  WHERE tr.date LIKE ? || '-%'
    AND tr.is_transfer = 0 AND tr.is_excluded = 0 AND tr.status = 'posted'
    AND ts.category_id IS NOT NULL
)
SELECT category_id, SUM(subtotal) AS actual
FROM line_items
GROUP BY category_id
"""

_REPORT_INCLUSION_NOTE = (
    "Transaction metrics include posted transactions only; transfers and explicitly "
    "excluded transactions are omitted; split transactions use split line amounts."
)

# Shared CTE for report metrics that use budget inclusion rules.
# Bind params: start_date, end_date, start_date, end_date.
# REQ: FUNC-REP-007
_REPORT_LINE_ITEMS_RANGE_CTE = """
WITH line_items AS (
  SELECT tr.id AS transaction_id, tr.date AS date,
         tr.category_id AS category_id, tr.amount AS amount
  FROM transaction_record tr
  WHERE tr.date >= ? AND tr.date <= ?
    AND tr.is_transfer = 0 AND tr.is_excluded = 0 AND tr.status = 'posted'
    AND tr.category_id IS NOT NULL
    AND NOT EXISTS (SELECT 1 FROM transaction_split WHERE transaction_id = tr.id)
  UNION ALL
  SELECT tr.id AS transaction_id, tr.date AS date,
         ts.category_id AS category_id, ts.amount AS amount
  FROM transaction_split ts
  JOIN transaction_record tr ON tr.id = ts.transaction_id
  WHERE tr.date >= ? AND tr.date <= ?
    AND tr.is_transfer = 0 AND tr.is_excluded = 0 AND tr.status = 'posted'
    AND ts.category_id IS NOT NULL
)
"""


def _parse_month_start(month: str) -> date:
    """Parse YYYY-MM into a month-start date object.

    REQ: FUNC-REP-008
    """
    try:
        return datetime.strptime(f"{month}-01", "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid month value") from exc


def _month_bounds(month: str) -> tuple[str, str]:
    """Return first and last day (YYYY-MM-DD) for a YYYY-MM month.

    REQ: FUNC-REP-008
    """
    start = _parse_month_start(month)
    last_day = calendar.monthrange(start.year, start.month)[1]
    end = date(start.year, start.month, last_day)
    return start.isoformat(), end.isoformat()


def _shift_month(month_start: date, delta_months: int) -> date:
    """Shift a month-start date by `delta_months`.

    REQ: FUNC-REP-008
    """
    month_index = (month_start.year * 12 + (month_start.month - 1)) + delta_months
    year = month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _iter_month_keys(start_date: date, end_date: date) -> list[str]:
    """Build inclusive list of month keys (YYYY-MM) between two dates.

    REQ: FUNC-REP-008
    """
    cursor = date(start_date.year, start_date.month, 1)
    end_month = date(end_date.year, end_date.month, 1)
    keys: list[str] = []
    while cursor <= end_month:
        keys.append(cursor.strftime("%Y-%m"))
        cursor = _shift_month(cursor, 1)
    return keys


def _parse_date_range(start: str, end: str) -> tuple[date, date]:
    """Parse and validate an inclusive ISO date range.

    REQ: FUNC-REP-008
    """
    try:
        start_date = datetime.strptime(start, "%Y-%m-%d").date()
        end_date = datetime.strptime(end, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid date value") from exc
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start must be <= end")
    return start_date, end_date


def _parse_csv_categories(categories: str) -> list[str]:
    """Parse a comma-separated category list.

    REQ: FUNC-REP-004
    """
    parsed = [item.strip() for item in categories.split(",") if item.strip()]
    if not parsed:
        raise HTTPException(status_code=422, detail="At least one category is required")
    seen: set[str] = set()
    deduped: list[str] = []
    for item in parsed:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _latest_included_transaction_date(conn: sqlcipher.Connection) -> date:
    """Return most recent transaction date that participates in report totals.

    REQ: FUNC-REP-007
    """
    row = conn.execute(
        "SELECT MAX(date) FROM transaction_record tr "
        "WHERE tr.is_transfer = 0 AND tr.is_excluded = 0 AND tr.status = 'posted' "
        "AND (tr.category_id IS NOT NULL "
        "OR EXISTS (SELECT 1 FROM transaction_split ts "
        "           WHERE ts.transaction_id = tr.id AND ts.category_id IS NOT NULL))"
    ).fetchone()
    if row and row[0]:
        return datetime.strptime(str(row[0]), "%Y-%m-%d").date()
    return datetime.now().date()


def _csv_attachment_response(
    *,
    filename: str,
    fieldnames: list[str],
    rows: list[dict[str, Any]],
) -> Response:
    """Create a CSV attachment response from row dictionaries.

    REQ: FUNC-EXP-001, FUNC-EXP-002
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


def _export_default_include_raw_payloads(conn: sqlcipher.Connection) -> bool:
    """Return default setting for raw payload inclusion in exports.

    REQ: FUNC-EXP-003
    """
    row = conn.execute("SELECT include_raw_payloads FROM export_defaults LIMIT 1").fetchone()
    if row is None:
        return False
    return bool(row[0])


def _sqlite_related_paths(database_path: Path) -> list[Path]:
    """Return SQLite database path and sidecar paths.

    REQ: FUNC-BKP-004
    """
    return [database_path, Path(f"{database_path}-wal"), Path(f"{database_path}-shm")]


def _read_file_bytes(path: Path) -> bytes:
    """Read all bytes from a file path.

    REQ: FUNC-BKP-001, FUNC-BKP-003
    """
    return path.read_bytes()


def _write_file_bytes_atomic(path: Path, content: bytes) -> None:
    """Atomically replace file content using a temporary path.

    REQ: FUNC-BKP-003
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp-{uuid4().hex}")
    temp_path.write_bytes(content)
    os.replace(temp_path, path)


def _best_effort_wipe(path: Path) -> bool:
    """Best-effort overwrite and unlink for local data wipe.

    REQ: FUNC-BKP-004, SEC-DATA-006
    """
    if not path.exists():
        return False
    try:
        if path.is_file():
            file_size = path.stat().st_size
            with path.open("r+b") as file_handle:
                chunk = b"\x00" * 65536
                remaining = file_size
                while remaining > 0:
                    write_size = min(remaining, len(chunk))
                    file_handle.write(chunk[:write_size])
                    remaining -= write_size
                file_handle.flush()
                os.fsync(file_handle.fileno())
    except OSError:
        # Overwrite failures are non-fatal; continue with unlink.
        pass
    try:
        path.unlink()
    except OSError:
        return False
    return True


def _validate_timezone_name(timezone_name: str) -> None:
    """Validate IANA timezone name.

    REQ: FUNC-SET-001
    """
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=422, detail="Invalid timezone") from exc


def _default_settings_payload() -> SettingsResponse:
    """Return default settings payload used for bootstrap reads.

    REQ: FUNC-SET-001, FUNC-SET-002, FUNC-SET-003, FUNC-SET-004, FUNC-SET-005
    """
    return SettingsResponse(
        timezone="UTC",
        currency="USD",
        retention=RetentionSettingsResponse(
            retain_raw_payloads=True,
            retain_logs_days=90,
        ),
        export_defaults=ExportDefaultsResponse(include_raw_payloads=False),
        security=SecuritySettingsResponse(auto_lock_minutes=15),
        sync=SyncSettingsResponse(
            schedule_enabled=False,
            frequency_minutes=360,
            scheduler_supported=False,
        ),
    )


def _load_retain_logs_days(conn: sqlcipher.Connection) -> int:
    """Return configured audit-log retention days.

    REQ: FUNC-SET-002, FUNC-AUD-003
    """
    row = conn.execute(
        "SELECT retain_logs_days FROM retention_policy ORDER BY rowid ASC LIMIT 1"
    ).fetchone()
    if row is None:
        return _default_settings_payload().retention.retain_logs_days
    return int(row[0])


def _prune_audit_log(conn: sqlcipher.Connection, retain_logs_days: int) -> int:
    """Prune audit rows older than configured retention window.

    REQ: FUNC-AUD-003
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retain_logs_days)
    cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%S")
    return conn.execute(
        "DELETE FROM audit_log WHERE timestamp_utc < ?",
        (cutoff_iso,),
    ).rowcount


def _load_settings(conn: sqlcipher.Connection) -> SettingsResponse:
    """Load consolidated settings from DB, falling back to defaults.

    REQ: FUNC-SET-001, FUNC-SET-002, FUNC-SET-003, FUNC-SET-004, FUNC-SET-005
    """
    default = _default_settings_payload()
    settings_row = conn.execute(
        "SELECT timezone, currency, auto_lock_minutes, sync_schedule_enabled, "
        "sync_frequency_minutes "
        "FROM settings ORDER BY rowid ASC LIMIT 1"
    ).fetchone()
    retention_row = conn.execute(
        "SELECT retain_raw_payloads, retain_logs_days FROM retention_policy "
        "ORDER BY rowid ASC LIMIT 1"
    ).fetchone()
    export_row = conn.execute(
        "SELECT include_raw_payloads FROM export_defaults ORDER BY rowid ASC LIMIT 1"
    ).fetchone()

    timezone = str(settings_row[0]) if settings_row else default.timezone
    currency = str(settings_row[1]) if settings_row else default.currency
    auto_lock_minutes = int(settings_row[2]) if settings_row else default.security.auto_lock_minutes
    schedule_enabled = bool(settings_row[3]) if settings_row else default.sync.schedule_enabled
    frequency_minutes = int(settings_row[4]) if settings_row else default.sync.frequency_minutes
    retain_raw_payloads = (
        bool(retention_row[0]) if retention_row else default.retention.retain_raw_payloads
    )
    retain_logs_days = (
        int(retention_row[1]) if retention_row else default.retention.retain_logs_days
    )
    include_raw_payloads = (
        bool(export_row[0]) if export_row else default.export_defaults.include_raw_payloads
    )
    return SettingsResponse(
        timezone=timezone,
        currency=currency,
        retention=RetentionSettingsResponse(
            retain_raw_payloads=retain_raw_payloads,
            retain_logs_days=retain_logs_days,
        ),
        export_defaults=ExportDefaultsResponse(include_raw_payloads=include_raw_payloads),
        security=SecuritySettingsResponse(auto_lock_minutes=auto_lock_minutes),
        sync=SyncSettingsResponse(
            schedule_enabled=schedule_enabled,
            frequency_minutes=frequency_minutes,
            scheduler_supported=False,
        ),
    )


def _upsert_settings_row(conn: sqlcipher.Connection, settings: SettingsResponse) -> None:
    """Persist consolidated settings across singleton settings tables.

    REQ: FUNC-SET-001, FUNC-SET-002, FUNC-SET-003, FUNC-SET-004, FUNC-SET-005
    """
    utc, tz, offset = local_timestamp_metadata()
    settings_row = conn.execute(
        "SELECT id, created_at_utc, created_at_tz, created_at_offset_minutes "
        "FROM settings ORDER BY rowid ASC LIMIT 1"
    ).fetchone()
    retention_row = conn.execute(
        "SELECT id, created_at_utc, created_at_tz, created_at_offset_minutes FROM retention_policy "
        "ORDER BY rowid ASC LIMIT 1"
    ).fetchone()
    export_row = conn.execute(
        "SELECT id, created_at_utc, created_at_tz, created_at_offset_minutes FROM export_defaults "
        "ORDER BY rowid ASC LIMIT 1"
    ).fetchone()

    settings_id = str(settings_row[0]) if settings_row else "settings-default"
    settings_created = (
        (str(settings_row[1]), str(settings_row[2]), int(settings_row[3]))
        if settings_row
        else (utc, tz, offset)
    )
    conn.execute(
        "INSERT OR REPLACE INTO settings ("
        "id, timezone, currency, auto_lock_minutes, sync_schedule_enabled, sync_frequency_minutes, "
        "created_at_utc, created_at_tz, created_at_offset_minutes, "
        "updated_at_utc, updated_at_tz, updated_at_offset_minutes"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            settings_id,
            settings.timezone,
            settings.currency,
            settings.security.auto_lock_minutes,
            1 if settings.sync.schedule_enabled else 0,
            settings.sync.frequency_minutes,
            settings_created[0],
            settings_created[1],
            settings_created[2],
            utc,
            tz,
            offset,
        ),
    )

    retention_id = str(retention_row[0]) if retention_row else "retention-default"
    retention_created = (
        (str(retention_row[1]), str(retention_row[2]), int(retention_row[3]))
        if retention_row
        else (utc, tz, offset)
    )
    conn.execute(
        "INSERT OR REPLACE INTO retention_policy ("
        "id, retain_raw_payloads, retain_logs_days, created_at_utc, created_at_tz, "
        "created_at_offset_minutes, updated_at_utc, updated_at_tz, updated_at_offset_minutes"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            retention_id,
            1 if settings.retention.retain_raw_payloads else 0,
            settings.retention.retain_logs_days,
            retention_created[0],
            retention_created[1],
            retention_created[2],
            utc,
            tz,
            offset,
        ),
    )

    export_id = str(export_row[0]) if export_row else "export-default"
    export_created = (
        (str(export_row[1]), str(export_row[2]), int(export_row[3]))
        if export_row
        else (utc, tz, offset)
    )
    conn.execute(
        "INSERT OR REPLACE INTO export_defaults ("
        "id, include_raw_payloads, created_at_utc, created_at_tz, created_at_offset_minutes, "
        "updated_at_utc, updated_at_tz, updated_at_offset_minutes"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            export_id,
            1 if settings.export_defaults.include_raw_payloads else 0,
            export_created[0],
            export_created[1],
            export_created[2],
            utc,
            tz,
            offset,
        ),
    )


def _apply_retention_pruning(
    conn: sqlcipher.Connection,
    *,
    retain_raw_payloads: bool,
    retain_logs_days: int,
) -> dict[str, int]:
    """Apply configured retention pruning to raw payloads and audit log rows.

    REQ: FUNC-SET-002, FUNC-AUD-003, SEC-DATA-005
    """
    purged_raw = 0
    if not retain_raw_payloads:
        purged_raw = conn.execute("DELETE FROM provider_raw").rowcount

    purged_audit = _prune_audit_log(conn, retain_logs_days)
    return {"purged_raw_payloads": purged_raw, "purged_audit_rows": purged_audit}


def _register_read_routes(app: FastAPI) -> None:  # noqa: PLR0915
    """Register read/query endpoints on the FastAPI application.

    REQ: FUNC-ACCT-003, FUNC-TXN-001, FUNC-TXN-002, FUNC-TXN-003,
    REQ: FUNC-REP-001, FUNC-REP-002, FUNC-REP-003, FUNC-REP-004, FUNC-REP-005,
    REQ: FUNC-REP-006, FUNC-REP-007, FUNC-REP-008, FUNC-ACCT-004, FUNC-CAT-001,
    REQ: FUNC-SYNC-006, SEC-ACC-004,
    REQ: FUNC-BUD-001, FUNC-BUD-002, FUNC-BUD-003, FUNC-BUD-004,
    REQ: FUNC-EXP-001, FUNC-EXP-002, FUNC-EXP-003,
    REQ: FUNC-SET-001, FUNC-SET-002, FUNC-SET-003, FUNC-SET-004, FUNC-SET-005,
    REQ: FUNC-AUD-001, FUNC-AUD-004

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
        where_clause, params = _build_transaction_filter_clause(
            table_alias="transaction_record",
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            category_id=category_id,
            merchant=merchant,
            amount_min=amount_min,
            amount_max=amount_max,
        )
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
            "account.name, balance_snapshot.date, balance_snapshot.balance, account.currency "
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
                account_name=row[3],
                date=row[4],
                balance=float(row[5]),
                currency=row[6],
            )
            for row in rows
        ]

    @app.get(
        "/export/transactions",
        dependencies=[Depends(require_api_key)],
        response_model=None,
    )
    async def export_transactions(  # noqa: PLR0913
        account_id: str | None = Query(default=None, min_length=1),
        date_from: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
        date_to: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
        category_id: str | None = Query(default=None, min_length=1),
        merchant: str | None = Query(default=None, min_length=1, max_length=128),
        amount_min: float | None = Query(default=None),
        amount_max: float | None = Query(default=None),
        sort_by: Literal["date", "amount"] = Query(default="date"),
        sort_order: Literal["asc", "desc"] = Query(default="desc"),
        include_raw_payloads: bool | None = Query(default=None),
    ) -> Response:
        """Export transactions as CSV using the same filter semantics as /transactions.

        REQ: FUNC-EXP-001, FUNC-EXP-003
        """
        sort_direction = "ASC" if sort_order == "asc" else "DESC"
        sort_field = "tr.date" if sort_by == "date" else "tr.amount"
        where_clause, params = _build_transaction_filter_clause(
            table_alias="tr",
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            category_id=category_id,
            merchant=merchant,
            amount_min=amount_min,
            amount_max=amount_max,
        )
        query = (
            "SELECT tr.id, tr.account_id, account.provider_account_id, account.name, "
            "tr.date, tr.amount, tr.currency, tr.status, tr.merchant_name, tr.display_name, "
            "tr.category_id, tr.notes, tr.is_transfer, tr.is_excluded "
            "FROM transaction_record tr "
            "JOIN account ON account.id = tr.account_id "
            f"{where_clause} "
            f"ORDER BY {sort_field} {sort_direction}, tr.id ASC"
        )

        with _db_connection() as conn:
            include_raw = (
                include_raw_payloads
                if include_raw_payloads is not None
                else _export_default_include_raw_payloads(conn)
            )
            tx_rows = conn.execute(query, params).fetchall()
            tx_ids = [str(row[0]) for row in tx_rows]

            tag_map: dict[str, list[str]] = {tx_id: [] for tx_id in tx_ids}
            split_map: dict[str, list[tuple[str, float, str | None, str | None]]] = {
                tx_id: [] for tx_id in tx_ids
            }
            raw_map: dict[str, list[str]] = {tx_id: [] for tx_id in tx_ids}
            if tx_ids:
                placeholders = ", ".join("?" for _ in tx_ids)
                tag_rows = conn.execute(
                    "SELECT transaction_tag.transaction_id, tag.name "
                    "FROM transaction_tag "
                    "JOIN tag ON tag.id = transaction_tag.tag_id "
                    f"WHERE transaction_tag.transaction_id IN ({placeholders}) "  # noqa: S608
                    "ORDER BY transaction_tag.transaction_id ASC, tag.name ASC",
                    tx_ids,
                ).fetchall()
                split_rows = conn.execute(
                    "SELECT id, transaction_id, amount, category_id, notes "
                    "FROM transaction_split "
                    f"WHERE transaction_id IN ({placeholders}) "  # noqa: S608
                    "ORDER BY transaction_id ASC, rowid ASC",
                    tx_ids,
                ).fetchall()
                for transaction_id, tag_name in tag_rows:
                    tag_map[str(transaction_id)].append(str(tag_name))
                for split_id, transaction_id, amount, split_category_id, split_notes in split_rows:
                    split_map[str(transaction_id)].append(
                        (
                            str(split_id),
                            float(amount),
                            str(split_category_id) if split_category_id is not None else None,
                            str(split_notes) if split_notes is not None else None,
                        )
                    )

                if include_raw:
                    raw_rows = conn.execute(
                        "SELECT transaction_id, raw_payload FROM provider_raw "
                        f"WHERE transaction_id IN ({placeholders}) "  # noqa: S608
                        "ORDER BY transaction_id ASC, created_at_utc ASC",
                        tx_ids,
                    ).fetchall()
                    for transaction_id, raw_payload in raw_rows:
                        raw_map[str(transaction_id)].append(str(raw_payload))

        fieldnames = [
            "transaction_id",
            "account_id",
            "provider_account_id",
            "account_name",
            "date",
            "amount",
            "currency",
            "status",
            "merchant_name",
            "display_name",
            "category_id",
            "notes",
            "is_transfer",
            "is_excluded",
            "tags",
            "split_id",
            "split_amount",
            "split_category_id",
            "split_notes",
        ]
        if include_raw:
            fieldnames.append("raw_provider_payloads")

        csv_rows: list[dict[str, Any]] = []
        for row in tx_rows:
            transaction_id = str(row[0])
            base = {
                "transaction_id": transaction_id,
                "account_id": str(row[1]),
                "provider_account_id": str(row[2]),
                "account_name": str(row[3]),
                "date": str(row[4]),
                "amount": float(row[5]),
                "currency": str(row[6]),
                "status": str(row[7]),
                "merchant_name": str(row[8]) if row[8] is not None else "",
                "display_name": str(row[9]),
                "category_id": str(row[10]) if row[10] is not None else "",
                "notes": str(row[11]) if row[11] is not None else "",
                "is_transfer": bool(row[12]),
                "is_excluded": bool(row[13]),
                "tags": "|".join(tag_map.get(transaction_id, [])),
            }
            raw_payloads = raw_map.get(transaction_id, [])
            if include_raw:
                base["raw_provider_payloads"] = json.dumps(raw_payloads)
            splits = split_map.get(transaction_id, [])
            if splits:
                for split_id, split_amount, split_category_id, split_notes in splits:
                    split_row = dict(base)
                    split_row["split_id"] = split_id
                    split_row["split_amount"] = split_amount
                    split_row["split_category_id"] = split_category_id or ""
                    split_row["split_notes"] = split_notes or ""
                    csv_rows.append(split_row)
            else:
                unsplit_row = dict(base)
                unsplit_row["split_id"] = ""
                unsplit_row["split_amount"] = ""
                unsplit_row["split_category_id"] = ""
                unsplit_row["split_notes"] = ""
                csv_rows.append(unsplit_row)

        return _csv_attachment_response(
            filename=f"transactions-export-{datetime.now().strftime('%Y%m%d')}.csv",
            fieldnames=fieldnames,
            rows=csv_rows,
        )

    @app.get(
        "/export/categories-budgets",
        dependencies=[Depends(require_api_key)],
        response_model=None,
    )
    async def export_categories_budgets(
        format: Literal["csv", "json"] = Query(default="csv"),  # noqa: A002
        month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    ) -> Response | dict[str, list[dict[str, Any]]]:
        """Export categories and budgets in CSV or JSON format.

        REQ: FUNC-EXP-002
        """
        with _db_connection() as conn:
            category_rows = conn.execute(
                "SELECT id, name, parent_id, active FROM category "
                "ORDER BY parent_id NULLS FIRST, name ASC"
            ).fetchall()
            budget_params: list[Any] = []
            budget_where = ""
            if month is not None:
                budget_where = " WHERE budget.month = ?"
                budget_params.append(month)
            budget_rows = conn.execute(
                "SELECT budget.id, budget.month, budget.category_id, budget.amount, category.name "
                "FROM budget "
                "JOIN category ON category.id = budget.category_id"
                f"{budget_where} "
                "ORDER BY budget.month ASC, budget.category_id ASC",
                budget_params,
            ).fetchall()

        categories_payload = [
            {
                "category_id": str(row[0]),
                "name": str(row[1]),
                "parent_id": str(row[2]) if row[2] is not None else None,
                "active": bool(row[3]),
            }
            for row in category_rows
        ]
        budgets_payload = [
            {
                "budget_id": str(row[0]),
                "month": str(row[1]),
                "category_id": str(row[2]),
                "amount": float(row[3]),
                "category_name": str(row[4]),
            }
            for row in budget_rows
        ]
        if format == "json":
            return {
                "categories": categories_payload,
                "budgets": budgets_payload,
            }

        csv_rows: list[dict[str, Any]] = []
        for category in categories_payload:
            csv_rows.append(
                {
                    "record_type": "category",
                    "category_id": category["category_id"],
                    "category_name": category["name"],
                    "parent_id": category["parent_id"] or "",
                    "category_active": category["active"],
                    "budget_id": "",
                    "budget_month": "",
                    "budget_category_id": "",
                    "budget_category_name": "",
                    "budget_amount": "",
                }
            )
        for budget in budgets_payload:
            csv_rows.append(
                {
                    "record_type": "budget",
                    "category_id": "",
                    "category_name": "",
                    "parent_id": "",
                    "category_active": "",
                    "budget_id": budget["budget_id"],
                    "budget_month": budget["month"],
                    "budget_category_id": budget["category_id"],
                    "budget_category_name": budget["category_name"],
                    "budget_amount": budget["amount"],
                }
            )

        suffix = f"-{month}" if month else ""
        return _csv_attachment_response(
            filename=f"categories-budgets-export{suffix}.csv",
            fieldnames=[
                "record_type",
                "category_id",
                "category_name",
                "parent_id",
                "category_active",
                "budget_id",
                "budget_month",
                "budget_category_id",
                "budget_category_name",
                "budget_amount",
            ],
            rows=csv_rows,
        )

    @app.get(
        "/settings",
        response_model=SettingsResponse,
        dependencies=[Depends(require_api_key)],
    )
    async def get_settings() -> SettingsResponse:
        """Return consolidated application settings.

        REQ: FUNC-SET-001, FUNC-SET-002, FUNC-SET-003, FUNC-SET-004, FUNC-SET-005
        """
        with _db_connection() as conn:
            return _load_settings(conn)

    @app.get(
        "/audit-log",
        dependencies=[Depends(require_api_key)],
        response_model=None,
    )
    async def get_audit_log(  # noqa: PLR0913
        format: Literal["json", "csv"] = Query(default="json"),  # noqa: A002
        event_type: str | None = Query(default=None, min_length=1, max_length=128),
        start: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
        end: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
        limit: int = Query(default=50, ge=1, le=_MAX_PAGE_SIZE),
        offset: int = Query(default=0, ge=0),
    ) -> Response | AuditLogResponse:
        """Fetch audit log entries with optional filters and CSV export.

        REQ: FUNC-AUD-001, FUNC-AUD-004
        """
        conditions: list[str] = []
        params: list[Any] = []
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if start:
            conditions.append("timestamp_utc >= ?")
            params.append(f"{start}T00:00:00")
        if end:
            conditions.append("timestamp_utc <= ?")
            params.append(f"{end}T23:59:59")
        where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        query = (
            "SELECT id, event_type, timestamp_utc, timestamp_tz, timestamp_offset_minutes, "
            "redacted_payload "
            "FROM audit_log "
            f"{where_clause} "
            "ORDER BY timestamp_utc DESC, id DESC "
            "LIMIT ? OFFSET ?"
        )

        with _db_connection() as conn:
            rows = conn.execute(query, [*params, limit, offset]).fetchall()
        entries: list[AuditLogEntryResponse] = []
        for row in rows:
            payload: dict[str, Any]
            try:
                parsed = json.loads(str(row[5]))
                payload = parsed if isinstance(parsed, dict) else {"raw": parsed}
            except (TypeError, ValueError):
                payload = {"raw": str(row[5])}
            entries.append(
                AuditLogEntryResponse(
                    id=str(row[0]),
                    event_type=str(row[1]),
                    timestamp_utc=str(row[2]),
                    timestamp_tz=str(row[3]),
                    timestamp_offset_minutes=int(row[4]),
                    redacted_payload=payload,
                )
            )

        if format == "csv":
            return _csv_attachment_response(
                filename="audit-log-export.csv",
                fieldnames=[
                    "id",
                    "event_type",
                    "timestamp_utc",
                    "timestamp_tz",
                    "timestamp_offset_minutes",
                    "redacted_payload",
                ],
                rows=[
                    {
                        "id": entry.id,
                        "event_type": entry.event_type,
                        "timestamp_utc": entry.timestamp_utc,
                        "timestamp_tz": entry.timestamp_tz,
                        "timestamp_offset_minutes": entry.timestamp_offset_minutes,
                        "redacted_payload": json.dumps(entry.redacted_payload, sort_keys=True),
                    }
                    for entry in entries
                ],
            )
        return AuditLogResponse(entries=entries, limit=limit, offset=offset)

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

    @app.get(
        "/budgets",
        response_model=list[BudgetLineResponse],
        dependencies=[Depends(require_api_key)],
    )
    async def get_budgets(
        month: str = Query(pattern=r"^\d{4}-\d{2}$"),
    ) -> list[BudgetLineResponse]:
        """List budget lines with planned/actual/remaining for the given month.

        REQ: FUNC-BUD-001, FUNC-BUD-002, FUNC-BUD-003, FUNC-BUD-004
        """
        with _db_connection() as conn:
            budget_rows = conn.execute(
                "SELECT id, category_id, amount FROM budget WHERE month = ?"
                " ORDER BY category_id ASC",
                (month,),
            ).fetchall()
            actual_rows = conn.execute(_BUDGET_ACTUALS_CTE, (month, month)).fetchall()

        actuals: dict[str, float] = {row[0]: float(row[1]) for row in actual_rows}
        result = []
        for row in budget_rows:
            planned = float(row[2])
            actual = actuals.get(row[1], 0.0)
            remaining = planned - actual
            result.append(
                BudgetLineResponse(
                    budget_id=row[0],
                    category_id=row[1],
                    month=month,
                    planned=planned,
                    actual=actual,
                    remaining=remaining,
                    is_overspent=actual > planned,
                )
            )
        return result

    @app.get(
        "/reports/monthly-overview",
        response_model=MonthlyOverviewResponse,
        dependencies=[Depends(require_api_key)],
    )
    async def get_monthly_overview(
        month: str = Query(pattern=r"^\d{4}-\d{2}$"),
    ) -> MonthlyOverviewResponse:
        """Return monthly overview totals and top spending categories.

        REQ: FUNC-REP-001, FUNC-REP-007, FUNC-REP-008
        """
        start_date, end_date = _month_bounds(month)
        params = (start_date, end_date, start_date, end_date)
        with _db_connection() as conn:
            summary_row = conn.execute(
                _REPORT_LINE_ITEMS_RANGE_CTE
                + "SELECT "
                + "COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0), "
                + "COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) "
                + "FROM line_items",
                params,
            ).fetchone()
            top_rows = conn.execute(
                _REPORT_LINE_ITEMS_RANGE_CTE
                + "SELECT line_items.category_id, category.name, SUM(line_items.amount) AS spend "
                + "FROM line_items "
                + "JOIN category ON category.id = line_items.category_id "
                + "WHERE line_items.amount > 0 "
                + "GROUP BY line_items.category_id, category.name "
                + "ORDER BY spend DESC, line_items.category_id ASC "
                + "LIMIT 5",
                params,
            ).fetchall()

        income = float(summary_row[0]) if summary_row else 0.0
        expenses = float(summary_row[1]) if summary_row else 0.0
        net_savings = income - expenses
        savings_rate = (net_savings / income) if income > 0 else 0.0
        top_categories = [
            TopSpendingCategoryResponse(
                category_id=row[0],
                category_name=row[1],
                amount=float(row[2]),
            )
            for row in top_rows
        ]
        return MonthlyOverviewResponse(
            month=month,
            start_date=start_date,
            end_date=end_date,
            income=income,
            expenses=expenses,
            net_savings=net_savings,
            savings_rate=savings_rate,
            top_categories=top_categories,
            inclusion_note=_REPORT_INCLUSION_NOTE,
            includes_excluded_items=False,
        )

    @app.get(
        "/reports/cash-flow",
        response_model=CashFlowReportResponse,
        dependencies=[Depends(require_api_key)],
    )
    async def get_cash_flow(
        start: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
        end: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
    ) -> CashFlowReportResponse:
        """Return monthly cash-flow metrics over a custom date range.

        REQ: FUNC-REP-003, FUNC-REP-007, FUNC-REP-008
        """
        start_dt, end_dt = _parse_date_range(start, end)
        params = (start, end, start, end)
        with _db_connection() as conn:
            rows = conn.execute(
                _REPORT_LINE_ITEMS_RANGE_CTE
                + "SELECT substr(date, 1, 7) AS month, "
                + "COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0) AS income, "
                + "COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) AS expenses "
                + "FROM line_items "
                + "GROUP BY substr(date, 1, 7) "
                + "ORDER BY month ASC",
                params,
            ).fetchall()

        monthly_totals = {str(row[0]): (float(row[1]), float(row[2])) for row in rows}
        points: list[CashFlowPointResponse] = []
        for month_key in _iter_month_keys(start_dt, end_dt):
            income, expenses = monthly_totals.get(month_key, (0.0, 0.0))
            net_savings = income - expenses
            points.append(
                CashFlowPointResponse(
                    month=month_key,
                    income=income,
                    expenses=expenses,
                    net_savings=net_savings,
                    savings_rate=(net_savings / income) if income > 0 else 0.0,
                )
            )

        return CashFlowReportResponse(
            start_date=start,
            end_date=end,
            points=points,
            inclusion_note=_REPORT_INCLUSION_NOTE,
            includes_excluded_items=False,
        )

    @app.get(
        "/reports/category-trends",
        response_model=CategoryTrendsResponse,
        dependencies=[Depends(require_api_key)],
    )
    async def get_category_trends(
        categories: str = Query(min_length=1),
        months: int = Query(default=12, ge=1, le=24),
        end_month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    ) -> CategoryTrendsResponse:
        """Return monthly category spend trends for one or more categories.

        REQ: FUNC-REP-004, FUNC-REP-007, FUNC-REP-008
        """
        category_ids = _parse_csv_categories(categories)
        with _db_connection() as conn:
            placeholders = ", ".join("?" for _ in category_ids)
            category_rows = conn.execute(
                f"SELECT id, name FROM category WHERE id IN ({placeholders})",  # noqa: S608
                category_ids,
            ).fetchall()
            category_names = {str(row[0]): str(row[1]) for row in category_rows}
            missing = [item for item in category_ids if item not in category_names]
            if missing:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unknown category id(s): {', '.join(missing)}",
                )

            if end_month:
                end_month_start = _parse_month_start(end_month)
            else:
                latest_date = _latest_included_transaction_date(conn)
                end_month_start = date(latest_date.year, latest_date.month, 1)
            start_month_start = _shift_month(end_month_start, -(months - 1))
            start_date = start_month_start.isoformat()
            end_day = calendar.monthrange(end_month_start.year, end_month_start.month)[1]
            end_date = date(end_month_start.year, end_month_start.month, end_day).isoformat()

            trend_rows = conn.execute(
                _REPORT_LINE_ITEMS_RANGE_CTE
                + "SELECT line_items.category_id, substr(line_items.date, 1, 7) AS month, "
                + "SUM(line_items.amount) AS spend "
                + "FROM line_items "
                + f"WHERE line_items.category_id IN ({placeholders}) "
                + "AND line_items.amount > 0 "
                + "GROUP BY line_items.category_id, substr(line_items.date, 1, 7) "
                + "ORDER BY month ASC, line_items.category_id ASC",
                [start_date, end_date, start_date, end_date, *category_ids],
            ).fetchall()

        month_keys = _iter_month_keys(start_month_start, end_month_start)
        per_category_month: dict[str, dict[str, float]] = {
            category_id: {month_key: 0.0 for month_key in month_keys}
            for category_id in category_ids
        }
        for row in trend_rows:
            category_id = str(row[0])
            month_key = str(row[1])
            if category_id in per_category_month and month_key in per_category_month[category_id]:
                per_category_month[category_id][month_key] = float(row[2])

        series = [
            CategoryTrendSeriesResponse(
                category_id=category_id,
                category_name=category_names[category_id],
                points=[
                    CategoryTrendPointResponse(month=month_key, amount=amount)
                    for month_key, amount in per_category_month[category_id].items()
                ],
            )
            for category_id in category_ids
        ]
        return CategoryTrendsResponse(
            start_month=month_keys[0],
            end_month=month_keys[-1],
            months=months,
            series=series,
            inclusion_note=_REPORT_INCLUSION_NOTE,
            includes_excluded_items=False,
        )

    @app.get(
        "/reports/net-worth",
        response_model=NetWorthReportResponse,
        dependencies=[Depends(require_api_key)],
    )
    async def get_net_worth(
        start: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
        end: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
    ) -> NetWorthReportResponse:
        """Return net-worth time series from balance snapshots.

        REQ: FUNC-REP-005, FUNC-REP-008
        """
        _parse_date_range(start, end)
        with _db_connection() as conn:
            rows = conn.execute(
                "SELECT balance_snapshot.date, "
                "COALESCE(SUM(CASE WHEN account.type IN ('credit', 'loan') "
                "                  THEN 0 ELSE balance_snapshot.balance END), 0) AS assets, "
                "COALESCE(SUM(CASE WHEN account.type IN ('credit', 'loan') "
                "                  THEN ABS(balance_snapshot.balance) ELSE 0 END), 0) "
                "AS liabilities "
                "FROM balance_snapshot "
                "JOIN account ON account.id = balance_snapshot.account_id "
                "WHERE balance_snapshot.date >= ? AND balance_snapshot.date <= ? "
                "GROUP BY balance_snapshot.date "
                "ORDER BY balance_snapshot.date ASC",
                (start, end),
            ).fetchall()

        points = [
            NetWorthPointResponse(
                date=str(row[0]),
                assets=float(row[1]),
                liabilities=float(row[2]),
                net_worth=float(row[1]) - float(row[2]),
            )
            for row in rows
        ]
        return NetWorthReportResponse(start_date=start, end_date=end, points=points)


def _register_write_routes(app: FastAPI) -> None:  # noqa: PLR0915
    """Register mutating endpoints for categories, transactions, conflicts, and budgets.

    REQ: FUNC-CAT-002, FUNC-TXN-004, FUNC-TXN-005, FUNC-TXN-006, FUNC-TXN-007,
    REQ: FUNC-TXN-008, FUNC-SYNC-004, FUNC-SYNC-007, SEC-ACC-004,
    REQ: FUNC-BUD-001, FUNC-BKP-001, FUNC-BKP-002, FUNC-BKP-003, FUNC-BKP-004,
    REQ: FUNC-SET-001, FUNC-SET-002, FUNC-SET-003, FUNC-SET-004, FUNC-SET-005

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

    @app.post(
        "/budgets",
        response_model=BudgetLineResponse,
        dependencies=[Depends(require_api_key)],
        status_code=201,
    )
    async def create_budget(request: CreateBudgetRequest) -> BudgetLineResponse:
        """Create a monthly budget line for a leaf category.

        REQ: FUNC-BUD-001
        """
        with _db_connection() as conn:
            _validate_category_assignment(conn, request.category_id)

            existing = conn.execute(
                "SELECT id FROM budget WHERE month = ? AND category_id = ?",
                (request.month, request.category_id),
            ).fetchone()
            if existing is not None:
                raise HTTPException(
                    status_code=409,
                    detail="A budget line already exists for this category and month",
                )

            new_id = str(uuid4())
            conn.execute(
                "INSERT INTO budget (id, month, category_id, amount) VALUES (?, ?, ?, ?)",
                (new_id, request.month, request.category_id, request.amount),
            )
            conn.commit()

            actual_rows = conn.execute(
                _BUDGET_ACTUALS_CTE, (request.month, request.month)
            ).fetchall()

        actuals: dict[str, float] = {row[0]: float(row[1]) for row in actual_rows}
        actual = actuals.get(request.category_id, 0.0)
        planned = request.amount
        remaining = planned - actual
        _log_event(
            logging.INFO,
            "budget_created",
            {"budget_id": new_id, "month": request.month, "category_id": request.category_id},
        )
        return BudgetLineResponse(
            budget_id=new_id,
            category_id=request.category_id,
            month=request.month,
            planned=planned,
            actual=actual,
            remaining=remaining,
            is_overspent=actual > planned,
        )

    @app.delete(
        "/budgets/{budget_id}",
        dependencies=[Depends(require_api_key)],
        status_code=204,
        response_model=None,
    )
    async def delete_budget(
        budget_id: str = FastAPIPath(min_length=1),
    ) -> None:
        """Delete a budget line by ID.

        REQ: FUNC-BUD-001
        """
        with _db_connection() as conn:
            row = conn.execute("SELECT id FROM budget WHERE id = ?", (budget_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Budget not found")
            conn.execute("DELETE FROM budget WHERE id = ?", (budget_id,))
            conn.commit()
        _log_event(logging.INFO, "budget_deleted", {"budget_id": budget_id})

    @app.post(
        "/backup",
        dependencies=[Depends(require_api_key)],
        response_model=None,
    )
    async def create_backup(request: BackupRequest) -> Response:
        """Create encrypted backup of local database and optional secrets store.

        REQ: FUNC-BKP-001, FUNC-BKP-002
        """
        db_path_raw, _ = _read_database_settings()
        db_path = _expand_path(db_path_raw)
        if not db_path.exists():
            raise HTTPException(status_code=404, detail="Database file not found")

        secrets_path_raw = os.environ.get("GODZILLA_SECRETS_PATH")
        secrets_path = _expand_path(secrets_path_raw) if secrets_path_raw else None
        db_bytes = _read_file_bytes(db_path)
        include_secrets = bool(request.include_secrets and secrets_path and secrets_path.exists())
        secrets_bytes = _read_file_bytes(secrets_path) if include_secrets and secrets_path else None
        secrets_name = secrets_path.name if include_secrets and secrets_path else None

        try:
            blob = create_backup_blob(
                db_bytes=db_bytes,
                db_filename=db_path.name,
                passphrase=request.passphrase,
                secrets_bytes=secrets_bytes,
                secrets_filename=secrets_name,
            )
        except BackupError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        _log_event(
            logging.INFO,
            "backup_created",
            {"include_secrets": include_secrets, "size_bytes": len(blob)},
        )
        return Response(
            content=blob,
            media_type="application/octet-stream",
            headers={"Content-Disposition": 'attachment; filename="godzilla-backup.gzbk"'},
        )

    @app.post(
        "/restore",
        dependencies=[Depends(require_api_key)],
        response_model=RestoreResponse,
    )
    async def restore_backup(  # noqa: PLR0912
        passphrase: Annotated[str, Form(min_length=1, max_length=512)],
        backup_file: Annotated[UploadFile, File(...)],
    ) -> RestoreResponse:
        """Restore local state from an encrypted backup file.

        REQ: FUNC-BKP-002, FUNC-BKP-003
        """
        _log_event(logging.INFO, "restore_started", {"filename": backup_file.filename})
        payload_bytes = await backup_file.read()
        try:
            backup = decrypt_backup_blob(blob=payload_bytes, passphrase=passphrase)
        except BackupIntegrityError as exc:
            _log_event(logging.ERROR, "restore_failed", {"reason": "integrity"})
            raise HTTPException(status_code=400, detail="Backup integrity check failed") from exc
        except BackupFormatError as exc:
            _log_event(logging.ERROR, "restore_failed", {"reason": "format"})
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except BackupError as exc:
            _log_event(logging.ERROR, "restore_failed", {"reason": "decrypt"})
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        db_path_raw, db_key = _read_database_settings()
        db_path = _expand_path(db_path_raw)
        old_db_bytes = _read_file_bytes(db_path) if db_path.exists() else None

        secrets_path_raw = os.environ.get("GODZILLA_SECRETS_PATH")
        secrets_path = _expand_path(secrets_path_raw) if secrets_path_raw else None
        old_secrets_bytes = (
            _read_file_bytes(secrets_path) if secrets_path and secrets_path.exists() else None
        )

        try:
            for sidecar_path in _sqlite_related_paths(db_path)[1:]:
                if sidecar_path.exists():
                    sidecar_path.unlink()
            _write_file_bytes_atomic(db_path, backup.db_bytes)

            restored_secrets = False
            if backup.secrets_bytes is not None:
                if secrets_path is None:
                    raise HTTPException(
                        status_code=500,
                        detail="Secrets store is not configured for this restore",
                    )
                for sidecar_path in _sqlite_related_paths(secrets_path)[1:]:
                    if sidecar_path.exists():
                        sidecar_path.unlink()
                _write_file_bytes_atomic(secrets_path, backup.secrets_bytes)
                restored_secrets = True

            schema_version = run_migrations(db_path=str(db_path), db_key=db_key)
        except HTTPException:
            if old_db_bytes is not None:
                _write_file_bytes_atomic(db_path, old_db_bytes)
            if secrets_path and old_secrets_bytes is not None:
                _write_file_bytes_atomic(secrets_path, old_secrets_bytes)
            raise
        except Exception as exc:
            if old_db_bytes is not None:
                _write_file_bytes_atomic(db_path, old_db_bytes)
            if secrets_path and old_secrets_bytes is not None:
                _write_file_bytes_atomic(secrets_path, old_secrets_bytes)
            _log_event(logging.ERROR, "restore_failed", {"reason": str(exc)})
            raise HTTPException(status_code=400, detail="Restore failed") from exc

        _log_event(
            logging.INFO,
            "restore_success",
            {"restored_secrets": restored_secrets, "schema_version": schema_version},
        )
        return RestoreResponse(
            restored_database=True,
            restored_secrets=restored_secrets,
            schema_version=schema_version,
        )

    @app.post(
        "/wipe",
        dependencies=[Depends(require_api_key)],
        response_model=WipeResponse,
    )
    async def wipe_local_data(request: WipeRequest) -> WipeResponse:
        """Wipe local DB and secrets files with best-effort secure deletion.

        REQ: FUNC-BKP-004
        """
        if request.confirm != "WIPE_LOCAL_DATA":
            raise HTTPException(status_code=422, detail="Invalid wipe confirmation token")

        _log_event(logging.WARNING, "wipe_started", {})
        db_path_raw, _ = _read_database_settings()
        db_paths = _sqlite_related_paths(_expand_path(db_path_raw))

        secrets_path_raw = os.environ.get("GODZILLA_SECRETS_PATH")
        secret_paths = (
            _sqlite_related_paths(_expand_path(secrets_path_raw)) if secrets_path_raw else []
        )
        deleted_files: list[str] = []
        missing_files: list[str] = []
        failed_files: list[str] = []
        for path in [*db_paths, *secret_paths]:
            if not path.exists():
                missing_files.append(str(path))
                continue
            if _best_effort_wipe(path):
                deleted_files.append(str(path))
            else:
                failed_files.append(str(path))

        event_name = "wipe_failure" if failed_files else "wipe_success"
        event_level = logging.ERROR if failed_files else logging.WARNING
        logger.log(
            event_level,
            json.dumps(
                redact_sensitive(
                    {
                        "event": event_name,
                        "deleted_count": len(deleted_files),
                        "missing_count": len(missing_files),
                        "failed_count": len(failed_files),
                    }
                ),
                sort_keys=True,
                default=str,
            ),
        )
        return WipeResponse(
            deleted_files=deleted_files,
            missing_files=missing_files,
            failed_files=failed_files,
        )

    @app.put(
        "/settings",
        response_model=SettingsResponse,
        dependencies=[Depends(require_api_key)],
    )
    async def update_settings(request: UpdateSettingsRequest) -> SettingsResponse:
        """Partially update consolidated settings and apply retention pruning.

        REQ: FUNC-SET-001, FUNC-SET-002, FUNC-SET-003, FUNC-SET-004, FUNC-SET-005
        """
        with _db_connection() as conn:
            current = _load_settings(conn)
            updated = current.model_copy(deep=True)

            if request.timezone is not None:
                _validate_timezone_name(request.timezone)
                updated.timezone = request.timezone
            if request.currency is not None:
                updated.currency = request.currency

            if request.retention is not None:
                if request.retention.retain_raw_payloads is not None:
                    updated.retention.retain_raw_payloads = request.retention.retain_raw_payloads
                if request.retention.retain_logs_days is not None:
                    updated.retention.retain_logs_days = request.retention.retain_logs_days

            if request.export_defaults is not None:
                if request.export_defaults.include_raw_payloads is not None:
                    updated.export_defaults.include_raw_payloads = (
                        request.export_defaults.include_raw_payloads
                    )

            if request.security is not None and request.security.auto_lock_minutes is not None:
                updated.security.auto_lock_minutes = request.security.auto_lock_minutes

            if request.sync is not None:
                if request.sync.schedule_enabled is not None:
                    updated.sync.schedule_enabled = request.sync.schedule_enabled
                if request.sync.frequency_minutes is not None:
                    updated.sync.frequency_minutes = request.sync.frequency_minutes

            _upsert_settings_row(conn, updated)
            prune_result = _apply_retention_pruning(
                conn,
                retain_raw_payloads=updated.retention.retain_raw_payloads,
                retain_logs_days=updated.retention.retain_logs_days,
            )
            conn.commit()

        _log_event(
            logging.INFO,
            "settings_updated",
            {
                "timezone": updated.timezone,
                "currency": updated.currency,
                "retain_raw_payloads": updated.retention.retain_raw_payloads,
                "retain_logs_days": updated.retention.retain_logs_days,
                "include_raw_payloads": updated.export_defaults.include_raw_payloads,
                "auto_lock_minutes": updated.security.auto_lock_minutes,
                "sync_schedule_enabled": updated.sync.schedule_enabled,
                "sync_frequency_minutes": updated.sync.frequency_minutes,
                **prune_result,
            },
        )
        return updated


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
    REQ: FUNC-REP-001, FUNC-REP-002, FUNC-REP-003, FUNC-REP-004, FUNC-REP-005,
    REQ: FUNC-REP-006, FUNC-REP-007, FUNC-REP-008,
    REQ: FUNC-EXP-001, FUNC-EXP-002, FUNC-EXP-003,
    REQ: FUNC-BKP-001, FUNC-BKP-002, FUNC-BKP-003, FUNC-BKP-004,
    REQ: FUNC-SET-001, FUNC-SET-002, FUNC-SET-003, FUNC-SET-004, FUNC-SET-005,
    REQ: FUNC-BUD-001, FUNC-BUD-002, FUNC-BUD-003, FUNC-BUD-004, SEC-ACC-004
    """
    app = FastAPI(title="Godzilla Core API", version="0.1.0")
    _register_plaid_routes(app)
    _register_read_routes(app)
    _register_write_routes(app)
    return app


app = create_app()
