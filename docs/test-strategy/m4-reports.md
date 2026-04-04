# M4 Test Plan — Reports, Dashboards, and Net Worth

**Requirements covered:** ACC-REP-001, ACC-REP-002, ACC-REP-003, ACC-REP-004, ACC-REP-005, ACC-REP-007, ACC-REP-008

---

## Automated tests

- Backend:
  - `godzilla_core/tests/test_api_layer.py`
  - New report-focused fixture and endpoint tests:
    - `test_reports_monthly_overview_returns_expected_metrics`
    - `test_reports_cash_flow_returns_monthly_points`
    - `test_reports_category_trends_supports_multi_category_selection`
    - `test_reports_net_worth_returns_assets_liabilities_and_net`
    - `test_reports_and_budgets_share_inclusion_rules`
    - validation/auth negative-path tests
- Frontend:
  - `ui/src/test/ReportsPanel.test.tsx`
  - `ui/src/test/App.test.tsx` (panel integration smoke)

---

## Verification matrix

| Requirement | Verification |
| --- | --- |
| ACC-REP-001 | Monthly overview endpoint + UI cards/top categories rendering |
| ACC-REP-002 | Report metric click paths update transaction filters |
| ACC-REP-003 | Cash-flow month aggregation and savings rate checks |
| ACC-REP-004 | Category trend series generation for selected categories |
| ACC-REP-005 | Net worth = assets - liabilities over snapshots |
| ACC-REP-007 | Reports reconcile with budget inclusion-rule totals |
| ACC-REP-008 | Month/range validation and UI date navigation refresh behavior |

---

## Run commands

```bash
# repo root
. venv/bin/activate
nox -s lint
nox -s tests
nox -s build

# frontend
cd ui
npm test
npm run build
```

---

## Manual API smoke checks

After starting `godzilla-api`, verify:

1. `GET /reports/monthly-overview?month=YYYY-MM` returns overview fields and top categories.
2. `GET /reports/cash-flow?start=...&end=...` returns month points.
3. `GET /reports/category-trends?categories=...&months=...` returns one series per category.
4. `GET /reports/net-worth?start=...&end=...` returns assets/liabilities/net points.
5. Missing `X-API-Key` yields `401`.
6. Invalid month/date/range inputs yield `422`.

---

## Manual UI smoke checks

1. Reports panel renders with month/date controls and all four report sections.
2. Changing month updates monthly overview.
3. Changing start/end dates updates cash-flow, trends, and net-worth sections.
4. Clicking overview/cash-flow/trend drill-down controls updates transaction filters and table content.
5. Inclusion-rule note is visible for transaction-derived reports.
