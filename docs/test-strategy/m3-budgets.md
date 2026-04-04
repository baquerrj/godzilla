# M3 Test Plan — Budgets, Monthly View, Overspend Drill-down

**Requirements covered:** ACC-BUD-001, ACC-BUD-002, ACC-BUD-003, ACC-BUD-004

**Automated tests:**
- Backend: `godzilla_core/tests/test_api_layer.py` (15 budget tests)
- Frontend: `ui/src/test/BudgetPanel.test.tsx` (8 tests), `ui/src/test/App.test.tsx` (1 smoke test)

**See also:** `docs/design/budgets.md` for API spec and inclusion-rule SQL rationale.

---

## Scope

M3 adds the ability to define monthly spending limits per category, view planned vs actual
spend, see overspent categories highlighted, and drill down into the transactions that drove
the overspend. This plan verifies all four requirements at the API layer and the UI layer.

| Req | Title | Covered in sections |
|---|---|---|
| ACC-BUD-001 | Monthly budgets (CRUD, scoping) | 2, 3 |
| ACC-BUD-002 | Budget performance (planned/actual/remaining) | 4 |
| ACC-BUD-003 | Overspend highlighting and drill-down | 5 |
| ACC-BUD-004 | Inclusion rules (transfers, excluded, pending, splits) | 6 |

---

## 1. Prerequisites

Complete steps 1.1–1.3 before running any manual steps. Automated suite steps (section 7)
only require 1.1.

### 1.1 Automated test suite (always required)

```bash
# From the repo root
source venv/bin/activate

# Backend — lint + tests
python3 -m ruff check godzilla_core
python3 -m black --check godzilla_core noxfile.py
python3 -m pytest

# Frontend — unit tests
cd ui && npx vitest run
```

All commands must exit 0 before proceeding to manual verification.

### 1.2 Start the API server for manual API steps

```bash
# In one terminal — start with a fresh temporary DB
export GODZILLA_DB_PATH=/tmp/m3-test.db
export GODZILLA_DB_KEY=m3-test-key
export GODZILLA_API_TOKEN=m3-test-token

source venv/bin/activate
migrations                  # run schema migrations
godzilla-api                # starts on http://127.0.0.1:8787
```

### 1.3 Seed a category for manual steps

Budget lines require a leaf category. Create one if your test DB has none, or use an
ID from the seeded taxonomy (e.g. `food_and_drink_coffee`):

```bash
TOKEN="m3-test-token"
BASE="http://127.0.0.1:8787"

# Verify a leaf category exists
curl -s -H "X-API-Key: $TOKEN" "$BASE/categories" | python3 -m json.tool | grep -A2 '"active": true'
```

If the seeded taxonomy has not been applied, create a minimal hierarchy:

```bash
curl -s -X POST "$BASE/categories" \
  -H "X-API-Key: $TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "Food"}' | python3 -m json.tool
# note the returned category_id, e.g. "food-parent-id"

curl -s -X POST "$BASE/categories" \
  -H "X-API-Key: $TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "Coffee", "parent_id": "food-parent-id"}' | python3 -m json.tool
# note the returned category_id, e.g. "coffee-leaf-id"
# Use this as LEAF_CAT in subsequent steps.

export LEAF_CAT="coffee-leaf-id"
export PARENT_CAT="food-parent-id"
```

---

## 2. ACC-BUD-001 — Monthly Budget CRUD

These steps verify that budget lines can be created, listed, and deleted; that they are
scoped to the correct month; and that invalid inputs are rejected.

### 2.1 Empty list for a month with no budgets

```bash
curl -s -H "X-API-Key: $TOKEN" "$BASE/budgets?month=2026-03" | python3 -m json.tool
```

**Expected:** HTTP 200, response body `[]`.

### 2.2 Create a budget line

```bash
curl -s -X POST "$BASE/budgets" \
  -H "X-API-Key: $TOKEN" -H "Content-Type: application/json" \
  -d "{\"month\": \"2026-03\", \"category_id\": \"$LEAF_CAT\", \"amount\": 75.00}" \
  | python3 -m json.tool
```

**Expected:** HTTP 201. Response contains:
- `budget_id` — a UUID string (non-empty)
- `category_id` matches `$LEAF_CAT`
- `month` = `"2026-03"`
- `planned` = `75.0`
- `actual` = `0.0` (no transactions yet)
- `remaining` = `75.0`
- `is_overspent` = `false`

Note the `budget_id` as `$BUD_ID`.

### 2.3 List returns the created line

```bash
curl -s -H "X-API-Key: $TOKEN" "$BASE/budgets?month=2026-03" | python3 -m json.tool
```

**Expected:** HTTP 200, list contains exactly one item matching the row created in 2.2.

### 2.4 Month scoping — other months are unaffected

```bash
curl -s -H "X-API-Key: $TOKEN" "$BASE/budgets?month=2026-04" | python3 -m json.tool
```

**Expected:** HTTP 200, `[]`. The 2026-03 budget must not appear.

### 2.5 Duplicate budget line rejected

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/budgets" \
  -H "X-API-Key: $TOKEN" -H "Content-Type: application/json" \
  -d "{\"month\": \"2026-03\", \"category_id\": \"$LEAF_CAT\", \"amount\": 50.00}"
```

**Expected:** HTTP 409.

### 2.6 Parent (non-leaf) category rejected

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/budgets" \
  -H "X-API-Key: $TOKEN" -H "Content-Type: application/json" \
  -d "{\"month\": \"2026-03\", \"category_id\": \"$PARENT_CAT\", \"amount\": 100.00}"
```

**Expected:** HTTP 422.

### 2.7 Unknown category rejected

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/budgets" \
  -H "X-API-Key: $TOKEN" -H "Content-Type: application/json" \
  -d '{"month": "2026-03", "category_id": "no-such-cat", "amount": 50.00}'
```

**Expected:** HTTP 422.

### 2.8 Non-positive amount rejected

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/budgets" \
  -H "X-API-Key: $TOKEN" -H "Content-Type: application/json" \
  -d "{\"month\": \"2026-03\", \"category_id\": \"$LEAF_CAT\", \"amount\": 0}"
```

**Expected:** HTTP 422. Repeat with `"amount": -10` — also expect 422.

### 2.9 Invalid month format rejected

```bash
# Missing month param entirely
curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $TOKEN" "$BASE/budgets"

# Malformed month string
curl -s -o /dev/null -w "%{http_code}" \
  -H "X-API-Key: $TOKEN" "$BASE/budgets?month=January-2026"
```

**Expected:** both return HTTP 422.

### 2.10 Delete the budget line

```bash
curl -s -o /dev/null -w "%{http_code}" -X DELETE \
  -H "X-API-Key: $TOKEN" "$BASE/budgets/$BUD_ID"
```

**Expected:** HTTP 204, empty response body.

### 2.11 Deleted line no longer appears in list

```bash
curl -s -H "X-API-Key: $TOKEN" "$BASE/budgets?month=2026-03" | python3 -m json.tool
```

**Expected:** HTTP 200, `[]`.

### 2.12 Delete unknown ID returns 404

```bash
curl -s -o /dev/null -w "%{http_code}" -X DELETE \
  -H "X-API-Key: $TOKEN" "$BASE/budgets/no-such-budget-id"
```

**Expected:** HTTP 404.

### 2.13 Auth required

```bash
curl -s -o /dev/null -w "%{http_code}" "$BASE/budgets?month=2026-03"
```

**Expected:** HTTP 401 (no `X-API-Key` header).

---

## 3. ACC-BUD-001 — UI Budget CRUD

Start the Tauri dev app or use the Vite browser proxy (`npm run dev` in `ui/`).

### 3.1 Budget panel is visible

**Action:** Load the app with a valid API token.

**Expected:** A **Budgets** section is visible on the main page, containing a month picker
(`<input type="month">`), a category dropdown, an amount input, and an **Add Budget** button.

### 3.2 Month picker defaults to the current month

**Action:** Observe the month picker on first load.

**Expected:** The input shows the current calendar month (e.g. `2026-02`).

### 3.3 Empty state message

**Action:** Switch to a month with no budgets (e.g. type `2026-07` into the picker).

**Expected:** The panel shows "No budgets set for 2026-07." No table is rendered.

### 3.4 Add a budget line

**Action:**
1. Select a leaf category from the dropdown.
2. Enter `100` in the amount field.
3. Click **Add Budget**.

**Expected:**
- A table row appears with the selected category name, `100.00` as Planned, `0.00` as
  Actual, `100.00` as Remaining, and **View** and **Delete** buttons.
- The dropdown and amount input are cleared.

### 3.5 Duplicate rejected with error

**Action:** With the row from 3.4 present, select the same category, enter `50`, click
**Add Budget** again.

**Expected:** An inline error message appears (e.g. "Failed to create budget: …already
exists…"). The duplicate row is not added to the table.

### 3.6 Delete a budget line

**Action:** Click **Delete** on the row added in 3.4.

**Expected:** The row disappears from the table. If it was the only row, the "No budgets
set" message reappears.

---

## 4. ACC-BUD-002 — Planned / Actual / Remaining Computation

This section verifies the arithmetic and that the API computes actuals from real
transactions in the database.

### 4.1 Seed transactions for a test month

Using the running server DB, insert three posted transactions for `2026-05` via the
transaction sync or directly via SQLite. The simplest approach is to run a
`sync-plaid-item` with sandbox data, then use the PATCH endpoint to assign categories.
For isolated verification, use the automated test (`test_get_budgets_computes_actuals_correctly`)
instead and skip to 4.2.

If inserting manually: create two posted, non-transfer, non-excluded transactions in
`2026-05`, both assigned to `$LEAF_CAT`, totalling a known amount (e.g. 30.00 + 20.00 = 50.00).

### 4.2 Create a budget and verify actuals

```bash
curl -s -X POST "$BASE/budgets" \
  -H "X-API-Key: $TOKEN" -H "Content-Type: application/json" \
  -d "{\"month\": \"2026-05\", \"category_id\": \"$LEAF_CAT\", \"amount\": 80.00}" \
  | python3 -m json.tool
```

**Expected:**
- `planned` = `80.0`
- `actual` = `50.0` (sum of the two transactions)
- `remaining` = `30.0` (`80 - 50`)
- `is_overspent` = `false`

### 4.3 GET reflects same values

```bash
curl -s -H "X-API-Key: $TOKEN" "$BASE/budgets?month=2026-05" | python3 -m json.tool
```

**Expected:** Same `actual`, `remaining`, and `is_overspent` as the POST response.

### 4.4 Remaining goes negative when overspent

```bash
# Lower the planned amount below the actual
curl -s -X DELETE -H "X-API-Key: $TOKEN" "$BASE/budgets/$PREV_BUD_ID"

curl -s -X POST "$BASE/budgets" \
  -H "X-API-Key: $TOKEN" -H "Content-Type: application/json" \
  -d "{\"month\": \"2026-05\", \"category_id\": \"$LEAF_CAT\", \"amount\": 30.00}" \
  | python3 -m json.tool
```

**Expected:**
- `planned` = `30.0`
- `actual` = `50.0`
- `remaining` = `-20.0`
- `is_overspent` = `true`

### 4.5 UI displays correct values

**Action:** In the Budgets panel, navigate to 2026-05.

**Expected:** The row shows `30.00` planned, `50.00` actual, and `-20.00` remaining.
The remaining cell is styled in red (class `budget-row-overspent`).

---

## 5. ACC-BUD-003 — Overspend Highlighting and Drill-down

### 5.1 Overspent row is visually distinct

**Prerequisite:** Step 4.4 — a budget with `is_overspent: true` in the UI.

**Action:** Navigate to the month containing the overspent budget.

**Expected:**
- The overspent row has the CSS class `budget-row-overspent` on the `<tr>` element
  (inspect element to confirm, or look for the red remaining value).
- Non-overspent rows in the same table do not have this class.

### 5.2 Drill-down populates transaction filters

**Action:** Click **View** on the overspent budget row.

**Expected:**
- The **Transaction Filters** section updates immediately:
  - `Category` is set to the overspent category.
  - `From` date = first day of the selected budget month (e.g. `2026-05-01`).
  - `To` date = last day of the selected budget month (e.g. `2026-05-31`).
- The **Transactions** table re-fetches and shows only transactions for that category
  within that month.

### 5.3 Drill-down shows only contributing transactions

**Prerequisite:** The test DB has exactly two transactions for `$LEAF_CAT` in `2026-05`.

**Action:** After clicking **View** (step 5.2), count the rows in the Transactions table.

**Expected:** Exactly 2 rows. Their sum equals the `actual` shown in the budget row.

### 5.4 Last-day edge case — month with 28, 30, and 31 days

**Action:** Create budget lines for `2026-02` (28 days), `2026-04` (30 days), and
`2026-01` (31 days). Click **View** on each.

**Expected `date_to` values:**
- `2026-02` → `2026-02-28`
- `2026-04` → `2026-04-30`
- `2026-01` → `2026-01-31`

Verify by inspecting the **To** date in the filter bar after each click.

### 5.5 Drill-down from non-overspent row also works

**Action:** Create a second budget line for a different leaf category with `planned` well
above `actual`. Click its **View** button.

**Expected:** The same filter update occurs with the correct category and month. The
Transactions table shows only transactions for that category in that month, even though
there is no overspend.

---

## 6. ACC-BUD-004 — Inclusion Rules

Each sub-step tests one inclusion rule in isolation. The automated backend tests cover
the same cases via `_seed_budget_data`; these steps verify the full data path with real
API calls using manually constructed transactions (or the automated test if manual DB
seeding is impractical).

For manual verification: insert transactions via the API (sync a Plaid sandbox item and
use PATCH to set flags) or directly into the SQLite DB using the `db_inspect` tool.

**Reference dataset:** the `_seed_budget_data` fixture in
`godzilla_core/tests/test_api_layer.py` is the authoritative definition of these rules.

---

### 6.1 Transfers excluded from actuals

**Setup:** In month `2026-06`, create a posted transaction assigned to `$LEAF_CAT` with
`is_transfer = true`.

**Action:** Create a budget for `$LEAF_CAT` in `2026-06` and fetch it.

**Expected:** `actual` = `0.0`. The transfer transaction does not count toward the budget.

**Verify with automated test:**
```bash
python3 -m pytest godzilla_core/tests/test_api_layer.py \
  -k "test_get_budgets_excludes_transfers_pending_excluded" -v
```

---

### 6.2 Explicitly excluded transactions do not count

**Setup:** In month `2026-06`, add a second posted, non-transfer transaction assigned to
`$LEAF_CAT` with `is_excluded = true`.

**Action:** Fetch the budget for `$LEAF_CAT` in `2026-06`.

**Expected:** `actual` still `0.0`. The excluded transaction does not count.

**Verify:** same automated test as 6.1.

---

### 6.3 Pending transactions do not count

**Setup:** Add a third transaction for `$LEAF_CAT` in `2026-06` with `status = 'pending'`.

**Action:** Fetch the budget.

**Expected:** `actual` still `0.0`. Pending transactions are excluded.

**Verify:** same automated test as 6.1.

---

### 6.4 Un-split posted transactions count

**Setup:** Add a posted, non-transfer, non-excluded transaction for `$LEAF_CAT` in
`2026-06` with `amount = 40.00` and **no splits**.

**Action:** Fetch the budget.

**Expected:** `actual` = `40.0`.

**Verify with automated test:**
```bash
python3 -m pytest godzilla_core/tests/test_api_layer.py \
  -k "test_get_budgets_computes_actuals_correctly" -v
```

---

### 6.5 Split transactions: parent ignored, splits counted

**Setup:** Create a posted, non-transfer, non-excluded transaction for a different leaf
category (`$OTHER_CAT`) in `2026-06` with `amount = 60.00`. Then add splits to it:
- Split 1: `$LEAF_CAT`, `amount = 35.00`
- Split 2: `$OTHER_CAT`, `amount = 25.00`

Use `POST /transactions/{id}/splits` to set the splits.

**Action:** Create budgets for both `$LEAF_CAT` and `$OTHER_CAT` in `2026-06`. Fetch
the budget list.

**Expected actuals (cumulative from 6.4 and 6.5):**
- `$LEAF_CAT`: `40.00` (un-split txn) + `35.00` (split 1) = `75.00`
- `$OTHER_CAT`: `25.00` (split 2 only; the parent's `$OTHER_CAT` assignment and `60.00`
  amount are ignored because splits exist)

**What must NOT happen:** `$OTHER_CAT` actual must not be `85.00` (which would happen if
both the parent's 60.00 and the split's 25.00 were counted).

**Verify with automated test:**
```bash
python3 -m pytest godzilla_core/tests/test_api_layer.py \
  -k "test_get_budgets_uses_splits_not_parent" -v
```

---

### 6.6 Mark-as-transfer affects budget retroactively

**Setup:** Start with a posted, non-excluded transaction assigned to `$LEAF_CAT` in
`2026-07` with `amount = 50.00`. Budget for that category shows `actual = 50.00`.

**Action:** Use `PATCH /transactions/{id}` to set `is_transfer: true`. Fetch the budget.

**Expected:** `actual` drops to `0.0`. The budget actual is recomputed from current
transaction state on each GET.

**Verify manually or with:**
```bash
# PATCH the transaction
curl -s -X PATCH "$BASE/transactions/$TXN_ID" \
  -H "X-API-Key: $TOKEN" -H "Content-Type: application/json" \
  -d '{"is_transfer": true}' | python3 -m json.tool

# Fetch budget — actual should now be 0
curl -s -H "X-API-Key: $TOKEN" "$BASE/budgets?month=2026-07" | python3 -m json.tool
```

---

### 6.7 Mark-as-excluded affects budget retroactively

Same as 6.6 but using `is_excluded: true` on a non-transfer transaction.

**Expected:** `actual` drops to `0.0` after the PATCH.

---

### 6.8 Cross-month isolation

**Setup:** Create two identical transactions — one in `2026-08-15`, one in `2026-09-15`
— both posted, non-transfer, non-excluded, assigned to `$LEAF_CAT`.

**Action:** Create a budget for `$LEAF_CAT` in `2026-08` and fetch it.

**Expected:** `actual` reflects only the August transaction. The September transaction
does not appear.

---

## 7. Automated Test Suite — Full Verification

Run these commands in order. All must succeed before M3 is considered verified.

```bash
cd /workspace/godzilla
source venv/bin/activate

# 1. Backend lint
python3 -m ruff check godzilla_core
python3 -m black --check godzilla_core noxfile.py

# 2. Backend unit + integration tests (138 total, 15 budget-specific)
python3 -m pytest -v

# 3. Confirm all 15 budget tests pass
python3 -m pytest godzilla_core/tests/test_api_layer.py -v -k "budget" 2>&1 | grep -E "PASSED|FAILED|ERROR"

# 4. Frontend unit tests (51 total, 9 budget-specific)
cd ui && npx vitest run

# 5. Confirm budget-specific frontend tests
npx vitest run src/test/BudgetPanel.test.tsx --reporter=verbose
```

**Expected output for step 3 (all PASSED):**
```
PASSED test_get_budgets_returns_empty_for_no_budgets
PASSED test_get_budgets_missing_month_returns_422
PASSED test_get_budgets_invalid_month_format_returns_422
PASSED test_create_budget_returns_201
PASSED test_create_budget_duplicate_returns_409
PASSED test_create_budget_parent_category_returns_422
PASSED test_create_budget_unknown_category_returns_422
PASSED test_create_budget_negative_amount_returns_422
PASSED test_get_budgets_computes_actuals_correctly
PASSED test_get_budgets_overspent_flagged
PASSED test_get_budgets_excludes_transfers_pending_excluded
PASSED test_get_budgets_uses_splits_not_parent
PASSED test_get_budgets_filters_by_month
PASSED test_delete_budget_returns_204
PASSED test_delete_budget_not_found_returns_404
```

**Expected output for step 5 (all ✓):**
```
✓ renders empty state when no budgets
✓ renders rows with planned/actual/remaining amounts
✓ highlights overspent rows
✓ calls onDrillDown with correct categoryId and month
✓ creates budget via form submit and clears inputs
✓ shows error message on 409 duplicate budget
✓ deletes budget when delete button clicked
✓ shows error message on fetch failure
```

---

## 8. Traceability Check

Verify the traceability index is current:

```bash
grep -A 20 "requirement_id: ACC-BUD-001" trace/requirements.yml
grep -A 10 "requirement_id: ACC-BUD-002" trace/requirements.yml
grep -A 10 "requirement_id: ACC-BUD-003" trace/requirements.yml
grep -A 10 "requirement_id: ACC-BUD-004" trace/requirements.yml
```

**Expected:** Each entry has non-empty `code_refs` and `test_refs` lists covering the
functions, components, and test names implemented in M3.

---

## 9. Out of Scope for M3

The following are deferred to later milestones and are not tested here:

| Item | Deferred to |
|---|---|
| Budget carry-over or rolling budgets | Post-MVP |
| Category-level totals (parent category aggregation) | M4 reports |
| Reporting consistency across dashboard widgets | M4 (ACC-REP-007) |
| CSV export of budget data | M5 (ACC-EXP-002) |
| Budget inclusion rules on report endpoints | M4 (shares `_BUDGET_ACTUALS_CTE`) |
