/**
 * Tests for AccountsTable component.
 *
 * REQ: ACC-ACCT-003, ACC-ACCT-009, TECH-ACCT-009-UI
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { AccountsTable } from "../components/AccountsTable";

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
const mockGetAccounts = vi.mocked(GodzillaApi.getAccounts);

const TOKEN = "tok";

describe("AccountsTable", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows empty state when no accounts", async () => {
    mockGetAccounts.mockResolvedValue([]);
    render(<AccountsTable token={TOKEN} refreshKey={0} />);
    await waitFor(() => {
      expect(screen.getByText(/no accounts/i)).toBeInTheDocument();
    });
  });

  it("renders account rows and owner names", async () => {
    mockGetAccounts.mockResolvedValue([
      {
        account_id: "acc1",
        provider_account_id: "prov-acc-1",
        item_id: "item-1",
        institution_id: "ins_1",
        name: "Plaid Checking",
        account_type: "depository",
        subtype: "checking",
        mask: "0000",
        balance: 1200.5,
        currency: "USD",
        owner_names: [{ names: ["Alex Example", "Jordan Example"] }],
      },
    ]);
    render(<AccountsTable token={TOKEN} refreshKey={0} />);
    await waitFor(() => {
      expect(screen.getByTestId("accounts-table")).toBeInTheDocument();
      expect(screen.getByText("Plaid Checking")).toBeInTheDocument();
      expect(screen.getByText("1200.50")).toBeInTheDocument();
      expect(screen.getByText("••••0000")).toBeInTheDocument();
      expect(screen.getByText("Alex Example, Jordan Example")).toBeInTheDocument();
    });
  });

  it("shows error on fetch failure", async () => {
    mockGetAccounts.mockRejectedValue(new Error("Network error"));
    render(<AccountsTable token={TOKEN} refreshKey={0} />);
    await waitFor(() => {
      expect(
        screen.getByText(/failed to load accounts/i),
      ).toBeInTheDocument();
    });
  });

  it("re-fetches when refreshKey changes", async () => {
    mockGetAccounts.mockResolvedValue([]);
    const { rerender } = render(
      <AccountsTable token={TOKEN} refreshKey={0} />,
    );
    await waitFor(() => expect(mockGetAccounts).toHaveBeenCalledTimes(1));

    rerender(<AccountsTable token={TOKEN} refreshKey={1} />);
    await waitFor(() => expect(mockGetAccounts).toHaveBeenCalledTimes(2));
  });
});
