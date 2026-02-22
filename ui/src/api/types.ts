/**
 * Shared type definitions for the Godzilla API client.
 *
 * Each interface mirrors the corresponding Pydantic response model in
 * godzilla_core/api/app.py so that the TypeScript compiler enforces the
 * same field names and optionality as the backend.
 *
 * REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-003, FUNC-ACCT-004,
 * REQ: FUNC-ACCT-005, FUNC-SYNC-001, FUNC-TXN-001, FUNC-REP-006
 */

// ---------------------------------------------------------------------------
// Response models (read)
// ---------------------------------------------------------------------------

/** Linked account metadata.  REQ: FUNC-ACCT-003 */
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

/** Transaction list-view record.  REQ: FUNC-TXN-001 */
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
}

/** Balance snapshot for net-worth views.  REQ: FUNC-REP-006 */
export interface BalanceSnapshot {
  snapshot_id: string;
  account_id: string;
  provider_account_id: string;
  date: string;
  balance: number;
  currency: string;
}

/** Per-item incremental-sync state.  REQ: FUNC-ACCT-004 */
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

/** Successful Plaid link result.  REQ: FUNC-ACCT-001, FUNC-ACCT-002 */
export interface PlaidLinkResult {
  item_id: string;
  institution_id: string;
  env: string;
}

/** Successful Plaid sync result.  REQ: FUNC-ACCT-005, FUNC-SYNC-001 */
export interface PlaidSyncResult {
  item_id: string;
  added: number;
  modified: number;
  removed: number;
  balance_accounts: number;
  cursor: string;
}

// ---------------------------------------------------------------------------
// Request payloads (write)
// ---------------------------------------------------------------------------

/** Body for POST /plaid/link.  REQ: FUNC-ACCT-001, FUNC-ACCT-002 */
export interface PlaidLinkRequest {
  institution_id?: string;
  products?: string[];
}

/** Body for POST /plaid/sync.  REQ: FUNC-ACCT-005, FUNC-SYNC-001 */
export interface PlaidSyncRequest {
  item_id: string;
  institution_id?: string;
}

// ---------------------------------------------------------------------------
// Query parameter shapes
// ---------------------------------------------------------------------------

/** Optional filters/pagination for GET /transactions.  REQ: FUNC-TXN-001 */
export interface GetTransactionsParams {
  account_id?: string;
  limit?: number;
  offset?: number;
  sort_by?: "date" | "amount";
  sort_order?: "asc" | "desc";
}

/** Optional filters/pagination for GET /balances.  REQ: FUNC-REP-006 */
export interface GetBalancesParams {
  account_id?: string;
  limit?: number;
  offset?: number;
}

// ---------------------------------------------------------------------------
// Async operation state
// ---------------------------------------------------------------------------

/**
 * Discriminated union representing the lifecycle of an async API call.
 *
 * REQ: FUNC-ACCT-003, FUNC-TXN-001, FUNC-REP-006
 *
 * Usage:
 *   const [result, execute] = useApiCall<Account[]>();
 *   switch (result.status) {
 *     case "idle":    // not yet called
 *     case "loading": // in flight
 *     case "success": // result.data is T
 *     case "error":   // result.message describes the failure
 *   }
 */
export type ApiResult<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; message: string; statusCode?: number };
