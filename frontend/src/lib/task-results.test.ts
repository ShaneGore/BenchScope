import { describe, expect, it } from 'vitest';
import type { BenchmarkRun } from '@/types';
import { comparableTaskRuns, taskResult } from './task-results';

const details = {
  benchmark_id: 'local-coding',
  release: 'release-1',
  manifest_sha256: 'a'.repeat(64),
  expected_task_ids: ['task-a', 'task-b'],
};

function run(overrides: Partial<BenchmarkRun> = {}): BenchmarkRun {
  return {
    id: 'run',
    owner_id: 'owner',
    status: 'completed',
    profile_snapshot: { profile_id: 'imported', name: 'Model', model_name: 'model' },
    benchmark_config: { name: 'local-coding' },
    started_at: '2026-10-26T10:00:00Z',
    metrics: {},
    benchmark_details: details,
    task_results: [{ task_id: 'task-a', passed: true }],
    ...overrides,
  };
}

describe('task result comparison', () => {
  it('requires matching benchmark identity, release, manifest and task set', () => {
    expect(comparableTaskRuns([run(), run({ id: 'two' })])).toBe(true);
    expect(comparableTaskRuns([run(), run({ benchmark_details: { ...details, release: 'release-2' } })])).toBe(false);
    expect(comparableTaskRuns([run(), run({ benchmark_details: { ...details, expected_task_ids: ['task-a'] } })])).toBe(false);
    expect(comparableTaskRuns([run(), run({ benchmark_details: null })])).toBe(false);
  });

  it('returns null for expected tasks that were not run', () => {
    expect(taskResult(run(), 'task-a')).toBe(true);
    expect(taskResult(run(), 'task-b')).toBeNull();
  });
});
