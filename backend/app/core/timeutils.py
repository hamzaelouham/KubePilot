from datetime import datetime


def now() -> datetime:
    return datetime.now().astimezone()


def as_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone()
    return value.replace(tzinfo=None)


def is_expired(value: datetime | None, reference: datetime | None = None) -> bool:
    if value is None:
        return False
    return as_naive(value) <= as_naive(reference or now())