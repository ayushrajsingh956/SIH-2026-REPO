import json
import logging
import re
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
            # Check either in mrp.raw or overall raw_text
            raw_all = (fields.mrp.raw + " " + (result.raw_text or "")).lower()
            if (
                norm_curr.get("taxes_inclusive")
                or "inclusive of all taxes" in raw_all
                or "incl. of all taxes" in raw_all
                or "incl. of taxes" in raw_all
                or "incl of all taxes" in raw_all
                or "incl. all taxes" in raw_all
                or ("incl" in raw_all and "tax" in raw_all)
            ):
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

    # 6. Country of Origin
    # Under LMPC Rule 6(1)(f), Country of Origin is mandatory for imported products.
    # If not explicitly captured, but manufacturer address or raw label text indicates domestic
    # manufacturing in India, infer "India" to prevent false positive violations.
    if not fields.country_of_origin.raw:
        addr = (fields.manufacturer_address.raw or "") + " " + (fields.manufacturer_address.normalized or "")
        mfg_name = fields.manufacturer_name.raw or ""
        raw_txt = result.raw_text or ""
        combined = (addr + " " + mfg_name + " " + raw_txt).lower()
        indian_keywords = [
            "india", "pune", "delhi", "mumbai", "bengaluru", "bangalore", "chennai", "kolkata",
            "hyderabad", "ahmedabad", "gujarat", "maharashtra", "karnataka", "tamil nadu",
            "haryana", "uttar pradesh", "rajasthan", "midc", "okhla", "talegaon", "noida",
            "gurgaon", "gurugram", "kerala", "punjab", "west bengal", "uttarakhand", "sidcul",
            "pantnagar", "haridwar", "ranipur"
        ]
        if any(kw in combined for kw in indian_keywords):
            fields.country_of_origin.raw = "India"
            fields.country_of_origin.normalized = "India"
            fields.country_of_origin.confidence = 0.95
            fields.country_of_origin.present = True

    # 7. Sugar Content Normalization (from table or raw text)
    if not fields.sugar_content.value_per_100g and result.raw_text:
        sugar_match = re.search(
            r"(?:total\s+sugar|added\s+sugar|sugars?)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:g|%)?",
            result.raw_text,
            re.IGNORECASE,
        )
        if sugar_match:
            try:
                s_val = float(sugar_match.group(1))
                fields.sugar_content.value_per_100g = s_val
                fields.sugar_content.raw = sugar_match.group(0)
                fields.sugar_content.confidence = 0.85
                fields.sugar_content.present = True
            except (ValueError, TypeError):
                pass

    # 8. Unit Sale Price (USP) Calculation / Normalization
    if fields.mrp.value and fields.net_quantity.value and fields.net_quantity.value > 0:
        calc_rate = round(fields.mrp.value / fields.net_quantity.value, 4)
        if fields.unit_sale_price.unit_price is not None:
            # Verify if matches within 5% tolerance
            if calc_rate > 0:
                diff = abs(fields.unit_sale_price.unit_price - calc_rate) / calc_rate
                fields.unit_sale_price.is_calculated_match = diff <= 0.05
        else:
            fields.unit_sale_price.unit_price = calc_rate
            fields.unit_sale_price.unit = fields.net_quantity.unit or "unit"
            fields.unit_sale_price.raw = f"Rs. {calc_rate:.2f}/{fields.unit_sale_price.unit}"
            fields.unit_sale_price.confidence = 0.85
            fields.unit_sale_price.present = True
            fields.unit_sale_price.is_calculated_match = True

    return result


def extract_with_gemini(
    images_bytes: list[bytes],
    mime_types: list[str] | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> tuple[ExtractionResultSchema, float]:
    """Invokes Gemini using google-genai SDK to extract structured LMPC fields.

    Uses gemini-3.1-flash-lite as primary high-speed model with automatic fallback
    to gemini-3.7-flash and gemini-3.8-flash upon server load spikes.

    Returns:
        tuple of (ExtractionResultSchema, avg_confidence)
    Raises:
        Exception on API or network failure.
    """
    key = api_key or settings.GEMINI_API_KEY
    if not key:
        raise ValueError("GEMINI_API_KEY is not configured.")

    candidate_models = [
        m for m in [
            model,
            settings.GEMINI_MODEL,
            "gemini-3.1-flash-lite",
            "gemini-3.7-flash",
            "gemini-3.8-flash",
        ] if m
    ]
    # Remove duplicates preserving order
    unique_candidates: list[str] = []
    for m in candidate_models:
        if m not in unique_candidates:
            unique_candidates.append(m)

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)

    contents: list[Any] = []
    for idx, img_buf in enumerate(images_bytes):
        mtype = mime_types[idx] if (mime_types and idx < len(mime_types)) else "image/png"
        contents.append(types.Part.from_bytes(data=img_buf, mime_type=mtype))

    contents.append(LMPC_EXTRACTION_PROMPT_V1)

    last_exc = None
    for cand_model in unique_candidates:
        try:
            response = client.models.generate_content(
                model=cand_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ExtractionResultSchema,
                    temperature=0.1,
                ),
            )
            if not response.text:
                raise ValueError(f"Gemini {cand_model} returned empty response text.")

            data = json.loads(response.text)
            result_schema = ExtractionResultSchema.model_validate(data)

            # Apply normalizers
            result_schema = apply_normalizations(result_schema)
            avg_conf = compute_avg_confidence(result_schema)

            logger.info("Gemini extraction succeeded with model '%s' (Confidence: %s)", cand_model, avg_conf)
            return result_schema, avg_conf
        except Exception as exc:
            logger.warning("Gemini model '%s' failed: %s", cand_model, exc)
            last_exc = exc
            continue

    raise ValueError(f"All Gemini models exhausted. Last error: {last_exc}") from last_exc
