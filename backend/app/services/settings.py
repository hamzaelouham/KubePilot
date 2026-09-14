from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as SQLAlchemySession

from app.api.v1.settings_schemas import (
    SettingsPreferencesResponse,
    SettingsPreferencesUpdate,
)
from app.models.entities import UserPreference

DEFAULT_THEME = "system"
THEME_KEY = "theme"


def get_user_preferences(
    database: SQLAlchemySession,
    user_id: UUID,
) -> SettingsPreferencesResponse:
    preference = _find_user_preference(database, user_id)
    if preference is None:
        return SettingsPreferencesResponse(default_namespace=None, theme=DEFAULT_THEME)
    return _to_response(preference)


def update_user_preferences(
    database: SQLAlchemySession,
    user_id: UUID,
    changes: SettingsPreferencesUpdate,
) -> SettingsPreferencesResponse:
    preference = _find_user_preference(database, user_id)
    if preference is None:
        preference = UserPreference(user_id=user_id, view_settings={})
        database.add(preference)

    updates = changes.model_dump(exclude_unset=True)
    if "default_namespace" in updates:
        preference.default_namespace = updates["default_namespace"]
    if "theme" in updates:
        view_settings = dict(preference.view_settings or {})
        view_settings[THEME_KEY] = updates["theme"]
        preference.view_settings = view_settings

    database.commit()
    database.refresh(preference)
    return _to_response(preference)


def _find_user_preference(database: SQLAlchemySession, user_id: UUID) -> UserPreference | None:
    return database.scalar(select(UserPreference).where(UserPreference.user_id == user_id))


def _to_response(preference: UserPreference) -> SettingsPreferencesResponse:
    view_settings = preference.view_settings if isinstance(preference.view_settings, dict) else {}
    theme = view_settings.get(THEME_KEY)
    if theme not in {"system", "light", "dark"}:
        theme = DEFAULT_THEME
    return SettingsPreferencesResponse(
        default_namespace=preference.default_namespace,
        theme=theme,
    )
