# Budgets — Design Document

**Requirements:** ACC-BUD-001, ACC-BUD-002, ACC-BUD-003, ACC-BUD-004

---

## Problem Statement

Users need to define monthly spending limits per category, see planned vs actual spend,
quickly identify overspent categories, and drill down into the contributing transactions.

---

## Data Model

The `budget` table was already present in the schema (from `migrations/0001_init.sql`):

```sql
CREATE TABLE IF NOT EXISTS budget (
    id          TEXT PRIMARY KEY,
    month       TEXT NOT NULL,        -- YYYY-MM
    category_id TEXT NOT NULL,
    amount      REAL NOT NULL,
    FOREIGN KEY (category_id) REFERENCES category(id)
);
```

No schema change was needed for M3. The `is_overspent` flag, `actual`, and `remaining`
fields are computed server-side on each `GET /budgets` request.

---

## API Specification

### `GET /budgets?month=YYYY-MM`

Returns all budget lines for the given month with computed actuals.

**Response:** `list[BudgetLineResponse]`

| Field | Type | Description |
|---|---|---|
| `budget_id` | str | Budget row UUID |
| `category_id` | str | Leaf category ID |
| `month` | str | YYYY-MM |
| `planned` | float | Budget amount |
| `actual` | float | Computed actual spend |
| `remaining` | float | `planned - actual` (negative when overspent) |
| `is_overspent` | bool | `actual > planned` |

**Validation:** `month` must match `^\d{4}-\d{2}$` (enforced by Pydantic regex on both
the `GET` query param and the `POST` request body).

### `POST /budgets` → 201

Creates a budget line. Validates that `category_id` is an active leaf category (via
`_validate_category_assignment`). Returns 409 if a budget already exists for the
same `(month, category_id)` pair.

### `DELETE /budgets/{id}` → 204

Deletes a budget line. Returns 404 if the ID does not exist.

---

## Inclusion-Rule SQL

The `_BUDGET_ACTUALS_CTE` constant implements all four inclusion rules in a single CTE:

```sql
WITH line_items AS (
  -- Non-split transactions (only when no splits exist for this transaction)
  SELECT tr.category_id, tr.amount AS subtotal
  FROM transaction_record tr
  WHERE tr.date LIKE ? || '-%'           -- month filter (YYYY-MM-*)
    AND tr.is_transfer = 0              -- REQ: ACC-BUD-004 exclude transfers
    AND tr.is_excluded = 0             -- REQ: ACC-BUD-004 exclude explicitly excluded
    AND tr.status = 'posted'           -- REQ: ACC-BUD-004 exclude pending
    AND tr.category_id IS NOT NULL
    AND NOT EXISTS (                   -- REQ: ACC-BUD-004 split-aware: skip parent
        SELECT 1 FROM transaction_split WHERE transaction_id = tr.id
    )
  UNION ALL
  -- Split amounts (parent's category/amount ignored when splits present)
  SELECT ts.category_id, ts.amount AS subtotal
  FROM transaction_split ts
  JOIN transaction_record tr ON tr.id = ts.transaction_id
  WHERE tr.date LIKE ? || '-%'
    AND tr.is_transfer = 0
    AND tr.is_excluded = 0
    AND tr.status = 'posted'
    AND ts.category_id IS NOT NULL
)
SELECT category_id, SUM(subtotal) AS actual
FROM line_items
GROUP BY category_id
```

**Safety:** The `LIKE ? || '-%'` pattern is safe because `month` is validated by Pydantic
to match `^\d{4}-\d{2}$` before reaching the SQL layer — no user-supplied wildcards can
enter the pattern.

**Rationale per clause:**
- `is_transfer = 0` — transfers move money between own accounts; counting them would
  double-count and distort budget actuals.
- `is_excluded = 0` — transactions explicitly flagged by the user as excluded from
  budgets/reports must not count.
- `status = 'posted'` — pending transactions have not settled; including them would
  cause budget figures to fluctuate unpredictably.
- `NOT EXISTS (splits)` / `UNION ALL splits` — when the user splits a transaction, the
  split rows represent the intended allocation. Using both parent and splits would
  double-count; only splits should count when present.

This CTE is designed for reuse by M4 report endpoints.

---

## Component Diagram

```mermaid
graph TD
    App["App.tsx"] -->|categories, onDrillDown| BP["BudgetPanel"]
    BP -->|getBudgets| API["/budgets API"]
    BP -->|createBudget| API
    BP -->|deleteBudget| API
    BP -->|onDrillDown(categoryId, month)| App
    App -->|setFilterValues| TF["TransactionFilters"]
    TF --> TT["TransactionsTable"]
```

### Drill-down flow

1. User clicks **View** on an overspent budget row.
2. `BudgetPanel` calls `onDrillDown(categoryId, selectedMonth)`.
3. `App.handleBudgetDrillDown` computes the first/last day of the month and calls
   `setFilterValues` with `category_id`, `date_from`, and `date_to` set.
4. `TransactionsTable` re-fetches with these filters, showing only transactions
   contributing to the overspent category.

---

## Security Notes

- **Regex-guarded LIKE pattern:** `month` is validated to `^\d{4}-\d{2}$` by Pydantic
  before it reaches the SQL layer. No wildcards or injection characters can enter the
  `LIKE` pattern.
- **Parameterized queries only:** all SQL uses `?` placeholders; no string concatenation.
- **Leaf-only validation:** `_validate_category_assignment` enforces that only active
  leaf categories can have budgets, preventing budget lines on parent nodes which would
  aggregate inconsistently.
- **Auth:** all three endpoints require the `X-API-Key` header via `Depends(require_api_key)`.

---

## Testing Strategy

| Layer | Count | What is covered |
|---|---|---|
| Backend (pytest) | 15 | CRUD, format validation, duplicate/404/422 errors, all 4 inclusion rules independently |
| Frontend (vitest) | 9 | Empty state, table rendering, overspend class, drill-down callback, create/delete flows, fetch error |

Inclusion-rule tests use dedicated fixture transactions (`_seed_budget_data`) targeting
each rule in isolation (transfer, excluded, pending, split-aware) to verify that the
computed actual for `food_coffee` is exactly 45.00 (12 + 8 + 25-from-split) and
`food_dining` is exactly 20.00 (20-from-split), with no contribution from the excluded
transactions.

---

## Trade-offs

**Server-side actuals on each GET:** Actuals are computed fresh on every `GET /budgets`
request via the SQL CTE. This keeps the data model simple (no materialized columns) and
ensures consistency at the cost of a slightly heavier read query. For a single-user
local app this is negligible; an M4 reports endpoint can reuse the same CTE.

**App-level uniqueness enforcement:** The API returns 409 when a duplicate
`(month, category_id)` budget line already exists. This is enforced via a `SELECT`
before `INSERT` rather than a database `UNIQUE` constraint, to give a clear 409 error
message. The single-user, non-concurrent nature of the app means this is safe.
