import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.extraction import Extraction
    from app.models.product import Product
    from app.models.report import Report
    from app.models.user import User
    from app.models.violation import Violation


class Scan(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "scans"

    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    scanned_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mode: Mapped[str] = mapped_column(
        String(50), default="retail", nullable=False
    )  # retail, wholesale, imported, ecommerce
    image_urls: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="queued", nullable=False, index=True
    )  # queued, processing, completed, needs_review, failed
    verdict: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )  # compliant, non_compliant, needs_review
    compliance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    font_check_mode: Mapped[str] = mapped_column(
        String(50), default="relative", nullable=False
    )  # surface_area, reference_object, relative
    surface_area_cm2: Mapped[float | None] = mapped_column(Float, nullable=True)
    pipeline_meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    search_vector = mapped_column(TSVECTOR, nullable=True)
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    product: Mapped[Optional["Product"]] = relationship("Product", back_populates="scans")
    inspector: Mapped["User"] = relationship("User", back_populates="scans")
    extraction: Mapped[Optional["Extraction"]] = relationship(
        "Extraction", back_populates="scan", uselist=False, cascade="all, delete-orphan"
    )
    violations: Mapped[list["Violation"]] = relationship(
        "Violation", back_populates="scan", cascade="all, delete-orphan"
    )
    reports: Mapped[list["Report"]] = relationship("Report", back_populates="scan")

    __table_args__ = (Index("ix_scans_search_vector", "search_vector", postgresql_using="gin"),)
