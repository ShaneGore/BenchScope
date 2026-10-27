import type {
  ApiError,
  AppMode,
  BenchmarkConfig,
  BenchmarkRun,
  ImportResult,
  ModelProfile,
  Paginated,
  RunEvent,
  RunFilters,
} from '@/types';
import {
  DEMO_OWNER,
  demoConfigs,
  demoProfiles,
  demoRuns,
  newId,
} from './fixtures';
import type { BenchmarkService } from '@/services/benchmark-service';

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));
const jitter = (base: number) => base + Math.floor(Math.random() * base * 0.4);

function fail(status: number, detail: ApiError['detail']): Promise<never> {
  return new Promise((_resolve, reject) =>
    reject({ status, detail } as ApiError)
  );
}

const clone = <T>(v: T): T =>
  typeof structuredClone !== 'undefined'
    ? structuredClone(v)
    : JSON.parse(JSON.stringify(v));

function matchesFilters(r: BenchmarkRun, f: RunFilters): boolean {
  if (f.status && r.status !== f.status) return false;
  if (f.model && r.profile_snapshot.model_name !== f.model) return false;
  if (f.from && r.started_at < f.from) return false;
  if (f.to && r.started_at > f.to) return false;
  return true;
}

class MockStore implements BenchmarkService {
  private runs: BenchmarkRun[] = clone(demoRuns);
  private profiles: ModelProfile[] = clone(demoProfiles);
  private activeRunId: string | null = null;
  mode: AppMode;
  owner: string;

  constructor(mode: AppMode) {
    this.mode = mode;
    this.owner = mode === 'demo' ? DEMO_OWNER : 'local-dev';
  }

  // ---- Profiles ----
  async listProfiles(): Promise<ModelProfile[]> {
    await delay(jitter(120));
    if (this.mode === 'demo') return this.stripEndpointFields(this.profiles);
    return clone(this.profiles);
  }

  async getProfile(id: string): Promise<ModelProfile> {
    await delay(jitter(100));
    const profile = this.profiles.find((item) => item.id === id);
    if (!profile) return fail(404, 'Profile not found');
    return clone(profile);
  }

  private stripEndpointFields(ps: ModelProfile[]): ModelProfile[] {
    return ps.map((p) => ({ ...p, endpoint_url: null, api_key_ref: null }));
  }

  async createProfile(
    input: Omit<ModelProfile, 'id' | 'owner_id' | 'created_at' | 'updated_at'>
  ): Promise<ModelProfile> {
    await delay(jitter(220));
    if (this.mode === 'demo') return fail(403, { _: 'Demo is read-only' });
    if (!input.name?.trim()) return fail(422, { name: 'Name is required' });
    if (!input.model_name?.trim())
      return fail(422, { model_name: 'Model name is required' });
    const now = new Date().toISOString();
    const p: ModelProfile = {
      ...input,
      id: newId('p_'),
      owner_id: this.owner,
      created_at: now,
      updated_at: now,
      endpoint_url: this.mode === 'hosted' ? null : input.endpoint_url ?? null,
      api_key_ref: this.mode === 'hosted' ? null : input.api_key_ref ?? null,
    };
    this.profiles.push(p);
    return clone(p);
  }

  async updateProfile(
    id: string,
    patch: Partial<ModelProfile>
  ): Promise<ModelProfile> {
    await delay(jitter(200));
    if (this.mode === 'demo') return fail(403, { _: 'Demo is read-only' });
    const idx = this.profiles.findIndex((p) => p.id === id);
    if (idx === -1) return fail(404, 'Profile not found');
    if (patch.name !== undefined && !patch.name.trim())
      return fail(422, { name: 'Name is required' });
    if (patch.model_name !== undefined && !patch.model_name.trim())
      return fail(422, { model_name: 'Model name is required' });
    const merged: ModelProfile = {
      ...this.profiles[idx],
      ...patch,
      id,
      owner_id: this.owner,
      updated_at: new Date().toISOString(),
      endpoint_url:
        this.mode === 'hosted' ? null : patch.endpoint_url ?? this.profiles[idx].endpoint_url,
      api_key_ref:
        this.mode === 'hosted' ? null : patch.api_key_ref ?? this.profiles[idx].api_key_ref,
    };
    this.profiles[idx] = merged;
    return clone(merged);
  }

  async deleteProfile(id: string): Promise<void> {
    await delay(jitter(180));
    if (this.mode === 'demo') return fail(403, { _: 'Demo is read-only' });
    const idx = this.profiles.findIndex((p) => p.id === id);
    if (idx === -1) return fail(404, 'Profile not found');
    this.profiles.splice(idx, 1);
  }

  // ---- Runs ----
  async listRuns(filters: RunFilters = {}): Promise<Paginated<BenchmarkRun>> {
    await delay(jitter(160));
    const limit = filters.limit ?? 50;
    const filtered = this.runs.filter((r) => matchesFilters(r, filters));
    const startIdx = filters.cursor
      ? filtered.findIndex((r) => r.id === filters.cursor) + 1
      : 0;
    const slice = filtered.slice(startIdx, startIdx + limit);
    const hasMore = startIdx + limit < filtered.length;
    return {
      items: clone(slice),
      next_cursor: hasMore ? slice[slice.length - 1]?.id ?? null : null,
      has_more: hasMore,
    };
  }

  async getRun(id: string): Promise<BenchmarkRun> {
    await delay(jitter(110));
    const r = this.runs.find((x) => x.id === id);
    if (!r) return fail(404, 'Run not found');
    return clone(r);
  }

  async deleteRun(id: string): Promise<void> {
    await delay(jitter(160));
    if (this.mode === 'demo') return fail(403, { _: 'Demo is read-only' });
    const idx = this.runs.findIndex((r) => r.id === id);
    if (idx === -1) return fail(404, 'Run not found');
    this.runs.splice(idx, 1);
  }

  async importRun(payload: unknown): Promise<ImportResult> {
    await delay(jitter(380));
    if (this.mode === 'demo')
      return { ok: false, status: 403, errors: [{ message: 'Demo is read-only' }] };
    const errors: ImportResult['ok'] extends true ? never : { field?: string; message: string }[] = [];
    const p = payload as Record<string, unknown>;
    if (!p || typeof p !== 'object')
      return { ok: false, status: 422, errors: [{ message: 'Invalid JSON object' }] };
    if (!p.profile_snapshot && !p.model_name)
      errors.push({ field: 'model_name', message: 'model_name or profile_snapshot is required' });
    if (!p.benchmark_config && !p.config_name)
      errors.push({ field: 'benchmark_config', message: 'benchmark_config is required' });
    if (errors.length > 0) return { ok: false, status: 422, errors };

    const model_name = (p.profile_snapshot as { model_name?: string })?.model_name ?? String(p.model_name);
    const fp = `fp_${model_name}_${(p.benchmark_config as { name?: string })?.name ?? 'cfg'}`;
    const existing = this.runs.find((r) => r.fingerprint === fp);
    if (existing)
      return {
        ok: false,
        status: 409,
        errors: [{ message: 'Duplicate import — this result already exists.' }],
        existingRun: clone(existing),
      };

    const now = new Date();
    const r: BenchmarkRun = {
      id: newId('r_'),
      owner_id: this.owner,
      status: 'completed',
      profile_snapshot: {
        profile_id: 'imported',
        name: model_name,
        model_name,
        quantization: (p.profile_snapshot as { quantization?: string })?.quantization ?? null,
        context_length: (p.profile_snapshot as { context_length?: number })?.context_length ?? null,
        inference_engine: (p.profile_snapshot as { inference_engine?: string })?.inference_engine ?? null,
      },
      benchmark_config: (p.benchmark_config as BenchmarkConfig) ?? {
        name: String(p.config_name ?? 'imported'),
      },
      started_at: p.started_at ? String(p.started_at) : now.toISOString(),
      ended_at: p.ended_at ? String(p.ended_at) : now.toISOString(),
      source: 'imported',
      fingerprint: fp,
      artifact_ref: null,
      hardware_snapshot: (p.hardware_snapshot as BenchmarkRun['hardware_snapshot']) ?? null,
      metrics: {
        quality_score: numOrNull(p.quality_score),
        pass_rate: numOrNull(p.pass_rate),
        ttft_ms: numOrNull(p.ttft_ms),
        prompt_tokens: numOrNull(p.prompt_tokens),
        output_tokens: numOrNull(p.output_tokens),
        prompt_throughput_tps: numOrNull(p.prompt_throughput_tps),
        generation_throughput_tps: numOrNull(p.generation_throughput_tps),
        elapsed_ms: numOrNull(p.elapsed_ms),
      },
    };
    this.runs.unshift(r);
    return { ok: true, run: clone(r) };
  }

  // ---- Benchmark launch (local only) ----
  async startBenchmark(
    profileId: string,
    config: BenchmarkConfig
  ): Promise<BenchmarkRun> {
    await delay(jitter(300));
    if (this.mode !== 'local') return fail(404, 'Benchmark launch is not available in this mode');
    if (this.activeRunId) return fail(409, 'A benchmark run is already active');
    const profile = this.profiles.find((p) => p.id === profileId);
    if (!profile) return fail(404, 'Profile not found');
    const id = newId('r_');
    const startedAt = new Date().toISOString();
    const r: BenchmarkRun = {
      id,
      owner_id: this.owner,
      status: 'running',
      profile_snapshot: {
        profile_id: profile.id,
        name: profile.name,
        model_name: profile.model_name,
        quantization: profile.quantization,
        context_length: profile.context_length,
        inference_engine: profile.inference_engine,
      },
      benchmark_config: config,
      started_at: startedAt,
      ended_at: null,
      source: 'launched',
      fingerprint: null,
      artifact_ref: null,
      hardware_snapshot: { gpu: 'NVIDIA RTX 4060 8GB', gpu_vram_gb: 8, cpu: 'Ryzen 7 7700X', ram_gb: 32, os: 'Linux 6.9' },
      metrics: {},
      events: [{ ts: startedAt, event: 'run_started' }],
    };
    this.runs.unshift(r);
    this.activeRunId = id;
    this.scheduleCompletion(id);
    return clone(r);
  }

  private scheduleCompletion(id: string) {
    const tick = () => {
      if (this.activeRunId !== id) return;
      const r = this.runs.find((x) => x.id === id);
      if (!r || r.status !== 'running') return;
      const evts = r.events ?? [];
      const phase = evts.length;
      if (phase < 4) {
        const nextEvt: RunEvent = {
          ts: new Date().toISOString(),
          event:
            phase === 1 ? 'model_loaded' : phase === 2 ? 'prompt_batch_started' : 'generation_started',
        };
        evts.push(nextEvt);
        setTimeout(tick, jitter(900));
        return;
      }
      const end = new Date().toISOString();
      r.status = 'completed';
      r.ended_at = end;
      r.events = [...evts, { ts: end, event: 'run_completed' }];
      const elapsed = Date.parse(end) - Date.parse(r.started_at);
      r.metrics = {
        quality_score: round(0.4 + Math.random() * 0.3, 3),
        pass_rate: round(0.35 + Math.random() * 0.3, 2),
        ttft_ms: Math.floor(300 + Math.random() * 250),
        prompt_tokens: 18400,
        output_tokens: Math.floor(7000 + Math.random() * 4000),
        prompt_throughput_tps: round(1200 + Math.random() * 900, 1),
        generation_throughput_tps: round(30 + Math.random() * 25, 1),
        elapsed_ms: elapsed,
      };
      this.activeRunId = null;
    };
    setTimeout(tick, jitter(1100));
  }

  async retryRun(id: string): Promise<BenchmarkRun> {
    await delay(jitter(260));
    if (this.mode !== 'local') return fail(404, 'Retry is not available in this mode');
    if (this.activeRunId) return fail(409, 'A benchmark run is already active');
    const base = this.runs.find((x) => x.id === id);
    if (!base) return fail(404, 'Run not found');
    const newId_ = newId('r_');
    const startedAt = new Date().toISOString();
    const r: BenchmarkRun = {
      ...clone(base),
      id: newId_,
      status: 'running',
      started_at: startedAt,
      ended_at: null,
      related_run_id: id,
      source: 'retry',
      fingerprint: null,
      artifact_ref: null,
      metrics: {},
      error_category: null,
      error_message_sanitised: null,
      process_exit_code: null,
      events: [{ ts: startedAt, event: 'run_started' }],
    };
    this.runs.unshift(r);
    this.activeRunId = newId_;
    this.scheduleCompletion(newId_);
    return clone(r);
  }

  // ---- Compare ----
  async compareRuns(ids: string[]): Promise<BenchmarkRun[]> {
    await delay(jitter(220));
    if (ids.length < 2) return fail(422, { ids: 'Select at least two runs' });
    const found = ids
      .map((id) => this.runs.find((r) => r.id === id))
      .filter((r): r is BenchmarkRun => Boolean(r) && r!.status === 'completed');
    if (found.length === 0) return fail(404, 'No completed runs found');
    return clone(found);
  }

  listConfigs(): BenchmarkConfig[] {
    return clone(demoConfigs);
  }

  getActiveRunId(): string | null {
    return this.activeRunId;
  }
}

function numOrNull(v: unknown): number | null {
  return typeof v === 'number' && !Number.isNaN(v) ? v : null;
}
function round(n: number, d: number): number {
  const f = Math.pow(10, d);
  return Math.round(n * f) / f;
}

let store: MockStore | null = null;
export function getStore(mode: AppMode): MockStore {
  if (!store) store = new MockStore(mode);
  return store;
}
export function resetStore(mode: AppMode): MockStore {
  store = new MockStore(mode);
  return store;
}
