import { apiOrigin } from './ports';
import { expect, test } from '@playwright/test';
import { readE2EState } from './support';

test('hosted anonymous demo stays GET-only and never contacts auth or runner APIs', async ({
  page,
}) => {
  const requests: { method: string; path: string; authorization?: string }[] = [];
  page.on('request', (request) => {
    if (!request.url().includes('/api/v1/')) return;
    requests.push({
      method: request.method(),
      path: new URL(request.url()).pathname,
      authorization: request.headers().authorization,
    });
  });

  await page.goto('/#/demo');
  const reasoningOffRun = page.getByRole('button', { name: /Qwen3\.8 27B GSQ-RCO \(MTP on\)/ }).filter({ hasText: 'Reasoning off' });
  await expect(reasoningOffRun).toBeVisible();
  await reasoningOffRun.click();
  await expect(page).toHaveURL(/#\/demo\/runs\/demo-run-01$/);
  await expect(page.getByRole('heading', { name: 'Qwen3.8 27B GSQ-RCO (MTP on) IQ3_XXS' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Delete' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Retry run' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Import|Launch/ })).toHaveCount(0);

  expect(requests.length).toBeGreaterThanOrEqual(2);
  expect(requests.every((request) =>
    request.method === 'GET' &&
    (request.path === '/api/v1/demo/runs' ||
      request.path === '/api/v1/demo/runs/demo-run-01') &&
    !request.authorization
  )).toBe(true);
  expect(requests.map(({ path }) => path)).toContain('/api/v1/demo/runs');
  expect(requests.map(({ path }) => path)).toContain(
    '/api/v1/demo/runs/demo-run-01'
  );

  const runnerEndpoint = await page.request.get(
    `${apiOrigin}/api/v1/benchmark/runs/00000000-0000-4000-8000-000000000001`
  );
  expect(runnerEndpoint.status()).toBe(404);
  const runnerStart = await page.request.post(
    `${apiOrigin}/api/v1/benchmark/runs`,
    { data: {} }
  );
  expect(runnerStart.status()).toBe(404);
  expect(readE2EState().jwks_fetches).toBe(0);
});


test('anonymous visitors select, compare and refresh public configurations', async ({ page }) => {
  const apiRequests: { method: string; path: string; auth?: string }[] = [];
  page.on('request', (request) => {
    if (request.url().includes('/api/v1/')) apiRequests.push({ method: request.method(), path: new URL(request.url()).pathname, auth: request.headers().authorization });
  });
  await page.goto('/#/demo');
  await page.getByRole('button', { name: 'Compare configurations', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Compare demo configurations' })).toBeVisible();
  const compare = page.getByRole('button', { name: 'Compare selected', exact: true });
  await expect(compare).toBeDisabled();
  await page.getByRole('checkbox').nth(0).check();
  await expect(compare).toBeDisabled();
  await page.getByRole('checkbox').nth(1).check();
  await compare.click();
  await expect(page).toHaveURL(/#\/demo\/compare\?ids=demo-run-01,demo-run-02$/);
  await expect(page.getByRole('heading', { name: 'Pass rate comparison', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Generation throughput comparison', exact: true })).toBeVisible();
  await expect(page.getByText('65.96%', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('63.83%', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('27.4 tok/s', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('33.9 tok/s', { exact: true }).first()).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Pass rate comparison', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /Import|Launch|Delete/ })).toHaveCount(0);
  expect(apiRequests.every((request) => request.method === 'GET' && request.path === '/api/v1/demo/runs' && !request.auth)).toBe(true);
  if (process.env.SHOWCASE_SCREENSHOT_PATH) {
    await page.setViewportSize({ width: 1440, height: 1080 });
    await page.screenshot({ path: process.env.SHOWCASE_SCREENSHOT_PATH, fullPage: true, animations: 'disabled' });
  }
});

test('forged comparison links cannot request personal records', async ({ page }) => {
  const paths: string[] = [];
  page.on('request', (request) => { if (request.url().includes('/api/v1/')) paths.push(new URL(request.url()).pathname); });
  await page.goto('/#/demo/compare?ids=demo-run-01,personal-run');
  await expect(page.getByText(/One or more selected configurations are unavailable/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Choose demo configurations' })).toBeVisible();
  expect(paths.length).toBeGreaterThan(0);
  expect(paths.every((path) => path === '/api/v1/demo/runs')).toBe(true);
});
