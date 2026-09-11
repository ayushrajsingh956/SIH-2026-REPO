import json
import logging
from typing import Any

from app.core.config import settings
from app.schemas.extraction import ExtractionResultSchema
from app.services.extraction.normalizers import (
    clean_address,
    normalize_indian_currency,
    normalize_metric_unit,
    normalize_month_year,
    normalize_phone,
)
from app.services.extraction.prompts import LMPC_EXTRACTION_PROMPT_V1

logger = logging.getLogger(__name__)


def compute_avg_confidence(schema: ExtractionResultSchema) -> float:
    """Calculates the average confidence score across all extracted fields."""
    fields = schema.fields
    confidences: list[float] = []

    for _, field_obj in fields:
        if getattr(field_obj, "present", True) and hasattr(field_obj, "confidence"):
            conf = float(field_obj.confidence)
            if conf > 0.0:
                confidences.append(conf)

    if not confidences:
        return 0.0
    return round(sum(confidences) / len(confidences), 4)


def apply_normalizations(result: ExtractionResultSchema) -> ExtractionResultSchema:
    """Applies pure normalizer functions across raw extracted values."""
    fields = result.fields

    # 1. Currency (MRP)
    if fields.mrp.raw:
        norm_curr = normalize_indian_currency(fields.mrp.raw)
        if norm_curr:
            fields.mrp.value = norm_curr["value"]
            fields.mrp.currency = norm_curr["currency"]
            if norm_curr.get("taxes_inclusive"):
                fields.mrp.taxes_inclusive_text = "Inclusive of all taxes"

    # 2. Dates
    if fields.mfg_date.raw:
        norm_mfg = normalize_month_year(fields.mfg_date.raw)
        if norm_mfg:
            fields.mfg_date.month = norm_mfg["month"]
            fields.mfg_date.year = norm_mfg["year"]

    if fields.expiry_date.raw:
        norm_exp = normalize_month_year(fields.expiry_date.raw)
        if norm_exp:
            fields.expiry_date.month = norm_exp["month"]
            fields.expiry_date.year = norm_exp["year"]

    # 3. Net quantity & units
    if fields.net_quantity.raw or fields.net_quantity.value:
        norm_qty = normalize_metric_unit(
            fields.net_quantity.raw or fields.net_quantity.value,
            fields.net_quantity.unit,
        )
        if norm_qty:
            fields.net_quantity.value = norm_qty["value"]
            fields.net_quantity.unit = norm_qty["unit"]

    # 4. Consumer Care
    all_phone_sources: list[str] = list(fields.consumer_care.phone)
    if fields.consumer_care.address:
        cleaned_addr = clean_address(fields.consumer_care.address)
        fields.consumer_care.address = cleaned_addr["address"]

    # Extract clean phones
    if all_phone_sources:
        joined_phones = " ".join(all_phone_sources)
        cleaned_phones = normalize_phone(joined_phones)
        if cleaned_phones:
            fields.consumer_care.phone = cleaned_phones

    # 5. Manufacturer Address
    if fields.manufacturer_address.raw:
        cleaned_mfg_addr = clean_address(fields.manufacturer_address.raw)
        fields.manufacturer_address.normalized = cleaned_mfg_addr["address"]

    return result


def extract_with_gemini(
    images_bytes: list[bytes],
    mime_types: list[str] | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> tuple[ExtractionResultSchema, float]:
    """Invokes Gemini 2.5 Flash using google-genai SDK to extract structured LMPC fields.

    Returns:
        tuple of (ExtractionResultSchema, avg_confidence)
    Raises:
        Exception on API or network failure.
    """
    key = api_key or settings.GEMINI_API_KEY
    if not key:
        raise ValueError("GEMINI_API_KEY is not configured.")

    model_name = model or settings.GEMINI_MODEL or "gemini-2.5-flash"

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)

    contents: list[Any] = []
    for idx, img_buf in enumerate(images_bytes):
        mtype = mime_types[idx] if (mime_types and idx < len(mime_types)) else "image/png"
        contents.append(types.Part.from_bytes(data=img_buf, mime_type=mtype))

    contents.append(LMPC_EXTRACTION_PROMPT_V1)

    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ExtractionResultSchema,
            temperature=0.1,
        ),
    )

    if not response.text:
        raise ValueError("Gemini returned empty response text.")

    try:
        data = json.loads(response.text)
        result_schema = ExtractionResultSchema.model_validate(data)
    except Exception as exc:
        logger.error("Failed to parse Gemini JSON schema response: %s", exc)
        raise ValueError(f"Gemini response parsing failed: {exc}") from exc

    # Apply normalizers
    result_schema = apply_normalizations(result_schema)
    avg_conf = compute_avg_confidence(result_schema)

    return result_schema, avg_conf
