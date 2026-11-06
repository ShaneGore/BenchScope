// Verify the built container frontend uses the real API, including browser CORS.
import { createRequire } from 'node:module';
const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium, expect } = require('@playwright/test');
const frontend = process.env.VERIFY_FRONTEND_URL;
const api = process.env.VERIFY_API_URL;
if (!frontend || !api) throw new Error('Owned verification frontend/API URLs are required.');
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  const response = page.waitForResponse((response) =>
    response.url().startsWith(`${api}/api/v1/runs?`) && response.status() === 200
  );
  await page.goto(frontend);
  await response;
  await expect(page.getByRole('heading', { name: 'Dashboard', exact: true })).toBeVisible();
  await page.getByRole('button', { name: /Completed Smoke Test Model/ }).click();
  await expect(page.getByRole('heading', { name: /Smoke Test Model/ })).toBeVisible();
  await expect(page.getByText('75.00%', { exact: true })).toBeVisible();
  console.log('PASS: built container frontend reads imported result from its real API in Chromium.');
} finally {
  await browser.close();
}
