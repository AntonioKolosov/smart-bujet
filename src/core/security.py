from __future__ import annotations

import base64
from functools import lru_cache
import hashlib
import hmac
import os
import time
from urllib.parse import parse_qsl
from sqlalchemy.types import TypeDecorator, String, Text
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from src.core.config import settings


def validate_init_data(init_data: str, bot_token: str) -> dict | None:
    if not bot_token or not bot_token.strip():
        return None

    try:
        parsed_data = dict(parse_qsl(init_data, keep_blank_values=True))
        if "hash" not in parsed_data:
            return None

        received_hash = parsed_data.pop("hash")

        if "auth_date" not in parsed_data:
            return None

        now = time.time()
        auth_date = int(parsed_data["auth_date"])
        # Reject expired data (> 24 hours old) or future timestamps beyond 60s clock skew
        if (now - auth_date > 86400) or (auth_date - now > 60):
            return None

        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed_data.items())
        )

        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if hmac.compare_digest(calculated_hash, received_hash):
            return parsed_data

        return None
    except Exception:
        return None


@lru_cache(maxsize=8)
def _derive_encryption_key_bytes(key_str: str, fallback_token: str) -> bytes:
    if not key_str:
        if fallback_token:
            return hashlib.sha256(fallback_token.encode("utf-8")).digest()
        raise RuntimeError("DATA_ENCRYPTION_KEY is required for encryption")
    if len(key_str) == 64:
        try:
            return bytes.fromhex(key_str)
        except Exception:
            pass
    try:
        raw = base64.b64decode(key_str)
        if len(raw) == 32:
            return raw
    except Exception:
        pass
    return hashlib.sha256(key_str.encode("utf-8")).digest()


@lru_cache(maxsize=8)
def _get_cached_aesgcm(key_str: str, fallback_token: str) -> AESGCM:
    return AESGCM(_derive_encryption_key_bytes(key_str, fallback_token))


def _get_encryption_key() -> bytes:
    key_str = (settings.data_encryption_key or "").strip()
    fallback_token = (settings.bot_token or "").strip()
    return _derive_encryption_key_bytes(key_str, fallback_token)


def _get_aesgcm() -> AESGCM:
    key_str = (settings.data_encryption_key or "").strip()
    fallback_token = (settings.bot_token or "").strip()
    return _get_cached_aesgcm(key_str, fallback_token)


def encrypt_value(value: str | None) -> str | None:
    if value is None:
        return None
    if value.startswith("enc:v1:"):
        return value
    aesgcm = _get_aesgcm()
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, value.encode("utf-8"), None)
    encoded = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    return f"enc:v1:{encoded}"


def decrypt_value(value: str | None) -> str | None:
    if value is None:
        return None
    if not value.startswith("enc:v1:"):
        return value  # Transparent backward-compatibility for plaintext
    try:
        aesgcm = _get_aesgcm()
        raw = base64.urlsafe_b64decode(value[7:].encode("ascii"))
        nonce, ct = raw[:12], raw[12:]
        return aesgcm.decrypt(nonce, ct, None).decode("utf-8")
    except Exception:
        return value


class EncryptedString(TypeDecorator):
    """Transparent AES-256-GCM string encryption decorator for database columns."""
    impl = String
    cache_ok = True

    def __init__(self, length: int = 512, **kwargs):
        super().__init__(length=length, **kwargs)

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        return encrypt_value(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        return decrypt_value(value)


class EncryptedText(TypeDecorator):
    """Transparent AES-256-GCM text encryption decorator."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        return encrypt_value(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        return decrypt_value(value)


@lru_cache(maxsize=8)
def _encode_blind_secret(secret_str: str) -> bytes:
    return secret_str.encode("utf-8")


def blind_index(value: str | None) -> str:
    """Computes deterministic 64-char hex HMAC-SHA256 hash for blind indexing."""
    if not value:
        return ""
    normalized = value.strip().lower()
    secret_str = (settings.blind_index_secret or settings.bot_token or "").strip()
    if not secret_str:
        raise RuntimeError("BLIND_INDEX_SECRET is required for blind indexing")
    secret = _encode_blind_secret(secret_str)
    return hmac.new(secret, normalized.encode("utf-8"), hashlib.sha256).hexdigest()
