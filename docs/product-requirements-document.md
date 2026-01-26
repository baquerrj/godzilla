## Product Requirements Document (PRD): Personal Budgeting App (Monarch-like, single-user)

### 1. Summary

A personal budgeting and net-worth app for a single user that aggregates financial accounts via Plaid, categorizes transactions, supports budgeting, and provides dashboards, reports, exports, and encrypted backup/restore. Although single-user, it follows secure-by-design practices appropriate for financial data.

### 2. Goals

* Provide a unified view of accounts, transactions, budgets, cash flow,  and net worth.
* Fast monthly budgeting workflow with automated categorization and easy manual corrections.
* Track trends over time (spend by category, income vs expenses, savings rate).
* Strong privacy and security for financial data.
* Clear provenance of imported vs user-edited data.

### 3. Non-goals

* Multi-user support (family sharing), subscription billing, or public distribution.
* Monetization/subscriptions and public distribution.
* Trading/investment execution or deep investment analytics.
* Full accounting software features (invoicing, double-entry bookkeeping).

### 4. Target User and Primary Use Cases

Single user.

* Daily/weekly: review new transactions, fix categories, mark transfers, add notes/tags.
* Monthly: set/adjust budgets, review budget performance, reconcile anomalies.
* Quarterly/yearly: analyze trends, plan savings goals, export data, archive backups.

### 5. Success Metrics (Personal)

* Monthly close time ≤ 30 minutes.
* Categorization accuracy after learning ≥ 90%.
* Data freshness aligns with Plaid-supported update cadence; manual refresh works.
* No plaintext storage of tokens/secrets; no secrets in logs; encryption at rest enabled.
* Backups and restores succeed reliably and are verifiable.

### 6. Assumptions and Constraints

* Accounts are linked via Plaid (Link flow) and updated via Plaid sync endpoints.
* Single-user, but with strong access control and secret handling.
* Prefer minimal operational burden: local-first or self-hosted with low maintenance.
* Must support common account types: checking, savings, credit cards, loans, investments (balances at minimum).
* App may operate offline for viewing/editing already-synced data (sync requires network).

### 7. MVP Scope

In MVP: linking accounts, syncing transactions, categorization, transaction management, monthly and per-category budgeting, dashboards/reports, exports, encrypted backup/restore, settings, audit logging, secure storage/redaction.
Out of MVP: rules engine v2, advanced forecasting, receipt scanning, shared budgets, investment analytics.

### 8. User Stories (MVP)

* As a user, I can link a financial institution using Plaid and see connected accounts.
* As a user, I can refresh/sync transactions and see newly imported items.
* As a user, I can categorize transactions and the app remembers/copies my choices.
* As a user, I can mark transactions as transfer, exclude from budget, or split a transaction.
* As a user, I can create monthly budgets per category and see remaining amounts.
* As a user, I can view monthly cash flow (income, expenses, savings).
* As a user, I can view net worth over time from account balances.
* As a user, I can search, filter, and export transactions (CSV).
* As a user, I can back up and restore the app database securely.

### 9. Requirements ()

#### 9.1 System requirements

| requirement ID | requirement title         | requirement body (including "shall" statements)                                                                                  | verification plan                                                                                                           | unit test                                   | parent requirement ID (if it is a derived requirement) |
| -------------- | ------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- | ------------------------------------------------------ |
| SYS-001        | System purpose            | The application shall provide a unified view of financial accounts, transactions, budgets, and net worth for a single user.      | End-to-end scenario: link accounts, sync transactions, set budgets, view net worth; confirm all views render and reconcile. | |                                                        |
| SYS-002        | Single-user scope         | The application shall support exactly one user profile and shall not include multi-user sharing features.                        | Confirm only one profile can be created; attempt to create additional profiles is blocked.                                  |         | SYS-001                                                |
| SYS-003        | Secure-by-design baseline | The application shall enforce secure handling of financial data (tokens, balances, transactions) even for single-user operation. | Security review checklist; confirm encryption, redaction, access control, and secret storage are enabled.                   | | SYS-001                                                |

#### 9.2 Account linking and institution management (Plaid)

| requirement ID | requirement title                       | requirement body (including "shall" statements)                                                                                                                       | verification plan                                                                                                                     | unit test                                      | parent requirement ID (if it is a derived requirement) |
| -------------- | --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------ |
| FUNC-ACCT-001  | Plaid Link initiation                   | The system shall initiate the Plaid Link flow to connect a financial institution and obtain a Plaid public\_token for exchange server-side.                            | Integration test using Plaid sandbox Link; confirm public\_token received and exchanged.                                               |               | SYS-001                                                |
| FUNC-ACCT-002  | Token exchange and storage              | The system shall exchange the public\_token for an access\_token server-side and shall store the access\_token only in a protected secret store (not in client storage). | Inspect client storage for absence of access\_token; validate server secret store has token; verify access via authenticated API only. |   | SYS-003                                                |
| FUNC-ACCT-003  | Account metadata retrieval              | After linking, the system shall retrieve and persist account metadata (name, type/subtype, mask, institution) for each connected account.                             | Link sandbox item; confirm accounts list matches Plaid response and persists across app restart.                                      |              | FUNC-ACCT-001                                          |
| FUNC-ACCT-004  | Connection state tracking               | The system shall track per-item connection state (linked, requires\_reauth, error) and last successful sync timestamp.                                                 | Simulate reauth-required item (or mock); confirm UI/status and timestamps update correctly.                                           |                  | FUNC-ACCT-003                                          |
| FUNC-ACCT-005  | Manual refresh                          | The system shall provide a manual refresh action that triggers an incremental sync of accounts and transactions and reports completion status.                        | Click refresh; verify incremental sync invoked; confirm status and last-sync updated.                                                 |        | FUNC-ACCT-004                                          |
| FUNC-ACCT-006  | Scheduled refresh (optional deployment) | If deployed with a scheduler, the system shall support scheduled sync at a configurable interval and shall surface the most recent run result.                        | Configure schedule; verify periodic runs and status surfaced.                                                                         |             | FUNC-ACCT-004                                          |
| FUNC-ACCT-007  | Error handling and messaging            | The system shall handle Plaid and network errors (rate limit, downtime, invalid credentials) and shall present actionable messages without exposing secrets.          | Inject API errors; verify user message; ensure logs contain no tokens/PII beyond policy.                                              |  | SYS-003                                                |
| FUNC-ACCT-008  | Unlink institution                      | The system shall allow the user to unlink an institution and shall revoke/delete associated tokens and cached raw payloads per retention settings.                    | Unlink item; confirm tokens removed; accounts/transactions handled per policy; sync no longer runs for that item.                     | | SYS-003                                                |

#### 9.3 Sync and ingestion

| requirement ID | requirement title            | requirement body (including "shall" statements)                                                                                                            | verification plan                                                                                    | unit test                                     | parent requirement ID (if it is a derived requirement) |
| -------------- | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | --------------------------------------------- | ------------------------------------------------------ |
| FUNC-SYNC-001  | Incremental transaction sync | The system shall support incremental transaction ingestion using a persisted cursor/sync state to avoid full re-imports.                                   | Sync twice; second sync should fetch only deltas; confirm runtime and counts.                        |           | FUNC-ACCT-004                                          |
| FUNC-SYNC-002  | Idempotent ingestion         | The system shall be idempotent: re-running the same sync shall not create duplicate transactions.                                                          | Replay same provider payload; confirm transaction counts unchanged.                                  | | FUNC-SYNC-001                                          |
| FUNC-SYNC-003  | Pending vs posted handling   | The system shall represent pending and posted transactions and shall reconcile pending-to-posted transitions without double counting.                      | Use mocked pending+posted sequence; confirm final single posted record with correct status handling. |       | FUNC-SYNC-001                                          |
| FUNC-SYNC-004  | Provider provenance          | The system shall store the source of each field (provider vs user override) and shall preserve raw provider values for audit/debug (subject to retention). | Edit category/name; confirm raw provider values preserved and UI shows override indicator.           |              | SYS-001                                                |

#### 9.4 Transactions

| requirement ID | requirement title                | requirement body (including "shall" statements)                                                                                                                                      | verification plan                                                              | unit test                                      | parent requirement ID (if it is a derived requirement) |
| -------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------ | ---------------------------------------------- | ------------------------------------------------------ |
| FUNC-TXN-001   | Transaction list                 | The system shall display a transaction list with pagination and sorting by date and amount.                                                                                          | Load dataset > page size; verify paging and sorting.                           | | SYS-001                                                |
| FUNC-TXN-002   | Search and filters               | The system shall support search and filters by date range, account, category, merchant/text, and amount range.                                                                       | Apply each filter; confirm results match expected subset.                      |   | FUNC-TXN-001                                           |
| FUNC-TXN-003   | Transaction detail view          | The system shall provide a detail view showing date, amount, merchant/name, account, category, status, and raw provider metadata (read-only).                                        | Open detail; confirm fields populated and raw view is non-editable.            |       | FUNC-TXN-001                                           |
| FUNC-TXN-004   | Category override                | The system shall allow the user to override a transaction category and shall persist the override across subsequent syncs.                                                           | Override category; re-sync; confirm override preserved.                        |   | FUNC-SYNC-004                                          |
| FUNC-TXN-005   | Notes and tags                   | The system shall allow the user to add notes and tags to a transaction and shall include them in search.                                                                             | Add note/tag; search by content; confirm hit.                                  |               | FUNC-TXN-002                                           |
| FUNC-TXN-006   | Mark transfer                    | The system shall allow marking transactions as transfers and shall exclude them from budget calculations by default.                                                                 | Mark as transfer; confirm budget totals adjust accordingly.                    |          | FUNC-BUD-004                                           |
| FUNC-TXN-007   | Exclude from budget              | The system shall allow excluding a transaction from budget calculations while retaining it for reporting (unless also excluded from reports).                                        | Exclude; confirm budgets change, report behavior matches setting.              |      | FUNC-BUD-004                                           |
| FUNC-TXN-008   | Split transactions               | The system shall allow splitting a transaction into multiple lines with independent categories and amounts, and the split total shall equal the original amount.                     | Create split; verify sum; verify budgets reflect split lines.                  |         | FUNC-TXN-003                                           |
| FUNC-TXN-009   | Deduplication heuristic fallback | If a provider transaction identifier is unavailable, the system shall apply a deterministic deduplication heuristic (date, amount, merchant, account) and flag conflicts for review. | Ingest crafted duplicates without IDs; confirm single record or conflict flag. |  | FUNC-SYNC-002                                          |

#### 9.5 Categories

| requirement ID | requirement title         | requirement body (including "shall" statements)                                                                                                                         | verification plan                                                                  | unit test                                   | parent requirement ID (if it is a derived requirement) |
| -------------- | ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------- | ------------------------------------------------------ |
| FUNC-CAT-001   | Category hierarchy        | The system shall support a category hierarchy (parent/child) and shall assign each transaction to exactly one leaf category.                                            | Create hierarchy; assign transaction; ensure leaf constraint enforced.             |    | SYS-001                                                |
| FUNC-CAT-002   | Category management       | The system shall allow creating, renaming, and deactivating categories; deactivated categories shall not be assignable but historical assignments shall remain visible. | Deactivate category; attempt assignment blocked; historical records still display. |  | FUNC-CAT-001                                           |
| FUNC-CAT-003   | Provider category mapping | The system shall ingest provider category signals (when available) and shall propose an initial category mapping that is user-editable.                                 | Sync provider categories; verify suggested mapping; override persists.             | | FUNC-SYNC-004                                          |

#### 9.6 Budgets

| requirement ID | requirement title      | requirement body (including "shall" statements)                                                                                                                | verification plan                                                           | unit test                                     | parent requirement ID (if it is a derived requirement) |
| -------------- | ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- | --------------------------------------------- | ------------------------------------------------------ |
| FUNC-BUD-001   | Monthly budgets        | The system shall allow defining a monthly budget amount per category for a selected month.                                                                     | Set budgets; switch months; confirm persistence and correct month scoping.  |                 | SYS-001                                                |
| FUNC-BUD-002   | Budget performance     | The system shall compute planned vs actual vs remaining per category for the month based on included transactions.                                             | Compare computed values against known fixture dataset.                      |     | FUNC-BUD-001                                           |
| FUNC-BUD-003   | Overspend highlighting | The system shall highlight overspent categories and allow drill-down to contributing transactions.                                                             | Force overspend; confirm highlight and drill-down list correctness.         | | FUNC-BUD-002                                           |
| FUNC-BUD-004   | Budget inclusion rules | The system shall exclude transfers and explicitly excluded transactions from budget actuals by default, and shall apply these rules consistently across views. | Create set of transfers/excluded; verify budgets and category totals match. |      | FUNC-TXN-006                                           |

##### 9.7 Dashboards and Reports

Dashboards provide at-a-glance visibility, while reports provide drill-down and time-series analysis. All metrics must respect inclusion rules (e.g., transfers excluded from budgets) and allow drill-down to underlying transactions.

| requirement ID | requirement title           | requirement body (including "shall" statements)                                                                                                     | verification plan                                                                      | unit test                                     | parent requirement ID (if it is a derived requirement) |
| -------------- | --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | --------------------------------------------- | ------------------------------------------------------ |
| FUNC-REP-001   | Monthly overview dashboard  | The system shall provide a monthly overview showing total income, total expenses, net savings (income minus expenses), and top spending categories. | Load fixture month; confirm computed totals and top categories match expected results. | | SYS-001                                                |
| FUNC-REP-002   | Drill-down from metrics     | The system shall allow drill-down from any dashboard metric (e.g., category spend) to the filtered transaction list that produced it.               | Click metric; confirm transaction list filters applied correctly and totals reconcile. |    | FUNC-TXN-002                                           |
| FUNC-REP-003   | Cash flow report            | The system shall provide a cash flow report by month aggregating income and expenses and shall display the savings rate.                            | Compare report outputs vs fixture dataset across multiple months.                      |     | FUNC-REP-001                                           |
| FUNC-REP-004   | Category trend report       | The system shall provide category spending trends over time (at least last 12 months) and shall support selecting one or more categories.           | Select categories; verify chart data points match computed aggregates.                 |      | FUNC-REP-002                                           |
| FUNC-REP-005   | Net worth time series       | The system shall compute net worth as assets minus liabilities using account balance snapshots and shall display net worth over time.               | Load snapshots; verify net worth points match expected calculations.                   |        | SYS-001                                                |
| FUNC-REP-006   | Balance snapshotting        | The system shall create balance snapshots for connected accounts at each successful sync (or daily, if more frequent) for net worth trending.       | Run sync; confirm snapshots created once per sync and are queryable.                   |       | FUNC-ACCT-005                                          |
| FUNC-REP-007   | Inclusion rules consistency | The system shall apply budget inclusion rules consistently across dashboards and reports and shall label any metric that includes excluded items.   | Create transfers/excluded; compare budget vs report totals; note labels.               |        | FUNC-BUD-004                                           |
| FUNC-REP-008   | Date navigation             | The system shall allow selecting a reporting period (month picker and custom date range) and shall update all visible metrics accordingly.          | Change month/range; verify all widgets reflect same period.                            |  | FUNC-REP-001                                           |

#### 9.8 Export, Backup, and Restore

Exports enable analysis outside the app; backups enable recovery and portability. Backup must be encrypted and integrity-checked.

| requirement ID | requirement title            | requirement body (including "shall" statements)                                                                                                                       | verification plan                                                                                          | unit test                                         | parent requirement ID (if it is a derived requirement) |
| -------------- | ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------ |
| FUNC-EXP-001   | Transaction export CSV       | The system shall export transactions to CSV, including user overrides (category, notes/tags, flags, split lines) and shall allow exporting the current filtered view. | Apply filters; export; validate file contents, headers, and row counts match filtered results.             |        | FUNC-TXN-002                                           |
| FUNC-EXP-002   | Category and budget export   | The system shall export categories and monthly budgets to CSV or JSON.                                                                                                | Export; validate schema and values against fixture.                                                        |       | SYS-001                                                |
| FUNC-EXP-003   | Export privacy controls      | The system shall provide export options to exclude sensitive raw provider payload fields and shall default to excluding raw payloads.                                 | Export with defaults; inspect file for absence of raw payload columns; toggle option and verify inclusion. |       | SYS-003                                                |
| FUNC-BKP-001   | Encrypted backup creation    | The system shall create an encrypted backup of the application database and settings, protected by a user-supplied passphrase or OS-stored key.                       | Create backup; verify file is encrypted (not readable as plaintext) and is restorable.                     |    | SYS-003                                                |
| FUNC-BKP-002   | Backup integrity check       | The system shall include an integrity check (e.g., authenticated encryption or MAC) and shall detect tampering/corruption during restore.                             | Corrupt backup bytes; confirm restore fails with explicit integrity error.                                 |                 | FUNC-BKP-001                                           |
| FUNC-BKP-003   | Restore workflow             | The system shall restore from an encrypted backup into a clean state and shall preserve user overrides and provenance markers.                                        | Restore into fresh install; compare key counts and sampled records; verify override flags.                 | | FUNC-SYNC-004                                          |
| FUNC-BKP-004   | Wipe local data              | The system shall provide a “wipe all local data” action that securely deletes local database files and removes secrets from secure storage.                           | Trigger wipe; confirm db deleted; confirm secrets removed; app returns to initial state.                   |                | SYS-003                                                |
| FUNC-BKP-005   | Backup scheduling (optional) | If deployed with a scheduler, the system shall support scheduled backups at a configurable interval and shall retain a configurable number of backups.                | Configure schedule; verify backup creation and rotation.                                                   |                  | FUNC-BKP-001                                           |

#### 9.9 Settings

Settings govern localization, budgeting behavior, privacy controls, retention, and sync behavior.

| requirement ID | requirement title     | requirement body (including "shall" statements)                                                                                                | verification plan                                                              | unit test                                         | parent requirement ID (if it is a derived requirement) |
| -------------- | --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------- | ------------------------------------------------------ |
| FUNC-SET-001   | Timezone and currency | The system shall allow configuring timezone and currency and shall apply them consistently to displayed dates and formatted amounts.           | Change settings; verify UI date boundaries and currency formatting update.     | | SYS-001                                                |
| FUNC-SET-002   | Retention settings    | The system shall allow configuring retention for raw provider payloads and diagnostic logs and shall enforce pruning according to policy.      | Set short retention; ingest data; run prune; confirm old raw/log data removed. |                 | SYS-003                                                |
| FUNC-SET-003   | Auto-lock and timeout | The system shall support auto-lock after a configurable inactivity period and shall require re-authentication/unlock to access financial data. | Set timeout low; wait; confirm lock; verify unlock required.                   |       | SEC-ACC-003                                            |
| FUNC-SET-004   | Sync configuration    | The system shall allow enabling/disabling scheduled sync (if available) and configuring sync frequency.                                        | Toggle schedule; confirm scheduler behavior changes.                           |                       | FUNC-ACCT-006                                          |
| FUNC-SET-005   | Export defaults       | The system shall allow configuring default export behavior (e.g., include/exclude raw payloads) and shall apply defaults in the export UI.     | Change defaults; export; verify settings persisted.                            |                    | FUNC-EXP-003                                           |

#### 9.10 Audit Logging

Audit logs are local/system logs intended to record significant events without leaking secrets. Logs must be redact-safe.

| requirement ID | requirement title       | requirement body (including "shall" statements)                                                                                                                                 | verification plan                                                                       | unit test                                            | parent requirement ID (if it is a derived requirement) |
| -------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------ |
| FUNC-AUD-001   | Event audit log         | The system shall record an audit log entry for major events (institution link/unlink, sync run start/end, backup/restore, wipe, settings changes).                              | Perform events; verify corresponding log entries exist with timestamps.                 |                | SYS-003                                                |
| FUNC-AUD-002   | Log redaction           | The system shall redact secrets and sensitive fields (tokens, credentials, full account numbers) from all logs and shall prevent accidental logging of raw payloads by default. | Force error conditions; inspect logs for redaction; run static checks on logging calls. | | SYS-003                                                |
| FUNC-AUD-003   | Log retention           | The system shall enforce log retention settings and shall rotate/prune logs automatically.                                                                                      | Configure retention; generate logs; verify rotation/pruning occurs.                     |                        | FUNC-SET-002                                           |
| FUNC-AUD-004   | Audit export (optional) | The system shall support exporting the audit log for troubleshooting, with secrets redacted.                                                                                    | Export audit log; verify format and absence of secrets.                                 |                         | FUNC-AUD-002                                           |

#### 9.11 Secrets Management and Cryptography

| requirement ID | requirement title              | requirement body (including "shall" statements)                                                                                                                   | verification plan                                                                                | unit test                                     | parent requirement ID (if it is a derived requirement) |
| -------------- | ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | --------------------------------------------- | ------------------------------------------------------ |
| SEC-CRY-001    | Encryption at rest             | The system shall encrypt financial data at rest (database and/or sensitive fields) using modern, vetted cryptography.                                             | Inspect storage; verify encrypted DB or encrypted sensitive fields; review crypto configuration. |       | SYS-003                                                |
| SEC-CRY-002    | Key storage                    | The system shall store encryption keys in an OS credential store or server-side secret store and shall not hardcode keys in source code or configs.               | Code review and runtime inspection; verify key retrieval from secure store.                      |           | SYS-003                                                |
| SEC-CRY-003    | Encrypted backups              | The system shall encrypt backups with authenticated encryption and shall require a passphrase/key for restore.                                                    | Attempt to read backup; confirm unreadable; restore requires key and validates integrity.        |       | FUNC-BKP-001                                           |
| SEC-CRY-004    | Secret rotation and revocation | The system shall support revoking Plaid access by deleting item tokens and shall support regenerating application encryption keys with a re-encryption procedure. | Unlink and confirm token invalidation; rotate keys and confirm data still decrypts.              | | SYS-003                                                |

#### 9.12 Access Control and Session Security

| requirement ID | requirement title        | requirement body (including "shall" statements)                                                                                                                             | verification plan                                                          | unit test                                      | parent requirement ID (if it is a derived requirement) |
| -------------- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------ |
| SEC-ACC-001    | App access gate          | The system shall require an application access gate (OS account restriction, biometric/PIN, or local secret) before displaying financial data.                              | Launch app; confirms locked by default; unlock required.                   | | SYS-003                                                |
| SEC-ACC-002    | Session timeout          | The system shall lock the app after a configurable period of inactivity and shall clear sensitive UI state on lock.                                                         | Idle beyond timeout; confirm lock; verify sensitive views not visible.     |  | SEC-ACC-001                                            |
| SEC-ACC-003    | Unlock configuration     | The system shall allow configuring unlock mechanism (where supported) and shall store unlock secrets only in secure storage.                                                | Change unlock method; verify persistence and secure storage.               |    | SEC-ACC-001                                            |
| SEC-ACC-004    | Authorization boundaries | If a client-server architecture is used, the system shall enforce authorization on all API endpoints and shall not trust client-provided identifiers for access to secrets. | Attempt unauthorized API calls; verify 401/403; verify server-side checks. |             | SYS-003                                                |

#### 9.13 Transport and Network Security

| requirement ID | requirement title         | requirement body (including "shall" statements)                                                                                          | verification plan                                                                  | unit test                                  | parent requirement ID (if it is a derived requirement) |
| -------------- | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------ | ------------------------------------------------------ |
| SEC-NET-001    | TLS enforcement           | The system shall enforce TLS for all network communications and shall validate certificates (no insecure skip/accept-all).               | Dynamic test with invalid cert; ensure connection fails.                           | | SYS-003                                                |
| SEC-NET-002    | Secure local endpoints    | If local APIs are exposed (loopback), the system shall bind to localhost only and shall require authentication for sensitive operations. | Inspect bind address; attempt remote access; ensure blocked; verify auth required. |             | SEC-ACC-004                                            |
| SEC-NET-003    | Rate limiting and backoff | The system shall implement retry with exponential backoff for transient errors and shall respect Plaid rate limits.                      | Simulate 429 and transient failures; verify backoff and stop conditions.           |  | FUNC-ACCT-007                                          |

#### 9.14 Secure Coding, Data Handling, and Privacy Controls

| requirement ID | requirement title    | requirement body (including "shall" statements)                                                                                                                   | verification plan                                                                 | unit test                                        | parent requirement ID (if it is a derived requirement) |
| -------------- | -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------ | ------------------------------------------------------ |
| SEC-DATA-001   | No secrets in client | The system shall not embed Plaid client\_secret or other provider secrets in any client-distributed artifact.                                                      | Binary/string scan and code review; validate secrets only on server side.         | | SYS-003                                                |
| SEC-DATA-002   | Logging policy       | The system shall implement structured logging with redaction and shall prevent logging of access tokens, full account numbers, or raw payloads by default.        | Run error scenarios; inspect logs; verify redaction rules applied.                |                   | FUNC-AUD-002                                           |
| SEC-DATA-003   | Input validation     | The system shall validate and sanitize all user-provided inputs (notes, tags, category names) and shall prevent injection into queries, exports, or UI rendering. | Fuzz inputs; attempt injection strings; verify safe behavior.                     |         | SYS-003                                                |
| SEC-DATA-004   | Dependency hygiene   | The system shall pin dependencies, maintain a lockfile, and shall run automated vulnerability checks as part of CI/local build.                                   | Review build pipeline; confirm checks run and fail on critical issues.            |       | SYS-003                                                |
| SEC-DATA-005   | Data minimization    | The system shall store only the minimum provider data required for functionality and shall allow disabling retention of raw provider payloads.                    | Toggle retention off; verify raw payloads not stored; functionality remains.      |              | FUNC-SET-002                                           |
| SEC-DATA-006   | Data deletion        | The system shall support deleting all local financial data and secrets (wipe) and shall confirm completion.                                                       | Run wipe; verify db removed and secrets cleared; app reset.                       |              | FUNC-BKP-004                                           |
| SEC-DATA-007   | Provenance integrity | The system shall preserve provenance markers for user overrides and shall not overwrite user-edited fields during sync unless explicitly reset by the user.       | Edit category; sync; confirm unchanged; use reset control (if present) to revert. |    | FUNC-SYNC-004                                          |

### 10. Data Model (Conceptual, MVP)

* Institution
* PlaidItem (institution connection)
* Account (belongs to item; type/subtype; mask; balances)
* Transaction (provider ids; posted/pending; category; user overrides; flags; splits; provenance)
* Category (hierarchy; active flag)
* Budget (month; category; amount)
* Tag (optional MVP)
* BalanceSnapshot (account; date; balance)

### 11. UX Requirements (MVP)

* “Uncategorized” queue for fast triage.
* Bulk actions: set category, exclude, mark transfer.
* Clear indicators for overridden fields.
* Global search and filter-first transaction exploration.
* Consistent month navigation across budget and reports.

### 12. Non-functional Requirements (MVP)

Performance and reliability

* The system shall complete a typical incremental sync within a reasonable time for personal datasets and provide progress/status.
* The UI shall remain responsive during sync by using background tasks/async operations.
* The system shall tolerate partial failures (one institution fails) without corrupting local state.

Maintainability

* Requirements traced to unit tests and verification plans (tables in Section 8–13).
* Centralized configuration for retention, logging, encryption, and sync behavior.

Portability

* The system shall support backup/restore between devices (subject to key/passphrase availability).

### 13. Open Questions (to finalize implementation details)

* Deployment mode: local-only (desktop) vs self-hosted server + client.
* Database choice: SQLite (local) vs Postgres (self-hosted).
* Encryption approach: full DB encryption vs field-level encryption (and which fields).
* Unlock mechanism: OS-native biometrics/PIN vs app-level PIN only.
* Plaid products: transactions only vs transactions + investments/holdings + liabilities (balances).

### 14. Milestones (Suggested)

* M1: Plaid Link + account listing + secure token storage + manual sync
* M2: Transaction list/detail + categorization overrides + inclusion rules + search/filters
* M3: Budgets + monthly view + overspend drill-down
* M4: Dashboards/reports + net worth snapshots
* M5: Export + encsrypted backup/restore + wipe + settings + audit logging hardening
* M6: Security review pass (redaction, TLS, dependency scanning, retention enforcement)
