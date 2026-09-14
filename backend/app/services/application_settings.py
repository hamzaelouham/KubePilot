from dataclasses import dataclass
import json
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as SQLAlchemySession

from app.core.audit import AuditEvent, record_audit
from app.core.config import Settings
from app.models.entities import ApplicationCredential, ApplicationSetting
from app.services.credential_encryption import CredentialEncryption


class SettingsServiceError(RuntimeError):
    status_code = 422
    code = "settings_error"


class UnknownSettingError(SettingsServiceError):
    status_code = 404
    code = "setting_not_found"


class UnknownCredentialError(SettingsServiceError):
    status_code = 404
    code = "credential_not_found"


class InvalidSettingValueError(SettingsServiceError):
    code = "invalid_setting_value"


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    default: Any = None
    validator: Callable[[Any], Any] | None = None

    def validate(self, value: Any) -> Any:
        if self.validator is None:
            return value
        try:
            return self.validator(value)
        except (TypeError, ValueError) as error:
            raise InvalidSettingValueError(f"Invalid value for setting {self.key}") from error


@dataclass(frozen=True)
class CredentialDefinition:
    key: str


# Later provider/integration modules register their own stable server-side keys.
# Keeping these registries empty here prevents bootstrap secrets or arbitrary
# environment variables from becoming editable through this foundation API.
SETTING_DEFINITIONS: dict[str, SettingDefinition] = {}
CREDENTIAL_DEFINITIONS: dict[str, CredentialDefinition] = {}


def register_setting_definition(definition: SettingDefinition) -> None:
    if definition.key in SETTING_DEFINITIONS:
        raise ValueError(f"Setting definition already registered: {definition.key}")
    SETTING_DEFINITIONS[definition.key] = definition


def register_credential_definition(definition: CredentialDefinition) -> None:
    if definition.key in CREDENTIAL_DEFINITIONS:
        raise ValueError(f"Credential definition already registered: {definition.key}")
    CREDENTIAL_DEFINITIONS[definition.key] = definition


def list_application_settings(database: SQLAlchemySession) -> list[dict[str, Any]]:
    rows = {
        row.key: row
        for row in database.scalars(select(ApplicationSetting)).all()
        if row.key in SETTING_DEFINITIONS
    }
    return [
        {
            "key": definition.key,
            "value": rows[definition.key].value_json if definition.key in rows else definition.default,
            "updated_at": rows[definition.key].updated_at if definition.key in rows else None,
        }
        for definition in SETTING_DEFINITIONS.values()
    ]


def upsert_application_setting(
    database: SQLAlchemySession,
    actor_id: UUID,
    key: str,
    value: Any,
) -> dict[str, Any]:
    definition = SETTING_DEFINITIONS.get(key)
    if definition is None:
        raise UnknownSettingError("Setting is not registered")
    validated = definition.validate(value)
    try:
        json.dumps(validated)
    except (TypeError, ValueError) as error:
        raise InvalidSettingValueError(f"Invalid value for setting {key}") from error
    row = database.scalar(select(ApplicationSetting).where(ApplicationSetting.key == key))
    action = AuditEvent.SETTING_UPDATED if row is not None else AuditEvent.SETTING_CREATED
    if row is None:
        row = ApplicationSetting(key=key, value_json=validated, created_by_id=actor_id, updated_by_id=actor_id)
        database.add(row)
    else:
        row.value_json = validated
        row.updated_by_id = actor_id
    record_audit(database, action, actor_id, "application_setting", key, result="succeeded", context={"key": key})
    _commit(database)
    database.refresh(row)
    return {"key": row.key, "value": row.value_json, "updated_at": row.updated_at}


def delete_application_setting(database: SQLAlchemySession, actor_id: UUID, key: str) -> dict[str, Any]:
    if key not in SETTING_DEFINITIONS:
        raise UnknownSettingError("Setting is not registered")
    row = database.scalar(select(ApplicationSetting).where(ApplicationSetting.key == key))
    if row is None:
        return {"key": key, "value": SETTING_DEFINITIONS[key].default, "updated_at": None}
    database.delete(row)
    record_audit(database, AuditEvent.SETTING_DELETED, actor_id, "application_setting", key, result="succeeded", context={"key": key})
    _commit(database)
    return {"key": key, "value": SETTING_DEFINITIONS[key].default, "updated_at": None}


def list_credential_metadata(database: SQLAlchemySession) -> list[dict[str, Any]]:
    rows = {
        row.credential_key: row
        for row in database.scalars(select(ApplicationCredential)).all()
        if row.credential_key in CREDENTIAL_DEFINITIONS
    }
    return [
        {
            "credential_key": definition.key,
            "configured": definition.key in rows,
            "updated_at": rows[definition.key].updated_at if definition.key in rows else None,
        }
        for definition in CREDENTIAL_DEFINITIONS.values()
    ]


def replace_credential(
    database: SQLAlchemySession,
    settings: Settings,
    actor_id: UUID,
    credential_key: str,
    value: str,
) -> dict[str, Any]:
    if credential_key not in CREDENTIAL_DEFINITIONS:
        raise UnknownCredentialError("Credential is not registered")
    ciphertext = CredentialEncryption.from_settings(settings).encrypt(value)
    row = database.scalar(
        select(ApplicationCredential).where(ApplicationCredential.credential_key == credential_key)
    )
    action = AuditEvent.CREDENTIAL_REPLACED if row is not None else AuditEvent.CREDENTIAL_CREATED
    if row is None:
        row = ApplicationCredential(
            credential_key=credential_key,
            ciphertext=ciphertext,
            created_by_id=actor_id,
            updated_by_id=actor_id,
        )
        database.add(row)
    else:
        row.ciphertext = ciphertext
        row.updated_by_id = actor_id
    record_audit(
        database,
        action,
        actor_id,
        "application_credential",
        credential_key,
        result="succeeded",
        context={"credential_key": credential_key},
    )
    _commit(database)
    database.refresh(row)
    return _credential_metadata(row)


def delete_credential(database: SQLAlchemySession, actor_id: UUID, credential_key: str) -> dict[str, Any]:
    if credential_key not in CREDENTIAL_DEFINITIONS:
        raise UnknownCredentialError("Credential is not registered")
    row = database.scalar(
        select(ApplicationCredential).where(ApplicationCredential.credential_key == credential_key)
    )
    if row is None:
        return {"credential_key": credential_key, "configured": False, "updated_at": None}
    database.delete(row)
    record_audit(
        database,
        AuditEvent.CREDENTIAL_DELETED,
        actor_id,
        "application_credential",
        credential_key,
        result="succeeded",
        context={"credential_key": credential_key},
    )
    _commit(database)
    return {"credential_key": credential_key, "configured": False, "updated_at": None}


def read_credential_value(database: SQLAlchemySession, settings: Settings, credential_key: str) -> str | None:
    if credential_key not in CREDENTIAL_DEFINITIONS:
        raise UnknownCredentialError("Credential is not registered")
    row = database.scalar(
        select(ApplicationCredential).where(ApplicationCredential.credential_key == credential_key)
    )
    if row is None:
        return None
    return CredentialEncryption.from_settings(settings).decrypt(row.ciphertext)


def _credential_metadata(row: ApplicationCredential) -> dict[str, Any]:
    return {"credential_key": row.credential_key, "configured": True, "updated_at": row.updated_at}


def _commit(database: SQLAlchemySession) -> None:
    try:
        database.commit()
    except Exception:
        database.rollback()
        raise
