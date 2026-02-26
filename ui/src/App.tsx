/**
 * Root application component.
 *
 * Reads the API token from the Tauri runtime, gates the UI on its
 * presence, and orchestrates data refresh across all panels.
 *
 * Accounts and settings are fetched here once and passed down as props so
 * child panels (AccountsTable, SettingsPanel, ExportPanel) do not issue
 * duplicate API requests for the same data on the same refresh cycle.
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

import { memo, useCallback, useEffect, useMemo, useState } from "react";
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
import { GodzillaApi, useApiCall } from "./api/client";
import type { Account, Category, GetTransactionsParams, SettingsResponse } from "./api/types";
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

// ---------------------------------------------------------------------------
// Memoized tab panels (S1-4)
// Each panel only re-renders when its own props change, isolating re-renders
// from App-level state that belongs to sibling tabs.
// ---------------------------------------------------------------------------

interface OverviewTabProps {
  token: string;
  refreshKey: number;
  accounts: Account[];
  accountsLoading: boolean;
  accountsError: string | null;
  onRefresh: () => void;
}

const OverviewTabPanel = memo(function OverviewTabPanel({
  token,
  refreshKey,
  accounts,
  accountsLoading,
  accountsError,
  onRefresh,
}: OverviewTabProps) {
  return (
    <>
      <SyncStatePanel token={token} refreshKey={refreshKey} onRefresh={onRefresh} />
      <ConflictQueue token={token} refreshKey={refreshKey} />
      <AccountsTable accounts={accounts} loading={accountsLoading} error={accountsError} />
      <BalancesTable token={token} refreshKey={refreshKey} />
    </>
  );
});

interface TransactionsTabProps {
  token: string;
  refreshKey: number;
  accounts: Account[];
  categories: Category[];
  filterValues: FilterValues;
  activeFilters: GetTransactionsParams;
  selectedTxnId: string | null;
  onFilterChange: (values: FilterValues) => void;
  onFilterReset: () => void;
  onSelectTransaction: (id: string) => void;
  onCloseDetail: () => void;
  onUpdated: () => void;
}

const TransactionsTabPanel = memo(function TransactionsTabPanel({
  token,
  refreshKey,
  accounts,
  categories,
  filterValues,
  activeFilters,
  selectedTxnId,
  onFilterChange,
  onFilterReset,
  onSelectTransaction,
  onCloseDetail,
  onUpdated,
}: TransactionsTabProps) {
  return (
    <>
      <TransactionFilters
        values={filterValues}
        accounts={accounts}
        categories={categories}
        onChange={onFilterChange}
        onReset={onFilterReset}
      />
      <TransactionsTable
        token={token}
        refreshKey={refreshKey}
        filters={activeFilters}
        onSelectTransaction={onSelectTransaction}
      />
      <TransactionDetailPanel
        token={token}
        transactionId={selectedTxnId}
        categories={categories}
        onClose={onCloseDetail}
        onUpdated={onUpdated}
      />
    </>
  );
});

interface ReportsTabProps {
  token: string;
  refreshKey: number;
  categories: Category[];
  trendCategoryIds: string[];
  onBudgetDrillDown: (categoryId: string, month: string) => void;
  onReportDrillDown: (input: ReportDrillDown) => void;
  onTrendCategoryIdsChange: (ids: string[]) => void;
}

const ReportsTabPanel = memo(function ReportsTabPanel({
  token,
  refreshKey,
  categories,
  trendCategoryIds,
  onBudgetDrillDown,
  onReportDrillDown,
  onTrendCategoryIdsChange,
}: ReportsTabProps) {
  return (
    <>
      <BudgetPanel
        token={token}
        refreshKey={refreshKey}
        categories={categories}
        onDrillDown={onBudgetDrillDown}
      />
      <ReportsPanel
        token={token}
        refreshKey={refreshKey}
        categories={categories}
        onDrillDown={onReportDrillDown}
        trendCategoryIds={trendCategoryIds}
        onTrendCategoryIdsChange={onTrendCategoryIdsChange}
      />
    </>
  );
});

interface DataTabProps {
  token: string;
  settings: SettingsResponse | null;
  settingsLoading: boolean;
  settingsError: string | null;
  activeFilters: GetTransactionsParams;
  onSaved: () => void;
  onDataChanged: () => void;
}

const DataTabPanel = memo(function DataTabPanel({
  token,
  settings,
  settingsLoading,
  settingsError,
  activeFilters,
  onSaved,
  onDataChanged,
}: DataTabProps) {
  return (
    <>
      <SettingsPanel
        token={token}
        settings={settings}
        settingsLoading={settingsLoading}
        settingsError={settingsError}
        onSaved={onSaved}
      />
      <ExportPanel
        token={token}
        filters={activeFilters}
        settings={settings}
        settingsError={settingsError}
      />
      <DataManagementPanel token={token} onDataChanged={onDataChanged} />
    </>
  );
});

// ---------------------------------------------------------------------------
// Root App component
// ---------------------------------------------------------------------------

export function App() {
  // null = still loading from Tauri; "" = token not configured
  const [token, setToken] = useState<string | null>(null);
  // Incrementing this causes all data panels to re-fetch.
  const [refreshKey, setRefreshKey] = useState(0);
  const [filterValues, setFilterValues] = useState<FilterValues>(EMPTY_FILTERS);
  const [selectedTxnId, setSelectedTxnId] = useState<string | null>(null);
  const [reportTrendCategoryIds, setReportTrendCategoryIds] = useState<string[]>([]);
  const [authReady, setAuthReady] = useState(false);
  const [activeTab, setActiveTab] = useState<AppTab>("overview");
  const [mountedTabs, setMountedTabs] = useState<MountedTabs>(INITIAL_MOUNTED_TABS);

  // Shared API results lifted from child components (S1-1, S1-2).
  const [accountsResult, executeAccounts] = useApiCall<Account[]>();
  const [categoriesResult, executeCategories] = useApiCall<Category[]>();
  const [settingsResult, executeSettings] = useApiCall<SettingsResponse>();

  // REQ: SEC-ACC-004, SEC-DATA-001 — obtain token from Tauri at runtime, and
  // fall back to a dev-only proxy token when running in a plain browser.
  useEffect(() => {
    const hasTauriRuntime =
      typeof window !== "undefined" &&
      "__TAURI_INTERNALS__" in (window as unknown as Record<string, unknown>);

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

  // S1-1: Fetch accounts + categories once per refresh cycle.
  // AccountsTable and TransactionFilters both consume this result via props.
  useEffect(() => {
    if (!token || !authReady) return;
    void executeAccounts(() => GodzillaApi.getAccounts(token));
    void executeCategories(() => GodzillaApi.getCategories(token));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, refreshKey, authReady]);

  // S1-2: Fetch settings once when the data tab is first mounted or refreshed.
  // SettingsPanel and ExportPanel both consume this result via props.
  useEffect(() => {
    if (!token || !authReady || !mountedTabs.data) return;
    void executeSettings(() => GodzillaApi.getSettings(token));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, refreshKey, authReady, mountedTabs.data]);

  const handleRefresh = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  const switchTab = useCallback((tab: AppTab) => {
    setMountedTabs((current) => (current[tab] ? current : { ...current, [tab]: true }));
    setActiveTab(tab);
    if (tab !== "transactions") {
      setSelectedTxnId(null);
    }
  }, []);

  const panelStyle = (tab: AppTab) =>
    activeTab === tab ? undefined : { display: "none" as const };

  // REQ: FUNC-BUD-003 — drill-down from overspent budget row into transactions
  const handleBudgetDrillDown = useCallback(
    (categoryId: string, month: string) => {
      const [year, monthNum] = month.split("-").map(Number);
      const lastDay = new Date(year, monthNum, 0).getDate();
      setFilterValues({
        ...EMPTY_FILTERS,
        category_id: categoryId,
        date_from: `${month}-01`,
        date_to: `${month}-${String(lastDay).padStart(2, "0")}`,
      });
      switchTab("transactions");
    },
    [switchTab],
  );

  // REQ: FUNC-REP-002 — drill-down from report metrics to transaction filters.
  const handleReportDrillDown = useCallback(
    (input: ReportDrillDown) => {
      setFilterValues({
        ...EMPTY_FILTERS,
        date_from: input.startDate,
        date_to: input.endDate,
        ...(input.categoryId ? { category_id: input.categoryId } : {}),
        ...(input.flow === "income" ? { amount_max: "-0.01" } : {}),
        ...(input.flow === "expense" ? { amount_min: "0.01" } : {}),
      });
      switchTab("transactions");
    },
    [switchTab],
  );

  const handleFilterReset = useCallback(() => setFilterValues(EMPTY_FILTERS), []);
  const handleCloseDetail = useCallback(() => setSelectedTxnId(null), []);

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

  // Derive shared data from API results.
  const accounts = accountsResult.status === "success" ? accountsResult.data : [];
  const categories = categoriesResult.status === "success" ? categoriesResult.data : [];
  const settings = settingsResult.status === "success" ? settingsResult.data : null;
  const settingsLoading = settingsResult.status === "loading";
  const settingsError = settingsResult.status === "error" ? settingsResult.message : null;
  const accountsLoading = accountsResult.status === "loading";
  const accountsError = accountsResult.status === "error" ? accountsResult.message : null;

  if (token === null) {
    return <div className="status-msg">Connecting…</div>;
  }

  if (token === "") {
    return (
      <div className="status-msg status-error">
        <p>
          <strong>GODZILLA_API_TOKEN</strong> is not set.
        </p>
        <p>Start the sidecar with the required environment variables and relaunch the app.</p>
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
            <OverviewTabPanel
              token={token}
              refreshKey={refreshKey}
              accounts={accounts}
              accountsLoading={accountsLoading}
              accountsError={accountsError}
              onRefresh={handleRefresh}
            />
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
            <TransactionsTabPanel
              token={token}
              refreshKey={refreshKey}
              accounts={accounts}
              categories={categories}
              filterValues={filterValues}
              activeFilters={activeFilters}
              selectedTxnId={selectedTxnId}
              onFilterChange={setFilterValues}
              onFilterReset={handleFilterReset}
              onSelectTransaction={setSelectedTxnId}
              onCloseDetail={handleCloseDetail}
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
            <ReportsTabPanel
              token={token}
              refreshKey={refreshKey}
              categories={categories}
              trendCategoryIds={reportTrendCategoryIds}
              onBudgetDrillDown={handleBudgetDrillDown}
              onReportDrillDown={handleReportDrillDown}
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
            <DataTabPanel
              token={token}
              settings={settings}
              settingsLoading={settingsLoading}
              settingsError={settingsError}
              activeFilters={activeFilters}
              onSaved={handleRefresh}
              onDataChanged={handleRefresh}
            />
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
