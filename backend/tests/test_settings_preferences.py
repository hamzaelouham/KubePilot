from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.v1.settings import router
from app.core.dependencies import AuthenticatedActor, get_current_actor, get_database_session
from app.models.base import Base
from app.models.entities import UserAccount, UserPreference
from app.services.settings import get_user_preferences


@pytest.fixture()
def preferences_api(tmp_path: Path) -> tuple[TestClient, object, AuthenticatedActor]:
    engine = create_engine(f"sqlite:///{tmp_path / 'preferences.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    user_id = uuid4()
    with factory() as database:
        database.add(UserAccount(id=user_id, email="admin@example.com", password_hash="hash", role="admin"))
        database.commit()

    actor = AuthenticatedActor("admin@example.com", "admin", user_id=user_id)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_current_actor] = lambda: actor

    def database_dependency():
        database = factory()
        try:
            yield database
        finally:
            database.close()

    app.dependency_overrides[get_database_session] = database_dependency
    return TestClient(app), factory, actor


def test_preferences_default_and_update_are_persisted(preferences_api) -> None:
    client, factory, actor = preferences_api
    with client as api:
        initial = api.get("/api/v1/settings/preferences")
        assert initial.status_code == 200
        assert initial.json() == {"default_namespace": None, "theme": "system"}

        updated = api.patch(
            "/api/v1/settings/preferences",
            json={"default_namespace": "kube-system", "theme": "dark"},
        )
        assert updated.status_code == 200
        assert updated.json() == {"default_namespace": "kube-system", "theme": "dark"}

    with factory() as database:
        preference = database.scalar(select(UserPreference).where(UserPreference.user_id == actor.user_id))
        assert preference is not None
        assert preference.default_namespace == "kube-system"
        assert preference.view_settings == {"theme": "dark"}
        assert get_user_preferences(database, actor.user_id).theme == "dark"


def test_theme_update_preserves_future_view_settings(preferences_api) -> None:
    client, factory, actor = preferences_api
    with factory() as database:
        database.add(UserPreference(user_id=actor.user_id, view_settings={"density": "compact"}))
        database.commit()

    with client as api:
        response = api.patch("/api/v1/settings/preferences", json={"theme": "light"})
        assert response.status_code == 200

    with factory() as database:
        preference = database.scalar(select(UserPreference).where(UserPreference.user_id == actor.user_id))
        assert preference.view_settings == {"density": "compact", "theme": "light"}


def test_preferences_reject_unknown_or_invalid_values(preferences_api) -> None:
    client, _factory, _actor = preferences_api
    with client as api:
        assert api.patch("/api/v1/settings/preferences", json={"database_url": "sqlite://"}).status_code == 422
        assert api.patch("/api/v1/settings/preferences", json={"theme": "solarized"}).status_code == 422
        assert api.patch("/api/v1/settings/preferences", json={"default_namespace": "Invalid_Name"}).status_code == 422


def test_preferences_are_not_addressable_for_another_user(preferences_api) -> None:
    client, factory, actor = preferences_api
    other_user_id = uuid4()
    with factory() as database:
        database.add(UserAccount(id=other_user_id, email="operator@example.com", password_hash="hash", role="operator"))
        database.commit()

    with client as api:
        response = api.patch(
            f"/api/v1/settings/preferences/{other_user_id}",
            json={"theme": "dark"},
        )
        assert response.status_code == 404

    with factory() as database:
        assert database.scalar(select(UserPreference).where(UserPreference.user_id == other_user_id)) is None
        assert database.scalar(select(UserPreference).where(UserPreference.user_id == actor.user_id)) is None
