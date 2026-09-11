import asyncio
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.product import Product
from app.models.report import Report
from app.models.scan import Scan
from app.models.user import User
from app.models.violation import Violation

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
        "name": "Public Viewer Verma",
        "email": "viewer@legalmetro.gov.in",
        "password": "ViewerPass123!",
        "role": "viewer",
        "district": "South Delhi",
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
        "name": "Officer Ananya Hegde",
        "email": "inspector.bengaluru@legalmetro.gov.in",
        "password": "InspectorPass123!",
        "role": "inspector",
        "district": "Bengaluru Urban",
        "state": "Karnataka",
    },
    {
        "name": "Officer Subhashish Bose",
        "email": "inspector.kolkata@legalmetro.gov.in",
        "password": "InspectorPass123!",
        "role": "inspector",
        "district": "Kolkata",
        "state": "West Bengal",
    },
    {
        "name": "Officer Meenakshi Sundaram",
        "email": "inspector.chennai@legalmetro.gov.in",
        "password": "InspectorPass123!",
        "role": "inspector",
        "district": "Chennai",
        "state": "Tamil Nadu",
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
    # Repeat Offender Commodity
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


async def seed_all():
    print("Starting LegalMetro Shield Demo Data Seeder...")
    now = datetime.now(UTC)

    async with AsyncSessionLocal() as session:
        # 1. Seed / Upsert Users
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
                user.password_hash = get_password_hash(u_data["password"])
                await session.flush()
            users_by_email[u_data["email"]] = user

        inspectors = [u for u in users_by_email.values() if u.role == "inspector"]

        # 2. Seed / Upsert Products
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
            products_by_barcode[p_data["barcode"]] = prod

        # 3. Seed Scans across the past 90 days
        print("  [*] Seeding 70+ chronological scans and violations...")
        repeat_offender_prod = products_by_barcode["8909999000011"]

        # Deliberate repeat offender scans for Royal Herbal
        repeat_dates = [now - timedelta(days=d) for d in [65, 45, 25, 8]]
        for _idx, scan_date in enumerate(repeat_dates):
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

            # Add recurring violations: LMPC-R9-1 and LMPC-R6-1d
            v1_t = next(t for t in VIOLATION_TEMPLATES if t["rule_code"] == "LMPC-R9-1")
            v2_t = next(t for t in VIOLATION_TEMPLATES if t["rule_code"] == "LMPC-R6-1d")
            session.add(
                Violation(
                    scan_id=r_scan.id,
                    rule_code=v1_t["rule_code"],
                    rule_title=v1_t["rule_title"],
                    citation=v1_t["citation"],
                    severity=v1_t["severity"],
                    field_name=v1_t["field_name"],
                    observed_value=v1_t["observed"],
                    expected_value=v1_t["expected"],
                )
            )
            session.add(
                Violation(
                    scan_id=r_scan.id,
                    rule_code=v2_t["rule_code"],
                    rule_title=v2_t["rule_title"],
                    citation=v2_t["citation"],
                    severity=v2_t["severity"],
                    field_name=v2_t["field_name"],
                    observed_value=v2_t["observed"],
                    expected_value=v2_t["expected"],
                )
            )

        # Distribute remaining scans across all other products
        modes = ["retail", "retail", "retail", "wholesale", "imported", "ecommerce"]
        other_products = [
            p for p in products_by_barcode.values() if p.id != repeat_offender_prod.id
        ]

        for day_offset in range(1, 85):
            # 1 to 2 scans per day
            num_scans_today = random.choices([1, 2, 3], weights=[0.5, 0.35, 0.15])[0]
            for _ in range(num_scans_today):
                prod = random.choice(other_products)
                insp = random.choice(inspectors)
                scan_dt = now - timedelta(
                    days=day_offset, hours=random.randint(1, 18), minutes=random.randint(0, 59)
                )
                mode = random.choice(modes)

                # 70% compliant, 20% non_compliant, 10% needs_review
                verdict_roll = random.random()
                if verdict_roll < 0.70:
                    verdict = "compliant"
                    score = round(random.uniform(92.0, 100.0), 1)
                    status = "completed"
                    scan_viols = []
                elif verdict_roll < 0.90:
                    verdict = "non_compliant"
                    score = round(random.uniform(35.0, 75.0), 1)
                    status = "completed"
                    # 1 to 3 violations
                    num_v = random.randint(1, 3)
                    scan_viols = random.sample(VIOLATION_TEMPLATES, num_v)
                else:
                    verdict = "needs_review"
                    score = round(random.uniform(55.0, 85.0), 1)
                    status = "needs_review"
                    scan_viols = random.sample(VIOLATION_TEMPLATES, 1)

                scan = Scan(
                    product_id=prod.id,
                    scanned_by=insp.id,
                    mode=mode,
                    image_urls=["https://storage.legalmetro.gov.in/scans/sample_label.jpg"],
                    status=status,
                    verdict=verdict,
                    compliance_score=score,
                    font_check_mode="relative",
                    scanned_at=scan_dt,
                )
                session.add(scan)
                await session.flush()

                for vt in scan_viols:
                    is_overridden = random.random() < 0.10  # 10% overridden
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
                            override_reason="Exemption approved by inspector under Rule 26."
                            if is_overridden
                            else None,
                        )
                    )

        # 4. Seed 6 Sample Reports
        res_scans = await session.execute(select(Scan).order_by(Scan.scanned_at.desc()).limit(6))
        recent_scans = res_scans.scalars().all()
        for s in recent_scans:
            report = Report(
                scan_id=s.id,
                generated_by=s.scanned_by,
                pdf_url=f"/api/v1/reports/downloads/{s.id}.pdf",
                docx_url=f"/api/v1/reports/downloads/{s.id}.docx",
                generated_at=s.scanned_at + timedelta(minutes=15),
            )
            session.add(report)

        await session.commit()
        print("  [✓] Demo data successfully seeded!")


if __name__ == "__main__":
    asyncio.run(seed_all())
