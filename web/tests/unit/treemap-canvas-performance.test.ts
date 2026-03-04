import { describe, expect, it } from "vitest";

import { resolveAnimationDuration } from "@/lib/treemap/perf";

describe("resolveAnimationDuration", () => {
  it("keeps base duration for smaller trees", () => {
    expect(resolveAnimationDuration(800, 100)).toBe(800);
    expect(resolveAnimationDuration(800, 400)).toBe(800);
  });

  it("reduces duration for medium trees", () => {
    expect(resolveAnimationDuration(800, 401)).toBe(496);
    expect(resolveAnimationDuration(800, 900)).toBe(496);
  });

  it("reduces further for very large trees", () => {
    expect(resolveAnimationDuration(800, 901)).toBe(320);
    expect(resolveAnimationDuration(1000, 1200)).toBe(400);
  });
});
