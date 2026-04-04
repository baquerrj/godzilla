# Requirements Traceability Gap Analysis

Requirements: SYS-001, SYS-002, SYS-003, FUNC-ACCT-006, FUNC-ACCT-009, FUNC-TXN-009, FUNC-BKP-005

## Canonical Sources

- Machine-readable trace index: `trace/requirements.yml`
- Canonical requirement set: `docs/requirements/requirements.md`

This document summarizes the current implementation and verification gaps across the MVP requirement set. `trace/requirements.yml` is the canonical machine-readable source for code, test, and documentation trace links.

## Verification Taxonomy

- `unit`: verified by isolated backend or utility tests with local fixtures and no cross-layer orchestration.
- `component`: verified primarily through API-route tests, UI component tests, or narrow integration tests across a small set of modules.
- `system`: verified through an end-to-end workflow spanning multiple subsystems; a tracked trace stub is used when the repo does not currently have a defensible automated system test.
- `manual`: requires runtime or deployment support that is not enabled in the current repo shape.
- `security_review`: verified through an aggregate review of multiple security controls and focused tests rather than a single unit.
- `static_analysis`: verified structurally through code, schema, and packaging review rather than runtime behavior.

## Current Coverage Snapshot

- Requirement count: 80
- Implementation status counts:
  - `implemented`: 76
  - `partial`: 2
  - `optional_deployment`: 2
- Verification method counts:
  - `component`: 63
  - `unit`: 10
  - `static_analysis`: 3
  - `manual`: 2
  - `security_review`: 1
  - `system`: 1

## Unresolved Gaps

| Requirement | Status | Primary method | Current evidence | Gap | Follow-up |
| --- | --- | --- | --- | --- | --- |
| `SYS-001` | implemented | system | Architecture and app orchestration are traced; `test_sys_001_system_trace_stub` records the umbrella workflow. | No single automated test proves the full MVP flow across linking, sync, budgets, reports, export, and backup. | `TASK-TRACE-SYS-001` |
| `SYS-002` | implemented | static_analysis | Single-profile local architecture is traced; `test_sys_002_single_user_scope_trace_stub` records the absence-of-feature verification path. | The requirement is proved structurally, not by a meaningful isolated unit test. | `TASK-TRACE-SYS-002` |
| `SYS-003` | implemented | security_review | Crypto, auth, transport, redaction, and secret-handling controls are traced; `test_sys_003_secure_baseline_trace_stub` records the umbrella review path. | The baseline spans multiple controls and is not honestly reducible to one unit test. | `TASK-TRACE-SYS-003` |
| `FUNC-ACCT-006` | optional_deployment | manual | Settings persistence and API surfaces are traced; `test_func_acct_006_scheduled_refresh_trace_stub` records the deployment dependency. | Scheduler runtime and surfaced last-run results are not enabled in the current deployment shape. | `TASK-TRACE-FUNC-ACCT-006` |
| `FUNC-ACCT-009` | partial | component | Owner names are ingested and returned by the API; backend tests cover ingestion and accounts payload shape. | [AccountsTable.tsx](/home/baquerrj/projects/godzilla/ui/src/components/AccountsTable.tsx) does not render owner names, so the UI half of the requirement is incomplete. | `TASK-TRACE-FUNC-ACCT-009` |
| `FUNC-TXN-009` | partial | unit | Fallback ID generation is deterministic and tested in sync ingestion tests. | The current implementation does not evidence "flag conflicts for review" when duplicates arrive without provider IDs. | `TASK-TRACE-FUNC-TXN-009` |
| `FUNC-BKP-005` | optional_deployment | manual | Backup creation and restore are traced; `test_func_bkp_005_backup_scheduling_trace_stub` records the scheduling gap. | Scheduled backup orchestration and retention-count enforcement are not implemented in the current deployment shape. | `TASK-TRACE-FUNC-BKP-005` |

## Notes

- Requirements verified at the `component`, `system`, `manual`, `security_review`, or `static_analysis` levels still have automated trace stubs or concrete automated tests linked from `trace/requirements.yml`.
- The requirements table in `docs/requirements/requirements.md` is aligned to the same trace data so reviewers can inspect human-readable verification coverage without opening the YAML index first.
