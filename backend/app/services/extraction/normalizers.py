import re
from typing import Any

# Month name mapping
MONTH_MAP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

# Metric units mapping table per Legal Metrology (Packaged Commodities) Rules
UNIT_MAPPING = {
    # Volume
    "ml": "ml",
    "mi": "ml",  # Common OCR misread of 'ml'
    "millilitre": "ml",
    "millilitres": "ml",
    "milliliter": "ml",
    "milliliters": "ml",
    "l": "l",
    "ltr": "l",
    "litre": "l",
    "litres": "l",
    "liter": "l",
    "liters": "l",
    # Mass
    "g": "g",
    "gm": "g",
    "gms": "g",
    "gram": "g",
    "grams": "g",
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    # Length / Dimensions
    "cm": "cm",
    "centimetre": "cm",
    "centimetres": "cm",
    "centimeter": "cm",
    "centimeters": "cm",
    "m": "m",
    "metre": "m",
    "metres": "m",
    "meter": "m",
    "meters": "m",
    "mm": "mm",
    "millimetre": "mm",
    "millimeter": "mm",
    # Count / Numbers
    "u": "u",
    "unit": "u",
    "units": "u",
    "n": "u",
    "number": "u",
    "numbers": "u",
    "pc": "u",
    "pcs": "u",
    "piece": "u",
    "pieces": "u",
}


def normalize_indian_currency(raw_text: str | None) -> dict[str, Any] | None:
    """Parses and normalizes Indian currency strings.

    Examples:
        '₹ 1,50,000/-' -> {'value': 150000.0, 'currency': 'INR', 'taxes_inclusive': False, 'raw': ...}
        'Rs. 45' -> {'value': 45.0, 'currency': 'INR', 'taxes_inclusive': False, ...}
        '₹ 299/- Inclusive of all taxes' -> {'value': 299.0, 'currency': 'INR', 'taxes_inclusive': True, ...}
    """
    if not raw_text or not isinstance(raw_text, str):
        return None

    cleaned = raw_text.strip()
    if not cleaned:
        return None

    # Check for taxes inclusive indication
    lower_text = cleaned.lower()
    taxes_inclusive = bool(
        re.search(r"\b(incl|inclusive)\b.*\b(tax|taxes)\b", lower_text)
        or "inclusive of all taxes" in lower_text
        or "incl. of all taxes" in lower_text
        or "incl. all taxes" in lower_text
    )

    # Pattern for numbers:
    # 1) Numbers with commas: e.g. 1,50,000 or 1,00,00,000 or 1,200.00
    # 2) Plain numbers with optional decimals: e.g. 299, 45.50
    comma_pattern = r"\b\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?\b"
    plain_pattern = r"\b\d+(?:\.\d{1,2})?\b"

    match = re.search(comma_pattern, cleaned)
    if not match:
        match = re.search(plain_pattern, cleaned)

    if not match:
        return None

    num_str = match.group(0).replace(",", "")
    try:
        val = float(num_str)
        if val <= 0 and not re.search(r"\b0(?:\.0+)?\b", cleaned):
            return None
        return {
            "value": val,
            "currency": "INR",
            "taxes_inclusive": taxes_inclusive,
            "raw": cleaned,
        }
    except (ValueError, TypeError):
        return None


def normalize_month_year(raw_text: str | None) -> dict[str, Any] | None:
    """Parses month and year variants under LMPC Rule 6(1)(c).

    Supported patterns:
        '02/2026', 'FEB 2026', '02-26', 'FEBRUARY 2026', '02.26', '2026/02', etc.
    """
    if not raw_text or not isinstance(raw_text, str):
        return None

    cleaned = raw_text.strip()
    if not cleaned:
        return None

    # Remove prefixes like 'mfg:', 'pkd:', 'mfd:', 'date:'
    text_to_parse = re.sub(
        r"^(?:mfg|pkd|mfd|date|packed|manufactured)[\s.:/]*", "", cleaned, flags=re.IGNORECASE
    ).strip()

    # Pattern 1: Named month + year (e.g., 'FEB 2026', 'February 2026', 'JAN 25')
    named_pattern = r"\b([a-zA-Z]{3,9})[\s,/-]+(\d{2,4})\b"
    named_match = re.search(named_pattern, text_to_parse)
    if named_match:
        m_name = named_match.group(1).lower()
        yr_str = named_match.group(2)
        if m_name in MONTH_MAP:
            month = MONTH_MAP[m_name]
            year = int(yr_str) if len(yr_str) == 4 else 2000 + int(yr_str)
            return {"month": month, "year": year, "raw": cleaned}

    # Pattern 2: Numeric YYYY/MM or YYYY-MM
    iso_pattern = r"\b(20\d{2})[/.-](0?[1-9]|1[0-2])\b"
    iso_match = re.search(iso_pattern, text_to_parse)
    if iso_match:
        year = int(iso_match.group(1))
        month = int(iso_match.group(2))
        return {"month": month, "year": year, "raw": cleaned}

    # Pattern 3: Numeric MM/YYYY, MM/YY, MM-YY, MM.YY
    num_pattern = r"\b(0?[1-9]|1[0-2])[/.-](\d{2,4})\b"
    num_match = re.search(num_pattern, text_to_parse)
    if num_match:
        month = int(num_match.group(1))
        yr_str = num_match.group(2)
        year = int(yr_str) if len(yr_str) == 4 else 2000 + int(yr_str)
        return {"month": month, "year": year, "raw": cleaned}

    return None


def normalize_metric_unit(
    raw_quantity: str | float | None, raw_unit: str | None = None
) -> dict[str, Any] | None:
    """Canonicalizes net quantity and standard metric units under LMPC Rules."""
    if raw_quantity is None and raw_unit is None:
        return None

    # If raw_quantity contains both number and unit (e.g. '500 ml' or 'Net Qty: 500 ml')
    if isinstance(raw_quantity, str):
        cleaned_qty = raw_quantity.strip()
        # Remove common prefixes like 'Net Qty:', 'Net Wt:', 'Quantity:'
        stripped = re.sub(
            r"^(?:net\s*(?:qty|quantity|weight|contents|wt)?|quantity|qty)[\s.:/]*",
            "",
            cleaned_qty,
            flags=re.IGNORECASE,
        ).strip()

        # Parse number and unit
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z.]+)?", stripped)
        if match:
            val = float(match.group(1))
            unit_candidate = match.group(2) or raw_unit or ""
            canonical_unit = _resolve_unit(unit_candidate)
            if canonical_unit:
                return {"value": val, "unit": canonical_unit, "raw": cleaned_qty}

    # If raw_quantity is numeric and unit is passed separately
    try:
        val = float(raw_quantity) if raw_quantity is not None else None
    except (ValueError, TypeError):
        return None

    if val is not None and raw_unit:
        canonical_unit = _resolve_unit(raw_unit)
        if canonical_unit:
            return {"value": val, "unit": canonical_unit, "raw": f"{val} {raw_unit}"}

    return None


def _resolve_unit(unit_str: str | None) -> str | None:
    if not unit_str:
        return None
    cleaned = unit_str.strip().lower().rstrip(".")
    return UNIT_MAPPING.get(cleaned)


def normalize_phone(raw_phone: str | None) -> list[str]:
    """Strips +91, leading 0, spaces, hyphens and extracts valid 10-digit or toll-free numbers."""
    if not raw_phone or not isinstance(raw_phone, str):
        return []

    cleaned = raw_phone.strip()
    if not cleaned:
        return []

    results: list[str] = []

    # 1. Toll-free numbers: 1800-xxx-xxxx or 1800xxxxxx
    toll_free_matches = re.findall(r"\b1800[\s-]*\d{3}[\s-]*\d{3,4}\b", cleaned)
    for tf in toll_free_matches:
        digits = re.sub(r"\D", "", tf)
        if len(digits) in (10, 11) and digits not in results:
            results.append(digits)

    # 2. Standard 10-digit Indian mobile numbers (starting with 6, 7, 8, 9)
    # Often prefixed with +91, 91, or 0
    mobile_pattern = r"(?:(?:\+91|91|0)[\s-]*)?([6-9]\d{4}[\s-]*\d{5})\b"
    for match in re.finditer(mobile_pattern, cleaned):
        digits = re.sub(r"\D", "", match.group(1))
        if len(digits) == 10 and digits not in results:
            results.append(digits)

    return results


def clean_address(raw_address: str | None) -> dict[str, Any]:
    """Cleans address text, removes OCR artifact noise, and extracts Indian 6-digit PIN code."""
    if not raw_address or not isinstance(raw_address, str):
        return {"address": "", "pincode": None}

    # Normalize whitespace per line, strip each line
    lines = [
        re.sub(r"\s+", " ", line).strip(" ,") for line in raw_address.splitlines() if line.strip()
    ]
    single_line = ", ".join(lines)
    single_line = re.sub(r"\s+", " ", single_line)
    single_line = re.sub(r",\s*,+", ", ", single_line).strip(" ,")

    # Extract 6-digit Indian PIN code (digits 1-9 followed by 5 digits, not preceded/followed by digits)
    pin_match = re.search(r"\b([1-9][0-9]{5})\b", single_line)
    pincode = pin_match.group(1) if pin_match else None

    return {"address": single_line, "pincode": pincode}
