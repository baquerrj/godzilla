# Database Schema (MVP)

Requirements: SYS-001, SYS-002, SYS-003, FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-003, FUNC-ACCT-004, FUNC-ACCT-005, FUNC-ACCT-008, FUNC-ACCT-009, FUNC-SYNC-001, FUNC-SYNC-002, FUNC-SYNC-003, FUNC-SYNC-004, FUNC-SYNC-005, FUNC-SYNC-006, FUNC-SYNC-007, FUNC-TXN-001, FUNC-TXN-002, FUNC-TXN-003, FUNC-TXN-004, FUNC-TXN-005, FUNC-TXN-006, FUNC-TXN-007, FUNC-TXN-008, FUNC-TXN-009, FUNC-CAT-001, FUNC-CAT-002, FUNC-CAT-003, FUNC-BUD-001, FUNC-BUD-002, FUNC-BUD-003, FUNC-BUD-004, FUNC-REP-005, FUNC-REP-006, FUNC-SET-001, FUNC-SET-002, FUNC-SET-003, FUNC-SET-005, FUNC-AUD-001, FUNC-AUD-002, FUNC-AUD-003, SEC-CRY-001, SEC-CRY-003, SEC-ACC-001, SEC-ACC-002, SEC-ACC-003, SEC-DATA-005, SEC-DATA-006, SEC-DATA-007

## Problem statement
Define a normalized, encrypted SQLite schema that supports sync, offline edits, conflicts, budgeting, reporting, and audit logging, with retention controls and provenance tracking.

## ER overview
```mermaid
erDiagram
  INSTITUTION ||--o{ PLAID_ITEM : has
  PLAID_ITEM ||--o{ ACCOUNT : has
  ACCOUNT ||--o{ TRANSACTION_RECORD : has
  ACCOUNT ||--o{ BALANCE_SNAPSHOT : has
  CATEGORY ||--o{ TRANSACTION_RECORD : categorizes
  CATEGORY ||--o{ BUDGET : plans
  CATEGORY ||--o{ CATEGORY : parent
  TRANSACTION_RECORD ||--o{ TRANSACTION_SPLIT : splits
  TRANSACTION_RECORD ||--o{ TRANSACTION_TAG : tags
  TAG ||--o{ TRANSACTION_TAG : tagged
  TRANSACTION_RECORD ||--o{ TRANSACTION_OVERRIDE : overrides
  TRANSACTION_RECORD ||--o{ PROVIDER_RAW : raw
  CONFLICT ||--o{ CONFLICT_RESOLUTION : resolved_by

  SETTINGS ||--o{ SYNC_STATE : sync_state
  SETTINGS ||--o{ EXPORT_DEFAULTS : export_defaults
  SETTINGS ||--o{ RETENTION_POLICY : retention_policy
  SETTINGS ||--o{ PIN_CONFIG : pin_config
```

## Tables (logical)

### schema_version
- `version` (int, not null)
- `applied_at_utc` (timestamp, not null)
- `applied_at_tz` (text, not null)
- `applied_at_offset_minutes` (int, not null)

### institution
- `id` (uuid, pk)
- `name` (text, not null)
- `plaid_institution_id` (text, not null, unique)
- `created_at_utc` (timestamp, not null)
- `created_at_tz` (text, not null)
- `created_at_offset_minutes` (int, not null)

### plaid_item
- `id` (uuid, pk)
- `institution_id` (uuid, fk institution.id, not null)
- `access_token_ref` (text, not null)  // secret ref in secure store
- `status` (text enum, not null)       // linked, requires_reauth, error
- `last_sync_at_utc` (timestamp, nullable)
- `last_sync_at_tz` (text, nullable)
- `last_sync_at_offset_minutes` (int, nullable)
- `created_at_utc` (timestamp, not null)
- `created_at_tz` (text, not null)
- `created_at_offset_minutes` (int, not null)

### account
- `id` (uuid, pk)
- `item_id` (uuid, fk plaid_item.id, not null)
- `name` (text, not null)
- `type` (text enum, not null)
- `subtype` (text, nullable)
- `mask` (text, nullable)
- `balance` (decimal, nullable)
- `currency` (text, not null)
- `owner_names` (json, nullable) // list of strings
- `created_at_utc` (timestamp, not null)
- `created_at_tz` (text, not null)
- `created_at_offset_minutes` (int, not null)

### transaction_record
- `id` (uuid, pk)
- `account_id` (uuid, fk account.id, not null)
- `provider_transaction_id` (text, nullable) // may be null
- `date` (date, not null)
- `amount` (decimal, not null)
- `currency` (text, not null)
- `status` (text enum, not null) // pending, posted
- `merchant_name` (text, nullable)
- `display_name` (text, not null)
- `category_id` (uuid, fk category.id, nullable)
- `is_transfer` (bool, not null default false)
- `is_excluded` (bool, not null default false)
- `notes` (text, nullable)
- `created_at_utc` (timestamp, not null)
- `created_at_tz` (text, not null)
- `created_at_offset_minutes` (int, not null)
- `updated_at_utc` (timestamp, not null)
- `updated_at_tz` (text, not null)
- `updated_at_offset_minutes` (int, not null)

### transaction_split
- `id` (uuid, pk)
- `transaction_id` (uuid, fk transaction_record.id, not null)
- `amount` (decimal, not null)
- `category_id` (uuid, fk category.id, nullable)
- `notes` (text, nullable)

### tag
- `id` (uuid, pk)
- `name` (text, not null, unique)
- `active` (bool, not null default true)

### transaction_tag
- `transaction_id` (uuid, fk transaction_record.id, not null)
- `tag_id` (uuid, fk tag.id, not null)
- primary key (`transaction_id`, `tag_id`)

### category
- `id` (uuid, pk)
- `name` (text, not null)
- `parent_id` (uuid, fk category.id, nullable)
- `active` (bool, not null default true)

### budget
- `id` (uuid, pk)
- `month` (date, not null) // first day of month
- `category_id` (uuid, fk category.id, not null)
- `amount` (decimal, not null)

### balance_snapshot
- `id` (uuid, pk)
- `account_id` (uuid, fk account.id, not null)
- `date` (date, not null)
- `balance` (decimal, not null)
- unique (`account_id`, `date`)

### transaction_override
Tracks field-level user overrides and provenance markers.
- `id` (uuid, pk)
- `transaction_id` (uuid, fk transaction_record.id, not null)
- `field_name` (text, not null)
- `source` (text enum, not null) // provider, user
- `provider_value` (json, nullable)
- `user_value` (json, nullable)
- `updated_at_utc` (timestamp, not null)
- `updated_at_tz` (text, not null)
- `updated_at_offset_minutes` (int, not null)

### provider_raw
Raw provider payloads (subject to retention).
- `id` (uuid, pk)
- `transaction_id` (uuid, fk transaction_record.id, not null)
- `raw_payload` (json, not null)
- `created_at_utc` (timestamp, not null)
- `created_at_tz` (text, not null)
- `created_at_offset_minutes` (int, not null)

### conflict
- `conflict_id` (uuid, pk)
- `entity_type` (text enum, not null)
- `entity_id` (uuid, not null)
- `field_name` (text, not null)
- `local_value` (json, not null)
- `provider_value` (json, not null)
- `local_updated_at_utc` (timestamp, not null)
- `local_updated_at_tz` (text, not null)
- `local_updated_at_offset_minutes` (int, not null)
- `provider_updated_at_utc` (timestamp, not null)
- `provider_updated_at_tz` (text, not null)
- `provider_updated_at_offset_minutes` (int, not null)
- `status` (text enum, not null) // open, resolved
- `resolution_choice` (text enum, nullable) // local, provider
- `resolved_at_utc` (timestamp, nullable)
- `resolved_at_tz` (text, nullable)
- `resolved_at_offset_minutes` (int, nullable)
- `sync_cursor_or_event_id` (text, nullable)

### conflict_resolution
- `id` (uuid, pk)
- `conflict_id` (uuid, fk conflict.conflict_id, not null)
- `resolved_by` (text, not null) // user
- `resolved_at_utc` (timestamp, not null)
- `resolved_at_tz` (text, not null)
- `resolved_at_offset_minutes` (int, not null)
- `choice` (text enum, not null)

### audit_log
- `id` (uuid, pk)
- `event_type` (text enum, not null)
- `timestamp_utc` (timestamp, not null)
- `timestamp_tz` (text, not null)
- `timestamp_offset_minutes` (int, not null)
- `redacted_payload` (json, not null)

### settings
Single-row table (single-user scope).
- `id` (uuid, pk)
- `timezone` (text, not null)
- `currency` (text, not null)
- `created_at_utc` (timestamp, not null)
- `created_at_tz` (text, not null)
- `created_at_offset_minutes` (int, not null)
- `updated_at_utc` (timestamp, not null)
- `updated_at_tz` (text, not null)
- `updated_at_offset_minutes` (int, not null)

### retention_policy
Single-row table.
- `id` (uuid, pk)
- `retain_raw_payloads` (bool, not null default true)
- `retain_logs_days` (int, not null)
- `created_at_utc` (timestamp, not null)
- `created_at_tz` (text, not null)
- `created_at_offset_minutes` (int, not null)
- `updated_at_utc` (timestamp, not null)
- `updated_at_tz` (text, not null)
- `updated_at_offset_minutes` (int, not null)

### export_defaults
Single-row table.
- `id` (uuid, pk)
- `include_raw_payloads` (bool, not null default false)
- `created_at_utc` (timestamp, not null)
- `created_at_tz` (text, not null)
- `created_at_offset_minutes` (int, not null)
- `updated_at_utc` (timestamp, not null)
- `updated_at_tz` (text, not null)
- `updated_at_offset_minutes` (int, not null)

### pin_config
Single-row table.
- `id` (uuid, pk)
- `pin_hash` (text, not null)
- `pin_salt` (text, not null)
- `updated_at_utc` (timestamp, not null)
- `updated_at_tz` (text, not null)
- `updated_at_offset_minutes` (int, not null)

### sync_state
Single-row table for cursors and last-run state.
- `id` (uuid, pk)
- `plaid_cursor` (text, nullable)
- `last_sync_at_utc` (timestamp, nullable)
- `last_sync_at_tz` (text, nullable)
- `last_sync_at_offset_minutes` (int, nullable)
- `last_sync_status` (text, nullable)

## Constraints and indexes
- Unique index on `transaction_record.provider_transaction_id` when not null.
- Index on `transaction_record.date`, `transaction_record.amount`, `transaction_record.category_id` for filters.
- Index on `transaction_record.account_id` for list/detail views.
- Index on `conflict.status` for queue performance.
- Foreign keys enforced (PRAGMA foreign_keys=ON).

## Security considerations
- Database file is encrypted with SQLCipher (SEC-CRY-001).
- Raw provider payloads are optional and prunable based on retention policy (FUNC-SET-002, SEC-DATA-005).
- Audit log payloads must be redacted before write (FUNC-AUD-002).
- PIN secrets stored as salted hash; raw PIN is never persisted (SEC-ACC-001, SEC-ACC-003).

## Migration strategy
- Use versioned SQL migrations (e.g., `migrations/0001_init.sql`).
- Maintain a `schema_version` table with the latest applied version.
- Migrations are applied at app startup by the Python core before serving requests.

## Testing strategy
- Schema migration tests to verify creation and upgrade paths.
- Query tests for transaction filters, conflict queue, and retention pruning.
