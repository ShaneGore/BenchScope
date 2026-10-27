import { expect, test } from '@playwright/test';

const profile = {
  id: '00000000-0000-0000-0000-000000000001',
  owner_id: 'local-user',
  name: 'Browser test profile',
  model_name: 'synthetic/browser-test',
  model_version: null,
  quantisation: null,
  endpoint_url: null,
  hardware_notes: null,
  inference_config: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

test('local launch controls stay hidden without capability and no start request is sent', async ({ page }) => {
  const runnerCalls: string[] = [];
  await page.route('**/api/v1/benchmark/**', async (route) => {
    runnerCalls.push(`${route.request().method()} ${new URL(route.request().url()).pathname}`);
    await route.fulfill({ json: { enabled: false } });
  });
  await page.route('**/api/v1/runs**', (route) =>
    route.fulfill({ json: { items: [], next_cursor: null, has_more: false } })
  );

  await page.goto('/#/benchmark');
  await expect(page).toHaveURL(/#\/$/);
  await expect(page.getByRole('button', { name: 'Start benchmark' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Benchmark', exact: true })).toHaveCount(0);
  expect(runnerCalls.length).toBeGreaterThanOrEqual(1);
  expect(runnerCalls.every((call) => call === 'GET /api/v1/benchmark/capabilities')).toBe(true);
});

test('local launch controls and runner requests are available only after capability is enabled', async ({ page }) => {
  const runnerCalls: string[] = [];
  const failedRequests: string[] = [];
  page.on('requestfailed', (request) => {
    failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText}`);
  });
  await page.route('**/api/v1/benchmark/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    runnerCalls.push(`${request.method()} ${path}`);
    if (request.method() === 'OPTIONS') {
      await route.fulfill({
        status: 204,
        headers: {
          'access-control-allow-origin': '*',
          'access-control-allow-methods': 'GET, POST, OPTIONS',
          'access-control-allow-headers': 'accept, content-type, traceparent, tracestate',
        },
      });
    } else if (path.endsWith('/capabilities')) {
      await route.fulfill({ json: { enabled: true } });
    } else if (request.method() === 'POST' && path.endsWith('/benchmark/runs')) {
      await route.fulfill({
        status: 202,
        json: { id: '00000000-0000-0000-0000-000000000002', status: 'running' },
      });
    } else {
      await route.fulfill({
        json: {
          id: '00000000-0000-0000-0000-000000000002',
          status: 'running',
          related_run_id: null,
          started_at: '2026-01-01T00:00:00Z',
          completed_at: null,
          elapsed_ms: null,
          metrics: {},
          error_category: null,
          error_message_sanitised: null,
        },
      });
    }
  });
  await page.route('**/api/v1/profiles', (route) => route.fulfill({ json: [profile] }));

  await page.goto('/#/benchmark');
  const launch = page.getByRole('button', { name: 'Start benchmark' });
  await expect(launch).toBeVisible();
  await launch.click();
  await expect.poll(() =>
    runnerCalls.some((call) => call.startsWith('POST /api/v1/benchmark/runs'))
  ).toBe(true, { message: `Runner calls: ${runnerCalls}; failed: ${failedRequests}` });
  await expect(page.getByRole('button', { name: 'Run in progress' })).toBeVisible();
  expect(runnerCalls).toContain('GET /api/v1/benchmark/capabilities');
  await expect.poll(() => runnerCalls).toContain(
    'GET /api/v1/benchmark/runs/00000000-0000-0000-0000-000000000002'
  );
});
