from sqlalchemy import create_engine

from app.core.config import Settings
from app.db.session import create_session_factory, get_database_session
from app.models.base import Base


def test_session_factory_uses_configured_database_url_without_connecting() -> None:
    settings = Settings(
        auth_secret="x" * 32,
        database_url="sqlite:///:memory:",
    )
    session_factory = create_session_factory(settings)
    assert str(session_factory.kw["bind"].url) == "sqlite:///:memory:"


def test_database_dependency_rolls_back_failed_request() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    settings = Settings(auth_secret="x" * 32, database_url="sqlite:///:memory:")
    session = engine.connect()
    transaction = session.begin()
    try:
        transaction.rollback()
        assert not transaction.is_active
    finally:
        session.close()

    dependency = get_database_session(settings)
    database_session = next(dependency)
    assert str(database_session.bind.url) == "sqlite:///:memory:"
    dependency.close()
    assert database_session.is_active
