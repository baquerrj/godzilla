# Reports Dashboard — Design Document

**Requirements:** ACC-REP-001, ACC-REP-002, ACC-REP-003, ACC-REP-004, ACC-REP-005, ACC-REP-007, ACC-REP-008

---

## Problem statement

M4 adds reporting surfaces that summarize monthly performance, show trend
data over time, and support direct drill-down into the transaction subset used
to compute each metric.

The implementation must:
- provide monthly overview totals and top categories,
- provide cash-flow and category trend time series,
- provide net-worth time series from balance snapshots,
- apply budget inclusion rules consistently for transaction-derived metrics, and
- keep report period navigation synchronized across visible widgets.

---

## API/interface changes

### New read endpoints

1. `GET /reports/monthly-overview?month=YYYY-MM`
2. `GET /reports/cash-flow?start=YYYY-MM-DD&end=YYYY-MM-DD`
3. `GET /reports/category-trends?categories=<csv>&months=<int>&end_month=YYYY-MM`  
`end_month` is optional for backward compatibility; when omitted, the server
uses the latest included transaction month.
4. `GET /reports/net-worth?start=YYYY-MM-DD&end=YYYY-MM-DD`

All endpoints require `X-API-Key` (`TECH-SEC-ACC-004` boundary).

### Shared inclusion-rule helper

`_REPORT_LINE_ITEMS_RANGE_CTE` reuses the same rules as budgets:
- posted only,
- excludes transfers,
- excludes explicitly excluded transactions,
- split-aware (parent ignored when split rows exist).

This enforces `ACC-REP-007` parity with `ACC-BUD-004`.

---

## Data model and computation notes

No schema migration is required.

- Income: `amount < 0` (reported as positive absolute value).
- Expenses: `amount > 0`.
- Net savings: `income - expenses`.
- Savings rate: `net_savings / income` when `income > 0`, else `0`.
- Net worth: `assets - liabilities` where liabilities are accounts with
  `account.type IN ('credit', 'loan')` and summed by `ABS(balance)`.

---

## UI architecture

`ReportsPanel` is integrated into `App.tsx` and shares app-level filter state
through `onDrillDown`.

```mermaid
graph TD
  RP[ReportsPanel] -->|onDrillDown| APP[App.tsx]
  APP -->|setFilterValues| TF[TransactionFilters]
  TF --> TT[TransactionsTable]
  RP -->|getMonthlyOverview| API[/reports/monthly-overview]
  RP -->|getCashFlow| API2[/reports/cash-flow]
  RP -->|getCategoryTrends| API3[/reports/category-trends]
  RP -->|getNetWorth| API4[/reports/net-worth]
```

Drill-down mappings:
- Overview income card => date range + `amount_max=-0.01`
- Overview expenses/top categories => date range + `amount_min=0.01` (+ `category_id` when relevant)
- Cash-flow row income/expense actions => month range + direction amount filter
- Category trend point => month range + `category_id` + expense direction

---

## Security considerations

- SQL is parameterized for all user-provided query inputs.
- Date/month inputs are regex-validated by FastAPI and parsed server-side.
- `start <= end` validation is enforced for range endpoints.
- Report responses include inclusion metadata and avoid exposing secrets/raw
  provider payloads.

---

## Tradeoffs

- `category-trends` keeps `categories,months` as primary API inputs for PRD
  compatibility and adds optional `end_month` to align UI date navigation.
- The UI uses table/bar-like controls instead of an external chart library to
  keep dependency scope small for MVP.

---

## Testing strategy and coverage mapping

- Backend: report endpoint math, validation, auth, and inclusion parity tests in
  `godzilla_core/tests/test_api_layer.py`.
- Frontend: report rendering and drill-down interactions in
  `ui/src/test/ReportsPanel.test.tsx` and integration presence in
  `ui/src/test/App.test.tsx`.

---

## Rollout notes

- M4 is additive and backward-compatible with existing endpoints.
- Existing balance snapshotting (`ACC-REP-006`) remains unchanged and continues
  to power net-worth calculations.
