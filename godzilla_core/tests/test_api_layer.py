# ruff: noqa
"""API layer tests.

REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-003, FUNC-ACCT-004, FUNC-ACCT-005,
REQ: FUNC-ACCT-007, FUNC-SYNC-001, FUNC-TXN-001, FUNC-REP-006, FUNC-AUD-002,
REQ: SEC-ACC-004, SEC-DATA-002, SEC-DATA-003, SEC-NET-002
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
    response = await api_client.get("/accounts")
    assert response.status_code == 401


async def test_input_validation_rejects_invalid_payloads(api_client: httpx.AsyncClient) -> None:
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


async def test_get_accounts_returns_expected_payload(api_client: httpx.AsyncClient) -> None:
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
    response = await api_client.get("/balances", headers={"X-API-Key": "test-api-token"})
    assert response.status_code == 200
    payload = response.json()

    assert len(payload) == 2
    assert payload[0]["snapshot_id"] == "bal-2"
    assert payload[0]["balance"] == 321.11


async def test_get_sync_state_returns_item_status(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/sync-state", headers={"X-API-Key": "test-api-token"})
    assert response.status_code == 200
    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["item_id"] == "item-provider-1"
    assert payload[0]["last_sync_status"] == "success"


async def test_plaid_link_endpoint_uses_link_helper(api_client: httpx.AsyncClient) -> None:
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


async def test_plaid_link_error_response_redacts_logs(api_client: httpx.AsyncClient) -> None:
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
    with patch.object(sys, "argv", ["godzilla-api", "--host", "0.0.0.0"]):
        with pytest.raises(SystemExit, match="Host must be a loopback address"):
            run_api_server_main()


def test_run_api_server_starts_with_loopback_host() -> None:
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
