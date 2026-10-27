import {
  InMemorySpanExporter,
  type SpanExporter,
} from '@opentelemetry/sdk-trace-base';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiBenchmarkService } from '@/services/api-benchmark-service';
import { initializeTelemetry } from '@/observability';

const prompt = 'PRIVATE_PROMPT_SENTINEL';
const code = 'GENERATED_CODE_SENTINEL';
const output = 'BENCHMARK_OUTPUT_SENTINEL';
const token = 'AUTH_TOKEN_SENTINEL';
const runId = 'c2a52d57-34c4-4a2d-b20d-2f7b414029c3';

function response(body: unknown, status: number): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  } as Response;
}

describe('journey telemetry', () => {
  let exporter: InMemorySpanExporter;

  beforeEach(() => {
    exporter = new InMemorySpanExporter();
    initializeTelemetry(undefined, exporter);
  });

  it('propagates trace context and exports only bounded route outcomes', async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/runs/import')) {
        return response(
          { ok: false, status: 422, errors: [{ message: 'Invalid request' }] },
          422
        );
      }
      if (url.includes('/runs?')) {
        return response({ items: [], next_cursor: null, has_more: false }, 200);
      }
      return response({ detail: 'Run not found' }, 404);
    });
    const service = new ApiBenchmarkService(
      'http://localhost:8000',
      fetcher as typeof fetch
    );
    const sensitivePayload = {
      prompt,
      generated_code: code,
      stdout: output,
      stderr: output,
      api_key: token,
      owner_id: token,
    };

    await service.importRun(sensitivePayload);
    await service.listRuns({ model: prompt });
    await expect(service.getRun(runId)).rejects.toMatchObject({ status: 404 });

    const spans = exporter.getFinishedSpans();
    expect(spans.map((span) => span.name)).toEqual([
      'POST /api/v1/runs/import',
      'GET /api/v1/runs',
      'GET /api/v1/runs/{id}',
    ]);
    expect(spans.map((span) => span.attributes['http.response.status_code'])).toEqual(
      [422, 200, 404]
    );
    expect(spans.map((span) => span.attributes['http.route'])).toEqual([
      '/api/v1/runs/import',
      '/api/v1/runs',
      '/api/v1/runs/{id}',
    ]);
    const exported = JSON.stringify(
      spans.map((span) => ({ name: span.name, attributes: span.attributes }))
    );
    expect(exported).not.toContain(prompt);
    expect(exported).not.toContain(code);
    expect(exported).not.toContain(output);
    expect(exported).not.toContain(token);
    expect(exported).not.toContain(runId);

    const traceparents = fetcher.mock.calls.map(([, init]) => {
      const headers = new Headers(init?.headers);
      return headers.get('traceparent');
    });
    expect(traceparents).toHaveLength(3);
    expect(traceparents.every((header) => /^00-[0-9a-f]{32}-[0-9a-f]{16}-01$/.test(header ?? ''))).toBe(true);
  });

  it('does not block API requests when span export fails', async () => {
    const brokenExporter = {
      export: () => {
        throw new Error('collector unavailable');
      },
      shutdown: () => undefined,
      forceFlush: async () => ({ code: 0 }),
    } as unknown as SpanExporter;
    initializeTelemetry(undefined, brokenExporter);
    const fetcher = vi.fn(async () =>
      response(
        { ok: false, status: 422, errors: [{ message: 'Invalid request' }] },
        422
      )
    );
    const service = new ApiBenchmarkService(
      'http://localhost:8000',
      fetcher as typeof fetch
    );

    await expect(service.importRun({ prompt })).resolves.toMatchObject({
      ok: false,
      status: 422,
    });
    expect(fetcher).toHaveBeenCalledOnce();
  });
});
