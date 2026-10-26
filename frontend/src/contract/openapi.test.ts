import { expect, expectTypeOf, test } from "vitest";
import type { components, paths } from "@/types/api.generated";

type BenchmarkRun = components["schemas"]["BenchmarkRun"];
type RunMetrics = components["schemas"]["RunMetrics"];
type ModelProfile = components["schemas"]["ModelProfile"];

const validRun: BenchmarkRun = {
  id: "r_1",
  owner_id: "u_1",
  status: "completed",
  profile_snapshot: {
    profile_id: "p_1",
    name: "Profile",
    model_name: "model",
    quantization: null,
    context_length: null,
    inference_engine: null,
  },
  benchmark_config: { name: "cfg" },
  started_at: "2026-01-01T00:00:00Z",
  ended_at: "2026-01-01T00:01:00Z",
  metrics: {
    quality_score: null,
    pass_rate: 0.5,
    ttft_ms: null,
    prompt_tokens: null,
    output_tokens: 10,
    prompt_throughput_tps: null,
    generation_throughput_tps: 20,
    elapsed_ms: 1000,
  },
};

const validProfile: ModelProfile = {
  id: "p_1",
  owner_id: "u_1",
  name: "Profile",
  model_name: "model",
  quantization: null,
  context_length: null,
  inference_engine: null,
  endpoint_url: null,
  api_key_ref: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

test("generated contract types compile for representative payloads", () => {
  expect(validRun.status).toBe("completed");
  expect(validRun.metrics.quality_score).toBeNull();
  expect(validProfile.endpoint_url).toBeNull();
});

test("contract exposes required endpoints", () => {
  expectTypeOf<paths>().toHaveProperty("/health");
  expectTypeOf<paths>().toHaveProperty("/profiles");
  expectTypeOf<paths>().toHaveProperty("/runs");
  expectTypeOf<paths>().toHaveProperty("/runs/import");
  expectTypeOf<paths>().toHaveProperty("/runs/compare");
  expectTypeOf<paths>().toHaveProperty("/benchmark/runs");
  expectTypeOf<paths>().toHaveProperty("/demo/runs");
});

test("nullable metrics are represented as number | null", () => {
  const m: RunMetrics = { quality_score: null, ttft_ms: 12 };
  expect(m.quality_score).toBeNull();
  expect(m.ttft_ms).toBe(12);
});

