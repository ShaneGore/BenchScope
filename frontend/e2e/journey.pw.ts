import { expect, test, type Page } from '@playwright/test';
import { apiRequest, installLocalAuth, runPayload } from './support';

async function importFile(
  page: Page,
  name: string,
  content: string
) {
  await page.goto('/#/import');
  await page.locator('input[type="file"]').setInputFiles({
    name,
    mimeType: 'application/json',
    buffer: Buffer.from(content),
  });
  await page.getByRole('main').getByRole('button', { name: 'Import', exact: true }).click();
}

test('real API import, history filters, comparison, and failure atomicity', async ({
  page,
}) => {
  test.setTimeout(90_000);
  await installLocalAuth(page);

  const traceparents: string[] = [];
  page.on('request', (request) => {
    if (request.url().endsWith('/api/v1/runs/import')) {
      traceparents.push(request.headers().traceparent ?? '');
    }
  });

  const startedAt = new Date(Date.now() - 10_000).toISOString();
  const firstPayload = runPayload(`journey-${Date.now()}-one`, startedAt);
  await importFile(page, 'synthetic-run.json', JSON.stringify(firstPayload));
  await expect(
    page.getByText('Run imported successfully. Missing metrics remain unavailable.')
  ).toBeVisible();
  await page.getByRole('button', { name: 'View detail' }).click();
  await expect(page.getByRole('heading', { name: 'Synthetic E2E profile' })).toBeVisible();
  await expect(page.getByText('Unavailable').first()).toBeVisible();

  const secondPayload = runPayload(
    `journey-${Date.now()}-two`,
    new Date(Date.now() - 5_000).toISOString(),
    { metrics: { quality_score: 0.8 } }
  );
  await importFile(page, 'second-synthetic-run.json', JSON.stringify(secondPayload));
  await expect(
    page.getByText('Run imported successfully. Missing metrics remain unavailable.')
  ).toBeVisible();

  const before = await apiRequest<{ items: unknown[] }>(page, '/runs?limit=100');
  expect(before.status).toBe(200);
  const countBeforeErrors = before.body.items.length;

  const invalid = runPayload(`journey-${Date.now()}-invalid`, startedAt, {
    format_version: 'unsupported.version',
    owner_id: 'e2e-owner-b',
  });
  await importFile(page, 'invalid-run.json', JSON.stringify(invalid));
  await expect(page.getByRole('heading', { name: 'Import failed' })).toBeVisible();

  const oversized = runPayload(`journey-${Date.now()}-oversized`, startedAt, {
    hardware_snapshot: { cpu: 'synthetic'.repeat(120_000) },
  });
  await importFile(page, 'oversized-run.json', JSON.stringify(oversized));
  await expect(page.getByRole('heading', { name: 'Import failed' })).toBeVisible();

  const after = await apiRequest<{ items: unknown[] }>(page, '/runs?limit=100');
  expect(after.status).toBe(200);
  expect(after.body.items).toHaveLength(countBeforeErrors);

  await page.goto('/#/runs');
  await expect(page.getByRole('heading', { name: 'Run history' })).toBeVisible();
  await page.getByLabel('Status').selectOption('completed');
  await page.getByLabel('Model').fill('synthetic/e2e');
  const selectableRuns = page.getByRole('checkbox', {
    name: 'Select run Synthetic E2E profile for comparison',
  });
  await expect(selectableRuns).toHaveCount(2);
  await selectableRuns.first().check();
  await selectableRuns.nth(1).check();
  await page.getByRole('button', { name: 'Compare 2 runs' }).click();
  await expect(page.getByRole('heading', { name: 'Compare runs' })).toBeVisible();
  await expect(page.getByText('Unavailable').first()).toBeVisible();

  expect(traceparents).toHaveLength(4);
  expect(traceparents.every((value) =>
    /^00-[0-9a-f]{32}-[0-9a-f]{16}-01$/.test(value)
  )).toBe(true);
});
