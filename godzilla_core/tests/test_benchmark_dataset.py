"""Benchmark dataset generator tests.

REQ: ACC-UX-001, ACC-UX-002, ACC-UX-003, ACC-UX-004
"""

from __future__ import annotations

import tempfile
import unittest

from sqlcipher3 import dbapi2 as sqlcipher

from godzilla_core.fixtures.benchmark_dataset import (
    REFERENCE_ACCOUNT_COUNT,
    REFERENCE_TRANSACTION_COUNT,
    seed_reference_dataset,
)


class BenchmarkDatasetTests(unittest.TestCase):
    """Tests for deterministic benchmark seeding.

    REQ: ACC-UX-001, ACC-UX-002, ACC-UX-003, ACC-UX-004
    """

    def test_seed_reference_dataset_creates_expected_counts(self) -> None:
        """Seeding writes the reference dataset shape and secrets.

        REQ: ACC-UX-001, ACC-UX-002, ACC-UX-003, ACC-UX-004
        """

        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = f"{tmp_dir}/benchmark.db"
            secrets_path = f"{tmp_dir}/benchmark-secrets.db"
            summary = seed_reference_dataset(
                db_path=db_path,
                db_key="db-key",
                secrets_path=secrets_path,
                secrets_key="secrets-key",
            )
            self.assertEqual(summary.accounts, REFERENCE_ACCOUNT_COUNT)
            self.assertEqual(summary.transactions, REFERENCE_TRANSACTION_COUNT)

            conn = sqlcipher.connect(db_path)
            conn.execute("PRAGMA key = 'db-key';")
            account_count = conn.execute("SELECT COUNT(*) FROM account").fetchone()[0]
            transaction_count = conn.execute("SELECT COUNT(*) FROM transaction_record").fetchone()[
                0
            ]
            conflict_count = conn.execute("SELECT COUNT(*) FROM conflict").fetchone()[0]
            owner_payload = conn.execute(
                "SELECT owner_names FROM account WHERE id = 'acc-1'"
            ).fetchone()[0]
            conn.close()

            self.assertEqual(account_count, REFERENCE_ACCOUNT_COUNT)
            self.assertEqual(transaction_count, REFERENCE_TRANSACTION_COUNT)
            self.assertEqual(conflict_count, 1)
            self.assertIn("Alex Example", owner_payload)
