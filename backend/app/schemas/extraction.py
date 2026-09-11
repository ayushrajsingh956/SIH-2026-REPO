from typing import Literal

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    # Normalized coordinates [ymin, xmin, ymax, xmax] or [x1, y1, x2, y2]
    coords: list[float] = Field(default_factory=list)


class BaseFieldExtraction(BaseModel):
    raw: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    bbox: list[float] = Field(default_factory=list)
    present: bool = True
    source: Literal["gemini", "ocr_fallback"] = "gemini"


class StandardTextField(BaseFieldExtraction):
    normalized: str | None = None


class NetQuantityField(BaseFieldExtraction):
    value: float | None = None
    unit: str | None = None


class MRPField(BaseFieldExtraction):
    value: float | None = None
    currency: str = "INR"
    taxes_inclusive_text: str | None = None


class DateField(BaseFieldExtraction):
    month: int | None = None
    year: int | None = None


class ConsumerCareField(BaseFieldExtraction):
    phone: list[str] = Field(default_factory=list)
    email: str | None = None
    address: str | None = None


class DimensionsField(BaseFieldExtraction):
    l_cm: float | None = None
    b_cm: float | None = None
    h_cm: float | None = None


class TextBlock(BaseModel):
    text: str
    bbox: list[float] = Field(default_factory=list)
    estimated_char_height_px: float | None = None
    estimated_font_height_mm: float | None = None


class ExtractionFields(BaseModel):
    manufacturer_name: StandardTextField = Field(default_factory=StandardTextField)
    manufacturer_address: StandardTextField = Field(default_factory=StandardTextField)
    importer_name: StandardTextField = Field(
        default_factory=lambda: StandardTextField(present=False)
    )
    importer_address: StandardTextField = Field(
        default_factory=lambda: StandardTextField(present=False)
    )
    country_of_origin: StandardTextField = Field(default_factory=StandardTextField)
    net_quantity: NetQuantityField = Field(default_factory=NetQuantityField)
    mrp: MRPField = Field(default_factory=MRPField)
    mfg_date: DateField = Field(default_factory=DateField)
    expiry_date: DateField = Field(default_factory=DateField)
    consumer_care: ConsumerCareField = Field(default_factory=ConsumerCareField)
    dimensions: DimensionsField = Field(default_factory=DimensionsField)
    generic_name: StandardTextField = Field(default_factory=StandardTextField)
    quantity_declaration_other: BaseFieldExtraction = Field(default_factory=BaseFieldExtraction)


class ExtractionResultSchema(BaseModel):
    fields: ExtractionFields = Field(default_factory=ExtractionFields)
    detected_text_blocks: list[TextBlock] = Field(default_factory=list)
    page_count: int = 1
    language_hints: list[str] = Field(default_factory=lambda: ["en"])
    raw_text: str | None = None
