"""Time utilities for UTC and local timestamp metadata.

REQ: TECH-SYS-004
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Tuple
from zoneinfo import ZoneInfo

DEFAULT_LOCAL_TZ = "America/Denver"


def local_timestamp_metadata(
    now_utc: datetime | None = None,
    tz_name: str | None = None,
) -> Tuple[str, str, int]:
    """Return (utc_iso, tz_name, offset_minutes) for the local timezone.

    REQ: TECH-SYS-004
    """
    now = now_utc or datetime.now(timezone.utc)
    tz = tz_name or os.environ.get("GODZILLA_LOCAL_TZ", DEFAULT_LOCAL_TZ)
    local_dt = now.astimezone(ZoneInfo(tz))
    offset = local_dt.utcoffset()
    offset_minutes = int(offset.total_seconds() // 60) if offset else 0
    return now.isoformat(timespec="seconds"), tz, offset_minutes


def local_date(now_utc: datetime | None = None, tz_name: str | None = None) -> str:
    """Return the local date (YYYY-MM-DD) for the configured timezone.

    REQ: TECH-SYS-004
    """
    now = now_utc or datetime.now(timezone.utc)
    tz = tz_name or os.environ.get("GODZILLA_LOCAL_TZ", DEFAULT_LOCAL_TZ)
    local_dt = now.astimezone(ZoneInfo(tz))
    return local_dt.date().isoformat()
