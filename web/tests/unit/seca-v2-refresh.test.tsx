import React from "react";
import { render } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { NewsmapExperimentalLivePage } from "@/components/dashboard/newsmap-experimental-live-page";

const mocks = vi.hoisted(() => ({ refresh: vi.fn(), data: { dashboard: { newsmap: { name: "Main" } }, lastLoadedAt: null as string | null } }));
const router = { refresh: mocks.refresh };
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@/lib/dashboard-client", () => ({ useDashboardData: () => mocks.data }));
vi.mock("@/components/newsmap/treemap-experimental-client", () => ({ TreemapExperimentalClient: () => <div>Tree</div> }));

beforeEach(() => { mocks.refresh.mockReset(); mocks.data.lastLoadedAt = null; });

it("refreshes the native V2 report when the existing dashboard poll completes", () => {
  const result = { mode: "v2" as const, batch: 2, day: "2026-10-28", retainedSourceCount: 0, tree: { name: "V2" }, decisions: [] };
  const view = render(<NewsmapExperimentalLivePage timelineResult={result} />);
  expect(mocks.refresh).not.toHaveBeenCalled();
  mocks.data.lastLoadedAt = "2026-10-28T12:00:00Z";
  view.rerender(<NewsmapExperimentalLivePage timelineResult={result} />);
  expect(mocks.refresh).toHaveBeenCalledTimes(1);
  view.rerender(<NewsmapExperimentalLivePage timelineResult={result} />);
  expect(mocks.refresh).toHaveBeenCalledTimes(1);
  mocks.data.lastLoadedAt = "2026-10-28T12:01:00Z";
  view.rerender(<NewsmapExperimentalLivePage timelineResult={result} />);
  expect(mocks.refresh).toHaveBeenCalledTimes(2);
});

it("leaves legacy fallback refresh behavior unchanged", () => {
  mocks.data.lastLoadedAt = "2026-10-28T12:00:00Z";
  render(<NewsmapExperimentalLivePage timelineResult={{ mode: "fallback", reason: "missing" }} />);
  expect(mocks.refresh).not.toHaveBeenCalled();
});
