"""Encrypted secrets store backed by SQLCipher.

REQ: SEC-CRY-002, SYS-004
"""

from __future__ import annotations

from pathlib import Path
import os
from typing import Optional

from sqlcipher3 import dbapi2 as sqlcipher

from godzilla_core.util.time import local_timestamp_metadata

class SecretStoreError(RuntimeError):
    pass


def _escape_key(db_key: str) -> str:
    return db_key.replace("'", "''")


def _expand_path(path_value: str) -> Path:
    expanded = os.path.expandvars(path_value)
    return Path(expanded).expanduser()


def _connect(db_path: Path, db_key: str) -> sqlcipher.Connection:
    conn = sqlcipher.connect(str(db_path))
    escaped_key = _escape_key(db_key)
    conn.execute(f"PRAGMA key = '{escaped_key}';")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


class SecretStore:
    def __init__(self, db_path: str, db_key: str) -> None:
        if not db_path:
            raise ValueError("db_path is required")
        if not db_key:
            raise ValueError("db_key is required")

        self._db_path = _expand_path(db_path)
        self._db_key = db_key
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        conn = _connect(self._db_path, self._db_key)
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS secrets ("
                "key TEXT PRIMARY KEY, "
                "value TEXT NOT NULL, "
                "updated_at_utc TEXT NOT NULL, "
                "updated_at_tz TEXT NOT NULL, "
                "updated_at_offset_minutes INTEGER NOT NULL"
                ")"
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(secrets)")}
            if "updated_at_utc" not in columns:
                conn.execute("ALTER TABLE secrets ADD COLUMN updated_at_utc TEXT")
                conn.execute("ALTER TABLE secrets ADD COLUMN updated_at_tz TEXT")
                conn.execute("ALTER TABLE secrets ADD COLUMN updated_at_offset_minutes INTEGER")
                if "updated_at" in columns:
                    conn.execute(
                        "UPDATE secrets SET "
                        "updated_at_utc = updated_at, "
                        "updated_at_tz = 'UTC', "
                        "updated_at_offset_minutes = 0"
                    )
            conn.commit()
        finally:
            conn.close()

    def set_secret(self, key: str, value: str) -> None:
        if not key:
            raise ValueError("key is required")
        if value is None:
            raise ValueError("value is required")

        conn = _connect(self._db_path, self._db_key)
        try:
            updated_at_utc, updated_at_tz, updated_at_offset = local_timestamp_metadata()
            conn.execute(
                "INSERT INTO secrets ("
                "key, value, updated_at_utc, updated_at_tz, updated_at_offset_minutes"
                ") "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET "
                "value=excluded.value, "
                "updated_at_utc=excluded.updated_at_utc, "
                "updated_at_tz=excluded.updated_at_tz, "
                "updated_at_offset_minutes=excluded.updated_at_offset_minutes",
                (key, value, updated_at_utc, updated_at_tz, updated_at_offset),
            )
            conn.commit()
        finally:
            conn.close()

    def get_secret(self, key: str) -> Optional[str]:
        if not key:
            raise ValueError("key is required")

        conn = _connect(self._db_path, self._db_key)
        try:
            row = conn.execute(
                "SELECT value FROM secrets WHERE key = ?",
                (key,),
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def delete_secret(self, key: str) -> None:
        if not key:
            raise ValueError("key is required")

        conn = _connect(self._db_path, self._db_key)
        try:
            conn.execute("DELETE FROM secrets WHERE key = ?", (key,))
            conn.commit()
        finally:
            conn.close()


def store_from_env() -> SecretStore:
    """Create a SecretStore from environment variables.

    REQ: SEC-CRY-002
    """
    db_path = os.environ.get("GODZILLA_SECRETS_PATH")
    db_key = os.environ.get("GODZILLA_SECRETS_KEY")
    if not db_path or not db_key:
        raise SecretStoreError("GODZILLA_SECRETS_PATH and GODZILLA_SECRETS_KEY are required")
    return SecretStore(db_path=db_path, db_key=db_key)
