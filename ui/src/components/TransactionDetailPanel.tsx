/**
 * TransactionDetailPanel: slide-in detail view for a selected transaction.
 *
 * Shows all fields, tags, splits, and (collapsed) raw provider payloads.
 * Allows patching category, notes, is_transfer, and is_excluded.
 *
 * REQ: FUNC-TXN-003, FUNC-TXN-004, FUNC-TXN-005, FUNC-TXN-006, FUNC-TXN-007
 */

import { useEffect, useState } from "react";
import { GodzillaApi, useApiCall } from "../api/client";
import type { Category, TransactionDetail } from "../api/types";

interface Props {
  token: string;
  transactionId: string | null;
  categories: Category[];
  onClose: () => void;
  onUpdated: () => void;
}

/** Returns the set of category IDs that are parents (non-leaf). */
function parentIds(categories: Category[]): Set<string> {
  const ids = new Set<string>();
  for (const cat of categories) {
    if (cat.parent_id !== null) ids.add(cat.parent_id);
  }
  return ids;
}

export function TransactionDetailPanel({
  token,
  transactionId,
  categories,
  onClose,
  onUpdated,
}: Props) {
  const [detail, fetchDetail] = useApiCall<TransactionDetail>();
  const [patchResult, executePatch] = useApiCall<TransactionDetail>();
  const [notes, setNotes] = useState("");
  const [categoryId, setCategoryId] = useState("");

  const parents = parentIds(categories);
  const leafCategories = categories.filter(
    (c) => c.active && !parents.has(c.category_id),
  );

  useEffect(() => {
    if (transactionId) {
      fetchDetail(() => GodzillaApi.getTransaction(token, transactionId));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, transactionId]);

  // Populate form when data loads
  useEffect(() => {
    if (detail.status === "success") {
      setNotes(detail.data.notes ?? "");
      setCategoryId(detail.data.category_id ?? "");
    }
  }, [detail]);

  if (!transactionId) return null;

  const handleSave = () => {
    executePatch(async () => {
      const result = await GodzillaApi.patchTransaction(token, transactionId, {
        notes: notes || null,
        category_id: categoryId || null,
      });
      onUpdated();
      return result;
    });
  };

  const handleToggle = (field: "is_transfer" | "is_excluded") => {
    if (detail.status !== "success") return;
    executePatch(async () => {
      const result = await GodzillaApi.patchTransaction(token, transactionId, {
        [field]: !detail.data[field],
      });
      onUpdated();
      // Re-fetch to sync state
      await fetchDetail(() => GodzillaApi.getTransaction(token, transactionId));
      return result;
    });
  };

  const txn = detail.status === "success" ? detail.data : null;

  return (
    <div className="detail-overlay" data-testid="detail-panel">
      <div className="detail-panel">
        <div className="panel-header">
          <h2>Transaction Detail</h2>
          <button className="btn btn-sm" onClick={onClose} data-testid="detail-close">
            ✕ Close
          </button>
        </div>

        {detail.status === "loading" && <p className="muted">Loading…</p>}
        {detail.status === "error" && (
          <p className="error-text">Failed to load: {detail.message}</p>
        )}

        {txn && (
          <div className="detail-body">
            <dl className="detail-fields">
              <dt>Date</dt><dd>{txn.date}</dd>
              <dt>Display Name</dt><dd>{txn.display_name}</dd>
              <dt>Merchant</dt><dd>{txn.merchant_name ?? "—"}</dd>
              <dt>Amount</dt>
              <dd className={`amount ${txn.amount < 0 ? "amount-negative" : ""}`}>
                {txn.amount.toFixed(2)} {txn.currency}
              </dd>
              <dt>Status</dt>
              <dd>
                <span className={`badge badge-${txn.status}`}>{txn.status}</span>
              </dd>
              <dt>Tags</dt>
              <dd>
                {txn.tags.length > 0 ? txn.tags.join(", ") : <span className="muted">none</span>}
              </dd>
            </dl>

            <div className="detail-section">
              <label htmlFor="detail-category">Category</label>
              <select
                id="detail-category"
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                data-testid="detail-category"
              >
                <option value="">— uncategorized —</option>
                {leafCategories.map((c) => (
                  <option key={c.category_id} value={c.category_id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="detail-section">
              <label htmlFor="detail-notes">Notes</label>
              <textarea
                id="detail-notes"
                rows={3}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                data-testid="detail-notes"
              />
            </div>

            <div className="detail-section detail-toggles">
              <label>
                <input
                  type="checkbox"
                  checked={txn.is_transfer}
                  onChange={() => handleToggle("is_transfer")}
                  data-testid="detail-is-transfer"
                />
                {" "}Mark as transfer
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={txn.is_excluded}
                  onChange={() => handleToggle("is_excluded")}
                  data-testid="detail-is-excluded"
                />
                {" "}Exclude from budget
              </label>
            </div>

            <div className="detail-actions">
              <button
                className="btn btn-primary"
                onClick={handleSave}
                disabled={patchResult.status === "loading"}
                data-testid="detail-save"
              >
                {patchResult.status === "loading" ? "Saving…" : "Save"}
              </button>
              {patchResult.status === "success" && (
                <span className="muted" data-testid="detail-saved-msg"> Saved.</span>
              )}
              {patchResult.status === "error" && (
                <span className="error-text" data-testid="detail-save-error">
                  {" "}Error: {patchResult.message}
                </span>
              )}
            </div>

            {txn.splits.length > 0 && (
              <div className="detail-section">
                <h3>Splits</h3>
                <table className="data-table" data-testid="detail-splits">
                  <thead>
                    <tr>
                      <th>Amount</th>
                      <th>Category</th>
                      <th>Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {txn.splits.map((s) => (
                      <tr key={s.split_id}>
                        <td className="amount">{s.amount.toFixed(2)}</td>
                        <td>{s.category_id ?? "—"}</td>
                        <td>{s.notes ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {txn.raw_provider_payloads.length > 0 && (
              <details className="detail-section">
                <summary>Raw Provider Data ({txn.raw_provider_payloads.length})</summary>
                <pre className="raw-payload" data-testid="detail-raw">
                  {JSON.stringify(txn.raw_provider_payloads, null, 2)}
                </pre>
              </details>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
