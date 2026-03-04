import fs from "fs/promises";
import path from "path";

import type { OpsCostRun, OpsCosts } from "@/lib/ops/types";

const DAY_MS = 24 * 60 * 60 * 1000;
const WEEK_MS = 7 * DAY_MS;
const MONTH_MS = 30 * DAY_MS;
const BUCKET_HOURS = 6;
const MAX_BUCKETS = 10;

type CostRow = {
  key: string;
  ts: Date;
  llmUsd: number;
  hasLlmExplicitPrice: boolean;
  hasLlmDerivedPrice: boolean;
  valyuUsd: number;
  hasValyuPrice: boolean;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
};

function zeroCosts(): OpsCosts {
  return {
    llm: {
      dayUsd: 0,
      weekUsd: 0,
      monthUsd: 0,
      dayTokens: 0,
      weekTokens: 0,
      monthTokens: 0,
      quality: {
        status: "unavailable",
        reason: "No LLM price rows found in active or backup datasets.",
        rowsInWindow: 0,
        rowsWithExplicitPrice: 0,
        rowsWithDerivedPrice: 0,
        rowsWithoutPrice: 0,
        evidence: ["results/data/news_data_with_llm_info.csv", "results/backup_data/news_data_with_llm_info.csv"]
      }
    },
    recentBuckets: [],
    valyu: {
      status: "unavailable",
      dayUsd: 0,
      weekUsd: 0,
      monthUsd: 0,
      reason: "No Source_Price rows found in active or backup datasets.",
      evidence: ["results/data/news_data_with_llm_info.csv", "results/backup_data/news_data_with_llm_info.csv"]
    }
  };
}

function asDate(value: string | undefined): Date | null {
  const raw = (value ?? "").trim();
  if (!raw) return null;
  const direct = new Date(raw);
  if (!Number.isNaN(direct.getTime())) return direct;
  const normalized = raw.replace(",", ".").replace(" ", "T");
  const fallback = new Date(normalized);
  if (!Number.isNaN(fallback.getTime())) return fallback;
  return null;
}

function parseNumberOrNull(value: string | undefined): number | null {
  if (value == null) return null;
  const trimmed = value.trim();
  if (!trimmed || trimmed.toLowerCase() === "none" || trimmed.toLowerCase() === "nan") return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function toNumber(value: string | undefined): number {
  return parseNumberOrNull(value) ?? 0;
}

function deriveUsdFromTokens(promptTokens: number, completionTokens: number): number {
  const inputPer1M = Number(process.env.OPENAI_PRICE_INPUT_PER_1M ?? "2.5");
  const outputPer1M = Number(process.env.OPENAI_PRICE_OUTPUT_PER_1M ?? "10");
  const inRate = Number.isFinite(inputPer1M) ? inputPer1M : 2.5;
  const outRate = Number.isFinite(outputPer1M) ? outputPer1M : 10;
  const promptCost = (Math.max(promptTokens, 0) / 1_000_000) * inRate;
  const completionCost = (Math.max(completionTokens, 0) / 1_000_000) * outRate;
  return Number((promptCost + completionCost).toFixed(8));
}

function parseCsvLine(line: string): string[] {
  const out: string[] = [];
  let cell = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === "\"") {
      const next = line[i + 1];
      if (inQuotes && next === "\"") {
        cell += "\"";
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === "," && !inQuotes) {
      out.push(cell);
      cell = "";
      continue;
    }
    cell += ch;
  }

  out.push(cell);
  return out;
}

function parseCsvRows(content: string): Record<string, string>[] {
  const lines = content
    .split(/\r?\n/)
    .filter((line) => line.trim().length > 0);
  if (lines.length < 2) return [];

  const headers = parseCsvLine(lines[0]).map((header) => header.trim());
  const rows: Record<string, string>[] = [];
  for (const line of lines.slice(1)) {
    const values = parseCsvLine(line);
    const row: Record<string, string> = {};
    for (let i = 0; i < headers.length; i += 1) {
      row[headers[i]] = values[i] ?? "";
    }
    rows.push(row);
  }
  return rows;
}

function bucketize(rows: CostRow[], now: Date): OpsCostRun[] {
  const bucketMs = BUCKET_HOURS * 60 * 60 * 1000;
  const byStart = new Map<number, OpsCostRun>();

  for (const row of rows) {
    const ageMs = now.getTime() - row.ts.getTime();
    if (ageMs < 0 || ageMs > MONTH_MS) continue;
    const startMs = Math.floor(row.ts.getTime() / bucketMs) * bucketMs;
    const endMs = startMs + bucketMs;
    const existing = byStart.get(startMs) ?? {
      bucketStartTs: new Date(startMs).toISOString(),
      bucketEndTs: new Date(endMs).toISOString(),
      llmUsd: 0,
      valyuUsd: 0,
      promptTokens: 0,
      completionTokens: 0,
      totalTokens: 0
    };
    existing.llmUsd += row.llmUsd;
    existing.valyuUsd += row.valyuUsd;
    existing.promptTokens += row.promptTokens;
    existing.completionTokens += row.completionTokens;
    existing.totalTokens += row.totalTokens;
    byStart.set(startMs, existing);
  }

  return Array.from(byStart.entries())
    .sort((a, b) => b[0] - a[0])
    .slice(0, MAX_BUCKETS)
    .map(([, value]) => value);
}

function resolveCostCsvPaths(): string[] {
  return [
    path.join(process.cwd(), "..", "results", "data", "news_data_with_llm_info.csv"),
    path.join(process.cwd(), "..", "results", "backup_data", "news_data_with_llm_info.csv")
  ];
}

export async function buildOpsCosts(now = new Date()): Promise<OpsCosts> {
  const csvPaths = resolveCostCsvPaths();
  const rawFiles = await Promise.all(
    csvPaths.map(async (csvPath) => {
      try {
        return await fs.readFile(csvPath, "utf-8");
      } catch (error) {
        const missing =
          error instanceof Error &&
          "code" in error &&
          (error as NodeJS.ErrnoException).code === "ENOENT";
        if (missing) return "";
        throw error;
      }
    })
  );

  const parsed = rawFiles.flatMap((raw) => (raw ? parseCsvRows(raw) : []));
  if (!parsed.length) return zeroCosts();

  const rowsByKey = new Map<string, CostRow>();
  for (const row of parsed) {
    const ts = asDate(row.API_Timestamp || row.Timestamp);
    if (!ts) continue;
    const promptTokens = Math.trunc(toNumber(row.PromptTokens));
    const completionTokens = Math.trunc(toNumber(row.CompletionTokens));
    const totalTokens = Math.trunc(toNumber(row.TotalTokens));
    const explicitUsd = parseNumberOrNull(row.LLM_Price);
    const explicitValyuUsd = parseNumberOrNull(row.Source_Price);
    const url = (row.URL ?? "").trim();
    const title = (row.Title ?? "").trim();
    const key = `${url}|${ts.toISOString()}|${title}`;
    const hasLlmDerivedPrice = explicitUsd === null && (promptTokens > 0 || completionTokens > 0 || totalTokens > 0);
    const llmUsd = explicitUsd ?? deriveUsdFromTokens(promptTokens, completionTokens);
    const existing = rowsByKey.get(key);
    if (existing) {
      if (!existing.hasLlmExplicitPrice && explicitUsd !== null) {
        existing.hasLlmExplicitPrice = true;
        existing.hasLlmDerivedPrice = false;
      } else if (!existing.hasLlmExplicitPrice && hasLlmDerivedPrice) {
        existing.hasLlmDerivedPrice = true;
      }
      if (!existing.hasValyuPrice && explicitValyuUsd !== null) {
        existing.valyuUsd = explicitValyuUsd;
        existing.hasValyuPrice = true;
      }
      continue;
    }
    rowsByKey.set(key, {
      key,
      ts,
      llmUsd,
      hasLlmExplicitPrice: explicitUsd !== null,
      hasLlmDerivedPrice,
      valyuUsd: explicitValyuUsd ?? 0,
      hasValyuPrice: explicitValyuUsd !== null,
      promptTokens,
      completionTokens,
      totalTokens
    });
  }
  const rows = Array.from(rowsByKey.values());

  let dayUsd = 0;
  let weekUsd = 0;
  let monthUsd = 0;
  let valyuDayUsd = 0;
  let valyuWeekUsd = 0;
  let valyuMonthUsd = 0;
  let dayTokens = 0;
  let weekTokens = 0;
  let monthTokens = 0;
  let monthRows = 0;
  let monthRowsWithValyuPrice = 0;

  for (const row of rows) {
    const ageMs = now.getTime() - row.ts.getTime();
    if (ageMs < 0) continue;
    if (ageMs <= MONTH_MS) {
      monthRows += 1;
      if (row.hasValyuPrice) monthRowsWithValyuPrice += 1;
    }
    if (ageMs <= DAY_MS) {
      dayUsd += row.llmUsd;
      valyuDayUsd += row.valyuUsd;
      dayTokens += row.totalTokens;
    }
    if (ageMs <= WEEK_MS) {
      weekUsd += row.llmUsd;
      valyuWeekUsd += row.valyuUsd;
      weekTokens += row.totalTokens;
    }
    if (ageMs <= MONTH_MS) {
      monthUsd += row.llmUsd;
      valyuMonthUsd += row.valyuUsd;
      monthTokens += row.totalTokens;
    }
  }

  let monthRowsWithLlmExplicitPrice = 0;
  let monthRowsWithLlmDerivedPrice = 0;
  let monthRowsWithoutLlmPrice = 0;
  for (const row of rows) {
    const ageMs = now.getTime() - row.ts.getTime();
    if (ageMs < 0 || ageMs > MONTH_MS) continue;
    if (row.hasLlmExplicitPrice) monthRowsWithLlmExplicitPrice += 1;
    else if (row.hasLlmDerivedPrice) monthRowsWithLlmDerivedPrice += 1;
    else monthRowsWithoutLlmPrice += 1;
  }

  let llmQualityStatus: OpsCosts["llm"]["quality"]["status"] = "unavailable";
  let llmQualityReason = "No explicit LLM_Price or derivable token usage rows in the 30-day window.";
  if (monthRowsWithLlmExplicitPrice > 0 && monthRowsWithLlmDerivedPrice === 0 && monthRowsWithoutLlmPrice === 0) {
    llmQualityStatus = "available";
    llmQualityReason = "All LLM costs in the 30-day window are from explicit LLM_Price.";
  } else if (monthRowsWithLlmExplicitPrice === 0 && monthRowsWithLlmDerivedPrice > 0 && monthRowsWithoutLlmPrice === 0) {
    llmQualityStatus = "derived_only";
    llmQualityReason = "LLM costs are fully token-derived because LLM_Price is missing.";
  } else if (monthRowsWithLlmExplicitPrice > 0 || monthRowsWithLlmDerivedPrice > 0) {
    llmQualityStatus = "partial";
    llmQualityReason = "LLM costs include a mix of explicit prices, derived prices, or missing rows.";
  }

  let valyuStatus: OpsCosts["valyu"]["status"] = "unavailable";
  let valyuReason = "No Source_Price rows found in active or backup datasets.";
  if (monthRowsWithValyuPrice > 0 && monthRowsWithValyuPrice < monthRows) {
    valyuStatus = "partial";
    valyuReason = "Source_Price is present for some rows and missing for others in the 30-day window.";
  } else if (monthRowsWithValyuPrice > 0) {
    valyuStatus = "available";
    valyuReason = "Source_Price is present for rows in the 30-day window.";
  }

  // Structured signal for observability; consumed by ops logs table.
  console.info(
    JSON.stringify({
      event: "ops_cost_quality",
      component: "web.ops.cost_aggregator",
      metric: "llm",
      llm_status: llmQualityStatus,
      rows_in_window: monthRows,
      rows_with_explicit_price: monthRowsWithLlmExplicitPrice,
      rows_with_derived_price: monthRowsWithLlmDerivedPrice,
      rows_without_price: monthRowsWithoutLlmPrice,
      source_files: [
        "results/data/news_data_with_llm_info.csv",
        "results/backup_data/news_data_with_llm_info.csv"
      ]
    })
  );

  return {
    llm: {
      dayUsd,
      weekUsd,
      monthUsd,
      dayTokens,
      weekTokens,
      monthTokens,
      quality: {
        status: llmQualityStatus,
        reason: llmQualityReason,
        rowsInWindow: monthRows,
        rowsWithExplicitPrice: monthRowsWithLlmExplicitPrice,
        rowsWithDerivedPrice: monthRowsWithLlmDerivedPrice,
        rowsWithoutPrice: monthRowsWithoutLlmPrice,
        evidence: ["results/data/news_data_with_llm_info.csv", "results/backup_data/news_data_with_llm_info.csv"]
      }
    },
    recentBuckets: bucketize(rows, now),
    valyu: {
      status: valyuStatus,
      dayUsd: valyuDayUsd,
      weekUsd: valyuWeekUsd,
      monthUsd: valyuMonthUsd,
      reason: valyuReason,
      evidence: [
        "results/data/news_data_with_llm_info.csv",
        "results/backup_data/news_data_with_llm_info.csv",
        `rows_with_price:${monthRowsWithValyuPrice}`,
        `rows_in_window:${monthRows}`
      ]
    }
  };
}
