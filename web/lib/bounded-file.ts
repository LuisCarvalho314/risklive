import fs from "fs/promises";

export type FileReadBudget = { remainingBytes: number };

// Limits apply before decoding/parsing, including when a writer grows the file
// after stat. Read-only access; no changes to pipeline artifacts.
export async function readBoundedText(
  filePath: string,
  maxBytes: number,
  budget: FileReadBudget
): Promise<string> {
  const handle = await fs.open(filePath, "r");
  try {
    const limit = Math.min(maxBytes, budget.remainingBytes);
    const stat = await handle.stat();
    if (stat.size > limit) {
      throw new Error(`Experimental newsmap input exceeds safe size limit: ${filePath}`);
    }
    const chunks: Buffer[] = [];
    let total = 0;
    while (true) {
      const chunk = Buffer.alloc(Math.min(64 * 1024, limit - total + 1));
      const { bytesRead } = await handle.read(chunk, 0, chunk.length, null);
      if (!bytesRead) break;
      total += bytesRead;
      if (total > limit) {
        throw new Error(`Experimental newsmap input exceeds safe size limit: ${filePath}`);
      }
      chunks.push(chunk.subarray(0, bytesRead));
    }
    budget.remainingBytes -= total;
    return Buffer.concat(chunks, total).toString("utf8");
  } finally {
    await handle.close();
  }
}
