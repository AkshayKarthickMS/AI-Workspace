"""Compliance agent review log (ARCHITECTURE.md §8, §12)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column_type
from app.schemas.compliance import ComplianceVerdict


class ComplianceReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "compliance_reviews"

    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    finding_id: Mapped[UUID | None] = mapped_column(default=None)
    report_id: Mapped[UUID | None] = mapped_column(default=None)
    rule_set_version: Mapped[str] = mapped_column(String(50))
    verdict: Mapped[ComplianceVerdict] = mapped_column(
        enum_column_type(ComplianceVerdict, name="compliance_verdict")
    )
    reviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    escalation_reference: Mapped[str | None] = mapped_column(String(200), default=None)
