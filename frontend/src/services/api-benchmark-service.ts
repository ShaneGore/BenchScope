import type { components } from '@/types/api.generated';
import type {
  ApiError,
  BenchmarkConfig,
  BenchmarkRun,
  ImportError,
  ImportResult,
  ModelProfile,
  Paginated,
  RunFilters,
} from '@/types';
import type { BenchmarkService } from './benchmark-service';
import { journeyRoute, traceJourneyRequest } from '@/observability';

type ApiProfile = components['schemas']['ModelProfile'];
type ApiProfileCreate = components['schemas']['ProfileCreate'];
type ApiProfileUpdate = components['schemas']['ProfileUpdate'];
type ApiRun = components['schemas']['BenchmarkRun'];
type ApiImportResult = components['schemas']['ImportResult'];

const API_PREFIX = '/api/v1';
type SessionTokenProvider = () => Promise<string | null>;
let sessionTokenProvider: SessionTokenProvider | undefined;

export function setApiSessionTokenProvider(
  provider: SessionTokenProvider | undefined
): void {
  sessionTokenProvider = provider;
}

function mapProfile(profile: ApiProfile): ModelProfile {
  const config = profile.inference_config ?? {};
  return {
    id: profile.id,
    owner_id: profile.owner_id,
    name: profile.name,
    model_name: profile.model_name,
    quantization: profile.quantisation,
    context_length: numberOrNull(config.context_length ?? config.ctx),
    inference_engine: stringOrNull(config.inference_engine),
    endpoint_url: profile.endpoint_url,
    api_key_ref: null,
    created_at: profile.created_at,
    updated_at: profile.updated_at,
  };
}

function profilePayload(
  input: Omit<ModelProfile, 'id' | 'owner_id' | 'created_at' | 'updated_at'>
): ApiProfileCreate {
  return {
    name: input.name,
    model_name: input.model_name,
    quantisation: input.quantization ?? null,
    endpoint_url: input.endpoint_url ?? null,
    inference_config: {
      context_length: input.context_length ?? null,
      inference_engine: input.inference_engine ?? null,
    },
    hardware_notes: null,
    model_version: null,
  };
}

function profilePatch(patch: Partial<ModelProfile>): ApiProfileUpdate {
  const body: ApiProfileUpdate = {};
  if (patch.name !== undefined) body.name = patch.name;
  if (patch.model_name !== undefined) body.model_name = patch.model_name;
  if (patch.quantization !== undefined) body.quantisation = patch.quantization;
  if (patch.endpoint_url !== undefined) body.endpoint_url = patch.endpoint_url;
  if (patch.context_length !== undefined || patch.inference_engine !== undefined) {
    body.inference_config = {
      ...(patch.context_length !== undefined && {
        context_length: patch.context_length,
      }),
      ...(patch.inference_engine !== undefined && {
        inference_engine: patch.inference_engine,
      }),
    };
  }
  return body;
}

function mapRun(run: ApiRun): BenchmarkRun {
  const snapshot = run.profile_snapshot;
  const config = run.benchmark_config;
  return {
    ...run,
    profile_snapshot: {
      profile_id: snapshot.profile_id ?? 'imported',
      name: snapshot.name,
      model_name: snapshot.model_name,
      quantization: snapshot.quantization ?? snapshot.quantisation ?? null,
      context_length: snapshot.context_length ?? null,
      inference_engine: snapshot.inference_engine ?? null,
    },
    benchmark_config: {
      name: config.name,
      temperature: config.temperature,
      max_tokens: config.max_tokens,
      concurrency: config.concurrency,
      prompt_set: config.prompt_set,
      reasoning: config.reasoning,
      mtp: config.mtp,
      ctx: config.ctx,
      seed: config.seed,
      repeat_index: config.repeat_index,
    } as BenchmarkConfig,
    ended_at: run.ended_at ?? null,
    related_run_id: run.related_run_id ?? null,
    source: run.source as BenchmarkRun['source'],
    fingerprint: run.fingerprint ?? null,
    artifact_ref: run.artifact_ref ?? null,
    events: (run.events ?? []).map(({ ts, event, detail }) =>
      detail == null ? { ts, event } : { ts, event, detail }
    ),
    metrics: {
      quality_score: run.metrics.quality_score ?? null,
      pass_rate: run.metrics.pass_rate ?? null,
      ttft_ms: run.metrics.ttft_ms ?? null,
      prompt_tokens: run.metrics.prompt_tokens ?? null,
      output_tokens: run.metrics.output_tokens ?? null,
      prompt_throughput_tps: run.metrics.prompt_throughput_tps ?? null,
      generation_throughput_tps: run.metrics.generation_throughput_tps ?? null,
      elapsed_ms: run.metrics.elapsed_ms ?? null,
    },
    hardware_snapshot: run.hardware_snapshot ?? null,
    benchmark_details: run.benchmark_details ?? null,
    task_results: run.task_results ?? null,
  };
}

function toApiError(status: number, body: unknown): ApiError {
  const detail =
    body && typeof body === 'object' && 'detail' in body
      ? (body as { detail: unknown }).detail
      : 'Request failed';
  if (typeof detail === 'string') return { status, detail };
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    return { status, detail: detail as Record<string, string> };
  }
  return { status, detail: 'Request failed' };
}

function importErrors(body: ApiImportResult): ImportError[] {
  return body.ok ? [] : body.errors;
}

export class ApiBenchmarkService implements BenchmarkService {
  private readonly baseUrl: string;
  private readonly fetcher: typeof fetch;

  constructor(
    apiUrl: string,
    fetcher: typeof fetch = globalThis.fetch,
    private readonly requireSessionToken = false
  ) {
    this.baseUrl = apiUrl.replace(/\/+$/, '');
    this.fetcher = fetcher.bind(globalThis);
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const method = init?.method ?? 'GET';
    return traceJourneyRequest(
      journeyRoute(path, method),
      method,
      async (traceHeaders, recordResponse) => {
        const token = await sessionTokenProvider?.();
        if (this.requireSessionToken && !token) {
          throw { status: 401, detail: 'Not authenticated' } satisfies ApiError;
        }
        const response = await this.fetcher(`${this.baseUrl}${API_PREFIX}${path}`, {
          ...init,
          headers: {
            Accept: 'application/json',
            ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...init?.headers,
            ...traceHeaders,
          },
        });
        recordResponse(response.status);
        if (response.status === 204) return undefined as T;

        let body: unknown;
        try {
          body = await response.json();
        } catch {
          body = null;
        }
        if (!response.ok) throw toApiError(response.status, body);
        return body as T;
      }
    );
  }

  async listProfiles(): Promise<ModelProfile[]> {
    const profiles = await this.request<ApiProfile[]>('/profiles');
    return profiles.map(mapProfile);
  }

  async getProfile(id: string): Promise<ModelProfile> {
    return mapProfile(await this.request<ApiProfile>(`/profiles/${encodeURIComponent(id)}`));
  }

  async createProfile(
    input: Omit<ModelProfile, 'id' | 'owner_id' | 'created_at' | 'updated_at'>
  ): Promise<ModelProfile> {
    return mapProfile(
      await this.request<ApiProfile>('/profiles', {
        method: 'POST',
        body: JSON.stringify(profilePayload(input)),
      })
    );
  }

  async updateProfile(id: string, patch: Partial<ModelProfile>): Promise<ModelProfile> {
    return mapProfile(
      await this.request<ApiProfile>(`/profiles/${encodeURIComponent(id)}`, {
        method: 'PATCH',
        body: JSON.stringify(profilePatch(patch)),
      })
    );
  }

  deleteProfile(id: string): Promise<void> {
    return this.request(`/profiles/${encodeURIComponent(id)}`, { method: 'DELETE' });
  }

  async importRun(payload: unknown): Promise<ImportResult> {
    return traceJourneyRequest(
      '/api/v1/runs/import',
      'POST',
      async (traceHeaders, recordResponse) => {
        const token = await sessionTokenProvider?.();
        if (this.requireSessionToken && !token) {
          throw { status: 401, detail: 'Not authenticated' } satisfies ApiError;
        }
        const response = await this.fetcher(`${this.baseUrl}${API_PREFIX}/runs/import`, {
          method: 'POST',
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
            ...traceHeaders,
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify(payload),
        });
        recordResponse(response.status);
        let body: ApiImportResult | null = null;
        try {
          body = (await response.json()) as ApiImportResult;
        } catch {
          body = null;
        }
        if (body && !body.ok) {
          return {
            ok: false,
            status: body.status || response.status,
            errors: importErrors(body),
          };
        }
        if (!response.ok || !body) throw toApiError(response.status, body);
        return { ok: true, run: mapRun(body.run) };
      }
    );
  }

  async listRuns(filters: RunFilters = {}): Promise<Paginated<BenchmarkRun>> {
    const query = new URLSearchParams();
    for (const key of ['status', 'model', 'from', 'to', 'limit', 'cursor'] as const) {
      const value = filters[key];
      if (value !== undefined && value !== null && value !== '') {
        query.set(key, String(value));
      }
    }
    const suffix = query.size ? `?${query}` : '';
    const result = await this.request<components['schemas']['PaginatedRuns']>(
      `/runs${suffix}`
    );
    return {
      items: result.items.map(mapRun),
      next_cursor: result.next_cursor ?? null,
      has_more: result.has_more,
    };
  }

  async getRun(id: string): Promise<BenchmarkRun> {
    return mapRun(await this.request<ApiRun>(`/runs/${encodeURIComponent(id)}`));
  }

  deleteRun(id: string): Promise<void> {
    return this.request(`/runs/${encodeURIComponent(id)}`, { method: 'DELETE' });
  }

  async compareRuns(ids: string[]): Promise<BenchmarkRun[]> {
    const query = new URLSearchParams({ ids: ids.join(',') });
    const runs = await this.request<ApiRun[]>(`/runs/compare?${query}`);
    return runs.map(mapRun);
  }
}

function numberOrNull(value: unknown): number | null {
  return typeof value === 'number' ? value : null;
}

function stringOrNull(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}
