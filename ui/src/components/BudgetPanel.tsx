/**
 * BudgetPanel: monthly budget view with planned/actual/remaining and drill-down.
 *
 * REQ: FUNC-BUD-001, FUNC-BUD-002, FUNC-BUD-003, FUNC-BUD-004
 */

import { useEffect, useState } from "react";
import { GodzillaApi, useApiCall } from "../api/client";
import { leafActiveCategories } from "./categoryUtils";
import type { BudgetLine, Category } from "../api/types";

interface Props {
  token: string;
  refreshKey: number;
  categories: Category[];
  onDrillDown: (categoryId: string, month: string) => void;
}

function defaultMonth(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  return `${y}-${m}`;
}

export function BudgetPanel({ token, refreshKey, categories, onDrillDown }: Props) {
  const [selectedMonth, setSelectedMonth] = useState<string>(defaultMonth);
  const [newAmount, setNewAmount] = useState<string>("");
  const [newCategoryId, setNewCategoryId] = useState<string>("");

  const [fetchResult, executeFetch] = useApiCall<BudgetLine[]>();
  const [createResult, executeCreate] = useApiCall<BudgetLine>();
  const [deleteResult, executeDelete] = useApiCall<void>();

  useEffect(() => {
    executeFetch(() => GodzillaApi.getBudgets(token, { month: selectedMonth }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, selectedMonth, refreshKey, createResult, deleteResult]);

  const leafCategories = leafActiveCategories(categories);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCategoryId || !newAmount) return;
    await executeCreate(() =>
      GodzillaApi.createBudget(token, {
        month: selectedMonth,
        category_id: newCategoryId,
        amount: parseFloat(newAmount),
      }),
    );
    setNewAmount("");
    setNewCategoryId("");
  };

  const handleDelete = (budgetId: string) => {
    executeDelete(() => GodzillaApi.deleteBudget(token, budgetId));
  };

  const categoryName = (categoryId: string): string => {
    const cat = categories.find((c) => c.category_id === categoryId);
    return cat ? cat.name : categoryId;
  };

  const lines = fetchResult.status === "success" ? fetchResult.data : [];

  return (
    <section className="panel" data-testid="budget-panel">
      <div className="panel-header">
        <h2>Budgets</h2>
        <input
          type="month"
          value={selectedMonth}
          onChange={(e) => setSelectedMonth(e.target.value)}
          data-testid="budget-month-input"
        />
      </div>

      {fetchResult.status === "loading" && <p className="muted">Loading…</p>}
      {fetchResult.status === "error" && (
        <p className="error-text">Failed to load budgets: {fetchResult.message}</p>
      )}
      {createResult.status === "error" && (
        <p className="error-text">Failed to create budget: {createResult.message}</p>
      )}
      {deleteResult.status === "error" && (
        <p className="error-text">Failed to delete budget: {deleteResult.message}</p>
      )}

      {fetchResult.status === "success" && lines.length === 0 && (
        <p className="muted">No budgets set for {selectedMonth}.</p>
      )}

      {lines.length > 0 && (
        <table className="data-table" data-testid="budget-table">
          <thead>
            <tr>
              <th>Category</th>
              <th className="amount">Planned</th>
              <th className="amount">Actual</th>
              <th className="amount">Remaining</th>
              <th></th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line) => (
              <tr
                key={line.budget_id}
                className={line.is_overspent ? "budget-row-overspent" : undefined}
                data-testid={`budget-row-${line.budget_id}`}
              >
                <td>{categoryName(line.category_id)}</td>
                <td className="amount">{line.planned.toFixed(2)}</td>
                <td className="amount">{line.actual.toFixed(2)}</td>
                <td className={`amount budget-remaining`}>{line.remaining.toFixed(2)}</td>
                <td>
                  <button
                    className="btn btn-sm"
                    onClick={() => onDrillDown(line.category_id, selectedMonth)}
                    data-testid={`budget-drilldown-${line.budget_id}`}
                  >
                    View
                  </button>
                </td>
                <td>
                  <button
                    className="btn btn-sm btn-danger"
                    onClick={() => handleDelete(line.budget_id)}
                    data-testid={`budget-delete-${line.budget_id}`}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <form className="budget-add-form" onSubmit={handleAdd}>
        <select
          value={newCategoryId}
          onChange={(e) => setNewCategoryId(e.target.value)}
          data-testid="budget-category-select"
        >
          <option value="">Select category…</option>
          {leafCategories.map((cat) => (
            <option key={cat.category_id} value={cat.category_id}>
              {cat.name}
            </option>
          ))}
        </select>
        <input
          type="number"
          step="0.01"
          min="0.01"
          placeholder="Amount"
          value={newAmount}
          onChange={(e) => setNewAmount(e.target.value)}
          data-testid="budget-amount-input"
        />
        <button
          type="submit"
          className="btn btn-primary btn-sm"
          disabled={!newCategoryId || !newAmount}
          data-testid="budget-add-btn"
        >
          Add Budget
        </button>
      </form>
    </section>
  );
}
