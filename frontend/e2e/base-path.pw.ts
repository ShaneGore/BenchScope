import { expect, test } from '@playwright/test';

test('production assets and hash routes work under the configured Vite base path', async ({ page }) => {
  const demoRequests: string[] = [];
  await page.route('**/api/v1/demo/runs', async (route) => {
    demoRequests.push(route.request().method());
    await route.fulfill({ json: [] });
  });

  await page.goto('#/demo');
  await expect(page.getByRole('heading', { name: 'Recent activity' })).toBeVisible();
  const assets = await page.locator('script[src], link[rel="stylesheet"]').evaluateAll((nodes) =>
    nodes.map((node) =>
      new URL(
        node instanceof HTMLScriptElement ? node.src : (node as HTMLLinkElement).href
      ).pathname
    )
  );
  expect(assets.length).toBeGreaterThan(0);
  expect(assets.every((path) => path.startsWith('/benchscope/'))).toBe(true);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Recent activity' })).toBeVisible();
  expect(new URL(page.url()).pathname).toBe('/benchscope/');
  expect(demoRequests.every((method) => method === 'GET')).toBe(true);
});
