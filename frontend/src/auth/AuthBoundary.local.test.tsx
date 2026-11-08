import { render, screen } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import type { ReactNode } from 'react';

const { clerkProvider } = vi.hoisted(() => ({ clerkProvider: vi.fn() }));
vi.mock('@clerk/react', () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => {
    clerkProvider();
    return children;
  },
  useAuth: vi.fn(),
}));
vi.mock('@/lib/mode', () => ({ APP_MODE: 'local' }));

import { AuthBoundary } from './AuthBoundary';

test('local mode bypasses Clerk even when it is not configured', () => {
  render(<AuthBoundary><div>Local application</div></AuthBoundary>);
  expect(screen.getByText('Local application')).toBeTruthy();
  expect(screen.queryByRole('status')).toBeNull();
  expect(clerkProvider).not.toHaveBeenCalled();
});
