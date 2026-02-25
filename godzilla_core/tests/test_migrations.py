"""Migration runner tests.

REQ: SEC-CRY-001, SYS-004
"""

import os
import tempfile
import unittest
from pathlib import Path

from sqlcipher3 import dbapi2 as sqlcipher

from godzilla_core.db.migrations import MigrationError, _load_migrations, run_migrations


class MigrationRunnerTests(unittest.TestCase):
    """Tests for the SQLCipher migration runner.

    REQ: SEC-CRY-001, SYS-004
    """

    def setUp(self) -> None:
        """Create a temp directory for each test.

        REQ: SEC-CRY-001
        """
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test.db")
        self.db_key = "test-key"

    def tearDown(self) -> None:
        """Remove temp directory.

        REQ: SEC-CRY-001
        """
        self.tmp_dir.cleanup()

    def test_applies_initial_schema(self) -> None:
        """Verify migrations create the expected schema version and key tables.

        REQ: SEC-CRY-001, SYS-004
        """
        version = run_migrations(db_path=self.db_path, db_key=self.db_key)
        self.assertEqual(version, 4)

        conn = sqlcipher.connect(self.db_path)
        conn.execute("PRAGMA key = 'test-key';")
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }

        for expected in (
            "schema_version",
            "institution",
            "plaid_item",
            "account",
            "transaction_record",
            "category",
            "budget",
            "balance_snapshot",
            "sync_state",
            "audit_log",
        ):
            self.assertIn(expected, tables)

        columns = {r[1] for r in conn.execute("PRAGMA table_info(settings)").fetchall()}
        self.assertIn("auto_lock_minutes", columns)
        self.assertIn("sync_schedule_enabled", columns)
        self.assertIn("sync_frequency_minutes", columns)
        plaid_item_columns = {
            r[1] for r in conn.execute("PRAGMA table_info(plaid_item)").fetchall()
        }
        self.assertIn("is_unlinked", plaid_item_columns)
        conn.close()

    def test_migration_is_idempotent(self) -> None:
        """Re-running migrations does not change the schema version.

        REQ: SEC-CRY-001
        """
        v1 = run_migrations(db_path=self.db_path, db_key=self.db_key)
        v2 = run_migrations(db_path=self.db_path, db_key=self.db_key)
        self.assertEqual(v1, v2)

    def test_missing_db_path_raises(self) -> None:
        """Empty db_path raises ValueError before touching the filesystem.

        REQ: SEC-CRY-001
        """
        with self.assertRaises(ValueError):
            run_migrations(db_path="", db_key="key")

    def test_missing_db_key_raises(self) -> None:
        """Empty db_key raises ValueError before touching the filesystem.

        REQ: SEC-CRY-001
        """
        with self.assertRaises(ValueError):
            run_migrations(db_path=self.db_path, db_key="")

    def test_missing_migrations_dir_raises(self) -> None:
        """Non-existent migrations directory raises MigrationError.

        REQ: SEC-CRY-001
        """
        with self.assertRaises(MigrationError):
            run_migrations(
                db_path=self.db_path,
                db_key=self.db_key,
                migrations_dir=Path(self.tmp_dir.name) / "no_such_dir",
            )

    def test_load_migrations_invalid_filename_raises(self) -> None:
        """A migration file without a numeric prefix raises MigrationError.

        REQ: SEC-CRY-001
        """
        bad_dir = Path(self.tmp_dir.name) / "bad_migrations"
        bad_dir.mkdir()
        (bad_dir / "init.sql").write_text("SELECT 1;")
        with self.assertRaises(MigrationError):
            _load_migrations(bad_dir)

    def test_schema_version_recorded_with_timestamp_metadata(self) -> None:
        """Verify schema_version row includes UTC, timezone, and offset columns.

        REQ: SEC-CRY-001, SYS-004
        """
        os.environ["GODZILLA_LOCAL_TZ"] = "UTC"
        try:
            run_migrations(db_path=self.db_path, db_key=self.db_key)
        finally:
            os.environ.pop("GODZILLA_LOCAL_TZ", None)

        conn = sqlcipher.connect(self.db_path)
        conn.execute("PRAGMA key = 'test-key';")
        row = conn.execute(
            "SELECT version, applied_at_utc, applied_at_tz, applied_at_offset_minutes "
            "FROM schema_version WHERE version = 1"
        ).fetchone()
        conn.close()

        self.assertEqual(row[0], 1)
        self.assertIsNotNone(row[1])
        self.assertEqual(row[2], "UTC")
        self.assertEqual(row[3], 0)
