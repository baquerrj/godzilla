/**
 * Sync state panel: per-item sync status, "Connect Sandbox Account",
 * and "Run Sync" actions.
 *
 * REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-004, FUNC-ACCT-005,
 * REQ: FUNC-SYNC-001
 */

import { useEffect } from "react";
import { GodzillaApi, useApiCall } from "../api/client";
import type { PlaidLinkResult, PlaidSyncResult, SyncState } from "../api/types";

interface Props {
  token: string;
  /** Increment to force a data refresh from the parent. */
  refreshKey: number;
  /** Called after a successful link or sync so the parent can refresh all panels. */
  onRefresh: () => void;
}

export function SyncStatePanel({ token, refreshKey, onRefresh }: Props) {
  const [stateResult, fetchState] = useApiCall<SyncState[]>();
  const [linkResult, executeLink] = useApiCall<PlaidLinkResult>();
  const [syncResult, executeSync] = useApiCall<PlaidSyncResult>();

  // REQ: FUNC-ACCT-004 — load sync state on mount and on every refresh
  useEffect(() => {
    fetchState(() => GodzillaApi.getSyncState(token));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, refreshKey]);

  // REQ: FUNC-ACCT-001, FUNC-ACCT-002 — connect a sandbox Plaid item
  const handleConnect = () => {
    executeLink(async () => {
      const result = await GodzillaApi.plaidLink(token, {});
      onRefresh();
      return result;
    });
  };

  // REQ: FUNC-ACCT-005, FUNC-SYNC-001 — trigger incremental sync
  const handleSync = (itemId: string) => {
    executeSync(async () => {
      const result = await GodzillaApi.plaidSync(token, { item_id: itemId });
      onRefresh();
      return result;
    });
  };

  const isBusy =
    linkResult.status === "loading" || syncResult.status === "loading";

  return (
    <section className="panel" data-testid="sync-state-panel">
      <div className="panel-header">
        <h2>Sync Status</h2>
        <button
          className="btn btn-primary"
          onClick={handleConnect}
          disabled={isBusy}
          data-testid="connect-btn"
        >
          {linkResult.status === "loading" ? "Connecting…" : "Connect Sandbox Account"}
        </button>
      </div>

      {linkResult.status === "success" && (
        <div className="alert alert-success" data-testid="link-success">
          Connected: item <code>{linkResult.data.item_id}</code>
        </div>
      )}
      {linkResult.status === "error" && (
        <div className="alert alert-error" data-testid="link-error">
          Link failed: {linkResult.message}
        </div>
      )}
      {syncResult.status === "success" && (
        <div className="alert alert-success" data-testid="sync-success">
          Sync complete — added {syncResult.data.added}, modified{" "}
          {syncResult.data.modified}, removed {syncResult.data.removed}
        </div>
      )}
      {syncResult.status === "error" && (
        <div className="alert alert-error" data-testid="sync-error">
          Sync failed: {syncResult.message}
        </div>
      )}

      {stateResult.status === "loading" && (
        <p className="muted">Loading…</p>
      )}
      {stateResult.status === "error" && (
        <p className="error-text">
          Failed to load sync state: {stateResult.message}
        </p>
      )}
      {stateResult.status === "success" && stateResult.data.length === 0 && (
        <p className="muted">
          No linked accounts. Use "Connect Sandbox Account" to add one.
        </p>
      )}
      {stateResult.status === "success" && stateResult.data.length > 0 && (
        <table className="data-table" data-testid="sync-table">
          <thead>
            <tr>
              <th>Item ID</th>
              <th>Institution</th>
              <th>Status</th>
              <th>Last Sync</th>
              <th>Result</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {stateResult.data.map((item) => (
              <tr key={item.item_id}>
                <td>
                  <code title={item.item_id}>
                    {item.item_id.slice(0, 12)}…
                  </code>
                </td>
                <td>{item.institution_id}</td>
                <td>
                  <span className={`badge badge-${item.status}`}>
                    {item.status}
                  </span>
                </td>
                <td>{item.last_sync_at_tz ?? item.last_sync_at_utc ?? "—"}</td>
                <td>{item.last_sync_status ?? "—"}</td>
                <td>
                  <button
                    className="btn btn-sm"
                    onClick={() => handleSync(item.item_id)}
                    disabled={isBusy}
                    data-testid={`sync-btn-${item.item_id}`}
                  >
                    {syncResult.status === "loading" ? "Syncing…" : "Run Sync"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
