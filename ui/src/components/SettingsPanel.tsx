/**
 * SettingsPanel: view/update persisted application settings.
 *
 * REQ: ACC-SET-001, ACC-SET-002, ACC-SET-003, ACC-SET-004, ACC-SET-005,
 * REQ: ACC-ACCT-006, ACC-BKP-005, TECH-ACCT-006-CONFIG
 */

import { type FormEvent, useEffect, useState } from "react";
import { GodzillaApi, useApiCall } from "../api/client";
import type { SettingsResponse } from "../api/types";

interface Props {
  token: string;
  refreshKey: number;
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
  syncLastRunSummary: string;
  backupScheduleEnabled: boolean;
  backupFrequencyMinutes: string;
  backupRetentionCount: string;
  backupDirectory: string;
  backupPassphraseConfigured: boolean;
  backupLastRunSummary: string;
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
  syncLastRunSummary: "No scheduled sync has run yet.",
  backupScheduleEnabled: false,
  backupFrequencyMinutes: "1440",
  backupRetentionCount: "7",
  backupDirectory: "",
  backupPassphraseConfigured: false,
  backupLastRunSummary: "No scheduled backup has run yet.",
};

function summarizeRun(
  value:
    | {
        status: string;
        finished_at_utc: string;
        summary: Record<string, unknown>;
      }
    | null
    | undefined,
): string {
  if (!value) {
    return "No scheduled run has completed yet.";
  }
  const itemTotal = value.summary.items_total;
  const prunedFiles = value.summary.pruned_files;
  if (typeof itemTotal === "number") {
    return `${value.status} at ${value.finished_at_utc} (${itemTotal} item(s))`;
  }
  if (typeof prunedFiles === "number") {
    return `${value.status} at ${value.finished_at_utc} (${prunedFiles} file(s) pruned)`;
  }
  return `${value.status} at ${value.finished_at_utc}`;
}

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
    syncLastRunSummary: summarizeRun(settings.sync.last_run),
    backupScheduleEnabled: settings.backup.schedule_enabled,
    backupFrequencyMinutes: String(settings.backup.frequency_minutes),
    backupRetentionCount: String(settings.backup.retention_count),
    backupDirectory: settings.backup.directory ?? "",
    backupPassphraseConfigured: settings.backup.scheduled_passphrase_configured,
    backupLastRunSummary: summarizeRun(settings.backup.last_run),
  };
}

export function SettingsPanel({ token, refreshKey, onSaved }: Props) {
  const [form, setForm] = useState<SettingsFormState>(DEFAULT_FORM);
  const [localError, setLocalError] = useState<string | null>(null);
  const [backupPassphrase, setBackupPassphrase] = useState("");

  const [loadResult, executeLoad] = useApiCall<SettingsResponse>();
  const [saveResult, executeSave] = useApiCall<SettingsResponse>();
  const [passphraseResult, executePassphraseAction] = useApiCall<string>();

  useEffect(() => {
    void executeLoad(() => GodzillaApi.getSettings(token));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, refreshKey]);

  useEffect(() => {
    if (loadResult.status === "success") {
      setForm(fromSettings(loadResult.data));
    }
  }, [loadResult]);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    setLocalError(null);

    const retainLogsDays = Number.parseInt(form.retainLogsDays, 10);
    const autoLockMinutes = Number.parseInt(form.autoLockMinutes, 10);
    const syncFrequencyMinutes = Number.parseInt(form.syncFrequencyMinutes, 10);
    const backupFrequencyMinutes = Number.parseInt(form.backupFrequencyMinutes, 10);
    const backupRetentionCount = Number.parseInt(form.backupRetentionCount, 10);
    if (
      ![
        retainLogsDays,
        autoLockMinutes,
        syncFrequencyMinutes,
        backupFrequencyMinutes,
        backupRetentionCount,
      ].every(Number.isFinite)
    ) {
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
        backup: {
          schedule_enabled: form.backupScheduleEnabled,
          frequency_minutes: backupFrequencyMinutes,
          retention_count: backupRetentionCount,
          directory: form.backupDirectory.trim() || null,
        },
      });
      setForm(fromSettings(updated));
      onSaved();
      return updated;
    });
  };

  const handleSaveBackupPassphrase = () => {
    void executePassphraseAction(async () => {
      await GodzillaApi.setScheduledBackupPassphrase(token, backupPassphrase);
      setBackupPassphrase("");
      setForm((current) => ({ ...current, backupPassphraseConfigured: true }));
      return "Scheduled backup passphrase saved.";
    });
  };

  const handleClearBackupPassphrase = () => {
    void executePassphraseAction(async () => {
      await GodzillaApi.clearScheduledBackupPassphrase(token);
      setBackupPassphrase("");
      setForm((current) => ({ ...current, backupPassphraseConfigured: false }));
      return "Scheduled backup passphrase cleared.";
    });
  };

  return (
    <section className="panel" data-testid="settings-panel">
      <div className="panel-header">
        <h2>Settings</h2>
      </div>
      <p className="muted" data-testid="settings-help-text">
        Scheduler-backed sync and backup settings persist and now drive the local runtime.
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
            onChange={(event) => setForm((prev) => ({ ...prev, retainLogsDays: event.target.value }))}
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
            onChange={(event) => setForm((prev) => ({ ...prev, autoLockMinutes: event.target.value }))}
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
        <label>
          Backup frequency (minutes)
          <input
            type="number"
            min={5}
            max={10080}
            value={form.backupFrequencyMinutes}
            onChange={(event) => {
              setForm((prev) => ({ ...prev, backupFrequencyMinutes: event.target.value }));
            }}
            data-testid="settings-backup-frequency-input"
          />
        </label>
        <label>
          Backup retention count
          <input
            type="number"
            min={1}
            max={365}
            value={form.backupRetentionCount}
            onChange={(event) => {
              setForm((prev) => ({ ...prev, backupRetentionCount: event.target.value }));
            }}
            data-testid="settings-backup-retention-input"
          />
        </label>
        <label>
          Backup directory
          <input
            type="text"
            value={form.backupDirectory}
            onChange={(event) => {
              setForm((prev) => ({ ...prev, backupDirectory: event.target.value }));
            }}
            data-testid="settings-backup-directory-input"
          />
        </label>
        <label className="m5-static-label" data-testid="settings-scheduler-supported">
          Scheduler support: {form.schedulerSupported ? "enabled" : "disabled"}
        </label>
        <label className="m5-static-label" data-testid="settings-sync-last-run">
          Scheduled sync: {form.syncLastRunSummary}
        </label>
        <label className="m5-static-label" data-testid="settings-backup-passphrase-status">
          Scheduled backup passphrase: {form.backupPassphraseConfigured ? "configured" : "missing"}
        </label>
        <label className="m5-static-label" data-testid="settings-backup-last-run">
          Scheduled backup: {form.backupLastRunSummary}
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

        <label className="m5-inline-toggle">
          <input
            type="checkbox"
            checked={form.backupScheduleEnabled}
            onChange={(event) => {
              setForm((prev) => ({ ...prev, backupScheduleEnabled: event.target.checked }));
            }}
            data-testid="settings-backup-schedule-toggle"
          />
          Backup schedule enabled
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

      <div className="m5-section">
        <h3>Scheduled Backup Passphrase</h3>
        <div className="m5-grid">
          <label>
            Passphrase
            <input
              type="password"
              value={backupPassphrase}
              onChange={(event) => setBackupPassphrase(event.target.value)}
              data-testid="settings-backup-passphrase-input"
            />
          </label>
        </div>
        <div className="panel-actions">
          <button
            type="button"
            className="btn btn-sm"
            disabled={!backupPassphrase || passphraseResult.status === "loading"}
            onClick={handleSaveBackupPassphrase}
            data-testid="settings-backup-passphrase-save-btn"
          >
            Save Scheduled Backup Passphrase
          </button>
          <button
            type="button"
            className="btn btn-sm"
            disabled={!form.backupPassphraseConfigured || passphraseResult.status === "loading"}
            onClick={handleClearBackupPassphrase}
            data-testid="settings-backup-passphrase-clear-btn"
          >
            Clear Scheduled Backup Passphrase
          </button>
        </div>
      </div>

      {loadResult.status === "loading" && <p className="muted">Loading settings…</p>}
      {loadResult.status === "error" && (
        <p className="error-text">Failed to load settings: {loadResult.message}</p>
      )}
      {localError && <p className="error-text">{localError}</p>}
      {saveResult.status === "error" && (
        <p className="error-text">Failed to save settings: {saveResult.message}</p>
      )}
      {saveResult.status === "success" && <p className="alert alert-success">Settings saved.</p>}
      {passphraseResult.status === "error" && (
        <p className="error-text">Passphrase update failed: {passphraseResult.message}</p>
      )}
      {passphraseResult.status === "success" && (
        <p className="alert alert-success">{passphraseResult.data}</p>
      )}
    </section>
  );
}
