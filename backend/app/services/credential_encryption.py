from cryptography.fernet import Fernet, InvalidToken

from app.core.config import ConfigurationError, Settings


class CredentialEncryption:
    """Server-only Fernet boundary for credential material."""

    def __init__(self, key: str | None) -> None:
        if not key:
            raise ConfigurationError(
                "Credential encryption is unavailable until KUBEPILOT_ENCRYPTION_KEY is configured"
            )
        try:
            self._fernet = Fernet(key.encode("ascii"))
        except (UnicodeEncodeError, TypeError, ValueError) as error:
            raise ConfigurationError("KUBEPILOT_ENCRYPTION_KEY is not a valid Fernet key") from error

    @classmethod
    def from_settings(cls, settings: Settings) -> "CredentialEncryption":
        return cls(settings.encryption_key)

    def encrypt(self, value: str) -> str:
        if not isinstance(value, str) or not value:
            raise ValueError("Credential values must be non-empty strings")
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError, InvalidToken, TypeError, ValueError) as error:
            raise ConfigurationError("Stored credential material cannot be decrypted") from error
