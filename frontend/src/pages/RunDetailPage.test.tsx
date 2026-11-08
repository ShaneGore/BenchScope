import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { RunDetailPage } from './RunDetailPage';

const { store } = vi.hoisted(() => ({ store: { getRun: vi.fn() } }));
vi.mock('@/services/benchmark-service', () => ({
  getBenchmarkService: () => store,
}));
const { getRun } = store;

beforeEach(() => getRun.mockReset());
afterEach(cleanup);

test.each([undefined, null])('detail rejection %s shows retry and preserves not found', async (reason) => {
  getRun.mockRejectedValueOnce(reason).mockRejectedValueOnce({ status: 404, detail: 'Not found' });
  render(<RunDetailPage id="missing" serviceMode="demo" />);
  expect(await screen.findByRole('alert')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: /retry request/i }));
  expect(await screen.findByText('Run not found')).toBeTruthy();
  expect(getRun).toHaveBeenCalledTimes(2);
});

test('detail ignores a late rejection after navigation', async () => {
  let rejectOld!: (reason: unknown) => void;
  getRun.mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectOld = reject; }))
    .mockRejectedValueOnce({ status: 404, detail: 'Not found' });
  const view = render(<RunDetailPage id="old" serviceMode="demo" />);
  view.rerender(<RunDetailPage id="new" serviceMode="demo" />);
  expect(await screen.findByText('No run exists with id new.')).toBeTruthy();
  await act(async () => rejectOld(undefined));
  expect(screen.getByText('No run exists with id new.')).toBeTruthy();
  expect(screen.queryByRole('alert')).toBeNull();
});

test.each(['success', 'failure'])('late polling %s cannot replace the next run', async (outcome) => {
  vi.useFakeTimers();
  try {
    let settle!: (value: unknown) => void;
    const running = {
      id: 'old', status: 'running', metrics: {}, profile_snapshot: { name: 'Old', model_name: 'Old' },
      benchmark_config: { name: 'test' }, started_at: '2026-01-01T00:00:00Z',
    };
    getRun.mockResolvedValueOnce(running)
      .mockImplementationOnce(() => new Promise((resolve, reject) => {
        settle = outcome === 'success' ? resolve : reject;
      }))
      .mockRejectedValueOnce({ status: 404, detail: 'Not found' });
    const view = render(<RunDetailPage id="old" serviceMode="hosted" />);
    await act(async () => {});
    await act(async () => vi.advanceTimersByTimeAsync(1000));
    view.rerender(<RunDetailPage id="new" serviceMode="hosted" />);
    await act(async () => {});
    expect(screen.getByText('No run exists with id new.')).toBeTruthy();
    await act(async () => settle(outcome === 'success' ? running : new Error('late')));
    expect(screen.getByText('No run exists with id new.')).toBeTruthy();
  } finally {
    vi.useRealTimers();
  }
});

test('malformed personal detail shows a retryable error and recovers', async () => {
  const valid = {
    id: 'run-1', owner_id: 'owner', status: 'completed', started_at: '2026-01-01T00:00:00Z',
    profile_snapshot: { name: 'Recovered profile', model_name: 'Model' }, benchmark_config: { name: 'Config' },
    metrics: {}, ended_at: null,
  };
  getRun.mockRejectedValueOnce({ status: 0, detail: 'Could not read response. Please retry.' })
    .mockResolvedValueOnce(valid);
  render(<RunDetailPage id="run-1" serviceMode="hosted" />);
  expect(await screen.findByRole('alert')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: /retry request/i }));
  expect((await screen.findAllByText('Recovered profile')).length).toBeGreaterThan(0);
});

test('polling is suspended while a retry is pending', async () => {
  vi.useFakeTimers();
  try {
    let finish!: (value: unknown) => void;
    const running = {
      id: 'run-1', status: 'running', metrics: {}, profile_snapshot: { name: 'Profile', model_name: 'Model' },
      benchmark_config: { name: 'test' }, started_at: '2026-01-01T00:00:00Z',
    };
    getRun.mockResolvedValueOnce(running)
      .mockRejectedValueOnce({ status: 0, detail: 'Poll failed' })
      .mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
    render(<RunDetailPage id="run-1" serviceMode="hosted" />);
    await act(async () => {});
    await act(async () => vi.advanceTimersByTimeAsync(1000));
    expect(screen.getByRole('alert')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /retry request/i }));
    await act(async () => vi.advanceTimersByTimeAsync(3000));
    expect(getRun).toHaveBeenCalledTimes(3);
    await act(async () => finish({ ...running, status: 'completed' }));
    expect(screen.queryByRole('alert')).toBeNull();
  } finally {
    vi.useRealTimers();
  }
});
