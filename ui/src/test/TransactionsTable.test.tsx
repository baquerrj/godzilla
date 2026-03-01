/**
 * Tests for TransactionsTable: rendering, pagination, sorting, filters.
 *
 * REQ: FUNC-TXN-001, FUNC-TXN-002, FUNC-TXN-003
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TransactionsTable } from "../components/TransactionsTable";
import type { Transaction } from "../api/types";

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
const mockGetTransactions = vi.mocked(GodzillaApi.getTransactions);

const TOKEN = "tok";

const makeTxn = (id: string, overrides: Partial<Transaction> = {}): Transaction => ({
  transaction_id: id,
  account_id: "acc1",
  provider_account_id: "prov1",
  account_name: "Checking",
  date: "2025-01-15",
  amount: 42.0,
  currency: "USD",
  status: "posted",
  merchant_name: "Coffee Shop",
  display_name: "Coffee Shop",
  is_transfer: false,
  is_excluded: false,
  category_id: null,
  notes: null,
  ...overrides,
});

describe("TransactionsTable", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows empty state when no transactions  REQ: FUNC-TXN-001", async () => {
    mockGetTransactions.mockResolvedValue([]);
    render(<TransactionsTable token={TOKEN} refreshKey={0} />);
    await waitFor(() => {
      expect(screen.getByText(/no transactions/i)).toBeInTheDocument();
    });
  });

  it("renders transaction rows  REQ: FUNC-TXN-001", async () => {
    mockGetTransactions.mockResolvedValue([
      makeTxn("txn-1", {
        account_name: "Plaid Diamond 12.5% APR Interest Credit Card",
        merchant_name: "Starbucks",
        amount: 5.75,
      }),
    ]);
    render(<TransactionsTable token={TOKEN} refreshKey={0} />);
    await waitFor(() => {
      expect(screen.getByTestId("transactions-table")).toBeInTheDocument();
      expect(
        screen.getByText("Plaid Diamond 12.5% APR Interest Credit Card"),
      ).toBeInTheDocument();
      expect(screen.getByText("Starbucks")).toBeInTheDocument();
      expect(screen.getByText("5.75")).toBeInTheDocument();
    });
  });

  it("shows error on fetch failure  REQ: FUNC-TXN-001", async () => {
    mockGetTransactions.mockRejectedValue(new Error("DB error"));
    render(<TransactionsTable token={TOKEN} refreshKey={0} />);
    await waitFor(() => {
      expect(
        screen.getByText(/failed to load transactions/i),
      ).toBeInTheDocument();
    });
  });

  it("next page is disabled when fewer rows than page size  REQ: FUNC-TXN-001", async () => {
    mockGetTransactions.mockResolvedValue([makeTxn("t1")]);
    render(<TransactionsTable token={TOKEN} refreshKey={0} />);
    await waitFor(() =>
      expect(screen.getByTestId("next-btn")).toBeDisabled(),
    );
    expect(screen.getByTestId("prev-btn")).toBeDisabled();
  });

  it("requests next page on Next click  REQ: FUNC-TXN-001", async () => {
    // Return a full page so Next is enabled
    const fullPage = Array.from({ length: 50 }, (_, i) => makeTxn(`t${i}`));
    mockGetTransactions.mockResolvedValue(fullPage);
    render(<TransactionsTable token={TOKEN} refreshKey={0} />);
    await waitFor(() =>
      expect(screen.getByTestId("next-btn")).not.toBeDisabled(),
    );

    await userEvent.click(screen.getByTestId("next-btn"));
    await waitFor(() => {
      expect(mockGetTransactions).toHaveBeenLastCalledWith(
        TOKEN,
        expect.objectContaining({ offset: 50 }),
      );
    });
  });

  it("toggles sort order on repeated column click  REQ: FUNC-TXN-001", async () => {
    // Provide one row so the table (and its sortable headers) are rendered.
    mockGetTransactions.mockResolvedValue([makeTxn("t-sort")]);
    render(<TransactionsTable token={TOKEN} refreshKey={0} />);
    await waitFor(() => screen.getByTestId("sort-date"));

    // First click: switch to amount desc
    await userEvent.click(screen.getByTestId("sort-amount"));
    await waitFor(() =>
      expect(mockGetTransactions).toHaveBeenLastCalledWith(
        TOKEN,
        expect.objectContaining({ sort_by: "amount", sort_order: "desc" }),
      ),
    );

    // Second click: toggle to amount asc
    await userEvent.click(screen.getByTestId("sort-amount"));
    await waitFor(() =>
      expect(mockGetTransactions).toHaveBeenLastCalledWith(
        TOKEN,
        expect.objectContaining({ sort_by: "amount", sort_order: "asc" }),
      ),
    );
  });

  it("passes filter params to getTransactions  REQ: FUNC-TXN-002", async () => {
    mockGetTransactions.mockResolvedValue([makeTxn("txn-filter")]);
    render(
      <TransactionsTable
        token={TOKEN}
        refreshKey={0}
        filters={{
          merchant: "Coffee",
          category_id: "food_coffee",
          account_id: "acc1",
        }}
      />,
    );
    await waitFor(() => {
      expect(mockGetTransactions).toHaveBeenLastCalledWith(
        TOKEN,
        expect.objectContaining({
          merchant: "Coffee",
          category_id: "food_coffee",
          account_id: "acc1",
        }),
      );
    });
  });

  it("calls onSelectTransaction when a row is clicked  REQ: FUNC-TXN-003", async () => {
    mockGetTransactions.mockResolvedValue([makeTxn("txn-choose")]);
    const onSelect = vi.fn();
    render(
      <TransactionsTable
        token={TOKEN}
        refreshKey={0}
        onSelectTransaction={onSelect}
      />,
    );
    await waitFor(() => screen.getByTestId("txn-row-txn-choose"));
    await userEvent.click(screen.getByTestId("txn-row-txn-choose"));
    expect(onSelect).toHaveBeenCalledWith("txn-choose");
  });
});
