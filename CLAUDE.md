# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Policy precedence: `AGENTS.md` is the repository-wide policy source. If any instruction here conflicts with `AGENTS.md`, follow `AGENTS.md`.

## Project Overview

Godzilla is a single-user personal budgeting app. The Python package `godzilla-core` contains all backend services: Plaid integration, an encrypted SQLite database, a local FastAPI sidecar, and CLI scripts.

## Commands

```bash
# Lint (ruff + black + biome lint)
nox -s lint
# or directly:
python3 -m ruff check godzilla_core
python3 -m black --check godzilla_core noxfile.py db_inspect.py
cd ui && npm run lint

# UI format check (non-writing)
cd ui && npm run format:check

# Auto-format
nox -s format
# or directly:
python3 -m black godzilla_core noxfile.py db_inspect.py
cd ui && npm run format

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

# Validate requirement traceability
python3 godzilla_core/scripts/validate_requirement_traceability.py

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

Follow the traceability policy in `AGENTS.md`:
- Add `REQ:` tags in production modules/functions/classes and tests.
- Update `trace/requirements.yml` when requirements are impacted.
- Run `python3 godzilla_core/scripts/validate_requirement_traceability.py` after requirement or traceability changes.
- Use requirement IDs from `docs/requirements/requirements.md`.
- Treat `ACC-*` IDs as acceptance requirements and `TECH-*` IDs as derived technical requirements.
- Use the layered verification taxonomy from `AGENTS.md`: `unit`, `integration`, `component`, `system`, `manual`, `static_analysis`, and `security_review`.
- Do not force acceptance requirements down to unit-only verification. Technical requirements should normally carry the lower-level automated evidence.

## Code Quality

- Line length: 100 characters (ruff + black + biome enforced).
- Google-style docstrings required on all public symbols.
- Ruff rules: `E, F, W, B, PL, D, I` (docstring rules exempt in test files).
- UI linting and formatting is enforced via Biome (`npm run lint`, `npm run format:check`).
- UI Biome rules currently use a pragmatic baseline with specific deferred rules; see `docs/design/developer-tooling.md` for the enforcement plan.
- Parameterized queries only — no string concatenation for SQL.
- All logs must pass through `redact_sensitive`.
- Design docs in `docs/design/` must be updated for non-trivial changes (Markdown + Mermaid).
- Always run commands using virtual environment
- Never install packages in system or user scope

## When to Run Lint and Tests

Run lint (`ruff` + `black --check` + `biome lint`) and the full test suite after any change to **functional** source code. Use `npm run format:check` when you need a non-writing UI format validation pass, and `nox -s format`/`npm run format` when formatting should be applied. For **purely non-functional changes** (for example comments, TODO annotations, or docstrings without logic changes), skip unit tests and run lint only.

## Commits and Progress
As progress is made, mark tasks complete in plan markdown files, and make a local commit following the Conventional Commits convention with the configured git user and e-mail.
