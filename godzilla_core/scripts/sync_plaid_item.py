"""CLI helper to sync a Plaid item into the encrypted DB.

REQ: FUNC-ACCT-003, FUNC-SYNC-001, FUNC-SYNC-002, FUNC-SYNC-003, FUNC-REP-006
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from godzilla_core.integrations.plaid_sync import (  # noqa: E402
    sync_item_transactions_and_balances,
)


def main() -> int:
    """Run sync for one Plaid item and print a JSON summary.

    REQ: FUNC-ACCT-003, FUNC-SYNC-001, FUNC-SYNC-002, FUNC-SYNC-003, FUNC-REP-006
    """
    parser = argparse.ArgumentParser(
        description="Sync transactions and balances for a Plaid item",
    )
    parser.add_argument(
        "--item-id",
        required=True,
        help="Plaid item_id from sandbox link flow",
    )
    parser.add_argument(
        "--institution-id",
        help="Plaid institution id (ins_*)",
    )
    args = parser.parse_args()

    result = sync_item_transactions_and_balances(
        provider_item_id=args.item_id,
        plaid_institution_id=args.institution_id,
    )

    print(
        json.dumps(
            {
                "item_id": result.item_id,
                "added": result.added,
                "modified": result.modified,
                "removed": result.removed,
                "balance_accounts": result.balance_accounts,
                "cursor": result.cursor,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
