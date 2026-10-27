import { expect, test } from '@playwright/test';

const validRun = {
  format_version: 'benchscope.run.v1',
  profile_snapshot: {
    name: 'Synthetic observability run',
    model_name: 'synthetic/observability',
    quantisation: null,
  },
  benchmark_config: {
    name: 'local synthetic',
    temperature: 0,
    max_tokens: 32,
  },
  started_at: '2026-10-26T10:00:00Z',
  ended_at: '2026-10-26T10:00:02Z',
  metrics: {
    quality_score: null,
    pass_rate: null,
    ttft_ms: null,
    prompt_tokens: null,
    output_tokens: null,
    prompt_throughput_tps: null,
    generation_throughput_tps: null,
    elapsed_ms: null,
  },
};

test('imports a synthetic run, views history/detail, and records invalid import', async ({
  page,
}) => {
  test.setTimeout(90_000);
  const traceparents: string[] = [];
  const importTraceparents: string[] = [];
  const syntheticPayload = {
    ...validRun,
    source_run_id: `observability-${Date.now()}`,
  };
  page.on('request', (request) => {
    const header = request.headers().traceparent;
    if (header && request.url().includes('/api/v1/runs')) {
      traceparents.push(header);
      if (request.url().endsWith('/runs/import')) {
        importTraceparents.push(header);
      }
    }
  });

  await page.goto('/#/import');
  await page.locator('input[type="file"]').setInputFiles({
    name: 'synthetic-run.json',
    mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify(syntheticPayload)),
  });
  await page.locator('main').getByRole('button', { name: 'Import', exact: true }).click();
  await expect(page.getByText('Run imported successfully. Missing metrics remain unavailable.')).toBeVisible();
  await page.getByRole('button', { name: 'View detail' }).click();
  await expect(page.getByText('Synthetic observability run')).toBeVisible();
  await expect(page.getByText('Unavailable').first()).toBeVisible();

  await page.goto('/#/runs');
  await expect(page.getByRole('heading', { name: 'Run history' })).toBeVisible();
  await expect(page.getByText('synthetic/observability').first()).toBeVisible();
  await page.getByRole('button', { name: /Synthetic observability run/ }).first().click();
  await expect(page.getByRole('heading', { name: 'Synthetic observability run' })).toBeVisible();

  await page.goto('/#/import');
  await page.locator('input[type="file"]').setInputFiles({
    name: 'invalid-run.json',
    mimeType: 'application/json',
    buffer: Buffer.from(
      JSON.stringify({
        ...validRun,
        format_version: 'unsupported.version',
        prompt: 'PRIVATE_PROMPT_SENTINEL',
        generated_code: 'GENERATED_CODE_SENTINEL',
        stdout: 'BENCHMARK_OUTPUT_SENTINEL',
        api_key: 'AUTH_TOKEN_SENTINEL',
      })
    ),
  });
  await page.locator('main').getByRole('button', { name: 'Import', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Import failed' })).toBeVisible();

  expect(traceparents.length).toBeGreaterThanOrEqual(5);
  expect(
    traceparents.every((value) =>
      /^00-[0-9a-f]{32}-[0-9a-f]{16}-01$/.test(value)
    )
  ).toBe(true);

  const invalidTraceId = importTraceparents.at(-1)?.split('-')[1];
  expect(invalidTraceId).toMatch(/^[0-9a-f]{32}$/);

  let exportedTrace = '';
  await expect
    .poll(
      async () => {
        const response = await fetch(
          `http://127.0.0.1:3200/api/traces/${invalidTraceId}`
        );
        exportedTrace = response.ok ? await response.text() : '';
        return exportedTrace;
      },
      { timeout: 30_000 }
    )
    .toContain('POST /api/v1/runs/import');
  expect(exportedTrace).toContain(
    Buffer.from(invalidTraceId!, 'hex').toString('base64')
  );

  const metricQuery = encodeURIComponent(
    'benchscope_http_server_requests_total{http_route="/api/v1/runs/import",http_response_status_code="422"}'
  );
  await expect
    .poll(
      async () => {
        const response = await fetch(
          `http://127.0.0.1:9090/api/v1/query?query=${metricQuery}`
        );
        const result = await response.json();
        return result.data.result.length;
      },
      { timeout: 30_000 }
    )
    .toBeGreaterThan(0);

  const start = Math.floor(Date.now() / 1000) - 3600;
  const end = Math.floor(Date.now() / 1000);
  const logQuery = encodeURIComponent(
    `{service_name="benchscope-api"} | trace_id="${invalidTraceId}"`
  );
  let exportedLogs = '';
  await expect
    .poll(
      async () => {
        const response = await fetch(
          `http://127.0.0.1:3100/loki/api/v1/query_range?query=${logQuery}&start=${start}&end=${end}&limit=5`
        );
        exportedLogs = await response.text();
        return response.ok ? JSON.parse(exportedLogs).data.result.length : 0;
      },
      { timeout: 30_000 }
    )
    .toBeGreaterThan(0);

  const telemetry = `${exportedTrace}\n${exportedLogs}`;
  for (const sentinel of [
    'PRIVATE_PROMPT_SENTINEL',
    'GENERATED_CODE_SENTINEL',
    'BENCHMARK_OUTPUT_SENTINEL',
    'AUTH_TOKEN_SENTINEL',
  ]) {
    expect(telemetry).not.toContain(sentinel);
  }
});
