import uuid
from datetime import datetime
from typing import ClassVar

from sqlalchemy import DateTime, TypeDecorator, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise Uuid on SQLite/other databases.
    Converts string inputs to Python uuid.UUID objects on bind.
    """

    impl = Uuid
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(Uuid())

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(value)
        except ValueError:
            return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


class Base(DeclarativeBase):
    """Declarative base class for all database models."""

    type_annotation_map: ClassVar[dict] = {
        uuid.UUID: GUID,
    }


class TimestampMixin:
    """Mixin for models requiring created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False
    )


class SoftDeleteMixin:
    """Mixin for models requiring soft deletion via deleted_at."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
