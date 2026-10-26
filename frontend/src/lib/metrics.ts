import type { BenchmarkRun, RunMetrics } from '@/types';
import { fmtMs, fmtNum, fmtRate, fmtTps } from '@/lib/format';

export const METRIC_DEFS: {
  key: keyof RunMetrics;
  label: string;
  unit?: string;
  fmt: (n: number) => string;
  higherBetter?: boolean;
}[] = [
  { key: 'quality_score', label: 'Quality Score', fmt: (n) => fmtRate(n, 2), higherBetter: true },
  { key: 'pass_rate', label: 'Pass Rate', fmt: (n) => fmtRate(n, 2), higherBetter: true },
  { key: 'ttft_ms', label: 'TTFT', fmt: (n) => fmtMs(n), higherBetter: false },
  { key: 'generation_throughput_tps', label: 'Gen Throughput', fmt: (n) => fmtTps(n), higherBetter: true },
  { key: 'prompt_throughput_tps', label: 'Prompt Throughput', fmt: (n) => fmtTps(n), higherBetter: true },
  { key: 'output_tokens', label: 'Output Tokens', fmt: (n) => fmtNum(n), higherBetter: true },
  { key: 'prompt_tokens', label: 'Prompt Tokens', fmt: (n) => fmtNum(n), higherBetter: true },
  { key: 'elapsed_ms', label: 'Elapsed', fmt: (n) => fmtMs(n), higherBetter: false },
];

export function metricAvailable(n: number | null | undefined): boolean {
  return n !== null && n !== undefined && !Number.isNaN(n);
}

export function runModelLabel(r: BenchmarkRun): string {
  return r.profile_snapshot.model_name;
}

export function runProfileLabel(r: BenchmarkRun): string {
  const p = r.profile_snapshot;
  const q = p.quantization ? ` ${p.quantization}` : '';
  return `${p.name}${q}`;
}
