"""PIN hashing helpers for application access gate.

REQ: TECH-SEC-ACC-001, TECH-SEC-ACC-003
"""

from __future__ import annotations

import hashlib
import os
from base64 import urlsafe_b64decode, urlsafe_b64encode
from hmac import compare_digest

_PIN_HASH_ITERATIONS = 310_000
_PIN_SALT_SIZE = 16


def generate_pin_salt() -> str:
    """Generate a random PIN salt as URL-safe base64.

    REQ: TECH-SEC-ACC-003
    """
    return urlsafe_b64encode(os.urandom(_PIN_SALT_SIZE)).decode("ascii")


def hash_pin(pin: str, salt_b64: str) -> str:
    """Hash a PIN using PBKDF2-HMAC-SHA256 and a persisted salt.

    REQ: TECH-SEC-ACC-003
    """
    salt = urlsafe_b64decode(salt_b64.encode("ascii"))
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("utf-8"),
        salt,
        _PIN_HASH_ITERATIONS,
    )
    return urlsafe_b64encode(digest).decode("ascii")


def verify_pin(pin: str, expected_hash_b64: str, salt_b64: str) -> bool:
    """Verify a candidate PIN against a stored hash and salt.

    REQ: TECH-SEC-ACC-001, TECH-SEC-ACC-003
    """
    calculated = hash_pin(pin, salt_b64)
    return compare_digest(calculated, expected_hash_b64)
