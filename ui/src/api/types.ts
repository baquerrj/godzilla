/**
 * Shared type definitions for the Godzilla API client.
 *
 * Each interface mirrors the corresponding Pydantic response model in
 * godzilla_core/api/app.py so that the TypeScript compiler enforces the
 * same field names and optionality as the backend.
 *
 * REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-003, FUNC-ACCT-004,
 * REQ: FUNC-ACCT-005, FUNC-SYNC-001, FUNC-TXN-001, FUNC-TXN-002,
 * REQ: FUNC-TXN-003, FUNC-TXN-004, FUNC-TXN-005, FUNC-TXN-006,
 * REQ: FUNC-TXN-007, FUNC-TXN-008, FUNC-CAT-001, FUNC-CAT-002,
 * REQ: FUNC-SYNC-006, FUNC-SYNC-007,
 * REQ: FUNC-REP-001, FUNC-REP-002, FUNC-REP-003, FUNC-REP-004, FUNC-REP-005,
 * REQ: FUNC-REP-006, FUNC-REP-007, FUNC-REP-008,
 * REQ: FUNC-BUD-001, FUNC-BUD-002, FUNC-BUD-003, FUNC-BUD-004
 */

// Response models (read)
export interface Account {
  account_id: string;
  provider_account_id: string;
  item_id: string;
  institution_id: string;
  name: string;
  account_type: string;
  subtype: string | null;
  mask: string | null;
  balance: number | null;
  currency: string;
  owner_names: unknown[];
}

export interface Transaction {
  transaction_id: string;
  account_id: string;
  provider_account_id: string;
  date: string;
  amount: number;
  currency: string;
  status: string;
  merchant_name: string | null;
  display_name: string;
  is_transfer: boolean;
  is_excluded: boolean;
  category_id: string | null;
  notes: string | null;
}

export interface TransactionSplit {
  split_id: string;
  amount: number;
  category_id: string | null;
  notes: string | null;
}

export interface TransactionDetail extends Transaction {
  tags: string[];
  splits: TransactionSplit[];
  raw_provider_payloads: Record<string, unknown>[];
}

export interface Category {
  category_id: string;
  name: string;
  parent_id: string | null;
  active: boolean;
}

export interface Conflict {
  conflict_id: string;
  entity_type: string;
  entity_id: string;
  field_name: string;
  local_value: string;
  provider_value: string;
  status: string;
  resolution_choice: string | null;
}

export interface BalanceSnapshot {
  snapshot_id: string;
  account_id: string;
  provider_account_id: string;
  account_name: string;
  date: string;
  balance: number;
  currency: string;
}

export interface TopSpendingCategory {
  category_id: string;
  category_name: string;
  amount: number;
}

export interface MonthlyOverview {
  month: string;
  start_date: string;
  end_date: string;
  income: number;
  expenses: number;
  net_savings: number;
  savings_rate: number;
  top_categories: TopSpendingCategory[];
  inclusion_note: string;
  includes_excluded_items: boolean;
}

export interface CashFlowPoint {
  month: string;
  income: number;
  expenses: number;
  net_savings: number;
  savings_rate: number;
}

export interface CashFlowReport {
  start_date: string;
  end_date: string;
  points: CashFlowPoint[];
  inclusion_note: string;
  includes_excluded_items: boolean;
}

export interface CategoryTrendPoint {
  month: string;
  amount: number;
}

export interface CategoryTrendSeries {
  category_id: string;
  category_name: string;
  points: CategoryTrendPoint[];
}

export interface CategoryTrendsReport {
  start_month: string;
  end_month: string;
  months: number;
  series: CategoryTrendSeries[];
  inclusion_note: string;
  includes_excluded_items: boolean;
}

export interface NetWorthPoint {
  date: string;
  assets: number;
  liabilities: number;
  net_worth: number;
}

export interface NetWorthReport {
  start_date: string;
  end_date: string;
  points: NetWorthPoint[];
}

export interface SyncState {
  item_id: string;
  institution_id: string;
  status: string;
  last_sync_at_utc: string | null;
  last_sync_at_tz: string | null;
  last_sync_at_offset_minutes: number | null;
  last_sync_status: string | null;
  cursor: string | null;
}

export interface PlaidLinkResult {
  item_id: string;
  institution_id: string;
  env: string;
}

export interface PlaidSyncResult {
  item_id: string;
  added: number;
  modified: number;
  removed: number;
  balance_accounts: number;
  cursor: string;
}

// Request payloads (write)
export interface PlaidLinkRequest {
  institution_id?: string;
  products?: string[];
}

export interface PlaidSyncRequest {
  item_id: string;
  institution_id?: string;
}

export interface PatchTransactionRequest {
  category_id?: string | null;
  display_name?: string | null;
  notes?: string | null;
  is_transfer?: boolean | null;
  is_excluded?: boolean | null;
  add_tags?: string[];
  remove_tags?: string[];
}

export interface SplitItem {
  amount: number;
  category_id?: string | null;
  notes?: string | null;
}

export interface CreateCategoryRequest {
  name: string;
  parent_id?: string | null;
}

export interface PatchCategoryRequest {
  name?: string | null;
  active?: boolean | null;
}

export interface ResolveConflictRequest {
  resolution_choice: "local" | "provider";
}

// Query parameter shapes
export interface GetTransactionsParams {
  account_id?: string;
  date_from?: string;
  date_to?: string;
  category_id?: string;
  merchant?: string;
  amount_min?: number;
  amount_max?: number;
  limit?: number;
  offset?: number;
  sort_by?: "date" | "amount";
  sort_order?: "asc" | "desc";
}

export interface GetBalancesParams {
  account_id?: string;
  limit?: number;
  offset?: number;
}

export interface GetMonthlyOverviewParams {
  month: string;
}

export interface GetCashFlowParams {
  start: string;
  end: string;
}

export interface GetCategoryTrendsParams {
  categories: string[];
  months?: number;
  end_month?: string;
}

export interface GetNetWorthParams {
  start: string;
  end: string;
}

// Budget types
// REQ: FUNC-BUD-001, FUNC-BUD-002, FUNC-BUD-003, FUNC-BUD-004
export interface BudgetLine {
  budget_id: string;
  category_id: string;
  month: string;
  planned: number;
  actual: number;
  remaining: number;
  is_overspent: boolean;
}

export interface CreateBudgetRequest {
  month: string;
  category_id: string;
  amount: number;
}

export interface GetBudgetsParams {
  month: string;
}

// Async operation state
export type ApiResult<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; message: string; statusCode?: number };
