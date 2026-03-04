import fs from "fs/promises";
import path from "path";

import type { OpsLogEvent } from "@/lib/ops/types";

export type ParsedLogs = {
  events: OpsLogEvent[];
  parseErrors: number;
};

export type LogFilter = {
  level?: string;
  component?: string;
  operation?: string;
  query?: string;
  limit?: number;
};

const DEFAULT_MAX_LINES = 10000;

function normalize(value: string | undefined): string {
  return (value ?? "").trim().toLowerCase();
}

function resolveLogPath(): string {
  return path.join(process.cwd(), "..", "logs", "app.log");
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function parseLogLine(line: string): OpsLogEvent | null {
  try {
    const raw = JSON.parse(line) as unknown;
    if (!isObject(raw)) return null;
    return raw as OpsLogEvent;
  } catch {
    return null;
  }
}

function eventTs(event: OpsLogEvent): number {
  if (!event.ts) return 0;
  const direct = Date.parse(event.ts);
  if (Number.isFinite(direct)) return direct;

  // Python logging default format: "YYYY-MM-DD HH:MM:SS,mmm"
  const normalized = event.ts.replace(",", ".").replace(" ", "T");
  const fallback = Date.parse(normalized);
  return Number.isFinite(fallback) ? fallback : 0;
}

export async function readLogEvents(maxLines = DEFAULT_MAX_LINES): Promise<ParsedLogs> {
  const logPath = resolveLogPath();
  let content = "";
  try {
    content = await fs.readFile(logPath, "utf-8");
  } catch (error) {
    const missing =
      error instanceof Error &&
      "code" in error &&
      (error as NodeJS.ErrnoException).code === "ENOENT";
    if (missing) return { events: [], parseErrors: 0 };
    throw error;
  }

  const lines = content
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const tail = lines.slice(-Math.max(1, maxLines));
  const events: OpsLogEvent[] = [];
  let parseErrors = 0;

  for (const line of tail) {
    const parsed = parseLogLine(line);
    if (parsed) {
      events.push(parsed);
    } else {
      parseErrors += 1;
    }
  }

  events.sort((a, b) => eventTs(b) - eventTs(a));
  return { events, parseErrors };
}

export function filterLogEvents(events: OpsLogEvent[], filter: LogFilter): OpsLogEvent[] {
  const level = normalize(filter.level);
  const component = normalize(filter.component);
  const operation = normalize(filter.operation);
  const query = normalize(filter.query);
  const limit = Math.max(1, Math.min(500, filter.limit ?? 100));

  return events
    .filter((event) => (level ? normalize(event.level) === level : true))
    .filter((event) => (component ? normalize(event.component).includes(component) : true))
    .filter((event) => (operation ? normalize(event.operation).includes(operation) : true))
    .filter((event) => {
      if (!query) return true;
      return normalize(JSON.stringify(event)).includes(query);
    })
    .slice(0, limit);
}
