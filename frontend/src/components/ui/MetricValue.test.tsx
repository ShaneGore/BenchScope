import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { MetricValue } from "./MetricValue";

test("renders unavailable for missing metric", () => {
  render(<MetricValue label="TTFT" value={null} available={false} />);
  expect(screen.getByText("Unavailable")).toBeTruthy();
});

test("renders value when available", () => {
  render(<MetricValue label="TTFT" value={123} available={true} unit="ms" />);
  expect(screen.getByText("123")).toBeTruthy();
});