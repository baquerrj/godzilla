# M6 Test Strategy
Requirements: ACC-ACCT-008, ACC-SET-003, TECH-SEC-ACC-001, TECH-SEC-ACC-002, TECH-SEC-ACC-003, TECH-SEC-NET-001, TECH-SEC-NET-002, TECH-SEC-NET-003, TECH-SEC-DATA-004, TECH-SEC-CRY-004

## Scope
This strategy covers automated tests for:
- PIN setup/unlock gating and inactivity timeout behavior
- TLS runner configuration and TLS status fingerprint exposure
- Plaid retry/backoff behavior for transient failures
- Unlink workflows (`keep`, `purge`) and sync blocking for unlinked items
- Security tooling checks (`nox -s security`)

## Automated Coverage
- Backend API:
  - `godzilla_core/tests/test_api_layer.py`
    - `test_auth_status_requires_pin_setup_when_unconfigured`
    - `test_auth_setup_unlock_and_timeout_enforcement`
    - `test_auth_setup_pin_rotation_requires_current_pin`
    - `test_auth_status_reports_tls_fingerprint_when_tls_configured`
    - `test_unlink_item_keep_marks_unlinked_and_preserves_ledger`
    - `test_unlink_item_purge_deletes_item_data`
    - `test_unlink_item_missing_records_failure_audit`
    - `test_run_api_server_rejects_partial_tls_configuration`
    - `test_run_api_server_uses_tls_files_from_environment`
- Plaid client:
  - `godzilla_core/tests/test_plaid_client.py`
    - retry/backoff and `remove_item` coverage
- Sync behavior:
  - `godzilla_core/tests/test_plaid_sync.py`
    - `test_sync_raises_for_unlinked_item`
- Tooling:
  - `godzilla_core/tests/test_tooling_config.py`
    - `test_nox_security_session_runs_vulnerability_scans`
- Frontend:
  - `ui/src/test/ApiClientTransport.test.ts`
  - `ui/src/test/AuthGatePanel.test.tsx`
  - `ui/src/test/SyncStatePanel.test.tsx`
  - `ui/src/test/App.test.tsx`

## Commands
```bash
. venv/bin/activate
python -m ruff check godzilla_core noxfile.py
python -m black --check godzilla_core noxfile.py
pytest godzilla_core/tests/test_api_layer.py godzilla_core/tests/test_plaid_client.py godzilla_core/tests/test_plaid_sync.py godzilla_core/tests/test_migrations.py godzilla_core/tests/test_tooling_config.py
cd ui
npm test -- src/test/ApiClientTransport.test.ts src/test/App.test.tsx src/test/SyncStatePanel.test.tsx src/test/AuthGatePanel.test.tsx
```

## Manual Checks
- Start API with `GODZILLA_DEV_BYPASS_PIN=0`, verify:
  - `/auth/status` shows setup required initially
  - protected routes return `423` until unlock token is provided
- Configure PIN, unlock, then set `auto_lock_minutes=1` and verify relock behavior.
- Verify unlink keep/purge outcomes from UI Sync panel actions.
- In Tauri runtime, verify cert pin success and mismatch behavior by changing `GODZILLA_TLS_CERT_SHA256`.
