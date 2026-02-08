# Development Dependencies (Linux MVP)

This document sets up the local development environment for the MVP (Linux-first). It assumes a local-only desktop app using Tauri + React UI, a Python FastAPI sidecar, and SQLite with SQLCipher.

## 1) System dependencies (Linux)
Install Tauri’s Linux prerequisites (Debian/Ubuntu example):

```bash
sudo apt update
sudo apt install libwebkit2gtk-4.1-dev \
  build-essential \
  curl \
  wget \
  file \
  libxdo-dev \
  libssl-dev \
  libayatana-appindicator3-dev \
  librsvg2-dev
```

For other Linux distros, use the distro-specific package lists on Tauri’s prerequisites page. citeturn3view2

## 2) Rust toolchain
Install Rust via rustup:

```bash
curl --proto '=https' --tlsv1.2 https://sh.rustup.rs -sSf | sh
```

Tauri requires Rust for development. citeturn3view1

## 3) Node.js (LTS)
Tauri recommends the Node.js LTS release for JavaScript frontend frameworks. For MVP, use Node.js v24 LTS.

If you use `nvm`:

```bash
nvm install 24
nvm use 24
```

Install the LTS build from nodejs.org (or via `nvm`), then verify:

```bash
node -v
npm -v
```

citeturn3view2turn0search7

## 4) Python environment
Create and activate a virtual environment (example):

```bash
python3 -m venv venv
source venv/bin/activate
```

### Python packages
Install the core Python dependencies:

```bash
pip install "fastapi[standard]"  # includes uvicorn
pip install sqlcipher3-binary
pip install pyinstaller
```

- `fastapi[standard]` includes `uvicorn`, which we use to run the local API. citeturn1search3
- `sqlcipher3-binary` provides a self-contained SQLCipher-backed DB-API build. citeturn1search0
- PyInstaller is installed via `pip install pyinstaller`. citeturn0search1

### Environment variables (dev)
Configure local DB and secrets store paths/keys (examples):

```bash
export GODZILLA_DB_PATH="$HOME/.local/share/godzilla/godzilla.db"
export GODZILLA_DB_KEY="replace-with-strong-passphrase"
export GODZILLA_SECRETS_PATH="$HOME/.local/share/godzilla/secrets.db"
export GODZILLA_SECRETS_KEY="replace-with-strong-passphrase"
export GODZILLA_LOCAL_TZ="America/Denver"
export PLAID_CLIENT_ID="replace-with-sandbox-client-id"
export PLAID_SECRET="replace-with-sandbox-secret"
export PLAID_ENV="sandbox"
export PLAID_SANDBOX_INSTITUTION_ID="ins_109508"
```

## 5) Local HTTPS for FastAPI
Run the FastAPI server with HTTPS enabled using Uvicorn’s SSL options:

```bash
uvicorn app.main:app \
  --host 127.0.0.1 \
  --port 8443 \
  --ssl-keyfile /path/to/key.pem \
  --ssl-certfile /path/to/cert.pem
```

Uvicorn supports `--ssl-keyfile` and `--ssl-certfile` for TLS. citeturn1search1

## 6) Tauri sidecar support
The Python FastAPI binary will be bundled as a Tauri sidecar via `externalBin` in `tauri.conf.json`. citeturn0search0

## 7) Dev workflow

- Install dev tooling:
  - `python3 -m pip install -e ".[dev]"`
  - `python3 -m pip install nox`
- Lint: `nox -s lint` (or `python3 -m ruff check godzilla_core`)
- Tests: `nox -s tests` (or `python3 -m pytest`)
- Build wheel: `nox -s build` (or `python3 -m build --wheel`)
- Console scripts (after editable install):
  - `link-sandbox-item --institution-id ins_109508 --products transactions,identity`
  - `migrations` (requires `GODZILLA_DB_PATH` and `GODZILLA_DB_KEY`)
  - `sync-plaid-item --item-id <item_id> --institution-id ins_109508`

## 8) Verification checklist
- `rustc --version`
  rustc 1.93.0 (254b59607 2026-01-19)
- `node -v`
  v24.13.0
- `npm -v`
  11.6.2
- `python3 --version`
  3.12.12
- `pip show fastapi sqlcipher3-binary pyinstaller`
  Name: fastapi
  Version: 0.128.0
  Summary: FastAPI framework, high performance, easy to learn, fast to code, ready for production
  Home-page: https://github.com/fastapi/fastapi
  Author: 
  Author-email: =?utf-8?q?Sebasti=C3=A1n_Ram=C3=ADrez?= <tiangolo@gmail.com>
  License-Expression: MIT
  Location: /home/baquerrj/projects/godzilla/venv/lib/python3.12/site-packages
  Requires: annotated-doc, pydantic, starlette, typing-extensions
  Required-by: 
  
  Name: sqlcipher3-binary
  Version: 0.6.0
  Summary: DB-API 2.0 interface for SQLCipher 3.x
  Home-page: https://github.com/coleifer/sqlcipher3
  Author: Charles Leifer
  Author-email: coleifer@gmail.com
  License: MIT License
  Location: /home/baquerrj/projects/godzilla/venv/lib/python3.12/site-packages
  Requires: 
  Required-by: 
  
  Name: pyinstaller
  Version: 6.18.0
  Summary: PyInstaller bundles a Python application and all its dependencies into a single package.
  Home-page: https://pyinstaller.org
  Author: Hartmut Goebel, Giovanni Bajo, David Vierra, David Cortesi, Martin Zibricky
  Author-email: 
  License: GPLv2-or-later with a special exception which allows to use PyInstaller to build and distribute non-free programs (including commercial ones)
  Location: /home/baquerrj/projects/godzilla/venv/lib/python3.12/site-packages
  Requires: altgraph, packaging, pyinstaller-hooks-contrib, setuptools
  Required-by:
