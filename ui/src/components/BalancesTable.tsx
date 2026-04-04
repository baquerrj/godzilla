/**
 * Balance snapshots table: most recent 100 snapshots across all accounts.
 *
 * REQ: ACC-REP-006
 */

import { useEffect } from "react";
import { GodzillaApi, useApiCall } from "../api/client";
import type { BalanceSnapshot } from "../api/types";

interface Props {
  token: string;
  refreshKey: number;
}

export function BalancesTable({ token, refreshKey }: Props) {
  const [result, execute] = useApiCall<BalanceSnapshot[]>();

  // REQ: ACC-REP-006 — fetch balance snapshots on mount and refresh
  useEffect(() => {
    execute(() => GodzillaApi.getBalances(token, { limit: 100 }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, refreshKey]);

  return (
    <section className="panel" data-testid="balances-panel">
      <div className="panel-header">
        <h2>Balance Snapshots</h2>
      </div>

      {result.status === "loading" && <p className="muted">Loading…</p>}
      {result.status === "error" && (
        <p className="error-text">
          Failed to load balances: {result.message}
        </p>
      )}
      {result.status === "success" && result.data.length === 0 && (
        <p className="muted">
          No balance snapshots. Sync a Plaid item to populate.
        </p>
      )}
      {result.status === "success" && result.data.length > 0 && (
        <table className="data-table" data-testid="balances-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Account</th>
              <th className="amount">Balance</th>
              <th>Currency</th>
            </tr>
          </thead>
          <tbody>
            {result.data.map((snap) => (
              <tr key={snap.snapshot_id}>
                <td>{snap.date}</td>
                <td>
                  <code title={snap.account_id}>
                    {snap.account_name}
                  </code>
                </td>
                <td className="amount">{snap.balance.toFixed(2)}</td>
                <td>{snap.currency}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
