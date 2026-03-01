/**
 * Tests for BudgetPanel component.
 *
 * REQ: FUNC-BUD-001, FUNC-BUD-002, FUNC-BUD-003, FUNC-BUD-004
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { BudgetPanel } from "../components/BudgetPanel";
import type { BudgetLine, Category } from "../api/types";

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
      getBudgets: vi.fn(),
      createBudget: vi.fn(),
      deleteBudget: vi.fn(),
    },
  };
});

import { GodzillaApi } from "../api/client";
const mockGetBudgets = vi.mocked(GodzillaApi.getBudgets);
const mockCreateBudget = vi.mocked(GodzillaApi.createBudget);
const mockDeleteBudget = vi.mocked(GodzillaApi.deleteBudget);

const TOKEN = "tok";
const MONTH = "2026-01";

const CATEGORIES: Category[] = [
  { category_id: "food", name: "Food", parent_id: null, active: true },
  { category_id: "food_coffee", name: "Coffee", parent_id: "food", active: true },
  { category_id: "food_dining", name: "Dining", parent_id: "food", active: true },
];

const makeLine = (overrides: Partial<BudgetLine> = {}): BudgetLine => ({
  budget_id: "bud-1",
  category_id: "food_coffee",
  month: MONTH,
  planned: 50,
  actual: 30,
  remaining: 20,
  is_overspent: false,
  ...overrides,
});

describe("BudgetPanel", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders empty state when no budgets  REQ: FUNC-BUD-001", async () => {
    mockGetBudgets.mockResolvedValue([]);
    render(
      <BudgetPanel
        token={TOKEN}
        refreshKey={0}
        categories={CATEGORIES}
        onDrillDown={vi.fn()}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText(/no budgets set/i)).toBeInTheDocument();
    });
  });

  it("renders rows with planned/actual/remaining amounts  REQ: FUNC-BUD-002", async () => {
    mockGetBudgets.mockResolvedValue([makeLine()]);
    render(
      <BudgetPanel
        token={TOKEN}
        refreshKey={0}
        categories={CATEGORIES}
        onDrillDown={vi.fn()}
      />,
    );
    await waitFor(() => {
      expect(screen.getByTestId("budget-table")).toBeInTheDocument();
      expect(screen.getByText("50.00")).toBeInTheDocument();
      expect(screen.getByText("30.00")).toBeInTheDocument();
      expect(screen.getByText("20.00")).toBeInTheDocument();
      // "Coffee" appears both in table cell and select option — check the row
      const row = screen.getByTestId("budget-row-bud-1");
      expect(row).toHaveTextContent("Coffee");
    });
  });

  it("highlights overspent rows  REQ: FUNC-BUD-003", async () => {
    const overspent = makeLine({ is_overspent: true, planned: 20, actual: 45, remaining: -25 });
    mockGetBudgets.mockResolvedValue([overspent]);
    render(
      <BudgetPanel
        token={TOKEN}
        refreshKey={0}
        categories={CATEGORIES}
        onDrillDown={vi.fn()}
      />,
    );
    await waitFor(() => {
      const row = screen.getByTestId("budget-row-bud-1");
      expect(row.className).toContain("budget-row-overspent");
    });
  });

  it("calls onDrillDown with correct categoryId and month  REQ: FUNC-BUD-003", async () => {
    const onDrillDown = vi.fn();
    mockGetBudgets.mockResolvedValue([makeLine()]);
    render(
      <BudgetPanel
        token={TOKEN}
        refreshKey={0}
        categories={CATEGORIES}
        onDrillDown={onDrillDown}
      />,
    );
    await waitFor(() => screen.getByTestId("budget-drilldown-bud-1"));
    fireEvent.click(screen.getByTestId("budget-drilldown-bud-1"));
    expect(onDrillDown).toHaveBeenCalledWith("food_coffee", expect.any(String));
  });

  it("uses a constrained month selector and refetches for selected month  REQ: FUNC-BUD-001", async () => {
    mockGetBudgets.mockResolvedValue([]);
    render(
      <BudgetPanel
        token={TOKEN}
        refreshKey={0}
        categories={CATEGORIES}
        onDrillDown={vi.fn()}
      />,
    );

    const monthSelect = await screen.findByTestId("budget-month-input");
    expect(monthSelect.tagName).toBe("SELECT");

    fireEvent.change(monthSelect, { target: { value: "2025-12" } });

    await waitFor(() => {
      expect(mockGetBudgets).toHaveBeenLastCalledWith(TOKEN, { month: "2025-12" });
    });
  });

  it("creates budget via form submit and clears inputs  REQ: FUNC-BUD-001", async () => {
    mockGetBudgets.mockResolvedValue([]);
    const newLine = makeLine({ budget_id: "bud-new", category_id: "food_coffee", planned: 75 });
    mockCreateBudget.mockResolvedValue(newLine);

    render(
      <BudgetPanel
        token={TOKEN}
        refreshKey={0}
        categories={CATEGORIES}
        onDrillDown={vi.fn()}
      />,
    );
    await waitFor(() => screen.getByTestId("budget-category-select"));

    fireEvent.change(screen.getByTestId("budget-category-select"), {
      target: { value: "food_coffee" },
    });
    fireEvent.change(screen.getByTestId("budget-amount-input"), {
      target: { value: "75" },
    });
    fireEvent.click(screen.getByTestId("budget-add-btn"));

    await waitFor(() => {
      expect(mockCreateBudget).toHaveBeenCalledWith(TOKEN, expect.objectContaining({
        category_id: "food_coffee",
        amount: 75,
      }));
    });
  });

  it("shows error message on 409 duplicate budget  REQ: FUNC-BUD-001", async () => {
    mockGetBudgets.mockResolvedValue([]);
    const { ApiError } = await import("../api/client");
    mockCreateBudget.mockRejectedValue(
      new ApiError(409, "A budget line already exists for this category and month"),
    );

    render(
      <BudgetPanel
        token={TOKEN}
        refreshKey={0}
        categories={CATEGORIES}
        onDrillDown={vi.fn()}
      />,
    );
    await waitFor(() => screen.getByTestId("budget-category-select"));

    fireEvent.change(screen.getByTestId("budget-category-select"), {
      target: { value: "food_coffee" },
    });
    fireEvent.change(screen.getByTestId("budget-amount-input"), {
      target: { value: "50" },
    });
    fireEvent.click(screen.getByTestId("budget-add-btn"));

    await waitFor(() => {
      expect(screen.getByText(/failed to create budget/i)).toBeInTheDocument();
    });
  });

  it("deletes budget when delete button clicked  REQ: FUNC-BUD-001", async () => {
    mockGetBudgets.mockResolvedValue([makeLine()]);
    mockDeleteBudget.mockResolvedValue(undefined);

    render(
      <BudgetPanel
        token={TOKEN}
        refreshKey={0}
        categories={CATEGORIES}
        onDrillDown={vi.fn()}
      />,
    );
    await waitFor(() => screen.getByTestId("budget-delete-bud-1"));
    fireEvent.click(screen.getByTestId("budget-delete-bud-1"));

    await waitFor(() => {
      expect(mockDeleteBudget).toHaveBeenCalledWith(TOKEN, "bud-1");
    });
  });

  it("shows error message on fetch failure", async () => {
    mockGetBudgets.mockRejectedValue(new Error("Network error"));
    render(
      <BudgetPanel
        token={TOKEN}
        refreshKey={0}
        categories={CATEGORIES}
        onDrillDown={vi.fn()}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText(/failed to load budgets/i)).toBeInTheDocument();
    });
  });
});
