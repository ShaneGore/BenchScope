export type RunStatus =
  | 'running'
  | 'completed'
  | 'failed'
  | 'interrupted';

export type AppMode = 'local' | 'hosted' | 'demo';

export type ErrorCategory =
  | 'OOM'
  | 'TIMEOUT'
  | 'MODEL_ERROR'
  | 'INFER_FRAMEWORK'
  | 'HOST_RESTART'
  | 'UNKNOWN'
  | 'timeout'
  | 'adapter_error'
  | 'interrupted';

export interface HardwareSnapshot {
  gpu?: string | null;
  gpu_vram_gb?: number | null;
  cpu?: string | null;
  ram_gb?: number | null;
  os?: string | null;
}

export interface ProfileSnapshot {
  profile_id: string;
  name: string;
  model_name: string;
  quantization?: string | null;
  context_length?: number | null;
  inference_engine?: string | null;
}

export interface RunEvent {
  ts: string;
  event: string;
  detail?: string;
}

export interface BenchmarkRun {
  id: string;
  owner_id: string;
  status: RunStatus;
  profile_snapshot: ProfileSnapshot;
  benchmark_config: BenchmarkConfig;
  started_at: string;
  ended_at?: string | null;
  related_run_id?: string | null;
  source?: 'imported' | 'launched' | 'retry' | null;
  fingerprint?: string | null;
  artifact_ref?: string | null;
  events?: RunEvent[];
  metrics: RunMetrics;
  error_category?: ErrorCategory | null;
  error_message_sanitised?: string | null;
  process_exit_code?: number | null;
  hardware_snapshot?: HardwareSnapshot | null;
}

export interface RunMetrics {
  quality_score?: number | null;
  pass_rate?: number | null;
  ttft_ms?: number | null;
  prompt_tokens?: number | null;
  output_tokens?: number | null;
  prompt_throughput_tps?: number | null;
  generation_throughput_tps?: number | null;
  elapsed_ms?: number | null;
}

export interface BenchmarkConfig {
  name: string;
  max_tokens?: number;
  concurrency?: number;
  prompt_set?: string;
}

export interface ModelProfile {
  id: string;
  owner_id: string;
  name: string;
  model_name: string;
  quantization?: string | null;
  context_length?: number | null;
  inference_engine?: string | null;
  endpoint_url?: string | null;
  api_key_ref?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Paginated<T> {
  items: T[];
  next_cursor?: string | null;
  has_more: boolean;
}

export interface RunFilters {
  status?: RunStatus | null;
  model?: string | null;
  from?: string | null;
  to?: string | null;
  limit?: number;
  cursor?: string | null;
}

export interface ImportError {
  field?: string;
  message: string;
}

export interface ApiError {
  status: number;
  detail: string | Record<string, string>;
}

export type ImportResult =
  | { ok: true; run: BenchmarkRun }
  | { ok: false; status: number; errors: ImportError[]; existingRun?: BenchmarkRun };
