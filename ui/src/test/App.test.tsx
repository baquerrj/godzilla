/**
 * Tests for the root App component: token gate and layout rendering.
 *
 * REQ: SEC-ACC-004, FUNC-ACCT-003, FUNC-ACCT-004, FUNC-ACCT-005,
 * REQ: FUNC-TXN-001, FUNC-TXN-002, FUNC-TXN-003, FUNC-SYNC-007,
 * REQ: FUNC-REP-001, FUNC-REP-003, FUNC-REP-004, FUNC-REP-005, FUNC-REP-006,
 * REQ: FUNC-EXP-001, FUNC-BKP-001, FUNC-SET-001,
 * REQ: SEC-ACC-001, SEC-DATA-001
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { App } from "../App";

// Mock Tauri invoke so tests run outside the Tauri runtime.
vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

// Mock all API calls — components are tested in isolation elsewhere.
vi.mock("../api/client", async () => {
  const actual =
    await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    GodzillaApi: {
      getAccounts: vi.fn().mockResolvedValue([]),
      getTransactions: vi.fn().mockResolvedValue([]),
      getTransaction: vi.fn(),
      patchTransaction: vi.fn(),
      postSplits: vi.fn(),
      getBalances: vi.fn().mockResolvedValue([]),
      getMonthlyOverview: vi.fn().mockResolvedValue({
        month: "2026-01",
        start_date: "2026-01-01",
        end_date: "2026-01-31",
        income: 0,
        expenses: 0,
        net_savings: 0,
        savings_rate: 0,
        top_categories: [],
        inclusion_note: "note",
        includes_excluded_items: false,
      }),
      getCashFlow: vi.fn().mockResolvedValue({
        start_date: "2026-01-01",
        end_date: "2026-01-31",
        points: [],
        inclusion_note: "note",
        includes_excluded_items: false,
      }),
      getCategoryTrends: vi.fn().mockResolvedValue({
        start_month: "2026-01",
        end_month: "2026-01",
        months: 1,
        series: [],
        inclusion_note: "note",
        includes_excluded_items: false,
      }),
      getNetWorth: vi.fn().mockResolvedValue({
        start_date: "2026-01-01",
        end_date: "2026-01-31",
        points: [],
      }),
      getSyncState: vi.fn().mockResolvedValue([]),
      getCategories: vi.fn().mockResolvedValue([]),
      postCategory: vi.fn(),
      patchCategory: vi.fn(),
      getConflicts: vi.fn().mockResolvedValue([]),
      resolveConflict: vi.fn(),
      plaidLink: vi.fn(),
      plaidSync: vi.fn(),
      unlinkItem: vi.fn(),
      getBudgets: vi.fn().mockResolvedValue([]),
      createBudget: vi.fn(),
      deleteBudget: vi.fn(),
      exportTransactions: vi.fn(),
      exportCategoriesBudgetsCsv: vi.fn(),
      exportCategoriesBudgetsJson: vi.fn(),
      createBackup: vi.fn(),
      restoreBackup: vi.fn(),
      wipeData: vi.fn(),
      reinitializeDatabase: vi.fn(),
      getSettings: vi.fn().mockResolvedValue({
        timezone: "UTC",
        currency: "USD",
        retention: { retain_raw_payloads: true, retain_logs_days: 90 },
        export_defaults: { include_raw_payloads: false },
        security: { auto_lock_minutes: 15 },
        sync: {
          schedule_enabled: false,
          frequency_minutes: 360,
          scheduler_supported: false,
        },
      }),
      setUnlockToken: vi.fn(),
      getAuthStatus: vi.fn().mockResolvedValue({
        pin_configured: false,
        setup_required: false,
        locked: false,
        auto_lock_minutes: 15,
        unlock_expires_at_utc: null,
        dev_bypass_enabled: true,
        tls: { enabled: false, cert_fingerprint_sha256: null },
      }),
      setupPin: vi.fn(),
      unlock: vi.fn(),
      updateSettings: vi.fn(),
      getAuditLog: vi.fn().mockResolvedValue({ entries: [], limit: 50, offset: 0 }),
      exportAuditLogCsv: vi.fn(),
    },
  };
});

import { invoke } from "@tauri-apps/api/core";
const mockInvoke = vi.mocked(invoke);
const tauriWindow = window as Window & { __TAURI_INTERNALS__?: unknown };

describe("App", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    tauriWindow.__TAURI_INTERNALS__ = {};
  });

  it("shows loading state while fetching token", () => {
    let resolveToken: (value: string) => void = () => {};
    mockInvoke.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveToken = resolve;
        }),
    );
    render(<App />);
    expect(screen.getByText(/connecting/i)).toBeInTheDocument();
    resolveToken("");
  });

  it("shows error when token is empty  REQ: SEC-ACC-004", async () => {
    mockInvoke.mockResolvedValue("");
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/GODZILLA_API_TOKEN/)).toBeInTheDocument();
    });
  });

  it("renders main panels when token is present  REQ: SEC-ACC-004", async () => {
    mockInvoke.mockResolvedValue("test-token-abc");
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId("sync-state-panel")).toBeInTheDocument();
      expect(screen.getByTestId("accounts-panel")).toBeInTheDocument();
      expect(screen.getByTestId("transaction-filters")).toBeInTheDocument();
      expect(screen.getByTestId("transactions-panel")).toBeInTheDocument();
      expect(screen.getByTestId("reports-panel")).toBeInTheDocument();
      expect(screen.getByTestId("settings-panel")).toBeInTheDocument();
      expect(screen.getByTestId("export-panel")).toBeInTheDocument();
      expect(screen.getByTestId("data-management-panel")).toBeInTheDocument();
      expect(screen.getByTestId("balances-panel")).toBeInTheDocument();
    });
  });

  it("falls back to dev proxy token when tauri runtime is unavailable  REQ: SEC-DATA-001", async () => {
    delete tauriWindow.__TAURI_INTERNALS__;
    mockInvoke.mockRejectedValue(new Error("No Tauri runtime"));

    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId("sync-state-panel")).toBeInTheDocument();
      expect(mockInvoke).not.toHaveBeenCalled();
    });
  });

  it("renders budget-panel when token is present  REQ: FUNC-BUD-001", async () => {
    mockInvoke.mockResolvedValue("test-token-abc");
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId("budget-panel")).toBeInTheDocument();
    });
  });
});
