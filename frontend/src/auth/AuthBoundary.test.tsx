import { useState, type ReactNode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  order: [] as string[],
  auth: {
    getToken: vi.fn(async () => 'session-jwt'),
    isLoaded: true,
    isSignedIn: true,
    signOut: vi.fn(async () => {
      mocks.order.push('sign-out');
    }),
    userId: 'user-1' as string | undefined,
  },
  tokenProvider: undefined as (() => Promise<string | null>) | undefined,
  setApiToken: (provider?: () => Promise<string | null>) => {
    mocks.tokenProvider = provider;
    mocks.order.push(provider ? 'set-token' : 'clear-token');
  },
}));

vi.mock('@clerk/react', () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => children,
  useAuth: () => mocks.auth,
}));

vi.mock('@/mock/store', () => ({
  resetStore: () => mocks.order.push('clear-user-state'),
}));

vi.mock('@/lib/mode', () => ({ APP_MODE: 'hosted' }));
vi.mock('@/services/api-benchmark-service', () => ({
  setApiSessionTokenProvider: mocks.setApiToken,
}));

let AuthBoundary: typeof import('./AuthBoundary').AuthBoundary;
let HostedAuthControls: typeof import('./AuthBoundary').HostedAuthControls;

beforeEach(async () => {
  vi.stubEnv('VITE_CLERK_PUBLISHABLE_KEY', 'pk_test_example');
  vi.resetModules();
  ({ AuthBoundary, HostedAuthControls } = await import('./AuthBoundary'));
  mocks.order.length = 0;
  mocks.tokenProvider = undefined;
  mocks.auth.isLoaded = true;
  mocks.auth.isSignedIn = true;
  mocks.auth.userId = 'user-1';
  mocks.auth.getToken.mockResolvedValue('session-jwt');
  mocks.auth.signOut.mockClear();
});

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

test('shows startup progress until authentication is ready', async () => {
  mocks.auth.isLoaded = false;
  const view = render(<AuthBoundary><div>Application ready</div></AuthBoundary>);
  expect(screen.getByRole('status').textContent).toMatch(/starting benchscope.*please wait/i);
  expect(screen.queryByText('Application ready')).toBeNull();
  mocks.auth.isLoaded = true;
  view.rerender(<AuthBoundary><div>Application ready</div></AuthBoundary>);
  expect(await screen.findByText('Application ready')).toBeTruthy();
});

test('missing hosted Clerk configuration fails closed', async () => {
  vi.stubEnv('VITE_CLERK_PUBLISHABLE_KEY', '');
  vi.resetModules();
  const { AuthBoundary: UnconfiguredBoundary } = await import('./AuthBoundary');
  render(<UnconfiguredBoundary><div>Protected content</div></UnconfiguredBoundary>);
  expect(screen.getByRole('alert').textContent).toMatch(/not configured/i);
  expect(screen.queryByText('Protected content')).toBeNull();
  expect(mocks.tokenProvider).toBeUndefined();
});

test('times out startup and retry restarts without showing stale content', () => {
  vi.useFakeTimers();
  try {
    mocks.auth.isLoaded = false;
    const view = render(<AuthBoundary><div>Protected content</div></AuthBoundary>);
    act(() => vi.advanceTimersByTime(5000));
    expect(screen.getByRole('status').textContent).toMatch(/cold start/i);
    act(() => vi.advanceTimersByTime(25000));
    expect(screen.getByRole('alert').textContent).toMatch(/authentication.*too long/i);
    mocks.auth.isLoaded = true;
    view.rerender(<AuthBoundary><div>Protected content</div></AuthBoundary>);
    expect(screen.queryByText('Protected content')).toBeNull();
    mocks.auth.isLoaded = false;
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(screen.getByRole('status')).toBeTruthy();
    mocks.auth.isLoaded = true;
    view.rerender(<AuthBoundary><div>Protected content</div></AuthBoundary>);
    expect(screen.getByText('Protected content')).toBeTruthy();
  } finally {
    vi.useRealTimers();
  }
});

test('clears user-scoped state before signing out', async () => {
  render(<HostedAuthControls />);
  fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));

  await waitFor(() => expect(mocks.auth.signOut).toHaveBeenCalledOnce());
  expect(mocks.order).toEqual(['clear-user-state', 'clear-token', 'sign-out']);
});

test('identity change clears state and remounts before the next identity is shown', async () => {
  function PersonalState() {
    const [value, setValue] = useState(0);
    return <button onClick={() => setValue(value + 1)}>Personal {value}</button>;
  }

  const view = render(<AuthBoundary><PersonalState /></AuthBoundary>);
  fireEvent.click(await screen.findByRole('button', { name: 'Personal 0' }));
  expect(screen.getByRole('button', { name: 'Personal 1' })).toBeTruthy();

  mocks.order.length = 0;
  mocks.auth.userId = 'user-2';
  mocks.auth.getToken.mockResolvedValue('token-b');
  view.rerender(<AuthBoundary><PersonalState /></AuthBoundary>);

  expect(await screen.findByRole('button', { name: 'Personal 0' })).toBeTruthy();
  await expect(mocks.tokenProvider?.()).resolves.toBe('token-b');
  expect(mocks.order).toContain('clear-token');
  expect(mocks.order).toContain('clear-user-state');
  expect(mocks.order.indexOf('clear-user-state')).toBeLessThan(
    mocks.order.lastIndexOf('set-token')
  );

  mocks.auth.isSignedIn = false;
  mocks.auth.userId = undefined;
  view.rerender(<AuthBoundary><PersonalState /></AuthBoundary>);
  expect(await screen.findByRole('button', { name: 'Personal 0' })).toBeTruthy();
  expect(mocks.tokenProvider).toBeUndefined();
});

test('signing out hides personal content before sign-out completes', async () => {
  mocks.auth.signOut.mockImplementation(() => new Promise<void>(() => {}));
  render(<AuthBoundary><div>Personal secret</div><HostedAuthControls /></AuthBoundary>);
  expect(screen.getByText('Personal secret')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
  expect(screen.queryByText('Personal secret')).toBeNull();
});
