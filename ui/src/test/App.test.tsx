/**
 * Tests for the root App component: token gate and layout rendering.
 *
 * REQ: SEC-ACC-004, FUNC-ACCT-003, FUNC-ACCT-004, FUNC-ACCT-005,
 * REQ: FUNC-TXN-001, FUNC-TXN-002, FUNC-TXN-003, FUNC-SYNC-007, FUNC-REP-006,
 * REQ: SEC-DATA-001
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
      getSyncState: vi.fn().mockResolvedValue([]),
      getCategories: vi.fn().mockResolvedValue([]),
      postCategory: vi.fn(),
      patchCategory: vi.fn(),
      getConflicts: vi.fn().mockResolvedValue([]),
      resolveConflict: vi.fn(),
      plaidLink: vi.fn(),
      plaidSync: vi.fn(),
      getBudgets: vi.fn().mockResolvedValue([]),
      createBudget: vi.fn(),
      deleteBudget: vi.fn(),
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
