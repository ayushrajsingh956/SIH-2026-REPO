import pytest

from app.schemas.extraction import (
    ConsumerCareField,
    DateField,
    ExtractionFields,
    MRPField,
    NetQuantityField,
    StandardTextField,
    TextBlock,
)
from app.services.rules.engine import evaluate_rules


class TestLMPCRulesTableDriven:
    """Table-driven test suite validating Pass, Fail, and Edge cases for every LMPC rule."""

    # 1. LMPC-R6-1a: Manufacturer Name & Address
    @pytest.mark.parametrize(
        "mfg_name, mfg_addr, expected_violation",
        [
            ("Britannia Industries", "5/1A Hungerford Street, Kolkata", False),  # Pass
            ("", "", True),  # Fail: missing both
            ("Britannia Industries", "", True),  # Fail: missing address
            ("", "5/1A Hungerford Street, Kolkata", True),  # Fail: missing name
            ("   ", "   ", True),  # Edge: whitespace only
        ],
    )
    def test_lmpc_r6_1a_manufacturer(self, mfg_name, mfg_addr, expected_violation):
        fields = ExtractionFields(
            manufacturer_name=StandardTextField(
                raw=mfg_name, normalized=mfg_name.strip(), present=bool(mfg_name.strip())
            ),
            manufacturer_address=StandardTextField(
                raw=mfg_addr, normalized=mfg_addr.strip(), present=bool(mfg_addr.strip())
            ),
        )
        violations, _ = evaluate_rules(fields=fields, scan_mode="retail")
        rule_violated = any(v.rule_code == "LMPC-R6-1a" for v in violations)
        assert rule_violated == expected_violation

    # 2. LMPC-R6-1b-name: Generic/Common Name
    @pytest.mark.parametrize(
        "name, present, expected_violation",
        [
            ("Wheat Flour", True, False),  # Pass
            ("", True, True),  # Fail: empty
            ("Shampoo", False, True),  # Fail: marked not present
            ("   ", True, True),  # Edge: whitespace
        ],
    )
    def test_lmpc_r6_1b_generic_name(self, name, present, expected_violation):
        fields = ExtractionFields(
            generic_name=StandardTextField(raw=name, normalized=name.strip(), present=present),
        )
        violations, _ = evaluate_rules(fields=fields, scan_mode="retail")
        rule_violated = any(v.rule_code == "LMPC-R6-1b-name" for v in violations)
        assert rule_violated == expected_violation

    # 3. LMPC-R6-1b-qty: Net Quantity Presence
    @pytest.mark.parametrize(
        "val, raw, present, expected_violation",
        [
            (500.0, "500 g", True, False),  # Pass
            (None, None, False, True),  # Fail: missing
            (None, "500 g", True, False),  # Edge: raw string present
            (None, "", True, True),  # Edge: empty raw
        ],
    )
    def test_lmpc_r6_1b_qty_presence(self, val, raw, present, expected_violation):
        fields = ExtractionFields(
            net_quantity=NetQuantityField(value=val, raw=raw, unit="g", present=present),
        )
        violations, _ = evaluate_rules(fields=fields, scan_mode="retail")
        rule_violated = any(v.rule_code == "LMPC-R6-1b-qty" for v in violations)
        assert rule_violated == expected_violation

    # 4. LMPC-R6-1c: Mfg Month & Year Presence
    @pytest.mark.parametrize(
        "month, year, raw, present, expected_violation",
        [
            (5, 2024, "05/2024", True, False),  # Pass
            (None, None, "", False, True),  # Fail: missing
            (None, 2024, "2024", True, False),  # Edge: year only
            (None, None, "May 2024", True, False),  # Edge: raw only
        ],
    )
    def test_lmpc_r6_1c_mfg_date_presence(self, month, year, raw, present, expected_violation):
        fields = ExtractionFields(
            mfg_date=DateField(month=month, year=year, raw=raw, present=present),
        )
        violations, _ = evaluate_rules(fields=fields, scan_mode="retail")
        rule_violated = any(v.rule_code == "LMPC-R6-1c" for v in violations)
        assert rule_violated == expected_violation

    # 5. LMPC-R6-1d: MRP Presence
    @pytest.mark.parametrize(
        "val, raw, present, expected_violation",
        [
            (150.0, "₹150.00", True, False),  # Pass
            (None, "", False, True),  # Fail
            (None, "MRP Rs. 150", True, False),  # Edge: raw only
        ],
    )
    def test_lmpc_r6_1d_mrp_presence(self, val, raw, present, expected_violation):
        fields = ExtractionFields(
            mrp=MRPField(value=val, raw=raw, present=present),
        )
        violations, _ = evaluate_rules(fields=fields, scan_mode="retail")
        rule_violated = any(v.rule_code == "LMPC-R6-1d" for v in violations)
        assert rule_violated == expected_violation

    # 6. LMPC-R6-1e: Consumer Care Details
    @pytest.mark.parametrize(
        "phone, email, addr, raw, present, expected_violation",
        [
            (
                ["1800-111-222"],
                "care@example.com",
                "Consumer Cell, Mumbai",
                "1800111222",
                True,
                False,
            ),  # Pass
            ([], None, None, None, False, True),  # Fail: completely absent
            ([], "customercare@brand.com", None, None, True, False),  # Edge: email only
            (["1800200300"], None, None, None, True, False),  # Edge: phone only
            ([], None, None, "Call toll-free 1800", True, False),  # Edge: raw only
        ],
    )
    def test_lmpc_r6_1e_consumer_care(self, phone, email, addr, raw, present, expected_violation):
        fields = ExtractionFields(
            consumer_care=ConsumerCareField(
                phone=phone, email=email, address=addr, raw=raw, present=present
            ),
        )
        violations, _ = evaluate_rules(fields=fields, scan_mode="retail")
        rule_violated = any(v.rule_code == "LMPC-R6-1e" for v in violations)
        assert rule_violated == expected_violation

    # 7. LMPC-R6-1f: Country of Origin
    @pytest.mark.parametrize(
        "origin, present, expected_violation",
        [
            ("India", True, False),  # Pass
            ("Made in India", True, False),  # Pass
            ("", False, True),  # Fail
            ("   ", True, True),  # Edge: blank
        ],
    )
    def test_lmpc_r6_1f_country_of_origin(self, origin, present, expected_violation):
        fields = ExtractionFields(
            country_of_origin=StandardTextField(
                raw=origin, normalized=origin.strip(), present=present
            ),
        )
        violations, _ = evaluate_rules(fields=fields, scan_mode="retail")
        rule_violated = any(v.rule_code == "LMPC-R6-1f" for v in violations)
        assert rule_violated == expected_violation

    # 8. LMPC-R6-importer: Importer Block Completeness
    @pytest.mark.parametrize(
        "origin, mode, imp_name, imp_addr, expected_violation",
        [
            ("India", "retail", "", "", False),  # Pass: domestic, no importer required
            (
                "Germany",
                "retail",
                "Global Importers Ltd",
                "22 Port Road, Mumbai",
                False,
            ),  # Pass: foreign, complete importer
            ("Germany", "retail", "", "", True),  # Fail: foreign, missing importer completely
            ("USA", "imported", "Tech Impex", "", True),  # Fail: missing importer address
            ("India", "imported", "", "", True),  # Edge: mode=imported forces importer requirement
        ],
    )
    def test_lmpc_r6_importer_block(self, origin, mode, imp_name, imp_addr, expected_violation):
        fields = ExtractionFields(
            country_of_origin=StandardTextField(
                raw=origin, normalized=origin.strip(), present=True
            ),
            importer_name=StandardTextField(
                raw=imp_name, normalized=imp_name.strip(), present=bool(imp_name.strip())
            ),
            importer_address=StandardTextField(
                raw=imp_addr, normalized=imp_addr.strip(), present=bool(imp_addr.strip())
            ),
        )
        violations, _ = evaluate_rules(fields=fields, scan_mode=mode)
        rule_violated = any(v.rule_code == "LMPC-R6-importer" for v in violations)
        assert rule_violated == expected_violation

    # 9. LMPC-R9-1a: MRP Format & Currency
    @pytest.mark.parametrize(
        "val, raw, expected_violation",
        [
            (199.0, "₹199.00", False),  # Pass
            (0.0, "₹0.00", True),  # Fail: zero
            (-50.0, "-₹50", True),  # Fail: negative
            (None, "Rs. 250", False),  # Edge: value inferred from raw
            (None, "FREE SAMPLE", True),  # Edge: no numeral
        ],
    )
    def test_lmpc_r9_1a_mrp_format(self, val, raw, expected_violation):
        fields = ExtractionFields(
            mrp=MRPField(value=val, raw=raw, present=True),
        )
        violations, _ = evaluate_rules(fields=fields, scan_mode="retail")
        rule_violated = any(v.rule_code == "LMPC-R9-1a" for v in violations)
        assert rule_violated == expected_violation

    # 10. LMPC-R9-1b: Taxes Inclusive Text
    @pytest.mark.parametrize(
        "tax_text, raw, expected_violation",
        [
            ("inclusive of all taxes", "MRP Rs. 100", False),  # Pass
            ("incl. of all taxes", "₹100", False),  # Pass
            ("incl of taxes", "Rs. 100", False),  # Pass
            (None, "MRP Rs. 100", True),  # Fail: no taxes statement
            (None, "MRP Rs. 100 (taxes extra)", True),  # Fail: explicit taxes extra
            (None, "MRP Rs. 50 (All Taxes Included)", False),  # Edge: in raw text
        ],
    )
    def test_lmpc_r9_1b_taxes_inclusive(self, tax_text, raw, expected_violation):
        fields = ExtractionFields(
            mrp=MRPField(value=100.0, raw=raw, taxes_inclusive_text=tax_text, present=True),
        )
        violations, _ = evaluate_rules(fields=fields, scan_mode="retail")
        rule_violated = any(v.rule_code == "LMPC-R9-1b" for v in violations)
        assert rule_violated == expected_violation

    # 11. LMPC-R9-3: Dual MRP Prohibition
    @pytest.mark.parametrize(
        "raw_text, mrp_raw, expected_violation",
        [
            ("MRP Rs. 150 inclusive of all taxes", "Rs. 150", False),  # Pass: single MRP
            (
                "MRP Rs. 100 on front, MRP Rs. 120 on back",
                "Rs. 100",
                True,
            ),  # Fail: differing prices
            ("MRP Rs. 150 and MRP Rs. 150", "Rs. 150", False),  # Edge: identical prices repeated
        ],
    )
    def test_lmpc_r9_3_dual_mrp(self, raw_text, mrp_raw, expected_violation):
        fields = ExtractionFields(
            mrp=MRPField(value=150.0, raw=mrp_raw, present=True),
        )
        violations, _ = evaluate_rules(fields=fields, raw_text=raw_text, scan_mode="retail")
        rule_violated = any(v.rule_code == "LMPC-R9-3" for v in violations)
        assert rule_violated == expected_violation

    # 12. LMPC-R10-1: Standard Metric Units
    @pytest.mark.parametrize(
        "unit, raw, expected_violation",
        [
            ("g", "200 g", False),  # Pass
            ("kg", "1 kg", False),  # Pass
            ("ml", "500 ml", False),  # Pass
            ("l", "1 l", False),  # Pass
            ("gms", "200 gms", True),  # Fail: illegal plural symbol
            ("kgs", "5 kgs", True),  # Fail: illegal plural symbol
            ("mls", "250 mls", True),  # Fail: illegal plural symbol
            ("ltrs", "2 ltrs", True),  # Fail: non-standard
            (None, "100 g", False),  # Edge: unit inferred from raw
            ("lbs", "2 lbs", True),  # Edge: imperial unit
        ],
    )
    def test_lmpc_r10_1_units_standard(self, unit, raw, expected_violation):
        fields = ExtractionFields(
            net_quantity=NetQuantityField(value=100.0, unit=unit, raw=raw, present=True),
        )
        violations, _ = evaluate_rules(fields=fields, scan_mode="retail")
        rule_violated = any(v.rule_code == "LMPC-R10-1" for v in violations)
        assert rule_violated == expected_violation

    # 13. LMPC-R10-2: Net Quantity Placement & Qualifier Prohibition
    @pytest.mark.parametrize(
        "raw, expected_violation",
        [
            ("Net Wt. 500 g", False),  # Pass
            ("Net Quantity: 1 kg", False),  # Pass
            ("approx 500 g", True),  # Fail: approx
            ("approx. 1 kg", True),  # Fail: approx.
            ("when packed 250 g", True),  # Fail: when packed
            ("minimum 100 ml", True),  # Fail: minimum
            ("average 50 g", True),  # Fail: average
        ],
    )
    def test_lmpc_r10_2_net_qty_placement(self, raw, expected_violation):
        fields = ExtractionFields(
            net_quantity=NetQuantityField(value=100.0, unit="g", raw=raw, present=True),
        )
        violations, _ = evaluate_rules(fields=fields, scan_mode="retail")
        rule_violated = any(v.rule_code == "LMPC-R10-2" for v in violations)
        assert rule_violated == expected_violation

    # 14. LMPC-R11-1: Validity of Mfg Date
    @pytest.mark.parametrize(
        "month, year, raw, expected_violation",
        [
            (3, 2024, "03/2024", False),  # Pass: past valid date
            (14, 2024, "14/2024", True),  # Fail: invalid month (14)
            (0, 2024, "00/2024", True),  # Fail: month 0
            (1, 2045, "01/2045", True),  # Fail: far future year
            (None, None, "15/2024", True),  # Edge: invalid month in raw string
        ],
    )
    def test_lmpc_r11_1_date_valid(self, month, year, raw, expected_violation):
        fields = ExtractionFields(
            mfg_date=DateField(month=month, year=year, raw=raw, present=True),
        )
        violations, _ = evaluate_rules(fields=fields, scan_mode="retail")
        rule_violated = any(v.rule_code == "LMPC-R11-1" for v in violations)
        assert rule_violated == expected_violation

    # 15. LMPC-R9-5: Font Size Surface Area
    @pytest.mark.parametrize(
        "area, estimated_mm, expected_violation",
        [
            (40.0, 1.2, False),  # Pass: <= 50cm2 requires 1.0mm, observed 1.2mm
            (600.0, 2.0, True),  # Fail: 500-2500cm2 requires 4.0mm, observed 2.0mm
            (None, 0.5, False),  # Edge: surface area None skips check
        ],
    )
    def test_lmpc_r9_5_font_size_surface_area(self, area, estimated_mm, expected_violation):
        class MockTextBlock:
            def __init__(self, mm):
                self.text = "Net Wt 500g"
                self.estimated_font_height_mm = mm
                self.estimated_char_height_px = 20.0
                self.bbox = [0, 0, 10, 10]

        blocks = [MockTextBlock(estimated_mm)] if estimated_mm is not None else []
        fields = ExtractionFields()
        violations, _ = evaluate_rules(
            fields=fields,
            surface_area_cm2=area,
            detected_text_blocks=blocks,
            scan_mode="retail",
        )
        rule_violated = any(v.rule_code == "LMPC-R9-5" for v in violations)
        assert rule_violated == expected_violation

    # 16. LMPC-R9-5-rel: Font Size Relative
    @pytest.mark.parametrize(
        "char_px, expected_violation",
        [
            (16.0, False),  # Pass: legible font
            (7.5, True),  # Fail: under 10.0px
            (None, False),  # Edge: no char height estimation
        ],
    )
    def test_lmpc_r9_5_rel_font_size(self, char_px, expected_violation):
        blocks = (
            [TextBlock(text="MRP 100", estimated_char_height_px=char_px, bbox=[0, 0, 5, 5])]
            if char_px
            else []
        )
        fields = ExtractionFields()
        violations, _ = evaluate_rules(
            fields=fields,
            detected_text_blocks=blocks,
            scan_mode="retail",
        )
        rule_violated = any(v.rule_code == "LMPC-R9-5-rel" for v in violations)
        assert rule_violated == expected_violation
