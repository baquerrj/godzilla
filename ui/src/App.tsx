/**
 * Root application component.
 *
 * Reads the API token from the Tauri runtime, gates the UI on its
 * presence, and orchestrates data refresh across all panels.
 *
 * REQ: FUNC-ACCT-001, FUNC-ACCT-002, FUNC-ACCT-003, FUNC-ACCT-004,
 * REQ: FUNC-ACCT-005, FUNC-SYNC-001, FUNC-TXN-001, FUNC-TXN-002,
 * REQ: FUNC-TXN-003, FUNC-TXN-004, FUNC-TXN-005, FUNC-TXN-006,
 * REQ: FUNC-TXN-007, FUNC-TXN-008, FUNC-CAT-001, FUNC-SYNC-006,
 * REQ: FUNC-SYNC-007,
 * REQ: FUNC-REP-001, FUNC-REP-002, FUNC-REP-003, FUNC-REP-004, FUNC-REP-005,
 * REQ: FUNC-REP-006, FUNC-REP-007, FUNC-REP-008,
 * REQ: FUNC-EXP-001, FUNC-EXP-002, FUNC-EXP-003,
 * REQ: FUNC-BKP-001, FUNC-BKP-002, FUNC-BKP-003, FUNC-BKP-004, FUNC-BKP-006,
 * REQ: FUNC-SET-001, FUNC-SET-002, FUNC-SET-003, FUNC-SET-004, FUNC-SET-005,
 * REQ: FUNC-AUD-004,
 * REQ: SEC-ACC-001, SEC-ACC-002, SEC-ACC-003, SEC-ACC-004, SEC-DATA-001,
 * REQ: FUNC-BUD-001, FUNC-BUD-002, FUNC-BUD-003, FUNC-BUD-004
 */

import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { AccountsTable } from "./components/AccountsTable";
import { AuthGatePanel } from "./components/AuthGatePanel";
import { BalancesTable } from "./components/BalancesTable";
import { BudgetPanel } from "./components/BudgetPanel";
import { ConflictQueue } from "./components/ConflictQueue";
import { DataManagementPanel } from "./components/DataManagementPanel";
import { ExportPanel } from "./components/ExportPanel";
import { ReportsPanel } from "./components/ReportsPanel";
import type { ReportDrillDown } from "./components/ReportsPanel";
import { SettingsPanel } from "./components/SettingsPanel";
import { SyncStatePanel } from "./components/SyncStatePanel";
import { TransactionDetailPanel } from "./components/TransactionDetailPanel";
import { TransactionFilters, EMPTY_FILTERS } from "./components/TransactionFilters";
import type { FilterValues } from "./components/TransactionFilters";
import { TransactionsTable } from "./components/TransactionsTable";
import { GodzillaApi } from "./api/client";
import type { Account, Category, GetTransactionsParams } from "./api/types";
import "./App.css";

const DEV_PROXY_TOKEN = "__vite_dev_proxy_token__";
type AppTab = "overview" | "transactions" | "reports" | "data";

export function App() {
  // null = still loading from Tauri; "" = token not configured
  const [token, setToken] = useState<string | null>(null);
  // Incrementing this causes all data panels to re-fetch.
  const [refreshKey, setRefreshKey] = useState(0);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [filterValues, setFilterValues] = useState<FilterValues>(EMPTY_FILTERS);
  const [selectedTxnId, setSelectedTxnId] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [activeTab, setActiveTab] = useState<AppTab>("overview");

  // REQ: SEC-ACC-004, SEC-DATA-001 — obtain token from Tauri at runtime, and
  // fall back to a dev-only proxy token when running in a plain browser.
  useEffect(() => {
    const hasTauriRuntime =
      typeof window !== "undefined"
      && "__TAURI_INTERNALS__" in (window as unknown as Record<string, unknown>);

    if (import.meta.env.DEV && !hasTauriRuntime) {
      setToken(DEV_PROXY_TOKEN);
      return;
    }

    invoke<string>("get_api_token")
      .then((t) => setToken(t ?? ""))
      .catch(() => setToken(""));
  }, []);

  useEffect(() => {
    GodzillaApi.setUnlockToken(null);
    setAuthReady(false);
    setActiveTab("overview");
    setSelectedTxnId(null);
    setFilterValues(EMPTY_FILTERS);
  }, [token]);

  useEffect(() => {
    const onLocked = () => {
      GodzillaApi.setUnlockToken(null);
      setAuthReady(false);
      setActiveTab("overview");
      setSelectedTxnId(null);
      setFilterValues(EMPTY_FILTERS);
    };
    window.addEventListener("godzilla-lock", onLocked);
    return () => window.removeEventListener("godzilla-lock", onLocked);
  }, []);

  // Load filter lookup data whenever token/refresh changes.
  useEffect(() => {
    if (!token || !authReady) return;
    const loadLookups = async () => {
      const [accountsResult, categoriesResult] = await Promise.allSettled([
        GodzillaApi.getAccounts(token),
        GodzillaApi.getCategories(token),
      ]);
      if (accountsResult.status === "fulfilled") {
        setAccounts(accountsResult.value);
      }
      if (categoriesResult.status === "fulfilled") {
        setCategories(categoriesResult.value);
      }
    };
    void loadLookups();
  }, [token, refreshKey, authReady]);

  const handleRefresh = () => {
    setRefreshKey((k) => k + 1);
  };

  const switchTab = (tab: AppTab) => {
    setActiveTab(tab);
    if (tab !== "transactions") {
      setSelectedTxnId(null);
    }
  };

  // REQ: FUNC-BUD-003 — drill-down from overspent budget row into transactions
  const handleBudgetDrillDown = (categoryId: string, month: string) => {
    const [year, monthNum] = month.split("-").map(Number);
    const lastDay = new Date(year, monthNum, 0).getDate();
    setFilterValues({
      ...EMPTY_FILTERS,
      category_id: categoryId,
      date_from: `${month}-01`,
      date_to: `${month}-${String(lastDay).padStart(2, "0")}`,
    });
    switchTab("transactions");
  };

  // REQ: FUNC-REP-002 — drill-down from report metrics to transaction filters.
  const handleReportDrillDown = (input: ReportDrillDown) => {
    setFilterValues({
      ...EMPTY_FILTERS,
      date_from: input.startDate,
      date_to: input.endDate,
      ...(input.categoryId ? { category_id: input.categoryId } : {}),
      ...(input.flow === "income" ? { amount_max: "-0.01" } : {}),
      ...(input.flow === "expense" ? { amount_min: "0.01" } : {}),
    });
    switchTab("transactions");
  };

  // Build API filter params from controlled filter form values
  const activeFilters: GetTransactionsParams = useMemo(
    () => ({
      ...(filterValues.account_id ? { account_id: filterValues.account_id } : {}),
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
    }),
    [filterValues],
  );

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

  if (!authReady) {
    return (
      <div className="app">
        <header className="app-header">
          <div className="app-header-row">
            <h1>Godzilla</h1>
          </div>
        </header>
        <main className="app-main">
          <AuthGatePanel
            token={token}
            onAuthenticated={(unlockToken) => {
              GodzillaApi.setUnlockToken(unlockToken);
              setAuthReady(true);
              setRefreshKey((key) => key + 1);
            }}
          />
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-row">
          <h1>Godzilla</h1>
          <nav className="app-nav" aria-label="Primary navigation" data-testid="app-tabs">
            <button
              className={`btn btn-sm ${activeTab === "overview" ? "btn-primary" : ""}`}
              onClick={() => switchTab("overview")}
              data-testid="tab-overview"
            >
              Overview
            </button>
            <button
              className={`btn btn-sm ${activeTab === "transactions" ? "btn-primary" : ""}`}
              onClick={() => switchTab("transactions")}
              data-testid="tab-transactions"
            >
              Transactions
            </button>
            <button
              className={`btn btn-sm ${activeTab === "reports" ? "btn-primary" : ""}`}
              onClick={() => switchTab("reports")}
              data-testid="tab-reports"
            >
              Reports
            </button>
            <button
              className={`btn btn-sm ${activeTab === "data" ? "btn-primary" : ""}`}
              onClick={() => switchTab("data")}
              data-testid="tab-data"
            >
              Data
            </button>
          </nav>
        </div>
      </header>
      <main className="app-main">
        {activeTab === "overview" && (
          <>
            <SyncStatePanel
              token={token}
              refreshKey={refreshKey}
              onRefresh={handleRefresh}
            />
            <ConflictQueue token={token} refreshKey={refreshKey} />
            <AccountsTable token={token} refreshKey={refreshKey} />
            <BalancesTable token={token} refreshKey={refreshKey} />
          </>
        )}
        {activeTab === "transactions" && (
          <>
            <TransactionFilters
              values={filterValues}
              accounts={accounts}
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
          </>
        )}
        {activeTab === "reports" && (
          <>
            <BudgetPanel
              token={token}
              refreshKey={refreshKey}
              categories={categories}
              onDrillDown={handleBudgetDrillDown}
            />
            <ReportsPanel
              token={token}
              refreshKey={refreshKey}
              categories={categories}
              onDrillDown={handleReportDrillDown}
            />
          </>
        )}
        {activeTab === "data" && (
          <>
            <SettingsPanel
              token={token}
              refreshKey={refreshKey}
              onSaved={handleRefresh}
            />
            <ExportPanel
              token={token}
              refreshKey={refreshKey}
              filters={activeFilters}
            />
            <DataManagementPanel
              token={token}
              onDataChanged={handleRefresh}
            />
          </>
        )}
      </main>
    </div>
  );
}

export default App;
