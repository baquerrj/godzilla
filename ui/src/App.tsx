/**
 * Root application component.
 *
 * Reads the API token from the Tauri runtime, gates the UI on its
 * presence, and orchestrates data refresh across all panels.
 *
 * REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-003, FUNC-ACCT-004,
 * REQ: FUNC-ACCT-005, FUNC-SYNC-001, FUNC-TXN-001, FUNC-REP-006,
 * REQ: SEC-ACC-004
 */

import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { AccountsTable } from "./components/AccountsTable";
import { BalancesTable } from "./components/BalancesTable";
import { SyncStatePanel } from "./components/SyncStatePanel";
import { TransactionsTable } from "./components/TransactionsTable";
import "./App.css";

export function App() {
  // null = still loading from Tauri; "" = token not configured
  const [token, setToken] = useState<string | null>(null);
  // Incrementing this causes all data panels to re-fetch.
  const [refreshKey, setRefreshKey] = useState(0);

  // REQ: SEC-ACC-004 — obtain API token from the Tauri runtime
  useEffect(() => {
    invoke<string>("get_api_token")
      .then((t) => setToken(t ?? ""))
      .catch(() => setToken(""));
  }, []);

  const handleRefresh = () => setRefreshKey((k) => k + 1);

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
        <AccountsTable token={token} refreshKey={refreshKey} />
        <TransactionsTable token={token} refreshKey={refreshKey} />
        <BalancesTable token={token} refreshKey={refreshKey} />
      </main>
    </div>
  );
}

export default App;
