# LegalMetro Shield — Enforcement Officer & User Manual

**Target Audience:** Legal Metrology Inspectors, Enforcement Officers, Regional Controllers, System Administrators  
**Applicable Law:** Legal Metrology Act, 2009 & Legal Metrology (Packaged Commodities) Rules, 2011 (LMPC Rules)

---

## 1. Introduction & Overview

**LegalMetro Shield** is a dedicated digital enforcement system designed for Legal Metrology officers to verify statutory compliance on pre-packaged goods sold across retail establishments, wholesale depots, e-commerce fulfilment centres, and customs ports of entry.

The system uses advanced Computer Vision and Vision AI to read packaging declarations and applies deterministic statutory rule algorithms to detect violations such as missing manufacturer credentials, non-standard metric units, missing MRP or tax declarations, prohibited dual pricing, and deceptive net weight declarations.

---

## 2. Progressive Web App (PWA) Setup on Mobile Devices

Inspectors can install LegalMetro Shield directly on their official Android or iOS smartphones without going through an app store.

### Installation on Android (Chrome)
1. Open Google Chrome and navigate to the portal URL (`https://legalmetro.gov.in`).
2. A prompt will appear at the bottom: **"Install LegalMetro Shield"**. Tap **Install**.
3. Alternatively, tap the Chrome menu (three vertical dots) $\to$ select **"Add to Home screen"** or **"Install app"**.
4. An official LegalMetro icon will appear on your phone's home screen.

### Installation on iOS (Safari)
1. Open Safari and navigate to the portal URL.
2. Tap the **Share** button (square with arrow pointing up) at the bottom toolbar.
3. Scroll down and tap **"Add to Home Screen"**.
4. Tap **Add** in the upper-right corner.

---

## 3. Conducting an Inspection Scan

### Step 1: Login to the Portal
1. Launch the app from your home screen or browser.
2. Enter your registered official email (e.g. `inspector@legalmetro.gov.in`) and password.
3. Tap **"Sign In to Enforcement Portal"**.

### Step 2: Navigate to "New Scan"
1. In the bottom navigation bar (mobile) or left sidebar (desktop), tap **"New Scan"**.
2. Select the **Inspection Mode**:
   - **Retail Packaging**: Standard domestic consumer goods sold in shops.
   - **Wholesale / Bulk**: Goods intended for distributors or commercial packaging.
   - **Imported Goods**: Verifies Country of Origin and mandatory Importer Address declarations.
   - **E-Commerce Commodity**: Verifies digital declarations or delivered packaging.

### Step 3: Capture Commodity Packaging Photos
1. Tap **"Use Device Camera"** to open your phone's camera directly.
2. Take clear, well-lit photos of the packaging:
   - **Front Face**: Brand name, generic commodity name, declared net weight/volume.
   - **Back / Side Panel**: Manufacturer and packer name & address, consumer care details, manufacturing month/year.
   - **Price Marking Area**: MRP stamp, unit sale price, batch/lot number, barcode.
3. You may attach up to **6 photos** per scan. Ensure text is in focus and not obscured by glare or fingers.

### Step 4: Offline Inspection in Low-Connectivity Zones
- If you are inspecting a remote shop or basement warehouse with **no internet connectivity**:
  - The top banner will display an orange badge: **"Offline Mode — Scans will be queued locally"**.
  - Tap **"Queue Scan in Offline Outbox"**.
  - Your scan is safely saved in your phone's local IndexedDB encrypted storage.
  - As soon as your device reconnects to 4G/Wi-Fi, the system **automatically uploads all pending scans** and alerts you with the completed inspection IDs.

---

## 5. Reviewing Results & Statutory Violations

Once uploaded, the automated pipeline completes within 3 to 6 seconds:

1. **Overall Compliance Score & Verdict**:
   - **COMPLIANT** (Green Stamp, Score $\ge 85$): All statutory declarations are present and compliant with LMPC 2011.
   - **NON-COMPLIANT** (Red Stamp, Score $< 60$ or Critical Violation): One or more statutory violations detected.
   - **NEEDS REVIEW** (Amber Stamp): Low lighting, obscured text, or borderline measurement requiring manual inspection.

2. **Interactive Bounding Box Overlay**:
   - Tap on any extracted field (e.g. `Net Quantity: 500 g`) to highlight the exact bounding box on the product photo where the AI extracted the text.

3. **Statutory Violations Table**:
   - Each violation provides:
     - **Rule Code**: e.g. `LMPC-R9-1b`
     - **Legal Citation**: e.g. *Rule 9(1), Legal Metrology (Packaged Commodities) Rules, 2011*
     - **Severity Level**: Critical (Immediate Compound Notice), Major, or Minor.
     - **Observed vs Statutory Requirement**: Explains exactly why the declaration failed (e.g. *Observed: 'Rs. 250' — Missing mandatory phrase '(inclusive of all taxes)'*).

---

## 6. Manual Override & Field Correction Workflow

In situations where a statutory exemption applies (e.g. package under 10 grams exempted under Rule 26) or OCR misread a stylistic font:

1. On the **Scan Detail** page, scroll to the **Statutory Violations** section.
2. Click **"Override Violation"** on the specific violation card.
3. Check **"Mark as Overridden / Exemption Granted"**.
4. Enter a **Mandatory Written Justification** (minimum 10 characters), citing the applicable exemption (e.g. *"Exemption granted under Rule 26 — package net content is 5g"*).
5. Click **"Save Override & Recalculate"**.
6. The compliance score and verdict will immediately recalculate, and the override with your officer ID is permanently logged in the **Audit Trail**.

---

## 7. Generating & Printing Official Inspection Reports

To issue a statutory notice or seizure memo:

1. On the top right of the **Scan Detail** page, click **"Generate Official Notice"**.
2. The system compiles a gazette-standard PDF featuring:
   - Ashok Stambh National Emblem & Ministry of Consumer Affairs header.
   - Date, District, and Inspecting Officer attestation block.
   - Product photo and barcode.
   - Complete Rule 6(1) declarations audit matrix.
   - Statutory violations table with sections and compounding penalties.
3. Click **"Download Official PDF"** or **"Download DOCX"** to download the document via a secure 5-minute presigned URL.
4. The downloaded notice can be printed directly or attached to departmental case files.

---

## 8. Administrator Management & Security

### Managing Officer Accounts
- Administrators can navigate to **Admin $\to$ Users Management** to:
  - Approve pending viewer/inspector self-registrations.
  - Promote officers to `inspector` or `admin`.
  - Deactivate transferred or retired personnel immediately.

### Audit Log Inspection
- Navigate to **Admin $\to$ Audit Logs** to review an unalterable log of:
  - User logins and failed password attempts.
  - Violation overrides and justifications.
  - Report downloads and data exports.
