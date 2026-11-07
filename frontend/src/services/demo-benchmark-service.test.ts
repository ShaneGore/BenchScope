import { expect, test, vi } from 'vitest';
import { DemoBenchmarkService } from './demo-benchmark-service';

const demoRun = {
  id: 'demo-run-01',
  status: 'completed',
  profile_snapshot: {
    name: 'Synthetic model',
    model_name: 'synthetic/model',
    model_version: null,
    quantisation: null,
  },
  benchmark_config: { name: 'synthetic', temperature: 0, max_tokens: 32 },
  started_at: '2026-01-01T00:00:00Z',
  ended_at: '2026-01-01T00:00:01Z',
  metrics: { quality_score: null },
  hardware_snapshot: { cpu: 'Demo CPU', gpu: null, ram_gb: null, gpu_vram_gb: null, os: null },
};

test('demo list and detail use only anonymous read-only demo GET endpoints', async () => {
  const fetcher = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify([demoRun])))
    .mockResolvedValueOnce(new Response(JSON.stringify(demoRun)));
  const service = new DemoBenchmarkService('https://api.example/', fetcher as unknown as typeof fetch);

  const list = await service.listRuns();
  expect(list.items[0]).toMatchObject({
    id: demoRun.id,
    profile_snapshot: { name: 'Synthetic model', model_name: 'synthetic/model' },
    metrics: { quality_score: null },
  });
  expect((await service.getRun(demoRun.id)).id).toBe(demoRun.id);
  expect(fetcher.mock.calls.map(([url, init]) => [url, init?.method])).toEqual([
    ['https://api.example/api/v1/demo/runs', undefined],
    [`https://api.example/api/v1/demo/runs/${demoRun.id}`, undefined],
  ]);
  expect(fetcher.mock.calls.every(([, init]) => !init?.headers || !('Authorization' in init.headers))).toBe(true);
});

test('demo API failure is surfaced without substituting mock personal data', async () => {
  const service = new DemoBenchmarkService(
    '',
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Unavailable' }), { status: 503 })
    ) as unknown as typeof fetch
  );
  await expect(service.listRuns()).rejects.toEqual({ status: 503, detail: 'Unavailable' });
});


test('demo comparison resolves public catalogue only and preserves null metrics', async () => {
  const second = { ...demoRun, id: 'demo-run-02', metrics: { pass_rate: 0.5, generation_throughput_tps: null } };
  const fetcher = vi.fn().mockImplementation(async () => new Response(JSON.stringify([demoRun, second])));
  const service = new DemoBenchmarkService('https://api.example', fetcher as unknown as typeof fetch);
  const runs = await service.compareRuns([demoRun.id, second.id]);
  expect(runs.map((run) => run.id)).toEqual([demoRun.id, second.id]);
  expect(runs[1].metrics.generation_throughput_tps).toBeNull();
  await expect(service.compareRuns([demoRun.id, 'personal-record'])).rejects.toMatchObject({ status: 422 });
  expect(fetcher.mock.calls.every(([url, init]) => url === 'https://api.example/api/v1/demo/runs' && !init.headers.Authorization)).toBe(true);
  await expect(service.importRun()).rejects.toMatchObject({ status: 403 });
  await expect(service.deleteRun()).rejects.toMatchObject({ status: 403 });
});

test('demo comparison validates selection before making requests', async () => {
  const fetcher = vi.fn();
  const service = new DemoBenchmarkService('', fetcher as unknown as typeof fetch);
  for (const ids of [[], ['one'], ['one', 'one'], Array.from({ length: 7 }, (_, i) => String(i))]) {
    await expect(service.compareRuns(ids)).rejects.toMatchObject({ status: 422 });
  }
  expect(fetcher).not.toHaveBeenCalled();
});
