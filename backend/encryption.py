from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from config import settings


def _derive_key(secret: str) -> bytes:
    """Derive a 32-byte Fernet key from the encryption_key setting."""
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_value(plaintext: str) -> str:
    f = Fernet(_derive_key(settings.encryption_key))
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    f = Fernet(_derive_key(settings.encryption_key))
    return f.decrypt(ciphertext.encode()).decode()
