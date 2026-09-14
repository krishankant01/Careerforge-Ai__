"""
Shared ORM base and mixins.

Every table in this app needs an id + created_at + updated_at. Defining that
once here means every future model (Resume, Job, Skill, ...) just inherits
`Base, TimestampMixin` instead of repeating three columns every time.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class all ORM models inherit from."""
    pass


class UUIDPrimaryKeyMixin:
    """
    UUID primary keys instead of auto-increment integers:
    - Don't leak how many rows exist (e.g. "user #4" tells you there are ~4 users).
    - Safe to generate client-side or across distributed services later.
    """
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    """created_at / updated_at, set automatically by the database."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
