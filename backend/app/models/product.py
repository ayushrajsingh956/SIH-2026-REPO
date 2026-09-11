from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.scan import Scan


class Product(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manufacturer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(100), unique=True, index=True, nullable=True)
    gtin: Mapped[str | None] = mapped_column(String(100), unique=True, index=True, nullable=True)
    search_vector = mapped_column(TSVECTOR, nullable=True)
    first_scanned: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    scans: Mapped[list["Scan"]] = relationship("Scan", back_populates="product")

    __table_args__ = (Index("ix_products_search_vector", "search_vector", postgresql_using="gin"),)
