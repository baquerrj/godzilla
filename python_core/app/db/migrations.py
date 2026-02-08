"""Migration runner for the encrypted SQLite database.

REQ: SEC-CRY-001, SYS-004
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Iterable, Optional

from sqlcipher3 import dbapi2 as sqlcipher

from app.util.time import local_timestamp_metadata

class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Migration:
    version: int
    path: Path


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "AGENTS.md").exists():
            return parent
    return current.parents[3]


def _default_migrations_dir() -> Path:
    return _repo_root() / "migrations"


def _load_migrations(migrations_dir: Path) -> list[Migration]:
    if not migrations_dir.exists():
        raise MigrationError(f"Migrations directory not found: {migrations_dir}")

    migrations: list[Migration] = []
    for path in sorted(migrations_dir.glob("*.sql")):
        version_str = path.name.split("_", 1)[0]
        if not version_str.isdigit():
            raise MigrationError(f"Invalid migration filename: {path.name}")
        migrations.append(Migration(version=int(version_str), path=path))

    migrations.sort(key=lambda m: m.version)
    return migrations


def _current_version(conn: sqlcipher.Connection) -> int:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()
    if row is None:
        return 0
    value = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    return int(value or 0)


def run_migrations(
    db_path: str,
    db_key: str,
    migrations_dir: Optional[Path] = None,
) -> int:
    """Apply pending SQL migrations and return the current schema version."""
    if not db_path:
        raise ValueError("db_path is required")
    if not db_key:
        raise ValueError("db_key is required")

    migrations_dir = migrations_dir or _default_migrations_dir()
    migrations = _load_migrations(migrations_dir)

    Path(db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    conn = sqlcipher.connect(db_path)
    try:
        # sqlcipher does not accept parameters in PRAGMA key; escape single quotes.
        escaped_key = db_key.replace("'", "''")
        conn.execute(f"PRAGMA key = '{escaped_key}';")
        conn.execute("PRAGMA foreign_keys = ON;")
        current = _current_version(conn)

        for migration in migrations:
            if migration.version <= current:
                continue
            sql = migration.path.read_text()
            conn.executescript(sql)
            if _current_version(conn) < migration.version:
                applied_at_utc, applied_at_tz, applied_at_offset = local_timestamp_metadata()
                conn.execute(
                    "INSERT INTO schema_version ("
                    "version, applied_at_utc, applied_at_tz, applied_at_offset_minutes"
                    ") VALUES (?, ?, ?, ?)",
                    (migration.version, applied_at_utc, applied_at_tz, applied_at_offset),
                )
                conn.commit()
            current = _current_version(conn)
            if current < migration.version:
                raise MigrationError(
                    f"Migration {migration.path.name} did not update schema_version"
                )

        return current
    finally:
        conn.close()


def main() -> int:
    db_path = os.environ.get("GODZILLA_DB_PATH")
    db_key = os.environ.get("GODZILLA_DB_KEY")
    if not db_path or not db_key:
        raise SystemExit("GODZILLA_DB_PATH and GODZILLA_DB_KEY are required")
    version = run_migrations(db_path=db_path, db_key=db_key)
    print(f"Schema version: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
