/**
 * Shared type definitions for the Godzilla API client.
 *
 * Each interface mirrors the corresponding Pydantic response model in
 * godzilla_core/api/app.py so that the TypeScript compiler enforces the
 * same field names and optionality as the backend.
 *
 * REQ: ACC-ACCT-001, ACC-ACCT-002, ACC-ACCT-003, ACC-ACCT-004,
 * REQ: ACC-ACCT-005, ACC-ACCT-008, ACC-SYNC-001, ACC-TXN-001, ACC-TXN-002,
 * REQ: ACC-TXN-003, ACC-TXN-004, ACC-TXN-005, ACC-TXN-006,
 * REQ: ACC-TXN-007, ACC-TXN-008, ACC-CAT-001, ACC-CAT-002,
 * REQ: ACC-SYNC-006, ACC-SYNC-007,
 * REQ: ACC-REP-001, ACC-REP-002, ACC-REP-003, ACC-REP-004, ACC-REP-005,
 * REQ: ACC-REP-006, ACC-REP-007, ACC-REP-008,
 * REQ: ACC-BUD-001, ACC-BUD-002, ACC-BUD-003, ACC-BUD-004,
 * REQ: ACC-EXP-001, ACC-EXP-002, ACC-EXP-003,
 * REQ: ACC-BKP-001, ACC-BKP-002, ACC-BKP-003, ACC-BKP-004, ACC-BKP-006,
 * REQ: ACC-SET-001, ACC-SET-002, ACC-SET-003, ACC-SET-004, ACC-SET-005,
 * REQ: ACC-AUD-001, ACC-AUD-004,
 * REQ: TECH-SEC-ACC-001, TECH-SEC-ACC-002, TECH-SEC-ACC-003, TECH-SEC-NET-001
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
  account_name: string;
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

export interface UnlinkItemResult {
  item_id: string;
  mode: "keep" | "purge";
  token_removed: boolean;
  remote_revoked: boolean;
  raw_payload_rows_deleted: number;
  local_data_purged: boolean;
}

export interface AuthStatusTls {
  enabled: boolean;
  cert_fingerprint_sha256: string | null;
}

export interface AuthStatus {
  pin_configured: boolean;
  setup_required: boolean;
  locked: boolean;
  auto_lock_minutes: number;
  unlock_expires_at_utc: string | null;
  dev_bypass_enabled: boolean;
  tls: AuthStatusTls;
}

export interface SetupPinRequest {
  new_pin: string;
  current_pin?: string;
}

export interface SetupPinResponse {
  pin_configured: boolean;
}

export interface UnlockRequest {
  pin: string;
}

export interface UnlockResponse {
  unlock_token: string;
  expires_at_utc: string;
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

export interface BackupRequest {
  passphrase: string;
  include_secrets?: boolean;
}

export interface RestoreResponse {
  restored_database: boolean;
  restored_secrets: boolean;
  schema_version: number;
}

export interface WipeRequest {
  confirm: "WIPE_LOCAL_DATA";
}

export interface WipeResponse {
  deleted_files: string[];
  missing_files: string[];
  failed_files: string[];
}

export interface ReinitializeResponse {
  schema_version: number;
}

export interface RetentionSettings {
  retain_raw_payloads: boolean;
  retain_logs_days: number;
}

export interface ExportDefaults {
  include_raw_payloads: boolean;
}

export interface SecuritySettings {
  auto_lock_minutes: number;
}

export interface SyncSettings {
  schedule_enabled: boolean;
  frequency_minutes: number;
  scheduler_supported: boolean;
}

export interface SettingsResponse {
  timezone: string;
  currency: string;
  retention: RetentionSettings;
  export_defaults: ExportDefaults;
  security: SecuritySettings;
  sync: SyncSettings;
}

export interface UpdateSettingsRequest {
  timezone?: string;
  currency?: string;
  retention?: Partial<RetentionSettings>;
  export_defaults?: Partial<ExportDefaults>;
  security?: Partial<Omit<SecuritySettings, "scheduler_supported">>;
  sync?: Partial<Omit<SyncSettings, "scheduler_supported">>;
}

export interface AuditLogEntry {
  id: string;
  event_type: string;
  timestamp_utc: string;
  timestamp_tz: string;
  timestamp_offset_minutes: number;
  redacted_payload: Record<string, unknown>;
}

export interface AuditLogResponse {
  entries: AuditLogEntry[];
  limit: number;
  offset: number;
}

export interface CategoriesBudgetsExportJson {
  categories: Array<{
    category_id: string;
    name: string;
    parent_id: string | null;
    active: boolean;
  }>;
  budgets: Array<{
    budget_id: string;
    month: string;
    category_id: string;
    amount: number;
    category_name: string;
  }>;
}

export interface BlobDownload {
  blob: Blob;
  filename: string | null;
  contentType: string;
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

export interface ExportTransactionsParams extends GetTransactionsParams {
  include_raw_payloads?: boolean;
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

export interface ExportCategoriesBudgetsParams {
  month?: string;
}

export interface GetAuditLogParams {
  event_type?: string;
  start?: string;
  end?: string;
  limit?: number;
  offset?: number;
}

// Budget types
// REQ: ACC-BUD-001, ACC-BUD-002, ACC-BUD-003, ACC-BUD-004
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
