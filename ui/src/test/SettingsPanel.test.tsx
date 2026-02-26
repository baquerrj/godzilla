/**
 * Tests for SettingsPanel component.
 *
 * Settings are provided by the parent as props; this component only
 * tests form rendering and save behaviour.
 *
 * REQ: FUNC-SET-001, FUNC-SET-002, FUNC-SET-003, FUNC-SET-004, FUNC-SET-005
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { SettingsPanel } from "../components/SettingsPanel";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    GodzillaApi: {
      updateSettings: vi.fn(),
    },
  };
});

import { GodzillaApi } from "../api/client";

const TOKEN = "tok";
const mockUpdateSettings = vi.mocked(GodzillaApi.updateSettings);

const SAMPLE_SETTINGS = {
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
};

describe("SettingsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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

  it("renders form from settings prop  REQ: FUNC-SET-001", () => {
    render(
      <SettingsPanel
        token={TOKEN}
        settings={SAMPLE_SETTINGS}
        settingsLoading={false}
        settingsError={null}
        onSaved={vi.fn()}
      />,
    );
    expect(screen.getByTestId("settings-help-text")).toHaveTextContent(
      /runtime enforcement is planned for m6/i,
    );
    expect(screen.getByTestId("settings-timezone-input")).toHaveValue("America/Los_Angeles");
    expect(screen.getByTestId("settings-currency-input")).toHaveValue("CAD");
    expect(screen.getByTestId("settings-retain-logs-input")).toHaveValue(180);
  });

  it("shows loading state when settings not yet loaded  REQ: FUNC-SET-001", () => {
    render(
      <SettingsPanel
        token={TOKEN}
        settings={null}
        settingsLoading={true}
        settingsError={null}
        onSaved={vi.fn()}
      />,
    );
    expect(screen.getByText(/loading settings/i)).toBeInTheDocument();
  });

  it("shows error when settings load fails  REQ: FUNC-SET-001", () => {
    render(
      <SettingsPanel
        token={TOKEN}
        settings={null}
        settingsLoading={false}
        settingsError="Network error"
        onSaved={vi.fn()}
      />,
    );
    expect(screen.getByText(/failed to load settings/i)).toBeInTheDocument();
  });

  it("saves updated settings and notifies parent  REQ: FUNC-SET-002, FUNC-SET-005", async () => {
    const onSaved = vi.fn();
    render(
      <SettingsPanel
        token={TOKEN}
        settings={SAMPLE_SETTINGS}
        settingsLoading={false}
        settingsError={null}
        onSaved={onSaved}
      />,
    );

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
      expect(mockUpdateSettings).toHaveBeenCalledWith(
        TOKEN,
        expect.objectContaining({
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
        }),
      );
      expect(onSaved).toHaveBeenCalled();
    });
  });

  it("shows local validation error for invalid number fields  REQ: FUNC-SET-003, FUNC-SET-004", async () => {
    render(
      <SettingsPanel
        token={TOKEN}
        settings={SAMPLE_SETTINGS}
        settingsLoading={false}
        settingsError={null}
        onSaved={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByTestId("settings-retain-logs-input"), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByTestId("settings-save-btn"));

    await waitFor(() => {
      expect(screen.getByText(/must use valid numbers/i)).toBeInTheDocument();
    });
  });
});
