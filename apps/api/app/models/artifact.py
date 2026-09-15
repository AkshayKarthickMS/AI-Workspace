"""Delivery artifact table (ARCHITECTURE.md §8)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonObject, TimestampMixin, UUIDPrimaryKeyMixin, json_column_type


class Artifact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "artifacts"

    mission_id: Mapped[UUID] = mapped_column(
        ForeignKey("missions.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), index=True, default=None
    )
    # Free-form rather than an enum: report/slide_deck today, more types later
    # without a migration (ARCHITECTURE.md §7 Report agent).
    artifact_type: Mapped[str] = mapped_column(String(50))
    storage_uri: Mapped[str] = mapped_column(String(500))
    checksum: Mapped[str] = mapped_column(String(128))
    artifact_metadata: Mapped[JsonObject] = mapped_column(json_column_type(), default=dict)
