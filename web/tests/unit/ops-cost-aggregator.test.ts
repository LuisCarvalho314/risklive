import { beforeEach, describe, expect, it, vi } from "vitest";

import { buildOpsCosts } from "@/lib/ops/cost-aggregator";

vi.mock("fs/promises", () => ({
  readFile: vi.fn(),
  default: {
    readFile: vi.fn()
  }
}));

describe("ops cost aggregator", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns zeros and valyu unavailable when csv is missing", async () => {
    const fs = await import("fs/promises");
    vi.mocked(fs.default.readFile).mockRejectedValue(Object.assign(new Error("missing"), { code: "ENOENT" }));

    const out = await buildOpsCosts(new Date("2026-02-27T12:00:00.000Z"));
    expect(out.llm.dayUsd).toBe(0);
    expect(out.recentBuckets).toEqual([]);
    expect(out.llm.quality.status).toBe("unavailable");
    expect(out.valyu.status).toBe("unavailable");
    expect(out.valyu.dayUsd).toBe(0);
  });

  it("aggregates llm and valyu cost across data+backup windows", async () => {
    const fs = await import("fs/promises");
    vi.mocked(fs.default.readFile).mockImplementation(async (p: unknown) => {
      const path = String(p);
      if (path.includes("/results/data/")) {
        return [
          "URL,API_Timestamp,LLM_Price,Source_Price,PromptTokens,CompletionTokens,TotalTokens",
          "https://a,2026-02-27T11:00:00.000Z,0.10,0.01,100,50,150",
          "https://b,2026-02-26T13:00:00.000Z,0.20,0.02,200,100,300"
        ].join("\n");
      }
      return [
        "URL,API_Timestamp,LLM_Price,Source_Price,PromptTokens,CompletionTokens,TotalTokens",
        "https://c,2026-02-20T13:00:00.000Z,0.30,0.03,300,150,450"
      ].join("\n");
    });

    const out = await buildOpsCosts(new Date("2026-02-27T12:00:00.000Z"));
    expect(out.llm.dayUsd).toBeCloseTo(0.3, 8);
    expect(out.llm.weekUsd).toBeCloseTo(0.6, 8);
    expect(out.llm.monthUsd).toBeCloseTo(0.6, 8);
    expect(out.llm.quality.status).toBe("available");
    expect(out.valyu.dayUsd).toBeCloseTo(0.03, 8);
    expect(out.valyu.weekUsd).toBeCloseTo(0.06, 8);
    expect(out.valyu.monthUsd).toBeCloseTo(0.06, 8);
    expect(out.valyu.status).toBe("available");
    expect(out.llm.dayTokens).toBe(450);
    expect(out.llm.weekTokens).toBe(900);
    expect(out.llm.monthTokens).toBe(900);
    expect(out.recentBuckets.length).toBeGreaterThan(0);
    expect(out.recentBuckets[0]?.valyuUsd).toBeGreaterThan(0);
  });

  it("derives llm cost and marks valyu partial when valyu prices are missing", async () => {
    const fs = await import("fs/promises");
    vi.mocked(fs.default.readFile).mockImplementation(async (p: unknown) => {
      const path = String(p);
      if (path.includes("/results/data/")) {
        return [
          "URL,Timestamp,LLM_Price,Source_Price,PromptTokens,CompletionTokens,TotalTokens",
          "https://a,2026-02-27T11:30:00.000Z,bad,,10,5,15",
          "https://b,2026-02-27T11:20:00.000Z,0.05,0.01,,2,7"
        ].join("\n");
      }
      return [
        "URL,Timestamp,LLM_Price,Source_Price,PromptTokens,CompletionTokens,TotalTokens",
        "https://c,bad-ts,0.90,0.50,9,9,18"
      ].join("\n");
    });

    const out = await buildOpsCosts(new Date("2026-02-27T12:00:00.000Z"));
    expect(out.llm.dayUsd).toBeCloseTo(0.050075, 8);
    expect(out.llm.dayTokens).toBe(22);
    expect(out.llm.quality.status).toBe("partial");
    expect(out.llm.quality.rowsWithDerivedPrice).toBeGreaterThan(0);
    expect(out.valyu.dayUsd).toBeCloseTo(0.01, 8);
    expect(out.valyu.status).toBe("partial");
  });
});
