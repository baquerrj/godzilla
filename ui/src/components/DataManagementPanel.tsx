/**
 * DataManagementPanel: encrypted backup download, restore upload, and wipe.
 *
 * REQ: FUNC-BKP-001, FUNC-BKP-002, FUNC-BKP-003, FUNC-BKP-004
 */

import { type FormEvent, useState } from "react";
import { GodzillaApi, useApiCall } from "../api/client";
import { downloadBlob } from "../utils/download";

interface Props {
  token: string;
  onDataChanged: () => void;
}

export function DataManagementPanel({ token, onDataChanged }: Props) {
  const [backupPassphrase, setBackupPassphrase] = useState("");
  const [includeSecrets, setIncludeSecrets] = useState(true);

  const [restorePassphrase, setRestorePassphrase] = useState("");
  const [restoreFile, setRestoreFile] = useState<File | null>(null);

  const [wipeConfirm, setWipeConfirm] = useState("");

  const [actionResult, executeAction] = useApiCall<string>();

  const handleBackup = () => {
    void executeAction(async () => {
      const result = await GodzillaApi.createBackup(token, {
        passphrase: backupPassphrase,
        include_secrets: includeSecrets,
      });
      downloadBlob(result.blob, result.filename ?? "godzilla-backup.gzbk");
      return "Backup downloaded.";
    });
  };

  const handleRestore = (event: FormEvent) => {
    event.preventDefault();
    if (!restoreFile) return;
    void executeAction(async () => {
      const result = await GodzillaApi.restoreBackup(token, {
        passphrase: restorePassphrase,
        file: restoreFile,
      });
      onDataChanged();
      setRestoreFile(null);
      return `Restore complete (schema v${result.schema_version}).`;
    });
  };

  const handleWipe = () => {
    void executeAction(async () => {
      const result = await GodzillaApi.wipeData(token, { confirm: "WIPE_LOCAL_DATA" });
      onDataChanged();
      setWipeConfirm("");
      return `Wipe complete. Deleted ${result.deleted_files.length} file(s).`;
    });
  };

  return (
    <section className="panel" data-testid="data-management-panel">
      <div className="panel-header">
        <h2>Data Management</h2>
      </div>
      <p className="muted" data-testid="data-management-help-text">
        Backups are passphrase-encrypted. Restore replaces local DB files atomically.
      </p>

      <div className="m5-section">
        <h3>Backup</h3>
        <div className="m5-grid">
          <label>
            Passphrase
            <input
              type="password"
              value={backupPassphrase}
              onChange={(event) => setBackupPassphrase(event.target.value)}
              data-testid="backup-passphrase-input"
            />
          </label>
        </div>
        <label className="m5-inline-toggle">
          <input
            type="checkbox"
            checked={includeSecrets}
            onChange={(event) => setIncludeSecrets(event.target.checked)}
            data-testid="backup-include-secrets-toggle"
          />
          Include secrets store
        </label>
        <button
          className="btn btn-sm"
          onClick={handleBackup}
          disabled={!backupPassphrase || actionResult.status === "loading"}
          data-testid="backup-download-btn"
        >
          Download Encrypted Backup
        </button>
      </div>

      <div className="m5-section">
        <h3>Restore</h3>
        <form onSubmit={handleRestore} className="m5-grid">
          <label>
            Passphrase
            <input
              type="password"
              value={restorePassphrase}
              onChange={(event) => setRestorePassphrase(event.target.value)}
              data-testid="restore-passphrase-input"
            />
          </label>
          <label>
            Backup file
            <input
              type="file"
              accept=".gzbk,application/octet-stream"
              onChange={(event) => setRestoreFile(event.target.files?.[0] ?? null)}
              data-testid="restore-file-input"
            />
          </label>
          <button
            type="submit"
            className="btn btn-sm"
            disabled={!restorePassphrase || !restoreFile || actionResult.status === "loading"}
            data-testid="restore-submit-btn"
          >
            Restore Backup
          </button>
        </form>
      </div>

      <div className="m5-section panel-warning">
        <h3>Wipe</h3>
        <p className="muted">Type <code>WIPE_LOCAL_DATA</code> to enable wipe.</p>
        <div className="m5-grid">
          <label>
            Confirmation
            <input
              type="text"
              value={wipeConfirm}
              onChange={(event) => setWipeConfirm(event.target.value)}
              data-testid="wipe-confirm-input"
            />
          </label>
        </div>
        <button
          className="btn btn-sm btn-danger"
          onClick={handleWipe}
          disabled={wipeConfirm !== "WIPE_LOCAL_DATA" || actionResult.status === "loading"}
          data-testid="wipe-submit-btn"
        >
          Wipe Local Data
        </button>
      </div>

      {actionResult.status === "error" && (
        <p className="error-text">Operation failed: {actionResult.message}</p>
      )}
      {actionResult.status === "success" && (
        <p className="alert alert-success">{actionResult.data}</p>
      )}
    </section>
  );
}
