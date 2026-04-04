/**
 * Tests for SettingsPanel component.
 *
 * REQ: ACC-SET-001, ACC-SET-002, ACC-SET-003, ACC-SET-004, ACC-SET-005,
 * REQ: ACC-ACCT-006, TECH-ACCT-006-CONFIG
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { SettingsPanel } from "../components/SettingsPanel";

vi.mock("../api/client", async () => {
  const actual =
    await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    GodzillaApi: {
      getSettings: vi.fn(),
      updateSettings: vi.fn(),
      setScheduledBackupPassphrase: vi.fn(),
      clearScheduledBackupPassphrase: vi.fn(),
    },
  };
});

import { GodzillaApi } from "../api/client";

const TOKEN = "tok";
const mockGetSettings = vi.mocked(GodzillaApi.getSettings);
const mockUpdateSettings = vi.mocked(GodzillaApi.updateSettings);
const mockSetScheduledBackupPassphrase = vi.mocked(GodzillaApi.setScheduledBackupPassphrase);
const mockClearScheduledBackupPassphrase = vi.mocked(GodzillaApi.clearScheduledBackupPassphrase);

describe("SettingsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetSettings.mockResolvedValue({
      timezone: "America/Los_Angeles",
      currency: "CAD",
      retention: { retain_raw_payloads: true, retain_logs_days: 180 },
      export_defaults: { include_raw_payloads: true },
      security: { auto_lock_minutes: 45 },
      sync: {
        schedule_enabled: true,
        frequency_minutes: 720,
        scheduler_supported: true,
        last_run: null,
      },
      backup: {
        schedule_enabled: false,
        frequency_minutes: 1440,
        retention_count: 7,
        directory: null,
        scheduler_supported: true,
        scheduled_passphrase_configured: false,
        last_run: null,
      },
    });
    mockUpdateSettings.mockResolvedValue({
      timezone: "America/New_York",
      currency: "EUR",
      retention: { retain_raw_payloads: false, retain_logs_days: 30 },
      export_defaults: { include_raw_payloads: true },
      security: { auto_lock_minutes: 20 },
      sync: {
        schedule_enabled: true,
        frequency_minutes: 120,
        scheduler_supported: true,
        last_run: null,
      },
      backup: {
        schedule_enabled: true,
        frequency_minutes: 720,
        retention_count: 5,
        directory: "/tmp/backups",
        scheduler_supported: true,
        scheduled_passphrase_configured: true,
        last_run: null,
      },
    });
    mockSetScheduledBackupPassphrase.mockResolvedValue({ scheduled_passphrase_configured: true });
    mockClearScheduledBackupPassphrase.mockResolvedValue({ scheduled_passphrase_configured: false });
  });

  it("loads settings values on mount  REQ: ACC-SET-001, ACC-ACCT-006, TECH-ACCT-006-CONFIG", async () => {
    render(<SettingsPanel token={TOKEN} refreshKey={0} onSaved={vi.fn()} />);

    await waitFor(() => {
      expect(mockGetSettings).toHaveBeenCalledWith(TOKEN);
      expect(screen.getByTestId("settings-help-text")).toHaveTextContent(/local runtime/i);
      expect(screen.getByTestId("settings-timezone-input")).toHaveValue("America/Los_Angeles");
      expect(screen.getByTestId("settings-currency-input")).toHaveValue("CAD");
    });
  });

  it("saves updated settings and notifies parent  REQ: ACC-SET-002, ACC-SET-005", async () => {
    const onSaved = vi.fn();
    render(<SettingsPanel token={TOKEN} refreshKey={0} onSaved={onSaved} />);

    await waitFor(() => {
      expect(screen.getByTestId("settings-timezone-input")).toHaveValue("America/Los_Angeles");
      expect(screen.getByTestId("settings-currency-input")).toHaveValue("CAD");
    });

    fireEvent.change(screen.getByTestId("settings-currency-input"), {
      target: { value: "eur" },
    });
    fireEvent.change(screen.getByTestId("settings-retain-logs-input"), {
      target: { value: "30" },
    });
    fireEvent.change(screen.getByTestId("settings-auto-lock-input"), {
      target: { value: "20" },
    });
    fireEvent.change(screen.getByTestId("settings-sync-frequency-input"), {
      target: { value: "120" },
    });
    fireEvent.change(screen.getByTestId("settings-backup-frequency-input"), {
      target: { value: "720" },
    });
    fireEvent.change(screen.getByTestId("settings-backup-retention-input"), {
      target: { value: "5" },
    });
    fireEvent.change(screen.getByTestId("settings-backup-directory-input"), {
      target: { value: "/tmp/backups" },
    });

    fireEvent.click(screen.getByTestId("settings-retain-raw-toggle"));
    fireEvent.click(screen.getByTestId("settings-export-raw-toggle"));
    fireEvent.click(screen.getByTestId("settings-sync-schedule-toggle"));
    fireEvent.click(screen.getByTestId("settings-backup-schedule-toggle"));

    fireEvent.click(screen.getByTestId("settings-save-btn"));

    await waitFor(() => {
      expect(mockUpdateSettings).toHaveBeenCalledWith(TOKEN, expect.objectContaining({
        timezone: "America/Los_Angeles",
        currency: "EUR",
        retention: {
          retain_raw_payloads: false,
          retain_logs_days: 30,
        },
        export_defaults: {
          include_raw_payloads: false,
        },
        security: {
          auto_lock_minutes: 20,
        },
        sync: {
          schedule_enabled: false,
          frequency_minutes: 120,
        },
        backup: {
          schedule_enabled: true,
          frequency_minutes: 720,
          retention_count: 5,
          directory: "/tmp/backups",
        },
      }));
      expect(onSaved).toHaveBeenCalled();
    });
  });

  it("shows local validation error for invalid number fields  REQ: ACC-SET-003, ACC-SET-004", async () => {
    render(<SettingsPanel token={TOKEN} refreshKey={0} onSaved={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId("settings-retain-logs-input")).toHaveValue(180);
    });

    fireEvent.change(screen.getByTestId("settings-retain-logs-input"), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByTestId("settings-save-btn"));

    await waitFor(() => {
      expect(screen.getByText(/must use valid numbers/i)).toBeInTheDocument();
    });
  });

  it("stores and clears scheduled backup passphrase  REQ: ACC-BKP-005", async () => {
    render(<SettingsPanel token={TOKEN} refreshKey={0} onSaved={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId("settings-backup-passphrase-status")).toHaveTextContent(/missing/i);
    });

    fireEvent.change(screen.getByTestId("settings-backup-passphrase-input"), {
      target: { value: "scheduled-passphrase" },
    });
    fireEvent.click(screen.getByTestId("settings-backup-passphrase-save-btn"));

    await waitFor(() => {
      expect(mockSetScheduledBackupPassphrase).toHaveBeenCalledWith(TOKEN, "scheduled-passphrase");
      expect(screen.getByText(/scheduled backup passphrase saved/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("settings-backup-passphrase-clear-btn"));

    await waitFor(() => {
      expect(mockClearScheduledBackupPassphrase).toHaveBeenCalledWith(TOKEN);
      expect(screen.getByText(/scheduled backup passphrase cleared/i)).toBeInTheDocument();
    });
  });
});
