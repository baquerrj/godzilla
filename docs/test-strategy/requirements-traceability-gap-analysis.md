# Requirements Traceability Gap Analysis

Requirements: ACC-SYS-001, ACC-SYS-002, ACC-SYS-003, ACC-ACCT-006, ACC-ACCT-009, ACC-TXN-009, ACC-BKP-005, ACC-UX-001, ACC-UX-002, ACC-UX-003, ACC-UX-004, TECH-ACCT-006-CONFIG, TECH-ACCT-006-RUNTIME, TECH-ACCT-009-INGEST, TECH-ACCT-009-API, TECH-ACCT-009-UI, TECH-TXN-009-FALLBACK, TECH-TXN-009-CONFLICT, TECH-SEC-CRY-003-ENVELOPE, TECH-SEC-CRY-003-INTEGRITY, TECH-SEC-CRY-003-RESTORE

## Canonical Sources

- Machine-readable trace index: `trace/requirements.yml`
- Canonical requirement set: `docs/requirements/requirements.md`

This document summarizes the layered agile verification model now used by the repo. Acceptance requirements capture product behavior. Technical requirements capture derived implementation behavior that supports an acceptance requirement and usually carries the lower-level automated evidence.

## Verification Taxonomy

- `acceptance`: user-visible or business-level behavior
- `unit`: isolated logic or module behavior with no cross-layer orchestration
- `integration`: backend multi-module or real local resource interaction without an API or UI boundary
- `component`: API route or UI component behavior through a public boundary
- `system`: end-to-end workflow spanning multiple subsystems
- `manual`: verification that depends on runtime or deployment support not enabled in the current repo shape
- `security_review`: aggregated verification across multiple security controls
- `static_analysis`: structural verification through code, schema, packaging, or configuration review

## Current Coverage Snapshot

- Requirement count: 94
- Requirement type counts:
  - `acceptance`: 65
  - `technical`: 29
- Implementation status counts:
  - `implemented`: 83
  - `partial`: 4
  - `optional_deployment`: 3
  - `not_implemented`: 4
- Verification method counts:
  - `component`: 69
  - `unit`: 7
  - `integration`: 6
  - `manual`: 7
  - `static_analysis`: 3
  - `system`: 1
  - `security_review`: 1

## Key Findings

- The repo is now explicitly split between acceptance and technical requirements, which is closer to agile verification practice than the prior single-layer model.
- The taxonomy now distinguishes `integration` from `component`, so backend tests using real SQLCipher and filesystem resources are no longer forced into the `unit` bucket. `MigrationRunnerTests` and persisted sync-conflict tests are now classified as `integration`.
- Verification is still component-heavy. That is acceptable for an MVP with a strong API/UI boundary, but the next improvement would be adding more explicit technical requirements and integration-level traces for sync, persistence, and retention behavior.
- Responsiveness and resize requirements are now formalized as acceptance requirements, but they are intentionally verified by manual benchmark methodology rather than jsdom or API timing assertions.

## Unresolved Gaps

| Requirement | Type | Status | Primary method | Gap | Follow-up |
| --- | --- | --- | --- | --- | --- |
| `ACC-SYS-001` | acceptance | implemented | system | No single automated test proves the full MVP flow across linking, sync, budgets, reports, export, and backup. | `TASK-TRACE-ACC-SYS-001` |
| `ACC-SYS-002` | acceptance | implemented | static_analysis | Single-user scope is proved structurally rather than through a meaningful isolated runtime test. | `TASK-TRACE-ACC-SYS-002` |
| `ACC-SYS-003` | acceptance | implemented | security_review | The secure-by-design baseline spans auth, crypto, transport, redaction, and secret-handling controls rather than one automated test. | `TASK-TRACE-ACC-SYS-003` |
| `ACC-ACCT-006` | acceptance | optional_deployment | manual | Scheduler runtime support is not enabled in the current deployment shape. | `TASK-TRACE-ACC-ACCT-006` |
| `TECH-ACCT-006-RUNTIME` | technical | optional_deployment | manual | Scheduled execution and surfaced last-run results are not implemented in the current runtime. | `TASK-TRACE-ACC-ACCT-006` |
| `ACC-ACCT-009` | acceptance | partial | component | Owner names are ingested and exposed by the API, but the UI does not yet render them. | `TASK-TRACE-ACC-ACCT-009` |
| `TECH-ACCT-009-UI` | technical | partial | component | [AccountsTable.tsx](/home/baquerrj/projects/godzilla/ui/src/components/AccountsTable.tsx) does not render owner names. | `TASK-TRACE-ACC-ACCT-009` |
| `ACC-TXN-009` | acceptance | partial | integration | Deterministic fallback dedup exists, but there is no evidence that provider-ID-less duplicates are surfaced for review. | `TASK-TRACE-ACC-TXN-009` |
| `TECH-TXN-009-CONFLICT` | technical | partial | integration | Conflict queue behavior for provider-ID-less duplicate transactions is not implemented or not evidenced. | `TASK-TRACE-ACC-TXN-009` |
| `ACC-BKP-005` | acceptance | optional_deployment | manual | Scheduled backup orchestration and retention-count enforcement are not implemented in the current deployment shape. | `TASK-TRACE-ACC-BKP-005` |
| `ACC-UX-001` | acceptance | not_implemented | manual | Primary view load responsiveness is defined, but no benchmark harness or verified evidence exists yet. | `TASK-TRACE-ACC-UX-001` |
| `ACC-UX-002` | acceptance | not_implemented | manual | Filter, search, and sort responsiveness is defined, but no benchmark harness or verified evidence exists yet. | `TASK-TRACE-ACC-UX-002` |
| `ACC-UX-003` | acceptance | not_implemented | manual | Dashboard and report switch responsiveness is defined, but no benchmark harness or verified evidence exists yet. | `TASK-TRACE-ACC-UX-003` |
| `ACC-UX-004` | acceptance | not_implemented | manual | Minimum supported desktop resize integrity is defined, but no automated or benchmarked verification exists yet. | `TASK-TRACE-ACC-UX-004` |

## Notes

- Acceptance requirements may verify honestly at `component`, `system`, `manual`, `static_analysis`, or `security_review` levels; they are not forced into unit-only evidence.
- Technical requirements are the preferred location for `unit`, `integration`, and low-level `component` evidence.
- `trace/requirements.yml` is the canonical source for the full verification mapping. The requirements table in `docs/requirements/requirements.md` intentionally shows only the primary verification artifacts.
- Use `python3 godzilla_core/scripts/validate_requirement_traceability.py` to validate requirement IDs, trace entries, `REQ:` tags, and test/code reference resolution under this taxonomy.
- Reference benchmark defaults for the responsiveness requirements are a local desktop runtime, a modern 4-core CPU with SSD and 16 GB RAM, and an MVP dataset of about 10 linked accounts and 15,000 transactions.
