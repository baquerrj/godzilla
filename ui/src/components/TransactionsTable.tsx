/**
 * Transactions table: paginated list with sort, filter, and detail on click.
 *
 * REQ: ACC-TXN-001, ACC-TXN-002, ACC-TXN-003
 */

import { useEffect, useState } from "react";
import { GodzillaApi, useApiCall } from "../api/client";
import type { GetTransactionsParams, Transaction } from "../api/types";

const PAGE_SIZE = 50;
const NO_FILTERS: Omit<
  GetTransactionsParams,
  "limit" | "offset" | "sort_by" | "sort_order"
> = {};

interface Props {
  token: string;
  refreshKey: number;
  filters?: Omit<GetTransactionsParams, "limit" | "offset" | "sort_by" | "sort_order">;
  onSelectTransaction?: (id: string) => void;
}

export function TransactionsTable({
  token,
  refreshKey,
  filters,
  onSelectTransaction,
}: Props) {
  const [offset, setOffset] = useState(0);
  const [sortBy, setSortBy] = useState<"date" | "amount">("date");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [result, execute] = useApiCall<Transaction[]>();
  const appliedFilters = filters ?? NO_FILTERS;

  // Reset to first page when filters change
  useEffect(() => {
    setOffset(0);
  }, [appliedFilters]);

  // REQ: ACC-TXN-001, ACC-TXN-002 — paginated, sorted, filtered transaction fetch
  useEffect(() => {
    execute(() =>
      GodzillaApi.getTransactions(token, {
        ...appliedFilters,
        limit: PAGE_SIZE,
        offset,
        sort_by: sortBy,
        sort_order: sortOrder,
      }),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, refreshKey, offset, sortBy, sortOrder, appliedFilters]);

  const handleSortClick = (field: "date" | "amount") => {
    if (field === sortBy) {
      setSortOrder((o) => (o === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(field);
      setSortOrder("desc");
      setOffset(0);
    }
  };

  const atFirstPage = offset === 0;
  const atLastPage =
    result.status === "success" && result.data.length < PAGE_SIZE;
  const isLoading = result.status === "loading";

  return (
    <section className="panel" data-testid="transactions-panel">
      <div className="panel-header">
        <h2>Transactions</h2>
        <div className="pagination">
          <button
            className="btn btn-sm"
            disabled={atFirstPage || isLoading}
            onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
            data-testid="prev-btn"
          >
            ← Prev
          </button>
          <span className="muted">
            {offset + 1}–{offset + PAGE_SIZE}
          </span>
          <button
            className="btn btn-sm"
            disabled={atLastPage || isLoading}
            onClick={() => setOffset((o) => o + PAGE_SIZE)}
            data-testid="next-btn"
          >
            Next →
          </button>
        </div>
      </div>

      {isLoading && <p className="muted">Loading…</p>}
      {result.status === "error" && (
        <p className="error-text">
          Failed to load transactions: {result.message}
        </p>
      )}
      {result.status === "success" && result.data.length === 0 && (
        <p className="muted">
          No transactions. Sync a Plaid item to populate.
        </p>
      )}
      {result.status === "success" && result.data.length > 0 && (
        <table className="data-table" data-testid="transactions-table">
          <thead>
            <tr>
              <th
                className="sortable"
                onClick={() => handleSortClick("date")}
                data-testid="sort-date"
              >
                Date{" "}
                {sortBy === "date" ? (sortOrder === "asc" ? "↑" : "↓") : ""}
              </th>
              <th>Account</th>
              <th>Merchant</th>
              <th>Display Name</th>
              <th>Category</th>
              <th>Status</th>
              <th
                className="sortable amount"
                onClick={() => handleSortClick("amount")}
                data-testid="sort-amount"
              >
                Amount{" "}
                {sortBy === "amount" ? (sortOrder === "asc" ? "↑" : "↓") : ""}
              </th>
              <th>Currency</th>
            </tr>
          </thead>
          <tbody>
            {result.data.map((txn) => (
              <tr
                key={txn.transaction_id}
                className={txn.is_excluded ? "excluded" : ""}
                onClick={
                  onSelectTransaction
                    ? () => onSelectTransaction(txn.transaction_id)
                    : undefined
                }
                style={onSelectTransaction ? { cursor: "pointer" } : undefined}
                data-testid={`txn-row-${txn.transaction_id}`}
              >
                <td>{txn.date}</td>
                <td>{txn.account_name}</td>
                <td>{txn.merchant_name ?? "—"}</td>
                <td>{txn.display_name}</td>
                <td>{txn.category_id ?? "—"}</td>
                <td>
                  <span className={`badge badge-${txn.status}`}>
                    {txn.status}
                  </span>
                </td>
                <td
                  className={`amount ${txn.amount < 0 ? "amount-negative" : ""}`}
                >
                  {txn.amount.toFixed(2)}
                </td>
                <td>{txn.currency}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
