/**
 * Tests for ExportPanel component.
 *
 * REQ: FUNC-EXP-001, FUNC-EXP-002, FUNC-EXP-003, FUNC-AUD-004, FUNC-SET-005
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ExportPanel } from "../components/ExportPanel";

vi.mock("../utils/download", () => ({
  downloadBlob: vi.fn(),
}));

vi.mock("../api/client", async () => {
  const actual =
    await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    GodzillaApi: {
      getSettings: vi.fn(),
      exportTransactions: vi.fn(),
      exportCategoriesBudgetsCsv: vi.fn(),
      exportCategoriesBudgetsJson: vi.fn(),
      exportAuditLogCsv: vi.fn(),
    },
  };
});

import { GodzillaApi } from "../api/client";
import { downloadBlob } from "../utils/download";

const TOKEN = "tok";

const mockGetSettings = vi.mocked(GodzillaApi.getSettings);
const mockExportTransactions = vi.mocked(GodzillaApi.exportTransactions);
const mockExportCategoriesBudgetsCsv = vi.mocked(GodzillaApi.exportCategoriesBudgetsCsv);
const mockExportCategoriesBudgetsJson = vi.mocked(GodzillaApi.exportCategoriesBudgetsJson);
const mockExportAuditLogCsv = vi.mocked(GodzillaApi.exportAuditLogCsv);
const mockDownloadBlob = vi.mocked(downloadBlob);

describe("ExportPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetSettings.mockResolvedValue({
      timezone: "UTC",
      currency: "USD",
      retention: { retain_raw_payloads: true, retain_logs_days: 90 },
      export_defaults: { include_raw_payloads: true },
      security: { auto_lock_minutes: 15 },
      sync: {
        schedule_enabled: false,
        frequency_minutes: 360,
        scheduler_supported: false,
      },
    });
    mockExportTransactions.mockResolvedValue({
      blob: new Blob(["csv"], { type: "text/csv" }),
      filename: "transactions-export.csv",
      contentType: "text/csv",
    });
    mockExportCategoriesBudgetsCsv.mockResolvedValue({
      blob: new Blob(["csv"], { type: "text/csv" }),
      filename: "categories-budgets-export.csv",
      contentType: "text/csv",
    });
    mockExportCategoriesBudgetsJson.mockResolvedValue({
      categories: [],
      budgets: [],
    });
    mockExportAuditLogCsv.mockResolvedValue({
      blob: new Blob(["csv"], { type: "text/csv" }),
      filename: "audit-log-export.csv",
      contentType: "text/csv",
    });
  });

  it("uses settings default and exports filtered transactions  REQ: FUNC-EXP-001, FUNC-EXP-003", async () => {
    render(
      <ExportPanel
        token={TOKEN}
        refreshKey={0}
        filters={{ merchant: "Cafe", amount_min: 10 }}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("export-include-raw-toggle")).toBeChecked();
    });

    fireEvent.click(screen.getByTestId("export-transactions-btn"));

    await waitFor(() => {
      expect(mockExportTransactions).toHaveBeenCalledWith(TOKEN, {
        merchant: "Cafe",
        amount_min: 10,
        include_raw_payloads: true,
      });
      expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), "transactions-export.csv");
    });
  });

  it("exports categories/budgets json  REQ: FUNC-EXP-002", async () => {
    render(<ExportPanel token={TOKEN} refreshKey={0} filters={{}} />);

    await waitFor(() => {
      expect(mockGetSettings).toHaveBeenCalled();
    });

    fireEvent.change(screen.getByTestId("export-categories-format"), {
      target: { value: "json" },
    });
    fireEvent.change(screen.getByTestId("export-categories-month"), {
      target: { value: "2026-01" },
    });
    fireEvent.click(screen.getByTestId("export-categories-budgets-btn"));

    await waitFor(() => {
      expect(mockExportCategoriesBudgetsJson).toHaveBeenCalledWith(TOKEN, { month: "2026-01" });
      expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), "categories-budgets-export.json");
    });
  });

  it("exports audit csv with filters  REQ: FUNC-AUD-004", async () => {
    render(<ExportPanel token={TOKEN} refreshKey={0} filters={{}} />);

    await waitFor(() => {
      expect(mockGetSettings).toHaveBeenCalled();
    });

    fireEvent.change(screen.getByTestId("export-audit-event-type"), {
      target: { value: "settings_updated" },
    });
    fireEvent.change(screen.getByTestId("export-audit-start"), {
      target: { value: "2026-02-01" },
    });
    fireEvent.change(screen.getByTestId("export-audit-end"), {
      target: { value: "2026-02-15" },
    });
    fireEvent.change(screen.getByTestId("export-audit-limit"), {
      target: { value: "150" },
    });

    fireEvent.click(screen.getByTestId("export-audit-btn"));

    await waitFor(() => {
      expect(mockExportAuditLogCsv).toHaveBeenCalledWith(TOKEN, {
        event_type: "settings_updated",
        start: "2026-02-01",
        end: "2026-02-15",
        limit: 150,
      });
      expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), "audit-log-export.csv");
    });
  });
});
