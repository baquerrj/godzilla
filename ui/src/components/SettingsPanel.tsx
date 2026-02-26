/**
 * SettingsPanel: view/update persisted application settings.
 *
 * Settings are loaded by the parent (App) and passed as props to avoid
 * duplicate /settings requests alongside ExportPanel.
 *
 * REQ: FUNC-SET-001, FUNC-SET-002, FUNC-SET-003, FUNC-SET-004, FUNC-SET-005
 */

import { type FormEvent, useEffect, useState } from "react";
import { GodzillaApi, useApiCall } from "../api/client";
import type { SettingsResponse } from "../api/types";

interface Props {
  token: string;
  settings: SettingsResponse | null;
  settingsLoading: boolean;
  settingsError: string | null;
  onSaved: () => void;
}

interface SettingsFormState {
  timezone: string;
  currency: string;
  retainRawPayloads: boolean;
  retainLogsDays: string;
  includeRawPayloads: boolean;
  autoLockMinutes: string;
  syncScheduleEnabled: boolean;
  syncFrequencyMinutes: string;
  schedulerSupported: boolean;
}

const DEFAULT_FORM: SettingsFormState = {
  timezone: "UTC",
  currency: "USD",
  retainRawPayloads: true,
  retainLogsDays: "90",
  includeRawPayloads: false,
  autoLockMinutes: "15",
  syncScheduleEnabled: false,
  syncFrequencyMinutes: "360",
  schedulerSupported: false,
};

function fromSettings(settings: SettingsResponse): SettingsFormState {
  return {
    timezone: settings.timezone,
    currency: settings.currency,
    retainRawPayloads: settings.retention.retain_raw_payloads,
    retainLogsDays: String(settings.retention.retain_logs_days),
    includeRawPayloads: settings.export_defaults.include_raw_payloads,
    autoLockMinutes: String(settings.security.auto_lock_minutes),
    syncScheduleEnabled: settings.sync.schedule_enabled,
    syncFrequencyMinutes: String(settings.sync.frequency_minutes),
    schedulerSupported: settings.sync.scheduler_supported,
  };
}

export function SettingsPanel({ token, settings, settingsLoading, settingsError, onSaved }: Props) {
  const [form, setForm] = useState<SettingsFormState>(DEFAULT_FORM);
  const [localError, setLocalError] = useState<string | null>(null);

  const [saveResult, executeSave] = useApiCall<SettingsResponse>();

  // Sync form whenever settings prop changes (initial load or post-save refresh).
  useEffect(() => {
    if (settings) {
      setForm(fromSettings(settings));
    }
  }, [settings]);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    setLocalError(null);

    const retainLogsDays = Number.parseInt(form.retainLogsDays, 10);
    const autoLockMinutes = Number.parseInt(form.autoLockMinutes, 10);
    const syncFrequencyMinutes = Number.parseInt(form.syncFrequencyMinutes, 10);
    if (![retainLogsDays, autoLockMinutes, syncFrequencyMinutes].every(Number.isFinite)) {
      setLocalError("Settings values must use valid numbers.");
      return;
    }

    void executeSave(async () => {
      const updated = await GodzillaApi.updateSettings(token, {
        timezone: form.timezone,
        currency: form.currency.toUpperCase(),
        retention: {
          retain_raw_payloads: form.retainRawPayloads,
          retain_logs_days: retainLogsDays,
        },
        export_defaults: {
          include_raw_payloads: form.includeRawPayloads,
        },
        security: {
          auto_lock_minutes: autoLockMinutes,
        },
        sync: {
          schedule_enabled: form.syncScheduleEnabled,
          frequency_minutes: syncFrequencyMinutes,
        },
      });
      setForm(fromSettings(updated));
      onSaved();
      return updated;
    });
  };

  return (
    <section className="panel" data-testid="settings-panel">
      <div className="panel-header">
        <h2>Settings</h2>
      </div>
      <p className="muted" data-testid="settings-help-text">
        Auto-lock and sync schedule values persist now; runtime enforcement is planned for M6.
      </p>

      <form className="m5-grid" onSubmit={handleSubmit}>
        <label>
          Timezone (IANA)
          <input
            type="text"
            value={form.timezone}
            onChange={(event) => setForm((prev) => ({ ...prev, timezone: event.target.value }))}
            data-testid="settings-timezone-input"
          />
        </label>
        <label>
          Currency (ISO-4217)
          <input
            type="text"
            maxLength={3}
            value={form.currency}
            onChange={(event) => {
              setForm((prev) => ({
                ...prev,
                currency: event.target.value.toUpperCase(),
              }));
            }}
            data-testid="settings-currency-input"
          />
        </label>
        <label>
          Retain logs (days)
          <input
            type="number"
            min={1}
            max={3650}
            value={form.retainLogsDays}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, retainLogsDays: event.target.value }))
            }
            data-testid="settings-retain-logs-input"
          />
        </label>
        <label>
          Auto-lock (minutes)
          <input
            type="number"
            min={1}
            max={1440}
            value={form.autoLockMinutes}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, autoLockMinutes: event.target.value }))
            }
            data-testid="settings-auto-lock-input"
          />
        </label>
        <label>
          Sync frequency (minutes)
          <input
            type="number"
            min={5}
            max={10080}
            value={form.syncFrequencyMinutes}
            onChange={(event) => {
              setForm((prev) => ({ ...prev, syncFrequencyMinutes: event.target.value }));
            }}
            data-testid="settings-sync-frequency-input"
          />
        </label>
        <label className="m5-static-label" data-testid="settings-scheduler-supported">
          Scheduler support: {form.schedulerSupported ? "enabled" : "disabled"}
        </label>

        <label className="m5-inline-toggle">
          <input
            type="checkbox"
            checked={form.retainRawPayloads}
            onChange={(event) => {
              setForm((prev) => ({ ...prev, retainRawPayloads: event.target.checked }));
            }}
            data-testid="settings-retain-raw-toggle"
          />
          Retain raw provider payloads
        </label>

        <label className="m5-inline-toggle">
          <input
            type="checkbox"
            checked={form.includeRawPayloads}
            onChange={(event) => {
              setForm((prev) => ({ ...prev, includeRawPayloads: event.target.checked }));
            }}
            data-testid="settings-export-raw-toggle"
          />
          Default export includes raw payloads
        </label>

        <label className="m5-inline-toggle">
          <input
            type="checkbox"
            checked={form.syncScheduleEnabled}
            onChange={(event) => {
              setForm((prev) => ({ ...prev, syncScheduleEnabled: event.target.checked }));
            }}
            data-testid="settings-sync-schedule-toggle"
          />
          Sync schedule enabled
        </label>

        <button
          type="submit"
          className="btn btn-primary btn-sm"
          disabled={saveResult.status === "loading"}
          data-testid="settings-save-btn"
        >
          Save Settings
        </button>
      </form>

      {settingsLoading && <p className="muted">Loading settings…</p>}
      {settingsError && <p className="error-text">Failed to load settings: {settingsError}</p>}
      {localError && <p className="error-text">{localError}</p>}
      {saveResult.status === "error" && (
        <p className="error-text">Failed to save settings: {saveResult.message}</p>
      )}
      {saveResult.status === "success" && <p className="alert alert-success">Settings saved.</p>}
    </section>
  );
}
