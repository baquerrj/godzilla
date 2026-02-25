/**
 * ExportPanel: transaction/categories/audit exports with download actions.
 *
 * REQ: FUNC-EXP-001, FUNC-EXP-002, FUNC-EXP-003, FUNC-AUD-004, FUNC-SET-005
 */

import { useEffect, useState } from "react";
import { GodzillaApi, useApiCall } from "../api/client";
import type {
  CategoriesBudgetsExportJson,
  GetTransactionsParams,
  SettingsResponse,
} from "../api/types";
import { downloadBlob } from "../utils/download";

interface Props {
  token: string;
  filters: GetTransactionsParams;
  refreshKey: number;
}

function normalizeMonth(value: string): string | undefined {
  return /^\d{4}-\d{2}$/.test(value) ? value : undefined;
}

export function ExportPanel({ token, filters, refreshKey }: Props) {
  const [includeRawPayloads, setIncludeRawPayloads] = useState(false);
  const [categoriesBudgetsFormat, setCategoriesBudgetsFormat] = useState<"csv" | "json">("csv");
  const [categoriesBudgetsMonth, setCategoriesBudgetsMonth] = useState("");
  const [auditEventType, setAuditEventType] = useState("");
  const [auditStart, setAuditStart] = useState("");
  const [auditEnd, setAuditEnd] = useState("");
  const [auditLimit, setAuditLimit] = useState("200");

  const [settingsResult, executeSettings] = useApiCall<SettingsResponse>();
  const [exportResult, executeExport] = useApiCall<string>();

  useEffect(() => {
    void executeSettings(() => GodzillaApi.getSettings(token));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, refreshKey]);

  useEffect(() => {
    if (settingsResult.status === "success") {
      setIncludeRawPayloads(settingsResult.data.export_defaults.include_raw_payloads);
    }
  }, [settingsResult]);

  const handleExportTransactions = () => {
    void executeExport(async () => {
      const result = await GodzillaApi.exportTransactions(token, {
        ...filters,
        include_raw_payloads: includeRawPayloads,
      });
      downloadBlob(result.blob, result.filename ?? "transactions-export.csv");
      return "Transactions export downloaded.";
    });
  };

  const handleExportCategoriesBudgets = () => {
    void executeExport(async () => {
      const month = normalizeMonth(categoriesBudgetsMonth);
      if (categoriesBudgetsFormat === "csv") {
        const result = await GodzillaApi.exportCategoriesBudgetsCsv(token, { month });
        downloadBlob(result.blob, result.filename ?? "categories-budgets-export.csv");
        return "Categories/budgets CSV export downloaded.";
      }

      const payload: CategoriesBudgetsExportJson = await GodzillaApi.exportCategoriesBudgetsJson(
        token,
        { month },
      );
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      });
      downloadBlob(blob, "categories-budgets-export.json");
      return "Categories/budgets JSON export downloaded.";
    });
  };

  const handleExportAuditCsv = () => {
    void executeExport(async () => {
      const limitValue = Number.parseInt(auditLimit, 10);
      const result = await GodzillaApi.exportAuditLogCsv(token, {
        event_type: auditEventType || undefined,
        start: auditStart || undefined,
        end: auditEnd || undefined,
        limit: Number.isFinite(limitValue) ? Math.min(Math.max(limitValue, 1), 200) : 200,
      });
      downloadBlob(result.blob, result.filename ?? "audit-log-export.csv");
      return "Audit log CSV export downloaded.";
    });
  };

  return (
    <section className="panel" data-testid="export-panel">
      <div className="panel-header">
        <h2>Export</h2>
      </div>
      <p className="muted" data-testid="export-help-text">
        Export data for offline analysis. Transaction export reuses the active transaction filters.
      </p>

      <div className="m5-section">
        <h3>Transactions</h3>
        <label className="m5-inline-toggle">
          <input
            type="checkbox"
            checked={includeRawPayloads}
            onChange={(event) => setIncludeRawPayloads(event.target.checked)}
            data-testid="export-include-raw-toggle"
          />
          Include raw provider payloads (default from settings)
        </label>
        <button
          className="btn btn-sm"
          onClick={handleExportTransactions}
          data-testid="export-transactions-btn"
          disabled={exportResult.status === "loading"}
        >
          Export Transactions CSV
        </button>
      </div>

      <div className="m5-section">
        <h3>Categories &amp; Budgets</h3>
        <div className="m5-grid m5-grid-compact">
          <label>
            Format
            <select
              value={categoriesBudgetsFormat}
              onChange={(event) => setCategoriesBudgetsFormat(event.target.value as "csv" | "json")}
              data-testid="export-categories-format"
            >
              <option value="csv">CSV</option>
              <option value="json">JSON</option>
            </select>
          </label>
          <label>
            Month (optional)
            <input
              type="month"
              value={categoriesBudgetsMonth}
              onChange={(event) => setCategoriesBudgetsMonth(event.target.value)}
              data-testid="export-categories-month"
            />
          </label>
        </div>
        <button
          className="btn btn-sm"
          onClick={handleExportCategoriesBudgets}
          data-testid="export-categories-budgets-btn"
          disabled={exportResult.status === "loading"}
        >
          Export Categories/Budgets
        </button>
      </div>

      <div className="m5-section">
        <h3>Audit Log</h3>
        <div className="m5-grid">
          <label>
            Event type (optional)
            <input
              type="text"
              value={auditEventType}
              onChange={(event) => setAuditEventType(event.target.value)}
              placeholder="settings_updated"
              data-testid="export-audit-event-type"
            />
          </label>
          <label>
            Start date (optional)
            <input
              type="date"
              value={auditStart}
              onChange={(event) => setAuditStart(event.target.value)}
              data-testid="export-audit-start"
            />
          </label>
          <label>
            End date (optional)
            <input
              type="date"
              value={auditEnd}
              onChange={(event) => setAuditEnd(event.target.value)}
              data-testid="export-audit-end"
            />
          </label>
          <label>
            Limit (1-200)
            <input
              type="number"
              min={1}
              max={200}
              value={auditLimit}
              onChange={(event) => setAuditLimit(event.target.value)}
              data-testid="export-audit-limit"
            />
          </label>
        </div>
        <button
          className="btn btn-sm"
          onClick={handleExportAuditCsv}
          data-testid="export-audit-btn"
          disabled={exportResult.status === "loading"}
        >
          Export Audit CSV
        </button>
      </div>

      {settingsResult.status === "error" && (
        <p className="error-text">Failed to load export defaults: {settingsResult.message}</p>
      )}
      {exportResult.status === "error" && (
        <p className="error-text">Export failed: {exportResult.message}</p>
      )}
      {exportResult.status === "success" && (
        <p className="alert alert-success">{exportResult.data}</p>
      )}
    </section>
  );
}
