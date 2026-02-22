#!/usr/bin/env bash
# gen-cert.sh — Generate a per-install self-signed TLS certificate for the
# Godzilla local API sidecar (127.0.0.1:8787).
#
# The generated key/cert are placed in ~/.config/godzilla/tls/ (Linux/macOS)
# or %APPDATA%\godzilla\tls\ (Windows via Git Bash).  They are intentionally
# NOT committed to source control (.gitignore excludes *.pem).
#
# Usage:
#   bash ui/scripts/gen-cert.sh
#
# The cert is valid for 3650 days and covers:
#   - DNS: localhost
#   - IP: 127.0.0.1, ::1
#
# Full integration (configuring uvicorn to use this cert and instructing the
# Tauri WebView to trust it) is completed in M6 (tasks 22).  This script only
# produces the key material so it can be committed alongside the app without
# storing secrets.

set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve output directory
# ---------------------------------------------------------------------------
if [[ "${XDG_CONFIG_HOME:-}" != "" ]]; then
    CONFIG_DIR="${XDG_CONFIG_HOME}/godzilla/tls"
elif [[ "$(uname -s)" == "Darwin" ]]; then
    CONFIG_DIR="${HOME}/Library/Application Support/com.godzilla.budget/tls"
else
    CONFIG_DIR="${HOME}/.config/godzilla/tls"
fi

mkdir -p "${CONFIG_DIR}"

KEY="${CONFIG_DIR}/api-server.key"
CERT="${CONFIG_DIR}/api-server.crt"
CSR="${CONFIG_DIR}/api-server.csr"
EXT="${CONFIG_DIR}/san.ext"

# ---------------------------------------------------------------------------
# Bail out if cert already exists and is still valid (> 30 days remaining)
# ---------------------------------------------------------------------------
if [[ -f "${CERT}" ]]; then
    EXPIRY=$(openssl x509 -enddate -noout -in "${CERT}" 2>/dev/null | cut -d= -f2)
    if openssl x509 -checkend $((30 * 86400)) -noout -in "${CERT}" &>/dev/null; then
        echo "Existing cert is valid until ${EXPIRY} — skipping generation."
        echo "CERT=${CERT}"
        echo "KEY=${KEY}"
        exit 0
    fi
    echo "Existing cert expires soon (${EXPIRY}). Regenerating..."
fi

# ---------------------------------------------------------------------------
# Write the SAN extension file
# ---------------------------------------------------------------------------
cat > "${EXT}" <<'EXT_EOF'
[req]
distinguished_name = req_distinguished_name
req_extensions     = v3_req
prompt             = no

[req_distinguished_name]
CN = Godzilla Local API

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
IP.1  = 127.0.0.1
IP.2  = ::1
EXT_EOF

# ---------------------------------------------------------------------------
# Generate key + self-signed cert
# ---------------------------------------------------------------------------
echo "Generating private key → ${KEY}"
openssl genrsa -out "${KEY}" 3072 2>/dev/null

echo "Generating self-signed certificate → ${CERT}"
openssl req \
    -new \
    -x509 \
    -key "${KEY}" \
    -out "${CERT}" \
    -days 3650 \
    -config "${EXT}" \
    -extensions v3_req \
    2>/dev/null

rm -f "${CSR}" "${EXT}"

# Restrict permissions on the private key
chmod 600 "${KEY}"

echo ""
echo "Done."
echo "  GODZILLA_TLS_CERT=${CERT}"
echo "  GODZILLA_TLS_KEY=${KEY}"
echo ""
echo "Pass these paths to the API server (M6 integration):"
echo "  GODZILLA_TLS_CERT=<path> GODZILLA_TLS_KEY=<path> godzilla-api"
