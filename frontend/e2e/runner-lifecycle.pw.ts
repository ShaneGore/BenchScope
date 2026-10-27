import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import { apiRequest, installLocalAuth } from './support';

const SUCCESS_CONFIG = '00000000-0000-4000-8000-000000000001';
const FAILURE_CONFIG = '00000000-0000-4000-8000-000000000002';
const TIMEOUT_CONFIG = '00000000-0000-4000-8000-000000000003';

interface StartedRun {
  id: string;
  status: string;
}

interface RunStatus {
  id: string;
  status: string;
  related_run_id: string | null;
  metrics: { quality_score: number | null };
  error_category: string | null;
  error_message_sanitised: string | null;
}

async function waitForStatus(page: Page, id: string) {
  let final: RunStatus | undefined;
  await expect
    .poll(
      async () => {
        const response = await apiRequest<RunStatus>(
          page,
          `/benchmark/runs/${id}`
        );
        expect(response.status).toBe(200);
        final = response.body;
        return response.body.status;
      },
      { timeout: 10_000 }
    )
    .not.toBe('running');
  return final!;
}

test('fake adapter success, failure, timeout, recovery, and retry stay isolated', async ({
  page,
}) => {
  await installLocalAuth(page);
  await page.goto('/');
  const profileResponse = await apiRequest<{ id: string }>(page, '/profiles', {
    method: 'POST',
    body: { name: 'E2E lifecycle profile', model_name: 'synthetic/lifecycle' },
  });
  expect(profileResponse.status).toBe(201);
  const profileId = profileResponse.body.id;

  const launch = async (configId: string) => {
    const response = await apiRequest<StartedRun>(page, '/benchmark/runs', {
      method: 'POST',
      body: { profile_id: profileId, config_id: configId },
    });
    expect(response.status).toBe(202);
    return response.body.id;
  };

  const successfulId = await launch(SUCCESS_CONFIG);
  const successful = await waitForStatus(page, successfulId);
  expect(successful.status).toBe('completed');
  expect(successful.metrics.quality_score).toBe(0.75);

  const failedId = await launch(FAILURE_CONFIG);
  const failed = await waitForStatus(page, failedId);
  expect(failed.status).toBe('failed');
  expect(failed.error_category).toBe('adapter_error');
  expect(failed.error_message_sanitised).toBe('Benchmark adapter failed.');
  const originalResponse = await apiRequest<RunStatus>(page, `/runs/${failedId}`);
  const original = originalResponse.body;

  await page.goto(`/#/runs/${failedId}`);
  await expect(page.getByRole('button', { name: 'Retry run' })).toBeVisible();
  const retryResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/runs/${failedId}/retry`) &&
      response.status() === 202
  );
  await page.getByRole('button', { name: 'Retry run' }).click();
  const retry = await (await retryResponse).json() as StartedRun;
  expect(retry.id).not.toBe(failedId);
  const retried = await waitForStatus(page, retry.id);
  expect(retried.status).toBe('completed');
  expect(retried.related_run_id).toBe(failedId);
  expect((await apiRequest<RunStatus>(page, `/runs/${failedId}`)).body).toEqual(
    original
  );

  const timedOutId = await launch(TIMEOUT_CONFIG);
  const timedOut = await waitForStatus(page, timedOutId);
  expect(timedOut.status).toBe('failed');
  expect(timedOut.error_category).toBe('timeout');

  const recoveryOutput = execFileSync(
    'uv',
    [
      'run',
      'python',
      'tests/e2e_server.py',
      'recover',
      profileId,
      'e2e-owner-a',
    ],
    {
      cwd: resolve('..', 'backend'),
      encoding: 'utf8',
      env: { ...process.env, PYTHONPATH: '.' },
    }
  ).trim();
  const interrupted = await apiRequest<RunStatus>(
    page,
    `/benchmark/runs/${recoveryOutput}`
  );
  expect(interrupted.status).toBe(200);
  expect(interrupted.body.status).toBe('interrupted');
  expect(interrupted.body.error_category).toBe('interrupted');

  const comparison = await apiRequest<RunStatus[]>(
    page,
    `/runs/compare?ids=${successfulId},${retry.id},${failedId},${recoveryOutput}`
  );
  expect(comparison.status).toBe(200);
  expect(comparison.body.map((run) => run.status)).toEqual([
    'completed',
    'completed',
  ]);
});
