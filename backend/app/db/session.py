from collections.abc import AsyncIterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings


def create_session_factory(settings: Settings) -> sessionmaker[SQLAlchemySession]:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_database_session(settings: Settings) -> AsyncIterator[SQLAlchemySession]:
    session_factory = create_session_factory(settings)
    session = session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
