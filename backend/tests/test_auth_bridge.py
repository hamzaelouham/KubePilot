import base64
import hashlib
import hmac
import json
import time

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DatabaseSession

from app.core.config import Settings
from app.core.dependencies import _resolve_cookie_actor
from app.models.base import Base
from app.models.entities import Session as StoredSession, UserAccount


def make_cookie(email: str, secret: str, expires_at: float) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps({"email": email, "expiresAt": expires_at}, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return f"{payload}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"


def test_shared_cookie_resolves_user_from_database() -> None:
    secret = "x" * 32
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with DatabaseSession(engine) as database:
        user = UserAccount(email="ops@example.com", password_hash="hash", role="admin")
        database.add(user)
        database.commit()
        cookie = make_cookie("OPS@example.com", secret, (time.time() + 300) * 1000)
        payload = cookie.split(".")[0]
        database.add(StoredSession(user_id=user.id, token_hash=hashlib.sha256(payload.encode()).hexdigest(), expires_at=datetime.fromtimestamp(time.time() + 300, tz=timezone.utc)))
        database.commit()
        actor = _resolve_cookie_actor(cookie, secret, database)

    assert actor is not None
    assert actor.identifier == "ops@example.com"
    assert actor.role == "admin"


def test_expired_shared_cookie_is_rejected() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    secret = "x" * 32
    with DatabaseSession(engine) as database:
        assert _resolve_cookie_actor(make_cookie("ops@example.com", secret, 0), secret, database) is None
