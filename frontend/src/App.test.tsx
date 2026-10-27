import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import App from "./App";

test("renders the application", () => {
  const { container } = render(<App />);
  expect(container).toBeTruthy();
});

test("demo route loads only anonymous synthetic API data", async () => {
  const demoRun = {
    id: 'demo-run-01',
    status: 'completed',
    profile_snapshot: {
      name: 'Synthetic browser model',
      model_name: 'synthetic/browser',
      model_version: null,
      quantisation: null,
    },
    benchmark_config: { name: 'synthetic', temperature: 0, max_tokens: 32 },
    started_at: '2026-01-01T00:00:00Z',
    ended_at: '2026-01-01T00:00:01Z',
    metrics: {},
    hardware_snapshot: { cpu: 'Demo CPU', gpu: null, ram_gb: null, gpu_vram_gb: null, os: null },
  };
  const fetcher = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith('/benchmark/capabilities')) {
      return new Response(JSON.stringify({ enabled: false }));
    }
    if (url.endsWith('/demo/runs')) {
      return new Response(JSON.stringify([demoRun]));
    }
    throw new Error(`Unexpected request ${url}`);
  });
  vi.stubGlobal("fetch", fetcher);
  window.location.hash = "/demo";

  try {
    render(<App />);
    expect(await screen.findByText("Synthetic browser model")).toBeTruthy();
    expect(fetcher.mock.calls.map(([url]) => String(url)).filter((url) => url.includes('/demo/'))).toEqual([
      '/api/v1/demo/runs',
    ]);
    expect(fetcher.mock.calls.some(([url]) => String(url).includes('/runs/import'))).toBe(false);
  } finally {
    window.location.hash = "";
    vi.unstubAllGlobals();
  }
});
