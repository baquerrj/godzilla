# ruff: noqa
"""API layer tests.

REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-003, FUNC-ACCT-004, FUNC-ACCT-005,
REQ: FUNC-ACCT-007, FUNC-SYNC-001, FUNC-TXN-001, FUNC-TXN-002, FUNC-TXN-003,
REQ: FUNC-TXN-004, FUNC-TXN-005, FUNC-TXN-006, FUNC-TXN-007, FUNC-TXN-008,
REQ: FUNC-CAT-001, FUNC-CAT-002, FUNC-SYNC-006, FUNC-SYNC-007,
REQ: FUNC-BUD-001, FUNC-BUD-002, FUNC-BUD-003, FUNC-BUD-004,
REQ: FUNC-REP-001, FUNC-REP-002, FUNC-REP-003, FUNC-REP-004, FUNC-REP-005,
REQ: FUNC-REP-006, FUNC-REP-007, FUNC-REP-008,
REQ: FUNC-AUD-002, SEC-ACC-004, SEC-DATA-002, SEC-DATA-003, SEC-NET-002
"""

from __future__ import annotations

import os
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
import pytest
from sqlcipher3 import dbapi2 as sqlcipher

from godzilla_core.api.app import create_app
from godzilla_core.db.migrations import run_migrations
from godzilla_core.integrations.plaid_client import PlaidApiError, PlaidConfig
from godzilla_core.integrations.plaid_sync import SyncResult
from godzilla_core.scripts.run_api_server import main as run_api_server_main
from godzilla_core.security.redaction import redact_sensitive

pytestmark = pytest.mark.anyio


def _seed_database(db_path: str, db_key: str) -> None:
    """Seed an encrypted test database with deterministic API fixture data.

    REQ: FUNC-ACCT-003, FUNC-ACCT-004, FUNC-REP-006, FUNC-TXN-001
    """
    conn = sqlcipher.connect(db_path)
    conn.execute(f"PRAGMA key = '{db_key}';")
    conn.execute("PRAGMA foreign_keys = ON;")

    conn.execute(
        "INSERT INTO institution ("
        "id, name, plaid_institution_id, created_at_utc, created_at_tz, "
        "created_at_offset_minutes"
        ") VALUES (?, ?, ?, ?, ?, ?)",
        ("inst-1", "Sandbox Bank", "ins_109508", "2026-01-01T00:00:00", "UTC", 0),
    )
    conn.execute(
        "INSERT INTO plaid_item ("
        "id, provider_item_id, institution_id, access_token_ref, status, "
        "last_sync_at_utc, last_sync_at_tz, last_sync_at_offset_minutes, "
        "created_at_utc, created_at_tz, created_at_offset_minutes"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "item-1",
            "item-provider-1",
            "inst-1",
            "plaid_access_token:item-provider-1",
            "linked",
            "2026-01-03T10:00:00",
            "UTC",
            0,
            "2026-01-01T00:00:00",
            "UTC",
            0,
        ),
    )
    conn.execute(
        "INSERT INTO account ("
        "id, item_id, provider_account_id, name, type, subtype, mask, balance, "
        "currency, owner_names, created_at_utc, created_at_tz, created_at_offset_minutes"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "acc-1",
            "item-1",
            "acct-provider-1",
            "Checking",
            "depository",
            "checking",
            "1111",
            321.11,
            "USD",
            '[{"names": ["Alex Example"]}]',
            "2026-01-01T00:00:00",
            "UTC",
            0,
        ),
    )
    conn.execute(
        "INSERT INTO transaction_record ("
        "id, account_id, provider_transaction_id, date, amount, currency, status, "
        "merchant_name, display_name, category_id, is_transfer, is_excluded, notes, "
        "created_at_utc, created_at_tz, created_at_offset_minutes, updated_at_utc, "
        "updated_at_tz, updated_at_offset_minutes"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "txn-1",
            "acc-1",
            "provider-txn-1",
            "2026-01-03",
            15.25,
            "USD",
            "posted",
            "Coffee Shop",
            "Coffee",
            None,
            0,
            0,
            None,
            "2026-01-03T10:00:00",
            "UTC",
            0,
            "2026-01-03T10:00:00",
            "UTC",
            0,
        ),
    )
    conn.execute(
        "INSERT INTO transaction_record ("
        "id, account_id, provider_transaction_id, date, amount, currency, status, "
        "merchant_name, display_name, category_id, is_transfer, is_excluded, notes, "
        "created_at_utc, created_at_tz, created_at_offset_minutes, updated_at_utc, "
        "updated_at_tz, updated_at_offset_minutes"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "txn-2",
            "acc-1",
            "provider-txn-2",
            "2026-01-01",
            250.0,
            "USD",
            "posted",
            "Rent Co",
            "Rent",
            None,
            0,
            0,
            None,
            "2026-01-01T10:00:00",
            "UTC",
            0,
            "2026-01-01T10:00:00",
            "UTC",
            0,
        ),
    )
    conn.execute(
        "INSERT INTO balance_snapshot (id, account_id, date, balance) VALUES (?, ?, ?, ?)",
        ("bal-1", "acc-1", "2026-01-02", 300.0),
    )
    conn.execute(
        "INSERT INTO balance_snapshot (id, account_id, date, balance) VALUES (?, ?, ?, ?)",
        ("bal-2", "acc-1", "2026-01-03", 321.11),
    )
    conn.execute(
        "INSERT INTO sync_state ("
        "id, item_id, plaid_cursor, last_sync_at_utc, last_sync_at_tz, "
        "last_sync_at_offset_minutes, last_sync_status"
        ") VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "sync-1",
            "item-1",
            "cursor-1",
            "2026-01-03T10:00:00",
            "UTC",
            0,
            "success",
        ),
    )
    conn.commit()
    conn.close()


@pytest.fixture
async def api_client() -> httpx.AsyncClient:
    """Provide an authenticated ASGI client bound to a seeded encrypted DB.

    REQ: FUNC-ACCT-003, FUNC-TXN-001, SEC-ACC-004
    """
    env_backup = {
        "GODZILLA_DB_PATH": os.environ.get("GODZILLA_DB_PATH"),
        "GODZILLA_DB_KEY": os.environ.get("GODZILLA_DB_KEY"),
        "GODZILLA_API_TOKEN": os.environ.get("GODZILLA_API_TOKEN"),
    }
    with TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "app.db")
        db_key = "test-db-key"
        run_migrations(db_path=db_path, db_key=db_key)
        _seed_database(db_path, db_key)

        os.environ["GODZILLA_DB_PATH"] = db_path
        os.environ["GODZILLA_DB_KEY"] = db_key
        os.environ["GODZILLA_API_TOKEN"] = "test-api-token"

        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client

    for key, value in env_backup.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_redact_sensitive_redacts_nested_values() -> None:
    """Verify nested sensitive fields are redacted in log payloads.

    REQ: FUNC-AUD-002, SEC-DATA-002
    """
    payload = {
        "access_token": "secret-token",
        "nested": {
            "client_secret": "top-secret",
            "safe": "value",
        },
        "items": [{"api_key": "abc123"}],
    }

    redacted = redact_sensitive(payload)

    assert redacted["access_token"] == "[REDACTED]"
    assert redacted["nested"]["client_secret"] == "[REDACTED]"
    assert redacted["nested"]["safe"] == "value"
    assert redacted["items"][0]["api_key"] == "[REDACTED]"


async def test_auth_required_for_endpoints(api_client: httpx.AsyncClient) -> None:
    """Verify API endpoints reject requests without the API key header.

    REQ: SEC-ACC-004
    """
    response = await api_client.get("/accounts")
    assert response.status_code == 401


async def test_input_validation_rejects_invalid_payloads(api_client: httpx.AsyncClient) -> None:
    """Verify request body validation failures return 422 responses.

    REQ: FUNC-ACCT-007, SEC-DATA-003
    """
    bad_sync = await api_client.post(
        "/plaid/sync",
        json={"item_id": ""},
        headers={"X-API-Key": "test-api-token"},
    )
    assert bad_sync.status_code == 422

    bad_link = await api_client.post(
        "/plaid/link",
        json={"products": []},
        headers={"X-API-Key": "test-api-token"},
    )
    assert bad_link.status_code == 422

    bad_link_products = await api_client.post(
        "/plaid/link",
        json={"products": ["transactions", "balance"]},
        headers={"X-API-Key": "test-api-token"},
    )
    assert bad_link_products.status_code == 422


async def test_get_accounts_returns_expected_payload(api_client: httpx.AsyncClient) -> None:
    """Verify the accounts endpoint returns mapped account read models.

    REQ: FUNC-ACCT-003
    """
    response = await api_client.get("/accounts", headers={"X-API-Key": "test-api-token"})
    assert response.status_code == 200
    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["account_id"] == "acc-1"
    assert payload[0]["provider_account_id"] == "acct-provider-1"
    assert payload[0]["owner_names"][0]["names"][0] == "Alex Example"


async def test_get_transactions_supports_pagination_and_sorting(
    api_client: httpx.AsyncClient,
) -> None:
    """Verify transaction listing supports sorting and pagination query params.

    REQ: FUNC-TXN-001
    """
    response = await api_client.get(
        "/transactions?sort_by=amount&sort_order=asc&limit=1&offset=0",
        headers={"X-API-Key": "test-api-token"},
    )
    assert response.status_code == 200
    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["transaction_id"] == "txn-1"
    assert payload[0]["amount"] == 15.25


async def test_get_balances_returns_snapshots(api_client: httpx.AsyncClient) -> None:
    """Verify balance snapshots are returned in descending date order.

    REQ: FUNC-REP-006
    """
    response = await api_client.get("/balances", headers={"X-API-Key": "test-api-token"})
    assert response.status_code == 200
    payload = response.json()

    assert len(payload) == 2
    assert payload[0]["snapshot_id"] == "bal-2"
    assert payload[0]["balance"] == 321.11


async def test_get_sync_state_returns_item_status(api_client: httpx.AsyncClient) -> None:
    """Verify sync state endpoint returns per-item status metadata.

    REQ: FUNC-ACCT-004
    """
    response = await api_client.get("/sync-state", headers={"X-API-Key": "test-api-token"})
    assert response.status_code == 200
    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["item_id"] == "item-provider-1"
    assert payload[0]["last_sync_status"] == "success"


async def test_plaid_link_endpoint_uses_link_helper(api_client: httpx.AsyncClient) -> None:
    """Verify link endpoint delegates to Plaid helper and returns mapped response.

    REQ: FUNC-ACCT-001, FUNC-ACCT-002
    """
    config = PlaidConfig(
        client_id="cid",
        secret="sec",
        env="sandbox",
        base_url="https://sandbox.plaid.com",
        sandbox_institution_id="ins_109508",
    )
    with (
        patch("godzilla_core.api.app.PlaidConfig.from_env", return_value=config),
        patch("godzilla_core.api.app.PlaidClient") as client_ctor,
        patch("godzilla_core.api.app.store_from_env", return_value=object()) as store_mock,
        patch(
            "godzilla_core.api.app.link_sandbox_item",
            return_value={"item_id": "item-provider-2", "access_token": "token"},
        ) as link_mock,
    ):
        response = await api_client.post(
            "/plaid/link",
            json={"institution_id": "ins_109508", "products": ["transactions", "identity"]},
            headers={"X-API-Key": "test-api-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["item_id"] == "item-provider-2"
    assert payload["institution_id"] == "ins_109508"
    client_ctor.assert_called_once_with(config)
    store_mock.assert_called_once()
    link_mock.assert_called_once()


async def test_plaid_link_persists_item_for_sync_state(api_client: httpx.AsyncClient) -> None:
    """Verify linking an item registers it for sync-state and run-sync workflows.

    REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-004
    """
    config = PlaidConfig(
        client_id="cid",
        secret="sec",
        env="sandbox",
        base_url="https://sandbox.plaid.com",
        sandbox_institution_id="ins_109508",
    )
    with (
        patch("godzilla_core.api.app.PlaidConfig.from_env", return_value=config),
        patch("godzilla_core.api.app.PlaidClient"),
        patch("godzilla_core.api.app.store_from_env", return_value=object()),
        patch(
            "godzilla_core.api.app.link_sandbox_item",
            return_value={"item_id": "item-provider-2", "access_token": "token"},
        ),
    ):
        response = await api_client.post(
            "/plaid/link",
            json={"institution_id": "ins_109508", "products": ["transactions", "identity"]},
            headers={"X-API-Key": "test-api-token"},
        )

    assert response.status_code == 200
    state_response = await api_client.get("/sync-state", headers={"X-API-Key": "test-api-token"})
    assert state_response.status_code == 200

    rows = state_response.json()
    matching = [row for row in rows if row["item_id"] == "item-provider-2"]
    assert len(matching) == 1
    assert matching[0]["institution_id"] == "ins_109508"
    assert matching[0]["status"] == "linked"


async def test_plaid_link_error_response_redacts_logs(api_client: httpx.AsyncClient) -> None:
    """Verify Plaid link errors redact sensitive values in structured logs.

    REQ: FUNC-AUD-002, SEC-DATA-002
    """
    config = PlaidConfig(
        client_id="cid",
        secret="sec",
        env="sandbox",
        base_url="https://sandbox.plaid.com",
        sandbox_institution_id="ins_109508",
    )
    with (
        patch("godzilla_core.api.app.PlaidConfig.from_env", return_value=config),
        patch("godzilla_core.api.app.PlaidClient"),
        patch("godzilla_core.api.app.store_from_env", return_value=object()),
        patch(
            "godzilla_core.api.app.link_sandbox_item",
            side_effect=PlaidApiError("access_token=very-secret", 400),
        ),
        patch("godzilla_core.api.app.logger") as logger_mock,
    ):
        response = await api_client.post(
            "/plaid/link",
            json={"institution_id": "ins_109508", "products": ["transactions"]},
            headers={"X-API-Key": "test-api-token"},
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "Plaid link request failed"
    logged = logger_mock.log.call_args[0][1]
    assert "very-secret" not in logged
    assert "[REDACTED]" in logged


async def test_plaid_sync_endpoint_returns_sync_result(api_client: httpx.AsyncClient) -> None:
    """Verify sync endpoint returns counters from the sync integration result.

    REQ: FUNC-ACCT-005, FUNC-SYNC-001
    """
    with patch(
        "godzilla_core.api.app.sync_item_transactions_and_balances",
        return_value=SyncResult(
            item_id="item-provider-1",
            added=2,
            modified=1,
            removed=0,
            balance_accounts=1,
            cursor="cursor-2",
        ),
    ) as sync_mock:
        response = await api_client.post(
            "/plaid/sync",
            json={"item_id": "item-provider-1", "institution_id": "ins_109508"},
            headers={"X-API-Key": "test-api-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["item_id"] == "item-provider-1"
    assert payload["added"] == 2
    assert payload["cursor"] == "cursor-2"
    sync_mock.assert_called_once_with(
        provider_item_id="item-provider-1",
        plaid_institution_id="ins_109508",
    )


def test_run_api_server_rejects_non_loopback_host() -> None:
    """Verify server CLI rejects non-loopback bind host values.

    REQ: SEC-NET-002
    """
    with patch.object(sys, "argv", ["godzilla-api", "--host", "0.0.0.0"]):
        with pytest.raises(SystemExit, match="Host must be a loopback address"):
            run_api_server_main()


def test_run_api_server_starts_with_loopback_host() -> None:
    """Verify server CLI starts when host is a loopback address.

    REQ: SEC-NET-002
    """
    with (
        patch.object(
            sys,
            "argv",
            ["godzilla-api", "--host", "127.0.0.1", "--port", "8899"],
        ),
        patch("godzilla_core.scripts.run_api_server.uvicorn.run") as run_mock,
    ):
        exit_code = run_api_server_main()

    assert exit_code == 0
    run_mock.assert_called_once_with(
        "godzilla_core.api.app:create_app",
        factory=True,
        host="127.0.0.1",
        port=8899,
    )


# ── Transaction filter tests (Task 6) ────────────────────────────────────────


async def test_get_transactions_filter_by_date_range(api_client: httpx.AsyncClient) -> None:
    """Verify date_from / date_to filters narrow transaction results.

    REQ: FUNC-TXN-002
    """
    response = await api_client.get(
        "/transactions?date_from=2026-01-03&date_to=2026-01-03",
        headers={"X-API-Key": "test-api-token"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["transaction_id"] == "txn-1"


async def test_get_transactions_filter_by_merchant(api_client: httpx.AsyncClient) -> None:
    """Verify merchant text filter matches merchant_name and display_name.

    REQ: FUNC-TXN-002
    """
    response = await api_client.get(
        "/transactions?merchant=Rent",
        headers={"X-API-Key": "test-api-token"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["transaction_id"] == "txn-2"


async def test_get_transactions_filter_by_amount_range(api_client: httpx.AsyncClient) -> None:
    """Verify amount_min / amount_max filters bound results correctly.

    REQ: FUNC-TXN-002
    """
    response = await api_client.get(
        "/transactions?amount_min=100",
        headers={"X-API-Key": "test-api-token"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["transaction_id"] == "txn-2"


async def test_get_transactions_response_includes_category_and_notes(
    api_client: httpx.AsyncClient,
) -> None:
    """Verify TransactionResponse includes category_id and notes fields.

    REQ: FUNC-TXN-001, FUNC-TXN-002
    """
    response = await api_client.get(
        "/transactions",
        headers={"X-API-Key": "test-api-token"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) > 0
    assert "category_id" in payload[0]
    assert "notes" in payload[0]


# ── Transaction detail tests (Task 7) ────────────────────────────────────────


async def test_get_transaction_detail_returns_full_record(api_client: httpx.AsyncClient) -> None:
    """Verify detail endpoint returns all transaction fields.

    REQ: FUNC-TXN-003
    """
    response = await api_client.get(
        "/transactions/txn-1",
        headers={"X-API-Key": "test-api-token"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["transaction_id"] == "txn-1"
    assert payload["display_name"] == "Coffee"
    assert "tags" in payload
    assert "splits" in payload
    assert "raw_provider_payloads" in payload
    assert isinstance(payload["tags"], list)
    assert isinstance(payload["splits"], list)
    assert isinstance(payload["raw_provider_payloads"], list)


async def test_get_transaction_detail_not_found(api_client: httpx.AsyncClient) -> None:
    """Verify detail endpoint returns 404 for unknown transaction ID.

    REQ: FUNC-TXN-003
    """
    response = await api_client.get(
        "/transactions/no-such-id",
        headers={"X-API-Key": "test-api-token"},
    )
    assert response.status_code == 404


# ── Category management tests (Task 8) ───────────────────────────────────────


async def test_get_categories_returns_seeded_taxonomy(api_client: httpx.AsyncClient) -> None:
    """Verify categories endpoint returns the seeded Plaid taxonomy.

    REQ: FUNC-CAT-001
    """
    response = await api_client.get("/categories", headers={"X-API-Key": "test-api-token"})
    assert response.status_code == 200
    payload = response.json()
    ids = {c["category_id"] for c in payload}
    assert "food_and_drink" in ids
    assert "food_and_drink_coffee" in ids
    parent_map = {c["category_id"]: c["parent_id"] for c in payload}
    assert parent_map["food_and_drink_coffee"] == "food_and_drink"
    assert parent_map["food_and_drink"] is None


async def test_create_category_and_patch(api_client: httpx.AsyncClient) -> None:
    """Verify POST /categories creates and PATCH /categories/{id} renames it.

    REQ: FUNC-CAT-002
    """
    create_resp = await api_client.post(
        "/categories",
        json={"name": "My Custom Category", "parent_id": "food_and_drink"},
        headers={"X-API-Key": "test-api-token"},
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["name"] == "My Custom Category"
    assert created["parent_id"] == "food_and_drink"
    assert created["active"] is True
    new_id = created["category_id"]

    patch_resp = await api_client.patch(
        f"/categories/{new_id}",
        json={"name": "Renamed Category"},
        headers={"X-API-Key": "test-api-token"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Renamed Category"


async def test_create_category_duplicate_name_rejected(api_client: httpx.AsyncClient) -> None:
    """Verify duplicate category name under same parent returns 409.

    REQ: FUNC-CAT-002
    """
    await api_client.post(
        "/categories",
        json={"name": "Dup Cat", "parent_id": "income"},
        headers={"X-API-Key": "test-api-token"},
    )
    resp = await api_client.post(
        "/categories",
        json={"name": "Dup Cat", "parent_id": "income"},
        headers={"X-API-Key": "test-api-token"},
    )
    assert resp.status_code == 409


async def test_patch_category_deactivate_rejects_if_assigned(
    api_client: httpx.AsyncClient,
) -> None:
    """Verify deactivating a category assigned to a transaction returns 409.

    REQ: FUNC-CAT-002
    """
    # Assign a leaf category to txn-1 first
    await api_client.patch(
        "/transactions/txn-1",
        json={"category_id": "food_and_drink_coffee"},
        headers={"X-API-Key": "test-api-token"},
    )
    resp = await api_client.patch(
        "/categories/food_and_drink_coffee",
        json={"active": False},
        headers={"X-API-Key": "test-api-token"},
    )
    assert resp.status_code == 409


# ── Transaction mutation tests (Task 9) ──────────────────────────────────────


async def test_patch_transaction_updates_category_and_notes(
    api_client: httpx.AsyncClient,
) -> None:
    """Verify PATCH /transactions/{id} persists category and notes overrides.

    REQ: FUNC-TXN-004, FUNC-TXN-005, FUNC-SYNC-004
    """
    resp = await api_client.patch(
        "/transactions/txn-1",
        json={"category_id": "food_and_drink_coffee", "notes": "Morning latte"},
        headers={"X-API-Key": "test-api-token"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["category_id"] == "food_and_drink_coffee"
    assert body["notes"] == "Morning latte"


async def test_patch_transaction_adds_and_removes_tags(api_client: httpx.AsyncClient) -> None:
    """Verify tag add/remove operations via PATCH /transactions/{id}.

    REQ: FUNC-TXN-005
    """
    resp = await api_client.patch(
        "/transactions/txn-1",
        json={"add_tags": ["coffee", "morning"]},
        headers={"X-API-Key": "test-api-token"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "coffee" in body["tags"]
    assert "morning" in body["tags"]

    resp2 = await api_client.patch(
        "/transactions/txn-1",
        json={"remove_tags": ["morning"]},
        headers={"X-API-Key": "test-api-token"},
    )
    assert resp2.status_code == 200
    assert "morning" not in resp2.json()["tags"]
    assert "coffee" in resp2.json()["tags"]


async def test_patch_transaction_marks_transfer_and_excluded(
    api_client: httpx.AsyncClient,
) -> None:
    """Verify is_transfer and is_excluded flags are persisted.

    REQ: FUNC-TXN-006, FUNC-TXN-007
    """
    resp = await api_client.patch(
        "/transactions/txn-2",
        json={"is_transfer": True, "is_excluded": True},
        headers={"X-API-Key": "test-api-token"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_transfer"] is True
    assert body["is_excluded"] is True


async def test_patch_transaction_parent_category_rejected(api_client: httpx.AsyncClient) -> None:
    """Verify assigning a parent (non-leaf) category returns 422.

    REQ: FUNC-CAT-002, FUNC-TXN-004
    """
    resp = await api_client.patch(
        "/transactions/txn-1",
        json={"category_id": "food_and_drink"},
        headers={"X-API-Key": "test-api-token"},
    )
    assert resp.status_code == 422


async def test_post_transaction_splits_replaces_splits(api_client: httpx.AsyncClient) -> None:
    """Verify POST /transactions/{id}/splits replaces existing splits.

    REQ: FUNC-TXN-008
    """
    resp = await api_client.post(
        "/transactions/txn-1/splits",
        json=[
            {"amount": 10.0, "category_id": "food_and_drink_coffee", "notes": "Coffee"},
            {"amount": 5.25, "notes": "Tip"},
        ],
        headers={"X-API-Key": "test-api-token"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["splits"]) == 2
    assert body["splits"][0]["amount"] == 10.0
    assert body["splits"][1]["amount"] == 5.25


async def test_post_transaction_splits_rejects_wrong_sum(api_client: httpx.AsyncClient) -> None:
    """Verify splits that don't sum to transaction amount return 422.

    REQ: FUNC-TXN-008
    """
    resp = await api_client.post(
        "/transactions/txn-1/splits",
        json=[{"amount": 5.0}, {"amount": 5.0}],
        headers={"X-API-Key": "test-api-token"},
    )
    assert resp.status_code == 422


# ── Conflicts tests (Task 11) ─────────────────────────────────────────────────


async def test_get_conflicts_returns_empty_by_default(api_client: httpx.AsyncClient) -> None:
    """Verify GET /conflicts returns empty list when no conflicts exist.

    REQ: FUNC-SYNC-006
    """
    resp = await api_client.get("/conflicts", headers={"X-API-Key": "test-api-token"})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_resolve_conflict_local_choice(api_client: httpx.AsyncClient) -> None:
    """Verify POST /conflicts/{id}/resolve with 'local' marks conflict resolved.

    REQ: FUNC-SYNC-007
    """
    from sqlcipher3 import dbapi2 as sqlcipher

    db_path = os.environ["GODZILLA_DB_PATH"]
    db_key = os.environ["GODZILLA_DB_KEY"]
    conn = sqlcipher.connect(db_path)
    conn.execute(f"PRAGMA key = '{db_key}';")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(
        "INSERT INTO conflict ("
        "conflict_id, entity_type, entity_id, field_name, local_value, provider_value, "
        "local_updated_at_utc, local_updated_at_tz, local_updated_at_offset_minutes, "
        "provider_updated_at_utc, provider_updated_at_tz, provider_updated_at_offset_minutes, "
        "status"
        ") VALUES (?, 'transaction', 'txn-1', 'display_name', 'Coffee', 'Bean Juice', "
        "'2026-01-03T10:00:00', 'UTC', 0, '2026-01-03T11:00:00', 'UTC', 0, 'open')",
        ("conflict-test-1",),
    )
    conn.commit()
    conn.close()

    resp = await api_client.post(
        "/conflicts/conflict-test-1/resolve",
        json={"resolution_choice": "local"},
        headers={"X-API-Key": "test-api-token"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "resolved"
    assert body["resolution_choice"] == "local"


# ── Report tests (M4) ──────────────────────────────────────────────────────────


def _seed_report_data(db_path: str, db_key: str) -> None:
    """Seed report-oriented fixture data for M4 endpoints.

    Dataset characteristics:
    - Includes income and expense rows across multiple months
    - Includes transfer/excluded/pending rows that must be ignored
    - Includes split rows that must replace parent contribution
    - Includes liability account snapshots for net-worth tests

    REQ: FUNC-REP-001, FUNC-REP-003, FUNC-REP-004, FUNC-REP-005, FUNC-REP-007
    """
    conn = sqlcipher.connect(db_path)
    conn.execute(f"PRAGMA key = '{db_key}';")
    conn.execute("PRAGMA foreign_keys = ON;")

    categories = [
        ("food", "Food", None, 1),
        ("food_coffee", "Coffee", "food", 1),
        ("food_dining", "Dining", "food", 1),
        ("income", "Income", None, 1),
        ("income_salary", "Salary", "income", 1),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO category (id, name, parent_id, active) VALUES (?, ?, ?, ?)",
        categories,
    )

    conn.execute(
        "INSERT OR IGNORE INTO account ("
        "id, item_id, provider_account_id, name, type, subtype, mask, balance, currency, "
        "owner_names, created_at_utc, created_at_tz, created_at_offset_minutes"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "acc-cc-1",
            "item-1",
            "acct-provider-cc-1",
            "Credit Card",
            "credit",
            "credit card",
            "2222",
            -120.0,
            "USD",
            None,
            "2026-01-01T00:00:00",
            "UTC",
            0,
        ),
    )

    txn_insert = (
        "INSERT OR IGNORE INTO transaction_record ("
        "id, account_id, provider_transaction_id, date, amount, currency, status, "
        "merchant_name, display_name, category_id, is_transfer, is_excluded, notes, "
        "created_at_utc, created_at_tz, created_at_offset_minutes, updated_at_utc, "
        "updated_at_tz, updated_at_offset_minutes"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    ts = ("2026-01-10T10:00:00", "UTC", 0)

    txns = [
        (
            "txn-r1",
            "acc-1",
            "prov-r1",
            "2026-01-05",
            30.0,
            "USD",
            "posted",
            "Cafe One",
            "Coffee Jan",
            "food_coffee",
            0,
            0,
            None,
            *ts,
            *ts,
        ),
        (
            "txn-r2",
            "acc-1",
            "prov-r2",
            "2026-01-08",
            70.0,
            "USD",
            "posted",
            "Dining House",
            "Dining Jan",
            "food_dining",
            0,
            0,
            None,
            *ts,
            *ts,
        ),
        (
            "txn-r3",
            "acc-1",
            "prov-r3",
            "2026-01-09",
            -200.0,
            "USD",
            "posted",
            "Employer",
            "Salary Jan",
            "income_salary",
            0,
            0,
            None,
            *ts,
            *ts,
        ),
        (
            "txn-r4",
            "acc-1",
            "prov-r4",
            "2026-01-11",
            40.0,
            "USD",
            "posted",
            "Transfer",
            "Transfer Jan",
            "food_coffee",
            1,
            0,
            None,
            *ts,
            *ts,
        ),
        (
            "txn-r5",
            "acc-1",
            "prov-r5",
            "2026-01-12",
            25.0,
            "USD",
            "posted",
            "Excluded",
            "Excluded Jan",
            "food_dining",
            0,
            1,
            None,
            *ts,
            *ts,
        ),
        (
            "txn-r6",
            "acc-1",
            "prov-r6",
            "2026-01-13",
            10.0,
            "USD",
            "pending",
            "Pending",
            "Pending Jan",
            "food_coffee",
            0,
            0,
            None,
            *ts,
            *ts,
        ),
        (
            "txn-r7",
            "acc-1",
            "prov-r7",
            "2026-01-14",
            60.0,
            "USD",
            "posted",
            "Split Dinner",
            "Split Dinner Jan",
            "food_dining",
            0,
            0,
            None,
            *ts,
            *ts,
        ),
        (
            "txn-r8",
            "acc-1",
            "prov-r8",
            "2025-12-07",
            50.0,
            "USD",
            "posted",
            "Cafe Two",
            "Coffee Dec",
            "food_coffee",
            0,
            0,
            None,
            *ts,
            *ts,
        ),
        (
            "txn-r9",
            "acc-1",
            "prov-r9",
            "2025-12-09",
            -150.0,
            "USD",
            "posted",
            "Employer",
            "Salary Dec",
            "income_salary",
            0,
            0,
            None,
            *ts,
            *ts,
        ),
        (
            "txn-r10",
            "acc-1",
            "prov-r10",
            "2025-11-15",
            20.0,
            "USD",
            "posted",
            "Bistro",
            "Dining Nov",
            "food_dining",
            0,
            0,
            None,
            *ts,
            *ts,
        ),
    ]
    conn.executemany(txn_insert, txns)

    conn.execute(
        "INSERT OR IGNORE INTO transaction_split (id, transaction_id, amount, category_id, notes) "
        "VALUES (?, ?, ?, ?, ?)",
        ("split-r7-1", "txn-r7", 40.0, "food_coffee", None),
    )
    conn.execute(
        "INSERT OR IGNORE INTO transaction_split (id, transaction_id, amount, category_id, notes) "
        "VALUES (?, ?, ?, ?, ?)",
        ("split-r7-2", "txn-r7", 20.0, "food_dining", None),
    )

    snapshots = [
        ("bal-cc-1", "acc-cc-1", "2026-01-02", -100.0),
        ("bal-cc-2", "acc-cc-1", "2026-01-03", -120.0),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO balance_snapshot (id, account_id, date, balance) VALUES (?, ?, ?, ?)",
        snapshots,
    )

    conn.commit()
    conn.close()


@pytest.fixture
async def report_client() -> httpx.AsyncClient:
    """Provide an authenticated ASGI client seeded for report endpoint tests.

    REQ: FUNC-REP-001, FUNC-REP-002, FUNC-REP-003, FUNC-REP-004, FUNC-REP-005,
    REQ: FUNC-REP-007, FUNC-REP-008
    """
    env_backup = {
        "GODZILLA_DB_PATH": os.environ.get("GODZILLA_DB_PATH"),
        "GODZILLA_DB_KEY": os.environ.get("GODZILLA_DB_KEY"),
        "GODZILLA_API_TOKEN": os.environ.get("GODZILLA_API_TOKEN"),
    }
    with TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "report.db")
        db_key = "report-test-key"
        run_migrations(db_path=db_path, db_key=db_key)
        _seed_database(db_path, db_key)
        _seed_report_data(db_path, db_key)

        os.environ["GODZILLA_DB_PATH"] = db_path
        os.environ["GODZILLA_DB_KEY"] = db_key
        os.environ["GODZILLA_API_TOKEN"] = "test-api-token"

        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client

    for key, value in env_backup.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


async def test_reports_monthly_overview_returns_expected_metrics(
    report_client: httpx.AsyncClient,
) -> None:
    """Verify monthly overview totals and top categories for a fixture month.

    REQ: FUNC-REP-001, FUNC-REP-007, FUNC-REP-008
    """
    resp = await report_client.get("/reports/monthly-overview?month=2026-01", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["income"] == pytest.approx(200.0)
    assert body["expenses"] == pytest.approx(160.0)
    assert body["net_savings"] == pytest.approx(40.0)
    assert body["savings_rate"] == pytest.approx(0.2)
    assert body["includes_excluded_items"] is False
    assert body["top_categories"][0]["category_id"] == "food_dining"
    assert body["top_categories"][0]["amount"] == pytest.approx(90.0)
    assert body["top_categories"][1]["category_id"] == "food_coffee"
    assert body["top_categories"][1]["amount"] == pytest.approx(70.0)


async def test_reports_monthly_overview_invalid_month_returns_422(
    report_client: httpx.AsyncClient,
) -> None:
    """Verify invalid month values are rejected for monthly overview.

    REQ: FUNC-REP-008
    """
    resp = await report_client.get("/reports/monthly-overview?month=2026-13", headers=_HEADERS)
    assert resp.status_code == 422


async def test_reports_cash_flow_returns_monthly_points(report_client: httpx.AsyncClient) -> None:
    """Verify cash-flow report aggregates by month with savings rate.

    REQ: FUNC-REP-003, FUNC-REP-008
    """
    resp = await report_client.get(
        "/reports/cash-flow?start=2025-11-01&end=2026-01-31",
        headers=_HEADERS,
    )
    assert resp.status_code == 200
    points = {row["month"]: row for row in resp.json()["points"]}
    assert points["2025-11"]["income"] == pytest.approx(0.0)
    assert points["2025-11"]["expenses"] == pytest.approx(20.0)
    assert points["2025-11"]["net_savings"] == pytest.approx(-20.0)
    assert points["2025-11"]["savings_rate"] == pytest.approx(0.0)
    assert points["2025-12"]["income"] == pytest.approx(150.0)
    assert points["2025-12"]["expenses"] == pytest.approx(50.0)
    assert points["2025-12"]["net_savings"] == pytest.approx(100.0)
    assert points["2025-12"]["savings_rate"] == pytest.approx(100.0 / 150.0)
    assert points["2026-01"]["income"] == pytest.approx(200.0)
    assert points["2026-01"]["expenses"] == pytest.approx(160.0)
    assert points["2026-01"]["net_savings"] == pytest.approx(40.0)
    assert points["2026-01"]["savings_rate"] == pytest.approx(0.2)


async def test_reports_category_trends_supports_multi_category_selection(
    report_client: httpx.AsyncClient,
) -> None:
    """Verify category trends return month-aligned series for selected categories.

    REQ: FUNC-REP-004, FUNC-REP-008
    """
    resp = await report_client.get(
        "/reports/category-trends?categories=food_coffee,food_dining&months=3",
        headers=_HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["start_month"] == "2025-11"
    assert body["end_month"] == "2026-01"
    series_map = {series["category_id"]: series for series in body["series"]}
    coffee = {point["month"]: point["amount"] for point in series_map["food_coffee"]["points"]}
    dining = {point["month"]: point["amount"] for point in series_map["food_dining"]["points"]}
    assert coffee == {"2025-11": 0.0, "2025-12": 50.0, "2026-01": 70.0}
    assert dining == {"2025-11": 20.0, "2025-12": 0.0, "2026-01": 90.0}


async def test_reports_category_trends_respects_end_month(
    report_client: httpx.AsyncClient,
) -> None:
    """Verify category trends can be anchored to a specific end month.

    REQ: FUNC-REP-008
    """
    resp = await report_client.get(
        "/reports/category-trends?categories=food_coffee&months=2&end_month=2025-12",
        headers=_HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["start_month"] == "2025-11"
    assert body["end_month"] == "2025-12"
    points = body["series"][0]["points"]
    assert [point["month"] for point in points] == ["2025-11", "2025-12"]


async def test_reports_category_trends_unknown_category_returns_422(
    report_client: httpx.AsyncClient,
) -> None:
    """Verify category trends reject unknown category ids.

    REQ: FUNC-REP-004
    """
    resp = await report_client.get(
        "/reports/category-trends?categories=food_coffee,nope&months=3",
        headers=_HEADERS,
    )
    assert resp.status_code == 422


async def test_reports_net_worth_returns_assets_liabilities_and_net(
    report_client: httpx.AsyncClient,
) -> None:
    """Verify net worth uses assets minus liabilities over snapshot dates.

    REQ: FUNC-REP-005, FUNC-REP-008
    """
    resp = await report_client.get(
        "/reports/net-worth?start=2026-01-02&end=2026-01-03",
        headers=_HEADERS,
    )
    assert resp.status_code == 200
    points = {row["date"]: row for row in resp.json()["points"]}
    assert points["2026-01-02"]["assets"] == pytest.approx(300.0)
    assert points["2026-01-02"]["liabilities"] == pytest.approx(100.0)
    assert points["2026-01-02"]["net_worth"] == pytest.approx(200.0)
    assert points["2026-01-03"]["assets"] == pytest.approx(321.11)
    assert points["2026-01-03"]["liabilities"] == pytest.approx(120.0)
    assert points["2026-01-03"]["net_worth"] == pytest.approx(201.11)


async def test_reports_and_budgets_share_inclusion_rules(report_client: httpx.AsyncClient) -> None:
    """Verify report expense totals reconcile with budget actual totals.

    REQ: FUNC-REP-007, FUNC-BUD-004
    """
    for category_id in ("food_coffee", "food_dining"):
        create_resp = await report_client.post(
            "/budgets",
            json={"month": "2026-01", "category_id": category_id, "amount": 500.0},
            headers=_HEADERS,
        )
        assert create_resp.status_code == 201

    budgets_resp = await report_client.get("/budgets?month=2026-01", headers=_HEADERS)
    report_resp = await report_client.get(
        "/reports/monthly-overview?month=2026-01",
        headers=_HEADERS,
    )
    assert budgets_resp.status_code == 200
    assert report_resp.status_code == 200
    budgets_total = sum(float(line["actual"]) for line in budgets_resp.json())
    report_expenses = float(report_resp.json()["expenses"])
    assert budgets_total == pytest.approx(report_expenses)


async def test_reports_reject_invalid_date_ranges(report_client: httpx.AsyncClient) -> None:
    """Verify report endpoints reject invalid date ranges and malformed dates.

    REQ: FUNC-REP-008
    """
    reverse = await report_client.get(
        "/reports/cash-flow?start=2026-02-01&end=2026-01-01",
        headers=_HEADERS,
    )
    assert reverse.status_code == 422

    invalid = await report_client.get(
        "/reports/net-worth?start=2026-02-30&end=2026-03-01",
        headers=_HEADERS,
    )
    assert invalid.status_code == 422


async def test_reports_require_api_key(report_client: httpx.AsyncClient) -> None:
    """Verify report endpoints enforce API-key authentication.

    REQ: SEC-ACC-004
    """
    resp = await report_client.get("/reports/monthly-overview?month=2026-01")
    assert resp.status_code == 401


# ── Budget tests (Task 13) ────────────────────────────────────────────────────


def _seed_budget_data(db_path: str, db_key: str) -> None:
    """Seed budget-specific fixture data into the test database.

    Inserts categories and transactions designed to verify each inclusion rule
    independently (transfer, excluded, pending, split-aware).

    Expected actuals for 2026-01:
      food_coffee = 45.00  (12 + 8 + 25 from split)
      food_dining = 20.00  (20 from split)

    REQ: FUNC-BUD-001, FUNC-BUD-002, FUNC-BUD-004
    """
    conn = sqlcipher.connect(db_path)
    conn.execute(f"PRAGMA key = '{db_key}';")
    conn.execute("PRAGMA foreign_keys = ON;")

    conn.execute(
        "INSERT OR IGNORE INTO category (id, name, parent_id, active) VALUES (?, ?, ?, ?)",
        ("food", "Food", None, 1),
    )
    conn.execute(
        "INSERT OR IGNORE INTO category (id, name, parent_id, active) VALUES (?, ?, ?, ?)",
        ("food_coffee", "Coffee", "food", 1),
    )
    conn.execute(
        "INSERT OR IGNORE INTO category (id, name, parent_id, active) VALUES (?, ?, ?, ?)",
        ("food_dining", "Dining", "food", 1),
    )

    _TXN_INSERT = (
        "INSERT OR IGNORE INTO transaction_record ("
        "id, account_id, provider_transaction_id, date, amount, currency, status, "
        "merchant_name, display_name, category_id, is_transfer, is_excluded, notes, "
        "created_at_utc, created_at_tz, created_at_offset_minutes, updated_at_utc, "
        "updated_at_tz, updated_at_offset_minutes"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    _TS = ("2026-01-10T10:00:00", "UTC", 0)

    # txn-b1: counted (posted, not transfer/excluded, no splits)
    conn.execute(
        _TXN_INSERT,
        (
            "txn-b1",
            "acc-1",
            "prov-b1",
            "2026-01-05",
            12.00,
            "USD",
            "posted",
            None,
            "Coffee A",
            "food_coffee",
            0,
            0,
            None,
            *_TS,
            *_TS,
        ),
    )

    # txn-b2: counted (same rules)
    conn.execute(
        _TXN_INSERT,
        (
            "txn-b2",
            "acc-1",
            "prov-b2",
            "2026-01-06",
            8.00,
            "USD",
            "posted",
            None,
            "Coffee B",
            "food_coffee",
            0,
            0,
            None,
            *_TS,
            *_TS,
        ),
    )

    # txn-b3: excluded (is_transfer=1)
    conn.execute(
        _TXN_INSERT,
        (
            "txn-b3",
            "acc-1",
            "prov-b3",
            "2026-01-07",
            50.00,
            "USD",
            "posted",
            None,
            "Transfer",
            "food_coffee",
            1,
            0,
            None,
            *_TS,
            *_TS,
        ),
    )

    # txn-b4: excluded (is_excluded=1)
    conn.execute(
        _TXN_INSERT,
        (
            "txn-b4",
            "acc-1",
            "prov-b4",
            "2026-01-08",
            30.00,
            "USD",
            "posted",
            None,
            "Excluded",
            "food_coffee",
            0,
            1,
            None,
            *_TS,
            *_TS,
        ),
    )

    # txn-b5: excluded (pending status)
    conn.execute(
        _TXN_INSERT,
        (
            "txn-b5",
            "acc-1",
            "prov-b5",
            "2026-01-09",
            5.00,
            "USD",
            "pending",
            None,
            "Pending",
            "food_coffee",
            0,
            0,
            None,
            *_TS,
            *_TS,
        ),
    )

    # txn-b6: has splits → parent ignored; splits contribute
    conn.execute(
        _TXN_INSERT,
        (
            "txn-b6",
            "acc-1",
            "prov-b6",
            "2026-01-10",
            45.00,
            "USD",
            "posted",
            None,
            "Dinner",
            "food_dining",
            0,
            0,
            None,
            *_TS,
            *_TS,
        ),
    )
    conn.execute(
        "INSERT OR IGNORE INTO transaction_split (id, transaction_id, amount, category_id, notes)"
        " VALUES (?, ?, ?, ?, ?)",
        ("split-b6-1", "txn-b6", 25.00, "food_coffee", None),
    )
    conn.execute(
        "INSERT OR IGNORE INTO transaction_split (id, transaction_id, amount, category_id, notes)"
        " VALUES (?, ?, ?, ?, ?)",
        ("split-b6-2", "txn-b6", 20.00, "food_dining", None),
    )

    conn.commit()
    conn.close()


@pytest.fixture
async def budget_client() -> httpx.AsyncClient:
    """Provide an authenticated ASGI client seeded with budget fixture data.

    REQ: FUNC-BUD-001, FUNC-BUD-002, FUNC-BUD-003, FUNC-BUD-004
    """
    env_backup = {
        "GODZILLA_DB_PATH": os.environ.get("GODZILLA_DB_PATH"),
        "GODZILLA_DB_KEY": os.environ.get("GODZILLA_DB_KEY"),
        "GODZILLA_API_TOKEN": os.environ.get("GODZILLA_API_TOKEN"),
    }
    with TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "budget.db")
        db_key = "budget-test-key"
        run_migrations(db_path=db_path, db_key=db_key)
        _seed_database(db_path, db_key)
        _seed_budget_data(db_path, db_key)

        os.environ["GODZILLA_DB_PATH"] = db_path
        os.environ["GODZILLA_DB_KEY"] = db_key
        os.environ["GODZILLA_API_TOKEN"] = "test-api-token"

        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client

    for key, value in env_backup.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


_HEADERS = {"X-API-Key": "test-api-token"}


async def test_get_budgets_returns_empty_for_no_budgets(budget_client: httpx.AsyncClient) -> None:
    """Verify GET /budgets returns empty list when no budgets exist.

    REQ: FUNC-BUD-001
    """
    resp = await budget_client.get("/budgets?month=2026-01", headers=_HEADERS)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_budgets_missing_month_returns_422(budget_client: httpx.AsyncClient) -> None:
    """Verify GET /budgets without month query param returns 422.

    REQ: FUNC-BUD-001
    """
    resp = await budget_client.get("/budgets", headers=_HEADERS)
    assert resp.status_code == 422


async def test_get_budgets_invalid_month_format_returns_422(
    budget_client: httpx.AsyncClient,
) -> None:
    """Verify GET /budgets with malformed month param returns 422.

    REQ: FUNC-BUD-001
    """
    resp = await budget_client.get("/budgets?month=January", headers=_HEADERS)
    assert resp.status_code == 422


async def test_create_budget_returns_201(budget_client: httpx.AsyncClient) -> None:
    """Verify POST /budgets creates a budget line and returns 201 with payload.

    REQ: FUNC-BUD-001, FUNC-BUD-002
    """
    resp = await budget_client.post(
        "/budgets",
        json={"month": "2026-01", "category_id": "food_coffee", "amount": 50.00},
        headers=_HEADERS,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["category_id"] == "food_coffee"
    assert body["month"] == "2026-01"
    assert body["planned"] == 50.00
    assert "budget_id" in body
    assert "actual" in body
    assert "remaining" in body
    assert "is_overspent" in body


async def test_create_budget_duplicate_returns_409(budget_client: httpx.AsyncClient) -> None:
    """Verify creating a duplicate budget line returns 409.

    REQ: FUNC-BUD-001
    """
    payload = {"month": "2026-02", "category_id": "food_coffee", "amount": 40.00}
    await budget_client.post("/budgets", json=payload, headers=_HEADERS)
    resp = await budget_client.post("/budgets", json=payload, headers=_HEADERS)
    assert resp.status_code == 409


async def test_create_budget_parent_category_returns_422(budget_client: httpx.AsyncClient) -> None:
    """Verify creating a budget for a parent (non-leaf) category returns 422.

    REQ: FUNC-BUD-001
    """
    resp = await budget_client.post(
        "/budgets",
        json={"month": "2026-01", "category_id": "food", "amount": 100.00},
        headers=_HEADERS,
    )
    assert resp.status_code == 422


async def test_create_budget_unknown_category_returns_422(budget_client: httpx.AsyncClient) -> None:
    """Verify creating a budget for an unknown category returns 422.

    REQ: FUNC-BUD-001
    """
    resp = await budget_client.post(
        "/budgets",
        json={"month": "2026-01", "category_id": "no_such_cat", "amount": 50.00},
        headers=_HEADERS,
    )
    assert resp.status_code == 422


async def test_create_budget_negative_amount_returns_422(budget_client: httpx.AsyncClient) -> None:
    """Verify creating a budget with amount <= 0 returns 422.

    REQ: FUNC-BUD-001
    """
    resp = await budget_client.post(
        "/budgets",
        json={"month": "2026-01", "category_id": "food_coffee", "amount": -5.00},
        headers=_HEADERS,
    )
    assert resp.status_code == 422


async def test_get_budgets_computes_actuals_correctly(budget_client: httpx.AsyncClient) -> None:
    """Verify GET /budgets returns correct actual values per inclusion rules.

    food_coffee actual = 12 + 8 + 25 (split) = 45.00
    food_dining actual = 20 (split) = 20.00

    REQ: FUNC-BUD-002, FUNC-BUD-004
    """
    await budget_client.post(
        "/budgets",
        json={"month": "2026-01", "category_id": "food_coffee", "amount": 60.00},
        headers=_HEADERS,
    )
    await budget_client.post(
        "/budgets",
        json={"month": "2026-01", "category_id": "food_dining", "amount": 30.00},
        headers=_HEADERS,
    )
    resp = await budget_client.get("/budgets?month=2026-01", headers=_HEADERS)
    assert resp.status_code == 200
    lines = {line["category_id"]: line for line in resp.json()}
    assert lines["food_coffee"]["actual"] == pytest.approx(45.00)
    assert lines["food_dining"]["actual"] == pytest.approx(20.00)


async def test_get_budgets_overspent_flagged(budget_client: httpx.AsyncClient) -> None:
    """Verify is_overspent is True when actual > planned.

    REQ: FUNC-BUD-002, FUNC-BUD-003
    """
    await budget_client.post(
        "/budgets",
        json={"month": "2026-01", "category_id": "food_coffee", "amount": 20.00},
        headers=_HEADERS,
    )
    resp = await budget_client.get("/budgets?month=2026-01", headers=_HEADERS)
    assert resp.status_code == 200
    line = resp.json()[0]
    assert line["is_overspent"] is True
    assert line["remaining"] == pytest.approx(20.00 - 45.00)


async def test_get_budgets_excludes_transfers_pending_excluded(
    budget_client: httpx.AsyncClient,
) -> None:
    """Verify transfers, excluded, and pending txns are excluded from actuals.

    txn-b3 (transfer), txn-b4 (excluded), txn-b5 (pending) must not count.
    Only txn-b1 (12) and txn-b2 (8) + split portion (25) = 45 should count.

    REQ: FUNC-BUD-004
    """
    await budget_client.post(
        "/budgets",
        json={"month": "2026-01", "category_id": "food_coffee", "amount": 200.00},
        headers=_HEADERS,
    )
    resp = await budget_client.get("/budgets?month=2026-01", headers=_HEADERS)
    assert resp.status_code == 200
    line = next(l for l in resp.json() if l["category_id"] == "food_coffee")
    # Must not include txn-b3 (50), txn-b4 (30), txn-b5 (5)
    assert line["actual"] == pytest.approx(45.00)


async def test_get_budgets_uses_splits_not_parent(budget_client: httpx.AsyncClient) -> None:
    """Verify that when splits exist the parent txn amount/category is ignored.

    txn-b6 has category food_dining, amount 45.00 — but has splits, so the
    parent row is excluded. Only the split rows contribute (25→coffee, 20→dining).

    REQ: FUNC-BUD-004
    """
    await budget_client.post(
        "/budgets",
        json={"month": "2026-01", "category_id": "food_dining", "amount": 100.00},
        headers=_HEADERS,
    )
    resp = await budget_client.get("/budgets?month=2026-01", headers=_HEADERS)
    assert resp.status_code == 200
    line = next(l for l in resp.json() if l["category_id"] == "food_dining")
    # Parent amount (45) must NOT count; only split-b6-2 (20) counts.
    assert line["actual"] == pytest.approx(20.00)


async def test_get_budgets_filters_by_month(budget_client: httpx.AsyncClient) -> None:
    """Verify GET /budgets only returns budgets for the requested month.

    REQ: FUNC-BUD-001
    """
    await budget_client.post(
        "/budgets",
        json={"month": "2026-01", "category_id": "food_coffee", "amount": 50.00},
        headers=_HEADERS,
    )
    await budget_client.post(
        "/budgets",
        json={"month": "2026-02", "category_id": "food_coffee", "amount": 60.00},
        headers=_HEADERS,
    )
    resp = await budget_client.get("/budgets?month=2026-01", headers=_HEADERS)
    assert resp.status_code == 200
    months = {line["month"] for line in resp.json()}
    assert months == {"2026-01"}


async def test_delete_budget_returns_204(budget_client: httpx.AsyncClient) -> None:
    """Verify DELETE /budgets/{id} returns 204 and removes the budget line.

    REQ: FUNC-BUD-001
    """
    create_resp = await budget_client.post(
        "/budgets",
        json={"month": "2026-03", "category_id": "food_coffee", "amount": 55.00},
        headers=_HEADERS,
    )
    assert create_resp.status_code == 201
    budget_id = create_resp.json()["budget_id"]

    del_resp = await budget_client.delete(f"/budgets/{budget_id}", headers=_HEADERS)
    assert del_resp.status_code == 204

    list_resp = await budget_client.get("/budgets?month=2026-03", headers=_HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json() == []


async def test_delete_budget_not_found_returns_404(budget_client: httpx.AsyncClient) -> None:
    """Verify DELETE /budgets/{id} returns 404 for unknown ID.

    REQ: FUNC-BUD-001
    """
    resp = await budget_client.delete("/budgets/no-such-budget-id", headers=_HEADERS)
    assert resp.status_code == 404
