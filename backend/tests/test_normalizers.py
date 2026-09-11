import pytest

from app.services.extraction.normalizers import (
    clean_address,
    normalize_indian_currency,
    normalize_metric_unit,
    normalize_month_year,
    normalize_phone,
)


class TestIndianCurrencyNormalizer:
    @pytest.mark.parametrize(
        ("input_text", "expected_val", "expected_curr", "expected_taxes"),
        [
            ("₹ 1,50,000/-", 150000.00, "INR", False),
            ("Rs. 45", 45.00, "INR", False),
            ("Rs. 45.50", 45.50, "INR", False),
            ("₹ 99.00 (incl. of all taxes)", 99.00, "INR", True),
            ("₹ 299/- Inclusive of all taxes", 299.00, "INR", True),
            ("MRP: Rs 1,200.00/-", 1200.00, "INR", False),
            ("INR 250", 250.00, "INR", False),
            ("₹ 1,00,00,000/-", 10000000.00, "INR", False),
            ("Rs 12/-", 12.00, "INR", False),
            ("MRP ₹ 499/- (INCL. ALL TAXES)", 499.00, "INR", True),
            ("45.00", 45.00, "INR", False),
        ],
    )
    def test_valid_currency_variations(
        self, input_text: str, expected_val: float, expected_curr: str, expected_taxes: bool
    ):
        result = normalize_indian_currency(input_text)
        assert result is not None
        assert result["value"] == expected_val
        assert result["currency"] == expected_curr
        assert result["taxes_inclusive"] == expected_taxes
        assert result["raw"] == input_text

    def test_invalid_or_empty_currency(self):
        assert normalize_indian_currency("") is None
        assert normalize_indian_currency("N/A") is None
        assert normalize_indian_currency("Free Sample") is None


class TestMonthYearNormalizer:
    @pytest.mark.parametrize(
        ("input_text", "expected_month", "expected_year"),
        [
            ("02/2026", 2, 2026),
            ("FEB 2026", 2, 2026),
            ("02-26", 2, 2026),
            ("FEBRUARY 2026", 2, 2026),
            ("02.26", 2, 2026),
            ("02/26", 2, 2026),
            ("Mar-2025", 3, 2025),
            ("03/25", 3, 2025),
            ("2026/02", 2, 2026),
            ("JAN 25", 1, 2025),
            ("DECEMBER 2024", 12, 2024),
            ("11/2027", 11, 2027),
            ("01-2026", 1, 2026),
            ("Pkd: 05/2025", 5, 2025),
            ("MFG: OCT 2025", 10, 2025),
        ],
    )
    def test_valid_month_year_variations(
        self, input_text: str, expected_month: int, expected_year: int
    ):
        result = normalize_month_year(input_text)
        assert result is not None
        assert result["month"] == expected_month
        assert result["year"] == expected_year
        assert result["raw"] == input_text

    def test_invalid_month_year(self):
        assert normalize_month_year("") is None
        assert normalize_month_year("13/2026") is None  # invalid month
        assert normalize_month_year("00/2026") is None
        assert normalize_month_year("not a date") is None


class TestMetricUnitNormalizer:
    @pytest.mark.parametrize(
        ("raw_qty", "raw_unit", "expected_val", "expected_canonical_unit"),
        [
            (500, "ml", 500.0, "ml"),
            ("500", "mL", 500.0, "ml"),
            (500.0, "ML", 500.0, "ml"),
            ("500 ml", None, 500.0, "ml"),
            ("500 millilitre", None, 500.0, "ml"),
            ("500 milliliters", None, 500.0, "ml"),
            ("1 L", None, 1.0, "l"),
            (1.5, "litre", 1.5, "l"),
            (2, "Liters", 2.0, "l"),
            (200, "g", 200.0, "g"),
            ("200 gm", None, 200.0, "g"),
            ("200 gms", None, 200.0, "g"),
            (200, "Grams", 200.0, "g"),
            ("1 kg", None, 1.0, "kg"),
            ("2.5 KG", None, 2.5, "kg"),
            (5, "Kilograms", 5.0, "kg"),
            ("15 cm", None, 15.0, "cm"),
            (1.2, "m", 1.2, "m"),
            ("50 mm", None, 50.0, "mm"),
            ("10 N", None, 10.0, "u"),
            ("5 pcs", None, 5.0, "u"),
            (1, "unit", 1.0, "u"),
            (10, "U", 10.0, "u"),
        ],
    )
    def test_valid_units_mapping(
        self,
        raw_qty: str | float,
        raw_unit: str | None,
        expected_val: float,
        expected_canonical_unit: str,
    ):
        result = normalize_metric_unit(raw_qty, raw_unit)
        assert result is not None
        assert result["value"] == expected_val
        assert result["unit"] == expected_canonical_unit

    def test_invalid_units(self):
        assert normalize_metric_unit(None, None) is None
        assert normalize_metric_unit("abc", "xyz") is None


class TestPhoneNormalizer:
    @pytest.mark.parametrize(
        ("input_text", "expected_cleaned"),
        [
            ("+91 98765 43210", ["9876543210"]),
            ("+91-98765-43210", ["9876543210"]),
            ("09876543210", ["9876543210"]),
            ("9876543210", ["9876543210"]),
            ("+91 (0) 98765 43210", ["9876543210"]),
            ("Contact: +91 9876543210 or 1800 123 456", ["9876543210", "1800123456"]),
            ("1800-200-1234", ["18002001234"]),
        ],
    )
    def test_valid_phone_cleanup(self, input_text: str, expected_cleaned: list[str]):
        result = normalize_phone(input_text)
        for expected in expected_cleaned:
            assert expected in result

    def test_empty_phone(self):
        assert normalize_phone("") == []
        assert normalize_phone("No phone provided") == []


class TestAddressNormalizer:
    def test_address_cleanup_and_pincode(self):
        raw = "   Plot No. 42,\nIndustrial Area, Phase-1,\n  New Delhi - 110020, India   "
        result = clean_address(raw)
        assert (
            "Plot No. 42, Industrial Area, Phase-1, New Delhi - 110020, India" in result["address"]
        )
        assert result["pincode"] == "110020"

    def test_address_without_pincode(self):
        raw = "Khasra No 12, Village Bilaspur, Gurugram"
        result = clean_address(raw)
        assert result["address"] == "Khasra No 12, Village Bilaspur, Gurugram"
        assert result["pincode"] is None

    def test_empty_address(self):
        assert clean_address("") == {"address": "", "pincode": None}
