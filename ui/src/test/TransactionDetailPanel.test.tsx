/**
 * Tests for TransactionDetailPanel component.
 *
 * REQ: ACC-TXN-003, ACC-TXN-004, ACC-TXN-005, ACC-TXN-006,
 * REQ: ACC-TXN-007, ACC-TXN-008
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { TransactionDetailPanel } from "../components/TransactionDetailPanel";
import type { Category, TransactionDetail } from "../api/types";

vi.mock("../api/client", async () => {
  const actual =
    await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    GodzillaApi: {
      getAccounts: vi.fn(),
      getTransactions: vi.fn(),
      getTransaction: vi.fn(),
      patchTransaction: vi.fn(),
      postSplits: vi.fn(),
      getBalances: vi.fn(),
      getSyncState: vi.fn(),
      getCategories: vi.fn(),
      postCategory: vi.fn(),
      patchCategory: vi.fn(),
      getConflicts: vi.fn(),
      resolveConflict: vi.fn(),
      plaidLink: vi.fn(),
      plaidSync: vi.fn(),
    },
  };
});

import { GodzillaApi } from "../api/client";
const mockGetTransaction = vi.mocked(GodzillaApi.getTransaction);
const mockPatchTransaction = vi.mocked(GodzillaApi.patchTransaction);
const mockPostSplits = vi.mocked(GodzillaApi.postSplits);

const TOKEN = "tok";
const CATEGORIES: Category[] = [
  { category_id: "food", name: "Food", parent_id: null, active: true },
  { category_id: "food_coffee", name: "Coffee", parent_id: "food", active: true },
  { category_id: "travel", name: "Travel", parent_id: null, active: true },
];

const makeTxnDetail = (overrides: Partial<TransactionDetail> = {}): TransactionDetail => ({
  transaction_id: "txn-1",
  account_id: "acc-1",
  provider_account_id: "prov-1",
  account_name: "Checking",
  date: "2025-01-15",
  amount: 42.0,
  currency: "USD",
  status: "posted",
  merchant_name: "Coffee Shop",
  display_name: "Coffee Shop",
  is_transfer: false,
  is_excluded: false,
  category_id: "food_coffee",
  notes: "morning coffee",
  tags: ["personal"],
  splits: [],
  raw_provider_payloads: [],
  ...overrides,
});

describe("TransactionDetailPanel", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders nothing when transactionId is null  REQ: ACC-TXN-003", () => {
    const { container } = render(
      <TransactionDetailPanel
        token={TOKEN}
        transactionId={null}
        categories={[]}
        onClose={vi.fn()}
        onUpdated={vi.fn()}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("fetches and displays transaction detail  REQ: ACC-TXN-003", async () => {
    mockGetTransaction.mockResolvedValue(makeTxnDetail());
    render(
      <TransactionDetailPanel
        token={TOKEN}
        transactionId="txn-1"
        categories={CATEGORIES}
        onClose={vi.fn()}
        onUpdated={vi.fn()}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText("Transaction Detail")).toBeInTheDocument();
      expect(screen.getByText("Checking")).toBeInTheDocument();
      expect(screen.getByText("42.00 USD")).toBeInTheDocument();
      expect(screen.getByDisplayValue("morning coffee")).toBeInTheDocument();
    });
  });

  it("calls onClose when close button is clicked  REQ: ACC-TXN-003", async () => {
    mockGetTransaction.mockResolvedValue(makeTxnDetail());
    const onClose = vi.fn();
    render(
      <TransactionDetailPanel
        token={TOKEN}
        transactionId="txn-1"
        categories={CATEGORIES}
        onClose={onClose}
        onUpdated={vi.fn()}
      />,
    );
    await waitFor(() => screen.getByTestId("detail-close"));
    fireEvent.click(screen.getByTestId("detail-close"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("saves category and notes via patchTransaction  REQ: ACC-TXN-004, ACC-TXN-005", async () => {
    const detail = makeTxnDetail({ notes: "", category_id: null });
    mockGetTransaction.mockResolvedValue(detail);
    mockPatchTransaction.mockResolvedValue({ ...detail, notes: "test note" });

    const onUpdated = vi.fn();
    render(
      <TransactionDetailPanel
        token={TOKEN}
        transactionId="txn-1"
        categories={CATEGORIES}
        onClose={vi.fn()}
        onUpdated={onUpdated}
      />,
    );

    await waitFor(() => screen.getByTestId("detail-save"));
    fireEvent.change(screen.getByTestId("detail-notes"), {
      target: { value: "test note" },
    });
    fireEvent.click(screen.getByTestId("detail-save"));

    await waitFor(() => {
      expect(mockPatchTransaction).toHaveBeenCalledWith(
        TOKEN,
        "txn-1",
        expect.objectContaining({ notes: "test note" }),
      );
      expect(onUpdated).toHaveBeenCalledOnce();
    });
  });

  it("toggles transfer flag via patchTransaction  REQ: ACC-TXN-006", async () => {
    const detail = makeTxnDetail({ is_transfer: false });
    mockGetTransaction.mockResolvedValue(detail);
    mockPatchTransaction.mockResolvedValue({ ...detail, is_transfer: true });

    render(
      <TransactionDetailPanel
        token={TOKEN}
        transactionId="txn-1"
        categories={CATEGORIES}
        onClose={vi.fn()}
        onUpdated={vi.fn()}
      />,
    );

    await waitFor(() => screen.getByTestId("detail-is-transfer"));
    fireEvent.click(screen.getByTestId("detail-is-transfer"));

    await waitFor(() => {
      expect(mockPatchTransaction).toHaveBeenCalledWith(
        TOKEN,
        "txn-1",
        expect.objectContaining({ is_transfer: true }),
      );
    });
  });

  it("toggles exclude flag via patchTransaction  REQ: ACC-TXN-007", async () => {
    const detail = makeTxnDetail({ is_excluded: false });
    mockGetTransaction.mockResolvedValue(detail);
    mockPatchTransaction.mockResolvedValue({ ...detail, is_excluded: true });

    render(
      <TransactionDetailPanel
        token={TOKEN}
        transactionId="txn-1"
        categories={CATEGORIES}
        onClose={vi.fn()}
        onUpdated={vi.fn()}
      />,
    );

    await waitFor(() => screen.getByTestId("detail-is-excluded"));
    fireEvent.click(screen.getByTestId("detail-is-excluded"));

    await waitFor(() => {
      expect(mockPatchTransaction).toHaveBeenCalledWith(
        TOKEN,
        "txn-1",
        expect.objectContaining({ is_excluded: true }),
      );
    });
  });

  it("saves splits via postSplits  REQ: ACC-TXN-008", async () => {
    const detail = makeTxnDetail({
      amount: 42.0,
      splits: [{ split_id: "s1", amount: 42.0, category_id: null, notes: null }],
    });
    mockGetTransaction.mockResolvedValue(detail);
    mockPostSplits.mockResolvedValue(detail);

    render(
      <TransactionDetailPanel
        token={TOKEN}
        transactionId="txn-1"
        categories={CATEGORIES}
        onClose={vi.fn()}
        onUpdated={vi.fn()}
      />,
    );

    await waitFor(() =>
      expect(screen.getByTestId("split-save")).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId("split-save"));

    await waitFor(() => {
      expect(mockPostSplits).toHaveBeenCalledWith(TOKEN, "txn-1", [
        { amount: 42, category_id: null, notes: null },
      ]);
    });
  });

  it("shows error on fetch failure  REQ: ACC-TXN-003", async () => {
    mockGetTransaction.mockRejectedValue(new Error("not found"));
    render(
      <TransactionDetailPanel
        token={TOKEN}
        transactionId="txn-1"
        categories={CATEGORIES}
        onClose={vi.fn()}
        onUpdated={vi.fn()}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
    });
  });
});
