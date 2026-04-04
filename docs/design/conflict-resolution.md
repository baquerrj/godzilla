# Conflict Resolution Design (MVP)

Requirements: ACC-SYNC-004, ACC-SYNC-005, ACC-SYNC-006, ACC-SYNC-007, TECH-SEC-DATA-007, ACC-SYS-003

## Problem statement
Offline edits must be preserved across syncs while still ingesting new provider data. When an incoming change conflicts with a user edit, the system must surface the conflict and let the user decide which value to keep, without silently overwriting local edits.

## Architecture overview
Conflict resolution is an application-core service that sits between sync ingestion and persistence. It detects field-level conflicts between provider updates and user-edited values, persists conflict records, and exposes a conflict queue for batch resolution.

### Components
- Conflict Detector: compares incoming provider fields to locally edited fields and identifies conflicts.
- Conflict Store: persists conflict records in the encrypted database.
- Conflict Queue UI: lists unresolved conflicts and provides per-field resolution actions.
- Resolution Applier: applies the selected value, updates provenance, and closes the conflict.

### Flow
```mermaid
flowchart LR
  SYNC[Sync Engine] --> DETECT[Conflict Detector]
  DETECT -->|no conflict| APPLY[Apply Provider Update]
  DETECT -->|conflict| STORE[Conflict Store]
  STORE --> QUEUE[Conflict Queue UI]
  QUEUE --> RESOLVE[Resolution Applier]
  RESOLVE --> STORE
  RESOLVE --> APPLY
```

## Data model changes
Add a Conflict record to the local database:
- conflict_id (uuid)
- entity_type (transaction, account, category, budget, settings)
- entity_id
- field_name
- local_value
- provider_value
- local_updated_at_utc
- local_updated_at_tz
- local_updated_at_offset_minutes
- provider_updated_at_utc
- provider_updated_at_tz
- provider_updated_at_offset_minutes
- status (open, resolved)
- resolution_choice (local, provider)
- resolved_at_utc
- resolved_at_tz
- resolved_at_offset_minutes
- sync_cursor_or_event_id

Notes:
- Conflicts are created for any user-editable field.
- Provenance markers are preserved; local edits remain authoritative until resolution.

## API and UI changes
- Sync Engine emits conflict records instead of overwriting user edits.
- Conflict Queue UI allows batch resolution and shows before/after values.
- Resolution applies selected value and updates provenance to reflect the choice.

## Security considerations
- Conflicts are stored in the encrypted database (TECH-SEC-CRY-001).
- Conflict data never includes secrets, tokens, or raw payloads beyond policy (TECH-SEC-DATA-007).
- Access is gated behind the PIN lock (TECH-SEC-ACC-001).
- Audit logs record conflict creation and resolution with redaction (ACC-AUD-001, ACC-AUD-002).

## Tradeoffs and alternatives
- Alternative: last-write-wins. Rejected because it can silently lose offline edits.
- Alternative: auto-merge by field priority. Rejected for lack of user intent clarity.

## Testing strategy and coverage mapping
- Unit tests:
  - Detects conflict when local edit differs from provider update.
  - Does not create conflict for unchanged or provider-only fields.
  - Applies resolution choice and updates provenance.
- Component tests:
  - Offline edit + sync produces conflict queue entry.
  - User resolution updates UI state and stored record.

## Rollout and migration notes
- MVP ships with conflict queue enabled by default for offline edits.
- No migration required beyond adding the Conflict table.
