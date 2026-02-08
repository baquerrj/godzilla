PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

CREATE TABLE schema_version (
  version INTEGER NOT NULL,
  applied_at_utc TEXT NOT NULL,
  applied_at_tz TEXT NOT NULL,
  applied_at_offset_minutes INTEGER NOT NULL
);

CREATE TABLE institution (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  plaid_institution_id TEXT NOT NULL UNIQUE,
  created_at_utc TEXT NOT NULL,
  created_at_tz TEXT NOT NULL,
  created_at_offset_minutes INTEGER NOT NULL
);

CREATE TABLE plaid_item (
  id TEXT PRIMARY KEY,
  provider_item_id TEXT NOT NULL UNIQUE,
  institution_id TEXT NOT NULL REFERENCES institution(id) ON DELETE CASCADE,
  access_token_ref TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('linked', 'requires_reauth', 'error')),
  last_sync_at_utc TEXT,
  last_sync_at_tz TEXT,
  last_sync_at_offset_minutes INTEGER,
  created_at_utc TEXT NOT NULL,
  created_at_tz TEXT NOT NULL,
  created_at_offset_minutes INTEGER NOT NULL
);

CREATE TABLE account (
  id TEXT PRIMARY KEY,
  item_id TEXT NOT NULL REFERENCES plaid_item(id) ON DELETE CASCADE,
  provider_account_id TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  subtype TEXT,
  mask TEXT,
  balance NUMERIC,
  currency TEXT NOT NULL,
  owner_names TEXT,
  created_at_utc TEXT NOT NULL,
  created_at_tz TEXT NOT NULL,
  created_at_offset_minutes INTEGER NOT NULL
);

CREATE TABLE category (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  parent_id TEXT REFERENCES category(id) ON DELETE SET NULL,
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE transaction_record (
  id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES account(id) ON DELETE CASCADE,
  provider_transaction_id TEXT,
  date TEXT NOT NULL,
  amount NUMERIC NOT NULL,
  currency TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending', 'posted')),
  merchant_name TEXT,
  display_name TEXT NOT NULL,
  category_id TEXT REFERENCES category(id) ON DELETE SET NULL,
  is_transfer INTEGER NOT NULL DEFAULT 0 CHECK (is_transfer IN (0, 1)),
  is_excluded INTEGER NOT NULL DEFAULT 0 CHECK (is_excluded IN (0, 1)),
  notes TEXT,
  created_at_utc TEXT NOT NULL,
  created_at_tz TEXT NOT NULL,
  created_at_offset_minutes INTEGER NOT NULL,
  updated_at_utc TEXT NOT NULL,
  updated_at_tz TEXT NOT NULL,
  updated_at_offset_minutes INTEGER NOT NULL
);

CREATE TABLE transaction_split (
  id TEXT PRIMARY KEY,
  transaction_id TEXT NOT NULL REFERENCES transaction_record(id) ON DELETE CASCADE,
  amount NUMERIC NOT NULL,
  category_id TEXT REFERENCES category(id) ON DELETE SET NULL,
  notes TEXT
);

CREATE TABLE tag (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE transaction_tag (
  transaction_id TEXT NOT NULL REFERENCES transaction_record(id) ON DELETE CASCADE,
  tag_id TEXT NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  PRIMARY KEY (transaction_id, tag_id)
);

CREATE TABLE budget (
  id TEXT PRIMARY KEY,
  month TEXT NOT NULL,
  category_id TEXT NOT NULL REFERENCES category(id) ON DELETE CASCADE,
  amount NUMERIC NOT NULL
);

CREATE TABLE balance_snapshot (
  id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES account(id) ON DELETE CASCADE,
  date TEXT NOT NULL,
  balance NUMERIC NOT NULL,
  UNIQUE (account_id, date)
);

CREATE TABLE transaction_override (
  id TEXT PRIMARY KEY,
  transaction_id TEXT NOT NULL REFERENCES transaction_record(id) ON DELETE CASCADE,
  field_name TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('provider', 'user')),
  provider_value TEXT,
  user_value TEXT,
  updated_at_utc TEXT NOT NULL,
  updated_at_tz TEXT NOT NULL,
  updated_at_offset_minutes INTEGER NOT NULL,
  UNIQUE (transaction_id, field_name)
);

CREATE TABLE provider_raw (
  id TEXT PRIMARY KEY,
  transaction_id TEXT NOT NULL REFERENCES transaction_record(id) ON DELETE CASCADE,
  raw_payload TEXT NOT NULL,
  created_at_utc TEXT NOT NULL,
  created_at_tz TEXT NOT NULL,
  created_at_offset_minutes INTEGER NOT NULL
);

CREATE TABLE conflict (
  conflict_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL CHECK (entity_type IN ('transaction', 'account', 'category', 'budget', 'settings')),
  entity_id TEXT NOT NULL,
  field_name TEXT NOT NULL,
  local_value TEXT NOT NULL,
  provider_value TEXT NOT NULL,
  local_updated_at_utc TEXT NOT NULL,
  local_updated_at_tz TEXT NOT NULL,
  local_updated_at_offset_minutes INTEGER NOT NULL,
  provider_updated_at_utc TEXT NOT NULL,
  provider_updated_at_tz TEXT NOT NULL,
  provider_updated_at_offset_minutes INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('open', 'resolved')),
  resolution_choice TEXT CHECK (resolution_choice IN ('local', 'provider')),
  resolved_at_utc TEXT,
  resolved_at_tz TEXT,
  resolved_at_offset_minutes INTEGER,
  sync_cursor_or_event_id TEXT
);

CREATE TABLE conflict_resolution (
  id TEXT PRIMARY KEY,
  conflict_id TEXT NOT NULL REFERENCES conflict(conflict_id) ON DELETE CASCADE,
  resolved_by TEXT NOT NULL,
  resolved_at_utc TEXT NOT NULL,
  resolved_at_tz TEXT NOT NULL,
  resolved_at_offset_minutes INTEGER NOT NULL,
  choice TEXT NOT NULL CHECK (choice IN ('local', 'provider'))
);

CREATE TABLE audit_log (
  id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  timestamp_utc TEXT NOT NULL,
  timestamp_tz TEXT NOT NULL,
  timestamp_offset_minutes INTEGER NOT NULL,
  redacted_payload TEXT NOT NULL
);

CREATE TABLE settings (
  id TEXT PRIMARY KEY,
  timezone TEXT NOT NULL,
  currency TEXT NOT NULL,
  created_at_utc TEXT NOT NULL,
  created_at_tz TEXT NOT NULL,
  created_at_offset_minutes INTEGER NOT NULL,
  updated_at_utc TEXT NOT NULL,
  updated_at_tz TEXT NOT NULL,
  updated_at_offset_minutes INTEGER NOT NULL
);

CREATE TABLE retention_policy (
  id TEXT PRIMARY KEY,
  retain_raw_payloads INTEGER NOT NULL DEFAULT 1 CHECK (retain_raw_payloads IN (0, 1)),
  retain_logs_days INTEGER NOT NULL,
  created_at_utc TEXT NOT NULL,
  created_at_tz TEXT NOT NULL,
  created_at_offset_minutes INTEGER NOT NULL,
  updated_at_utc TEXT NOT NULL,
  updated_at_tz TEXT NOT NULL,
  updated_at_offset_minutes INTEGER NOT NULL
);

CREATE TABLE export_defaults (
  id TEXT PRIMARY KEY,
  include_raw_payloads INTEGER NOT NULL DEFAULT 0 CHECK (include_raw_payloads IN (0, 1)),
  created_at_utc TEXT NOT NULL,
  created_at_tz TEXT NOT NULL,
  created_at_offset_minutes INTEGER NOT NULL,
  updated_at_utc TEXT NOT NULL,
  updated_at_tz TEXT NOT NULL,
  updated_at_offset_minutes INTEGER NOT NULL
);

CREATE TABLE pin_config (
  id TEXT PRIMARY KEY,
  pin_hash TEXT NOT NULL,
  pin_salt TEXT NOT NULL,
  updated_at_utc TEXT NOT NULL,
  updated_at_tz TEXT NOT NULL,
  updated_at_offset_minutes INTEGER NOT NULL
);

CREATE TABLE sync_state (
  id TEXT PRIMARY KEY,
  item_id TEXT NOT NULL REFERENCES plaid_item(id) ON DELETE CASCADE,
  plaid_cursor TEXT,
  last_sync_at_utc TEXT,
  last_sync_at_tz TEXT,
  last_sync_at_offset_minutes INTEGER,
  last_sync_status TEXT
);

CREATE INDEX idx_transaction_date ON transaction_record(date);
CREATE INDEX idx_transaction_amount ON transaction_record(amount);
CREATE INDEX idx_transaction_category ON transaction_record(category_id);
CREATE INDEX idx_transaction_account ON transaction_record(account_id);
CREATE INDEX idx_conflict_status ON conflict(status);
CREATE INDEX idx_budget_month_category ON budget(month, category_id);
CREATE UNIQUE INDEX idx_account_provider_id ON account(provider_account_id);
CREATE UNIQUE INDEX idx_sync_state_item_id ON sync_state(item_id);

CREATE UNIQUE INDEX idx_transaction_provider_id
  ON transaction_record(provider_transaction_id)
  WHERE provider_transaction_id IS NOT NULL;

COMMIT;
