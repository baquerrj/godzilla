BEGIN TRANSACTION;

ALTER TABLE settings ADD COLUMN auto_lock_minutes INTEGER NOT NULL DEFAULT 15;
ALTER TABLE settings ADD COLUMN sync_schedule_enabled INTEGER NOT NULL DEFAULT 0 CHECK (sync_schedule_enabled IN (0, 1));
ALTER TABLE settings ADD COLUMN sync_frequency_minutes INTEGER NOT NULL DEFAULT 360;

INSERT INTO schema_version (
  version, applied_at_utc, applied_at_tz, applied_at_offset_minutes
) VALUES (3, '2026-02-25T00:00:00', 'UTC', 0);

COMMIT;
