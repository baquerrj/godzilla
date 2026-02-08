"""Helpers to redact sensitive values from logs.

REQ: FUNC-AUD-002, SEC-DATA-002
"""

from __future__ import annotations

import re
from typing import Any

_REDACTED = "[REDACTED]"

_SENSITIVE_SUBSTRINGS = (
    "access_token",
    "token",
    "secret",
    "password",
    "api_key",
    "pin",
    "credential",
)
_SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"(?i)(access_token|api_key|client_secret|password|pin|secret)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bbearer\s+\S+"),
)


def _is_sensitive_key(key: str) -> bool:
    """Return whether a dictionary key should be treated as sensitive.

    REQ: FUNC-AUD-002, SEC-DATA-002

    Args:
        key: Candidate key name.

    Returns:
        `True` when the key indicates sensitive content.
    """
    normalized = key.strip().lower()
    return any(fragment in normalized for fragment in _SENSITIVE_SUBSTRINGS)


def redact_sensitive(payload: Any) -> Any:
    """Return a copy of payload with known sensitive fields redacted.

    REQ: FUNC-AUD-002, SEC-DATA-002
    """
    if isinstance(payload, dict):
        redacted: dict[str, Any] = {}
        for key, value in payload.items():
            if _is_sensitive_key(str(key)):
                redacted[key] = _REDACTED
            else:
                redacted[key] = redact_sensitive(value)
        return redacted

    if isinstance(payload, list):
        return [redact_sensitive(item) for item in payload]

    if isinstance(payload, tuple):
        return tuple(redact_sensitive(item) for item in payload)

    if isinstance(payload, str):
        if any(pattern.search(payload) for pattern in _SENSITIVE_VALUE_PATTERNS):
            return _REDACTED
        return payload

    return payload
