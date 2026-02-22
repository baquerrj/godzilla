/**
 * Typed HTTP client for the Godzilla local API sidecar.
 *
 * All six MVP endpoints are covered.  Each function accepts an API token
 * as its first argument so the caller (typically obtained from a Tauri
 * invoke command) controls the credential lifetime.
 *
 * Base URL selection:
 *   - Dev (Vite proxy):  /api  →  Vite forwards to 127.0.0.1:8787
 *   - Production build:  http://127.0.0.1:8787  (no proxy available)
 *
 * REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-003, FUNC-ACCT-004,
 * REQ: FUNC-ACCT-005, FUNC-SYNC-001, FUNC-TXN-001, FUNC-REP-006,
 * REQ: SEC-ACC-004
 */

import { useCallback, useState } from "react";
import type {
  Account,
  ApiResult,
  BalanceSnapshot,
  GetBalancesParams,
  GetTransactionsParams,
  PlaidLinkRequest,
  PlaidLinkResult,
  PlaidSyncRequest,
  PlaidSyncResult,
  SyncState,
  Transaction,
} from "./types";

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** In dev the Vite proxy strips /api and forwards to 127.0.0.1:8787.
 *  In production Tauri builds the WebView loads from tauri://localhost so
 *  we must use the absolute loopback address instead.
 */
const API_BASE: string = import.meta.env.DEV
  ? "/api"
  : "http://127.0.0.1:8787";

/** Structured error carrying the HTTP status code from the sidecar. */
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
      // Ignore JSON parse failure — keep the generic status message.
    }
    throw new ApiError(response.status, message);
  }

  return response.json() as Promise<T>;
}

function buildQueryString(
  params: Record<string, string | number | boolean | undefined>,
): string {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== null,
  );
  if (entries.length === 0) return "";
  const qs = new URLSearchParams(entries.map(([k, v]) => [k, String(v)]));
  return `?${qs.toString()}`;
}

// ---------------------------------------------------------------------------
// Public API client
// ---------------------------------------------------------------------------

/**
 * Godzilla API client.
 *
 * A plain object of async functions — no class instantiation required.
 * The API token is passed per-call so individual views can use different
 * token sources (e.g., a Tauri invoke command vs. a test fixture).
 *
 * REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-003, FUNC-ACCT-004,
 * REQ: FUNC-ACCT-005, FUNC-SYNC-001, FUNC-TXN-001, FUNC-REP-006,
 * REQ: SEC-ACC-004
 */
export const GodzillaApi = {
  /**
   * List all linked accounts.
   *
   * REQ: FUNC-ACCT-003
   */
  getAccounts(token: string): Promise<Account[]> {
    return request<Account[]>("/accounts", token);
  },

  /**
   * List transactions with optional pagination and sorting.
   *
   * REQ: FUNC-TXN-001
   */
  getTransactions(
    token: string,
    params: GetTransactionsParams = {},
  ): Promise<Transaction[]> {
    const qs = buildQueryString(
      params as Record<string, string | number | boolean | undefined>,
    );
    return request<Transaction[]>(`/transactions${qs}`, token);
  },

  /**
   * List balance snapshots with optional account filter and pagination.
   *
   * REQ: FUNC-REP-006
   */
  getBalances(
    token: string,
    params: GetBalancesParams = {},
  ): Promise<BalanceSnapshot[]> {
    const qs = buildQueryString(
      params as Record<string, string | number | boolean | undefined>,
    );
    return request<BalanceSnapshot[]>(`/balances${qs}`, token);
  },

  /**
   * List per-item sync state for all linked Plaid items.
   *
   * REQ: FUNC-ACCT-004
   */
  getSyncState(token: string): Promise<SyncState[]> {
    return request<SyncState[]>("/sync-state", token);
  },

  /**
   * Create a sandbox Plaid item and store its access token.
   *
   * REQ: FUNC-ACCT-001, FUNC-ACCT-002
   */
  plaidLink(token: string, body: PlaidLinkRequest): Promise<PlaidLinkResult> {
    return request<PlaidLinkResult>("/plaid/link", token, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  /**
   * Trigger an incremental sync for one Plaid item.
   *
   * REQ: FUNC-ACCT-005, FUNC-SYNC-001
   */
  plaidSync(
    token: string,
    body: PlaidSyncRequest,
  ): Promise<PlaidSyncResult> {
    return request<PlaidSyncResult>("/plaid/sync", token, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
} as const;

// ---------------------------------------------------------------------------
// React hook
// ---------------------------------------------------------------------------

/**
 * React hook for wrapping any GodzillaApi call with loading/error/success state.
 *
 * REQ: FUNC-ACCT-003, FUNC-TXN-001, FUNC-REP-006
 *
 * @example
 * ```tsx
 * const [result, execute] = useApiCall<Account[]>();
 *
 * useEffect(() => {
 *   execute(() => GodzillaApi.getAccounts(token));
 * }, [token]);
 *
 * if (result.status === "loading") return <Spinner />;
 * if (result.status === "error")   return <ErrorBanner message={result.message} />;
 * if (result.status === "success") return <AccountList accounts={result.data} />;
 * return null;
 * ```
 */
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
