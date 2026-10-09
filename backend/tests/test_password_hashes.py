import hashlib

import pytest

from app.core.passwords import hash_password, password_matches, password_needs_rehash


def test_salts_are_unique_and_verification_rejects_wrong_password():
    first, second = hash_password("secret"), hash_password("secret")
    assert first != second
    assert password_matches("secret", first)
    assert password_matches("secret", second)
    assert not password_matches("wrong", first)
    assert not password_needs_rehash(first)


def test_legacy_hashes_remain_verifiable_for_login_upgrade():
    salt = hashlib.sha256(b"kubepilot-password-salt").digest()
    legacy = "pbkdf2_sha256$120000$" + hashlib.pbkdf2_hmac("sha256", b"secret", salt, 120000).hex()
    assert password_matches("secret", legacy)
    assert not password_matches("wrong", legacy)
    assert password_needs_rehash(legacy)


@pytest.mark.parametrize("stored", ["", "unknown", "pbkdf2_sha256$120000$bad", "pbkdf2_sha256$120000$00$00", "pbkdf2_sha256$120000$zz$zz", "pbkdf2_sha256$999999999999$00$00"])
def test_malformed_hashes_fail_closed(stored):
    assert not password_matches("secret", stored)
