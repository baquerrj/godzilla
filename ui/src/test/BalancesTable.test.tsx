/**
 * Tests for BalancesTable component.
 *
 * REQ: FUNC-REP-006
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { BalancesTable } from "../components/BalancesTable";

vi.mock("../api/client", async () => {
  const actual =
    await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    GodzillaApi: {
      getAccounts: vi.fn(),
      getTransactions: vi.fn(),
      getBalances: vi.fn(),
      getSyncState: vi.fn(),
      plaidLink: vi.fn(),
      plaidSync: vi.fn(),
    },
  };
});

import { GodzillaApi } from "../api/client";
const mockGetBalances = vi.mocked(GodzillaApi.getBalances);

const TOKEN = "tok";

describe("BalancesTable", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows empty state when no snapshots  REQ: FUNC-REP-006", async () => {
    mockGetBalances.mockResolvedValue([]);
    render(<BalancesTable token={TOKEN} refreshKey={0} />);
    await waitFor(() => {
      expect(screen.getByText(/no balance snapshots/i)).toBeInTheDocument();
    });
  });

  it("renders balance rows  REQ: FUNC-REP-006", async () => {
    mockGetBalances.mockResolvedValue([
      {
        snapshot_id: "snap1",
        account_id: "acc1",
        provider_account_id: "prov-acc-1",
        date: "2025-01-15",
        balance: 4500.0,
        currency: "USD",
      },
    ]);
    render(<BalancesTable token={TOKEN} refreshKey={0} />);
    await waitFor(() => {
      expect(screen.getByTestId("balances-table")).toBeInTheDocument();
      expect(screen.getByText("2025-01-15")).toBeInTheDocument();
      expect(screen.getByText("4500.00")).toBeInTheDocument();
    });
  });

  it("shows error on fetch failure  REQ: FUNC-REP-006", async () => {
    mockGetBalances.mockRejectedValue(new Error("timeout"));
    render(<BalancesTable token={TOKEN} refreshKey={0} />);
    await waitFor(() => {
      expect(screen.getByText(/failed to load balances/i)).toBeInTheDocument();
    });
  });

  it("requests limit=100  REQ: FUNC-REP-006", async () => {
    mockGetBalances.mockResolvedValue([]);
    render(<BalancesTable token={TOKEN} refreshKey={0} />);
    await waitFor(() => {
      expect(mockGetBalances).toHaveBeenCalledWith(TOKEN, { limit: 100 });
    });
  });
});
