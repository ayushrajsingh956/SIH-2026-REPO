import asyncio
import logging
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.product import Product
from app.models.report import Report
from app.models.scan import Scan
from app.models.user import User
from app.models.violation import Violation

logger = logging.getLogger(__name__)

USERS_DATA = [
    {
        "name": "Super Admin",
        "email": "admin@legalmetro.gov.in",
        "password": "AdminPass123!",
        "role": "admin",
        "district": "Central Delhi",
        "state": "Delhi",
    },
    {
        "name": "Senior Inspector Sharma",
        "email": "inspector@legalmetro.gov.in",
        "password": "InspectorPass123!",
        "role": "inspector",
        "district": "North Delhi",
        "state": "Delhi",
    },
    {
        "name": "Officer Rajesh Kadam",
        "email": "inspector.mumbai@legalmetro.gov.in",
        "password": "InspectorPass123!",
        "role": "inspector",
        "district": "Mumbai Suburban",
        "state": "Maharashtra",
    },
    {
        "name": "Public Viewer Verma",
        "email": "viewer@legalmetro.gov.in",
        "password": "ViewerPass123!",
        "role": "viewer",
        "district": "South Delhi",
        "state": "Delhi",
    },
]

PRODUCTS_DATA = [
    {
        "name": "Tata Tea Gold 500g",
        "brand": "Tata Tea",
        "manufacturer": "Tata Consumer Products Ltd",
        "category": "Beverages",
        "barcode": "8901052001018",
    },
    {
        "name": "Amul Pure Ghee 1L Tin",
        "brand": "Amul",
        "manufacturer": "GCMMF Ltd",
        "category": "Dairy",
        "barcode": "8901262010015",
    },
    {
        "name": "Parle-G Gold Biscuits 100g",
        "brand": "Parle-G",
        "manufacturer": "Parle Products Pvt Ltd",
        "category": "Bakery",
        "barcode": "8901719102011",
    },
    {
        "name": "Dabur Honey 250g Glass Jar",
        "brand": "Dabur",
        "manufacturer": "Dabur India Limited",
        "category": "Health Foods",
        "barcode": "8901207011021",
    },
    {
        "name": "Haldiram's Nagpur Aloo Bhujia 400g",
        "brand": "Haldiram's",
        "manufacturer": "Haldiram Foods International",
        "category": "Snacks",
        "barcode": "8904004401052",
    },
    {
        "name": "Himalaya Purifying Neem Face Wash 150ml",
        "brand": "Himalaya",
        "manufacturer": "Himalaya Wellness Company",
        "category": "Personal Care",
        "barcode": "8901138820012",
    },
    {
        "name": "Patanjali Kesh Kanti Hair Oil 200ml",
        "brand": "Patanjali",
        "manufacturer": "Patanjali Ayurved Ltd",
        "category": "Personal Care",
        "barcode": "8904109405014",
    },
    {
        "name": "Fortune Sunlite Refined Sunflower Oil 1L",
        "brand": "Fortune",
        "manufacturer": "Adani Wilmar Ltd",
        "category": "Edible Oils",
        "barcode": "8906007281013",
    },
    {
        "name": "Aashirvaad Shudh Chakki Atta 5kg",
        "brand": "Aashirvaad",
        "manufacturer": "ITC Limited",
        "category": "Staples",
        "barcode": "8901725131012",
    },
    {
        "name": "Britannia Good Day Butter Cookies 200g",
        "brand": "Britannia",
        "manufacturer": "Britannia Industries Ltd",
        "category": "Bakery",
        "barcode": "8901063102018",
    },
    {
        "name": "Nescafe Classic Coffee 100g Jar",
        "brand": "Nescafe",
        "manufacturer": "Nestle India Ltd",
        "category": "Beverages",
        "barcode": "8901058852010",
    },
    {
        "name": "Colgate MaxFresh Blue Gel 150g",
        "brand": "Colgate",
        "manufacturer": "Colgate-Palmolive India Ltd",
        "category": "Oral Care",
        "barcode": "8901314010017",
    },
    {
        "name": "Saffola Gold Pro Healthy Heart 1L",
        "brand": "Saffola",
        "manufacturer": "Marico Limited",
        "category": "Edible Oils",
        "barcode": "8901088012019",
    },
    {
        "name": "VVD Gold Pure Coconut Oil 500ml",
        "brand": "VVD Gold",
        "manufacturer": "VVD & Sons Pvt Ltd",
        "category": "Hair Care",
        "barcode": "8901234005011",
    },
    {
        "name": "Royal Herbal Ayurvedic Hair Tonic 200ml",
        "brand": "Royal Herbal",
        "manufacturer": "Royal Herbs Remedies Pvt Ltd",
        "category": "Personal Care",
        "barcode": "8909999000011",
    },
]

VIOLATION_TEMPLATES = [
    {
        "rule_code": "LMPC-R6-1a",
        "rule_title": "Mandatory Manufacturer / Packer Name and Address",
        "citation": "Rule 6(1)(a), LMPC Rules 2011",
        "severity": "critical",
        "field_name": "manufacturer_name",
        "observed": "Marketed by Royal Herbs (No packer address)",
        "expected": "Complete physical address with city and PIN code",
    },
    {
        "rule_code": "LMPC-R6-1b",
        "rule_title": "Net Quantity Declaration and Standard Units",
        "citation": "Rule 6(1)(b) read with Rule 10, LMPC Rules 2011",
        "severity": "critical",
        "field_name": "net_quantity",
        "observed": "500 MLTS",
        "expected": "500 ml or 500 mL in standard metric units",
    },
    {
        "rule_code": "LMPC-R6-1c",
        "rule_title": "Month and Year of Manufacture / Packing",
        "citation": "Rule 6(1)(c), LMPC Rules 2011",
        "severity": "major",
        "field_name": "mfg_date",
        "observed": "Missing packing month/year",
        "expected": "MM/YYYY format or Month and Year",
    },
    {
        "rule_code": "LMPC-R6-1d",
        "rule_title": "Consumer Care Details Completeness",
        "citation": "Rule 6(1)(d), LMPC Rules 2011",
        "severity": "major",
        "field_name": "consumer_care",
        "observed": "Telephone only (No email or address)",
        "expected": "Name, address, phone number and email of grievance officer",
    },
    {
        "rule_code": "LMPC-R9-1",
        "rule_title": "Maximum Retail Price (MRP) Statutory Formatting",
        "citation": "Rule 9(1), LMPC Rules 2011",
        "severity": "critical",
        "field_name": "mrp",
        "observed": "Rs. 250 (Missing 'inclusive of all taxes')",
        "expected": "Maximum Retail Price ₹ 250.00 (inclusive of all taxes) or MRP incl. of all taxes",
    },
    {
        "rule_code": "LMPC-R9-5",
        "rule_title": "Minimum Font Size for Mandatory Declarations",
        "citation": "Rule 9(5) Table, LMPC Rules 2011",
        "severity": "minor",
        "field_name": "net_quantity",
        "observed": "Height 1.4 mm (Declared weight 500g)",
        "expected": "Minimum numeral height 4.0 mm for net quantity 200g - 1kg",
    },
    {
        "rule_code": "LMPC-R10-1",
        "rule_title": "Standard Metric Measurement Units",
        "citation": "Rule 10, LMPC Rules 2011",
        "severity": "major",
        "field_name": "net_quantity",
        "observed": "Weight: 16 Ounces / 1 Lbs",
        "expected": "Standard metric unit (g, kg, ml, l)",
    },
    {
        "rule_code": "LMPC-R11-1",
        "rule_title": "Future Dated Packing Prohibition",
        "citation": "Rule 11, LMPC Rules 2011",
        "severity": "major",
        "field_name": "mfg_date",
        "observed": "Mfg Date: 12/2028 (Exceeds maximum allowable future dating)",
        "expected": "Current or prior calendar month",
    },
]


async def seed_data():
    now = datetime.now(UTC)
    print("🌱 [LegalMetro] Running idempotent database seeder...")

    async with AsyncSessionLocal() as session:
        # 1. Seed Users
        users_by_email = {}
        for u_data in USERS_DATA:
            res = await session.execute(select(User).where(User.email == u_data["email"]))
            user = res.scalar_one_or_none()
            if not user:
                user = User(
                    name=u_data["name"],
                    email=u_data["email"],
                    password_hash=get_password_hash(u_data["password"]),
                    role=u_data["role"],
                    district=u_data["district"],
                    state=u_data["state"],
                    is_active=True,
                )
                session.add(user)
                await session.flush()
                print(f"  [+] Created user: {u_data['email']} ({u_data['role']})")
            else:
                user.name = u_data["name"]
                user.district = u_data["district"]
                user.state = u_data["state"]
                user.role = u_data["role"]
                user.is_active = True
                user.password_hash = get_password_hash(u_data["password"])
                await session.flush()
                print(f"  [*] Verified user: {u_data['email']} ({u_data['role']})")
            users_by_email[u_data["email"]] = user

        inspectors = [u for u in users_by_email.values() if u.role == "inspector"]

        # 2. Seed Products
        products_by_barcode = {}
        for p_data in PRODUCTS_DATA:
            res = await session.execute(select(Product).where(Product.barcode == p_data["barcode"]))
            prod = res.scalar_one_or_none()
            if not prod:
                days_ago = random.randint(30, 80)
                prod = Product(
                    name=p_data["name"],
                    brand=p_data["brand"],
                    manufacturer_name=p_data["manufacturer"],
                    category=p_data["category"],
                    barcode=p_data["barcode"],
                    gtin=p_data["barcode"],
                    first_scanned=now - timedelta(days=days_ago),
                )
                session.add(prod)
                await session.flush()
                print(f"  [+] Created product: {p_data['name']}")
            else:
                print(f"  [*] Verified product: {p_data['name']}")
            products_by_barcode[p_data["barcode"]] = prod

        # 3. Check existing scans count for idempotency
        scan_count_res = await session.execute(select(func.count(Scan.id)))
        total_scans = scan_count_res.scalar_one() or 0

        if total_scans >= 40:
            print(f"  [*] Database already contains {total_scans} scans. Skipping scan generation.")
        else:
            print(f"  [*] Current scans: {total_scans}. Generating scans to reach ~45 scans...")
            repeat_offender_prod = products_by_barcode["8909999000011"]

            # Repeat offender scans
            repeat_dates = [now - timedelta(days=d) for d in [65, 45, 25, 8]]
            for scan_date in repeat_dates:
                insp = random.choice(inspectors)
                r_scan = Scan(
                    product_id=repeat_offender_prod.id,
                    scanned_by=insp.id,
                    mode="retail",
                    image_urls=["https://storage.legalmetro.gov.in/scans/sample_royal_herbal.jpg"],
                    status="completed",
                    verdict="non_compliant",
                    compliance_score=45.0,
                    font_check_mode="relative",
                    scanned_at=scan_date,
                )
                session.add(r_scan)
                await session.flush()

                v1_t = next(t for t in VIOLATION_TEMPLATES if t["rule_code"] == "LMPC-R9-1")
                v2_t = next(t for t in VIOLATION_TEMPLATES if t["rule_code"] == "LMPC-R6-1d")
                for vt in [v1_t, v2_t]:
                    session.add(
                        Violation(
                            scan_id=r_scan.id,
                            rule_code=vt["rule_code"],
                            rule_title=vt["rule_title"],
                            citation=vt["citation"],
                            severity=vt["severity"],
                            field_name=vt["field_name"],
                            observed_value=vt["observed"],
                            expected_value=vt["expected"],
                        )
                    )

            modes = ["retail", "retail", "wholesale", "imported", "ecommerce"]
            other_products = [
                p for p in products_by_barcode.values() if p.id != repeat_offender_prod.id
            ]

            # Generate ~40 scans across products
            for _i in range(40):
                prod = random.choice(other_products)
                insp = random.choice(inspectors)
                days_back = random.randint(1, 60)
                scan_dt = now - timedelta(days=days_back, hours=random.randint(1, 12))
                mode = random.choice(modes)

                roll = random.random()
                if roll < 0.65:
                    verdict = "compliant"
                    score = round(random.uniform(90.0, 100.0), 1)
                    status_val = "completed"
                    viols = []
                elif roll < 0.85:
                    verdict = "non_compliant"
                    score = round(random.uniform(40.0, 75.0), 1)
                    status_val = "completed"
                    viols = random.sample(VIOLATION_TEMPLATES, random.randint(1, 3))
                else:
                    verdict = "needs_review"
                    score = round(random.uniform(60.0, 85.0), 1)
                    status_val = "needs_review"
                    viols = random.sample(VIOLATION_TEMPLATES, 1)

                scan = Scan(
                    product_id=prod.id,
                    scanned_by=insp.id,
                    mode=mode,
                    image_urls=["https://storage.legalmetro.gov.in/scans/sample_label.jpg"],
                    status=status_val,
                    verdict=verdict,
                    compliance_score=score,
                    font_check_mode="relative",
                    scanned_at=scan_dt,
                )
                session.add(scan)
                await session.flush()

                for vt in viols:
                    is_overridden = random.random() < 0.08
                    session.add(
                        Violation(
                            scan_id=scan.id,
                            rule_code=vt["rule_code"],
                            rule_title=vt["rule_title"],
                            citation=vt["citation"],
                            severity=vt["severity"],
                            field_name=vt["field_name"],
                            observed_value=vt["observed"],
                            expected_value=vt["expected"],
                            overridden=is_overridden,
                            override_reason="Exemption approved by inspecting officer."
                            if is_overridden
                            else None,
                        )
                    )

        # 4. Seed Reports for recent completed scans if needed
        report_count_res = await session.execute(select(func.count(Report.id)))
        report_count = report_count_res.scalar_one() or 0
        if report_count < 6:
            recent_scans_res = await session.execute(
                select(Scan)
                .where(Scan.status == "completed")
                .order_by(Scan.scanned_at.desc())
                .limit(6)
            )
            for s in recent_scans_res.scalars().all():
                rep_res = await session.execute(select(Report).where(Report.scan_id == s.id))
                if not rep_res.scalar_one_or_none():
                    session.add(
                        Report(
                            scan_id=s.id,
                            generated_by=s.scanned_by,
                            pdf_url=f"/api/v1/reports/downloads/{s.id}.pdf",
                            docx_url=f"/api/v1/reports/downloads/{s.id}.docx",
                            generated_at=s.scanned_at + timedelta(minutes=10),
                        )
                    )
            print("  [+] Generated sample inspection reports.")

        await session.commit()
        print("✅ [LegalMetro] Database seeding completed successfully!")


def main():
    asyncio.run(seed_data())


if __name__ == "__main__":
    main()
