"""Scheduled sync and backup job tests.

REQ: ACC-ACCT-006, TECH-ACCT-006-RUNTIME, ACC-BKP-005
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from sqlcipher3 import dbapi2 as sqlcipher

from godzilla_core.api import app as app_module
from godzilla_core.db.migrations import run_migrations
from godzilla_core.integrations.plaid_sync import SyncError, SyncResult
from godzilla_core.security.secrets import SecretStore


class ScheduledJobTests(unittest.TestCase):
    """Integration tests for scheduled sync and backup helpers.

    REQ: ACC-ACCT-006, TECH-ACCT-006-RUNTIME, ACC-BKP-005
    """

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "app.db")
        self.secrets_path = os.path.join(self.tmp_dir.name, "secrets.db")
        self.db_key = "db-key"
        self.secrets_key = "secrets-key"
        self.old_env = {
            key: os.environ.get(key)
            for key in (
                "GODZILLA_DB_PATH",
                "GODZILLA_DB_KEY",
                "GODZILLA_SECRETS_PATH",
                "GODZILLA_SECRETS_KEY",
            )
        }
        os.environ["GODZILLA_DB_PATH"] = self.db_path
        os.environ["GODZILLA_DB_KEY"] = self.db_key
        os.environ["GODZILLA_SECRETS_PATH"] = self.secrets_path
        os.environ["GODZILLA_SECRETS_KEY"] = self.secrets_key
        run_migrations(db_path=self.db_path, db_key=self.db_key)
        self.conn = sqlcipher.connect(self.db_path)
        self.conn.execute("PRAGMA key = 'db-key';")
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.conn.execute(
            "INSERT INTO institution ("
            "id, name, plaid_institution_id, created_at_utc, created_at_tz, "
            "created_at_offset_minutes"
            ") "
            "VALUES ('inst-1', 'Bank One', 'ins-1', '2026-01-01T00:00:00', 'UTC', 0)"
        )
        self.conn.execute(
            "INSERT INTO institution ("
            "id, name, plaid_institution_id, created_at_utc, created_at_tz, "
            "created_at_offset_minutes"
            ") "
            "VALUES ('inst-2', 'Bank Two', 'ins-2', '2026-01-01T00:00:00', 'UTC', 0)"
        )
        for idx in (1, 2):
            self.conn.execute(
                "INSERT INTO plaid_item ("
                "id, provider_item_id, institution_id, access_token_ref, status, is_unlinked, "
                "last_sync_at_utc, last_sync_at_tz, last_sync_at_offset_minutes, "
                "created_at_utc, created_at_tz, created_at_offset_minutes"
                ") VALUES ("
                "?, ?, ?, ?, 'linked', 0, NULL, NULL, NULL, "
                "'2026-01-01T00:00:00', 'UTC', 0"
                ")",
                (
                    f"item-{idx}",
                    f"provider-item-{idx}",
                    f"inst-{idx}",
                    f"plaid_access_token:provider-item-{idx}",
                ),
            )
        self.conn.execute(
            "INSERT INTO settings ("
            "id, timezone, currency, auto_lock_minutes, sync_schedule_enabled, "
            "sync_frequency_minutes, backup_schedule_enabled, "
            "backup_frequency_minutes, backup_retention_count, backup_directory, "
            "created_at_utc, created_at_tz, created_at_offset_minutes, "
            "updated_at_utc, updated_at_tz, updated_at_offset_minutes"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "settings-default",
                "UTC",
                "USD",
                15,
                1,
                60,
                1,
                60,
                1,
                os.path.join(self.tmp_dir.name, "scheduled-backups"),
                "2026-01-01T00:00:00",
                "UTC",
                0,
                "2026-01-01T00:00:00",
                "UTC",
                0,
            ),
        )
        self.conn.commit()
        secret_store = SecretStore(db_path=self.secrets_path, db_key=self.secrets_key)
        secret_store.set_secret("plaid_access_token:provider-item-1", "token-1")
        secret_store.set_secret("plaid_access_token:provider-item-2", "token-2")
        secret_store.set_secret("scheduled_backup_passphrase", "scheduled-passphrase")

    def tearDown(self) -> None:
        self.conn.close()
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmp_dir.cleanup()

    def test_run_scheduled_sync_job_records_partial_status(self) -> None:
        """Per-item failures are aggregated without aborting the whole run.

        REQ: ACC-ACCT-006, TECH-ACCT-006-RUNTIME
        """

        def fake_sync(provider_item_id: str, plaid_institution_id: str | None = None) -> SyncResult:
            if provider_item_id == "provider-item-2":
                raise SyncError("boom")
            return SyncResult(
                item_id=provider_item_id,
                added=3,
                modified=1,
                removed=0,
                balance_accounts=1,
                cursor="cursor",
            )

        with patch.object(app_module, "sync_item_transactions_and_balances", side_effect=fake_sync):
            app_module._run_scheduled_sync_job()

        row = self.conn.execute(
            "SELECT status, summary_json, error_message "
            "FROM scheduled_job_run WHERE job_type = 'sync'"
        ).fetchone()
        self.assertEqual(row[0], "partial")
        self.assertIn('"items_failed": 1', row[1])
        self.assertIn("provider-item-2", row[2])

    def test_run_scheduled_backup_job_writes_and_prunes_files(self) -> None:
        """Scheduled backup writes encrypted files and prunes older ones by count.

        REQ: ACC-BKP-005
        """

        backup_dir = os.path.join(self.tmp_dir.name, "scheduled-backups")
        os.makedirs(backup_dir, exist_ok=True)
        with open(os.path.join(backup_dir, "old-1.gzbk"), "wb") as handle:
            handle.write(b"old")
        with open(os.path.join(backup_dir, "old-2.gzbk"), "wb") as handle:
            handle.write(b"old")

        app_module._run_scheduled_backup_job()

        files = sorted(name for name in os.listdir(backup_dir) if name.endswith(".gzbk"))
        self.assertEqual(len(files), 1)
        row = self.conn.execute(
            "SELECT status, summary_json FROM scheduled_job_run WHERE job_type = 'backup'"
        ).fetchone()
        self.assertEqual(row[0], "success")
        self.assertIn('"pruned_files": 2', row[1])
