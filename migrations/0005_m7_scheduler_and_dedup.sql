BEGIN TRANSACTION;

ALTER TABLE settings
  ADD COLUMN backup_schedule_enabled INTEGER NOT NULL DEFAULT 0 CHECK (backup_schedule_enabled IN (0, 1));
ALTER TABLE settings
  ADD COLUMN backup_frequency_minutes INTEGER NOT NULL DEFAULT 1440;
ALTER TABLE settings
  ADD COLUMN backup_retention_count INTEGER NOT NULL DEFAULT 7;
ALTER TABLE settings
  ADD COLUMN backup_directory TEXT;

ALTER TABLE transaction_record
  ADD COLUMN provider_fingerprint TEXT;

CREATE TABLE scheduled_job_run (
  job_run_id TEXT PRIMARY KEY,
  job_type TEXT NOT NULL CHECK (job_type IN ('sync', 'backup')),
  status TEXT NOT NULL CHECK (status IN ('success', 'partial', 'failed')),
  started_at_utc TEXT NOT NULL,
  started_at_tz TEXT NOT NULL,
  started_at_offset_minutes INTEGER NOT NULL,
  finished_at_utc TEXT NOT NULL,
  finished_at_tz TEXT NOT NULL,
  finished_at_offset_minutes INTEGER NOT NULL,
  summary_json TEXT NOT NULL,
  error_message TEXT
);

CREATE INDEX idx_scheduled_job_run_type_started_at
  ON scheduled_job_run (job_type, started_at_utc DESC, job_run_id DESC);

INSERT INTO schema_version (
  version, applied_at_utc, applied_at_tz, applied_at_offset_minutes
) VALUES (5, '2026-04-03T00:00:00', 'UTC', 0);

COMMIT;
