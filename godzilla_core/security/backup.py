"""Encrypted backup helpers for database and secrets snapshots.

REQ: FUNC-BKP-001, FUNC-BKP-002, FUNC-BKP-003, SEC-CRY-003
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from godzilla_core.util.time import local_timestamp_metadata

_BACKUP_FORMAT = "godzilla_backup"
_BACKUP_VERSION = 1
_SALT_BYTES = 16
_NONCE_BYTES = 12
_KDF_N = 2**14
_KDF_R = 8
_KDF_P = 1
_KEY_BYTES = 32
_AAD = b"godzilla-backup-v1"


class BackupError(RuntimeError):
    """Base backup/restore error type.

    REQ: FUNC-BKP-001, FUNC-BKP-002, FUNC-BKP-003
    """


class BackupIntegrityError(BackupError):
    """Raised when encrypted backup authentication fails.

    REQ: FUNC-BKP-002
    """


class BackupFormatError(BackupError):
    """Raised when backup envelope or payload fields are invalid.

    REQ: FUNC-BKP-001, FUNC-BKP-003
    """


@dataclass(frozen=True)
class DecryptedBackup:
    """Decoded and verified backup payload.

    REQ: FUNC-BKP-003
    """

    db_bytes: bytes
    db_filename: str
    secrets_bytes: bytes | None
    secrets_filename: str | None
    created_at_utc: str
    created_at_tz: str
    created_at_offset_minutes: int


def _b64_encode(value: bytes) -> str:
    """Encode bytes as URL-safe base64 text.

    REQ: FUNC-BKP-001
    """
    return base64.urlsafe_b64encode(value).decode("ascii")


def _b64_decode(value: str) -> bytes:
    """Decode URL-safe base64 text to bytes.

    REQ: FUNC-BKP-003
    """
    try:
        return base64.urlsafe_b64decode(value.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise BackupFormatError("Invalid backup base64 encoding") from exc


def _derive_key(passphrase: str, *, salt: bytes, n: int, r: int, p: int) -> bytes:
    """Derive an encryption key from passphrase using Scrypt.

    REQ: FUNC-BKP-001, SEC-CRY-003
    """
    if not passphrase:
        raise BackupFormatError("passphrase is required")
    kdf = Scrypt(salt=salt, length=_KEY_BYTES, n=n, r=r, p=p)
    return kdf.derive(passphrase.encode("utf-8"))


def create_backup_blob(
    *,
    db_bytes: bytes,
    db_filename: str,
    passphrase: str,
    secrets_bytes: bytes | None = None,
    secrets_filename: str | None = None,
) -> bytes:
    """Create an encrypted, authenticated backup envelope.

    REQ: FUNC-BKP-001, FUNC-BKP-002, SEC-CRY-003
    """
    if not db_bytes:
        raise BackupFormatError("Database backup payload is empty")
    if not db_filename:
        raise BackupFormatError("Database filename is required")
    if (secrets_bytes is None) != (secrets_filename is None):
        raise BackupFormatError("Secrets bytes and filename must both be set or both omitted")

    created_at_utc, created_at_tz, created_at_offset = local_timestamp_metadata()
    payload: dict[str, Any] = {
        "version": _BACKUP_VERSION,
        "created_at_utc": created_at_utc,
        "created_at_tz": created_at_tz,
        "created_at_offset_minutes": created_at_offset,
        "db_filename": db_filename,
        "db_sha256": sha256(db_bytes).hexdigest(),
        "db_bytes_b64": _b64_encode(db_bytes),
        "secrets_filename": secrets_filename,
        "secrets_sha256": sha256(secrets_bytes).hexdigest() if secrets_bytes is not None else None,
        "secrets_bytes_b64": _b64_encode(secrets_bytes) if secrets_bytes is not None else None,
    }
    plaintext = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    salt = os.urandom(_SALT_BYTES)
    nonce = os.urandom(_NONCE_BYTES)
    key = _derive_key(passphrase, salt=salt, n=_KDF_N, r=_KDF_R, p=_KDF_P)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, _AAD)

    envelope = {
        "format": _BACKUP_FORMAT,
        "version": _BACKUP_VERSION,
        "kdf": {
            "name": "scrypt",
            "salt_b64": _b64_encode(salt),
            "n": _KDF_N,
            "r": _KDF_R,
            "p": _KDF_P,
        },
        "encryption": {
            "name": "AESGCM",
            "nonce_b64": _b64_encode(nonce),
            "aad_b64": _b64_encode(_AAD),
        },
        "ciphertext_b64": _b64_encode(ciphertext),
    }
    return json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode("utf-8")


def decrypt_backup_blob(  # noqa: PLR0912, PLR0915
    *, blob: bytes, passphrase: str
) -> DecryptedBackup:
    """Decrypt and validate an encrypted backup envelope.

    REQ: FUNC-BKP-002, FUNC-BKP-003, SEC-CRY-003
    """
    try:
        envelope = json.loads(blob.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise BackupFormatError("Backup envelope is not valid JSON") from exc
    if not isinstance(envelope, dict):
        raise BackupFormatError("Backup envelope must be a JSON object")

    if envelope.get("format") != _BACKUP_FORMAT or envelope.get("version") != _BACKUP_VERSION:
        raise BackupFormatError("Unsupported backup format or version")

    kdf_payload = envelope.get("kdf")
    enc_payload = envelope.get("encryption")
    if not isinstance(kdf_payload, dict) or not isinstance(enc_payload, dict):
        raise BackupFormatError("Backup envelope is missing encryption metadata")

    try:
        salt = _b64_decode(str(kdf_payload["salt_b64"]))
        nonce = _b64_decode(str(enc_payload["nonce_b64"]))
        aad = _b64_decode(str(enc_payload["aad_b64"]))
        ciphertext = _b64_decode(str(envelope["ciphertext_b64"]))
        n = int(kdf_payload["n"])
        r = int(kdf_payload["r"])
        p = int(kdf_payload["p"])
    except (KeyError, TypeError, ValueError) as exc:
        raise BackupFormatError("Backup envelope has invalid encryption metadata") from exc

    key = _derive_key(passphrase, salt=salt, n=n, r=r, p=p)
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
    except InvalidTag as exc:
        raise BackupIntegrityError("Backup integrity check failed") from exc

    try:
        payload = json.loads(plaintext.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise BackupFormatError("Backup payload is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise BackupFormatError("Backup payload must be a JSON object")
    if payload.get("version") != _BACKUP_VERSION:
        raise BackupFormatError("Unsupported backup payload version")

    try:
        db_filename = str(payload["db_filename"])
        db_bytes = _b64_decode(str(payload["db_bytes_b64"]))
        db_hash = str(payload["db_sha256"])
    except KeyError as exc:
        raise BackupFormatError("Backup payload is missing database fields") from exc
    if sha256(db_bytes).hexdigest() != db_hash:
        raise BackupIntegrityError("Backup database checksum mismatch")

    secrets_filename = payload.get("secrets_filename")
    secrets_b64 = payload.get("secrets_bytes_b64")
    secrets_hash = payload.get("secrets_sha256")
    secrets_bytes: bytes | None = None
    if secrets_filename is not None or secrets_b64 is not None or secrets_hash is not None:
        if not (secrets_filename and secrets_b64 and secrets_hash):
            raise BackupFormatError("Secrets payload fields are incomplete")
        secrets_bytes = _b64_decode(str(secrets_b64))
        if sha256(secrets_bytes).hexdigest() != str(secrets_hash):
            raise BackupIntegrityError("Backup secrets checksum mismatch")

    return DecryptedBackup(
        db_bytes=db_bytes,
        db_filename=db_filename,
        secrets_bytes=secrets_bytes,
        secrets_filename=str(secrets_filename) if secrets_filename is not None else None,
        created_at_utc=str(payload.get("created_at_utc", "")),
        created_at_tz=str(payload.get("created_at_tz", "")),
        created_at_offset_minutes=int(payload.get("created_at_offset_minutes", 0)),
    )
