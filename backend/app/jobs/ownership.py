"""One worker owns recovery and side effects for a database at a time."""

from contextlib import contextmanager
import fcntl

from sqlalchemy import text

LOCK_ID = 0x4B55424550494C


@contextmanager
def worker_ownership(engine):
    if engine.dialect.name == "postgresql":
        # Retain this dedicated connection until all synchronous work has finished.
        with engine.connect() as connection:
            acquired = connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_ID})
            connection.commit()
            try:
                yield bool(acquired)
            finally:
                if acquired:
                    connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_ID})
                    connection.commit()
    elif engine.dialect.name == "sqlite" and engine.url.database not in (None, "", ":memory:"):
        with open(engine.url.database + ".worker.lock", "a") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
    else:
        raise RuntimeError("Worker ownership requires PostgreSQL or file-backed SQLite")
