import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { BenchmarkRun } from "@/types";
import type { BenchmarkService } from "@/services/benchmark-service";
import { getBenchmarkService } from "@/services/benchmark-service";
import { resetStore } from "@/mock/store";
import { BenchmarkPage } from "./BenchmarkPage";
import { RunDetailPage } from "./RunDetailPage";

vi.mock("@/services/benchmark-service", () => ({
  getBenchmarkService: vi.fn(),
}));

afterEach(() => {
  vi.restoreAllMocks();
  window.location.hash = "";
});

test("local launch stays mock-backed without a run-cancel action", async () => {
  const store = resetStore("local");
  const sourceRun = (await store.listRuns({})).items[0];
  const activeRun: BenchmarkRun = {
    ...sourceRun,
    id: "r_active_test",
    status: "running",
    ended_at: null,
  };
  const start = vi
    .spyOn(store, "startBenchmark")
    .mockResolvedValue(activeRun);
  vi.spyOn(store, "getRun").mockResolvedValue(activeRun);

  render(<BenchmarkPage />);
  fireEvent.change(await screen.findByRole("combobox", { name: /profile/i }), {
    target: { value: "p_demo1" },
  });
  fireEvent.click(await screen.findByRole("button", { name: "Start benchmark" }));

  await waitFor(() => expect(start).toHaveBeenCalledOnce());
  expect(await screen.findByText("Active run")).toBeTruthy();
  expect(screen.queryByRole("button", { name: /^cancel$/i })).toBeNull();
});

test("failed run detail keeps mock retry and exposes no cancellation action", async () => {
  const mockStore = resetStore("local");
  const sourceRun = (await mockStore.listRuns({})).items[0];
  const failedRun: BenchmarkRun = {
    ...sourceRun,
    id: "r_failed_test",
    status: "failed",
    error_category: "adapter_error",
  };
  const retryRun: BenchmarkRun = {
    ...failedRun,
    id: "r_retry_test",
    status: "running",
  };
  const service = {
    getRun: vi.fn().mockResolvedValue(failedRun),
  } as unknown as BenchmarkService;
  vi.mocked(getBenchmarkService).mockReturnValue(service);
  const retry = vi.spyOn(mockStore, "retryRun").mockResolvedValue(retryRun);

  render(<RunDetailPage id={failedRun.id} />);

  const retryButton = await screen.findByRole("button", { name: "Retry run" });
  expect(screen.queryByRole("button", { name: /cancel run/i })).toBeNull();
  fireEvent.click(retryButton);
  await waitFor(() => expect(retry).toHaveBeenCalledWith(failedRun.id));
});
