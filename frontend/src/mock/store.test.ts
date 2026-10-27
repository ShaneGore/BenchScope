import { expect, test } from "vitest";
import { resetStore } from "@/mock/store";

test("mock store provides synthetic profiles and runs", async () => {
  const store = resetStore("local");
  const profiles = await store.listProfiles();
  const runs = await store.listRuns({});
  expect(profiles.length).toBeGreaterThan(0);
  expect(runs.items.length).toBeGreaterThan(0);
});

test("mock store marks missing metrics as null, not zero", async () => {
  const store = resetStore("local");
  const runs = await store.listRuns({});
  const run = runs.items.find((r) => r.status !== "completed");
  // failed/interrupted runs may have empty metrics
  if (run) {
    expect(run.status).not.toBe("completed");
  }
  const completed = runs.items.find((r) => r.status === "completed");
  expect(completed).toBeTruthy();
});

test("interim mock has no run-cancel operation or cancelled sample", async () => {
  const store = resetStore("local");
  const runs = await store.listRuns({});

  expect("cancelRun" in store).toBe(false);
  expect(runs.items.map((run) => run.status as string)).not.toContain("cancelled");
  expect(
    runs.items.map((run) => run.error_category as string | null)
  ).not.toContain("CANCELLED");
  expect(typeof store.startBenchmark).toBe("function");
  expect(typeof store.retryRun).toBe("function");
});