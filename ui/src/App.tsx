/**
 * Root application component.
 *
 * Reads the API token from the Tauri runtime, gates the UI on its
 * presence, and orchestrates data refresh across all panels.
 *
 * REQ: ACC-SYS-001, ACC-SYS-002, ACC-SYS-003,
 * REQ: ACC-ACCT-001, ACC-ACCT-002, ACC-ACCT-003, ACC-ACCT-004,
 * REQ: ACC-ACCT-005, ACC-SYNC-001, ACC-TXN-001, ACC-TXN-002,
 * REQ: ACC-TXN-003, ACC-TXN-004, ACC-TXN-005, ACC-TXN-006,
 * REQ: ACC-TXN-007, ACC-TXN-008, ACC-CAT-001, ACC-SYNC-006,
 * REQ: ACC-SYNC-007,
 * REQ: ACC-REP-001, ACC-REP-002, ACC-REP-003, ACC-REP-004, ACC-REP-005,
 * REQ: ACC-REP-006, ACC-REP-007, ACC-REP-008,
 * REQ: ACC-EXP-001, ACC-EXP-002, ACC-EXP-003,
 * REQ: ACC-BKP-001, ACC-BKP-002, ACC-BKP-003, ACC-BKP-004, ACC-BKP-006,
 * REQ: ACC-SET-001, ACC-SET-002, ACC-SET-003, ACC-SET-004, ACC-SET-005,
 * REQ: ACC-AUD-004,
 * REQ: TECH-SEC-ACC-001, TECH-SEC-ACC-002, TECH-SEC-ACC-003, TECH-SEC-ACC-004, TECH-SEC-DATA-001,
 * REQ: ACC-BUD-001, ACC-BUD-002, ACC-BUD-003, ACC-BUD-004
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
type MountedTabs = Record<AppTab, boolean>;
const INITIAL_MOUNTED_TABS: MountedTabs = {
  overview: true,
  transactions: false,
  reports: false,
  data: false,
};

export function App() {
  // null = still loading from Tauri; "" = token not configured
  const [token, setToken] = useState<string | null>(null);
  // Incrementing this causes all data panels to re-fetch.
  const [refreshKey, setRefreshKey] = useState(0);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [filterValues, setFilterValues] = useState<FilterValues>(EMPTY_FILTERS);
  const [selectedTxnId, setSelectedTxnId] = useState<string | null>(null);
  const [reportTrendCategoryIds, setReportTrendCategoryIds] = useState<string[]>([]);
  const [authReady, setAuthReady] = useState(false);
  const [activeTab, setActiveTab] = useState<AppTab>("overview");
  const [mountedTabs, setMountedTabs] = useState<MountedTabs>(INITIAL_MOUNTED_TABS);

  // REQ: TECH-SEC-ACC-004, TECH-SEC-DATA-001 — obtain token from Tauri at runtime, and
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
    setMountedTabs(INITIAL_MOUNTED_TABS);
    setSelectedTxnId(null);
    setReportTrendCategoryIds([]);
    setFilterValues(EMPTY_FILTERS);
  }, [token]);

  useEffect(() => {
    const onLocked = () => {
      GodzillaApi.setUnlockToken(null);
      setAuthReady(false);
      setActiveTab("overview");
      setMountedTabs(INITIAL_MOUNTED_TABS);
      setSelectedTxnId(null);
      setReportTrendCategoryIds([]);
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
    setMountedTabs((current) => (current[tab] ? current : { ...current, [tab]: true }));
    setActiveTab(tab);
    if (tab !== "transactions") {
      setSelectedTxnId(null);
    }
  };
  const panelStyle = (tab: AppTab) => (activeTab === tab ? undefined : { display: "none" as const });

  // REQ: ACC-BUD-003 — drill-down from overspent budget row into transactions
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

  // REQ: ACC-REP-002 — drill-down from report metrics to transaction filters.
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
              id="tab-button-overview"
              className={`btn btn-sm ${activeTab === "overview" ? "btn-primary" : ""}`}
              onClick={() => switchTab("overview")}
              data-testid="tab-overview"
              aria-controls="tab-panel-overview"
            >
              Overview
            </button>
            <button
              id="tab-button-transactions"
              className={`btn btn-sm ${activeTab === "transactions" ? "btn-primary" : ""}`}
              onClick={() => switchTab("transactions")}
              data-testid="tab-transactions"
              aria-controls="tab-panel-transactions"
            >
              Transactions
            </button>
            <button
              id="tab-button-reports"
              className={`btn btn-sm ${activeTab === "reports" ? "btn-primary" : ""}`}
              onClick={() => switchTab("reports")}
              data-testid="tab-reports"
              aria-controls="tab-panel-reports"
            >
              Reports
            </button>
            <button
              id="tab-button-data"
              className={`btn btn-sm ${activeTab === "data" ? "btn-primary" : ""}`}
              onClick={() => switchTab("data")}
              data-testid="tab-data"
              aria-controls="tab-panel-data"
            >
              Data
            </button>
          </nav>
        </div>
      </header>
      <main className="app-main">
        {mountedTabs.overview && (
          <section
            id="tab-panel-overview"
            role="tabpanel"
            aria-labelledby="tab-button-overview"
            hidden={activeTab !== "overview"}
            style={panelStyle("overview")}
            className="tab-panel"
            data-testid="tab-panel-overview"
          >
            <SyncStatePanel
              token={token}
              refreshKey={refreshKey}
              onRefresh={handleRefresh}
            />
            <ConflictQueue token={token} refreshKey={refreshKey} />
            <AccountsTable token={token} refreshKey={refreshKey} />
            <BalancesTable token={token} refreshKey={refreshKey} />
          </section>
        )}
        {mountedTabs.transactions && (
          <section
            id="tab-panel-transactions"
            role="tabpanel"
            aria-labelledby="tab-button-transactions"
            hidden={activeTab !== "transactions"}
            style={panelStyle("transactions")}
            className="tab-panel"
            data-testid="tab-panel-transactions"
          >
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
          </section>
        )}
        {mountedTabs.reports && (
          <section
            id="tab-panel-reports"
            role="tabpanel"
            aria-labelledby="tab-button-reports"
            hidden={activeTab !== "reports"}
            style={panelStyle("reports")}
            className="tab-panel"
            data-testid="tab-panel-reports"
          >
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
              trendCategoryIds={reportTrendCategoryIds}
              onTrendCategoryIdsChange={setReportTrendCategoryIds}
            />
          </section>
        )}
        {mountedTabs.data && (
          <section
            id="tab-panel-data"
            role="tabpanel"
            aria-labelledby="tab-button-data"
            hidden={activeTab !== "data"}
            style={panelStyle("data")}
            className="tab-panel"
            data-testid="tab-panel-data"
          >
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
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
