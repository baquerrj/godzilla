# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Godzilla is a single-user personal budgeting app. The Python package `godzilla-core` contains all backend services: Plaid integration, an encrypted SQLite database, a local FastAPI sidecar, and CLI scripts.

## Commands

```bash
# Lint (ruff + black)
nox -s lint
# or directly:
python3 -m ruff check godzilla_core
python3 -m black --check godzilla_core noxfile.py db_inspect.py

# Auto-format
nox -s format

# Run all tests
nox -s tests
# or directly:
python3 -m pytest

# Run a single test file
python3 -m pytest godzilla_core/tests/test_plaid_sync.py

# Run a single test by name
python3 -m pytest godzilla_core/tests/test_api_layer.py::test_get_accounts_returns_expected_payload

# Build wheel
nox -s build

# Run database migrations
GODZILLA_DB_PATH=<path> GODZILLA_DB_KEY=<key> migrations

# Start the API server (loopback only, default port 8787)
GODZILLA_DB_PATH=<path> GODZILLA_DB_KEY=<key> GODZILLA_API_TOKEN=<token> godzilla-api

# Link a Plaid sandbox item
PLAID_CLIENT_ID=<id> PLAID_SECRET=<secret> PLAID_ENV=sandbox \
  GODZILLA_SECRETS_PATH=<path> GODZILLA_SECRETS_KEY=<key> link-sandbox-item

# Sync a linked Plaid item
PLAID_CLIENT_ID=<id> PLAID_SECRET=<secret> ... sync-plaid-item --item-id <item_id>
```

## Architecture

```
godzilla_core/
  api/          FastAPI application (routes, Pydantic models, auth)
  db/           Migration runner for the encrypted SQLCipher database
  integrations/ Plaid HTTP client + incremental sync ingestion logic
  scripts/      CLI entry points (link item, sync item, run API server)
  security/     Encrypted secrets store (SecretStore) and log redaction
  util/         Local timestamp helpers (timezone-aware metadata)
  tests/        pytest test suite
migrations/     Versioned SQL files (NNNN_<name>.sql)
trace/          requirements.yml — bidirectional traceability index
docs/design/    Markdown design docs with Mermaid diagrams
```

### Key architectural patterns

**Two encrypted SQLCipher databases:**
- Main DB (`GODZILLA_DB_PATH` / `GODZILLA_DB_KEY`): all financial data (accounts, transactions, balances, budgets, etc.) managed via versioned SQL migrations in `migrations/`.
- Secrets DB (`GODZILLA_SECRETS_PATH` / `GODZILLA_SECRETS_KEY`): Plaid access tokens stored by `SecretStore` in `godzilla_core/security/secrets.py`. Access tokens are stored under the key `plaid_access_token:<provider_item_id>`.

**Plaid integration flow:**
1. `link_sandbox_item` (plaid_client.py) — creates sandbox public token → exchanges for access token → stores in SecretStore.
2. `sync_item_transactions_and_balances` (plaid_sync.py) — reads access token from SecretStore → calls Plaid balance + transactions/sync API → upserts accounts, balance snapshots, and transactions into the main DB with cursor-based incremental sync.

**API layer** (`godzilla_core/api/app.py`): FastAPI sidecar exposing read endpoints (`/accounts`, `/transactions`, `/balances`, `/sync-state`) and write endpoints (`/plaid/link`, `/plaid/sync`). All routes require the `X-API-Key` header matched against `GODZILLA_API_TOKEN`. The server only binds to loopback addresses.

**Structured logging with redaction:** All API log events go through `redact_sensitive` before emission (`_log_event` in app.py). Never log raw tokens, keys, or account data.

## Required Environment Variables

| Variable | Purpose |
|---|---|
| `GODZILLA_DB_PATH` | Path to the main encrypted database |
| `GODZILLA_DB_KEY` | Encryption key for the main database |
| `GODZILLA_SECRETS_PATH` | Path to the secrets encrypted database |
| `GODZILLA_SECRETS_KEY` | Encryption key for the secrets database |
| `GODZILLA_API_TOKEN` | Bearer token for API authentication |
| `PLAID_CLIENT_ID` | Plaid API client ID |
| `PLAID_SECRET` | Plaid API secret |
| `PLAID_ENV` | Plaid environment (`sandbox`, `development`, `production`) |

## Traceability Requirements

Every production function/class **must** include `REQ: <REQ-ID>` tags in its docstring or module header. Every test **must** also include `REQ:` tags. After any change, update `trace/requirements.yml` with new `code_refs` and `test_refs`.

Requirement IDs follow the pattern: `SYS-NNN`, `FUNC-<DOMAIN>-NNN`, `SEC-<DOMAIN>-NNN`. See `docs/product-requirements-document.md` for the full list.

## Code Quality

- Line length: 100 characters (ruff + black enforced).
- Google-style docstrings required on all public symbols.
- Ruff rules: `E, F, W, B, PL, D, I` (docstring rules exempt in test files).
- Parameterized queries only — no string concatenation for SQL.
- All logs must pass through `redact_sensitive`.
- Design docs in `docs/design/` must be updated for non-trivial changes (Markdown + Mermaid).

## When to Run Lint and Tests

Run lint (`ruff` + `black --check`) and the full test suite after any change to **functional** source code. For **purely non-functional changes** (e.g. adding or editing comments, TODO annotations, or docstrings without altering logic), skip running the unit tests — only run lint to verify formatting.
