# First-Load Latency Profile (2026-02-26T01:05:02Z)

## Scope
Measured first-load API call groups used by UI tabs:
- Overview
- Transactions
- Reports
- Data

Runs per scenario: 12

Base URL: `https://127.0.0.1:19787`

Notes:
- Environment values were taken from `ui/current_env`.
- A dedicated profiling sidecar was started with `GODZILLA_DEV_BYPASS_PIN=1` to avoid lock-gate interference.
- This profile captures backend request latency for first-load call sets and critical-path duration (max concurrent request time per run).

## Scenario Latency (ms)

| Scenario | Min | P50 | Mean | P95 | Max |
|---|---:|---:|---:|---:|---:|
| overview_first_load | 805.450 | 868.650 | 890.869 | 989.139 | 1014.213 |
| transactions_first_load | 145.028 | 202.399 | 212.293 | 318.746 | 383.679 |
| reports_first_load | 462.026 | 524.452 | 524.273 | 590.362 | 606.028 |
| data_first_load | 231.025 | 285.620 | 282.997 | 316.127 | 318.054 |

## Top Endpoint Contributors

- Overview critical path is dominated by `balancesTable.getBalances` (mean 867.576 ms).
- Overview also spends significant time in duplicate account fetches:
  - `app.getAccounts` mean 237.677 ms
  - `accountsTable.getAccounts` mean 736.816 ms
- Reports critical path is driven by:
  - `reportsPanel.getNetWorth` mean 497.673 ms
  - `reportsPanel.getCashFlow` mean 458.700 ms
- Data tab does two settings calls on first-load:
  - `settingsPanel.getSettings` mean 195.447 ms
  - `exportPanel.getSettings` mean 237.115 ms

## Artifacts

- `trace/perf/first-load-latency-20260226T010502Z.raw.json`
- `trace/perf/first-load-latency-20260226T010502Z.summary.json`
- `trace/perf/first-load-latency-20260226T010502Z.summary.csv`
- `trace/perf/first-load-latency-20260226T010502Z.endpoints.csv`
