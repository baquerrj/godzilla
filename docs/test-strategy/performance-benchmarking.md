# Performance Benchmarking

Requirements: ACC-UX-001, ACC-UX-002, ACC-UX-003, ACC-UX-004

## Purpose

This document is the canonical Linux-first runbook for rerunning the
responsiveness and layout benchmark locally. The benchmark uses a deterministic
dataset, a local FastAPI sidecar, the Vite dev server, and a Playwright browser
run so results are reproducible and tied directly to the MVP UX requirements.

Use this when you need to:

- verify `ACC-UX-001` through `ACC-UX-004`
- confirm that a UI or API change did not regress responsiveness
- regenerate `ui/perf-results/metrics.json` and failure artifacts

## Reference Dataset

- Generator: `python3 -m godzilla_core.scripts.seed_benchmark_dataset`
- Deterministic seed: `20260403`
- Shape:
  - about `10` linked accounts
  - `15,000` transactions
  - budgets, balance snapshots, tags, splits, conflicts, settings, and linked-item sync state
  - at least one account with owner metadata

## Prerequisites

- Linux local development environment prepared per [dependencies.md](../setup/dependencies.md)
- Python virtual environment created at `venv/`
- editable Python install completed:

```bash
source venv/bin/activate
python3 -m pip install -e ".[dev]"
```

- UI dependencies installed:

```bash
cd ui
npm install
```

## One-Time Setup

Install the Playwright browser runtime once per machine or whenever Playwright
is upgraded:

```bash
cd ui
npx playwright install chromium
```

## Terminal Layout

Use four terminals so the run is easy to repeat:

- Terminal 1: dataset seeding and preflight checks
- Terminal 2: API sidecar
- Terminal 3: Vite UI dev server
- Terminal 4: Playwright benchmark run

## Preflight Checks

Before each benchmark run:

1. Make sure ports `8787` and `1420` are free or already owned by the intended
   benchmark processes.
2. Activate the Python virtual environment in any shell that runs Python
   commands.
3. Use the same `GODZILLA_API_TOKEN` in both the API shell and the UI shell.
4. Set `GODZILLA_DEV_BYPASS_PIN=1` for the API shell so the browser harness can
   enter the app without manual unlock steps.
5. If you need a non-default base URL, export `GODZILLA_PERF_BASE_URL` before
   running `npm run perf`.

Useful checks:

```bash
ss -ltn '( sport = :8787 or sport = :1420 )'
curl -I http://127.0.0.1:1420
curl -s http://127.0.0.1:8787/health || true
```

The UI check should succeed before the benchmark starts. The API health probe is
optional because this project does not currently expose a dedicated health
endpoint; a connection refusal still tells you the sidecar is not running.

## Dataset Seeding

In Terminal 1, seed a clean benchmark dataset into a temporary directory:

```bash
source venv/bin/activate
mkdir -p /tmp/godzilla-benchmark
python3 -m godzilla_core.scripts.seed_benchmark_dataset \
  --db-path /tmp/godzilla-benchmark/app.db \
  --db-key benchmark-db-key \
  --secrets-path /tmp/godzilla-benchmark/secrets.db \
  --secrets-key benchmark-secrets-key
```

Expected result:

- the command prints a JSON summary describing the seeded dataset
- `/tmp/godzilla-benchmark/app.db` and `/tmp/godzilla-benchmark/secrets.db`
  exist afterward

## API Startup

In Terminal 2, start the API sidecar against the seeded dataset:

```bash
source venv/bin/activate
export GODZILLA_DB_PATH=/tmp/godzilla-benchmark/app.db
export GODZILLA_DB_KEY=benchmark-db-key
export GODZILLA_SECRETS_PATH=/tmp/godzilla-benchmark/secrets.db
export GODZILLA_SECRETS_KEY=benchmark-secrets-key
export GODZILLA_API_TOKEN=test-api-token
export GODZILLA_DEV_BYPASS_PIN=1
python3 -m godzilla_core.scripts.run_api_server --host 127.0.0.1 --port 8787
```

Expected result:

- the process stays running
- Uvicorn binds to `127.0.0.1:8787`
- no authentication or migration error appears on startup

## UI Startup

In Terminal 3, start the Vite UI dev server:

```bash
cd ui
export GODZILLA_API_TOKEN=test-api-token
npm run dev
```

Expected result:

- Vite binds to port `1420`
- `http://127.0.0.1:1420` loads in a browser
- the dev proxy forwards `/api/*` requests to the Python sidecar on `8787`

## Benchmark Execution

In Terminal 4, run the benchmark:

```bash
cd ui
npm run perf
```

For visual debugging instead of headless execution:

```bash
cd ui
npm run perf:headed
```

The benchmark uses `http://127.0.0.1:1420` by default. Override this only when
you are intentionally running the UI on a different base URL:

```bash
cd ui
export GODZILLA_PERF_BASE_URL=http://127.0.0.1:1420
npm run perf
```

## Outputs

- Metrics JSON: `ui/perf-results/metrics.json`
- Failure screenshots, videos, and traces: `ui/perf-results/artifacts/`
- Dataset seed summary: stdout from `seed_benchmark_dataset`

On a successful run, inspect `ui/perf-results/metrics.json` for:

- per-test pass/fail status
- timing annotations emitted by the Playwright spec
- the exact requirement-aligned test names for `ACC-UX-001` through
  `ACC-UX-004`

## Thresholds

- `ACC-UX-001`: primary views render within `1.0s`
- `ACC-UX-002`: transaction filter/search interactions respond within `500ms`
- `ACC-UX-003`: dashboard/view switching responds within `500ms`
- `ACC-UX-004`: layout remains intact at `1024x700`, `1280x800`, and `1440x900`

## Cleanup

When the run is complete:

- stop the Playwright process if still running
- stop the Vite dev server
- stop the FastAPI sidecar
- optionally delete `/tmp/godzilla-benchmark/` if you do not need to rerun
  against the same seeded dataset

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `Executable doesn't exist` for Chromium | Playwright browser runtime is not installed | Run `cd ui && npx playwright install chromium` |
| `ERR_CONNECTION_REFUSED` at `http://127.0.0.1:1420/` | Vite dev server is not running or bound to a different port | Start `npm run dev` in `ui/` and confirm port `1420` is listening |
| API requests fail from the UI | `GODZILLA_API_TOKEN` differs between API and UI shells | Use the same token value in both terminals |
| Browser lands on auth flow instead of the app | API shell did not set `GODZILLA_DEV_BYPASS_PIN=1` | Restart the API with `GODZILLA_DEV_BYPASS_PIN=1` |
| Benchmark uses the wrong target URL | `GODZILLA_PERF_BASE_URL` is set incorrectly | Unset it or set it to the correct UI base URL |
| Vite logs page reloads referencing `perf-results/` during the run | Playwright writes traces and screenshots under the Vite project root, which the dev server notices | The benchmark can still complete, but compare timings only against runs performed the same way and inspect artifacts before treating a regression as product behavior |
| No useful output after a failed run | Results directory not inspected | Check `ui/perf-results/metrics.json` and `ui/perf-results/artifacts/` |
