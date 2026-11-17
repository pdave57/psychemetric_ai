"""Core authentication, password hashing, and token utilities."""

import os
import hmac
import hashlib
import json
import base64
import time
import uuid
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET") or "psychemetre-dev-secret-change-in-production-123456"
TOKEN_EXPIRE_SECONDS = 3600 * 24  # 24 hours
REFRESH_EXPIRE_SECONDS = 3600 * 24 * 7  # 7 days


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with salt."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"pbkdf2:sha256:100000${salt.hex()}${key.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against stored PBKDF2 hash."""
    try:
        header, salt_hex, key_hex = hashed.split("$")
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        actual_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return hmac.compare_digest(actual_key, expected_key)
    except Exception:
        return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(data: str) -> bytes:
    pad = len(data) % 4
    if pad > 0:
        data += "=" * (4 - pad)
    return base64.urlsafe_b64decode(data.encode("utf-8"))


def create_access_token(user_id: str, role: str = "user", expires_in: int = TOKEN_EXPIRE_SECONDS) -> str:
    """Create a signed JWT-compatible token."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": int(time.time()) + expires_in,
        "jti": str(uuid.uuid4()),
        "token_type": "access",
    }
    header_b64 = _b64url_encode(json.dumps(header).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload).encode("utf-8"))
    sig = hmac.new(
        SECRET_KEY.encode("utf-8"),
        f"{header_b64}.{payload_b64}".encode("utf-8"),
        hashlib.sha256
    ).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(sig)}"


def create_refresh_token(user_id: str, expires_in: int = REFRESH_EXPIRE_SECONDS) -> str:
    """Create a signed refresh token."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "exp": int(time.time()) + expires_in,
        "jti": str(uuid.uuid4()),
        "token_type": "refresh",
    }
    header_b64 = _b64url_encode(json.dumps(header).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload).encode("utf-8"))
    sig = hmac.new(
        SECRET_KEY.encode("utf-8"),
        f"{header_b64}.{payload_b64}".encode("utf-8"),
        hashlib.sha256
    ).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(sig)}"


def decode_token(token: str) -> Optional[dict]:
    """Decode and verify a signed token."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        expected_sig = hmac.new(
            SECRET_KEY.encode("utf-8"),
            f"{header_b64}.{payload_b64}".encode("utf-8"),
            hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected_sig, _b64url_decode(sig_b64)):
            return None
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
