/**
 * Typed HTTP client for the Godzilla local API sidecar.
 *
 * REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-003, FUNC-ACCT-004,
 * REQ: FUNC-ACCT-005, FUNC-ACCT-008, FUNC-SYNC-001, FUNC-TXN-001, FUNC-TXN-002,
 * REQ: FUNC-TXN-003, FUNC-TXN-004, FUNC-TXN-005, FUNC-TXN-006,
 * REQ: FUNC-TXN-007, FUNC-TXN-008, FUNC-CAT-001, FUNC-CAT-002,
 * REQ: FUNC-SYNC-006, FUNC-SYNC-007,
 * REQ: FUNC-REP-001, FUNC-REP-002, FUNC-REP-003, FUNC-REP-004, FUNC-REP-005,
 * REQ: FUNC-REP-006, FUNC-REP-007, FUNC-REP-008,
 * REQ: FUNC-BUD-001, FUNC-BUD-002, FUNC-BUD-003, FUNC-BUD-004,
 * REQ: FUNC-EXP-001, FUNC-EXP-002, FUNC-EXP-003,
 * REQ: FUNC-BKP-001, FUNC-BKP-002, FUNC-BKP-003, FUNC-BKP-004, FUNC-BKP-006,
 * REQ: FUNC-SET-001, FUNC-SET-002, FUNC-SET-003, FUNC-SET-004, FUNC-SET-005,
 * REQ: FUNC-AUD-001, FUNC-AUD-004,
 * REQ: SEC-ACC-001, SEC-ACC-002, SEC-ACC-003, SEC-ACC-004, SEC-NET-001
 */

import { useCallback, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import type {
  Account,
  ApiResult,
  AuditLogResponse,
  BackupRequest,
  BalanceSnapshot,
  BlobDownload,
  BudgetLine,
  CashFlowReport,
  CategoriesBudgetsExportJson,
  Category,
  CategoryTrendsReport,
  Conflict,
  CreateBudgetRequest,
  CreateCategoryRequest,
  ExportCategoriesBudgetsParams,
  ExportTransactionsParams,
  GetAuditLogParams,
  GetBalancesParams,
  GetBudgetsParams,
  GetCashFlowParams,
  GetCategoryTrendsParams,
  GetMonthlyOverviewParams,
  GetNetWorthParams,
  GetTransactionsParams,
  MonthlyOverview,
  NetWorthReport,
  AuthStatus,
  PatchCategoryRequest,
  PatchTransactionRequest,
  PlaidLinkRequest,
  PlaidLinkResult,
  PlaidSyncRequest,
  PlaidSyncResult,
  SetupPinRequest,
  SetupPinResponse,
  ReinitializeResponse,
  ResolveConflictRequest,
  RestoreResponse,
  SettingsResponse,
  SplitItem,
  SyncState,
  UnlockRequest,
  UnlockResponse,
  Transaction,
  TransactionDetail,
  UnlinkItemResult,
  UpdateSettingsRequest,
  WipeRequest,
  WipeResponse,
} from "./types";

// Internal helpers

const API_BASE: string = import.meta.env.DEV
  ? "/api"
  : "https://127.0.0.1:8787";

let unlockToken: string | null = null;

export class ApiError extends Error {
  constructor(
    public readonly statusCode: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type RuntimeHttpResponse = {
  status: number;
  headers: Headers;
  body: Uint8Array;
};

type TauriApiProxyRequest = {
  method: string;
  path: string;
  headers: Array<{ name: string; value: string }>;
  bodyBase64?: string;
};

type TauriApiProxyResponse = {
  status: number;
  headers: Array<{ name: string; value: string }>;
  bodyBase64: string;
};

function hasTauriRuntime(): boolean {
  return (
    typeof window !== "undefined"
    && "__TAURI_INTERNALS__" in (window as unknown as Record<string, unknown>)
  );
}

function buildHeaders(apiToken: string, options: RequestInit): Headers {
  const headers = new Headers(options.headers);
  headers.set("X-API-Key", apiToken);
  if (unlockToken) {
    headers.set("X-App-Unlock-Token", unlockToken);
  }
  const hasBody = options.body !== undefined;
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  if (hasBody && !isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return headers;
}

function parseErrorPayload(statusCode: number, rawBody: string): never {
  let message = `HTTP ${statusCode}`;
  try {
    const body = JSON.parse(rawBody) as { detail?: string };
    if (body.detail) {
      message = body.detail;
    }
  } catch {
    // Ignore JSON parse failure.
  }
  if (statusCode === 423) {
    unlockToken = null;
    if (typeof window !== "undefined") {
      window.dispatchEvent(new Event("godzilla-lock"));
    }
  }
  throw new ApiError(statusCode, message);
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

function base64ToBytes(value: string): Uint8Array {
  if (!value) return new Uint8Array();
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function isFormDataBody(body: BodyInit | null | undefined): body is FormData {
  return typeof FormData !== "undefined" && body instanceof FormData;
}

async function encodeRequestBody(
  options: RequestInit,
  headers: Headers,
): Promise<string | undefined> {
  const body = options.body;
  if (body === undefined || body === null) {
    return undefined;
  }

  if (typeof body === "string") {
    return bytesToBase64(new TextEncoder().encode(body));
  }

  if (body instanceof URLSearchParams) {
    return bytesToBase64(new TextEncoder().encode(body.toString()));
  }

  if (body instanceof Blob) {
    const bytes = new Uint8Array(await body.arrayBuffer());
    return bytesToBase64(bytes);
  }

  if (body instanceof ArrayBuffer) {
    return bytesToBase64(new Uint8Array(body));
  }

  if (body instanceof Uint8Array) {
    return bytesToBase64(body);
  }

  if (isFormDataBody(body)) {
    // Serialize FormData with browser-generated multipart boundary.
    const syntheticRequest = new Request("https://127.0.0.1", {
      method: options.method ?? "POST",
      body,
    });
    const contentType = syntheticRequest.headers.get("Content-Type");
    if (contentType && !headers.has("Content-Type")) {
      headers.set("Content-Type", contentType);
    }
    const bytes = new Uint8Array(await syntheticRequest.arrayBuffer());
    return bytesToBase64(bytes);
  }

  return undefined;
}

function shouldUseTauriTransport(): boolean {
  // REQ: SEC-NET-001 — Tauri runtime enforces pinned local TLS through backend proxy command.
  return hasTauriRuntime();
}

async function fetchResponse(
  path: string,
  options: RequestInit,
  headers: Headers,
): Promise<RuntimeHttpResponse> {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, { ...options, headers });
  return {
    status: response.status,
    headers: response.headers,
    body: new Uint8Array(await response.arrayBuffer()),
  };
}

async function tauriResponse(
  path: string,
  options: RequestInit,
  headers: Headers,
): Promise<RuntimeHttpResponse> {
  const request: TauriApiProxyRequest = {
    method: (options.method ?? "GET").toUpperCase(),
    path,
    headers: Array.from(headers.entries()).map(([name, value]) => ({ name, value })),
  };
  const bodyBase64 = await encodeRequestBody(options, headers);
  if (bodyBase64) {
    request.bodyBase64 = bodyBase64;
  }

  let proxyResponse: TauriApiProxyResponse;
  try {
    proxyResponse = await invoke<TauriApiProxyResponse>("api_request", { request });
  } catch (error) {
    throw new ApiError(0, String(error));
  }

  const responseHeaders = new Headers();
  for (const header of proxyResponse.headers) {
    responseHeaders.set(header.name, header.value);
  }
  return {
    status: proxyResponse.status,
    headers: responseHeaders,
    body: base64ToBytes(proxyResponse.bodyBase64),
  };
}

async function executeRequest(
  path: string,
  apiToken: string,
  options: RequestInit = {},
): Promise<RuntimeHttpResponse> {
  const headers = buildHeaders(apiToken, options);
  if (shouldUseTauriTransport()) {
    return tauriResponse(path, options, headers);
  }
  return fetchResponse(path, options, headers);
}

async function request<T>(
  path: string,
  apiToken: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await executeRequest(path, apiToken, options);
  const responseText = new TextDecoder().decode(response.body);

  if (response.status < 200 || response.status >= 300) {
    parseErrorPayload(response.status, responseText);
  }

  if (response.status === 204) return undefined as unknown as T;

  return JSON.parse(responseText) as T;
}

function parseFilename(contentDisposition: string | null): string | null {
  if (!contentDisposition) return null;

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1]);
  }

  const simpleMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
  if (simpleMatch?.[1]) {
    return simpleMatch[1];
  }

  return null;
}

async function requestBlob(
  path: string,
  apiToken: string,
  options: RequestInit = {},
): Promise<BlobDownload> {
  const response = await executeRequest(path, apiToken, options);
  const responseText = new TextDecoder().decode(response.body);
  if (response.status < 200 || response.status >= 300) {
    parseErrorPayload(response.status, responseText);
  }

  const contentType = response.headers.get("Content-Type") ?? "application/octet-stream";
  const blob = new Blob([response.body], { type: contentType });
  return {
    blob,
    filename: parseFilename(response.headers.get("Content-Disposition")),
    contentType,
  };
}

function buildQueryString<T extends object>(params: T): string {
  const entries = Object.entries(params as Record<string, unknown>).filter(([, value]) =>
    typeof value === "string" || typeof value === "number" || typeof value === "boolean",
  );
  if (entries.length === 0) return "";
  const qs = new URLSearchParams(entries.map(([key, value]) => [key, String(value)]));
  return `?${qs.toString()}`;
}

// Public API client

export const GodzillaApi = {
  setUnlockToken(token: string | null): void {
    unlockToken = token;
  },

  getAuthStatus(token: string): Promise<AuthStatus> {
    return request<AuthStatus>("/auth/status", token);
  },

  setupPin(token: string, body: SetupPinRequest): Promise<SetupPinResponse> {
    return request<SetupPinResponse>("/auth/setup-pin", token, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  unlock(token: string, body: UnlockRequest): Promise<UnlockResponse> {
    return request<UnlockResponse>("/auth/unlock", token, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

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

  unlinkItem(
    token: string,
    itemId: string,
    mode: "keep" | "purge",
  ): Promise<UnlinkItemResult> {
    return request<UnlinkItemResult>(
      `/plaid/items/${encodeURIComponent(itemId)}?mode=${encodeURIComponent(mode)}`,
      token,
      { method: "DELETE" },
    );
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

  exportTransactions(token: string, params: ExportTransactionsParams = {}): Promise<BlobDownload> {
    const qs = buildQueryString(params);
    return requestBlob(`/export/transactions${qs}`, token);
  },

  exportCategoriesBudgetsCsv(
    token: string,
    params: ExportCategoriesBudgetsParams = {},
  ): Promise<BlobDownload> {
    const qs = buildQueryString({ format: "csv", month: params.month });
    return requestBlob(`/export/categories-budgets${qs}`, token);
  },

  exportCategoriesBudgetsJson(
    token: string,
    params: ExportCategoriesBudgetsParams = {},
  ): Promise<CategoriesBudgetsExportJson> {
    const qs = buildQueryString({ format: "json", month: params.month });
    return request<CategoriesBudgetsExportJson>(`/export/categories-budgets${qs}`, token);
  },

  createBackup(token: string, body: BackupRequest): Promise<BlobDownload> {
    return requestBlob("/backup", token, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  restoreBackup(
    token: string,
    payload: { passphrase: string; file: File },
  ): Promise<RestoreResponse> {
    const body = new FormData();
    body.append("passphrase", payload.passphrase);
    body.append("backup_file", payload.file);
    return request<RestoreResponse>("/restore", token, {
      method: "POST",
      body,
    });
  },

  wipeData(token: string, body: WipeRequest): Promise<WipeResponse> {
    return request<WipeResponse>("/wipe", token, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  reinitializeDatabase(token: string): Promise<ReinitializeResponse> {
    return request<ReinitializeResponse>("/reinitialize", token, {
      method: "POST",
    });
  },

  getSettings(token: string): Promise<SettingsResponse> {
    return request<SettingsResponse>("/settings", token);
  },

  updateSettings(token: string, body: UpdateSettingsRequest): Promise<SettingsResponse> {
    return request<SettingsResponse>("/settings", token, {
      method: "PUT",
      body: JSON.stringify(body),
    });
  },

  getAuditLog(token: string, params: GetAuditLogParams = {}): Promise<AuditLogResponse> {
    const qs = buildQueryString({ format: "json", ...params });
    return request<AuditLogResponse>(`/audit-log${qs}`, token);
  },

  exportAuditLogCsv(token: string, params: GetAuditLogParams = {}): Promise<BlobDownload> {
    const qs = buildQueryString({ format: "csv", ...params });
    return requestBlob(`/audit-log${qs}`, token);
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
