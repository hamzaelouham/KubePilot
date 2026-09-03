import uuid
from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, MetaData, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


metadata = MetaData()


class Base(DeclarativeBase):
    metadata = metadata


PrimaryKey = Annotated[
    uuid.UUID,
    mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
]
CreatedAt = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now().astimezone()),
]
