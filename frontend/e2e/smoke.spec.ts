import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe('LegalMetro Shield Smoke Flow', () => {
  test('Complete officer inspection flow: Login -> Scan Upload -> Reports', async ({ page }) => {
    // 1. Visit Login Page
    await page.goto('/login');
    await expect(page.locator('h1')).toContainText('Enforcement Officer Login');

    // 2. Perform Authentication as Inspector
    await page.fill('#email-input', 'inspector@legalmetro.gov.in');
    await page.fill('#password-input', 'InspectorPass123!');
    await page.click('button[type="submit"]');

    // Wait for successful navigation to Dashboard or Scans page
    await page.waitForURL(/\/(dashboard|scans)/, { timeout: 10000 });

    // 3. Navigate to New Scan Page
    await page.goto('/scans/new');
    await expect(page.locator('h1, h2')).toContainText(/New Packaging Scan|Packaged Commodity Compliance Scan/i);

    // 4. Attach image fixture
    const fixturePath = path.join(__dirname, 'fixtures', 'test-pack.png');
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles(fixturePath);

    // Verify thumbnail or file preview appears
    await expect(page.locator('text=test-pack.png')).toBeVisible({ timeout: 5000 });

    // 5. Submit Scan (or verify upload button state)
    const submitBtn = page.locator('button:has-text("Submit Scan for Audit"), button:has-text("Upload & Analyze")').first();
    await expect(submitBtn).toBeEnabled();

    // 6. Navigate to Reports Directory
    await page.goto('/reports');
    await expect(page.locator('h1, h2')).toContainText(/Inspection Reports|Official Compliance Reports/i);
  });
});
