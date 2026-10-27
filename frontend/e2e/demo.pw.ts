import { expect, test } from '@playwright/test';

const demoRun = {
  id: 'demo-run-01',
  status: 'completed',
  profile_snapshot: {
    name: 'Synthetic browser model',
    model_name: 'synthetic/browser',
    model_version: null,
    quantisation: null,
  },
  benchmark_config: { name: 'synthetic-demo', temperature: 0, max_tokens: 32 },
  started_at: '2026-01-01T00:00:00Z',
  ended_at: '2026-01-01T00:00:01Z',
  metrics: { quality_score: null },
  hardware_snapshot: { cpu: 'Demo CPU', gpu: null, ram_gb: null, gpu_vram_gb: null, os: null },
};

test('anonymous synthetic demo list and detail stay read-only and use only demo GET endpoints', async ({ page }) => {
  const requests: string[] = [];
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    requests.push(`${request.method()} ${path}`);
    if (path.endsWith('/demo/runs')) {
      await route.fulfill({ json: [demoRun] });
    } else if (path.endsWith(`/demo/runs/${demoRun.id}`)) {
      await route.fulfill({ json: demoRun });
    } else {
      await route.fulfill({ status: 404, json: { detail: 'Unexpected endpoint' } });
    }
  });

  await page.goto('/#/demo');
  await expect(page.getByText('Synthetic browser model')).toBeVisible();
  await page.getByRole('button', { name: /Synthetic browser model/ }).click();
  await expect(page).toHaveURL(/#\/demo\/runs\/demo-run-01$/);
  await expect(page.getByRole('heading', { name: 'Synthetic browser model' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Delete' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Retry run' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Compare' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Import|Launch/ })).toHaveCount(0);
  expect(requests.every((request) =>
    request === 'GET /api/v1/demo/runs' ||
    request === `GET /api/v1/demo/runs/${demoRun.id}`
  )).toBe(true);
  expect(requests).toContain('GET /api/v1/demo/runs');
  expect(requests).toContain(`GET /api/v1/demo/runs/${demoRun.id}`);
});
