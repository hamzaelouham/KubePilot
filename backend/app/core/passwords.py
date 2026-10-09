import hashlib
import hmac
import secrets


_SCHEME_PREFIX = "pbkdf2_sha256$120000$"
_SALT = hashlib.sha256(b"kubepilot-password-salt").digest()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return _SCHEME_PREFIX + salt.hex() + "$" + digest.hex()


def password_matches(password: str, stored_hash: str) -> bool:
    if not stored_hash.startswith(_SCHEME_PREFIX):
        return False
    parts = stored_hash[len(_SCHEME_PREFIX):].split("$")
    try:
        if len(parts) == 1:
            salt, expected = _SALT, bytes.fromhex(parts[0])
        elif len(parts) == 2:
            salt, expected = bytes.fromhex(parts[0]), bytes.fromhex(parts[1])
            if len(salt) != 16:
                return False
        else:
            return False
        if len(expected) != 32:
            return False
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return hmac.compare_digest(actual, expected)


def password_needs_rehash(stored_hash: str) -> bool:
    return stored_hash.startswith(_SCHEME_PREFIX) and stored_hash.count("$") == 2


def validate_password_policy(password: str, min_length: int) -> tuple[bool, str]:
    if not password or len(password) < min_length:
        return False, f"Password must be at least {min_length} characters"
    return True, ""
