import type { BenchmarkRun } from '@/types';

export function comparableTaskRuns(runs: BenchmarkRun[]): boolean {
  const first = runs[0]?.benchmark_details;
  if (!first || runs.length < 2) return false;
  const expected = [...first.expected_task_ids].sort();
  return runs.every((run) => {
    const details = run.benchmark_details;
    return (
      details?.benchmark_id === first.benchmark_id &&
      details.release === first.release &&
      details.manifest_sha256 === first.manifest_sha256 &&
      JSON.stringify([...details.expected_task_ids].sort()) === JSON.stringify(expected)
    );
  });
}

export function taskResult(run: BenchmarkRun, taskId: string): boolean | null {
  return run.task_results?.find((result) => result.task_id === taskId)?.passed ?? null;
}
