import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.scan import Scan


class Extraction(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "extractions"

    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    fields: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(100), default="gemini-2.5-flash", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    scan: Mapped["Scan"] = relationship("Scan", back_populates="extraction")
