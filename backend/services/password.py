"""Password hashing and constant-time verification helpers using salted scrypt."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from typing import Optional

_SCRYPT_N = 16384
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SCRYPT_MAXMEM = 32 * 1024 * 1024
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Hash a plain-text password using salted scrypt."""
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string.")
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        maxmem=_SCRYPT_MAXMEM,
        dklen=_SCRYPT_DKLEN,
    )
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii")
    digest_b64 = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt_b64}${digest_b64}"


def verify_password(plain_password: Optional[str], stored_hash: Optional[str]) -> bool:
    """Verify a plain-text password against a stored scrypt hash in constant time."""
    if not plain_password or not isinstance(plain_password, str):
        return False
    if not stored_hash or not isinstance(stored_hash, str):
        return False

    parts = stored_hash.split("$")
    if len(parts) != 6 or parts[0] != "scrypt":
        return False

    try:
        n = int(parts[1])
        r = int(parts[2])
        p = int(parts[3])
        salt = base64.urlsafe_b64decode(parts[4].encode("ascii"))
        expected = base64.urlsafe_b64decode(parts[5].encode("ascii"))
    except Exception:
        return False

    if n <= 1 or r <= 0 or p <= 0 or not salt or not expected:
        return False

    try:
        derived = hashlib.scrypt(
            plain_password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            maxmem=_SCRYPT_MAXMEM,
            dklen=len(expected),
        )
    except Exception:
        return False

    return hmac.compare_digest(derived, expected)
