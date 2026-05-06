"""Token encryption helpers — AES-128-Fernet at rest for GitHub access tokens."""
import os
from cryptography.fernet import Fernet


def _cipher() -> Fernet:
    key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("ENCRYPTION_KEY not configured")
    return Fernet(key.encode())


def encrypt_token(plain: str) -> str:
    if not plain:
        return ""
    return _cipher().encrypt(plain.encode()).decode()


def decrypt_token(token: str) -> str:
    if not token:
        return ""
    return _cipher().decrypt(token.encode()).decode()
