import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import type { BenchmarkRun, ModelProfile } from '@/types';
import { BenchmarkPage } from './BenchmarkPage';
import { RunDetailPage } from './RunDetailPage';

const mocks = vi.hoisted(() => ({
  service: {
    listProfiles: vi.fn(),
    getRun: vi.fn(),
  },
  runner: {
    start: vi.fn(),
    status: vi.fn(),
    retry: vi.fn(),
  },
}));

vi.mock('@/services/benchmark-service', () => ({
  getBenchmarkService: () => mocks.service,
}));
vi.mock('@/services/runner-service', () => ({
  LocalRunnerService: vi.fn(() => mocks.runner),
}));
vi.mock('@/mock/store', () => ({
  getStore: () => ({
    listConfigs: () => [{ name: 'test-config', max_tokens: 32 }],
  }),
}));

const profile: ModelProfile = {
  id: '00000000-0000-0000-0000-000000000001',
  owner_id: 'local',
  name: 'Local test profile',
  model_name: 'test/model',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const failedRun: BenchmarkRun = {
  id: '00000000-0000-0000-0000-000000000002',
  owner_id: 'local',
  status: 'failed',
  profile_snapshot: {
    profile_id: profile.id,
    name: profile.name,
    model_name: profile.model_name,
  },
  benchmark_config: { name: 'test-config' },
  started_at: '2026-01-01T00:00:00Z',
  metrics: {},
  error_category: 'adapter_error',
};

beforeEach(() => {
  mocks.service.listProfiles.mockResolvedValue([profile]);
  mocks.service.getRun.mockResolvedValue(failedRun);
  mocks.runner.start.mockResolvedValue({ id: 'run-id', status: 'running' });
  mocks.runner.status.mockResolvedValue({
    id: 'run-id',
    status: 'running',
    started_at: '2026-01-01T00:00:00Z',
    completed_at: null,
    elapsed_ms: null,
    metrics: {},
    error_category: null,
    error_message_sanitised: null,
  });
  mocks.runner.retry.mockResolvedValue({ id: 'retry-id' });
});

afterEach(() => {
  vi.clearAllMocks();
  window.location.hash = '';
});

test('benchmark launch stays hidden and sends no personal or runner request when capability is off', () => {
  render(<BenchmarkPage runnerEnabled={false} />);
  expect(screen.queryByRole('button', { name: 'Start benchmark' })).toBeNull();
  expect(mocks.service.listProfiles).not.toHaveBeenCalled();
  expect(mocks.runner.start).not.toHaveBeenCalled();
});

test('enabled local launch starts and polls through the backend runner routes', async () => {
  render(<BenchmarkPage runnerEnabled />);
  fireEvent.change(await screen.findByRole('combobox', { name: /profile/i }), {
    target: { value: profile.id },
  });
  fireEvent.click(await screen.findByRole('button', { name: 'Start benchmark' }));

  await waitFor(() => expect(mocks.runner.start).toHaveBeenCalledOnce());
  expect(mocks.runner.start).toHaveBeenCalledWith(
    profile.id,
    expect.stringMatching(/^[0-9a-f-]{36}$/i)
  );
  await waitFor(() => expect(mocks.runner.status).toHaveBeenCalledWith('run-id'));
});

test('local retry uses the backend runner route when capability is enabled', async () => {
  render(<RunDetailPage id={failedRun.id} runnerEnabled />);
  fireEvent.click(await screen.findByRole('button', { name: 'Retry run' }));
  await waitFor(() => expect(mocks.runner.retry).toHaveBeenCalledWith(failedRun.id));
});
