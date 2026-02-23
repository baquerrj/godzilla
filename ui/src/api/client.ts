/**
 * Typed HTTP client for the Godzilla local API sidecar.
 *
 * REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-003, FUNC-ACCT-004,
 * REQ: FUNC-ACCT-005, FUNC-SYNC-001, FUNC-TXN-001, FUNC-TXN-002,
 * REQ: FUNC-TXN-003, FUNC-TXN-004, FUNC-TXN-005, FUNC-TXN-006,
 * REQ: FUNC-TXN-007, FUNC-TXN-008, FUNC-CAT-001, FUNC-CAT-002,
 * REQ: FUNC-SYNC-006, FUNC-SYNC-007,
 * REQ: FUNC-REP-001, FUNC-REP-002, FUNC-REP-003, FUNC-REP-004, FUNC-REP-005,
 * REQ: FUNC-REP-006, FUNC-REP-007, FUNC-REP-008,
 * REQ: SEC-ACC-004,
 * REQ: FUNC-BUD-001, FUNC-BUD-002, FUNC-BUD-003, FUNC-BUD-004
 */

import { useCallback, useState } from "react";
import type {
  Account,
  ApiResult,
  BalanceSnapshot,
  BudgetLine,
  CashFlowReport,
  Category,
  CategoryTrendsReport,
  Conflict,
  CreateBudgetRequest,
  CreateCategoryRequest,
  GetCashFlowParams,
  GetBalancesParams,
  GetBudgetsParams,
  GetCategoryTrendsParams,
  GetMonthlyOverviewParams,
  GetNetWorthParams,
  GetTransactionsParams,
  MonthlyOverview,
  NetWorthReport,
  PatchCategoryRequest,
  PatchTransactionRequest,
  PlaidLinkRequest,
  PlaidLinkResult,
  PlaidSyncRequest,
  PlaidSyncResult,
  ResolveConflictRequest,
  SplitItem,
  SyncState,
  Transaction,
  TransactionDetail,
} from "./types";

// Internal helpers

const API_BASE: string = import.meta.env.DEV
  ? "/api"
  : "http://127.0.0.1:8787";

export class ApiError extends Error {
  constructor(
    public readonly statusCode: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  apiToken: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiToken,
      ...options.headers,
    },
  });

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // Ignore JSON parse failure
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) return undefined as unknown as T;

  return response.json() as Promise<T>;
}

function buildQueryString<T extends object>(params: T): string {
  const entries = Object.entries(params as Record<string, unknown>).filter(([, v]) =>
    typeof v === "string" || typeof v === "number" || typeof v === "boolean",
  );
  if (entries.length === 0) return "";
  const qs = new URLSearchParams(entries.map(([k, v]) => [k, String(v)]));
  return `?${qs.toString()}`;
}

// Public API client

export const GodzillaApi = {
  getAccounts(token: string): Promise<Account[]> {
    return request<Account[]>("/accounts", token);
  },

  getTransactions(
    token: string,
    params: GetTransactionsParams = {},
  ): Promise<Transaction[]> {
    const qs = buildQueryString(params);
    return request<Transaction[]>(`/transactions${qs}`, token);
  },

  getTransaction(token: string, id: string): Promise<TransactionDetail> {
    return request<TransactionDetail>(`/transactions/${encodeURIComponent(id)}`, token);
  },

  patchTransaction(
    token: string,
    id: string,
    body: PatchTransactionRequest,
  ): Promise<TransactionDetail> {
    return request<TransactionDetail>(`/transactions/${encodeURIComponent(id)}`, token, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  postSplits(token: string, id: string, splits: SplitItem[]): Promise<TransactionDetail> {
    return request<TransactionDetail>(`/transactions/${encodeURIComponent(id)}/splits`, token, {
      method: "POST",
      body: JSON.stringify(splits),
    });
  },

  getBalances(
    token: string,
    params: GetBalancesParams = {},
  ): Promise<BalanceSnapshot[]> {
    const qs = buildQueryString(params);
    return request<BalanceSnapshot[]>(`/balances${qs}`, token);
  },

  getMonthlyOverview(token: string, params: GetMonthlyOverviewParams): Promise<MonthlyOverview> {
    const qs = buildQueryString(params);
    return request<MonthlyOverview>(`/reports/monthly-overview${qs}`, token);
  },

  getCashFlow(token: string, params: GetCashFlowParams): Promise<CashFlowReport> {
    const qs = buildQueryString(params);
    return request<CashFlowReport>(`/reports/cash-flow${qs}`, token);
  },

  getCategoryTrends(
    token: string,
    params: GetCategoryTrendsParams,
  ): Promise<CategoryTrendsReport> {
    const qs = buildQueryString({
      categories: params.categories.join(","),
      months: params.months,
      end_month: params.end_month,
    });
    return request<CategoryTrendsReport>(`/reports/category-trends${qs}`, token);
  },

  getNetWorth(token: string, params: GetNetWorthParams): Promise<NetWorthReport> {
    const qs = buildQueryString(params);
    return request<NetWorthReport>(`/reports/net-worth${qs}`, token);
  },

  getSyncState(token: string): Promise<SyncState[]> {
    return request<SyncState[]>("/sync-state", token);
  },

  getCategories(token: string): Promise<Category[]> {
    return request<Category[]>("/categories", token);
  },

  postCategory(token: string, body: CreateCategoryRequest): Promise<Category> {
    return request<Category>("/categories", token, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  patchCategory(token: string, id: string, body: PatchCategoryRequest): Promise<Category> {
    return request<Category>(`/categories/${encodeURIComponent(id)}`, token, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  getConflicts(token: string, status = "open"): Promise<Conflict[]> {
    return request<Conflict[]>(`/conflicts?status=${encodeURIComponent(status)}`, token);
  },

  resolveConflict(
    token: string,
    id: string,
    body: ResolveConflictRequest,
  ): Promise<Conflict> {
    return request<Conflict>(`/conflicts/${encodeURIComponent(id)}/resolve`, token, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  plaidLink(token: string, body: PlaidLinkRequest): Promise<PlaidLinkResult> {
    return request<PlaidLinkResult>("/plaid/link", token, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  plaidSync(
    token: string,
    body: PlaidSyncRequest,
  ): Promise<PlaidSyncResult> {
    return request<PlaidSyncResult>("/plaid/sync", token, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  getBudgets(token: string, params: GetBudgetsParams): Promise<BudgetLine[]> {
    const qs = buildQueryString(params);
    return request<BudgetLine[]>(`/budgets${qs}`, token);
  },

  createBudget(token: string, body: CreateBudgetRequest): Promise<BudgetLine> {
    return request<BudgetLine>("/budgets", token, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  deleteBudget(token: string, id: string): Promise<void> {
    return request<void>(`/budgets/${encodeURIComponent(id)}`, token, {
      method: "DELETE",
    });
  },
} as const;

// React hook

export function useApiCall<T>(): [
  ApiResult<T>,
  (fn: () => Promise<T>) => Promise<void>,
] {
  const [result, setResult] = useState<ApiResult<T>>({ status: "idle" });

  const execute = useCallback(async (fn: () => Promise<T>) => {
    setResult({ status: "loading" });
    try {
      const data = await fn();
      setResult({ status: "success", data });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "An unexpected error occurred";
      const statusCode =
        err instanceof ApiError ? err.statusCode : undefined;
      setResult({ status: "error", message, statusCode });
    }
  }, []);

  return [result, execute];
}
