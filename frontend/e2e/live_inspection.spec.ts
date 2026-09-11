import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const artifactDir = '/Users/vikranty/.gemini/antigravity/brain/9ae38b47-c322-482f-a67c-7d2c082026c1';

test.describe('Live Visual Inspection & End-to-End Verification', () => {
  test('Inspect Dashboard UI Charts and verify complete workflow', async ({ page }) => {
    // 1. Visit Login Page
    await page.goto('/login');
    await expect(page.locator('h1')).toContainText('Enforcement Officer Login');
    await page.waitForTimeout(1000);

    // 2. Perform Authentication as Admin
    await page.fill('#email-input', 'admin@legalmetro.gov.in');
    await page.fill('#password-input', 'AdminPass123!');
    await page.click('button[type="submit"]');

    // Wait for Dashboard
    await page.waitForURL(/\/dashboard/, { timeout: 15000 });
    await expect(page.locator('h1')).toContainText('Compliance Analytics Dashboard');
    await page.waitForTimeout(2000);

    // Capture screenshot of the full Dashboard to verify charts alignment
    await page.screenshot({
      path: path.join(artifactDir, 'dashboard_charts_perfect.png'),
      fullPage: true,
    });

    // 3. Navigate to New Scan Page
    await page.goto('/scans/new');
    await page.waitForTimeout(1500);

    // 4. Attach sample test label
    const sampleLabelPath = path.resolve(__dirname, '..', 'public', 'sample_test_label.jpg');
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles(sampleLabelPath);
    await page.waitForTimeout(1500);

    // 5. Submit Scan
    const submitBtn = page.locator('button:has-text("Submit for Statutory Verification")').first();
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // Wait for scan detail page navigation
    await page.waitForURL(/\/scans\/[0-9a-f-]+/, { timeout: 20000 });
    await page.waitForTimeout(4000);

    // Capture screenshot of the scan result page
    await page.screenshot({
      path: path.join(artifactDir, 'scan_detail_live.png'),
      fullPage: true,
    });

    // 6. Navigate to Violations Explorer
    await page.goto('/violations');
    await page.waitForTimeout(1500);
    await page.screenshot({
      path: path.join(artifactDir, 'violations_page_live.png'),
      fullPage: true,
    });

    // 7. Navigate to Rules Configuration
    await page.goto('/rules');
    await page.waitForTimeout(1500);
    await page.screenshot({
      path: path.join(artifactDir, 'rules_page_live.png'),
      fullPage: true,
    });

    // 8. Return to Dashboard
    await page.goto('/dashboard');
    await page.waitForTimeout(2000);
    await page.screenshot({
      path: path.join(artifactDir, 'dashboard_final_live.png'),
      fullPage: true,
    });
  });
});
