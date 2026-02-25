# User Guide (M6)

This guide documents how to run the current desktop app in development mode and
what limitations apply at this stage.

## 1. Before you run `npm run tauri dev`

Use two terminals:
- Terminal A: run the Python API sidecar.
- Terminal B: run the Tauri app (`npm run tauri dev`).

### 1.1 Required environment variables

Set these before starting the API sidecar and Tauri runtime:

```bash
# SQLCipher main database
export GODZILLA_DB_PATH="$HOME/.local/share/godzilla/godzilla.db"
export GODZILLA_DB_KEY="replace-with-strong-db-key"

# SQLCipher secrets store (PIN material, Plaid token refs, etc.)
export GODZILLA_SECRETS_PATH="$HOME/.local/share/godzilla/secrets.db"
export GODZILLA_SECRETS_KEY="replace-with-strong-secrets-key"

# API auth token (required by both API and Tauri runtime)
export GODZILLA_API_TOKEN="replace-with-local-api-token"

# Local TLS cert + key for the API sidecar
export GODZILLA_TLS_CERT="$HOME/.config/godzilla/tls/api-server.crt"
export GODZILLA_TLS_KEY="$HOME/.config/godzilla/tls/api-server.key"

# TLS pin expected by Tauri runtime
export GODZILLA_TLS_CERT_SHA256="$(openssl x509 -in "$GODZILLA_TLS_CERT" -noout -fingerprint -sha256 | cut -d= -f2 | tr -d ':')"
```

If you do not have a local cert/key yet:

```bash
bash ui/scripts/gen-cert.sh
```

### 1.2 Optional but recommended variables

```bash
# Local timestamp metadata timezone
export GODZILLA_LOCAL_TZ="America/Denver"

# Plaid config (required if you want link/sync workflows)
export PLAID_CLIENT_ID="replace-with-plaid-client-id"
export PLAID_SECRET="replace-with-plaid-secret"
export PLAID_ENV="sandbox"
export PLAID_SANDBOX_INSTITUTION_ID="ins_109508"

# Dev-only bypass for PIN gate (0 = enforce lock; 1 = bypass)
export GODZILLA_DEV_BYPASS_PIN="0"

# Optional if sidecar base URL differs from default https://127.0.0.1:8787
export GODZILLA_API_BASE="https://127.0.0.1:8787"
```

## 2. Launch sequence

### 2.1 Terminal A (API sidecar)

```bash
. venv/bin/activate
migrations
godzilla-api --host 127.0.0.1 --port 8787
```

### 2.2 Terminal B (Tauri app)

```bash
cd ui
npm install
npm run tauri dev
```

## 3. Current limitations

- Single-user only. Multi-user/shared budgets are out of scope.
- Local-only sidecar. API host is restricted to loopback addresses.
- Plaid link endpoint currently supports `PLAID_ENV=sandbox` only.
- Scheduled sync runtime is not available in the current build (`scheduler_supported` is `false`).
- Unlock sessions are in-memory; restarting the API sidecar invalidates active unlock sessions.
- Out-of-MVP features are not implemented (for example: advanced forecasting,
  receipt scanning, deep investment analytics).
