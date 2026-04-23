"""Password hashing, JWT issuance/verification, Fernet encryption for Naukri password."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

_settings = get_settings()


# ------------------------------ passwords ---------------------------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# --------------------------------- JWT ------------------------------------

def create_access_token(subject: str | UUID, extra: dict[str, Any] | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=_settings.jwt_expire_minutes)
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire, "iat": datetime.now(timezone.utc)}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, _settings.jwt_secret, algorithms=["HS256"])


# ------------------------- Fernet (at-rest) -------------------------------

def _fernet() -> Fernet:
    key = _settings.fernet_key.encode("utf-8")
    # Allow plain 32-byte secrets too — auto-wrap into Fernet format.
    try:
        return Fernet(key)
    except ValueError:
        padded = base64.urlsafe_b64encode(key.ljust(32, b"0")[:32])
        return Fernet(padded)


def encrypt_secret(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode("utf-8"))


def decrypt_secret(ciphertext: bytes) -> str:
    try:
        return _fernet().decrypt(ciphertext).decode("utf-8")
    except InvalidToken as e:  # noqa: F841
        raise ValueError("Stored Naukri password could not be decrypted — rotate or reset.")
