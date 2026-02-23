/**
 * Tests for ReportsPanel component.
 *
 * REQ: FUNC-REP-001, FUNC-REP-002, FUNC-REP-003, FUNC-REP-004, FUNC-REP-005,
 * REQ: FUNC-REP-007, FUNC-REP-008
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ReportsPanel } from "../components/ReportsPanel";
import type { Category } from "../api/types";

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
      getMonthlyOverview: vi.fn(),
      getCashFlow: vi.fn(),
      getCategoryTrends: vi.fn(),
      getNetWorth: vi.fn(),
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

const mockGetMonthlyOverview = vi.mocked(GodzillaApi.getMonthlyOverview);
const mockGetCashFlow = vi.mocked(GodzillaApi.getCashFlow);
const mockGetCategoryTrends = vi.mocked(GodzillaApi.getCategoryTrends);
const mockGetNetWorth = vi.mocked(GodzillaApi.getNetWorth);

const TOKEN = "tok";
const CATEGORIES: Category[] = [
  { category_id: "food", name: "Food", parent_id: null, active: true },
  { category_id: "food_coffee", name: "Coffee", parent_id: "food", active: true },
  { category_id: "food_dining", name: "Dining", parent_id: "food", active: true },
];

describe("ReportsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetMonthlyOverview.mockResolvedValue({
      month: "2026-01",
      start_date: "2026-01-01",
      end_date: "2026-01-31",
      income: 200,
      expenses: 160,
      net_savings: 40,
      savings_rate: 0.2,
      top_categories: [
        { category_id: "food_dining", category_name: "Dining", amount: 90 },
        { category_id: "food_coffee", category_name: "Coffee", amount: 70 },
      ],
      inclusion_note: "Rule note",
      includes_excluded_items: false,
    });
    mockGetCashFlow.mockResolvedValue({
      start_date: "2026-01-01",
      end_date: "2026-01-31",
      points: [
        { month: "2026-01", income: 200, expenses: 160, net_savings: 40, savings_rate: 0.2 },
      ],
      inclusion_note: "Rule note",
      includes_excluded_items: false,
    });
    mockGetCategoryTrends.mockResolvedValue({
      start_month: "2025-12",
      end_month: "2026-01",
      months: 2,
      series: [
        {
          category_id: "food_coffee",
          category_name: "Coffee",
          points: [
            { month: "2025-12", amount: 50 },
            { month: "2026-01", amount: 70 },
          ],
        },
      ],
      inclusion_note: "Rule note",
      includes_excluded_items: false,
    });
    mockGetNetWorth.mockResolvedValue({
      start_date: "2026-01-01",
      end_date: "2026-01-31",
      points: [{ date: "2026-01-03", assets: 320, liabilities: 120, net_worth: 200 }],
    });
  });

  it("renders report sections and data  REQ: FUNC-REP-001, FUNC-REP-003, FUNC-REP-004, FUNC-REP-005", async () => {
    render(
      <ReportsPanel
        token={TOKEN}
        refreshKey={0}
        categories={CATEGORIES}
        onDrillDown={vi.fn()}
      />,
    );
    await waitFor(() => {
      expect(screen.getByTestId("reports-panel")).toBeInTheDocument();
      expect(screen.getByTestId("report-top-categories")).toBeInTheDocument();
      expect(screen.getByTestId("report-cash-flow")).toBeInTheDocument();
      expect(screen.getByTestId("report-category-trends")).toBeInTheDocument();
      expect(screen.getByTestId("report-net-worth")).toBeInTheDocument();
      expect(screen.getByText(/rule note/i)).toBeInTheDocument();
    });
  });

  it("requests all report endpoints on load  REQ: FUNC-REP-008", async () => {
    render(
      <ReportsPanel
        token={TOKEN}
        refreshKey={0}
        categories={CATEGORIES}
        onDrillDown={vi.fn()}
      />,
    );
    await waitFor(() => {
      expect(mockGetMonthlyOverview).toHaveBeenCalled();
      expect(mockGetCashFlow).toHaveBeenCalled();
      expect(mockGetCategoryTrends).toHaveBeenCalled();
      expect(mockGetNetWorth).toHaveBeenCalled();
    });
  });

  it("updates range-driven report calls when month changes  REQ: FUNC-REP-008", async () => {
    render(
      <ReportsPanel
        token={TOKEN}
        refreshKey={0}
        categories={CATEGORIES}
        onDrillDown={vi.fn()}
      />,
    );
    await waitFor(() => {
      expect(mockGetMonthlyOverview).toHaveBeenCalled();
    });

    fireEvent.change(screen.getByTestId("reports-month-input"), {
      target: { value: "2025-12" },
    });

    await waitFor(() => {
      expect(mockGetMonthlyOverview).toHaveBeenLastCalledWith(TOKEN, { month: "2025-12" });
      expect(mockGetCashFlow).toHaveBeenLastCalledWith(TOKEN, {
        start: "2025-12-01",
        end: "2025-12-31",
      });
      expect(mockGetNetWorth).toHaveBeenLastCalledWith(TOKEN, {
        start: "2025-12-01",
        end: "2025-12-31",
      });
    });
  });

  it("drills down from top category and overview cards  REQ: FUNC-REP-002", async () => {
    const onDrillDown = vi.fn();
    render(
      <ReportsPanel
        token={TOKEN}
        refreshKey={0}
        categories={CATEGORIES}
        onDrillDown={onDrillDown}
      />,
    );
    await waitFor(() => screen.getByTestId("report-top-category-food_dining"));
    fireEvent.change(screen.getByTestId("reports-month-input"), {
      target: { value: "2026-01" },
    });
    await waitFor(() => {
      expect(mockGetMonthlyOverview).toHaveBeenLastCalledWith(TOKEN, { month: "2026-01" });
    });

    fireEvent.click(screen.getByTestId("report-top-category-food_dining"));
    fireEvent.click(screen.getByTestId("report-income-card"));
    fireEvent.click(screen.getByTestId("report-expenses-card"));

    expect(onDrillDown).toHaveBeenCalledWith({
      startDate: "2026-01-01",
      endDate: "2026-01-31",
      categoryId: "food_dining",
      flow: "expense",
    });
    expect(onDrillDown).toHaveBeenCalledWith({
      startDate: "2026-01-01",
      endDate: "2026-01-31",
      flow: "income",
    });
    expect(onDrillDown).toHaveBeenCalledWith({
      startDate: "2026-01-01",
      endDate: "2026-01-31",
      flow: "expense",
    });
  });

  it("drills down from cash-flow and category trend points  REQ: FUNC-REP-002", async () => {
    const onDrillDown = vi.fn();
    render(
      <ReportsPanel
        token={TOKEN}
        refreshKey={0}
        categories={CATEGORIES}
        onDrillDown={onDrillDown}
      />,
    );
    await waitFor(() => screen.getByTestId("report-cashflow-income-2026-01"));
    fireEvent.click(screen.getByTestId("report-cashflow-income-2026-01"));
    fireEvent.click(screen.getByTestId("report-cashflow-expense-2026-01"));
    fireEvent.click(screen.getByTestId("report-trend-food_coffee-2026-01"));

    expect(onDrillDown).toHaveBeenCalledWith({
      startDate: "2026-01-01",
      endDate: "2026-01-31",
      flow: "income",
    });
    expect(onDrillDown).toHaveBeenCalledWith({
      startDate: "2026-01-01",
      endDate: "2026-01-31",
      flow: "expense",
    });
    expect(onDrillDown).toHaveBeenCalledWith({
      startDate: "2026-01-01",
      endDate: "2026-01-31",
      categoryId: "food_coffee",
      flow: "expense",
    });
  });
});
