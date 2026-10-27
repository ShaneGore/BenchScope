import { readFileSync } from 'node:fs';
import type { Page } from '@playwright/test';

const API_ORIGIN = 'http://127.0.0.1:8000';

interface E2EState {
  tokens: Record<string, string>;
  subjects: string[];
  jwks_fetches: number;
}

export function readE2EState(): E2EState {
  const path = process.env.E2E_STATE_FILE;
  if (!path) throw new Error('E2E_STATE_FILE is not configured.');
  return JSON.parse(readFileSync(path, 'utf8')) as E2EState;
}

export async function installLocalAuth(
  page: Page,
  defaultSubject = 'e2e-owner-a'
): Promise<void> {
  const { tokens } = readE2EState();
  await page.addInitScript(
    ({ apiOrigin, subject, subjectTokens }) => {
      if (!localStorage.getItem('benchscope-e2e-subject')) {
        localStorage.setItem('benchscope-e2e-subject', subject);
      }
      const originalFetch = window.fetch.bind(window);
      window.fetch = (input, init = {}) => {
        const requestUrl =
          typeof input === 'string'
            ? input
            : input instanceof URL
              ? input.href
              : input.url;
        if (new URL(requestUrl, window.location.href).origin !== apiOrigin) {
          return originalFetch(input, init);
        }
        const activeSubject =
          localStorage.getItem('benchscope-e2e-subject') ?? subject;
        const token = subjectTokens[activeSubject];
        const sourceHeaders =
          input instanceof Request ? input.headers : undefined;
        const headers = new Headers(sourceHeaders);
        new Headers(init.headers).forEach((value, key) =>
          headers.set(key, value)
        );
        if (token) headers.set('Authorization', `Bearer ${token}`);
        return originalFetch(input, { ...init, headers });
      };
    },
    { apiOrigin: API_ORIGIN, subject: defaultSubject, subjectTokens: tokens }
  );
}

export async function setLocalSubject(
  page: Page,
  subject: 'e2e-owner-a' | 'e2e-owner-b'
): Promise<void> {
  await page.evaluate((value) => {
    localStorage.setItem('benchscope-e2e-subject', value);
  }, subject);
}

export async function apiRequest<T = unknown>(
  page: Page,
  path: string,
  options: { method?: string; body?: unknown } = {}
): Promise<{ status: number; body: T }> {
  return page.evaluate(
    async ({ apiOrigin, requestPath, method, body }) => {
      const response = await fetch(`${apiOrigin}/api/v1${requestPath}`, {
        method,
        headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      let payload: unknown;
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }
      return { status: response.status, body: payload as T };
    },
    {
      apiOrigin: API_ORIGIN,
      requestPath: path,
      method: options.method ?? 'GET',
      body: options.body,
    }
  );
}

export const runPayload = (
  sourceRunId: string,
  startedAt: string,
  overrides: Record<string, unknown> = {}
) => ({
  format_version: 'benchscope.run.v1',
  source_run_id: sourceRunId,
  profile_snapshot: {
    name: 'Synthetic E2E profile',
    model_name: 'synthetic/e2e',
    quantisation: null,
  },
  benchmark_config: { name: 'synthetic local', temperature: 0, max_tokens: 32 },
  started_at: startedAt,
  ended_at: new Date(new Date(startedAt).getTime() + 1000).toISOString(),
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
  ...overrides,
});
