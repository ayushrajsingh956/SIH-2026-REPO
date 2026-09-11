import base64
import logging
from pathlib import Path
from typing import Any

import weasyprint
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models.scan import Scan
from app.services.storage.minio_client import get_object_bytes

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _load_image_base64(storage_key: str | None) -> str | None:
    """Safely fetches image bytes from MinIO and converts to base64 string."""
    if not storage_key:
        return None
    try:
        raw_bytes = get_object_bytes(storage_key)
        return base64.b64encode(raw_bytes).decode("ascii")
    except Exception as exc:
        logger.warning("Could not fetch image '%s' for PDF report: %s", storage_key, exc)
        return None


def generate_pdf_report(
    scan: Scan,
    product_photo_bytes: bytes | None = None,
    annotated_photo_bytes: bytes | None = None,
) -> bytes:
    """Renders statutory inspection report to PDF using WeasyPrint and Jinja2."""
    template = jinja_env.get_template("gov-report.html")

    # Resolve product photo (either provided directly or retrieved from MinIO)
    product_photo_b64 = None
    if product_photo_bytes:
        product_photo_b64 = base64.b64encode(product_photo_bytes).decode("ascii")
    elif scan.image_urls and len(scan.image_urls) > 0:
        product_photo_b64 = _load_image_base64(scan.image_urls[0])

    # Resolve annotated/processed photo
    annotated_photo_b64 = None
    if annotated_photo_bytes:
        annotated_photo_b64 = base64.b64encode(annotated_photo_bytes).decode("ascii")
    elif scan.pipeline_meta and isinstance(scan.pipeline_meta, dict):
        proc_urls = scan.pipeline_meta.get("processed_image_urls")
        if proc_urls and len(proc_urls) > 0:
            annotated_photo_b64 = _load_image_base64(proc_urls[0])

    # Prepare extraction fields
    extraction = scan.extraction
    raw_fields = extraction.fields if extraction and extraction.fields else {}

    standard_order = [
        "manufacturer_name",
        "manufacturer_address",
        "importer_name",
        "importer_address",
        "country_of_origin",
        "net_quantity",
        "mrp",
        "mfg_date",
        "expiry_date",
        "consumer_care",
        "dimensions",
        "generic_name",
    ]

    field_rows: list[tuple[str, Any]] = []
    seen = set()
    for key in standard_order:
        if key in raw_fields:
            field_rows.append((key, raw_fields[key]))
            seen.add(key)
    for key, val in sorted(raw_fields.items()):
        if key not in seen and not key.startswith("_"):
            field_rows.append((key, val))

    # Identify violating fields
    violations = scan.violations or []
    violating_fields = {v.field_name for v in violations if v.field_name and not v.overridden}

    context = {
        "scan": scan,
        "product": scan.product,
        "inspector": scan.inspector,
        "violations": violations,
        "field_rows": field_rows,
        "violating_fields": violating_fields,
        "product_photo_b64": product_photo_b64,
        "annotated_photo_b64": annotated_photo_b64,
    }

    rendered_html = template.render(**context)

    # Compile with WeasyPrint
    html_doc = weasyprint.HTML(string=rendered_html, base_url=str(TEMPLATES_DIR))
    pdf_bytes = html_doc.write_pdf()
    return pdf_bytes
