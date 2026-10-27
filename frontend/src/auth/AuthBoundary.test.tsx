import type { ReactNode } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  order: [] as string[],
  auth: {
    getToken: vi.fn(async () => 'session-jwt'),
    isLoaded: true,
    isSignedIn: true,
    signOut: vi.fn(async () => {
      mocks.order.push('sign-out');
    }),
    userId: 'user-1',
  },
}));

vi.mock('@clerk/react', () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => children,
  useAuth: () => mocks.auth,
}));

vi.mock('@/mock/store', () => ({
  resetStore: () => mocks.order.push('clear-user-state'),
}));

import { HostedAuthControls } from './AuthBoundary';

beforeEach(() => {
  mocks.order.length = 0;
  mocks.auth.signOut.mockClear();
});

test('clears user-scoped state before signing out', async () => {
  render(<HostedAuthControls />);
  fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));

  await waitFor(() => expect(mocks.auth.signOut).toHaveBeenCalledOnce());
  expect(mocks.order).toEqual(['clear-user-state', 'sign-out']);
});
