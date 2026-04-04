"""Encrypted secrets store backed by SQLCipher.

REQ: TECH-SEC-CRY-002, TECH-SYS-004
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from sqlcipher3 import dbapi2 as sqlcipher

from godzilla_core.util.time import local_timestamp_metadata


class SecretStoreError(RuntimeError):
    """Raised when environment-based secret store configuration is invalid.

    REQ: TECH-SEC-CRY-002
    """

    pass


def _escape_key(db_key: str) -> str:
    """Escape a SQLCipher key for use in PRAGMA statements.

    REQ: TECH-SEC-CRY-002

    Args:
        db_key: Raw encryption key string.

    Returns:
        Escaped key string.
    """
    return db_key.replace("'", "''")


def _expand_path(path_value: str) -> Path:
    """Expand environment variables and user-home references in a path.

    REQ: TECH-SYS-004

    Args:
        path_value: Raw configured path value.

    Returns:
        Expanded filesystem path.
    """
    expanded = os.path.expandvars(path_value)
    return Path(expanded).expanduser()


def _connect(db_path: Path, db_key: str) -> sqlcipher.Connection:
    """Create an encrypted SQLCipher connection for the secrets database.

    REQ: TECH-SEC-CRY-002

    Args:
        db_path: Path to the secrets database file.
        db_key: Encryption key.

    Returns:
        Open SQLCipher connection.
    """
    conn = sqlcipher.connect(str(db_path))
    escaped_key = _escape_key(db_key)
    conn.execute(f"PRAGMA key = '{escaped_key}';")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


class SecretStore:
    """Encrypted key-value store backed by SQLCipher.

    REQ: TECH-SEC-CRY-002, TECH-SYS-004
    """

    def __init__(self, db_path: str, db_key: str) -> None:
        """Initialize the secret store and ensure schema exists.

        REQ: TECH-SEC-CRY-002, TECH-SYS-004
        """
        if not db_path:
            raise ValueError("db_path is required")
        if not db_key:
            raise ValueError("db_key is required")

        self._db_path = _expand_path(db_path)
        self._db_key = db_key
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Create and migrate the secrets table schema.

        REQ: TECH-SEC-CRY-002
        """
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
        """Persist a secret value for the given key.

        REQ: TECH-SEC-CRY-002
        """
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
        """Fetch a secret value by key.

        REQ: TECH-SEC-CRY-002
        """
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
        """Delete a secret by key.

        REQ: TECH-SEC-CRY-002
        """
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

    REQ: TECH-SEC-CRY-002
    """
    db_path = os.environ.get("GODZILLA_SECRETS_PATH")
    db_key = os.environ.get("GODZILLA_SECRETS_KEY")
    if not db_path or not db_key:
        raise SecretStoreError("GODZILLA_SECRETS_PATH and GODZILLA_SECRETS_KEY are required")
    return SecretStore(db_path=db_path, db_key=db_key)
