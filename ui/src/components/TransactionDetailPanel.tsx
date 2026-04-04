/**
 * TransactionDetailPanel: slide-in detail view for a selected transaction.
 *
 * Shows all fields, tags, splits, and raw provider payloads.
 * Allows patching category/notes/flags and replacing transaction splits.
 *
 * REQ: ACC-TXN-003, ACC-TXN-004, ACC-TXN-005, ACC-TXN-006,
 * REQ: ACC-TXN-007, ACC-TXN-008
 */

import { useEffect, useState } from "react";
import { GodzillaApi, useApiCall } from "../api/client";
import type { Category, TransactionDetail } from "../api/types";
import { leafActiveCategories } from "./categoryUtils";

interface Props {
  token: string;
  transactionId: string | null;
  categories: Category[];
  onClose: () => void;
  onUpdated: () => void;
}

interface EditableSplitRow {
  amount: string;
  category_id: string;
  notes: string;
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
  const [splitResult, executeSplit] = useApiCall<TransactionDetail>();
  const [notes, setNotes] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [splitRows, setSplitRows] = useState<EditableSplitRow[]>([]);
  const leafCategories = leafActiveCategories(categories);

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
      if (detail.data.splits.length > 0) {
        setSplitRows(
          detail.data.splits.map((split) => ({
            amount: split.amount.toFixed(2),
            category_id: split.category_id ?? "",
            notes: split.notes ?? "",
          })),
        );
      } else {
        setSplitRows([
          {
            amount: detail.data.amount.toFixed(2),
            category_id: detail.data.category_id ?? "",
            notes: "",
          },
        ]);
      }
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
  const splitTotal = splitRows.reduce((total, split) => {
    const amount = Number.parseFloat(split.amount);
    return Number.isFinite(amount) ? total + amount : total;
  }, 0);
  const splitRemaining = txn ? txn.amount - splitTotal : 0;
  const splitHasInvalidAmount = splitRows.some(
    (split) => split.amount.trim() === "" || !Number.isFinite(Number.parseFloat(split.amount)),
  );
  const splitCanSave = txn !== null && !splitHasInvalidAmount && Math.abs(splitRemaining) <= 0.005;

  const updateSplit = (
    index: number,
    field: keyof EditableSplitRow,
    value: string,
  ) => {
    setSplitRows((rows) =>
      rows.map((row, rowIndex) =>
        rowIndex === index ? { ...row, [field]: value } : row,
      ),
    );
  };

  const addSplitRow = () => {
    setSplitRows((rows) => [
      ...rows,
      { amount: "0.00", category_id: "", notes: "" },
    ]);
  };

  const removeSplitRow = (index: number) => {
    setSplitRows((rows) => rows.filter((_, rowIndex) => rowIndex !== index));
  };

  const handleSaveSplits = () => {
    if (!txn || !splitCanSave) return;
    executeSplit(async () => {
      const payload = splitRows.map((split) => ({
        amount: Number.parseFloat(split.amount),
        category_id: split.category_id || null,
        notes: split.notes.trim() === "" ? null : split.notes,
      }));
      const result = await GodzillaApi.postSplits(token, transactionId, payload);
      await fetchDetail(() => GodzillaApi.getTransaction(token, transactionId));
      onUpdated();
      return result;
    });
  };

  const handleClearSplits = () => {
    executeSplit(async () => {
      const result = await GodzillaApi.postSplits(token, transactionId, []);
      await fetchDetail(() => GodzillaApi.getTransaction(token, transactionId));
      onUpdated();
      return result;
    });
  };

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
              <dt>Account</dt><dd>{txn.account_name}</dd>
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

            <div className="detail-section">
              <h3>Splits</h3>
              <table className="data-table" data-testid="detail-splits-editor">
                <thead>
                  <tr>
                    <th>Amount</th>
                    <th>Category</th>
                    <th>Notes</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {splitRows.map((split, index) => (
                    <tr key={`split-row-${index}`}>
                      <td>
                        <input
                          type="number"
                          step="0.01"
                          value={split.amount}
                          onChange={(event) => updateSplit(index, "amount", event.target.value)}
                          data-testid={`split-amount-${index}`}
                        />
                      </td>
                      <td>
                        <select
                          value={split.category_id}
                          onChange={(event) =>
                            updateSplit(index, "category_id", event.target.value)
                          }
                          data-testid={`split-category-${index}`}
                        >
                          <option value="">— uncategorized —</option>
                          {leafCategories.map((category) => (
                            <option key={category.category_id} value={category.category_id}>
                              {category.name}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <input
                          type="text"
                          value={split.notes}
                          onChange={(event) => updateSplit(index, "notes", event.target.value)}
                          data-testid={`split-notes-${index}`}
                        />
                      </td>
                      <td>
                        <button
                          className="btn btn-sm"
                          onClick={() => removeSplitRow(index)}
                          disabled={splitRows.length <= 1}
                          data-testid={`split-remove-${index}`}
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="split-meta">
                <span data-testid="split-total">Total: {splitTotal.toFixed(2)}</span>
                <span data-testid="split-remaining">
                  Remaining: {splitRemaining.toFixed(2)}
                </span>
              </div>
              {splitHasInvalidAmount && (
                <p className="error-text" data-testid="split-invalid-amount">
                  Every split must have a numeric amount.
                </p>
              )}
              {!splitHasInvalidAmount && Math.abs(splitRemaining) > 0.005 && (
                <p className="error-text" data-testid="split-invalid-total">
                  Split amounts must sum to the transaction amount.
                </p>
              )}
              <div className="detail-actions">
                <button
                  className="btn btn-sm"
                  onClick={addSplitRow}
                  data-testid="split-add"
                >
                  Add Split
                </button>
                <button
                  className="btn btn-sm"
                  onClick={handleClearSplits}
                  disabled={splitResult.status === "loading"}
                  data-testid="split-clear"
                >
                  Clear Splits
                </button>
                <button
                  className="btn btn-primary"
                  onClick={handleSaveSplits}
                  disabled={!splitCanSave || splitResult.status === "loading"}
                  data-testid="split-save"
                >
                  {splitResult.status === "loading" ? "Saving Splits…" : "Save Splits"}
                </button>
                {splitResult.status === "error" && (
                  <span className="error-text" data-testid="split-save-error">
                    Error: {splitResult.message}
                  </span>
                )}
              </div>
            </div>

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
