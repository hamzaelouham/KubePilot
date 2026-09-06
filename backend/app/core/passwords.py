import hashlib


_SCHEME_PREFIX = "pbkdf2_sha256$120000$"
_SALT = hashlib.sha256(b"kubepilot-password-salt").digest()


def hash_password(password: str) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), _SALT, 120_000)
    return _SCHEME_PREFIX + digest.hex()


def password_matches(password: str, stored_hash: str) -> bool:
    if not stored_hash.startswith(_SCHEME_PREFIX):
        return False
    return hash_password(password) == stored_hash


def validate_password_policy(password: str, min_length: int) -> tuple[bool, str]:
    if not password or len(password) < min_length:
        return False, f"Password must be at least {min_length} characters"
    return True, ""