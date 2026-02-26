/**
 * ConflictQueue: lists open field-level conflicts with resolution actions.
 *
 * REQ: FUNC-SYNC-006, FUNC-SYNC-007
 */

import { useEffect } from "react";
import { GodzillaApi, useApiCall } from "../api/client";
import type { Conflict } from "../api/types";

interface Props {
  token: string;
  refreshKey: number;
}

export function ConflictQueue({ token, refreshKey }: Props) {
  const [result, fetchConflicts] = useApiCall<Conflict[]>();
  const [resolveResult, executeResolve] = useApiCall<Conflict>();

  useEffect(() => {
    fetchConflicts(() => GodzillaApi.getConflicts(token, "open"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, refreshKey, resolveResult]);

  const handleResolve = (id: string, choice: "local" | "provider") => {
    executeResolve(async () => {
      const result = await GodzillaApi.resolveConflict(token, id, {
        resolution_choice: choice,
      });
      return result;
    });
  };

  const isBusy = resolveResult.status === "loading";
  const conflicts =
    result.status === "success" ? result.data.filter((c) => c.status === "open") : [];

  if (result.status === "success" && conflicts.length === 0) {
    return null;
  }

  return (
    <section className="panel panel-warning" data-testid="conflict-queue">
      <div className="panel-header">
        <h2>
          Conflicts
          {result.status === "success" && (
            <span className="badge badge-warning" data-testid="conflict-count">
              {" "}
              {conflicts.length}
            </span>
          )}
        </h2>
      </div>

      {result.status === "loading" && <p className="muted">Loading…</p>}
      {result.status === "error" && (
        <p className="error-text">Failed to load conflicts: {result.message}</p>
      )}
      {resolveResult.status === "error" && (
        <p className="error-text">Resolve failed: {resolveResult.message}</p>
      )}

      {result.status === "success" && conflicts.length > 0 && (
        <table className="data-table" data-testid="conflict-table">
          <thead>
            <tr>
              <th>Transaction</th>
              <th>Field</th>
              <th>Your Value</th>
              <th>Provider Value</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {conflicts.map((c) => (
              <tr key={c.conflict_id}>
                <td>
                  <code title={c.entity_id}>{c.entity_id.slice(0, 8)}…</code>
                </td>
                <td>{c.field_name}</td>
                <td>{c.local_value}</td>
                <td>{c.provider_value}</td>
                <td className="conflict-actions">
                  <button
                    className="btn btn-sm"
                    disabled={isBusy}
                    onClick={() => handleResolve(c.conflict_id, "local")}
                    data-testid={`keep-local-${c.conflict_id}`}
                  >
                    Keep Mine
                  </button>
                  <button
                    className="btn btn-sm"
                    disabled={isBusy}
                    onClick={() => handleResolve(c.conflict_id, "provider")}
                    data-testid={`use-provider-${c.conflict_id}`}
                  >
                    Use Provider's
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
