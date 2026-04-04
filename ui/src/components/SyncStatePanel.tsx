/**
 * Sync state panel: per-item sync status, "Connect Sandbox Account",
 * and "Run Sync" actions.
 *
 * REQ: ACC-ACCT-001, ACC-ACCT-002, ACC-ACCT-004, ACC-ACCT-005,
 * REQ: ACC-ACCT-008, ACC-SYNC-001
 */

import { useEffect } from "react";
import { GodzillaApi, useApiCall } from "../api/client";
import type {
  PlaidLinkResult,
  PlaidSyncResult,
  SyncState,
  UnlinkItemResult,
} from "../api/types";

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
  const [unlinkResult, executeUnlink] = useApiCall<UnlinkItemResult>();

  // REQ: ACC-ACCT-004 — load sync state on mount and on every refresh
  useEffect(() => {
    fetchState(() => GodzillaApi.getSyncState(token));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, refreshKey]);

  // REQ: ACC-ACCT-001, ACC-ACCT-002 — connect a sandbox Plaid item
  const handleConnect = () => {
    executeLink(async () => {
      const result = await GodzillaApi.plaidLink(token, {});
      onRefresh();
      return result;
    });
  };

  // REQ: ACC-ACCT-005, ACC-SYNC-001 — trigger incremental sync
  const handleSync = (itemId: string) => {
    executeSync(async () => {
      const result = await GodzillaApi.plaidSync(token, { item_id: itemId });
      onRefresh();
      return result;
    });
  };

  // REQ: ACC-ACCT-008 — unlink institution with keep/purge modes.
  const handleUnlink = (itemId: string, mode: "keep" | "purge") => {
    const warning = mode === "purge"
      ? "Unlink and purge will delete linked local records. Continue?"
      : "Unlink and keep preserves local ledger data but disables sync. Continue?";
    if (!window.confirm(warning)) {
      return;
    }
    executeUnlink(async () => {
      const result = await GodzillaApi.unlinkItem(token, itemId, mode);
      onRefresh();
      return result;
    });
  };

  const isBusy =
    linkResult.status === "loading"
    || syncResult.status === "loading"
    || unlinkResult.status === "loading";

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
      {unlinkResult.status === "success" && (
        <div className="alert alert-success" data-testid="unlink-success">
          Unlinked <code>{unlinkResult.data.item_id}</code> with mode{" "}
          <strong>{unlinkResult.data.mode}</strong>.
        </div>
      )}
      {unlinkResult.status === "error" && (
        <div className="alert alert-error" data-testid="unlink-error">
          Unlink failed: {unlinkResult.message}
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
              <th>Actions</th>
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
                    disabled={isBusy || item.status === "unlinked"}
                    data-testid={`sync-btn-${item.item_id}`}
                  >
                    {syncResult.status === "loading" ? "Syncing…" : "Run Sync"}
                  </button>
                  <button
                    className="btn btn-sm"
                    onClick={() => handleUnlink(item.item_id, "keep")}
                    disabled={isBusy}
                    data-testid={`unlink-keep-btn-${item.item_id}`}
                  >
                    Unlink (Keep)
                  </button>
                  <button
                    className="btn btn-sm"
                    onClick={() => handleUnlink(item.item_id, "purge")}
                    disabled={isBusy}
                    data-testid={`unlink-purge-btn-${item.item_id}`}
                  >
                    Unlink + Purge
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
