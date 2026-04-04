# Architecture Components (MVP)

Requirements: SYS-001, SYS-002, SYS-003, FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-003, FUNC-ACCT-004, FUNC-ACCT-005, FUNC-ACCT-006, FUNC-ACCT-007, FUNC-ACCT-008, FUNC-ACCT-009, FUNC-SYNC-001, FUNC-SYNC-002, FUNC-SYNC-003, FUNC-SYNC-004, FUNC-SYNC-005, FUNC-SYNC-006, FUNC-SYNC-007, FUNC-TXN-001, FUNC-TXN-002, FUNC-TXN-003, FUNC-TXN-004, FUNC-TXN-005, FUNC-TXN-006, FUNC-TXN-007, FUNC-TXN-008, FUNC-TXN-009, FUNC-CAT-001, FUNC-CAT-002, FUNC-CAT-003, FUNC-BUD-001, FUNC-BUD-002, FUNC-BUD-003, FUNC-BUD-004, FUNC-REP-001, FUNC-REP-002, FUNC-REP-003, FUNC-REP-004, FUNC-REP-005, FUNC-REP-006, FUNC-REP-007, FUNC-REP-008, FUNC-EXP-001, FUNC-EXP-002, FUNC-EXP-003, FUNC-BKP-001, FUNC-BKP-002, FUNC-BKP-003, FUNC-BKP-004, FUNC-BKP-005, FUNC-SET-001, FUNC-SET-002, FUNC-SET-003, FUNC-SET-004, FUNC-SET-005, FUNC-AUD-001, FUNC-AUD-002, FUNC-AUD-003, FUNC-AUD-004, SEC-CRY-001, SEC-CRY-002, SEC-CRY-003, SEC-CRY-004, SEC-ACC-001, SEC-ACC-002, SEC-ACC-003, SEC-ACC-004, SEC-NET-001, SEC-NET-002, SEC-NET-003, SEC-DATA-001, SEC-DATA-002, SEC-DATA-003, SEC-DATA-004, SEC-DATA-005, SEC-DATA-006, SEC-DATA-007

This document supplements `architecture-overview.md`, which is the canonical MVP architecture source.

## Goals and scope
- Define language-agnostic components, responsibilities, and interfaces for the MVP.
- Provide data contracts and invariants to guide implementation in any stack.
- Detail key workflows: Link, Sync, Offline edits and conflicts, Export, Backup/Restore, PIN access.

## Component map
| Component | Responsibilities | Inputs | Outputs | Primary requirements |
| --- | --- | --- | --- | --- |
| Desktop UI (React) | Views, forms, conflict queue, navigation | User actions | Commands, queries | SYS-001, FUNC-TXN-001, FUNC-BUD-001, FUNC-REP-001, FUNC-SYNC-007, SEC-ACC-001 |
| Tauri Host (Rust) | UI bridge, HTTPS client with cert pinning, sidecar lifecycle | UI commands | HTTPS calls, results | SEC-NET-001, SEC-NET-002 |
| Python Core (FastAPI) | Application API, orchestration | HTTPS requests | Domain outputs | SYS-001, FUNC-BUD-004, FUNC-SYNC-004, SEC-DATA-007 |
| Sync Engine | Incremental sync, idempotency, pending->posted, cursor | Sync trigger, Plaid deltas | Upserts, conflicts | FUNC-SYNC-001..007 |
| Conflict Service | Conflict detection, queue, resolution | Local edits, provider updates | Conflict records, resolutions | FUNC-SYNC-006, FUNC-SYNC-007 |
| Data Store | Repositories, transactions, settings, retention | Reads/writes | Durable data | SEC-CRY-001, FUNC-SET-002 |
| Domain Services | Transactions, categories, budgets, reports | App core inputs | Computed outputs | FUNC-TXN-001..009, FUNC-CAT-001..003, FUNC-BUD-001..004, FUNC-REP-001..008 |
| Export Service | CSV/JSON export with privacy controls | Filters, export options | Files | FUNC-EXP-001..003 |
| Backup/Restore | Encrypted backup, restore, wipe | Passphrase, target file | Encrypted files, restored state | FUNC-BKP-001..005, SEC-CRY-003 |
| Security Services | PIN gate, secrets, crypto, redaction | Auth events, secrets requests | Access decisions, encrypted blobs | SEC-ACC-001..003, SEC-CRY-001..002, FUNC-AUD-002 |
| Audit Logger | Structured audit events + redaction + retention | Event data | Log entries | FUNC-AUD-001..004 |
| Scheduler (optional) | Scheduled sync/backup | Schedule config | Triggered jobs | FUNC-ACCT-006, FUNC-BKP-005, FUNC-SET-004 |

## Interfaces and contracts (language-agnostic)

### UI to Application Core
Commands:
- `linkInstitution()`
- `refreshSync()`
- `updateTransaction(transaction_id, patch)`
- `splitTransaction(transaction_id, splits[])`
- `setBudget(month, category_id, amount)`
- `exportTransactions(filter, options)`
- `exportBudgets(options)`
- `createBackup(passphrase, target_path)`
- `restoreBackup(passphrase, source_path)`
- `wipeLocalData(confirm_token)`
- `resolveConflict(conflict_id, resolution_choice)`

Queries:
- `getAccounts()`
- `getTransactions(filter, page)`
- `getBudgets(month)`
- `getReports(range)`
- `getConflicts()`
- `getSettings()`

Transport (stack decision):
- UI invokes Tauri commands, which call the local FastAPI service over HTTPS on localhost.
- The Tauri host pins the FastAPI certificate to enforce encrypted local transport.

### Application Core to Services
- Implemented as Python FastAPI handlers and domain services behind the local HTTPS API.
- Uses transaction-scoped units of work for sync ingestion and conflict creation.
- Enforces inclusion rules (transfers/excluded) consistently across budgets and reports.
- Ensures provenance markers are set for user overrides and preserved across sync.

### Sync Engine
Interface:
- `startIncrementalSync()` -> `SyncRunResult`
- `resumeSync(sync_run_id)` -> `SyncRunResult`
- `getLastSyncStatus()` -> `SyncStatus`

Behavior:
- Uses persisted cursor for incremental sync.
- Idempotently upserts by provider transaction ID or fallback heuristic.
- Maps pending->posted transitions without double counting.
- Delegates conflict detection to Conflict Service.

### Conflict Service
Interface:
- `detectConflicts(entity_type, entity_id, incoming_fields)` -> `Conflict[]`
- `queueConflicts(conflicts[])`
- `resolveConflict(conflict_id, choice)`

Behavior:
- Detects conflicts on any user-editable field.
- Local edits are preserved until user resolution.
- Resolution updates provenance (user or provider source).

### Data Store
Repositories:
- Accounts, Transactions, Categories, Budgets, Reports, Settings, Conflicts, AuditLogs.
- Uses parameterized queries, enforces retention policies.
- Stores raw provider payloads only when retention is enabled.

### Security Services
- `AuthGate`: `lock()`, `unlock(pin)`, `isUnlocked()`; enforces timeout.
- `Crypto`: encrypt/decrypt DB, backup, and sensitive blobs with authenticated encryption.
- `Secrets`: get/set/delete tokens and encryption keys in secure storage.
- `Redaction`: redact structured logs and sensitive fields by default.

## Stack-specific notes (MVP)
- Tauri v2 bundles the Python FastAPI sidecar via `externalBin`.
- FastAPI runs on loopback with HTTPS; a per-install certificate is generated and pinned in the Tauri host.
- SQLite is encrypted using SQLCipher via `sqlcipher3-binary` (self-contained wheels).
- Secrets are stored in a separate SQLCipher DB at `GODZILLA_SECRETS_PATH` using `GODZILLA_SECRETS_KEY`.
- Python sidecar is packaged with PyInstaller.

## Data contracts and invariants

### Core entities
UML-style class diagram provides the clearest view of entity fields and relationships.

```mermaid
classDiagram
  class Institution {
    +id (uuid)
    +name (string)
    +plaid_institution_id (string, provider id)
    +created_at_utc (timestamp)
    +created_at_tz (string)
    +created_at_offset_minutes (int)
  }
  class PlaidItem {
    +id (uuid)
    +provider_item_id (string)
    +institution_id (uuid, fk Institution.id)
    +access_token_ref (string, secret ref)
    +status (enum)
    +last_sync_at_utc (timestamp)
    +last_sync_at_tz (string)
    +last_sync_at_offset_minutes (int)
    +created_at_utc (timestamp)
    +created_at_tz (string)
    +created_at_offset_minutes (int)
  }
  class Account {
    +id (uuid)
    +item_id (uuid, fk PlaidItem.id)
    +provider_account_id (string)
    +name (string)
    +type (enum)
    +subtype (string)
    +mask (string)
    +balance (decimal)
    +owner_names (string[])
    +created_at_utc (timestamp)
    +created_at_tz (string)
    +created_at_offset_minutes (int)
  }
  class Transaction {
    +id (uuid)
    +account_id (uuid, fk Account.id)
    +date (date)
    +amount (decimal)
    +currency (string)
    +status (enum)
    +category_id (uuid, fk Category.id)
    +flags (string[])
    +notes (string, nullable)
    +tags (string[])
    +splits (json[])
    +created_at_utc (timestamp)
    +created_at_tz (string)
    +created_at_offset_minutes (int)
    +updated_at_utc (timestamp)
    +updated_at_tz (string)
    +updated_at_offset_minutes (int)
  }
  class Category {
    +id (uuid)
    +name (string)
    +parent_id (uuid, nullable)
    +active (bool)
  }
  class Budget {
    +id (uuid)
    +month (date)
    +category_id (uuid, fk Category.id)
    +amount (decimal)
  }
  class BalanceSnapshot {
    +id (uuid)
    +account_id (uuid, fk Account.id)
    +date (date)
    +balance (decimal)
  }
  class Conflict {
    +conflict_id (uuid)
    +entity_type (enum)
    +entity_id (uuid)
    +field_name (string)
    +local_value (json)
    +provider_value (json)
    +local_updated_at_utc (timestamp)
    +local_updated_at_tz (string)
    +local_updated_at_offset_minutes (int)
    +provider_updated_at_utc (timestamp)
    +provider_updated_at_tz (string)
    +provider_updated_at_offset_minutes (int)
    +status (enum)
    +resolution_choice (enum)
    +resolved_at_utc (timestamp, nullable)
    +resolved_at_tz (string, nullable)
    +resolved_at_offset_minutes (int, nullable)
    +sync_cursor_or_event_id (string or uuid)
  }
  class AuditLog {
    +id (uuid)
    +event_type (enum)
    +timestamp_utc (timestamp)
    +timestamp_tz (string)
    +timestamp_offset_minutes (int)
    +redacted_payload (json)
  }
  class Settings {
    +timezone (string)
    +currency (string)
    +retention_policy (json)
    +export_defaults (json)
    +sync_schedule (json)
    +backup_schedule (json)
    +pin_config (json)
    +created_at_utc (timestamp)
    +created_at_tz (string)
    +created_at_offset_minutes (int)
    +updated_at_utc (timestamp)
    +updated_at_tz (string)
    +updated_at_offset_minutes (int)
  }

  Institution "1" --> "many" PlaidItem
  PlaidItem "1" --> "many" Account
  Account "1" --> "many" Transaction
  Account "1" --> "many" BalanceSnapshot
  Category "1" --> "many" Transaction
  Category "1" --> "many" Budget
  Category "1" --> "many" Category : parent/child
```

Timestamp metadata: any timestamp field is stored as a UTC value plus `*_tz` (IANA timezone ID) and `*_offset_minutes` at the time of write.

### Provenance model
- Each user-editable field maintains a source marker: `provider` or `user`.
- Provider raw values are stored separately for audit/debug (subject to retention).
- User edits must not be overwritten by provider data unless resolved in conflict queue.

### Transaction invariants
- Split total equals original transaction amount.
- Transfer/excluded flags are honored by budgets and reports.
- Pending and posted states reconcile into a single posted transaction.

## Key workflows

### Plaid Link and token exchange
```mermaid
sequenceDiagram
  participant U as User
  participant UI as Desktop UI
  participant CORE as Application Core
  participant PLAID as Plaid API
  participant SEC as Secrets Store
  participant DB as Data Store

  U->>UI: Link institution
  UI->>CORE: linkInstitution()
  CORE->>PLAID: Start Link flow
  PLAID-->>CORE: public_token
  CORE->>PLAID: Exchange for access_token
  CORE->>SEC: Store access_token
  CORE->>PLAID: Fetch accounts + identity
  CORE->>DB: Persist institution, item, accounts, owner names
```

### Incremental sync with conflicts
```mermaid
sequenceDiagram
  participant UI as Desktop UI
  participant CORE as Application Core
  participant SYNC as Sync Engine
  participant PLAID as Plaid API
  participant CONFLICT as Conflict Service
  participant DB as Data Store

  UI->>CORE: refreshSync()
  CORE->>SYNC: startIncrementalSync()
  SYNC->>PLAID: Fetch deltas (cursor)
  PLAID-->>SYNC: Added/Modified/Removed
  SYNC->>CONFLICT: detectConflicts(incoming)
  CONFLICT-->>SYNC: conflicts
  SYNC->>DB: Apply non-conflicting updates
  SYNC->>DB: Persist conflicts
  SYNC-->>CORE: SyncRunResult
```

### Offline edits and conflict queue
```mermaid
sequenceDiagram
  participant U as User
  participant UI as Desktop UI
  participant CORE as Application Core
  participant DB as Data Store
  participant SYNC as Sync Engine
  participant CONFLICT as Conflict Service

  U->>UI: Edit transaction offline
  UI->>CORE: updateTransaction(patch)
  CORE->>DB: Save edit + provenance
  U->>UI: Later sync
  UI->>CORE: refreshSync()
  CORE->>SYNC: startIncrementalSync()
  SYNC->>CONFLICT: detectConflicts(incoming)
  CONFLICT->>DB: Persist conflict
  U->>UI: Resolve conflict
  UI->>CORE: resolveConflict()
  CORE->>DB: Apply chosen value + close conflict
```

### Backup, restore, and wipe
```mermaid
sequenceDiagram
  participant UI as Desktop UI
  participant CORE as Application Core
  participant BK as Backup Service
  participant CRY as Crypto Service
  participant DB as Data Store
  participant SEC as Secrets Store

  UI->>CORE: createBackup(passphrase, path)
  CORE->>DB: Export database snapshot
  CORE->>CRY: Encrypt snapshot (AEAD)
  CORE->>BK: Write backup file

  UI->>CORE: restoreBackup(passphrase, path)
  CORE->>BK: Read backup file
  CORE->>CRY: Decrypt + verify integrity
  CORE->>DB: Restore clean state

  UI->>CORE: wipeLocalData(confirm)
  CORE->>DB: Secure delete database
  CORE->>SEC: Delete secrets
```

### PIN access gate
```mermaid
stateDiagram-v2
  [*] --> Locked
  Locked --> Unlocked: unlock(pin)
  Unlocked --> Locked: lock()
  Unlocked --> Locked: timeout
```

## Error handling and resilience
- Sync is idempotent; replays do not duplicate transactions.
- Partial failures are isolated per institution with user-visible status.
- Conflicts are queued rather than overwritten.

## Security boundaries
- No secrets in client artifacts; tokens stored in secure store only.
- All logs pass through redaction layer.
- Retention policy governs raw provider payloads and logs.
- TLS enforced for Plaid communication; backoff for rate limits.

## Testing strategy
- Unit tests for conflict detection, provenance, budget math, and inclusion rules.
- Component tests for sync cursor behavior, backup/restore integrity, PIN gate.
- Security tests for log redaction and absence of secrets.
