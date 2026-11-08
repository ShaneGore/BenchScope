import { act, render, screen } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import { DemoLoading } from './State';

test('announces demo loading immediately and a cold start after five seconds', () => {
  vi.useFakeTimers();
  try {
    const view = render(<DemoLoading />);
    expect(screen.getByRole('status').textContent).toMatch(/loading demo/i);
    act(() => vi.advanceTimersByTime(4999));
    expect(screen.queryByText(/cold start/i)).toBeNull();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.getByRole('status').textContent).toMatch(/cold start/i);
    view.unmount();
  } finally {
    vi.useRealTimers();
  }
});

test('personal loading is identified correctly and still announces cold starts', () => {
  vi.useFakeTimers();
  try {
    const view = render(<DemoLoading personal />);
    expect(screen.getByRole('status').textContent).toMatch(/loading your data/i);
    expect(screen.getByRole('status').textContent).not.toMatch(/demo/i);
    act(() => vi.advanceTimersByTime(5000));
    expect(screen.getByRole('status').textContent).toMatch(/cold start/i);
    view.unmount();
  } finally {
    vi.useRealTimers();
  }
});
