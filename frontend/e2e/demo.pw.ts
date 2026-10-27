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
  await expect(page.getByText('Sample Model A')).toBeVisible();
  await page.getByRole('button', { name: /Sample Model A/ }).click();
  await expect(page).toHaveURL(/#\/demo\/runs\/demo-run-01$/);
  await expect(page.getByRole('heading', { name: 'Sample Model A' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Delete' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Retry run' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Compare' })).toHaveCount(0);
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
    'http://127.0.0.1:8000/api/v1/benchmark/runs/00000000-0000-4000-8000-000000000001'
  );
  expect(runnerEndpoint.status()).toBe(404);
  const runnerStart = await page.request.post(
    'http://127.0.0.1:8000/api/v1/benchmark/runs',
    { data: {} }
  );
  expect(runnerStart.status()).toBe(404);
  expect(readE2EState().jwks_fetches).toBe(0);
});
