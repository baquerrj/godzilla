/**
 * ReportsPanel: monthly overview, cash flow, category trends, and net worth.
 *
 * REQ: FUNC-REP-001, FUNC-REP-002, FUNC-REP-003, FUNC-REP-004, FUNC-REP-005,
 * REQ: FUNC-REP-007, FUNC-REP-008
 */

import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { GodzillaApi, useApiCall } from "../api/client";
import { leafActiveCategories } from "./categoryUtils";
import type {
  CashFlowReport,
  Category,
  CategoryTrendsReport,
  MonthlyOverview,
  NetWorthReport,
} from "../api/types";

export interface ReportDrillDown {
  startDate: string;
  endDate: string;
  categoryId?: string;
  flow?: "income" | "expense";
}

interface Props {
  token: string;
  refreshKey: number;
  categories: Category[];
  onDrillDown: (input: ReportDrillDown) => void;
}

function defaultMonth(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  return `${y}-${m}`;
}

function monthBounds(month: string): { start: string; end: string } {
  const [year, monthNum] = month.split("-").map(Number);
  const endDay = new Date(year, monthNum, 0).getDate();
  return {
    start: `${month}-01`,
    end: `${month}-${String(endDay).padStart(2, "0")}`,
  };
}

function monthSpan(startDate: string, endDate: string): number {
  const [sy, sm] = startDate.split("-").slice(0, 2).map(Number);
  const [ey, em] = endDate.split("-").slice(0, 2).map(Number);
  if (!Number.isFinite(sy) || !Number.isFinite(sm) || !Number.isFinite(ey) || !Number.isFinite(em)) {
    return 12;
  }
  const span = (ey - sy) * 12 + (em - sm) + 1;
  return Math.max(1, Math.min(24, span));
}

export function ReportsPanel({ token, refreshKey, categories, onDrillDown }: Props) {
  const [selectedMonth, setSelectedMonth] = useState<string>(defaultMonth);
  const [rangeStart, setRangeStart] = useState<string>(monthBounds(defaultMonth()).start);
  const [rangeEnd, setRangeEnd] = useState<string>(monthBounds(defaultMonth()).end);
  const [trendCategoryIds, setTrendCategoryIds] = useState<string[]>([]);

  const [overviewResult, executeOverview] = useApiCall<MonthlyOverview>();
  const [cashFlowResult, executeCashFlow] = useApiCall<CashFlowReport>();
  const [trendResult, executeTrends] = useApiCall<CategoryTrendsReport>();
  const [netWorthResult, executeNetWorth] = useApiCall<NetWorthReport>();

  const leafCategories = useMemo(() => leafActiveCategories(categories), [categories]);
  const trendMonths = useMemo(() => monthSpan(rangeStart, rangeEnd), [rangeStart, rangeEnd]);

  useEffect(() => {
    const next = monthBounds(selectedMonth);
    setRangeStart(next.start);
    setRangeEnd(next.end);
  }, [selectedMonth]);

  useEffect(() => {
    if (leafCategories.length === 0) {
      setTrendCategoryIds([]);
      return;
    }
    if (trendCategoryIds.length === 0) {
      setTrendCategoryIds(leafCategories.slice(0, 2).map((cat) => cat.category_id));
    }
  }, [leafCategories, trendCategoryIds.length]);

  useEffect(() => {
    executeOverview(() => GodzillaApi.getMonthlyOverview(token, { month: selectedMonth }));
    executeCashFlow(() => GodzillaApi.getCashFlow(token, { start: rangeStart, end: rangeEnd }));
    executeNetWorth(() => GodzillaApi.getNetWorth(token, { start: rangeStart, end: rangeEnd }));
    if (trendCategoryIds.length > 0) {
      executeTrends(() =>
        GodzillaApi.getCategoryTrends(token, {
          categories: trendCategoryIds,
          months: trendMonths,
          end_month: rangeEnd.slice(0, 7),
        }),
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, refreshKey, selectedMonth, rangeStart, rangeEnd, trendCategoryIds, trendMonths]);

  const handleTrendCategoryChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const selected = Array.from(event.target.selectedOptions).map((option) => option.value);
    setTrendCategoryIds(selected);
  };

  const handleIncomeDrillDown = () => {
    const bounds = monthBounds(selectedMonth);
    onDrillDown({ startDate: bounds.start, endDate: bounds.end, flow: "income" });
  };

  const handleExpenseDrillDown = () => {
    const bounds = monthBounds(selectedMonth);
    onDrillDown({ startDate: bounds.start, endDate: bounds.end, flow: "expense" });
  };

  return (
    <section className="panel" data-testid="reports-panel">
      <div className="panel-header">
        <h2>Reports</h2>
        <div className="reports-controls">
          <label>
            Month
            <input
              type="month"
              value={selectedMonth}
              onChange={(event) => setSelectedMonth(event.target.value)}
              data-testid="reports-month-input"
            />
          </label>
          <label>
            Start
            <input
              type="date"
              value={rangeStart}
              onChange={(event) => setRangeStart(event.target.value)}
              data-testid="reports-start-input"
            />
          </label>
          <label>
            End
            <input
              type="date"
              value={rangeEnd}
              onChange={(event) => setRangeEnd(event.target.value)}
              data-testid="reports-end-input"
            />
          </label>
        </div>
      </div>
      <p className="reports-help" data-testid="reports-help-summary">
        Use Month for the default reporting window. Start and End update cash flow, category trends,
        and net worth. Click report values to open matching transactions.
      </p>
      <p className="reports-help">
        Transaction-based metrics include posted transactions only, exclude transfers and excluded
        records, and remain split-aware.
      </p>

      <div className="reports-section">
        <h3>Monthly Overview</h3>
        <p className="reports-help">Use Income, Expenses, or View to drill into filtered transactions.</p>
        {overviewResult.status === "loading" && <p className="muted">Loading…</p>}
        {overviewResult.status === "error" && (
          <p className="error-text">Failed to load monthly overview: {overviewResult.message}</p>
        )}
        {overviewResult.status === "success" && (
          <>
            <p className="muted">{overviewResult.data.inclusion_note}</p>
            <div className="reports-cards">
              <button
                className="btn btn-sm"
                data-testid="report-income-card"
                onClick={handleIncomeDrillDown}
              >
                Income {overviewResult.data.income.toFixed(2)}
              </button>
              <button
                className="btn btn-sm"
                data-testid="report-expenses-card"
                onClick={handleExpenseDrillDown}
              >
                Expenses {overviewResult.data.expenses.toFixed(2)}
              </button>
              <div className="report-card-static">
                Net Savings {overviewResult.data.net_savings.toFixed(2)}
              </div>
              <div className="report-card-static">
                Savings Rate {(overviewResult.data.savings_rate * 100).toFixed(1)}%
              </div>
            </div>
            <table className="data-table" data-testid="report-top-categories">
              <thead>
                <tr>
                  <th>Category</th>
                  <th className="amount">Spend</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {overviewResult.data.top_categories.map((row) => (
                  <tr key={row.category_id}>
                    <td>{row.category_name}</td>
                    <td className="amount">{row.amount.toFixed(2)}</td>
                    <td>
                      <button
                        className="btn btn-sm"
                        data-testid={`report-top-category-${row.category_id}`}
                        onClick={() => {
                          const bounds = monthBounds(selectedMonth);
                          onDrillDown({
                            startDate: bounds.start,
                            endDate: bounds.end,
                            categoryId: row.category_id,
                            flow: "expense",
                          });
                        }}
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>

      <div className="reports-section">
        <h3>Cash Flow</h3>
        <p className="reports-help">Income and Expenses buttons apply month-specific transaction filters.</p>
        {cashFlowResult.status === "loading" && <p className="muted">Loading…</p>}
        {cashFlowResult.status === "error" && (
          <p className="error-text">Failed to load cash flow: {cashFlowResult.message}</p>
        )}
        {cashFlowResult.status === "success" && (
          <table className="data-table" data-testid="report-cash-flow">
            <thead>
              <tr>
                <th>Month</th>
                <th className="amount">Income</th>
                <th className="amount">Expenses</th>
                <th className="amount">Net</th>
                <th className="amount">Rate</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {cashFlowResult.data.points.map((point) => {
                const bounds = monthBounds(point.month);
                return (
                  <tr key={point.month}>
                    <td>{point.month}</td>
                    <td className="amount">{point.income.toFixed(2)}</td>
                    <td className="amount">{point.expenses.toFixed(2)}</td>
                    <td className="amount">{point.net_savings.toFixed(2)}</td>
                    <td className="amount">{(point.savings_rate * 100).toFixed(1)}%</td>
                    <td className="report-actions">
                      <button
                        className="btn btn-sm"
                        data-testid={`report-cashflow-income-${point.month}`}
                        onClick={() =>
                          onDrillDown({
                            startDate: bounds.start,
                            endDate: bounds.end,
                            flow: "income",
                          })}
                      >
                        Income
                      </button>
                      <button
                        className="btn btn-sm"
                        data-testid={`report-cashflow-expense-${point.month}`}
                        onClick={() =>
                          onDrillDown({
                            startDate: bounds.start,
                            endDate: bounds.end,
                            flow: "expense",
                          })}
                      >
                        Expenses
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="reports-section">
        <h3>Category Trends</h3>
        <p className="reports-help">Select one or more categories. Use Ctrl/Cmd + click to multi-select.</p>
        <label className="reports-category-picker">
          Categories
          <select
            multiple
            value={trendCategoryIds}
            onChange={handleTrendCategoryChange}
            data-testid="report-trend-categories"
          >
            {leafCategories.map((cat) => (
              <option key={cat.category_id} value={cat.category_id}>
                {cat.name}
              </option>
            ))}
          </select>
        </label>
        {trendResult.status === "loading" && <p className="muted">Loading…</p>}
        {trendResult.status === "error" && (
          <p className="error-text">Failed to load category trends: {trendResult.message}</p>
        )}
        {trendResult.status === "success" && (
          <div className="trend-series-list" data-testid="report-category-trends">
            {trendResult.data.series.map((series) => (
              <div key={series.category_id} className="trend-series-row">
                <strong>{series.category_name}</strong>
                <div className="trend-points">
                  {series.points.map((point) => {
                    const bounds = monthBounds(point.month);
                    return (
                      <button
                        key={`${series.category_id}-${point.month}`}
                        className="btn btn-sm"
                        data-testid={`report-trend-${series.category_id}-${point.month}`}
                        onClick={() =>
                          onDrillDown({
                            startDate: bounds.start,
                            endDate: bounds.end,
                            categoryId: series.category_id,
                            flow: "expense",
                          })}
                      >
                        {point.month}: {point.amount.toFixed(2)}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="reports-section">
        <h3>Net Worth</h3>
        <p className="reports-help">Net worth equals assets minus liabilities from balance snapshots.</p>
        {netWorthResult.status === "loading" && <p className="muted">Loading…</p>}
        {netWorthResult.status === "error" && (
          <p className="error-text">Failed to load net worth: {netWorthResult.message}</p>
        )}
        {netWorthResult.status === "success" && (
          <table className="data-table" data-testid="report-net-worth">
            <thead>
              <tr>
                <th>Date</th>
                <th className="amount">Assets</th>
                <th className="amount">Liabilities</th>
                <th className="amount">Net Worth</th>
              </tr>
            </thead>
            <tbody>
              {netWorthResult.data.points.map((point) => (
                <tr key={point.date}>
                  <td>{point.date}</td>
                  <td className="amount">{point.assets.toFixed(2)}</td>
                  <td className="amount">{point.liabilities.toFixed(2)}</td>
                  <td className="amount">{point.net_worth.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
