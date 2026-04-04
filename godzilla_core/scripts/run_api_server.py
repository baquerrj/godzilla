"""Run the local FastAPI sidecar for UI integration.

REQ: TECH-SEC-NET-001, TECH-SEC-NET-002
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from godzilla_core.db.migrations import main as run_migrations

_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}


def main() -> int:
    """Run the API server on a loopback address only.

    REQ: TECH-SEC-NET-001, TECH-SEC-NET-002
    """
    parser = argparse.ArgumentParser(description="Run the Godzilla API sidecar")
    parser.add_argument("--host", default="127.0.0.1", help="Loopback host address")
    parser.add_argument("--port", type=int, default=8787, help="Loopback port")
    parser.add_argument(
        "--tls-cert",
        default=None,
        help="Path to TLS certificate (PEM). Falls back to GODZILLA_TLS_CERT.",
    )
    parser.add_argument(
        "--tls-key",
        default=None,
        help="Path to TLS private key (PEM). Falls back to GODZILLA_TLS_KEY.",
    )
    parser.add_argument(
        "--migrations",
        action="store_true",
        default=False,
        help="Run database migrations before starting the server",
    )

    args = parser.parse_args()

    if args.host not in _ALLOWED_HOSTS:
        raise SystemExit("Host must be a loopback address")

    if args.migrations:
        print("Running database migrations...")
        try:
            run_migrations()
        except Exception as e:
            raise SystemExit(f"Database migration failed: {e}") from e

    tls_cert = args.tls_cert or os.environ.get("GODZILLA_TLS_CERT")
    tls_key = args.tls_key or os.environ.get("GODZILLA_TLS_KEY")
    if bool(tls_cert) != bool(tls_key):
        raise SystemExit("Both TLS cert and key must be set together")

    ssl_certfile: str | None = None
    ssl_keyfile: str | None = None
    if tls_cert and tls_key:
        cert_path = Path(os.path.expandvars(tls_cert)).expanduser()
        key_path = Path(os.path.expandvars(tls_key)).expanduser()
        if not cert_path.exists():
            raise SystemExit(f"TLS cert file not found: {cert_path}")
        if not key_path.exists():
            raise SystemExit(f"TLS key file not found: {key_path}")
        ssl_certfile = str(cert_path)
        ssl_keyfile = str(key_path)

    uvicorn.run(
        "godzilla_core.api.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
