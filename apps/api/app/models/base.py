"""Shared declarative base, column mixins, and cross-dialect column helpers.

Models in this package may depend on ``app.schemas`` (pure data contracts) but
never on ``app.agents``, ``app.tools``, or ``app.workflows`` — the persistence
layer sits below business logic, not above it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base shared by every AegisOS persistence model."""


class UUIDPrimaryKeyMixin(Base):
    """UUID primary key, per ARCHITECTURE.md §8.

    Callers may pass an explicit ``id`` (e.g. a plan step reusing its domain
    ``Task.task_id``) — the ``uuid4`` default only applies when one isn't given.

    Inherits ``Base`` and is marked ``__abstract__`` (SQLAlchemy's shared-column
    pattern) rather than being a plain mixin, so it contributes only the ``id``
    column to concrete subclasses — never a table of its own — while still
    being a real ``Base`` subclass. That lets the repository layer bind its
    generic ``ModelT`` to this class and get a typed ``.id`` back, instead of
    the plain ``Base`` bound where mypy can't see that attribute at all (see
    ``app.db.repositories.base``).
    """

    __abstract__ = True

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)


class TimestampMixin:
    """``created_at``/``updated_at`` columns, per ARCHITECTURE.md §8."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


def json_column_type() -> JSON:
    """JSONB on PostgreSQL, plain JSON elsewhere so SQLite-backed tests still work."""

    return JSON().with_variant(JSONB(), "postgresql")


def enum_column_type(enum_cls: type[Enum], *, name: str) -> SAEnum:
    """Native Postgres enum storing the member's ``.value``, not its ``.name``.

    SQLAlchemy's default ``Enum`` handling persists ``.name`` (e.g.
    ``"ORCHESTRATOR"``); every domain enum here is upper-snake-name /
    lower-snake-value, so without ``values_callable`` the stored value would
    silently diverge from what the Pydantic layer serializes.
    """

    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda obj: [member.value for member in obj],
    )


JsonScalar = str | int | float | bool | None
JsonObject = dict[str, Any]

__all__ = [
    "Base",
    "JsonObject",
    "JsonScalar",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "enum_column_type",
    "json_column_type",
]
