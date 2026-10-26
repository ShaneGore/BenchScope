import { expect, test } from "vitest";
import { metricAvailable } from "@/lib/metrics";

test("metricAvailable treats null/undefined/NaN as unavailable", () => {
  expect(metricAvailable(null)).toBe(false);
  expect(metricAvailable(undefined)).toBe(false);
  expect(metricAvailable(Number.NaN)).toBe(false);
  expect(metricAvailable(0)).toBe(true);
});

test("metricAvailable accepts finite numbers", () => {
  expect(metricAvailable(42)).toBe(true);
});