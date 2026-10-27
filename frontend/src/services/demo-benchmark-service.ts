import type {
  ApiError,
  BenchmarkRun,
  ImportResult,
  ModelProfile,
  Paginated,
  RunFilters,
} from '@/types';
import type { BenchmarkService } from './benchmark-service';

interface DemoRunResponse {
  id: string;
  status: 'completed';
  profile_snapshot: {
    name: string;
    model_name: string;
    model_version: string | null;
    quantisation: string | null;
  };
  benchmark_config: {
    name: string;
    temperature: number | null;
    max_tokens: number | null;
  };
  started_at: string;
  ended_at: string;
  metrics: BenchmarkRun['metrics'];
  hardware_snapshot: NonNullable<BenchmarkRun['hardware_snapshot']>;
}

const readonlyError = (): ApiError => ({ status: 403, detail: 'Demo is read-only' });

export class DemoBenchmarkService implements BenchmarkService {
  private readonly baseUrl: string;

  constructor(
    apiUrl = import.meta.env.VITE_API_URL ?? '',
    private readonly fetcher?: typeof fetch
  ) {
    this.baseUrl = apiUrl.replace(/\/+$/, '');
  }

  async listRuns(filters: RunFilters = {}): Promise<Paginated<BenchmarkRun>> {
    const response = await this.request<DemoRunResponse[]>('/demo/runs');
    let runs = response.map(mapDemoRun);
    if (filters.status) runs = runs.filter((run) => run.status === filters.status);
    if (filters.model) {
      runs = runs.filter((run) => run.profile_snapshot.model_name === filters.model);
    }
    if (filters.from) runs = runs.filter((run) => run.started_at >= filters.from!);
    if (filters.to) runs = runs.filter((run) => run.started_at < filters.to!);
    return { items: runs.slice(0, filters.limit ?? 50), next_cursor: null, has_more: false };
  }

  async getRun(id: string): Promise<BenchmarkRun> {
    return mapDemoRun(
      await this.request<DemoRunResponse>(`/demo/runs/${encodeURIComponent(id)}`)
    );
  }

  listProfiles(): Promise<ModelProfile[]> {
    return Promise.reject(readonlyError());
  }

  getProfile(): Promise<ModelProfile> {
    return Promise.reject(readonlyError());
  }

  createProfile(): Promise<ModelProfile> {
    return Promise.reject(readonlyError());
  }

  updateProfile(): Promise<ModelProfile> {
    return Promise.reject(readonlyError());
  }

  deleteProfile(): Promise<void> {
    return Promise.reject(readonlyError());
  }

  importRun(): Promise<ImportResult> {
    return Promise.reject(readonlyError());
  }

  deleteRun(): Promise<void> {
    return Promise.reject(readonlyError());
  }

  compareRuns(): Promise<BenchmarkRun[]> {
    return Promise.reject(readonlyError());
  }

  private async request<T>(path: string): Promise<T> {
    const response = await (this.fetcher ?? globalThis.fetch)(
      `${this.baseUrl}/api/v1${path}`,
      {
      headers: { Accept: 'application/json' },
      }
    );
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

function mapDemoRun(run: DemoRunResponse): BenchmarkRun {
  return {
    id: run.id,
    owner_id: 'demo',
    status: run.status,
    profile_snapshot: {
      profile_id: 'demo',
      name: run.profile_snapshot.name,
      model_name: run.profile_snapshot.model_name,
      quantization: run.profile_snapshot.quantisation,
    },
    benchmark_config: {
      name: run.benchmark_config.name,
      max_tokens: run.benchmark_config.max_tokens ?? undefined,
    },
    started_at: run.started_at,
    ended_at: run.ended_at,
    source: 'imported',
    metrics: run.metrics,
    hardware_snapshot: run.hardware_snapshot,
  };
}
