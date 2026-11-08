import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';

let fetcher: ReturnType<typeof vi.fn>;

const auth = vi.hoisted(() => ({
  isLoaded: true,
  isSignedIn: false as boolean | undefined,
}));

vi.mock('@clerk/react', () => ({
  useAuth: () => auth,
  SignIn: () => 'Sign in widget',
  SignUp: () => 'Sign up widget',
}));

vi.mock('@/lib/mode', () => ({
  APP_MODE: 'hosted',
  canLaunch: false,
  canImport: true,
  canEditProfiles: true,
  canDelete: true,
  canRetry: false,
  showEndpointFields: false,
  isDemo: false,
  isHosted: true,
  isLocal: false,
  modeLabel: { local: 'Local', hosted: 'Hosted', demo: 'Demo' },
}));

import App from './App';

beforeEach(() => {
  auth.isLoaded = true;
  auth.isSignedIn = false;
  window.location.hash = '';
  fetcher = vi.fn().mockResolvedValue(
    new Response(JSON.stringify([]), { status: 200 })
  );
  vi.stubGlobal('fetch', fetcher);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.location.hash = '';
});

test('anonymous hosted root lands in the read-only demo without capability or runner requests', async () => {
  window.location.hash = '/';
  render(<App />);

  expect(await screen.findByText('Benchmark configurations')).toBeTruthy();
  await waitFor(() => expect(window.location.hash).toBe('#/demo'));
  const requests = fetcher.mock.calls.map(([url, init]) => ({
    url: String(url),
    method: init?.method ?? 'GET',
  }));
  expect(requests).toEqual([{ url: '/api/v1/demo/runs', method: 'GET' }]);
  expect(screen.queryByRole('button', { name: /launch/i })).toBeNull();
  expect(screen.queryByRole('button', { name: /import/i })).toBeNull();
});

test('anonymous hosted protected routes go to sign-in while demo remains public', async () => {
  window.location.hash = '/runs';
  const { rerender } = render(<App />);
  await waitFor(() => expect(window.location.hash).toBe('#/sign-in'));
  expect(screen.getByText('Sign in widget')).toBeTruthy();

  window.location.hash = '/demo';
  rerender(<App />);
  expect(await screen.findByText('Benchmark configurations')).toBeTruthy();
  expect(fetcher.mock.calls.every(([url]) => !String(url).includes('/benchmark/'))).toBe(true);
});

test('hosted benchmark direct navigation redirects to the mode-appropriate route', async () => {
  window.location.hash = '/benchmark';
  render(<App />);
  await waitFor(() => expect(window.location.hash).toBe('#/demo'));
  expect(await screen.findByText('Benchmark configurations')).toBeTruthy();
  expect(fetcher.mock.calls).toHaveLength(1);
  expect(String(fetcher.mock.calls[0]?.[0])).toBe('/api/v1/demo/runs');
});

test('signed-in hosted benchmark direct navigation returns to the personal dashboard', async () => {
  auth.isSignedIn = true;
  window.location.hash = '/benchmark';
  render(<App />);
  await waitFor(() => expect(window.location.hash).toBe('#/'));
  expect(fetcher).not.toHaveBeenCalled();
});


test('anonymous comparison deep links stay public and use only the demo catalogue', async () => {
  window.location.hash = '/demo/compare?ids=one,two';
  const base = { status: 'completed', profile_snapshot: { name: 'Model', model_name: 'model', model_version: null, quantisation: null }, benchmark_config: { name: 'Reasoning off', temperature: 0, max_tokens: 100 }, started_at: null, ended_at: null, metrics: { pass_rate: 0.5, generation_throughput_tps: null }, hardware_snapshot: {} };
  fetcher.mockImplementation(async () => new Response(JSON.stringify([{ ...base, id: 'one' }, { ...base, id: 'two' }])));
  render(<App />);
  expect(await screen.findByText('Pass rate comparison')).toBeTruthy();
  expect(window.location.hash).toBe('#/demo/compare?ids=one,two');
  expect(fetcher.mock.calls.map(([url]) => String(url))).toEqual(['/api/v1/demo/runs']);
  expect(screen.queryByRole('button', { name: 'Import' })).toBeNull();
  expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull();
});

test('anonymous demo failure retries and detail navigation ignores late catalogue results', async () => {
  let resolveOld!: (response: Response) => void;
  fetcher.mockImplementationOnce(() => Promise.resolve(new Response('{}', { status: 503 })))
    .mockImplementationOnce(() => new Promise<Response>((resolve) => { resolveOld = resolve; }))
    .mockImplementationOnce(() => Promise.resolve(new Response('{}', { status: 404 })));
  window.location.hash = '/demo';
  render(<App />);
  expect(await screen.findByRole('alert')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: /retry request/i }));
  expect(screen.getByRole('status').textContent).toMatch(/loading demo/i);
  act(() => {
    window.location.hash = '/demo/runs/missing';
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  });

  expect(await screen.findByText('Run not found')).toBeTruthy();
  await act(async () => { resolveOld(new Response('[]')); });
  expect(screen.getByText('Run not found')).toBeTruthy();
  expect(fetcher.mock.calls.map(([url]) => String(url))).toEqual([
    '/api/v1/demo/runs', '/api/v1/demo/runs', '/api/v1/demo/runs/missing',
  ]);
});

test.each([
  ['/demo', 'Benchmark configurations'],
  ['/demo/compare', 'Compare demo configurations'],
])('anonymous %s retries a rejection without a reason', async (path, heading) => {
  fetcher.mockRejectedValueOnce(undefined).mockResolvedValueOnce(new Response('[]'));
  window.location.hash = path;
  render(<App />);
  expect(await screen.findByRole('alert')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: /retry request/i }));
  expect(await screen.findByText(heading)).toBeTruthy();
  expect(fetcher).toHaveBeenCalledTimes(2);
});
