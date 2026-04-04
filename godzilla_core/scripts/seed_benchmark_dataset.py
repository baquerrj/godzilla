"""CLI to generate the deterministic benchmark dataset for perf verification.

REQ: ACC-UX-001, ACC-UX-002, ACC-UX-003, ACC-UX-004
"""

from __future__ import annotations

import argparse
import json

from godzilla_core.fixtures.benchmark_dataset import seed_reference_dataset


def main() -> int:
    """Seed the benchmark dataset into encrypted main/secrets databases."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--db-key", required=True)
    parser.add_argument("--secrets-path", required=True)
    parser.add_argument("--secrets-key", required=True)
    args = parser.parse_args()

    summary = seed_reference_dataset(
        db_path=args.db_path,
        db_key=args.db_key,
        secrets_path=args.secrets_path,
        secrets_key=args.secrets_key,
    )
    print(json.dumps(summary.__dict__, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
