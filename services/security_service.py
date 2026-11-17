import base64
import hashlib

from flask import current_app
from cryptography.fernet import Fernet, InvalidToken


def _cipher():
    configured = current_app.config.get("EMBEDDING_ENCRYPTION_KEY", "")
    secret = configured or current_app.config["SECRET_KEY"]
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_embedding(value: bytes) -> bytes:
    return _cipher().encrypt(value)


def decrypt_embedding(value: bytes, encrypted: bool) -> bytes:
    if not encrypted:
        return value
    try:
        return _cipher().decrypt(value)
    except InvalidToken as exc:
        raise ValueError("Stored face data could not be decrypted.") from exc
