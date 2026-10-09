"""Persist ciphertext; expose plaintext only when a cluster client needs it."""

import os

from sqlalchemy import select, update

from app.core.config import ConfigurationError
from app.services.credential_encryption import CredentialEncryption

PREFIX = "fernet:v1:"


def encrypt_kubeconfig(value: str | None) -> str | None:
    if value is None:
        return None
    return PREFIX + CredentialEncryption(os.getenv("KUBEPILOT_ENCRYPTION_KEY")).encrypt(value)


def decrypt_kubeconfig(value: str | None) -> str | None:
    if value is None:
        return None
    if not value.startswith(PREFIX):
        raise ConfigurationError("Stored kubeconfigs require the encryption migration")
    return CredentialEncryption(os.getenv("KUBEPILOT_ENCRYPTION_KEY")).decrypt(value[len(PREFIX):])


def migrate_kubeconfigs(connection, table) -> None:
    # The caller owns one transaction: a missing key must never partially rewrite rows.
    for row in connection.execute(select(table.c.id, table.c.kubeconfig_content)):
        value = row.kubeconfig_content
        if value is not None and not value.startswith(PREFIX):
            connection.execute(update(table).where(table.c.id == row.id).values(
                kubeconfig_content=encrypt_kubeconfig(value),
            ))
