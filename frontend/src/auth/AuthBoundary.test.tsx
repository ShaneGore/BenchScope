import { useState, type ReactNode } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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

afterEach(() => vi.unstubAllEnvs());

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
