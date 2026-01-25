## Product Requirements Document (PRD): Personal Budgeting App (Monarch-like, single-user)

### 1. Summary

A personal budgeting and net-worth app for a single user that aggregates financial accounts via Plaid, categorizes transactions, supports budgeting and goals, and provides dashboards and exports. Although single-user, it follows secure-by-design practices appropriate for financial data.

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

* Full accounting software features (invoicing, double-entry bookkeeping).
* Categorization accuracy after learning ≥ 90%.
* Data freshness aligns with Plaid-supported update cadence; manual refresh works.
* No plaintext storage of tokens/secrets; no secrets in logs; encryption at rest enabled.

### 6. Assumptions and Constraints

* Accounts are linked via Plaid (Link flow) and updated via Plaid sync endpoints.
* Single-user, but with strong access control and secret handling.
* Prefer minimal operational burden: local-first or self-hosted with low maintenance.
* Must support common account types: checking, savings, credit cards, loans, investments (balances at minimum).

### 7. MVP Scope

In MVP: linking accounts, syncing transactions, categorization, transaction management, monthly and per-category budgeting, dashboards, exports, encrypted backup/restore, secure storage/redaction.
Out of MVP: rules enginne v2, advanced forecasting, receipt scanning, shared budgets, investment analytics.

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

### 9. Requirements (MVP)

The tables below are the authoritative functional and system requirements for MVP. IDs are stable and can be used for tracing, test planning, and backlog items.

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
