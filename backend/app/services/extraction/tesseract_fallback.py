import io
import logging
import re

import pytesseract
from PIL import Image

from app.schemas.extraction import (
    ConsumerCareField,
    DateField,
    ExtractionFields,
    ExtractionResultSchema,
    MRPField,
    NetQuantityField,
    StandardTextField,
    TextBlock,
)
from app.services.extraction.gemini_extractor import compute_avg_confidence
from app.services.extraction.normalizers import (
    clean_address,
    normalize_indian_currency,
    normalize_metric_unit,
    normalize_month_year,
    normalize_phone,
)

logger = logging.getLogger(__name__)


def extract_with_tesseract_fallback(
    images_bytes: list[bytes],
) -> tuple[ExtractionResultSchema, float]:
    """Runs offline OCR via Pytesseract and applies regex normalizers.

    All extracted fields are flagged with source='ocr_fallback'.
    """
    aggregated_text_blocks: list[TextBlock] = []
    full_raw_lines: list[str] = []

    for img_buf in images_bytes:
        try:
            pil_img = Image.open(io.BytesIO(img_buf))
        except Exception as exc:
            logger.warning("Failed to open image for tesseract fallback: %s", exc)
            continue

        # Extract full string
        try:
            raw_text = pytesseract.image_to_string(pil_img)
            full_raw_lines.extend(raw_text.splitlines())
        except Exception as exc:
            logger.warning("pytesseract image_to_string failed: %s", exc)
            raw_text = ""

        # Extract data with bounding boxes
        try:
            data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
            n_boxes = len(data.get("text", []))
            img_w, img_h = pil_img.size

            for i in range(n_boxes):
                word = (data["text"][i] or "").strip()
                if word:
                    x, y, w, h = (
                        data["left"][i],
                        data["top"][i],
                        data["width"][i],
                        data["height"][i],
                    )
                    # Normalize to 0-1000 scale [ymin, xmin, ymax, xmax]
                    norm_bbox = [
                        round((y / img_h) * 1000, 1),
                        round((x / img_w) * 1000, 1),
                        round(((y + h) / img_h) * 1000, 1),
                        round(((x + w) / img_w) * 1000, 1),
                    ]
                    aggregated_text_blocks.append(
                        TextBlock(
                            text=word,
                            bbox=norm_bbox,
                            estimated_char_height_px=h,
                        )
                    )
        except Exception as exc:
            logger.debug("pytesseract image_to_data failed: %s", exc)

    combined_text = "\n".join(full_raw_lines)
    fields = ExtractionFields()

    # Heuristic Regex Extraction from combined lines
    for line in full_raw_lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        # 1. MRP
        if not fields.mrp.raw and any(
            k in line_clean.lower() for k in ("mrp", "₹", "rs.", "rs ", "inr")
        ):
            norm_mrp = normalize_indian_currency(line_clean)
            if norm_mrp:
                fields.mrp = MRPField(
                    raw=line_clean,
                    value=norm_mrp["value"],
                    currency="INR",
                    taxes_inclusive_text="Inclusive of all taxes"
                    if norm_mrp["taxes_inclusive"]
                    else None,
                    confidence=0.55,
                    source="ocr_fallback",
                )

        # 2. Net Quantity
        if not fields.net_quantity.raw and any(
            u in line_clean.lower() for u in ("net", "qty", "ml", "g", "kg", "l")
        ):
            norm_qty = normalize_metric_unit(line_clean)
            if norm_qty:
                fields.net_quantity = NetQuantityField(
                    raw=line_clean,
                    value=norm_qty["value"],
                    unit=norm_qty["unit"],
                    confidence=0.55,
                    source="ocr_fallback",
                )

        # 3. Mfg Date
        if not fields.mfg_date.raw and any(
            d in line_clean.lower() for d in ("mfg", "pkd", "mfd", "date")
        ):
            norm_date = normalize_month_year(line_clean)
            if norm_date:
                fields.mfg_date = DateField(
                    raw=line_clean,
                    month=norm_date["month"],
                    year=norm_date["year"],
                    confidence=0.55,
                    source="ocr_fallback",
                )

        # 4. Manufacturer Name
        if not fields.manufacturer_name.raw and any(
            corp in line_clean.lower()
            for corp in ("ltd", "limited", "pvt", "industries", "foods", "enterprises")
        ):
            fields.manufacturer_name = StandardTextField(
                raw=line_clean,
                normalized=line_clean,
                confidence=0.50,
                source="ocr_fallback",
            )

        # 5. Address (check for PIN code)
        if not fields.manufacturer_address.raw and re.search(r"\b[1-9][0-9]{5}\b", line_clean):
            addr_res = clean_address(line_clean)
            fields.manufacturer_address = StandardTextField(
                raw=line_clean,
                normalized=addr_res["address"],
                confidence=0.50,
                source="ocr_fallback",
            )

    # 6. Consumer Care (phones)
    phones = normalize_phone(combined_text)
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", combined_text)
    if phones or email_match:
        fields.consumer_care = ConsumerCareField(
            phone=phones,
            email=email_match.group(0) if email_match else None,
            confidence=0.55 if phones else 0.40,
            source="ocr_fallback",
        )

    # 7. Generic name (fallback to first prominent capitalized text line if available)
    if not fields.generic_name.raw and full_raw_lines:
        for candidate in full_raw_lines[:5]:
            cand = candidate.strip()
            if len(cand) >= 3 and not any(
                k in cand.lower() for k in ("mrp", "mfg", "net", "qty", "rs")
            ):
                fields.generic_name = StandardTextField(
                    raw=cand,
                    normalized=cand.title(),
                    confidence=0.45,
                    source="ocr_fallback",
                )
                break

    result = ExtractionResultSchema(
        fields=fields,
        detected_text_blocks=aggregated_text_blocks,
        page_count=len(images_bytes),
        language_hints=["en"],
        raw_text=combined_text,
    )

    avg_conf = compute_avg_confidence(result)
    return result, avg_conf
