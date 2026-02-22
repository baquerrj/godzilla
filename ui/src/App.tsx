/**
 * Root application component.
 *
 * Reads the API token from the Tauri runtime, gates the UI on its
 * presence, and orchestrates data refresh across all panels.
 *
 * REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-003, FUNC-ACCT-004,
 * REQ: FUNC-ACCT-005, FUNC-SYNC-001, FUNC-TXN-001, FUNC-TXN-002,
 * REQ: FUNC-TXN-003, FUNC-CAT-001, FUNC-SYNC-006, FUNC-SYNC-007,
 * REQ: FUNC-REP-006, SEC-ACC-004
 */

import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { AccountsTable } from "./components/AccountsTable";
import { BalancesTable } from "./components/BalancesTable";
import { ConflictQueue } from "./components/ConflictQueue";
import { SyncStatePanel } from "./components/SyncStatePanel";
import { TransactionDetailPanel } from "./components/TransactionDetailPanel";
import { TransactionFilters, EMPTY_FILTERS } from "./components/TransactionFilters";
import type { FilterValues } from "./components/TransactionFilters";
import { TransactionsTable } from "./components/TransactionsTable";
import { GodzillaApi } from "./api/client";
import type { Category, GetTransactionsParams } from "./api/types";
import "./App.css";

export function App() {
  // null = still loading from Tauri; "" = token not configured
  const [token, setToken] = useState<string | null>(null);
  // Incrementing this causes all data panels to re-fetch.
  const [refreshKey, setRefreshKey] = useState(0);
  const [categories, setCategories] = useState<Category[]>([]);
  const [filterValues, setFilterValues] = useState<FilterValues>(EMPTY_FILTERS);
  const [selectedTxnId, setSelectedTxnId] = useState<string | null>(null);

  // REQ: SEC-ACC-004 — obtain API token from the Tauri runtime
  useEffect(() => {
    invoke<string>("get_api_token")
      .then((t) => setToken(t ?? ""))
      .catch(() => setToken(""));
  }, []);

  // Load categories once after token is available
  useEffect(() => {
    if (token) {
      GodzillaApi.getCategories(token)
        .then(setCategories)
        .catch(() => {
          // Categories are optional; swallow error silently
        });
    }
  }, [token]);

  const handleRefresh = () => {
    setRefreshKey((k) => k + 1);
    if (token) {
      GodzillaApi.getCategories(token)
        .then(setCategories)
        .catch(() => {});
    }
  };

  // Build API filter params from controlled filter form values
  const activeFilters: GetTransactionsParams = {
    ...(filterValues.date_from ? { date_from: filterValues.date_from } : {}),
    ...(filterValues.date_to ? { date_to: filterValues.date_to } : {}),
    ...(filterValues.merchant ? { merchant: filterValues.merchant } : {}),
    ...(filterValues.amount_min !== ""
      ? { amount_min: parseFloat(filterValues.amount_min) }
      : {}),
    ...(filterValues.amount_max !== ""
      ? { amount_max: parseFloat(filterValues.amount_max) }
      : {}),
    ...(filterValues.category_id ? { category_id: filterValues.category_id } : {}),
  };

  if (token === null) {
    return <div className="status-msg">Connecting…</div>;
  }

  if (token === "") {
    return (
      <div className="status-msg status-error">
        <p>
          <strong>GODZILLA_API_TOKEN</strong> is not set.
        </p>
        <p>
          Start the sidecar with the required environment variables and
          relaunch the app.
        </p>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Godzilla</h1>
      </header>
      <main className="app-main">
        <SyncStatePanel
          token={token}
          refreshKey={refreshKey}
          onRefresh={handleRefresh}
        />
        <ConflictQueue token={token} refreshKey={refreshKey} />
        <AccountsTable token={token} refreshKey={refreshKey} />
        <TransactionFilters
          values={filterValues}
          categories={categories}
          onChange={setFilterValues}
          onReset={() => setFilterValues(EMPTY_FILTERS)}
        />
        <TransactionsTable
          token={token}
          refreshKey={refreshKey}
          filters={activeFilters}
          onSelectTransaction={setSelectedTxnId}
        />
        <TransactionDetailPanel
          token={token}
          transactionId={selectedTxnId}
          categories={categories}
          onClose={() => setSelectedTxnId(null)}
          onUpdated={handleRefresh}
        />
        <BalancesTable token={token} refreshKey={refreshKey} />
      </main>
    </div>
  );
}

export default App;
