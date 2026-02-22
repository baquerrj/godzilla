/**
 * Accounts table: lists all linked accounts with current balance.
 *
 * REQ: FUNC-ACCT-003
 */

import { useEffect } from "react";
import { GodzillaApi, useApiCall } from "../api/client";
import type { Account } from "../api/types";

interface Props {
  token: string;
  refreshKey: number;
}

export function AccountsTable({ token, refreshKey }: Props) {
  const [result, execute] = useApiCall<Account[]>();

  // REQ: FUNC-ACCT-003 — fetch accounts on mount and refresh
  useEffect(() => {
    execute(() => GodzillaApi.getAccounts(token));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, refreshKey]);

  return (
    <section className="panel" data-testid="accounts-panel">
      <div className="panel-header">
        <h2>Accounts</h2>
      </div>

      {result.status === "loading" && <p className="muted">Loading…</p>}
      {result.status === "error" && (
        <p className="error-text">
          Failed to load accounts: {result.message}
        </p>
      )}
      {result.status === "success" && result.data.length === 0 && (
        <p className="muted">No accounts. Sync a Plaid item to populate.</p>
      )}
      {result.status === "success" && result.data.length > 0 && (
        <table className="data-table" data-testid="accounts-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Subtype</th>
              <th>Mask</th>
              <th>Balance</th>
              <th>Currency</th>
              <th>Institution</th>
            </tr>
          </thead>
          <tbody>
            {result.data.map((acct) => (
              <tr key={acct.account_id}>
                <td>{acct.name}</td>
                <td>{acct.account_type}</td>
                <td>{acct.subtype ?? "—"}</td>
                <td>{acct.mask ? `••••${acct.mask}` : "—"}</td>
                <td className="amount">
                  {acct.balance !== null ? acct.balance.toFixed(2) : "—"}
                </td>
                <td>{acct.currency}</td>
                <td>{acct.institution_id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
