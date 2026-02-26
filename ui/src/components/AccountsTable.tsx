/**
 * Accounts table: lists all linked accounts with current balance.
 *
 * Accounts data is fetched by the parent (App) to avoid duplicate
 * API calls when the same data is needed for filter lookups.
 *
 * REQ: FUNC-ACCT-003
 */

import type { Account } from "../api/types";

interface Props {
  accounts: Account[];
  loading: boolean;
  error: string | null;
}

export function AccountsTable({ accounts, loading, error }: Props) {
  return (
    <section className="panel" data-testid="accounts-panel">
      <div className="panel-header">
        <h2>Accounts</h2>
      </div>

      {loading && <p className="muted">Loading…</p>}
      {error && <p className="error-text">Failed to load accounts: {error}</p>}
      {!loading && !error && accounts.length === 0 && (
        <p className="muted">No accounts. Sync a Plaid item to populate.</p>
      )}
      {!loading && !error && accounts.length > 0 && (
        <table className="data-table" data-testid="accounts-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Subtype</th>
              <th>Mask</th>
              <th className="amount">Balance</th>
              <th>Currency</th>
              <th>Institution</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((acct) => (
              <tr key={acct.account_id}>
                <td>{acct.name}</td>
                <td>{acct.account_type}</td>
                <td>{acct.subtype ?? "—"}</td>
                <td>{acct.mask ? `••••${acct.mask}` : "—"}</td>
                <td className="amount">{acct.balance !== null ? acct.balance.toFixed(2) : "—"}</td>
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
