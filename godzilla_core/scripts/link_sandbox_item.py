"""CLI helper to create a Plaid sandbox item and store its access token.

REQ: FUNC-ACCT-001, FUNC-ACCT-002, SEC-CRY-002, SEC-DATA-001
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from godzilla_core.integrations.plaid_client import (  # noqa: E402
    PlaidClient,
    PlaidConfig,
    link_sandbox_item,
)
from godzilla_core.security.secrets import store_from_env  # noqa: E402


def _parse_products(value: str | None) -> list[str] | None:
    """Parse a comma-separated products argument.

    REQ: FUNC-ACCT-001

    Args:
        value: Raw comma-separated product list.

    Returns:
        Normalized product names or `None` when not provided.
    """
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> int:
    """Run sandbox link flow and persist the resulting access token.

    REQ: FUNC-ACCT-001, FUNC-ACCT-002, SEC-CRY-002, SEC-DATA-001
    """
    parser = argparse.ArgumentParser(
        description="Create a Plaid sandbox item and store its access token",
    )
    parser.add_argument(
        "--institution-id",
        help="Sandbox institution ID (default from PLAID_SANDBOX_INSTITUTION_ID)",
    )
    parser.add_argument(
        "--products",
        help="Comma-separated products (default: transactions,identity)",
    )
    args = parser.parse_args()

    config = PlaidConfig.from_env()
    client = PlaidClient(config)
    secrets = store_from_env()

    result = link_sandbox_item(
        client=client,
        secret_store=secrets,
        institution_id=args.institution_id,
        products=_parse_products(args.products),
    )
    item_id = result["item_id"]
    secret_key = f"plaid_access_token:{item_id}"

    print(
        json.dumps(
            {
                "item_id": item_id,
                "secret_key": secret_key,
                "env": config.env,
                "institution_id": args.institution_id or config.sandbox_institution_id,
                "note": "access_token stored in secrets DB",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
