/**
 * Tests for SettingsPanel component.
 *
 * REQ: FUNC-SET-001, FUNC-SET-002, FUNC-SET-003, FUNC-SET-004, FUNC-SET-005
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
    },
  };
});

import { GodzillaApi } from "../api/client";

const TOKEN = "tok";
const mockGetSettings = vi.mocked(GodzillaApi.getSettings);
const mockUpdateSettings = vi.mocked(GodzillaApi.updateSettings);

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
        scheduler_supported: false,
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
        scheduler_supported: false,
      },
    });
  });

  it("loads settings values on mount  REQ: FUNC-SET-001", async () => {
    render(<SettingsPanel token={TOKEN} refreshKey={0} onSaved={vi.fn()} />);

    await waitFor(() => {
      expect(mockGetSettings).toHaveBeenCalledWith(TOKEN);
      expect(screen.getByTestId("settings-help-text")).toHaveTextContent(/runtime enforcement is planned for m6/i);
      expect(screen.getByTestId("settings-timezone-input")).toHaveValue("America/Los_Angeles");
      expect(screen.getByTestId("settings-currency-input")).toHaveValue("CAD");
    });
  });

  it("saves updated settings and notifies parent  REQ: FUNC-SET-002, FUNC-SET-005", async () => {
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

    fireEvent.click(screen.getByTestId("settings-retain-raw-toggle"));
    fireEvent.click(screen.getByTestId("settings-export-raw-toggle"));
    fireEvent.click(screen.getByTestId("settings-sync-schedule-toggle"));

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
      }));
      expect(onSaved).toHaveBeenCalled();
    });
  });

  it("shows local validation error for invalid number fields  REQ: FUNC-SET-003, FUNC-SET-004", async () => {
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
});
