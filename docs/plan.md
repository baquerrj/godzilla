# MVP Plan

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

- [ ] **3. Frontend scaffold (Tauri v2 + React + Vite)**
  Initialize Tauri v2 project, pin Node.js v24 LTS, configure Vite dev proxy to
  forward `/api/*` → `127.0.0.1:8787`, generate per-install self-signed cert and
  configure Tauri to pin it.

- [ ] **4. Typed frontend API client module**
  TypeScript client for all 6 endpoints with loading/error/success state handling.

- [ ] **5. MVP UI — accounts + sync flow**
  "Connect sandbox account", "Run sync", accounts/transactions/balances tables,
  sync status panel.

---

## M2 — Transaction list/detail + categorization + search/filters

- [ ] **6. Transaction search & filter API** (`FUNC-TXN-002`)
  Extend `GET /transactions` with date range, account, category, merchant text,
  and amount range filters.

- [ ] **7. Transaction detail endpoint** (`FUNC-TXN-003`)
  `GET /transactions/{id}` with full detail including read-only raw provider metadata.

- [ ] **8. Category management endpoints** (`FUNC-CAT-001`, `FUNC-CAT-002`)
  `GET/POST /categories`, `PATCH /categories/{id}` (rename/deactivate). Enforce
  leaf-only assignment and block deactivated categories.

- [ ] **9. Transaction mutation endpoints** (`FUNC-TXN-004`–`FUNC-TXN-008`)
  `PATCH /transactions/{id}` (category, notes, tags, is_transfer, is_excluded),
  `POST /transactions/{id}/splits`. Write to `transaction_override` for provenance.

- [ ] **10. Provider category mapping on sync** (`FUNC-CAT-003`)
  Map Plaid category signals to local hierarchy as a suggested default during ingestion.

- [ ] **11. Conflict detection + resolution endpoints** (`FUNC-SYNC-005`–`FUNC-SYNC-007`)
  Detect field-level conflicts during sync, write to `conflict` table.
  `GET /conflicts`, `POST /conflicts/{id}/resolve`.

- [ ] **12. M2 UI**
  Transaction list with search/filter, detail view, category picker,
  mark transfer/exclude/split, conflict resolution queue.

---

## M3 — Budgets + monthly view + overspend drill-down

- [ ] **13. Budget endpoints** (`FUNC-BUD-001`–`FUNC-BUD-004`)
  `GET /budgets?month=YYYY-MM` (planned/actual/remaining), `POST /budgets`,
  `DELETE /budgets/{id}`. Enforce budget inclusion rules throughout.

- [ ] **14. M3 UI**
  Monthly budget view with overspend highlighting and drill-down to transactions.

---

## M4 — Dashboards/reports + net worth snapshots

- [ ] **15. Dashboard/report endpoints** (`FUNC-REP-001`–`FUNC-REP-008`)
  - `GET /reports/monthly-overview?month=YYYY-MM`
  - `GET /reports/cash-flow?start=...&end=...`
  - `GET /reports/category-trends?categories=...&months=12`
  - `GET /reports/net-worth?start=...&end=...`
  All respect inclusion rules and support date navigation.

- [ ] **16. M4 UI**
  Monthly overview dashboard, cash flow chart, category trend chart,
  net worth chart, date/month navigation.

---

## M5 — Export + encrypted backup/restore + settings + audit logging hardening

- [ ] **17. Export endpoints** (`FUNC-EXP-001`–`FUNC-EXP-003`)
  `GET /export/transactions` (CSV, filter-aware, raw payload excluded by default),
  `GET /export/categories-budgets` (CSV/JSON).

- [ ] **18. Encrypted backup/restore + wipe** (`FUNC-BKP-001`–`FUNC-BKP-004`)
  `POST /backup` (passphrase-encrypted, authenticated MAC),
  `POST /restore` (verify MAC, fail on tamper),
  `POST /wipe` (secure delete DB + secrets).

- [ ] **19. Settings endpoints** (`FUNC-SET-001`–`FUNC-SET-005`)
  `GET /settings`, `PUT /settings` — timezone, currency, retention policy,
  export defaults, sync config. Apply retention pruning.

- [ ] **20. Audit log enforcement** (`FUNC-AUD-001`, `FUNC-AUD-003`, `FUNC-AUD-004`)
  Write to `audit_log` for major events, enforce retention/pruning,
  `GET /audit-log` (redacted export).

- [ ] **21. M5 UI**
  Export buttons, backup/restore/wipe dialogs, settings page.

---

## M6 — Security review pass

- [ ] **22. HTTPS / TLS for local sidecar** (`SEC-NET-001`, `SEC-NET-002`)
  Per-install self-signed cert, uvicorn TLS config, Tauri WebView cert pinning.

- [ ] **23. PIN access gate + session timeout** (`SEC-ACC-001`–`SEC-ACC-003`)
  `POST /auth/setup-pin`, `POST /auth/unlock`, inactivity lock + clear UI state.

- [ ] **24. Rate limiting + retry backoff for Plaid calls** (`SEC-NET-003`)
  Exponential backoff with jitter in `PlaidClient._post` for 429/5xx.

- [ ] **25. Unlink institution** (`FUNC-ACCT-008`)
  `DELETE /plaid/items/{item_id}` — call Plaid `/item/remove`, delete token,
  handle data per retention policy.

- [ ] **26. Dependency vulnerability scanning** (`SEC-DATA-004`)
  Add `pip-audit` to `nox -s lint` or a new `nox -s security` session.

- [ ] **27. Final security review pass**
  Audit log redaction completeness, no secrets in client artifacts,
  TLS cert pinning end-to-end, dependency audit resolved.

---

## Cross-cutting (ongoing throughout)

- [ ] **28. Traceability maintenance**
  Keep `trace/requirements.yml` `code_refs` and `test_refs` current after every task.

- [ ] **29. Design doc updates**
  Create/update `docs/design/` docs with Mermaid diagrams for M2–M6 features.
