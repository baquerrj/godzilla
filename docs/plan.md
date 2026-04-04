# MVP Plan

## MVP Definition

The canonical MVP definition is split across:
- [Vision](vision.md)
- [Architecture](design/architecture-overview.md)
- [Requirements](requirements/requirements.md)

Use this file only as the execution tracker for milestone and verification work.

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

---

## M1 — Plaid Link + account listing + secure token storage + manual sync

- [x] **1. Editable install + smoke test validation**
  Confirm `pip install -e ".[dev]"` and all four console scripts (`migrations`,
  `link-sandbox-item`, `sync-plaid-item`, `godzilla-api`) work end-to-end.

- [x] **2. Improve test coverage for existing modules**
  Target modules with low/zero coverage:
  - `scripts/link_sandbox_item.py` — 0%
  - `scripts/sync_plaid_item.py` — 0%
  - `security/secrets.py` — 24%
  - `integrations/plaid_sync.py` — 20%
  - `integrations/plaid_client.py` — 37%
  - `db/migrations.py` — 26%

- [x] **3. Frontend scaffold (Tauri v2 + React + Vite)**
  Initialize Tauri v2 project, pin Node.js v24 LTS, configure Vite dev proxy to
  forward `/api/*` → `127.0.0.1:8787`, generate per-install self-signed cert and
  configure Tauri to pin it.

- [x] **4. Typed frontend API client module**
  TypeScript client for all 6 endpoints with loading/error/success state handling.

- [x] **5. MVP UI — accounts + sync flow**
  "Connect sandbox account", "Run sync", accounts/transactions/balances tables,
  sync status panel.

---

## M2 — Transaction list/detail + categorization + search/filters

- [x] **6. Transaction search & filter API** (`FUNC-TXN-002`)
  Extend `GET /transactions` with date range, account, category, merchant text,
  and amount range filters.

- [x] **7. Transaction detail endpoint** (`FUNC-TXN-003`)
  `GET /transactions/{id}` with full detail including read-only raw provider metadata.

- [x] **8. Category management endpoints** (`FUNC-CAT-001`, `FUNC-CAT-002`)
  `GET/POST /categories`, `PATCH /categories/{id}` (rename/deactivate). Enforce
  leaf-only assignment and block deactivated categories.

- [x] **9. Transaction mutation endpoints** (`FUNC-TXN-004`–`FUNC-TXN-008`)
  `PATCH /transactions/{id}` (category, notes, tags, is_transfer, is_excluded),
  `POST /transactions/{id}/splits`. Write to `transaction_override` for provenance.

- [x] **10. Provider category mapping on sync** (`FUNC-CAT-003`)
  Map Plaid category signals to local hierarchy as a suggested default during ingestion.

- [x] **11. Conflict detection + resolution endpoints** (`FUNC-SYNC-005`–`FUNC-SYNC-007`)
  Detect field-level conflicts during sync, write to `conflict` table.
  `GET /conflicts`, `POST /conflicts/{id}/resolve`.

- [x] **12. M2 UI**
  Transaction list with search/filter, detail view, category picker,
  mark transfer/exclude/split, conflict resolution queue.

---

## M3 — Budgets + monthly view + overspend drill-down

- [x] **13. Budget endpoints** (`FUNC-BUD-001`–`FUNC-BUD-004`)
  - [x] 13a. Pydantic models: `CreateBudgetRequest`, `BudgetLineResponse`
  - [x] 13b. `_BUDGET_ACTUALS_CTE` module-level SQL constant
  - [x] 13c. `GET /budgets?month=YYYY-MM` in `_register_read_routes`
  - [x] 13d. `POST /budgets` and `DELETE /budgets/{id}` in `_register_write_routes`
  - [x] 13e. Backend tests (15 tests) + `_seed_budget_data` helper
  - [x] 13f. Lint + full test suite green → commit

- [x] **14. M3 UI**
  - [x] 14a. TypeScript types: `BudgetLine`, `CreateBudgetRequest`, `GetBudgetsParams`
  - [x] 14b. API client methods: `getBudgets`, `createBudget`, `deleteBudget`; 204 handling
  - [x] 14c. `BudgetPanel` component
  - [x] 14d. `App.tsx` integration + `handleBudgetDrillDown`
  - [x] 14e. CSS additions
  - [x] 14f. Frontend tests (8 tests in `BudgetPanel.test.tsx`, smoke in `App.test.tsx`)
  - [x] 14g. Traceability + design doc + mark plan complete → commit

---

## M4 — Dashboards/reports + net worth snapshots

- [x] **15. Dashboard/report endpoints** (`FUNC-REP-001`–`FUNC-REP-008`)
  - [x] 15a. Add shared report SQL helpers that reuse M3 inclusion rules
    (posted-only, exclude transfer/excluded, split-aware) for all
    transaction-derived report metrics (`FUNC-REP-007`).
  - [x] 15b. Add Pydantic request/response models for monthly overview, cash
    flow, category trends, and net worth.
  - [x] 15c. Implement `GET /reports/monthly-overview?month=YYYY-MM`
    (`FUNC-REP-001`, `FUNC-REP-008`).
  - [x] 15d. Implement `GET /reports/cash-flow?start=YYYY-MM-DD&end=YYYY-MM-DD`
    (`FUNC-REP-003`, `FUNC-REP-008`).
  - [x] 15e. Implement
    `GET /reports/category-trends?categories=<csv>&months=<int>`
    (`FUNC-REP-004`, `FUNC-REP-008`).
  - [x] 15f. Implement `GET /reports/net-worth?start=YYYY-MM-DD&end=YYYY-MM-DD`
    with assets/liabilities/net (`FUNC-REP-005`).
  - [x] 15g. Add backend tests for math correctness, inclusion consistency,
    auth, and validation.
  - [x] 15h. Update traceability/docs: `trace/requirements.yml`,
    `docs/design/reports-dashboard.md`, `docs/test-strategy/m4-reports.md`.

- [x] **16. M4 UI** (`FUNC-REP-001`–`FUNC-REP-008`)
  - [x] 16a. Add TypeScript report types and API client methods.
  - [x] 16b. Add `ReportsPanel` with unified month + custom range controls
    driving all report widgets (`FUNC-REP-008`).
  - [x] 16c. Add monthly overview cards + top-category table with drill-down
    (`FUNC-REP-001`, `FUNC-REP-002`).
  - [x] 16d. Add cash-flow chart + category-trends chart with drill-down from
    selected points/categories (`FUNC-REP-002`, `FUNC-REP-003`,
    `FUNC-REP-004`).
  - [x] 16e. Add net-worth chart (assets, liabilities, net) for selected range
    (`FUNC-REP-005`).
  - [x] 16f. Add inclusion-rule labeling on transaction-derived metrics
    (`FUNC-REP-007`).
  - [x] 16g. Integrate drill-down into existing `App.tsx` transaction filter
    state.
  - [x] 16h. Add frontend tests for rendering, navigation, and drill-down.

- [ ] **M4 verification checklist (step-by-step to run)**
  - [x] 1. Activate env and run quality gates:
    `source venv/bin/activate && nox -s lint && nox -s tests && nox -s build`
  - [x] 2. Run frontend tests/build:
    `cd ui && npm test && npm run build`
  - [ ] 3. Start API against a fresh DB:
    `export GODZILLA_DB_PATH=/tmp/m4-test.db`
    `export GODZILLA_DB_KEY=m4-test-key`
    `export GODZILLA_API_TOKEN=m4-test-token`
    `source venv/bin/activate && migrations && godzilla-api`
  - [x] 4. Seed fresh DB with at least one linked/synced sandbox item:
    `curl -s -X POST -H "X-API-Key: m4-test-token" -H "Content-Type: application/json" -d '{}' "http://127.0.0.1:8787/plaid/link"`
    Copy `item_id` from response, then:
    `curl -s -X POST -H "X-API-Key: m4-test-token" -H "Content-Type: application/json" -d '{"item_id":"<item_id>"}' "http://127.0.0.1:8787/plaid/sync"`
  - [x] 5. Verify monthly overview endpoint:
    `curl -s -H "X-API-Key: m4-test-token" "http://127.0.0.1:8787/reports/monthly-overview?month=2026-01"`
    Expect HTTP 200 and keys: `income`, `expenses`, `net_savings`,
    `savings_rate`, `top_categories`.
  - [x] 6. Verify cash-flow endpoint:
    `curl -s -H "X-API-Key: m4-test-token" "http://127.0.0.1:8787/reports/cash-flow?start=2025-01-01&end=2026-01-31"`
    Expect HTTP 200 monthly series with each point containing `month`, `income`,
    `expenses`, `net_savings`, `savings_rate`. For an unsynced/empty DB, `points: []`
    is expected.
  - [x] 7. Discover valid category IDs for this DB:
    `curl -s -H "X-API-Key: m4-test-token" "http://127.0.0.1:8787/categories"`
    Choose two active leaf `category_id` values from the response.
  - [x] 8. Verify category-trends endpoint:
    `curl -s -H "X-API-Key: m4-test-token" "http://127.0.0.1:8787/reports/category-trends?categories=<cat_id_1>,<cat_id_2>&months=12"`
    Expect HTTP 200 with one series per requested category and <= 12 monthly
    points each. If IDs do not exist, expect HTTP 422 with `Unknown category id(s)`.
  - [x] 9. Verify net-worth endpoint:
    `curl -s -H "X-API-Key: m4-test-token" "http://127.0.0.1:8787/reports/net-worth?start=2025-01-01&end=2026-01-31"`
    Expect HTTP 200 points where `net_worth = assets - liabilities`.
  - [x] 10. Verify negative API cases:
    missing token => HTTP 401 on all `/reports/*`;
    bad dates/month/months => HTTP 422.
  - [x] 11. Launch UI (`cd ui && npm run dev`) and verify:
    reports panel renders, month/range changes refresh all report widgets, and
    inclusion-rule label is visible.
  - [x] 12. Verify drill-down UX:
    click monthly overview/top-category/cash-flow/category-trend metrics and
    confirm transaction filters auto-populate with matching
    dates/category/amount-direction.
  - [x] 13. Verify traceability completion:
    `trace/requirements.yml` has populated `code_refs` + `test_refs` for
    `FUNC-REP-001..008`.
  - [x] 14. Mark M4 tasks complete and commit with Conventional Commit.

---

## M5 — Export + encrypted backup/restore + settings + audit logging hardening

- [x] **17. Export endpoints** (`FUNC-EXP-001`–`FUNC-EXP-003`)
  - [x] 17a. Shared export helpers (CSV attachment, transaction filter reuse from `/transactions`).
  - [x] 17b. `GET /export/transactions` (filter-aware CSV, split-row expansion, tags/overrides/flags).
  - [x] 17c. `GET /export/categories-budgets` (`format=csv|json`, optional `month=YYYY-MM`).
  - [x] 17d. Backend tests for filter behavior, CSV/JSON shape, split behavior, defaults, auth/validation.

- [x] **18. Encrypted backup/restore + wipe** (`FUNC-BKP-001`–`FUNC-BKP-004`)
  - [x] 18a. Added `godzilla_core/security/backup.py` with Scrypt + AESGCM envelope.
  - [x] 18b. Added `cryptography>=43` dependency.
  - [x] 18c. `POST /backup` (encrypted downloadable blob).
  - [x] 18d. `POST /restore` (multipart upload, integrity checks, atomic replace + migrations).
  - [x] 18e. `POST /wipe` (DB + sidecars + secrets best-effort wipe).
  - [x] 18f. Backend tests for encrypted output, tamper failure, restore correctness, wipe behavior.

- [x] **19. Settings endpoints** (`FUNC-SET-001`–`FUNC-SET-005`)
  - [x] 19a. Added migration `0003_m5_settings_extensions.sql`.
  - [x] 19b. Added consolidated settings models and defaults bootstrap.
  - [x] 19c. `GET /settings` and partial `PUT /settings`.
  - [x] 19d. Retention pruning on update (`provider_raw`, `audit_log`).
  - [x] 19e. Backend tests for defaults, updates, validation, and pruning side effects.

- [x] **20. Audit log enforcement** (`FUNC-AUD-001`, `FUNC-AUD-003`, `FUNC-AUD-004`)
  - [x] 20a. Persist redacted events in `audit_log` while retaining structured logger output.
  - [x] 20b. Added major workflow events: link/sync/backup/restore/wipe/settings.
  - [x] 20c. Retention pruning enforced both on settings update and on audit write path.
  - [x] 20d. `GET /audit-log` with filters, pagination, and `format=json|csv`.
  - [x] 20e. Backend tests for event presence, filtering/export, retention, auth/validation.

- [x] **21. M5 UI**
  - [x] 21a. Extended `ui/src/api/types.ts` and `ui/src/api/client.ts` for M5 endpoints.
  - [x] 21b. Added `ExportPanel` with filtered transaction export, category/budget export, audit export.
  - [x] 21c. Added `DataManagementPanel` for backup/restore/wipe workflows.
  - [x] 21d. Added `SettingsPanel` for timezone/currency/retention/export-default/security/sync config.
  - [x] 21e. Integrated all panels in `App.tsx` refresh flow.
  - [x] 21f. Added frontend tests for render, request wiring, and file-operation flows.

- [x] **22. Post-wipe database re-initialization** (`FUNC-BKP-006`)
  - [x] 22a. Added authenticated `POST /reinitialize` endpoint to re-run migrations on current DB path.
  - [x] 22b. Added Data Management UI action to trigger re-initialization after wipe.
  - [x] 22c. Added backend + frontend tests for wipe -> re-initialize -> recoverable clean state flow.
  - [x] 22d. Updated traceability and M5 design/test docs for new requirement coverage.

- [ ] **M5 verification checklist (step-by-step to run)**
  - [ ] 1. Activate env and run quality gates:
    `. venv/bin/activate && nox -s lint && nox -s tests && nox -s build`
  - [x] 2. Run frontend tests/build:
    `cd ui && npm test && npm run build`
  - [x] 3. Start API against a fresh DB/secrets set:
    ```bash
    export GODZILLA_DB_PATH=/tmp/m5-test.db
    export GODZILLA_DB_KEY=m5-test-key
    export GODZILLA_SECRETS_PATH=/tmp/m5-secrets.db
    export GODZILLA_SECRETS_KEY=m5-secrets-key
    export GODZILLA_API_TOKEN=m5-test-token
    . venv/bin/activate && migrations && godzilla-api
    ```
  - [x] 4. Seed data with one sandbox item + sync:
    ```bash
    curl -s -X POST -H "X-API-Key: m5-test-token" -H "Content-Type: application/json" -d '{}' "http://127.0.0.1:8787/plaid/link"
    ```
    Then sync returned `item_id`:
    ```bash
    curl -s -X POST -H "X-API-Key: m5-test-token" -H "Content-Type: application/json" -d '{"item_id":"<item_id>"}' "http://127.0.0.1:8787/plaid/sync"
    ```
    Confirm sync response shows `added > 0` or `modified > 0`; otherwise raw export values can remain `[]`.
  - [x] 5. Verify `/settings` defaults:
    ```bash
    curl -s -H "X-API-Key: m5-test-token" "http://127.0.0.1:8787/settings"
    ```
    Expect HTTP 200 with timezone/currency/retention/export/security/sync keys.
  - [x] 6. Verify settings update (without purging raw payloads yet):
    ```bash
    curl -s -X PUT -H "X-API-Key: m5-test-token" -H "Content-Type: application/json" -d '{"currency":"USD","retention":{"retain_raw_payloads":true,"retain_logs_days":30},"export_defaults":{"include_raw_payloads":false},"security":{"auto_lock_minutes":15},"sync":{"schedule_enabled":false,"frequency_minutes":360}}' "http://127.0.0.1:8787/settings"
    ```
  - [x] 7. Verify `/balances` includes `account_name`:
    ```bash
    curl -s -H "X-API-Key: m5-test-token" "http://127.0.0.1:8787/balances?limit=5"
    ```
  - [x] 8. Verify transaction export privacy default:
    ```bash
    curl -s -D /tmp/m5-tx.hdr -o /tmp/m5-transactions.csv -H "X-API-Key: m5-test-token" "http://127.0.0.1:8787/export/transactions"
    ```
    Expect no `raw_provider_payloads` column.
  - [x] 9. Verify transaction export with raw payloads included:
    ```bash
    curl -s -o /tmp/m5-transactions-raw.csv -H "X-API-Key: m5-test-token" "http://127.0.0.1:8787/export/transactions?include_raw_payloads=true"
    ```
    Expect `raw_provider_payloads` column present and populated for synced transactions.
  - [x] 10. Verify categories/budgets export CSV + JSON:
    ```bash
    curl -s -o /tmp/m5-categories-budgets.csv -H "X-API-Key: m5-test-token" "http://127.0.0.1:8787/export/categories-budgets?format=csv"
    curl -s -H "X-API-Key: m5-test-token" "http://127.0.0.1:8787/export/categories-budgets?format=json"
    ```
  - [x] 11. Verify backup creation:
    ```bash
    curl -s -o /tmp/m5-backup.gzbk -X POST -H "X-API-Key: m5-test-token" -H "Content-Type: application/json" -d '{"passphrase":"m5-passphrase","include_secrets":true}' "http://127.0.0.1:8787/backup"
    ```
  - [x] 12. Verify integrity failure on tampered backup:
    Tamper encrypted ciphertext (not envelope JSON) so integrity failure is deterministic:
    ```bash
    cp /tmp/m5-backup.gzbk /tmp/m5-backup-tampered.gzbk
    ```
    ```bash
    python3 - <<'PY'
    import json
    from base64 import urlsafe_b64decode, urlsafe_b64encode
    p = "/tmp/m5-backup-tampered.gzbk"
    env = json.loads(open(p, "rb").read().decode("utf-8"))
    c = bytearray(urlsafe_b64decode(env["ciphertext_b64"].encode("ascii")))
    c[len(c)//2] ^= 1
    env["ciphertext_b64"] = urlsafe_b64encode(bytes(c)).decode("ascii")
    open(p, "wb").write(json.dumps(env, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    PY
    ```
    ```bash
    curl -s -X POST -H "X-API-Key: m5-test-token" -F "passphrase=m5-passphrase" -F "backup_file=@/tmp/m5-backup-tampered.gzbk" "http://127.0.0.1:8787/restore"
    ```
    Expect HTTP 400 with `{"detail":"Backup integrity check failed"}`.
  - [x] 13. Verify successful restore:
    ```bash
    curl -s -X POST -H "X-API-Key: m5-test-token" -F "passphrase=m5-passphrase" -F "backup_file=@/tmp/m5-backup.gzbk" "http://127.0.0.1:8787/restore"
    ```
  - [x] 14. Verify audit log JSON + CSV:
    ```bash
    curl -s -H "X-API-Key: m5-test-token" "http://127.0.0.1:8787/audit-log?format=json&limit=50"
    curl -s -o /tmp/m5-audit.csv -H "X-API-Key: m5-test-token" "http://127.0.0.1:8787/audit-log?format=csv"
    ```
  - [x] 15. Verify UI (`cd ui && npm run dev`):
    export downloads, settings save/reload, backup/restore/wipe confirmations, balances show account names.
  - [x] 16. Verify traceability:
    `trace/requirements.yml` has populated `code_refs` + `test_refs` for M5 requirement IDs.
  - [x] 17. Verify wipe flow (run last because it deletes local test data):
    ```bash
    curl -s -X POST -H "X-API-Key: m5-test-token" -H "Content-Type: application/json" -d '{"confirm":"WIPE_LOCAL_DATA"}' "http://127.0.0.1:8787/wipe"
    ```
  - [x] 18. Verify post-wipe re-initialize flow:
    ```bash
    curl -s -X POST -H "X-API-Key: m5-test-token" "http://127.0.0.1:8787/reinitialize"
    ```
  - [x] 19. Mark M5 complete and finalize Conventional Commit checkpoints.

---

## M6 — Security review pass

- [x] **23. HTTPS / TLS for local sidecar** (`SEC-NET-001`, `SEC-NET-002`)
  - [x] 23a. Extend API server runner to accept TLS cert/key from CLI and env (`GODZILLA_TLS_CERT`, `GODZILLA_TLS_KEY`) and run uvicorn in TLS mode when both are provided.
  - [x] 23b. Enforce loopback bind only (`127.0.0.1`, `localhost`, `::1`) and reject non-loopback hosts.
  - [x] 23c. Add `/auth/status` TLS diagnostics with `tls.enabled` + `tls.cert_fingerprint_sha256` (fingerprint only, no private material).
  - [x] 23d. Implement Tauri runtime pinned transport path (command/proxy flow) that validates API cert fingerprint against `GODZILLA_TLS_CERT_SHA256`.
  - [x] 23e. Preserve browser dev path using Vite `/api` HTTP proxy for local dev velocity.
  - [x] 23f. Update Tauri CSP/connect-src and frontend transport wiring for runtime HTTPS + pinning behavior.
  - [x] 23g. Add backend/frontend/Tauri tests for TLS success path and pin mismatch failure path.

- [x] **24. PIN access gate + session timeout** (`SEC-ACC-001`–`SEC-ACC-003`)
  - [x] 24a. Add auth models/endpoints: `GET /auth/status`, `POST /auth/setup-pin`, `POST /auth/unlock`.
  - [x] 24b. Persist PIN verification material only in secure secrets storage.
  - [x] 24c. Enforce unlock-session header (`X-App-Unlock-Token`) for sensitive API routes.
  - [x] 24d. Enforce inactivity lock using persisted `settings.security.auto_lock_minutes`; return HTTP `423` when locked.
  - [x] 24e. Add first-run PIN setup + unlock UI gate before rendering financial panels.
  - [x] 24f. Add dev-only bypass switch (`GODZILLA_DEV_BYPASS_PIN=1`) for local development/testing.
  - [x] 24g. Clear sensitive UI state on lock or timeout event.

- [x] **25. Rate limiting + retry backoff for Plaid calls** (`SEC-NET-003`)
  - [x] 25a. Implement retry in `PlaidClient._post` for transient failures (`429`, transient `5xx`, network errors).
  - [x] 25b. Use bounded exponential backoff + jitter and honor `Retry-After` when present.
  - [x] 25c. Keep non-retriable `4xx` fail-fast behavior.
  - [x] 25d. Add deterministic tests with mocked sleep/jitter and status-code scenarios.

- [x] **26. Unlink institution** (`FUNC-ACCT-008`)
  - [x] 26a. Add Plaid client method for `/item/remove`.
  - [x] 26b. Add `DELETE /plaid/items/{item_id}?mode=keep|purge` with auth + validation.
  - [x] 26c. `mode=keep`: remove/revoke token, clear raw payload cache for item, preserve ledger history.
  - [x] 26d. `mode=purge`: remove/revoke token, delete item-linked local data through cascade policy.
  - [x] 26e. Add unlinked item state and block sync for unlinked items.
  - [x] 26f. Add UI unlink controls in sync panel with explicit mode and destructive confirmation for purge.
  - [x] 26g. Add audit events and tests for unlink start/success/failure in both modes.

- [x] **27. Dependency vulnerability scanning** (`SEC-DATA-004`)
  - [x] 27a. Add dedicated `nox -s security` session.
  - [x] 27b. Run `pip-audit` and `npm audit` (high severity threshold).
  - [x] 27c. Add tooling tests to ensure security session wiring remains intact.
  - [x] 27d. Update setup docs with security scan workflow and failure/triage expectations.

- [~] **28. Final security review pass**
  - [ ] 28a. Verify redaction coverage for new TLS/auth/unlink/backoff paths.
  - [ ] 28b. Verify no token/PIN leakage in logs or client artifacts.
  - [ ] 28c. Verify Tauri pinning end-to-end (success and mismatch failure).
  - [x] 28d. Verify dependency scan output is clean or triaged with documented remediation decisions.

- [x] **29. Traceability maintenance**
  - [x] 29a. Update `trace/requirements.yml` `code_refs`/`test_refs`/`doc_refs` for all M6 IDs.
  - [x] 29b. Ensure coverage for `FUNC-ACCT-008`, `SEC-ACC-001..003`, `SEC-NET-001..003`, `SEC-DATA-004`.

- [x] **30. Design doc updates**
  - [x] 30a. Add `docs/design/m6-security-review-pass.md`.
  - [x] 30b. Add `docs/test-strategy/m6-security-review-pass.md`.
  - [x] 30c. Document dev-vs-prod TLS transport behavior and Tauri pinning tradeoffs.

- [x] **M6 checkpoint commits (required while implementing)**
  - [x] 1. `feat(m6): add tls sidecar enforcement and auth status tls diagnostics` (Task 23 core)
  - [x] 2. `feat(m6): add pin setup unlock gate and session timeout enforcement` (Task 24)
  - [x] 3. `feat(m6): add plaid retry backoff and unlink institution workflows` (Tasks 25–26 backend)
  - [x] 4. `feat(ui): add auth gate lock handling and unlink controls for m6` (Tasks 24e/24g/26f + transport wiring)
  - [x] 5. `chore(m6): add dependency security scan session and tooling coverage` (Task 27)
  - [x] 6. `docs(m6): update trace design and test strategy for security pass` (Tasks 28–30)
  - [x] 7. `docs(plan): mark m6 tasks and checklist status` (final bookkeeping)

- [ ] **M6 verification checklist (step-by-step to run)**
  - [x] 1. Activate environment and run core quality gates:
    ```bash
    . venv/bin/activate
    nox -s lint
    nox -s tests
    nox -s build
    ```
  - [x] 2. Run frontend tests/build:
    ```bash
    cd ui
    npm test
    npm run build
    cd ..
    ```
  - [x] 3. Generate per-install TLS cert/key and fingerprint:
    ```bash
    bash ui/scripts/gen-cert.sh
    export GODZILLA_TLS_CERT="${HOME}/.config/godzilla/tls/api-server.crt"
    export GODZILLA_TLS_KEY="${HOME}/.config/godzilla/tls/api-server.key"
    export GODZILLA_TLS_CERT_SHA256="$(openssl x509 -in "${GODZILLA_TLS_CERT}" -noout -fingerprint -sha256 | cut -d= -f2 | tr -d ':')"
    ```
  - [x] 4. Verify non-loopback bind is rejected:
    ```bash
    . venv/bin/activate
    godzilla-api --host 0.0.0.0 --port 8787
    ```
    Expect startup failure with loopback-only host validation message.
  - [x] 5. Start API with fresh DB/secrets in TLS-required mode (Terminal A):
    ```bash
    export GODZILLA_DB_PATH=/tmp/m6-test.db
    export GODZILLA_DB_KEY=m6-test-key
    export GODZILLA_SECRETS_PATH=/tmp/m6-secrets.db
    export GODZILLA_SECRETS_KEY=m6-secrets-key
    export GODZILLA_API_TOKEN=m6-test-token
    export GODZILLA_DEV_BYPASS_PIN=0
    export GODZILLA_TLS_CERT="${HOME}/.config/godzilla/tls/api-server.crt"
    export GODZILLA_TLS_KEY="${HOME}/.config/godzilla/tls/api-server.key"
    rm -f /tmp/m6-test.db /tmp/m6-test.db-wal /tmp/m6-test.db-shm /tmp/m6-secrets.db /tmp/m6-secrets.db-wal /tmp/m6-secrets.db-shm
    . venv/bin/activate
    migrations
    godzilla-api --host 127.0.0.1 --port 8787
    ```
    Keep this running; execute steps 6+ in Terminal B.
  - [x] 6. Set Terminal B env vars for API calls:
    ```bash
    export GODZILLA_API_TOKEN=m6-test-token
    export GODZILLA_TLS_CERT="${HOME}/.config/godzilla/tls/api-server.crt"
    export GODZILLA_TLS_CERT_SHA256="$(openssl x509 -in "${GODZILLA_TLS_CERT}" -noout -fingerprint -sha256 | cut -d= -f2 | tr -d ':')"
    ```
  - [x] 7. Verify plain HTTP fails and HTTPS works:
    ```bash
    curl -sS --max-time 5 -H "X-API-Key: ${GODZILLA_API_TOKEN}" "http://127.0.0.1:8787/auth/status" || true
    curl --cacert "${GODZILLA_TLS_CERT}" -sS -H "X-API-Key: ${GODZILLA_API_TOKEN}" "https://127.0.0.1:8787/auth/status"
    ```
  - [x] 8. Verify PIN bootstrap gate:
    ```bash
    curl --cacert "${GODZILLA_TLS_CERT}" -sS -H "X-API-Key: ${GODZILLA_API_TOKEN}" "https://127.0.0.1:8787/auth/status"
    curl --cacert "${GODZILLA_TLS_CERT}" -sS -H "X-API-Key: ${GODZILLA_API_TOKEN}" "https://127.0.0.1:8787/accounts"
    ```
    Expect setup-required/locked status and HTTP `423` for protected endpoint.
  - [x] 9. Configure PIN and unlock:
    ```bash
    curl --cacert "${GODZILLA_TLS_CERT}" -sS -X POST -H "X-API-Key: ${GODZILLA_API_TOKEN}" -H "Content-Type: application/json" -d '{"new_pin":"123456"}' "https://127.0.0.1:8787/auth/setup-pin"
    UNLOCK_TOKEN=$(curl --cacert "${GODZILLA_TLS_CERT}" -sS -X POST -H "X-API-Key: ${GODZILLA_API_TOKEN}" -H "Content-Type: application/json" -d '{"pin":"123456"}' "https://127.0.0.1:8787/auth/unlock" | python3 -c "import json,sys; print(json.load(sys.stdin)['unlock_token'])")
    curl --cacert "${GODZILLA_TLS_CERT}" -sS -H "X-API-Key: ${GODZILLA_API_TOKEN}" -H "X-App-Unlock-Token: ${UNLOCK_TOKEN}" "https://127.0.0.1:8787/accounts"
    ```
  - [x] 10. Verify inactivity timeout lock:
    ```bash
    curl --cacert "${GODZILLA_TLS_CERT}" -sS -X PUT -H "X-API-Key: ${GODZILLA_API_TOKEN}" -H "X-App-Unlock-Token: ${UNLOCK_TOKEN}" -H "Content-Type: application/json" -d '{"security":{"auto_lock_minutes":1}}' "https://127.0.0.1:8787/settings"
    sleep 70
    curl --cacert "${GODZILLA_TLS_CERT}" -sS -H "X-API-Key: ${GODZILLA_API_TOKEN}" -H "X-App-Unlock-Token: ${UNLOCK_TOKEN}" "https://127.0.0.1:8787/accounts"
    ```
    Expect HTTP `423` after timeout.
  - [x] 11. Run targeted backoff tests:
    ```bash
    . venv/bin/activate
    pytest godzilla_core/tests/test_plaid_client.py -k "backoff or retry or rate_limit"
    ```
  - [x] 12. Link/sync first item and verify unlink `mode=keep`:
    ```bash
    UNLOCK_TOKEN=$(curl --cacert "${GODZILLA_TLS_CERT}" -sS -X POST -H "X-API-Key: ${GODZILLA_API_TOKEN}" -H "Content-Type: application/json" -d '{"pin":"123456"}' "https://127.0.0.1:8787/auth/unlock" | python3 -c "import json,sys; print(json.load(sys.stdin)['unlock_token'])")
    ITEM_1=$(curl --cacert "${GODZILLA_TLS_CERT}" -sS -X POST -H "X-API-Key: ${GODZILLA_API_TOKEN}" -H "X-App-Unlock-Token: ${UNLOCK_TOKEN}" -H "Content-Type: application/json" -d '{}' "https://127.0.0.1:8787/plaid/link" | python3 -c "import json,sys; print(json.load(sys.stdin)['item_id'])")
    curl --cacert "${GODZILLA_TLS_CERT}" -sS -X POST -H "X-API-Key: ${GODZILLA_API_TOKEN}" -H "X-App-Unlock-Token: ${UNLOCK_TOKEN}" -H "Content-Type: application/json" -d "{\"item_id\":\"${ITEM_1}\"}" "https://127.0.0.1:8787/plaid/sync"
    curl --cacert "${GODZILLA_TLS_CERT}" -sS -X DELETE -H "X-API-Key: ${GODZILLA_API_TOKEN}" -H "X-App-Unlock-Token: ${UNLOCK_TOKEN}" "https://127.0.0.1:8787/plaid/items/${ITEM_1}?mode=keep"
    curl --cacert "${GODZILLA_TLS_CERT}" -sS -X POST -H "X-API-Key: ${GODZILLA_API_TOKEN}" -H "X-App-Unlock-Token: ${UNLOCK_TOKEN}" -H "Content-Type: application/json" -d "{\"item_id\":\"${ITEM_1}\"}" "https://127.0.0.1:8787/plaid/sync"
    ```
    Expect keep-unlink success and follow-up sync blocked for unlinked item.
  - [x] 13. Link/sync second item and verify unlink `mode=purge`:
    ```bash
    ITEM_2=$(curl --cacert "${GODZILLA_TLS_CERT}" -sS -X POST -H "X-API-Key: ${GODZILLA_API_TOKEN}" -H "X-App-Unlock-Token: ${UNLOCK_TOKEN}" -H "Content-Type: application/json" -d '{}' "https://127.0.0.1:8787/plaid/link" | python3 -c "import json,sys; print(json.load(sys.stdin)['item_id'])")
    curl --cacert "${GODZILLA_TLS_CERT}" -sS -X POST -H "X-API-Key: ${GODZILLA_API_TOKEN}" -H "X-App-Unlock-Token: ${UNLOCK_TOKEN}" -H "Content-Type: application/json" -d "{\"item_id\":\"${ITEM_2}\"}" "https://127.0.0.1:8787/plaid/sync"
    curl --cacert "${GODZILLA_TLS_CERT}" -sS -X DELETE -H "X-API-Key: ${GODZILLA_API_TOKEN}" -H "X-App-Unlock-Token: ${UNLOCK_TOKEN}" "https://127.0.0.1:8787/plaid/items/${ITEM_2}?mode=purge"
    curl --cacert "${GODZILLA_TLS_CERT}" -sS -H "X-API-Key: ${GODZILLA_API_TOKEN}" -H "X-App-Unlock-Token: ${UNLOCK_TOKEN}" "https://127.0.0.1:8787/sync-state"
    ```
    Expect purged item absent from sync-state and local linked records removed per policy.
  - [x] 14. Verify UI lock/unlock workflow in browser dev mode:
    Run API without TLS
    ```bash
    unset GODZILLA_TLS_CERT
    unset GODZILLA_TLS_KEY
    export GODZILLA_DB_PATH=/tmp/m6-test.db
    export GODZILLA_DB_KEY=m6-test-key
    export GODZILLA_SECRETS_PATH=/tmp/m6-secrets.db
    export GODZILLA_SECRETS_KEY=m6-secrets-key
    export GODZILLA_API_TOKEN=m6-test-token
    export GODZILLA_DEV_BYPASS_PIN=0
    . venv/bin/activate
    godzilla-api --host 127.0.0.1 --port 8787
    ```
    ```bash
    cd ui
    npm run dev
    ```
    Verify setup/unlock gate appears first, financial panels are hidden while locked, and lock event clears sensitive UI state.
  - [x] 15. Verify Tauri pinned transport behavior (success then mismatch):
    ```bash
    cd ui
    export GODZILLA_TLS_CERT_SHA256="${GODZILLA_TLS_CERT_SHA256}"
    npm run tauri dev
    ```
    Stop app, then run mismatch check:
    ```bash
    cd ui
    export GODZILLA_TLS_CERT_SHA256=DEADBEEF
    npm run tauri dev
    ```
    Expect API transport failure on mismatch.
  - [x] 16. Run dependency vulnerability scan:
    ```bash
    . venv/bin/activate
    nox -s security
    ```
  - [x] 17. Verify traceability coverage for all M6 IDs:
    ```bash
    rg -n "FUNC-ACCT-008|SEC-ACC-001|SEC-ACC-002|SEC-ACC-003|SEC-NET-001|SEC-NET-002|SEC-NET-003|SEC-DATA-004" trace/requirements.yml
    ```
