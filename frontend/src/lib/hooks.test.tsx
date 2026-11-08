import { act, renderHook, waitFor } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import { useAsync } from './hooks';

test('ignores superseded and unmounted requests', async () => {
  const resolves: Array<(value: string) => void> = [];
  const fetcher = vi.fn(() => new Promise<string>((resolve) => resolves.push(resolve)));
  const { result, rerender, unmount } = renderHook(({ id }) => useAsync(fetcher, [id]), { initialProps: { id: 1 } });
  rerender({ id: 2 });
  await act(async () => { resolves[0]('stale'); });
  expect(result.current.loading).toBe(true);
  await act(async () => { resolves[1]('current'); });
  expect(result.current.data).toBe('current');
  act(() => result.current.refetch());
  unmount();
  await act(async () => { resolves[2]('late'); });
});

test.each([undefined, null, false, 0, ''])('normalizes rejection %s and allows retry', async (reason) => {
  const fetcher = vi.fn().mockRejectedValueOnce(reason).mockResolvedValueOnce('recovered');
  const { result } = renderHook(() => useAsync(fetcher));
  await waitFor(() => expect(result.current.error).toEqual({ status: 0, detail: 'Request failed. Please retry.' }));
  act(() => result.current.refetch());
  await waitFor(() => expect(result.current.data).toBe('recovered'));
});

test('ignores a late rejection after a newer request succeeds', async () => {
  let rejectOld!: (reason: unknown) => void;
  const fetcher = vi.fn()
    .mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectOld = reject; }))
    .mockResolvedValueOnce('current');
  const { result } = renderHook(() => useAsync(fetcher));
  act(() => result.current.refetch());
  await waitFor(() => expect(result.current.data).toBe('current'));
  await act(async () => rejectOld(undefined));
  expect(result.current.error).toBeNull();
  expect(result.current.data).toBe('current');
});
