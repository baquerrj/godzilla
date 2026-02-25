BEGIN TRANSACTION;

ALTER TABLE plaid_item
  ADD COLUMN is_unlinked INTEGER NOT NULL DEFAULT 0 CHECK (is_unlinked IN (0, 1));

INSERT INTO schema_version (
  version, applied_at_utc, applied_at_tz, applied_at_offset_minutes
) VALUES (4, '2026-02-26T00:00:00', 'UTC', 0);

COMMIT;
