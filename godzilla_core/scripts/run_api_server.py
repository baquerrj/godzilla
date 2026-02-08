"""Run the local FastAPI sidecar for UI integration.

REQ: SEC-NET-002
"""

from __future__ import annotations

import argparse

import uvicorn

_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}


def main() -> int:
    """Run the API server on a loopback address only.

    REQ: SEC-NET-002
    """
    parser = argparse.ArgumentParser(description="Run the Godzilla API sidecar")
    parser.add_argument("--host", default="127.0.0.1", help="Loopback host address")
    parser.add_argument("--port", type=int, default=8787, help="Loopback port")
    args = parser.parse_args()

    if args.host not in _ALLOWED_HOSTS:
        raise SystemExit("Host must be a loopback address")

    uvicorn.run(
        "godzilla_core.api.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
