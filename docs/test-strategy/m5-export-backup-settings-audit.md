# M5 Test Strategy — Export, Backup/Restore, Settings, Audit

Requirements covered: FUNC-EXP-001, FUNC-EXP-002, FUNC-EXP-003, FUNC-BKP-001, FUNC-BKP-002, FUNC-BKP-003, FUNC-BKP-004, FUNC-BKP-006, FUNC-SET-001, FUNC-SET-002, FUNC-SET-003, FUNC-SET-004, FUNC-SET-005, FUNC-AUD-001, FUNC-AUD-003, FUNC-AUD-004, FUNC-REP-006

## Automated tests

Backend (`godzilla_core/tests/test_api_layer.py`):

1. Export endpoints:
   - `test_export_transactions_csv_includes_splits_tags_and_user_fields`
   - `test_export_transactions_raw_payloads_default_is_excluded`
   - `test_export_transactions_raw_payloads_can_be_included`
   - `test_export_transactions_respects_filters`
   - `test_export_categories_budgets_json_and_csv`
   - `test_export_endpoints_auth_and_validation`
2. Backup/restore/wipe:
   - `test_backup_returns_encrypted_blob`
   - `test_restore_rejects_tampered_backup`
   - `test_restore_recovers_database_and_secrets`
   - `test_wipe_removes_database_and_secrets_files`
   - `test_reinitialize_recreates_schema_after_wipe`
   - `test_backup_restore_wipe_auth_and_validation`
3. Settings:
   - `test_get_settings_returns_bootstrap_defaults`
   - `test_put_settings_updates_and_persists`
   - `test_put_settings_rejects_invalid_values`
   - `test_put_settings_applies_retention_pruning`
4. Audit:
   - `test_audit_log_records_events_and_supports_filters`
   - `test_audit_log_csv_export`
   - `test_audit_log_retention_pruned_on_write`
   - `test_audit_log_auth_and_validation`
5. Balance name display payload:
   - `test_get_balances_returns_snapshots`

Frontend (`ui/src/test/*.test.tsx`):

1. `ExportPanel.test.tsx`
2. `DataManagementPanel.test.tsx`
3. `SettingsPanel.test.tsx`
4. `App.test.tsx` integration assertions for new panels
5. `BalancesTable.test.tsx` account name rendering

## Verification matrix

| Requirement | Verification |
| --- | --- |
| FUNC-EXP-001 | Filter-aware transaction CSV export with split expansion and editable fields |
| FUNC-EXP-002 | Categories/budgets export in CSV and JSON formats |
| FUNC-EXP-003 | Raw payload export defaults + explicit override behavior |
| FUNC-BKP-001 | Encrypted backup blob generation and attachment response |
| FUNC-BKP-002 | Tampered backup integrity failure path |
| FUNC-BKP-003 | Restore workflow recovers DB and secrets |
| FUNC-BKP-004 | Confirmed wipe removes DB/secrets and sidecars |
| FUNC-BKP-006 | Reinitialize endpoint recreates schema after wipe and UI can trigger it |
| FUNC-SET-001 | Settings bootstrap + timezone/currency update validation |
| FUNC-SET-002 | Retention config persistence and pruning side effects |
| FUNC-SET-003 | Auto-lock persistence and validation bounds |
| FUNC-SET-004 | Sync settings persistence and validation bounds |
| FUNC-SET-005 | Export-default settings roundtrip + UI defaulting |
| FUNC-AUD-001 | Major workflow events persisted as redacted audit entries |
| FUNC-AUD-003 | Audit retention pruning on settings update and write path |
| FUNC-AUD-004 | JSON/CSV audit retrieval and UI export control |
| FUNC-REP-006 | `/balances` payload includes `account_name` and UI renders it |

## Command runbook

```bash
# Backend
. venv/bin/activate
pytest godzilla_core/tests/test_api_layer.py -k "export or backup or restore or wipe or settings or audit"

# Frontend
cd ui
npm test
npm run build
```

## Manual smoke checks

1. Run the M5 verification checklist in `docs/plan.md` section "M5 verification checklist (step-by-step to run)".
2. Focus manual checks on:
   - download behavior and filenames for exports/backup
   - restore tamper-failure UX and success UX
   - wipe confirmation gating
   - settings save/reload and effects on export defaults
   - audit CSV/JSON filters against expected events
