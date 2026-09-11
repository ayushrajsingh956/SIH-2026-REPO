import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.scan import Scan


class Violation(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "violations"

    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    rule_title: Mapped[str] = mapped_column(String(255), nullable=False)
    citation: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # critical, major, minor, advisory
    field_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    observed_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    bbox: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    overridden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    scan: Mapped["Scan"] = relationship("Scan", back_populates="violations")

    __table_args__ = (Index("ix_violations_scan_rule", "scan_id", "rule_code"),)
