import { expect, expectTypeOf, test } from "vitest";
import type { components, paths } from "@/types/api.generated";
import type { ErrorCategory, RunStatus } from "@/types";

type BenchmarkRun = components["schemas"]["BenchmarkRun"];
type RunMetrics = components["schemas"]["RunMetrics"];
type ModelProfile = components["schemas"]["ModelProfile"];
type ProfileCreate = components["schemas"]["ProfileCreate"];
type ProfileUpdate = components["schemas"]["ProfileUpdate"];

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
  model_version: null,
  quantisation: null,
  endpoint_url: null,
  hardware_notes: null,
  inference_config: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const createProfile: ProfileCreate = {
  name: "Profile",
  model_name: "model",
  inference_config: { temperature: 0.2 },
};

const updateProfile: ProfileUpdate = {
  quantisation: "Q4_K_M",
  endpoint_url: "http://localhost:9000/v1",
};

test("generated contract types compile for representative payloads", () => {
  expect(validRun.status).toBe("completed");
  expect(validRun.metrics.quality_score).toBeNull();
  expect(validProfile.endpoint_url).toBeNull();
  expect(createProfile.model_name).toBe("model");
  expect(updateProfile.quantisation).toBe("Q4_K_M");
});

test("contract exposes required endpoints", () => {
  expectTypeOf<paths>().toHaveProperty("/health");
  expectTypeOf<paths>().toHaveProperty("/api/v1/profiles");
  expectTypeOf<paths>().toHaveProperty("/api/v1/profiles/{id}");
  expectTypeOf<paths>().toHaveProperty("/api/v1/runs");
  expectTypeOf<paths>().toHaveProperty("/api/v1/runs/import");
  expectTypeOf<paths>().toHaveProperty("/api/v1/runs/compare");
  expectTypeOf<paths>().toHaveProperty("/benchmark/runs");
  expectTypeOf<paths>().toHaveProperty("/benchmark/runs/{id}");
  expectTypeOf<paths>().toHaveProperty("/benchmark/capabilities");
  expectTypeOf<paths>().toHaveProperty("/runs/{id}/retry");
  expectTypeOf<paths>().not.toHaveProperty("/benchmark/runs/{id}/cancel");
  expectTypeOf<paths>().toHaveProperty("/api/v1/demo/runs");
  expectTypeOf<paths>().toHaveProperty("/api/v1/demo/runs/{id}");
});

test("interim runner contract validates IDs and exposes no cancellation mapping", () => {
  type StartRequest = components["schemas"]["BenchmarkStartRequest"];
  expectTypeOf<StartRequest>().toHaveProperty("profile_id");
  expectTypeOf<StartRequest>().toHaveProperty("config_id");
  expectTypeOf<components["schemas"]["RunStatus"]>().toEqualTypeOf<
    "running" | "completed" | "failed" | "interrupted"
  >();
  expectTypeOf<RunStatus>().toEqualTypeOf<
    "running" | "completed" | "failed" | "interrupted"
  >();
  expectTypeOf<"cancelled">().not.toMatchTypeOf<RunStatus>();
  expectTypeOf<"CANCELLED">().not.toMatchTypeOf<ErrorCategory>();
});

test("profile contract has CRUD operations and excludes unapproved fields", () => {
  expectTypeOf<paths["/api/v1/profiles"]["get"]>().not.toBeNever();
  expectTypeOf<paths["/api/v1/profiles"]["post"]>().not.toBeNever();
  expectTypeOf<paths["/api/v1/profiles/{id}"]["get"]>().not.toBeNever();
  expectTypeOf<paths["/api/v1/profiles/{id}"]["patch"]>().not.toBeNever();
  expectTypeOf<paths["/api/v1/profiles/{id}"]["delete"]>().not.toBeNever();
  expectTypeOf<ModelProfile>().not.toHaveProperty("api_key_ref");
  expectTypeOf<ProfileCreate>().not.toHaveProperty("owner_id");
});

test("nullable metrics are represented as number | null", () => {
  const m: RunMetrics = { quality_score: null, ttft_ms: 12 };
  expect(m.quality_score).toBeNull();
  expect(m.ttft_ms).toBe(12);
});
