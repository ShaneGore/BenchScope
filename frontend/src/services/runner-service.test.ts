import { beforeEach, expect, test, vi } from 'vitest';
import { getBenchmarkCapability, LocalRunnerService } from './runner-service';

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

beforeEach(() => {
  vi.stubEnv('VITE_APP_MODE', 'local');
});

test('capability request reads only the enabled flag and fails closed', async () => {
  const fetcher = vi.fn()
    .mockResolvedValueOnce(response({ enabled: true }))
    .mockResolvedValueOnce(response({ enabled: false }))
    .mockResolvedValueOnce(response({ enabled: true, secret: 'ignored' }))
    .mockRejectedValueOnce(new Error('offline'));

  expect(await getBenchmarkCapability(fetcher as unknown as typeof fetch)).toBe(true);
  expect(await getBenchmarkCapability(fetcher as unknown as typeof fetch)).toBe(false);
  expect(await getBenchmarkCapability(fetcher as unknown as typeof fetch)).toBe(true);
  expect(await getBenchmarkCapability(fetcher as unknown as typeof fetch)).toBe(false);
  expect(fetcher).toHaveBeenCalledTimes(4);
  expect(fetcher.mock.calls[0]?.[0]).toBe('/api/v1/benchmark/capabilities');
});

test('runner start, status and retry use the configured API routes', async () => {
  const fetcher = vi.fn()
    .mockResolvedValueOnce(response({ id: 'run-id', status: 'running' }, 202))
    .mockResolvedValueOnce(response({
      id: 'run-id',
      status: 'running',
      related_run_id: null,
      started_at: '2026-01-01T00:00:00Z',
      completed_at: null,
      elapsed_ms: null,
      metrics: {},
      error_category: null,
      error_message_sanitised: null,
    }))
    .mockResolvedValueOnce(response({ id: 'retry-id', status: 'running' }, 202));
  const runner = new LocalRunnerService('https://api.example/', fetcher as unknown as typeof fetch);

  await runner.start('profile-id', 'config-id');
  await runner.status('run-id');
  await runner.retry('run-id');

  expect(fetcher.mock.calls.map(([url]) => url)).toEqual([
    'https://api.example/api/v1/benchmark/runs',
    'https://api.example/api/v1/benchmark/runs/run-id',
    'https://api.example/api/v1/runs/run-id/retry',
  ]);
  expect(JSON.parse(String(fetcher.mock.calls[0]?.[1]?.body))).toEqual({
    profile_id: 'profile-id',
    config_id: 'config-id',
  });
});
