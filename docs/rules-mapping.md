# Legal Metrology (Packaged Commodities) Rules, 2011 — Rules Engine Mapping

This document defines all deterministic compliance rules implemented in **LegalMetro Shield**.
Under the principle **"LLM extracts, code judges"**, Gemini 2.5 Flash and Tesseract OCR extract package text fields,
while these deterministic rules compute every violation, citation, and compliance score.

## Summary Table

| Rule Code | Title | Check Type | Default Severity | Mandatory | Applicable Modes |
|---|---|---|---|---|---|
| `LMPC-R10-1` | **Standard Metric Unit for Net Quantity** | `net_quantity_unit_standard` | `MAJOR` | Yes | retail, wholesale, imported, ecommerce |
| `LMPC-R10-2` | **Net Quantity Placement & Qualifier Prohibition** | `net_quantity_placement` | `MINOR` | Yes | retail, wholesale, imported, ecommerce |
| `LMPC-R11-1` | **Validity of Month and Year of Manufacture / Packing** | `date_valid_not_future` | `CRITICAL` | Yes | retail, wholesale, imported, ecommerce |
| `LMPC-R6-1a` | **Manufacturer / Packer / Importer Name & Address** | `presence` | `CRITICAL` | Yes | retail, wholesale, imported, ecommerce |
| `LMPC-R6-1b-name` | **Common / Generic Name Declaration** | `presence` | `MAJOR` | Yes | retail, wholesale, imported, ecommerce |
| `LMPC-R6-1b-qty` | **Net Quantity Declaration Presence** | `presence` | `CRITICAL` | Yes | retail, wholesale, imported, ecommerce |
| `LMPC-R6-1c` | **Month and Year of Manufacture / Packing / Import** | `presence` | `MAJOR` | Yes | retail, wholesale, imported, ecommerce |
| `LMPC-R6-1d` | **Maximum Retail Price (MRP) Declaration Presence** | `presence` | `CRITICAL` | Yes | retail, imported, ecommerce |
| `LMPC-R6-1e` | **Consumer Care Contact Details** | `presence` | `MAJOR` | Yes | retail, wholesale, imported, ecommerce |
| `LMPC-R6-1f` | **Country of Origin Declaration** | `presence` | `MAJOR` | Yes | retail, wholesale, imported, ecommerce |
| `LMPC-R6-importer` | **Completeness of Importer Declaration for Imported Goods** | `field_pair_match` | `CRITICAL` | Yes | retail, wholesale, imported, ecommerce |
| `LMPC-R9-1a` | **Maximum Retail Price Format & Currency** | `mrp_format` | `CRITICAL` | Yes | retail, imported, ecommerce |
| `LMPC-R9-1b` | **MRP Inclusive of All Taxes Declaration** | `taxes_inclusive_text` | `MAJOR` | Yes | retail, imported, ecommerce |
| `LMPC-R9-3` | **Prohibition of Dual MRP** | `condition` | `CRITICAL` | Yes | retail, imported, ecommerce |
| `LMPC-R9-5` | **Minimum Font Size Compliance (Rule 9(5) Table 1)** | `font_size_surface_area` | `MAJOR` | No | retail, wholesale, imported |
| `LMPC-R9-5-rel` | **Relative Font Legibility & Prominence** | `font_size_relative` | `MINOR` | No | retail, wholesale, imported, ecommerce |

---

## Detailed Rule Definitions & Citations

### `LMPC-R10-1`: Standard Metric Unit for Net Quantity

- **LMPC Citation**: Rule 10(1), Legal Metrology (Packaged Commodities) Rules, 2011: The declaration of quantity shall be expressed in terms of standard units of weight, measure or number (g, kg, ml, l, m, cm, mm, or number/u) with no non-standard symbols or symbols in plural form.
- **Validator**: `net_quantity_unit_standard`
- **Default Severity**: `major`
- **Mandatory**: `True`
- **Applies To**: `['retail', 'wholesale', 'imported', 'ecommerce']`
- **Plain Language Requirement**: Net quantity must be declared using standard metric units without illegal plural symbols (e.g. g not gms, kg not kgs, ml not mls).
- **Parameters**: `{'field': 'net_quantity', 'allowed_units': ['g', 'kg', 'ml', 'l', 'm', 'cm', 'mm', 'u', 'n', 'piece', 'pieces', 'count']}`

### `LMPC-R10-2`: Net Quantity Placement & Qualifier Prohibition

- **LMPC Citation**: Rule 10(2), Legal Metrology (Packaged Commodities) Rules, 2011: The declaration of quantity shall not contain any qualifying words, expressions or symbols at variance with the net quantity, and must be prominently placed.
- **Validator**: `net_quantity_placement`
- **Default Severity**: `minor`
- **Mandatory**: `True`
- **Applies To**: `['retail', 'wholesale', 'imported', 'ecommerce']`
- **Plain Language Requirement**: Net quantity must not include misleading qualifying phrases like 'approx', 'when packed', or 'average'.
- **Parameters**: `{'field': 'net_quantity', 'disallowed_qualifiers': ['approx', 'approx.', 'approximately', 'when packed', 'minimum', 'min.', 'average']}`

### `LMPC-R11-1`: Validity of Month and Year of Manufacture / Packing

- **LMPC Citation**: Rule 11, Legal Metrology (Packaged Commodities) Rules, 2011: Month and year of manufacture or packing shall be valid calendar values and shall not indicate a future date beyond permitted packing allowances.
- **Validator**: `date_valid_not_future`
- **Default Severity**: `critical`
- **Mandatory**: `True`
- **Applies To**: `['retail', 'wholesale', 'imported', 'ecommerce']`
- **Plain Language Requirement**: The manufacturing/packing date must have a valid month (1-12) and year, and must not be post-dated into the future.
- **Parameters**: `{'field': 'mfg_date', 'tolerance_months': 1}`

### `LMPC-R6-1a`: Manufacturer / Packer / Importer Name & Address

- **LMPC Citation**: Rule 6(1)(a), Legal Metrology (Packaged Commodities) Rules, 2011: The name and complete address of the manufacturer, or where manufacturer is not the packer, the name and address of the manufacturer and packer and for any imported package the name and address of the importer shall be declared.
- **Validator**: `presence`
- **Default Severity**: `critical`
- **Mandatory**: `True`
- **Applies To**: `['retail', 'wholesale', 'imported', 'ecommerce']`
- **Plain Language Requirement**: Every packaged commodity must visibly declare the registered name and complete physical address of the manufacturer or packer.
- **Parameters**: `{'field': 'manufacturer_name', 'secondary_field': 'manufacturer_address'}`

### `LMPC-R6-1b-name`: Common / Generic Name Declaration

- **LMPC Citation**: Rule 6(1)(b), Legal Metrology (Packaged Commodities) Rules, 2011: The common or generic names of the commodity contained in the package shall be declared.
- **Validator**: `presence`
- **Default Severity**: `major`
- **Mandatory**: `True`
- **Applies To**: `['retail', 'wholesale', 'imported', 'ecommerce']`
- **Plain Language Requirement**: The generic or common commodity name (e.g. Shampoo, Toothpaste, Coffee) must be declared.
- **Parameters**: `{'field': 'generic_name'}`

### `LMPC-R6-1b-qty`: Net Quantity Declaration Presence

- **LMPC Citation**: Rule 6(1)(b), Legal Metrology (Packaged Commodities) Rules, 2011: The net quantity in terms of standard metric unit of weight or measure shall be declared on every package.
- **Validator**: `presence`
- **Default Severity**: `critical`
- **Mandatory**: `True`
- **Applies To**: `['retail', 'wholesale', 'imported', 'ecommerce']`
- **Plain Language Requirement**: The net quantity of the commodity contained in the package must be prominently declared.
- **Parameters**: `{'field': 'net_quantity'}`

### `LMPC-R6-1c`: Month and Year of Manufacture / Packing / Import

- **LMPC Citation**: Rule 6(1)(c), Legal Metrology (Packaged Commodities) Rules, 2011: The month and year in which the commodity is manufactured or pre-packed or imported shall be declared on every package.
- **Validator**: `presence`
- **Default Severity**: `major`
- **Mandatory**: `True`
- **Applies To**: `['retail', 'wholesale', 'imported', 'ecommerce']`
- **Plain Language Requirement**: Every package must clearly declare the month and year of packaging, manufacture, or import.
- **Parameters**: `{'field': 'mfg_date'}`

### `LMPC-R6-1d`: Maximum Retail Price (MRP) Declaration Presence

- **LMPC Citation**: Rule 6(1)(d), Legal Metrology (Packaged Commodities) Rules, 2011: The maximum retail price at which the commodity in packaged form may be sold to the consumer, inclusive of all taxes, shall be declared.
- **Validator**: `presence`
- **Default Severity**: `critical`
- **Mandatory**: `True`
- **Applies To**: `['retail', 'imported', 'ecommerce']`
- **Plain Language Requirement**: The maximum retail price (MRP) is mandatory on all packaged commodities intended for retail sale.
- **Parameters**: `{'field': 'mrp'}`

### `LMPC-R6-1e`: Consumer Care Contact Details

- **LMPC Citation**: Rule 6(1)(e), Legal Metrology (Packaged Commodities) Rules, 2011: The name, address, telephone number, and e-mail address of the person or the office which may be contacted in case of consumer complaints shall be declared.
- **Validator**: `presence`
- **Default Severity**: `major`
- **Mandatory**: `True`
- **Applies To**: `['retail', 'wholesale', 'imported', 'ecommerce']`
- **Plain Language Requirement**: Consumer redressal details (at least telephone number or email address) must be provided.
- **Parameters**: `{'field': 'consumer_care'}`

### `LMPC-R6-1f`: Country of Origin Declaration

- **LMPC Citation**: Rule 6(1)(f), Legal Metrology (Packaged Commodities) Rules, 2011: The name of the country of origin or manufacture or assembly in case of imported products shall be declared.
- **Validator**: `presence`
- **Default Severity**: `major`
- **Mandatory**: `True`
- **Applies To**: `['retail', 'wholesale', 'imported', 'ecommerce']`
- **Plain Language Requirement**: Country of origin must be declared on every packaged commodity (mandatory for all imported goods).
- **Parameters**: `{'field': 'country_of_origin'}`

### `LMPC-R6-importer`: Completeness of Importer Declaration for Imported Goods

- **LMPC Citation**: Rule 6(1)(a) and Rule 6(1)(f), Legal Metrology (Packaged Commodities) Rules, 2011: For any imported package, the name and complete address of the importer as well as the country of origin shall be declared.
- **Validator**: `field_pair_match`
- **Default Severity**: `critical`
- **Mandatory**: `True`
- **Applies To**: `['retail', 'wholesale', 'imported', 'ecommerce']`
- **Plain Language Requirement**: If the product is imported or country of origin is outside India, both importer name and importer complete address must be declared.
- **Parameters**: `{'condition_field': 'country_of_origin', 'non_domestic_values_exclude': ['india', 'bharat', 'in'], 'required_fields': ['importer_name', 'importer_address']}`

### `LMPC-R9-1a`: Maximum Retail Price Format & Currency

- **LMPC Citation**: Rule 9(1), Legal Metrology (Packaged Commodities) Rules, 2011: The declaration on a package shall contain retail sale price in Indian Rupees (INR or ₹) followed by the actual numerical price.
- **Validator**: `mrp_format`
- **Default Severity**: `critical`
- **Mandatory**: `True`
- **Applies To**: `['retail', 'imported', 'ecommerce']`
- **Plain Language Requirement**: MRP must be a positive numerical value declared in Indian Rupees (₹ or Rs.).
- **Parameters**: `{'field': 'mrp'}`

### `LMPC-R9-1b`: MRP Inclusive of All Taxes Declaration

- **LMPC Citation**: Rule 9(1), Legal Metrology (Packaged Commodities) Rules, 2011: The Maximum Retail Price shall be clearly stated as 'inclusive of all taxes' or 'incl. of all taxes'.
- **Validator**: `taxes_inclusive_text`
- **Default Severity**: `major`
- **Mandatory**: `True`
- **Applies To**: `['retail', 'imported', 'ecommerce']`
- **Plain Language Requirement**: MRP declaration must explicitly include the words 'inclusive of all taxes' or recognized abbreviation.
- **Parameters**: `{'field': 'mrp'}`

### `LMPC-R9-3`: Prohibition of Dual MRP

- **LMPC Citation**: Rule 9(3), Legal Metrology (Packaged Commodities) Rules, 2011: No person shall declare different maximum retail prices on an identical pre-packaged commodity.
- **Validator**: `condition`
- **Default Severity**: `critical`
- **Mandatory**: `True`
- **Applies To**: `['retail', 'imported', 'ecommerce']`
- **Plain Language Requirement**: Declaration of dual or multiple differing MRPs on an identical pre-packaged commodity is strictly prohibited.
- **Parameters**: `{'check_type': 'dual_mrp'}`

### `LMPC-R9-5`: Minimum Font Size Compliance (Rule 9(5) Table 1)

- **LMPC Citation**: Rule 9(5), Legal Metrology (Packaged Commodities) Rules, 2011: The minimum height of any numeral and letter in the declaration shall be as specified in Table 1 according to the area of the principal display panel.
- **Validator**: `font_size_surface_area`
- **Default Severity**: `major`
- **Mandatory**: `False`
- **Applies To**: `['retail', 'wholesale', 'imported']`
- **Plain Language Requirement**: The height of numerals and letters in mandatory declarations must satisfy the minimum prescribed height based on the principal display panel surface area.
- **Parameters**: `{'area_brackets': [{'max_area': 50, 'min_height_mm': 1.0}, {'max_area': 100, 'min_height_mm': 1.5}, {'max_area': 500, 'min_height_mm': 2.5}, {'max_area': 2500, 'min_height_mm': 4.0}, {'max_area': 999999, 'min_height_mm': 6.0}]}`

### `LMPC-R9-5-rel`: Relative Font Legibility & Prominence

- **LMPC Citation**: Rule 9(5), Legal Metrology (Packaged Commodities) Rules, 2011: Declarations shall be conspicuous, legible and presented in appropriate font size proportionate to the display surface.
- **Validator**: `font_size_relative`
- **Default Severity**: `minor`
- **Mandatory**: `False`
- **Applies To**: `['retail', 'wholesale', 'imported', 'ecommerce']`
- **Plain Language Requirement**: Declarations must maintain sufficient character pixel height in the scanned image to ensure clear visual legibility.
- **Parameters**: `{'min_char_height_px': 10.0}`
