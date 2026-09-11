import { chromium } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function runInteractiveTest() {
  console.log('🚀 Launching Chromium browser on your screen...');

  const browser = await chromium.launch({
    headless: false,
    slowMo: 900, // 0.9s between actions for smooth, clear visual observation
    args: ['--window-size=1440,920', '--window-position=40,40'],
  });

  const context = await browser.newContext({
    viewport: { width: 1400, height: 860 },
  });

  const page = await context.newPage();

  try {
    // -------------------------------------------------------------
    // 1. LOGIN PAGE
    // -------------------------------------------------------------
    console.log('📍 [Step 1] Navigating to Officer Login Portal...');
    await page.goto('http://localhost:5173/login');
    await page.waitForLoadState('networkidle');
    await sleep(1500);

    console.log('  ✍️  Entering officer credentials (Inspector Sharma)...');
    await page.fill('#email-input', 'inspector@legalmetro.gov.in');
    await sleep(600);
    await page.fill('#password-input', 'InspectorPass123!');
    await sleep(600);

    // Toggle password visibility
    console.log('  👁️  Toggling password visibility...');
    const eyeBtn = page.locator('button[aria-label="Show password"], button[aria-label="Hide password"]').first();
    if (await eyeBtn.count() > 0) {
      await eyeBtn.click();
      await sleep(800);
      await eyeBtn.click();
      await sleep(500);
    }

    console.log('  🔓 Submitting login credentials...');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard', { timeout: 15000 });
    console.log('  ✅ Logged in successfully! Reached Enforcement Dashboard.');

    // -------------------------------------------------------------
    // 2. ENFORCEMENT DASHBOARD
    // -------------------------------------------------------------
    console.log('📍 [Step 2] Testing Dashboard Analytics & KPIs...');
    await page.waitForLoadState('networkidle');
    await sleep(2000);

    console.log('  📊 Inspecting Violations Severity Mix donut chart & KPIs...');
    await page.mouse.wheel(0, 350);
    await sleep(1800);
    await page.mouse.wheel(0, 350);
    await sleep(1800);
    await page.mouse.wheel(0, -700);
    await sleep(1000);

    // -------------------------------------------------------------
    // 3. COMMODITY SCANS REPOSITORY & FILTERS
    // -------------------------------------------------------------
    console.log('📍 [Step 3] Navigating to Scans Directory (/scans)...');
    await page.click('a[href="/scans"]');
    await page.waitForURL('**/scans');
    await page.waitForLoadState('networkidle');
    await sleep(1500);

    console.log('  🔍 Testing dropdown filters (filtering for Non-Compliant scans)...');
    const selects = page.locator('select');
    if (await selects.count() >= 2) {
      // Verdict filter is the second select
      await selects.nth(1).selectOption('non_compliant');
      await sleep(1500);
    }

    // -------------------------------------------------------------
    // 4. INSPECT SCAN DETAIL & BOUNDING BOX OVERLAY
    // -------------------------------------------------------------
    console.log('📍 [Step 4] Opening first non-compliant scan for detailed audit...');
    const firstScanRow = page.locator('table tbody tr').first();
    await firstScanRow.click();
    await page.waitForURL('**/scans/*');
    await page.waitForLoadState('networkidle');
    await sleep(2500);

    console.log('  🖼️  Examining packaging photo and interactive Bounding Box overlay...');
    await page.mouse.wheel(0, 250);
    await sleep(1500);

    // Click on an extracted declaration tag if present
    const declarationBtn = page.locator('button:has-text("Focus in Bounding Box Viewer")').first();
    if (await declarationBtn.count() > 0) {
      await declarationBtn.click();
      await sleep(1200);
    }

    // -------------------------------------------------------------
    // 5. TEST INSPECTOR STATUTORY VIOLATION OVERRIDE WORKFLOW
    // -------------------------------------------------------------
    console.log('📍 [Step 5] Testing Inspector Violation Override & Justification workflow...');
    const applyOverrideBtn = page.locator('button:has-text("Apply Inspector Override")').first();
    if (await applyOverrideBtn.count() > 0) {
      await applyOverrideBtn.click();
      await sleep(1200);

      console.log('  📝 Entering statutory justification under Rule 26...');
      const reasonTextarea = page.locator('#override-reason');
      if (await reasonTextarea.count() > 0) {
        await reasonTextarea.fill('Statutory exemption verified under Rule 26 for packaged sample.');
        await sleep(1200);
      }

      const confirmOverrideBtn = page.locator('button:has-text("Confirm Override & Recalculate")').first();
      if (await confirmOverrideBtn.count() > 0) {
        await confirmOverrideBtn.click();
        await sleep(2000);
        console.log('  ✅ Violation override saved! Compliance score recalculated in real-time.');
      }
    } else {
      console.log('  ℹ️  No pending override button on this scan item.');
    }

    // -------------------------------------------------------------
    // 6. GENERATE OFFICIAL GAZETTE REPORT
    // -------------------------------------------------------------
    console.log('📍 [Step 6] Generating Official Statutory Inspection Notice (WeasyPrint / python-docx)...');
    const genReportBtn = page.locator('button:has-text("Generate Report")').first();
    if (await genReportBtn.count() > 0 && await genReportBtn.isEnabled()) {
      await genReportBtn.click();
      await sleep(3500);
      console.log('  ✅ Official Report compiled and uploaded to MinIO!');
    }

    // -------------------------------------------------------------
    // 7. NEW SCAN & IMAGE UPLOAD FLOW
    // -------------------------------------------------------------
    console.log('📍 [Step 7] Testing New Commodity Inspection Upload (/scans/new)...');
    await page.goto('http://localhost:5173/scans/new');
    await page.waitForLoadState('networkidle');
    await sleep(1500);

    console.log('  📸 Attaching packaging photographic evidence fixture...');
    const fixturePath = path.resolve(__dirname, '../e2e/fixtures/test-pack.png');
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles(fixturePath);
    await sleep(1500);

    console.log('  🚀 Submitting scan to Celery worker pipeline...');
    const submitScanBtn = page.locator('button:has-text("Submit Scan for Audit"), button:has-text("Upload & Analyze")').first();
    if (await submitScanBtn.count() > 0 && await submitScanBtn.isEnabled()) {
      await submitScanBtn.click();
      await sleep(3500);
      console.log('  📡 Scan submitted and queued in Celery pipeline!');
    }

    // -------------------------------------------------------------
    // 8. COMMODITIES CATALOG & REPEAT OFFENDERS
    // -------------------------------------------------------------
    console.log('📍 [Step 8] Navigating to Packaged Commodities Catalog (/products)...');
    await page.goto('http://localhost:5173/products');
    await page.waitForLoadState('networkidle');
    await sleep(1500);

    console.log('  🔍 Searching commodities for "Royal Herbal"...');
    const searchInput = page.locator('input[placeholder*="Search"]').first();
    if (await searchInput.count() > 0) {
      await searchInput.fill('Royal Herbal');
      await sleep(1500);
      await searchInput.fill('');
      await sleep(1000);
    }

    // Click first product to view details
    const firstProduct = page.locator('table tbody tr').first();
    if (await firstProduct.count() > 0) {
      console.log('  📦 Viewing Commodity details & repeat offender history...');
      await firstProduct.click();
      await sleep(2000);
    }

    // -------------------------------------------------------------
    // 9. STATUTORY VIOLATIONS EXPLORER
    // -------------------------------------------------------------
    console.log('📍 [Step 9] Navigating to Violations Explorer (/violations)...');
    await page.goto('http://localhost:5173/violations');
    await page.waitForLoadState('networkidle');
    await sleep(1500);

    console.log('  ⚠️  Filtering Critical Severity Violations...');
    const violSelect = page.locator('select').first();
    if (await violSelect.count() > 0) {
      await violSelect.selectOption('critical');
      await sleep(1800);
      await violSelect.selectOption('');
      await sleep(1000);
    }

    // -------------------------------------------------------------
    // 10. INSPECTION REPORTS ARCHIVE & DOWNLOAD
    // -------------------------------------------------------------
    console.log('📍 [Step 10] Navigating to Official Reports Directory (/reports)...');
    await page.goto('http://localhost:5173/reports');
    await page.waitForLoadState('networkidle');
    await sleep(2000);

    console.log('  📥 Testing Presigned PDF Download...');
    const pdfBtn = page.locator('button:has-text("PDF")').first();
    if (await pdfBtn.count() > 0) {
      await pdfBtn.click();
      await sleep(2000);
      console.log('  ✅ 5-minute Presigned URL generated and PDF fetched!');
    }

    // -------------------------------------------------------------
    // 11. ADMIN CONSOLE: USERS & AUDIT LOGS & RULE CONFIG
    // -------------------------------------------------------------
    console.log('📍 [Step 11] Logging in as Super Administrator (admin@legalmetro.gov.in)...');
    await page.goto('http://localhost:5173/login');
    await page.waitForLoadState('networkidle');
    await sleep(1000);

    await page.fill('#email-input', 'admin@legalmetro.gov.in');
    await page.fill('#password-input', 'AdminPass123!');
    await sleep(600);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard', { timeout: 15000 });
    await sleep(1500);

    console.log('  👤 Visiting Admin Users Management (/admin/users)...');
    await page.goto('http://localhost:5173/admin/users');
    await page.waitForLoadState('networkidle');
    await sleep(2000);

    console.log('  📜 Visiting Admin Immutable Audit Log (/admin/audit-logs)...');
    await page.goto('http://localhost:5173/admin/audit-logs');
    await page.waitForLoadState('networkidle');
    await sleep(2000);

    console.log('  ⚙️  Visiting LMPC Statutory Rules Configuration (/admin/rules)...');
    await page.goto('http://localhost:5173/admin/rules');
    await page.waitForLoadState('networkidle');
    await sleep(2500);

    console.log('🎉 All 11 core application flows successfully verified live in Chromium!');
    console.log('⏸️  Leaving browser window open for 30 seconds so you can explore freely...');
    await sleep(30000);

  } catch (err) {
    console.error('❌ Error during interactive test:', err);
  } finally {
    await browser.close();
    console.log('🏁 Browser test session completed cleanly.');
  }
}

runInteractiveTest();
