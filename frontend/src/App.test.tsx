import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import App from "./App";

test("renders the application", () => {
  const { container } = render(<App />);
  expect(container).toBeTruthy();
});

test("demo route uses synthetic data without personal API requests", async () => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  window.location.hash = "/demo";

  try {
    render(<App />);
    expect(await screen.findByText("Recent activity")).toBeTruthy();
    expect(fetcher).not.toHaveBeenCalled();
  } finally {
    window.location.hash = "";
    vi.unstubAllGlobals();
  }
});
