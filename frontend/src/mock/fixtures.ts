import type {
  BenchmarkRun,
  ModelProfile,
  RunStatus,
} from '@/types';

const NOW = Date.UTC(2026, 9, 26, 14, 0, 0);
const iso = (offsetMin: number) =>
  new Date(NOW + offsetMin * 60_000).toISOString();
const uid = (p: string) => `${p}_${Math.random().toString(36).slice(2, 10)}`;

export const DEMO_OWNER = 'demo';

function run(
  o: Partial<BenchmarkRun> & { id: string; status: RunStatus }
): BenchmarkRun {
  return {
    owner_id: DEMO_OWNER,
    profile_snapshot: {
      profile_id: 'p_demo1',
      name: 'Mistral 7B Q4',
      model_name: 'mistral-7b-instruct',
      quantization: 'Q4_K_M',
      context_length: 4096,
      inference_engine: 'llama.cpp',
    },
    benchmark_config: { name: 'coding-pilot-v2', max_tokens: 2048, concurrency: 1, prompt_set: 'coding-pilot' },
    started_at: iso(-180),
    ended_at: iso(-178),
    source: 'launched',
    artifact_ref: 'runs/2026/demo.jsonl',
    hardware_snapshot: {
      gpu: 'NVIDIA RTX 4060 8GB',
      gpu_vram_gb: 8,
      cpu: 'Ryzen 7 7700X',
      ram_gb: 32,
      os: 'Linux 6.9',
    },
    metrics: {},
    ...o,
  } as BenchmarkRun;
}

export const demoRuns: BenchmarkRun[] = [
  run({
    id: 'r_demo_01',
    status: 'completed',
    profile_snapshot: {
      profile_id: 'p_demo1',
      name: 'Llama 3.1 8B Q4',
      model_name: 'llama-3.1-8b-instruct',
      quantization: 'Q4_K_M',
      context_length: 8192,
      inference_engine: 'llama.cpp',
    },
    benchmark_config: { name: 'coding-pilot-v2', max_tokens: 2048, concurrency: 1, prompt_set: 'coding-pilot' },
    started_at: iso(-240),
    ended_at: iso(-232),
    metrics: {
      quality_score: 0.62,
      pass_rate: 0.58,
      ttft_ms: 412,
      prompt_tokens: 18400,
      output_tokens: 9120,
      prompt_throughput_tps: 1820.4,
      generation_throughput_tps: 41.2,
      elapsed_ms: 232000,
    },
    events: [
      { ts: iso(-240), event: 'run_started' },
      { ts: iso(-238), event: 'model_loaded', detail: '8.4 GB resident' },
      { ts: iso(-236), event: 'prompt_batch_started' },
      { ts: iso(-234), event: 'generation_started' },
      { ts: iso(-232), event: 'run_completed' },
    ],
  }),
  run({
    id: 'r_demo_02',
    status: 'completed',
    profile_snapshot: {
      profile_id: 'p_demo2',
      name: 'Mistral 7B Q4',
      model_name: 'mistral-7b-instruct',
      quantization: 'Q4_K_M',
      context_length: 4096,
      inference_engine: 'llama.cpp',
    },
    started_at: iso(-200),
    ended_at: iso(-193),
    metrics: {
      quality_score: 0.55,
      pass_rate: 0.51,
      ttft_ms: 318,
      prompt_tokens: 18400,
      output_tokens: 8410,
      prompt_throughput_tps: 2240.1,
      generation_throughput_tps: 48.7,
      elapsed_ms: 193000,
    },
  }),
  run({
    id: 'r_demo_03',
    status: 'completed',
    profile_snapshot: {
      profile_id: 'p_demo3',
      name: 'Phi-3 Mini Q5',
      model_name: 'phi-3-mini-4k-instruct',
      quantization: 'Q5_K_M',
      context_length: 4096,
      inference_engine: 'llama.cpp',
    },
    started_at: iso(-160),
    ended_at: iso(-155),
    metrics: {
      quality_score: 0.41,
      pass_rate: 0.36,
      ttft_ms: 540,
      prompt_tokens: 18400,
      output_tokens: 7320,
      prompt_throughput_tps: 980.5,
      generation_throughput_tps: 28.9,
      elapsed_ms: 155000,
    },
  }),
  run({
    id: 'r_demo_04',
    status: 'failed',
    profile_snapshot: {
      profile_id: 'p_demo4',
      name: 'Llama 3.1 70B Q3',
      model_name: 'llama-3.1-70b-instruct',
      quantization: 'Q3_K_M',
      context_length: 8192,
      inference_engine: 'llama.cpp',
    },
    started_at: iso(-120),
    ended_at: iso(-118),
    metrics: {},
    error_category: 'OOM',
    error_message_sanitised:
      'Model load exceeded available VRAM. Reduce context length or quantization.',
    process_exit_code: 137,
    hardware_snapshot: {
      gpu: 'NVIDIA RTX 4060 8GB',
      gpu_vram_gb: 8,
      cpu: 'Ryzen 7 7700X',
      ram_gb: 32,
      os: 'Linux 6.9',
    },
    events: [
      { ts: iso(-120), event: 'run_started' },
      { ts: iso(-119), event: 'model_load_started' },
      { ts: iso(-118), event: 'run_failed', detail: 'OOM' },
    ],
  }),
  run({
    id: 'r_demo_05',
    status: 'interrupted',
    profile_snapshot: {
      profile_id: 'p_demo1',
      name: 'Llama 3.1 8B Q4',
      model_name: 'llama-3.1-8b-instruct',
      quantization: 'Q4_K_M',
      context_length: 8192,
      inference_engine: 'llama.cpp',
    },
    started_at: iso(-90),
    ended_at: iso(-88),
    metrics: {},
    error_category: 'HOST_RESTART',
    error_message_sanitised:
      'Host process restarted mid-run; partial output discarded.',
    process_exit_code: null,
    events: [
      { ts: iso(-90), event: 'run_started' },
      { ts: iso(-88), event: 'run_interrupted', detail: 'HOST_RESTART' },
    ],
  }),
  run({
    id: 'r_demo_06',
    status: 'completed',
    profile_snapshot: {
      profile_id: 'p_demo5',
      name: 'Qwen2.5 14B Q4',
      model_name: 'qwen2.5-14b-instruct',
      quantization: 'Q4_K_M',
      context_length: 8192,
      inference_engine: 'llama.cpp',
    },
    started_at: iso(-50),
    ended_at: iso(-44),
    metrics: {
      quality_score: 0.68,
      pass_rate: 0.61,
      ttft_ms: 360,
      prompt_tokens: 18400,
      output_tokens: 10150,
      prompt_throughput_tps: 1610.2,
      generation_throughput_tps: 38.1,
      elapsed_ms: 272000,
    },
  }),
  run({
    id: 'r_demo_07',
    status: 'cancelled',
    profile_snapshot: {
      profile_id: 'p_demo2',
      name: 'Mistral 7B Q4',
      model_name: 'mistral-7b-instruct',
      quantization: 'Q4_K_M',
      context_length: 4096,
      inference_engine: 'llama.cpp',
    },
    started_at: iso(-20),
    ended_at: iso(-19),
    metrics: {},
    error_category: 'CANCELLED',
    error_message_sanitised: 'Run cancelled by user before completion.',
    process_exit_code: 130,
    events: [
      { ts: iso(-20), event: 'run_started' },
      { ts: iso(-19), event: 'run_cancelled' },
    ],
  }),
];

export const demoProfiles: ModelProfile[] = [
  {
    id: 'p_demo1',
    owner_id: DEMO_OWNER,
    name: 'Llama 3.1 8B Q4',
    model_name: 'llama-3.1-8b-instruct',
    quantization: 'Q4_K_M',
    context_length: 8192,
    inference_engine: 'llama.cpp',
    endpoint_url: 'http://localhost:8080/v1',
    api_key_ref: 'local-dev',
    created_at: iso(-10000),
    updated_at: iso(-2000),
  },
  {
    id: 'p_demo2',
    owner_id: DEMO_OWNER,
    name: 'Mistral 7B Q4',
    model_name: 'mistral-7b-instruct',
    quantization: 'Q4_K_M',
    context_length: 4096,
    inference_engine: 'llama.cpp',
    endpoint_url: 'http://localhost:8081/v1',
    api_key_ref: 'local-dev',
    created_at: iso(-9000),
    updated_at: iso(-1500),
  },
  {
    id: 'p_demo3',
    owner_id: DEMO_OWNER,
    name: 'Phi-3 Mini Q5',
    model_name: 'phi-3-mini-4k-instruct',
    quantization: 'Q5_K_M',
    context_length: 4096,
    inference_engine: 'llama.cpp',
    endpoint_url: null,
    api_key_ref: null,
    created_at: iso(-8000),
    updated_at: iso(-1200),
  },
  {
    id: 'p_demo4',
    owner_id: DEMO_OWNER,
    name: 'Llama 3.1 70B Q3',
    model_name: 'llama-3.1-70b-instruct',
    quantization: 'Q3_K_M',
    context_length: 8192,
    inference_engine: 'llama.cpp',
    endpoint_url: 'http://localhost:8082/v1',
    api_key_ref: 'local-dev',
    created_at: iso(-7000),
    updated_at: iso(-1000),
  },
  {
    id: 'p_demo5',
    owner_id: DEMO_OWNER,
    name: 'Qwen2.5 14B Q4',
    model_name: 'qwen2.5-14b-instruct',
    quantization: 'Q4_K_M',
    context_length: 8192,
    inference_engine: 'llama.cpp',
    endpoint_url: 'http://localhost:8083/v1',
    api_key_ref: 'local-dev',
    created_at: iso(-6000),
    updated_at: iso(-800),
  },
];

export const demoConfigs = [
  { name: 'coding-pilot-v2', max_tokens: 2048, concurrency: 1, prompt_set: 'coding-pilot' },
  { name: 'coding-pilot-quick', max_tokens: 512, concurrency: 1, prompt_set: 'coding-pilot' },
  { name: 'coding-pilot-full', max_tokens: 4096, concurrency: 2, prompt_set: 'coding-pilot' },
];

export function newId(prefix: string) {
  return uid(prefix);
}
