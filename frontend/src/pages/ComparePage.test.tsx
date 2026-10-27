import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { BenchmarkRun } from '@/types';
import { ComparePage } from './ComparePage';

const { compareRuns } = vi.hoisted(() => ({ compareRuns: vi.fn() }));

vi.mock('@/services/benchmark-service', () => ({
  getBenchmarkService: () => ({ compareRuns }),
}));

const details = {
  benchmark_id: 'local-coding',
  release: 'release-1',
  manifest_sha256: 'a'.repeat(64),
  expected_task_ids: ['task-a', 'task-b'],
};

function run(id: string, detailChanges: Partial<typeof details> = {}): BenchmarkRun {
  return {
    id,
    owner_id: 'owner',
    status: 'completed',
    profile_snapshot: { profile_id: 'imported', name: id, model_name: 'model' },
    benchmark_config: { name: 'local-coding' },
    started_at: '2026-10-26T10:00:00Z',
    metrics: { pass_rate: 0.5 },
    benchmark_details: { ...details, ...detailChanges },
    task_results: [{ task_id: 'task-a', passed: true }],
  };
}

describe('ComparePage task outcomes', () => {
  afterEach(cleanup);
  beforeEach(() => compareRuns.mockReset());

  it('shows matching task outcomes and missing tasks as not run', async () => {
    compareRuns.mockResolvedValue([run('one'), run('two')]);
    render(<ComparePage ids={['one', 'two']} />);

    expect(await screen.findByText('Per-task outcomes')).toBeTruthy();
    expect(screen.getAllByText('Not run')).toHaveLength(2);
    expect(screen.getAllByText('Pass')).toHaveLength(2);
  });

  it('hides task outcomes and pass rates for mismatched v2 releases', async () => {
    compareRuns.mockResolvedValue([run('one'), run('two', { release: 'release-2' })]);
    render(<ComparePage ids={['one', 'two']} />);

    expect(
      await screen.findByText(/Task outcomes and pass rates are hidden/)
    ).toBeTruthy();
    expect(screen.queryByText('Per-task outcomes')).toBeNull();
    expect(screen.queryByText('Pass Rate')).toBeNull();
  });

  it.each([
    ['benchmark IDs', { benchmark_id: 'other-benchmark' }],
    ['manifest digests', { manifest_sha256: 'b'.repeat(64) }],
  ])('hides task outcomes and pass rates for mismatched %s', async (_label, changes) => {
    compareRuns.mockResolvedValue([run('one'), run('two', changes)]);
    render(<ComparePage ids={['one', 'two']} />);

    expect(
      await screen.findByText(/Task outcomes and pass rates are hidden/)
    ).toBeTruthy();
    expect(screen.queryByText('Per-task outcomes')).toBeNull();
    expect(screen.queryByText('Pass Rate')).toBeNull();
  });
});
