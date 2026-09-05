import hashlib
import hmac

_SCHEME = "pbkdf2_sha256"
_ITERATIONS = 120_000
_FIXED_SALT_TEXT = b"kubepilot-password-salt"


def _salt() -> bytes:
    return hashlib.sha256(_FIXED_SALT_TEXT).digest()


def hash_password(password: str, *, iterations: int = _ITERATIONS) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), _salt(), iterations)
    return f"{_SCHEME}${iterations}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations_text, expected_hex = stored.split("$")
        iterations = int(iterations_text)
    except ValueError:
        return False
    if scheme != _SCHEME or iterations <= 0:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), _salt(), iterations).hex()
    return hmac.compare_digest(actual, expected_hex)