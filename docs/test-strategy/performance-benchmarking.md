# Performance Benchmarking

Requirements: ACC-UX-001, ACC-UX-002, ACC-UX-003, ACC-UX-004

## Purpose

This harness provides repeatable responsiveness and layout verification against a representative local dataset instead of ad hoc manual spot checks.

## Reference Dataset

- Generator: `python3 -m godzilla_core.scripts.seed_benchmark_dataset`
- Deterministic seed: `20260403`
- Shape:
  - about `10` linked accounts
  - `15,000` transactions
  - budgets, balance snapshots, tags, splits, conflicts, settings, and linked-item sync state
  - at least one account with owner metadata

## Running

1. Seed the encrypted benchmark databases:

```bash
source venv/bin/activate
python3 -m godzilla_core.scripts.seed_benchmark_dataset \
  --db-path /tmp/godzilla-benchmark/app.db \
  --db-key benchmark-db-key \
  --secrets-path /tmp/godzilla-benchmark/secrets.db \
  --secrets-key benchmark-secrets-key
```

2. Start the API sidecar against the seeded dataset with PIN bypass enabled for harness access:

```bash
source venv/bin/activate
export GODZILLA_DB_PATH=/tmp/godzilla-benchmark/app.db
export GODZILLA_DB_KEY=benchmark-db-key
export GODZILLA_SECRETS_PATH=/tmp/godzilla-benchmark/secrets.db
export GODZILLA_SECRETS_KEY=benchmark-secrets-key
export GODZILLA_API_TOKEN=test-api-token
export GODZILLA_DEV_BYPASS_PIN=1
python3 -m godzilla_core.scripts.run_api_server
```

3. Start the UI in Vite dev mode so the browser harness can use the existing `/api` proxy:

```bash
cd ui
export GODZILLA_API_TOKEN=test-api-token
npm run dev
```

4. Run the opt-in Playwright suite:

```bash
cd ui
npm run perf
```

## Outputs

- Metrics JSON: `ui/perf-results/metrics.json`
- Failure screenshots, videos, and traces: `ui/perf-results/artifacts/`

## Thresholds

- `ACC-UX-001`: primary views render within `1.0s`
- `ACC-UX-002`: transaction filter/search interactions respond within `500ms`
- `ACC-UX-003`: dashboard/view switching responds within `500ms`
- `ACC-UX-004`: layout remains intact at `1024x700`, `1280x800`, and `1440x900`
