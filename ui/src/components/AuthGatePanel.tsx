/**
 * Authentication gate panel shown before sensitive data panels.
 *
 * REQ: TECH-SEC-ACC-001, TECH-SEC-ACC-002, TECH-SEC-ACC-003
 */

import { useEffect, useState } from "react";
import { GodzillaApi, useApiCall } from "../api/client";
import type { AuthStatus, SetupPinResponse, UnlockResponse } from "../api/types";

interface Props {
  token: string;
  onAuthenticated: (unlockToken: string | null) => void;
}

export function AuthGatePanel({ token, onAuthenticated }: Props) {
  const [statusResult, loadStatus] = useApiCall<AuthStatus>();
  const [setupResult, setupPin] = useApiCall<SetupPinResponse>();
  const [unlockResult, unlock] = useApiCall<UnlockResponse>();
  const [newPin, setNewPin] = useState("");
  const [confirmPin, setConfirmPin] = useState("");
  const [unlockPin, setUnlockPin] = useState("");

  useEffect(() => {
    loadStatus(() => GodzillaApi.getAuthStatus(token));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (statusResult.status !== "success") return;
    if (!statusResult.data.locked && !statusResult.data.setup_required) {
      onAuthenticated(null);
    }
  }, [statusResult, onAuthenticated]);

  const refreshStatus = () => {
    loadStatus(() => GodzillaApi.getAuthStatus(token));
  };

  const handleSetupPin = () => {
    if (newPin !== confirmPin) {
      return;
    }
    setupPin(async () => {
      const result = await GodzillaApi.setupPin(token, { new_pin: newPin });
      setNewPin("");
      setConfirmPin("");
      refreshStatus();
      return result;
    });
  };

  const handleUnlock = () => {
    unlock(async () => {
      const result = await GodzillaApi.unlock(token, { pin: unlockPin });
      setUnlockPin("");
      onAuthenticated(result.unlock_token);
      return result;
    });
  };

  if (statusResult.status === "loading" || statusResult.status === "idle") {
    return <div className="status-msg">Checking app lock status…</div>;
  }
  if (statusResult.status === "error") {
    return (
      <div className="status-msg status-error" data-testid="auth-gate-error">
        Failed to load auth status: {statusResult.message}
      </div>
    );
  }

  const status = statusResult.data;
  if (status.setup_required) {
    const pinsMismatch = newPin.length > 0 && confirmPin.length > 0 && newPin !== confirmPin;
    return (
      <section className="panel" data-testid="auth-setup-panel">
        <h2>Set App PIN</h2>
        <p className="muted">Create a PIN to unlock financial data panels.</p>
        <div className="form-row">
          <input
            type="password"
            inputMode="numeric"
            placeholder="New PIN"
            value={newPin}
            onChange={(event) => setNewPin(event.target.value)}
          />
          <input
            type="password"
            inputMode="numeric"
            placeholder="Confirm PIN"
            value={confirmPin}
            onChange={(event) => setConfirmPin(event.target.value)}
          />
          <button
            className="btn btn-primary"
            onClick={handleSetupPin}
            disabled={
              setupResult.status === "loading"
              || newPin.length < 4
              || confirmPin.length < 4
              || pinsMismatch
            }
            data-testid="setup-pin-btn"
          >
            {setupResult.status === "loading" ? "Saving…" : "Save PIN"}
          </button>
        </div>
        {pinsMismatch && <p className="error-text">PIN values do not match.</p>}
        {setupResult.status === "error" && (
          <p className="error-text">Setup failed: {setupResult.message}</p>
        )}
      </section>
    );
  }

  return (
    <section className="panel" data-testid="auth-unlock-panel">
      <h2>App Locked</h2>
      <p className="muted">
        Enter your PIN to unlock. Auto-lock timeout: {status.auto_lock_minutes} minute(s).
      </p>
      <div className="form-row">
        <input
          type="password"
          inputMode="numeric"
          placeholder="PIN"
          value={unlockPin}
          onChange={(event) => setUnlockPin(event.target.value)}
          data-testid="unlock-pin-input"
        />
        <button
          className="btn btn-primary"
          onClick={handleUnlock}
          disabled={unlockResult.status === "loading" || unlockPin.length < 4}
          data-testid="unlock-btn"
        >
          {unlockResult.status === "loading" ? "Unlocking…" : "Unlock"}
        </button>
      </div>
      {unlockResult.status === "error" && (
        <p className="error-text">Unlock failed: {unlockResult.message}</p>
      )}
    </section>
  );
}
