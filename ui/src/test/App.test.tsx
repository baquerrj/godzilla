/**
 * Tests for the root App component: token gate and layout rendering.
 *
 * REQ: TECH-SEC-ACC-004, ACC-ACCT-003, ACC-ACCT-004, ACC-ACCT-005,
 * REQ: ACC-TXN-001, ACC-TXN-002, ACC-TXN-003, ACC-SYNC-007,
 * REQ: ACC-REP-001, ACC-REP-003, ACC-REP-004, ACC-REP-005, ACC-REP-006,
 * REQ: ACC-EXP-001, ACC-BKP-001, ACC-SET-001,
 * REQ: TECH-SEC-ACC-001, TECH-SEC-DATA-001
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
import { GodzillaApi } from "../api/client";
const mockInvoke = vi.mocked(invoke);
const mockGetCategories = vi.mocked(GodzillaApi.getCategories);
const mockGetMonthlyOverview = vi.mocked(GodzillaApi.getMonthlyOverview);
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

  it("shows error when token is empty  REQ: TECH-SEC-ACC-004", async () => {
    mockInvoke.mockResolvedValue("");
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/GODZILLA_API_TOKEN/)).toBeInTheDocument();
    });
  });

  it("renders overview tab by default when token is present  REQ: TECH-SEC-ACC-004", async () => {
    mockInvoke.mockResolvedValue("test-token-abc");
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId("app-tabs")).toBeInTheDocument();
      expect(screen.getByTestId("sync-state-panel")).toBeInTheDocument();
      expect(screen.getByTestId("accounts-panel")).toBeInTheDocument();
      expect(screen.getByTestId("balances-panel")).toBeInTheDocument();
      expect(screen.queryByTestId("transactions-panel")).not.toBeInTheDocument();
      expect(screen.queryByTestId("reports-panel")).not.toBeInTheDocument();
      expect(screen.queryByTestId("settings-panel")).not.toBeInTheDocument();
    });
  });

  it("switches tabs while keeping visited section panels mounted  REQ: ACC-TXN-001, ACC-REP-001, ACC-SET-001", async () => {
    mockInvoke.mockResolvedValue("test-token-abc");
    render(<App />);

    await waitFor(() => expect(screen.getByTestId("tab-transactions")).toBeInTheDocument());

    await userEvent.click(screen.getByTestId("tab-transactions"));
    await waitFor(() => {
      expect(screen.getByTestId("tab-panel-overview")).toHaveAttribute("hidden");
      expect(screen.getByTestId("tab-panel-transactions")).not.toHaveAttribute("hidden");
      expect(screen.getByTestId("transaction-filters")).toBeInTheDocument();
      expect(screen.getByTestId("transactions-panel")).toBeInTheDocument();
      expect(screen.getByTestId("sync-state-panel")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByTestId("tab-reports"));
    await waitFor(() => {
      expect(screen.getByTestId("tab-panel-transactions")).toHaveAttribute("hidden");
      expect(screen.getByTestId("tab-panel-reports")).not.toHaveAttribute("hidden");
      expect(screen.getByTestId("budget-panel")).toBeInTheDocument();
      expect(screen.getByTestId("reports-panel")).toBeInTheDocument();
      expect(screen.getByTestId("transactions-panel")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByTestId("tab-data"));
    await waitFor(() => {
      expect(screen.getByTestId("tab-panel-reports")).toHaveAttribute("hidden");
      expect(screen.getByTestId("tab-panel-data")).not.toHaveAttribute("hidden");
      expect(screen.getByTestId("settings-panel")).toBeInTheDocument();
      expect(screen.getByTestId("export-panel")).toBeInTheDocument();
      expect(screen.getByTestId("data-management-panel")).toBeInTheDocument();
      expect(screen.getByTestId("reports-panel")).toBeInTheDocument();
    });
  });

  it("does not refetch reports when returning to an already mounted reports tab  REQ: ACC-REP-008", async () => {
    mockInvoke.mockResolvedValue("test-token-abc");
    render(<App />);

    await waitFor(() => expect(screen.getByTestId("tab-reports")).toBeInTheDocument());
    await userEvent.click(screen.getByTestId("tab-reports"));
    await waitFor(() => {
      expect(screen.getByTestId("reports-panel")).toBeInTheDocument();
      expect(mockGetMonthlyOverview).toHaveBeenCalledTimes(1);
    });

    await userEvent.click(screen.getByTestId("tab-transactions"));
    await userEvent.click(screen.getByTestId("tab-reports"));
    await waitFor(() => {
      expect(screen.getByTestId("reports-panel")).toBeInTheDocument();
    });
    expect(mockGetMonthlyOverview).toHaveBeenCalledTimes(1);
  });

  it("falls back to dev proxy token when tauri runtime is unavailable  REQ: TECH-SEC-DATA-001", async () => {
    delete tauriWindow.__TAURI_INTERNALS__;
    mockInvoke.mockRejectedValue(new Error("No Tauri runtime"));

    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId("sync-state-panel")).toBeInTheDocument();
      expect(mockInvoke).not.toHaveBeenCalled();
    });
  });

  it("renders budget-panel when token is present  REQ: ACC-BUD-001", async () => {
    mockInvoke.mockResolvedValue("test-token-abc");
    render(<App />);
    await waitFor(() => screen.getByTestId("tab-reports"));
    await userEvent.click(screen.getByTestId("tab-reports"));
    await waitFor(() => {
      expect(screen.getByTestId("budget-panel")).toBeInTheDocument();
    });
  });

  it("preserves selected report trend categories across tab switches  REQ: ACC-REP-004", async () => {
    mockInvoke.mockResolvedValue("test-token-abc");
    mockGetCategories.mockResolvedValue([
      { category_id: "food", name: "Food", parent_id: null, active: true },
      { category_id: "food_fast_food", name: "Fast Food", parent_id: "food", active: true },
      { category_id: "fees", name: "Fees", parent_id: null, active: true },
      { category_id: "fees_atm", name: "ATM Fees", parent_id: "fees", active: true },
    ]);

    render(<App />);
    await waitFor(() => screen.getByTestId("tab-reports"));
    await userEvent.click(screen.getByTestId("tab-reports"));
    await waitFor(() => screen.getByTestId("report-trend-categories"));

    const trendSelect = screen.getByTestId("report-trend-categories") as HTMLSelectElement;
    for (const option of Array.from(trendSelect.options)) {
      option.selected = option.value === "food_fast_food";
    }
    fireEvent.change(trendSelect);

    await waitFor(() => {
      const selectedValues = Array.from(
        (screen.getByTestId("report-trend-categories") as HTMLSelectElement).selectedOptions,
      ).map((option) => option.value);
      expect(selectedValues).toEqual(["food_fast_food"]);
    });

    await userEvent.click(screen.getByTestId("tab-transactions"));
    await userEvent.click(screen.getByTestId("tab-reports"));
    await waitFor(() => {
      const selectedValues = Array.from(
        (screen.getByTestId("report-trend-categories") as HTMLSelectElement).selectedOptions,
      ).map((option) => option.value);
      expect(selectedValues).toEqual(["food_fast_food"]);
    });
  });
});
