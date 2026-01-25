## Product Requirements Document (PRD): Personal Budgeting App (Monarch-like, single-user)

### 1. Summary

A personal budgeting and net-worth app for a single user that aggregates financial accounts via Plaid, categorizes transactions, supports budgeting and goals, and provides dashboards and exports. Although single-user, it must follow secure-by-design practices appropriate for financial data.

### 2. Goals

* Provide a unified view of accounts, transactions, budgets, cash flow, and net worth.
* Make monthly budgeting fast: automated categorization with easy manual corrections.
* Track trends over time (spend by category, income vs expenses, savings rate).
* Keep data private and secure on the user’s devices/controlled infrastructure.
* Be reliable with clear data provenance (what came from Plaid vs manual edits).

### 3. Non-goals

* Multi-user support (family sharing), subscription billing, or public distribution.
* Investing features beyond balances/holdings visibility (e.g., trading).
* Full accounting software features (invoicing, double-entry bookkeeping).
* Credit score monitoring.

### 4. Target User and Use Cases

Single user (you).

Primary use cases:

* Daily/weekly: review new transactions, fix categories, mark transfers, add notes/tags.
* Monthly: set/adjust category budgets, review budget performance, reconcile anomalies.
* Quarterly/yearly: analyze trends, plan savings goals, export for taxes or archiving.

### 5. Success Metrics (Personal)

* Time to “close” a month: ≤ 30 minutes of review/categorization.
* Categorization accuracy after learning rules: ≥ 90% auto-categorized correctly.
* Data freshness: transactions updated within Plaid-supported cadence; manual refresh works.
* No plaintext storage of sensitive tokens; no secrets in logs; encryption at rest enabled.

### 6. Assumptions and Constraints

* Accounts are linked via Plaid (Link flow) and updated via Plaid sync endpoints.
* Single-user authentication can be simpler, but app still needs strong device/app access control.
* Prefer minimal operational burden: local-first or self-hosted with low maintenance.
* Must support common account types: checking, savings, credit cards, loans, investments (balances at minimum).

### 7. MVP Scope

MVP focuses on: linking accounts, ingesting transactions, categorization, budgeting, dashboards, exports, and secure storage.

Out of MVP (later): rules engine v2, advanced forecasting, receipt scanning, shared budgets, extensive investment analytics.

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

### 9. Functional Requirements (MVP)

Account Linking and Data Ingestion

* Integrate Plaid Link to connect institutions and retrieve account metadata.
* Store Plaid item/account identifiers and sync state needed for incremental updates.
* Support manual refresh and scheduled refresh (if self-hosted) with clear last-sync timestamps.
* Handle errors gracefully: item requires re-auth, institution down, rate limit, etc.

Transactions

* Transaction list with pagination, search, filters (date range, account, category, amount).
* Transaction detail: merchant/name, date, amount, account, category, notes, tags, attachments (optional later), raw fields (read-only).
* Edits: category override, notes/tags, mark as transfer, exclude from budget, split into multiple lines.
* Deduplication strategy (provider transaction_id where available; otherwise heuristic).
* Reconciliation indicators (optional MVP): “pending” vs “posted” handling.

Categories

* Category hierarchy (e.g., parent/child) with ability to add/rename/deactivate.
* Default mapping suggestions (based on Plaid category info / merchant) but editable.

Budgets

* Monthly budget setup per category (fixed amount; optional rollover later).
* Budget view by month: planned vs actual vs remaining.
* Overspend highlighting and drill-down to transactions.

Dashboards/Reports

* Monthly overview: total income, total spend, savings (income - spend), top categories.
* Trends: spend by category over time (at least last 12 months).
* Net worth: total assets - liabilities over time (based on balances snapshots).

Data Export/Import

* Export transactions to CSV (filtered or full).
* Export budgets and categories (CSV/JSON).
* Backup/restore encrypted database (MVP requirement).

Settings

* Timezone and currency.
* Data retention options (keep all, prune old raw payloads).
* Plaid re-link flow when required.

### 10. Security and Privacy Requirements (MVP)

Data Classification

* Highly sensitive: Plaid access tokens, item identifiers, account numbers (masked), balances, transactions, notes, exports.
* Sensitive metadata: institution names, merchants, categories.

Storage Security

* Encrypt data at rest:

  * If local app: use OS keychain/credential vault for encryption keys; database encrypted (or encrypted fields).
  * If self-hosted: server-side encryption with keys stored in a secrets manager (or environment + OS-level secret store) and database encryption where feasible.
* Never store Plaid secrets (client_id/secret) in the client application; keep them server-side only.

Secrets Handling

* No secrets in logs; implement structured logging with redaction.
* Token rotation and revocation path (delete Plaid item, wipe tokens, wipe local cache).

Authentication / App Access

* Require local app lock (PIN/biometric) or OS account gating if available.
* Session timeout and auto-lock on inactivity (configurable).

Transport Security

* TLS everywhere; certificate validation enforced.
* If using a local-only mode, still treat loopback calls securely and avoid exposing admin endpoints.

Least Privilege

* Minimal scopes/products in Plaid enabled (only what’s needed).
* Principle of least privilege in app processes and database permissions.

Secure Development Practices

* Dependency scanning and lockfiles; pin versions.
* Input validation for all user-editable fields; protect against injection even in local contexts.
* Explicit threat model for: token theft, backup leakage, device compromise, export leakage.

Auditability

* Activity log (local) for major events: account linked/unlinked, backup created/restored, data deleted.

### 11. Data Model (Conceptual, MVP)

* Institution
* PlaidItem (institution connection)
* Account (belongs to item; type/subtype; mask; balance snapshots)
* Transaction (provider ids; posted/pending; category; user overrides; flags; splits)
* Category (hierarchy; active flag)
* Budget (month; category; amount)
* Tag (optional MVP)
* Note (inline on transaction)
* BalanceSnapshot (account; date; balances)

### 12. UX Requirements (MVP)

* Fast transaction triage:

  * “Uncategorized” queue
  * Bulk actions (set category, exclude, mark transfer)
* Consistent month navigation for budget/report screens.
* Clear indicator for edited vs imported fields.
* Search-first design: quick find any merchant/transaction.