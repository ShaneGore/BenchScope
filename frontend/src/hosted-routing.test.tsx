import { cleanup, render, screen, waitFor } from '@testing-library/react';
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

  expect(await screen.findByText('Recent activity')).toBeTruthy();
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
  expect(await screen.findByText('Recent activity')).toBeTruthy();
  expect(fetcher.mock.calls.every(([url]) => !String(url).includes('/benchmark/'))).toBe(true);
});

test('hosted benchmark direct navigation redirects to the mode-appropriate route', async () => {
  window.location.hash = '/benchmark';
  render(<App />);
  await waitFor(() => expect(window.location.hash).toBe('#/demo'));
  expect(await screen.findByText('Recent activity')).toBeTruthy();
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
