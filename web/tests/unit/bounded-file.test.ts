import fs from "fs/promises";
import os from "os";
import path from "path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { readBoundedText } from "@/lib/bounded-file";

const dirs: string[] = [];
afterEach(async () => {
  vi.restoreAllMocks();
  await Promise.all(dirs.splice(0).map(dir => fs.rm(dir, { recursive: true })));
});
async function fixture(content: string) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "risklive-bounded-"));
  dirs.push(dir);
  const file = path.join(dir, "input");
  await fs.writeFile(file, content);
  return file;
}

describe("bounded experimental inputs", () => {
  it("decodes UTF-8 and accounts for bytes across files", async () => {
    const file = await fixture("é");
    const budget = { remainingBytes: 3 };
    expect(await readBoundedText(file, 2, budget)).toBe("é");
    expect(budget.remainingBytes).toBe(1);
    await expect(readBoundedText(file, 2, budget)).rejects.toThrow("safe size limit");
  });

  it("rejects an oversized file before reading and closes the handle", async () => {
    const read = vi.fn();
    const close = vi.fn();
    vi.spyOn(fs, "open").mockResolvedValue({
      stat: async () => ({ size: 1024 ** 3 }), read, close,
    } as never);
    await expect(readBoundedText("large.json", 8 * 1024 ** 2, { remainingBytes: 32 * 1024 ** 2 }))
      .rejects.toThrow("safe size limit");
    expect(read).not.toHaveBeenCalled();
    expect(close).toHaveBeenCalledOnce();
  });

  it("bounds reads even if the file grows after stat", async () => {
    const close = vi.fn();
    vi.spyOn(fs, "open").mockResolvedValue({
      stat: async () => ({ size: 0 }),
      read: async (buffer: Buffer) => ({ bytesRead: buffer.length }), close,
    } as never);
    await expect(readBoundedText("growing.json", 10, { remainingBytes: 10 }))
      .rejects.toThrow("safe size limit");
    expect(close).toHaveBeenCalledOnce();
  });
});
