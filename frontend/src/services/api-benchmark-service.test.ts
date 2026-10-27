import { beforeEach, expect, test, vi } from 'vitest';
import type { components } from '@/types/api.generated';
import { resetStore } from '@/mock/store';
import {
  ApiBenchmarkService,
  setApiSessionTokenProvider,
} from './api-benchmark-service';
import { createBenchmarkService } from './benchmark-service';

type ApiRun = components['schemas']['BenchmarkRun'];
type ApiProfile = components['schemas']['ModelProfile'];

const profile = {
  id: '00000000-0000-0000-0000-000000000001',
  owner_id: 'local',
  name: 'Local model',
  model_name: 'example/model',
  model_version: null,
  quantisation: 'Q4_K_M',
  endpoint_url: 'http://127.0.0.1:9000/v1',
  hardware_notes: null,
  inference_config: { context_length: 4096, inference_engine: 'llama.cpp' },
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
} satisfies ApiProfile;

const run = {
  id: '00000000-0000-0000-0000-000000000002',
  owner_id: 'local',
  status: 'completed',
  profile_snapshot: {
    name: 'Local model',
    model_name: 'example/model',
    quantisation: 'Q4_K_M',
  },
  benchmark_config: { name: 'short' },
  started_at: '2026-01-01T00:00:00Z',
  ended_at: '2026-01-01T00:01:00Z',
  metrics: {
    quality_score: null,
    pass_rate: 0.5,
    ttft_ms: null,
    prompt_tokens: null,
    output_tokens: 100,
    prompt_throughput_tps: null,
    generation_throughput_tps: 20,
    elapsed_ms: null,
  },
} satisfies ApiRun;

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function fetchQueue(...responses: Response[]) {
  const mock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => {
    const response = responses.shift();
    if (!response) throw new Error('No fake response queued');
    return response;
  });
  return { fetcher: mock as unknown as typeof fetch, mock };
}

beforeEach(() => {
  resetStore('hosted');
  setApiSessionTokenProvider(undefined);
});

test('maps profile CRUD to the in-scope API contract', async () => {
  const { fetcher, mock } = fetchQueue(
    jsonResponse([profile]),
    jsonResponse(profile),
    jsonResponse(profile, 201),
    jsonResponse(profile),
    new Response(null, { status: 204 })
  );
  const service = new ApiBenchmarkService('http://127.0.0.1:8000/', fetcher);

  const listed = await service.listProfiles();
  expect(listed[0]).toMatchObject({
    id: profile.id,
    quantization: 'Q4_K_M',
    context_length: 4096,
    inference_engine: 'llama.cpp',
  });
  await service.getProfile(profile.id);
  await service.createProfile({
    name: 'Local model',
    model_name: 'example/model',
    quantization: 'Q4_K_M',
    context_length: 4096,
    inference_engine: 'llama.cpp',
    endpoint_url: profile.endpoint_url,
    api_key_ref: 'must-not-be-sent',
  });
  await service.updateProfile(profile.id, { name: 'Updated', context_length: 8192 });
  await service.deleteProfile(profile.id);

  expect(fetcher).toHaveBeenNthCalledWith(
    1,
    'http://127.0.0.1:8000/api/v1/profiles',
    expect.objectContaining({ headers: { Accept: 'application/json' } })
  );
  const createRequest = mock.mock.calls[2]?.[1] as RequestInit;
  const createBody = JSON.parse(String(createRequest.body));
  expect(createBody).toMatchObject({
    name: 'Local model',
    model_name: 'example/model',
    quantisation: 'Q4_K_M',
    inference_config: { context_length: 4096, inference_engine: 'llama.cpp' },
  });
  expect(createBody).not.toHaveProperty('api_key_ref');
  expect(mock.mock.calls.map(([url]) => url)).toEqual([
    'http://127.0.0.1:8000/api/v1/profiles',
    `http://127.0.0.1:8000/api/v1/profiles/${profile.id}`,
    'http://127.0.0.1:8000/api/v1/profiles',
    `http://127.0.0.1:8000/api/v1/profiles/${profile.id}`,
    `http://127.0.0.1:8000/api/v1/profiles/${profile.id}`,
  ]);
});

test('filters history, preserves empty results and nullable metrics, maps detail and compare', async () => {
  const { fetcher, mock } = fetchQueue(
    jsonResponse({ items: [], next_cursor: null, has_more: false }),
    jsonResponse({ items: [run], next_cursor: null, has_more: false }),
    jsonResponse(run),
    jsonResponse([run, run])
  );
  const service = new ApiBenchmarkService('http://localhost:8000', fetcher);

  expect(await service.listRuns()).toEqual({
    items: [],
    next_cursor: null,
    has_more: false,
  });
  const filtered = await service.listRuns({
    status: 'completed',
    model: 'example/model',
    from: '2026-01-01T00:00:00Z',
    limit: 10,
  });
  expect(filtered.items[0]?.metrics).toMatchObject({
    quality_score: null,
    pass_rate: 0.5,
    ttft_ms: null,
    output_tokens: 100,
    elapsed_ms: null,
  });
  expect(mock.mock.calls[1]?.[0]).toContain(
    '/api/v1/runs?status=completed&model=example%2Fmodel&from=2026-01-01T00%3A00%3A00Z&limit=10'
  );
  expect((await service.getRun(run.id)).profile_snapshot.quantization).toBe('Q4_K_M');
  expect((await service.compareRuns([run.id, 'another-id'])).map((item) => item.id)).toEqual([
    run.id,
    run.id,
  ]);
  expect(mock.mock.calls[3]?.[0]).toBe(
    `http://localhost:8000/api/v1/runs/compare?ids=${run.id}%2Canother-id`
  );
});

test('maps import success and structured validation errors', async () => {
  const { fetcher, mock } = fetchQueue(
    jsonResponse({ ok: true, run }),
    jsonResponse(
      {
        ok: false,
        status: 422,
        errors: [{ field: 'profile_snapshot.model_name', message: 'Field is required.' }],
      },
      422
    ),
    jsonResponse(
      { ok: false, status: 409, errors: [{ field: 'request', message: 'Already imported.' }] },
      409
    )
  );
  const service = new ApiBenchmarkService('', fetcher);
  const success = await service.importRun({ format_version: 'benchscope.run.v1' });
  expect(success.ok).toBe(true);
  if (success.ok) expect(success.run.metrics.quality_score).toBeNull();
  expect(await service.importRun({})).toEqual({
    ok: false,
    status: 422,
    errors: [{ field: 'profile_snapshot.model_name', message: 'Field is required.' }],
  });
  expect(await service.importRun({ source_run_id: 'duplicate' })).toEqual({
    ok: false,
    status: 409,
    errors: [{ field: 'request', message: 'Already imported.' }],
  });
  expect(mock.mock.calls[0]?.[0]).toBe('/api/v1/runs/import');
});

test('maps API validation and other HTTP errors to the existing ApiError shape', async () => {
  const service = new ApiBenchmarkService(
    '',
    fetchQueue(
      jsonResponse({ detail: { endpoint_url: 'Credentials must not be embedded' } }, 422),
      jsonResponse({ detail: 'Run not found' }, 404)
    ).fetcher
  );

  await expect(
    service.createProfile({
      name: 'bad',
      model_name: 'example/model',
      endpoint_url: 'http://user:secret@localhost',
    })
  ).rejects.toEqual({
    status: 422,
    detail: { endpoint_url: 'Credentials must not be embedded' },
  });
  await expect(service.getRun('missing')).rejects.toEqual({
    status: 404,
    detail: 'Run not found',
  });
});

test('attaches the current Clerk session token to personal API requests', async () => {
  const { fetcher, mock } = fetchQueue(
    jsonResponse([profile]),
    jsonResponse({ ok: true, run })
  );
  setApiSessionTokenProvider(async () => 'session-jwt');
  const service = new ApiBenchmarkService('', fetcher);

  await service.listProfiles();
  await service.importRun({ format_version: 'benchscope.run.v1' });

  expect((mock.mock.calls[0]?.[1] as RequestInit).headers).toMatchObject({
    Authorization: 'Bearer session-jwt',
  });
  expect((mock.mock.calls[1]?.[1] as RequestInit).headers).toMatchObject({
    Authorization: 'Bearer session-jwt',
  });
});

test('only local mode selects the API service', async () => {
  const { fetcher: localFetch, mock: localMock } = fetchQueue(
    jsonResponse({ items: [], next_cursor: null, has_more: false })
  );
  const local = createBenchmarkService('local', 'http://127.0.0.1:8000', localFetch);
  await local.listRuns();
  expect(localMock.mock.calls[0]?.[0]).toBe('http://127.0.0.1:8000/api/v1/runs');

  for (const mode of ['hosted', 'demo'] as const) {
    resetStore(mode);
    const fetcher = vi.fn();
    const service = createBenchmarkService(mode, 'http://127.0.0.1:8000', fetcher);
    expect((await service.listProfiles()).length).toBeGreaterThan(0);
    expect(fetcher).not.toHaveBeenCalled();
  }
});
