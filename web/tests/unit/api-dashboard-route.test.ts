import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("fs/promises", () => ({
  readFile: vi.fn(),
  default: {
    readFile: vi.fn()
  }
}));

describe("api dashboard route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  it("returns dashboard json with cache headers", async () => {
    const fs = await import("fs/promises");
    vi.mocked(fs.readFile).mockResolvedValueOnce('{"ok":true}');
    vi.mocked(fs.default.readFile).mockResolvedValueOnce('{"ok":true}');

    const { GET } = await import("@/app/api/dashboard/route");
    const response = await GET();

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("application/json");
    expect(response.headers.get("cache-control")).toContain("max-age=60");
    await expect(response.text()).resolves.toBe('{"ok":true}');
  });

  it("returns 404 when file does not exist", async () => {
    const fs = await import("fs/promises");
    vi.mocked(fs.readFile).mockRejectedValueOnce(new Error("missing"));
    vi.mocked(fs.default.readFile).mockRejectedValueOnce(new Error("missing"));

    const { GET } = await import("@/app/api/dashboard/route");
    const response = await GET();

    expect(response.status).toBe(404);
    await expect(response.json()).resolves.toEqual({ error: "dashboard.json not found" });
  });
});
