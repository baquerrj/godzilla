# Product Vision (MVP)

This document is the canonical product and scope definition for the MVP.

Related MVP source docs:
- [Architecture](design/architecture-overview.md)
- [Requirements](requirements/requirements.md)
- [Execution plan](plan.md)

## Summary

A personal budgeting and net-worth app for a single user that aggregates financial accounts via Plaid, categorizes transactions, supports budgeting, and provides dashboards, reports, exports, and encrypted backup/restore. Although single-user, it follows secure-by-design practices appropriate for financial data.

## Goals

- Provide a unified view of accounts, transactions, budgets, cash flow, and net worth.
- Fast monthly budgeting workflow with automated categorization and easy manual corrections.
- Track trends over time (spend by category, income vs expenses, savings rate).
- Strong privacy and security for financial data.
- Clear provenance of imported vs user-edited data.
- Highly responsive desktop UI for common workflows.
- Resizable interface that maintains layout integrity across supported window sizes.

## Non-goals

- Multi-user support (family sharing), subscription billing, or public distribution.
- Trading/investment execution or deep investment analytics.
- Full accounting software features (invoicing, double-entry bookkeeping).

## Target User and Primary Use Cases

Single user.

- Daily/weekly: review new transactions, fix categories, mark transfers, add notes/tags.
- Monthly: set or adjust budgets, review budget performance, reconcile anomalies.
- Quarterly/yearly: analyze trends, plan savings goals, export data, archive backups.

## Success Metrics

- Monthly close time <= 30 minutes.
- Categorization accuracy after learning >= 90%.
- Data freshness aligns with Plaid-supported update cadence; manual refresh works.
- No plaintext storage of tokens or secrets, no secrets in logs, and encryption at rest enabled.
- Backups and restores succeed reliably and are verifiable.
- Primary views load within 1.0 second on the reference MVP dataset.
- Common filter, search, and sort interactions complete within 500 ms.
- Dashboard and view switches complete within 500 ms when data is already loaded.
- UI remains intact and usable at supported desktop sizes of 1024x700 and above.

## Assumptions and Constraints

- Deployment target for MVP is a local-only desktop app; self-hosted server plus client comes after MVP.
- Database is SQLite.
- Full-database encryption is required; no OS keychain requirement.
- Access control is app-level PIN only; primary OS target is Linux.
- Accounts are linked via Plaid (Link flow) and updated via Plaid sync endpoints; Plaid products used are Transactions (up to 24 months), Balance, and Identity.
- Single-user, but with strong access control and secret handling.
- Must support common account types: checking, savings, credit cards, loans, investments (balances at minimum).
- The app may operate offline for viewing and editing already-synced data; sync requires network access, and conflicts are queued in a dedicated conflict resolution view.
- Raw provider payloads and diagnostic logs are retained by default and remain configurable.
- Backups are password-based and stored locally.

## MVP Scope

In MVP:
- Linking accounts
- Syncing transactions
- Categorization
- Transaction management
- Offline edits with conflict resolution
- Monthly and per-category budgeting
- Dashboards and reports
- Exports
- Encrypted backup and restore
- Settings
- Audit logging
- Secure storage and redaction

Out of MVP:
- Rules engine v2
- Advanced forecasting
- Receipt scanning
- Shared budgets
- Investment analytics

## User Stories

- As a user, I can link a financial institution using Plaid and see connected accounts.
- As a user, I can refresh or sync transactions and see newly imported items.
- As a user, I can categorize transactions and the app remembers or copies my choices.
- As a user, I can mark transactions as transfer, exclude from budget, or split a transaction.
- As a user, I can resolve sync conflicts from offline edits in a dedicated conflicts view.
- As a user, I can create monthly budgets per category and see remaining amounts.
- As a user, I can view monthly cash flow (income, expenses, savings).
- As a user, I can view net worth over time from account balances.
- As a user, I can search, filter, and export transactions (CSV).
- As a user, I can back up and restore the app database securely.

## Open Questions

- Post-MVP: server plus client architecture details and hosting model.
- Post-MVP: database choice for server deployment, if needed.
