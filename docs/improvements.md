# MVP Improvements Backlog

## Summary
This document defines a stack-ranked improvement backlog for the MVP. It is
performance-first and includes user-facing and developer QoL improvements.

Every performance item must include:
1. Profiler-based analysis
2. Generated output artifacts
3. Review-ready comparison data

## Stack and Rank Scheme

- `S1 (Now)`: highest impact + low/medium risk; immediate MVP gains
- `S2 (Next)`: medium/high impact after S1 baselines are complete
- `S3 (Later)`: lower impact polish or optional hardening

Within each stack, lower `Rank` means higher execution priority.

## Improvement Items (Stack-Ranked)

| Stack | Rank | Category | Item | Target Outcome |
|---|---:|---|---|---|
| S1 | 1 | Performance | Remove duplicate overview account fetches (`App` + `AccountsTable`) | Lower overview first-load API and render latency |
| S1 | 2 | Performance | Consolidate settings loading in Data tab (`SettingsPanel` + `ExportPanel`) | One settings request per refresh cycle |
| S1 | 3 | Performance/QoL | Add request cancellation/debounce for filter-driven API calls | Reduce request storms and stale updates |
| S1 | 4 | Performance | Isolate tab scene re-renders with memoized tab scene containers | Faster tab switches with stable UI behavior |
| S1 | 5 | Dev QoL | Standardize profiling and comparison workflow in `trace/perf/` | Repeatable evidence for every performance change |
| S2 | 1 | Performance | Optimize report query paths; apply DB/index tuning if S1 gates fail | Reduce report first-load critical path |
| S2 | 2 | Performance | Optimize balances endpoint path; apply DB/index tuning if S1 gates fail | Reduce overview critical path |
| S2 | 3 | Accessibility | Full tab keyboard pattern and focus management | Better keyboard/screen-reader navigation |
| S2 | 4 | QoL | Improve transaction filter UX (explicit apply/reset/persisted presets) | More predictable filtering workflows |
| S3 | 1 | QoL | Searchable category picker for large category lists | Faster category selection |
| S3 | 2 | Aesthetic | Visual consistency pass (spacing, density, hierarchy) | Better readability and scanning |
| S3 | 3 | Dev QoL | Build/package noise reduction and reproducibility cleanup | Cleaner build output and faster troubleshooting |

## Performance Analysis and Evidence (Mandatory)

This section is required for all S1/S2 performance items.

### 1. Profiling Methods (Required per optimization batch)

- API latency profiler: `tools/profile_first_load_latency.py`
- UI render profiler: React DevTools Profiler in `ui` browser dev mode (`npm run dev`)
- Tab-switch timing instrumentation:
  - `performance.mark` / `performance.measure`
  - Capture switch start, first-visible content ready, and settled render duration

### 2. Required Output Artifacts (Must be generated and committed/logged)

For each optimization batch (`S1`, `S2`, etc.), create timestamped artifacts in
`trace/perf/`:

- `*-api.raw.json`
- `*-api.summary.json`
- `*-api.summary.csv`
- `*-api.endpoints.csv`
- `*-ui.profiler.md`
- `*-comparison.md`

Naming convention:

`trace/perf/<batch>-<yyyymmddThhmmssZ>-<artifact>`

Example:

- `trace/perf/s1-20260226T220000Z-api.raw.json`
- `trace/perf/s1-20260226T220000Z-api.summary.json`
- `trace/perf/s1-20260226T220000Z-api.summary.csv`
- `trace/perf/s1-20260226T220000Z-api.endpoints.csv`
- `trace/perf/s1-20260226T220000Z-ui.profiler.md`
- `trace/perf/s1-20260226T220000Z-comparison.md`

### 3. Review Format (Required in each `*-comparison.md`)

Each comparison report shall include:

- Baseline artifact references
- Post-change artifact references
- p50/p95 delta table per scenario
- Top 5 slowest endpoints/components before vs after
- Decision: `PASS`, `PARTIAL`, or `FAIL`
- Next action:
  - Ship
  - Iterate S1
  - Trigger S2 DB/index gate

### 4. Stack-Rank Integration (Mandatory gate)

- S1 and S2 items cannot be marked complete without profiling artifacts.
- S2 DB/index work is only executed if post-S1 thresholds fail.
- Subjective statements like “feels faster” are not sufficient for completion.

## Benchmark Gates

Use existing API profiler baseline artifacts in `trace/perf/` as canonical seed.

Trigger S2 DB/index work only if any post-S1 scenario remains above:

- `overview_first_load` p50 > `700ms`
- `reports_first_load` p50 > `450ms`
- `data_first_load` p50 > `240ms`
- `transactions_first_load` p50 > `190ms`

## Updated Acceptance Criteria

An optimization item is complete only when:

1. Functional checks pass
2. Profiling outputs are produced
3. Before/after comparison is documented
4. Threshold result is explicit (`PASS`/`FAIL`)
5. Artifact links are listed in this file

## Assumptions

- Existing API profiler baseline artifacts under `trace/perf/` remain canonical.
- Profiling documentation is part of MVP process quality, not post-MVP work.
- This document remains in PRD MVP scope (no out-of-scope feature expansion).
