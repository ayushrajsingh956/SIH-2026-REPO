import io
import logging
from typing import Any

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Inches, Pt, RGBColor

from app.models.scan import Scan
from app.services.storage.minio_client import get_object_bytes

logger = logging.getLogger(__name__)


def _set_cell_background(cell: Any, fill_hex: str) -> None:
    """Sets background color of a Word table cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tc_pr.append(shd)


def _set_cell_margins(
    cell: Any, top: int = 100, bottom: int = 100, left: int = 150, right: int = 150
) -> None:
    """Sets cell padding."""
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = parse_xml(
        f"<w:tcMar {nsdecls('w')}>"
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f"</w:tcMar>"
    )
    tc_pr.append(tc_mar)


def generate_docx_report(
    scan: Scan,
    product_photo_bytes: bytes | None = None,
) -> bytes:
    """Generates editable Microsoft Word (.docx) statutory inspection report."""
    doc = Document()

    # Configure Margins (A4 standard)
    sections = doc.sections
    for s in sections:
        s.top_margin = Inches(0.7)
        s.bottom_margin = Inches(0.7)
        s.left_margin = Inches(0.7)
        s.right_margin = Inches(0.7)

    # 1. Official National Gov Header
    p_gov = doc.add_paragraph()
    p_gov.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_gov = p_gov.add_run("GOVERNMENT OF INDIA\n")
    r_gov.font.size = Pt(12)
    r_gov.font.bold = True
    r_gov.font.color.rgb = RGBColor(15, 23, 42)

    r_min = p_gov.add_run("MINISTRY OF CONSUMER AFFAIRS, FOOD & PUBLIC DISTRIBUTION\n")
    r_min.font.size = Pt(9.5)
    r_min.font.bold = True
    r_min.font.color.rgb = RGBColor(51, 65, 85)

    r_div = p_gov.add_run("DEPARTMENT OF CONSUMER AFFAIRS • LEGAL METROLOGY ENFORCEMENT DIVISION\n")
    r_div.font.size = Pt(8.5)
    r_div.font.color.rgb = RGBColor(30, 58, 138)

    # Title Banner
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_title = p_title.add_run("STATUTORY COMPLIANCE INSPECTION REPORT\n")
    r_title.font.size = Pt(13)
    r_title.font.bold = True
    r_title.font.color.rgb = RGBColor(15, 23, 42)

    r_stat = p_title.add_run(
        "Issued under Legal Metrology Act, 2009 & Legal Metrology (Packaged Commodities) Rules, 2011\n"
    )
    r_stat.font.size = Pt(8.5)
    r_stat.font.italic = True
    r_stat.font.color.rgb = RGBColor(71, 85, 105)

    r_ref = p_title.add_run(f"Statutory Reference: LM-{scan.id.hex[:8].upper()}")
    r_ref.font.size = Pt(9)
    r_ref.font.bold = True
    r_ref.font.color.rgb = RGBColor(30, 58, 138)

    doc.add_paragraph()  # Spacer

    # 2. Metadata Grid Table
    meta_table = doc.add_table(rows=4, cols=4)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_table.autofit = False

    inspector = scan.inspector
    product = scan.product

    metadata_cells = [
        (
            "Commodity / Product",
            product.name if product else "Packaged Commodity Label",
            "Inspection Date",
            scan.scanned_at.strftime("%d %B %Y, %H:%M UTC"),
        ),
        (
            "Brand / Manufacturer",
            product.brand if product and product.brand else "Declared on Packaging",
            "Inspection Mode",
            f"{scan.mode.capitalize()} Package",
        ),
        (
            "Scan UUID",
            str(scan.id),
            "Font Check Mode",
            f"{scan.font_check_mode.capitalize()} ({scan.surface_area_cm2} cm²)"
            if scan.surface_area_cm2
            else scan.font_check_mode.capitalize(),
        ),
        (
            "Inspecting Officer",
            inspector.name if inspector else "Authorized Officer",
            "Jurisdiction / District",
            f"{inspector.district or 'National Enforcement Cell'}, {inspector.state or 'India'}"
            if inspector
            else "National Enforcement Cell",
        ),
    ]

    for row_idx, row_data in enumerate(metadata_cells):
        row = meta_table.rows[row_idx]
        for col_idx in range(4):
            cell = row.cells[col_idx]
            cell.text = row_data[col_idx]
            _set_cell_margins(cell, top=60, bottom=60, left=100, right=100)
            if col_idx in (0, 2):
                _set_cell_background(cell, "F8FAFC")
                p = cell.paragraphs[0]
                p.runs[0].font.bold = True
                p.runs[0].font.size = Pt(8)
                p.runs[0].font.color.rgb = RGBColor(71, 85, 105)
            else:
                p = cell.paragraphs[0]
                p.runs[0].font.size = Pt(8)
                p.runs[0].font.color.rgb = RGBColor(15, 23, 42)

    doc.add_paragraph()

    # 3. Verdict and Score Summary Box
    verdict = scan.verdict or "needs_review"
    score = scan.compliance_score if scan.compliance_score is not None else 0.0

    v_table = doc.add_table(rows=1, cols=2)
    v_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    row_v = v_table.rows[0]

    # Left cell: Verdict
    cell_v = row_v.cells[0]
    p_v = cell_v.paragraphs[0]
    r_v_lbl = p_v.add_run("STATUTORY VERDICT:\n")
    r_v_lbl.font.size = Pt(8.5)
    r_v_lbl.font.bold = True
    r_v_lbl.font.color.rgb = RGBColor(71, 85, 105)

    if verdict == "compliant":
        verdict_str = "✓ STATUTORY COMPLIANT"
        fill_color = "F0FDF4"
        text_rgb = RGBColor(21, 128, 61)
    elif verdict == "non_compliant":
        verdict_str = "✕ NON-COMPLIANT (STATUTORY DEFICIENCIES RECORDED)"
        fill_color = "FEF2F2"
        text_rgb = RGBColor(185, 28, 28)
    else:
        verdict_str = "⚠ SCRUTINY REQUIRED / NEEDS REVIEW"
        fill_color = "FFFBEB"
        text_rgb = RGBColor(180, 83, 9)

    r_v_val = p_v.add_run(verdict_str)
    r_v_val.font.size = Pt(11)
    r_v_val.font.bold = True
    r_v_val.font.color.rgb = text_rgb

    _set_cell_background(cell_v, fill_color)
    _set_cell_margins(cell_v, top=120, bottom=120, left=150, right=150)

    # Right cell: Score
    cell_s = row_v.cells[1]
    p_s = cell_s.paragraphs[0]
    p_s.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r_s_lbl = p_s.add_run("COMPLIANCE SCORE:\n")
    r_s_lbl.font.size = Pt(8.5)
    r_s_lbl.font.bold = True
    r_s_lbl.font.color.rgb = RGBColor(71, 85, 105)

    r_s_val = p_s.add_run(f"{score:.1f} / 100")
    r_s_val.font.size = Pt(14)
    r_s_val.font.bold = True
    r_s_val.font.color.rgb = RGBColor(15, 23, 42)

    _set_cell_background(cell_s, fill_color)
    _set_cell_margins(cell_s, top=120, bottom=120, left=150, right=150)

    doc.add_paragraph()

    # 4. Product Photo Embedding (if available)
    raw_img_bytes = product_photo_bytes
    if not raw_img_bytes and scan.image_urls and len(scan.image_urls) > 0:
        try:
            raw_img_bytes = get_object_bytes(scan.image_urls[0])
        except Exception as exc:
            logger.debug("Could not fetch product photo for docx: %s", exc)

    if raw_img_bytes:
        h_ev = doc.add_heading("1. Photographic Inspection Evidence", level=1)
        h_ev.style.font.color.rgb = RGBColor(15, 23, 42)
        h_ev.style.font.size = Pt(11)

        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        try:
            img_stream = io.BytesIO(raw_img_bytes)
            p_img.add_run().add_picture(img_stream, width=Inches(3.5))
            p_cap = doc.add_paragraph(
                "Exhibit A: Packaged Commodity Packaging Surface As Submitted for Inspection"
            )
            p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_cap.runs[0].font.size = Pt(8)
            p_cap.runs[0].font.italic = True
            p_cap.runs[0].font.color.rgb = RGBColor(100, 116, 139)
        except Exception as img_err:
            logger.warning("Failed to embed image in docx: %s", img_err)

    # 5. Statutory Violations Table
    h_viol = doc.add_heading("2. Statutory Violations & Deficiencies Statement", level=1)
    h_viol.style.font.color.rgb = RGBColor(15, 23, 42)
    h_viol.style.font.size = Pt(11)

    violations = scan.violations or []
    if violations:
        viol_table = doc.add_table(rows=len(violations) + 1, cols=5)
        viol_table.alignment = WD_TABLE_ALIGNMENT.CENTER

        headers = [
            "Rule Code",
            "Statutory Citation",
            "Severity",
            "Observed Value",
            "Statutory Requirement",
        ]
        for col_idx, h_text in enumerate(headers):
            cell = viol_table.rows[0].cells[col_idx]
            cell.text = h_text
            _set_cell_background(cell, "0F172A")
            _set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
            p = cell.paragraphs[0]
            p.runs[0].font.bold = True
            p.runs[0].font.size = Pt(8)
            p.runs[0].font.color.rgb = RGBColor(255, 255, 255)

        for row_idx, v in enumerate(violations, start=1):
            row = viol_table.rows[row_idx]
            values = [
                v.rule_code,
                f"{v.citation}\n({v.rule_title})",
                v.severity.upper() + (" (OVERRIDDEN)" if v.overridden else ""),
                v.observed_value or "Declaration missing on label",
                (v.expected_value or "Mandatory statutory compliance")
                + (
                    f"\nOverride reason: {v.override_reason}"
                    if v.overridden and v.override_reason
                    else ""
                ),
            ]
            for col_idx, text in enumerate(values):
                cell = row.cells[col_idx]
                cell.text = text
                _set_cell_margins(cell, top=60, bottom=60, left=100, right=100)
                if row_idx % 2 == 0:
                    _set_cell_background(cell, "F8FAFC")
                p = cell.paragraphs[0]
                p.runs[0].font.size = Pt(8)
                if col_idx == 2:
                    p.runs[0].font.bold = True
                    if "CRITICAL" in text:
                        p.runs[0].font.color.rgb = RGBColor(153, 27, 27)
                    elif "MAJOR" in text:
                        p.runs[0].font.color.rgb = RGBColor(154, 52, 18)
    else:
        p_no = doc.add_paragraph(
            "No Statutory Violations Detected. All declarations comply with LMPC Rules, 2011."
        )
        p_no.runs[0].font.size = Pt(9)
        p_no.runs[0].font.color.rgb = RGBColor(21, 128, 61)

    doc.add_paragraph()

    # 6. Extracted Mandatory Declarations Table
    h_ext = doc.add_heading("3. Mandatory Declarations Audit (Rule 6(1) Verification)", level=1)
    h_ext.style.font.color.rgb = RGBColor(15, 23, 42)
    h_ext.style.font.size = Pt(11)

    extraction = scan.extraction
    fields = extraction.fields if extraction and extraction.fields else {}

    standard_fields = [
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

    field_rows = []
    seen = set()
    for key in standard_fields:
        if key in fields:
            field_rows.append((key, fields[key]))
            seen.add(key)
    for key, val in sorted(fields.items()):
        if key not in seen and not key.startswith("_"):
            field_rows.append((key, val))

    violating_fields = {v.field_name for v in violations if v.field_name and not v.overridden}

    f_table = doc.add_table(rows=len(field_rows) + 1, cols=4)
    f_table.alignment = WD_TABLE_ALIGNMENT.CENTER

    f_headers = ["Statutory Field", "Declared Value Extracted", "AI Confidence", "Conformity"]
    for col_idx, h_text in enumerate(f_headers):
        cell = f_table.rows[0].cells[col_idx]
        cell.text = h_text
        _set_cell_background(cell, "0F172A")
        _set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
        p = cell.paragraphs[0]
        p.runs[0].font.bold = True
        p.runs[0].font.size = Pt(8)
        p.runs[0].font.color.rgb = RGBColor(255, 255, 255)

    for row_idx, (f_name, f_data) in enumerate(field_rows, start=1):
        row = f_table.rows[row_idx]
        if isinstance(f_data, dict):
            disp_val = f_data.get("raw") or f_data.get("normalized") or str(f_data)
            conf = (
                f"{f_data.get('confidence', 0.0) * 100:.0f}%"
                if f_data.get("confidence") is not None
                else "—"
            )
        else:
            disp_val = str(f_data) if f_data is not None else "Not Detected"
            conf = "—"

        is_def = f_name in violating_fields
        conformity_str = "DEFICIENT" if is_def else "PASS"

        row_vals = [f_name.replace("_", " ").capitalize(), str(disp_val), conf, conformity_str]
        for col_idx, text in enumerate(row_vals):
            cell = row.cells[col_idx]
            cell.text = text
            _set_cell_margins(cell, top=60, bottom=60, left=100, right=100)
            if row_idx % 2 == 0:
                _set_cell_background(cell, "F8FAFC")
            p = cell.paragraphs[0]
            p.runs[0].font.size = Pt(8)
            if col_idx == 3:
                p.runs[0].font.bold = True
                p.runs[0].font.color.rgb = (
                    RGBColor(185, 28, 28) if is_def else RGBColor(21, 128, 61)
                )

    doc.add_paragraph()

    # 7. Official Certification & Attestation Block
    doc.add_paragraph()
    p_attest = doc.add_paragraph()
    p_attest.paragraph_format.space_before = Pt(14)
    r_attest = p_attest.add_run(
        "OFFICIAL STATUTORY ATTESTATION:\n"
        "I hereby certify that this compliance verification report has been generated through the LegalMetro Shield automated compliance assessment system under the authority vested under Section 15 of the Legal Metrology Act, 2009. The findings recorded herein reflect the statutory evaluation of the packaged commodity label submitted for inspection."
    )
    r_attest.font.size = Pt(8)
    r_attest.font.color.rgb = RGBColor(71, 85, 105)

    p_sig = doc.add_paragraph()
    p_sig.paragraph_format.space_before = Pt(20)
    p_sig.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r_sig_line = p_sig.add_run("_________________________________________\n")
    r_sig_line.font.color.rgb = RGBColor(71, 85, 105)
    r_sig_name = p_sig.add_run(
        f"Authorized Inspecting Officer: {inspector.name if inspector else 'Legal Metrology Officer'}\n"
    )
    r_sig_name.font.bold = True
    r_sig_name.font.size = Pt(8.5)
    r_sig_name.font.color.rgb = RGBColor(15, 23, 42)
    r_sig_date = p_sig.add_run(
        f"Date: {scan.scanned_at.strftime('%d-%m-%Y')} • LegalMetro Shield PS ID 26034"
    )
    r_sig_date.font.size = Pt(8)
    r_sig_date.font.color.rgb = RGBColor(100, 116, 139)

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()
