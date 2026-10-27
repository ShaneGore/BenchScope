import { APP_MODE } from '@/lib/mode';
import type { ApiError, RunMetrics, RunStatus } from '@/types';

const API_PREFIX = '/api/v1';

export interface RunnerStatus {
  id: string;
  status: RunStatus;
  started_at: string;
  completed_at: string | null;
  elapsed_ms: number | null;
  metrics: RunMetrics;
  error_category: string | null;
  error_message_sanitised: string | null;
}

export async function getBenchmarkCapability(
  fetcher: typeof fetch = fetch
): Promise<boolean> {
  if (APP_MODE !== 'local') return false;
  try {
    const response = await fetcher(
      `${(import.meta.env.VITE_API_URL ?? '').replace(/\/+$/, '')}${API_PREFIX}/benchmark/capabilities`,
      { headers: { Accept: 'application/json' } }
    );
    if (!response.ok) return false;
    const body: unknown = await response.json();
    return !!body && typeof body === 'object' && 'enabled' in body && body.enabled === true;
  } catch {
    return false;
  }
}

export class LocalRunnerService {
  private readonly baseUrl: string;
  private readonly fetcher: typeof fetch;

  constructor(
    apiUrl = import.meta.env.VITE_API_URL ?? '',
    fetcher: typeof fetch = fetch
  ) {
    this.baseUrl = apiUrl.replace(/\/+$/, '');
    this.fetcher = fetcher.bind(globalThis);
  }

  async start(profileId: string, configId: string): Promise<{ id: string }> {
    return this.request('/benchmark/runs', {
      method: 'POST',
      body: JSON.stringify({ profile_id: profileId, config_id: configId }),
    });
  }

  status(id: string): Promise<RunnerStatus> {
    return this.request(`/benchmark/runs/${encodeURIComponent(id)}`);
  }

  async retry(id: string): Promise<{ id: string }> {
    return this.request(`/runs/${encodeURIComponent(id)}/retry`, { method: 'POST' });
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    if (APP_MODE !== 'local') {
      throw { status: 404, detail: 'Benchmark runner is unavailable in this mode' } satisfies ApiError;
    }
    const response = await this.fetcher(`${this.baseUrl}${API_PREFIX}${path}`, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...init?.headers,
      },
    });
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    if (!response.ok) {
      const detail =
        body && typeof body === 'object' && 'detail' in body
          ? (body as { detail: ApiError['detail'] }).detail
          : 'Request failed';
      throw { status: response.status, detail } satisfies ApiError;
    }
    return body as T;
  }
}
