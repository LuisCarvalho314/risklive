import { TreemapTuning } from "@/lib/treemap/config";

const textMeasureCache = new Map<string, number>();
const TEXT_MEASURE_CACHE_MAX = 5000;
let measureCanvas: HTMLCanvasElement | null = null;
let measureCtx: CanvasRenderingContext2D | null = null;

function getMeasureContext(): CanvasRenderingContext2D | null {
  if (measureCtx) return measureCtx;
  measureCanvas = document.createElement("canvas");
  measureCtx = measureCanvas.getContext("2d");
  return measureCtx;
}

export function measureTextWidth(text: string, fontSize: number, fontFamily?: string): number {
  if (!text || fontSize <= 0) return 0;
  const fontKey = fontFamily || "sans-serif";
  const key = `${fontSize}|${fontKey}|${text}`;
  const cached = textMeasureCache.get(key);
  if (cached !== undefined) return cached;
  const ctx = getMeasureContext();
  if (!ctx) return text.length * fontSize * 0.6;
  ctx.font = `${fontSize}px ${fontKey}`;
  const metrics = ctx.measureText(text);
  const width = metrics.width || 0;
  textMeasureCache.set(key, width);
  if (textMeasureCache.size > TEXT_MEASURE_CACHE_MAX) textMeasureCache.clear();
  return width;
}

export function wrapTextLinesMeasured(
  text: string,
  width: number,
  fontSize: number,
  maxLines: number,
  fontFamily?: string,
  breakWords = false
): string[] {
  if (!text) return [];
  if (width <= 0 || fontSize <= 0 || maxLines <= 0) return [];

  if (breakWords) {
    const normalized = text.replace(/\s+/g, " ").trim();
    if (!normalized) return [];

    const lines: string[] = [];
    let current = "";
    let index = 0;
    let consumedAll = true;

    const pushLine = (line: string) => {
      if (!line) return;
      lines.push(line);
    };

    while (index < normalized.length) {
      const ch = normalized[index];
      const next = `${current}${ch}`;
      if (measureTextWidth(next, fontSize, fontFamily) <= width || !current) {
        current = next;
        index += 1;
        continue;
      }

      let line = current.trimEnd();
      if (line && index < normalized.length && normalized[index] !== " ") {
        let hyphenated = `${line}-`;
        while (line.length > 1 && measureTextWidth(hyphenated, fontSize, fontFamily) > width) {
          line = line.slice(0, -1);
          hyphenated = `${line}-`;
        }
        line = measureTextWidth(hyphenated, fontSize, fontFamily) <= width ? hyphenated : line;
      }
      pushLine(line);
      current = "";
      while (index < normalized.length && normalized[index] === " ") index += 1;
      if (lines.length >= maxLines) {
        consumedAll = false;
        break;
      }
    }

    if (lines.length < maxLines && current) pushLine(current.trimEnd());
    if (lines.length > maxLines) lines.length = maxLines;
    if (index < normalized.length) consumedAll = false;

    if (!consumedAll) {
      const last = lines[lines.length - 1] ?? "";
      if (last.length) {
        let trimmed = last;
        while (trimmed.length > 1 && measureTextWidth(`${trimmed}…`, fontSize, fontFamily) > width) {
          trimmed = trimmed.slice(0, -1);
        }
        lines[lines.length - 1] = `${trimmed}…`;
      } else {
        lines[lines.length - 1] = "…";
      }
    }
    return lines;
  }

  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let current = "";
  let consumedAllWords = true;

  const pushLine = (line: string) => {
    if (!line) return;
    lines.push(line);
  };

  for (let index = 0; index < words.length; index += 1) {
    const word = words[index];
    const next = current ? `${current} ${word}` : word;
    if (measureTextWidth(next, fontSize, fontFamily) <= width) {
      current = next;
      continue;
    }
    pushLine(current);
    current = word;
    if (lines.length >= maxLines) {
      consumedAllWords = false;
      break;
    }
  }

  if (lines.length < maxLines && current) pushLine(current);
  if (lines.length > maxLines) lines.length = maxLines;

  if (!consumedAllWords) {
    const last = lines[lines.length - 1] ?? "";
    if (last.length) {
      let trimmed = last;
      while (trimmed.length > 1 && measureTextWidth(`${trimmed}…`, fontSize, fontFamily) > width) {
        trimmed = trimmed.slice(0, -1);
      }
      lines[lines.length - 1] = `${trimmed}…`;
    } else {
      lines[lines.length - 1] = "…";
    }
  }

  return lines;
}

export function truncateToWidthMeasured(
  text: string,
  width: number,
  fontSize: number,
  fontFamily?: string
): string {
  if (!text) return "";
  if (width <= 0 || fontSize <= 0) return "";
  if (measureTextWidth(text, fontSize, fontFamily) <= width) return text;
  let end = text.length;
  let start = 0;
  let best = "…";
  while (start <= end) {
    const mid = Math.floor((start + end) / 2);
    const candidate = text.slice(0, Math.max(0, mid - 1)) + "…";
    if (measureTextWidth(candidate, fontSize, fontFamily) <= width) {
      best = candidate;
      start = mid + 1;
    } else {
      end = mid - 1;
    }
  }
  return best;
}

export function refineFontSizeToFitSingleLineMeasured(
  text: string,
  width: number,
  fontSize: number,
  minFontSize: number,
  maxIterations = 6
): number {
  let size = fontSize;
  let iterations = 0;
  while (size > minFontSize && iterations < maxIterations) {
    if (measureTextWidth(text, size) <= width) return size;
    size -= 1;
    iterations += 1;
  }
  return size;
}

export function refineFontSizeToFitWrappedMeasured(
  text: string,
  width: number,
  height: number,
  fontSize: number,
  minFontSize: number,
  maxLines: number,
  lineHeightFactor: number,
  maxIterations = 6,
  breakWords = false
): number {
  let size = fontSize;
  let iterations = 0;
  while (size > minFontSize && iterations < maxIterations) {
    const lineHeight = size * lineHeightFactor;
    const allowedLines = Math.max(1, Math.floor(height / Math.max(1, lineHeight)));
    const effectiveMaxLines = Math.max(1, Math.min(maxLines, allowedLines));
    const lines = wrapTextLinesMeasured(text, width, size, effectiveMaxLines, undefined, breakWords);
    const fits = lines.length > 0 && lines.length <= allowedLines && !lines[lines.length - 1]?.endsWith("…");
    if (fits) return size;
    size -= 1;
    iterations += 1;
  }
  return size;
}

export function wrapTextLines(
  text: string,
  width: number,
  fontSize: number,
  maxLines: number,
  tuning: TreemapTuning
): string[] {
  if (!text) return [];
  if (width <= 0 || fontSize <= 0 || maxLines <= 0) return [];

  const avgGlyphWidth = fontSize * tuning.wrapGlyphWidthFactor;
  const maxChars = Math.max(3, Math.floor(width / avgGlyphWidth));
  if (tuning.allowMidWordWrap) {
    const normalized = text.replace(/\s+/g, " ").trim();
    if (!normalized) return [];

    const lines: string[] = [];
    let current = "";
    let index = 0;
    let consumedAll = true;

    const pushLine = (line: string) => {
      if (!line) return;
      lines.push(line);
    };

    while (index < normalized.length) {
      const ch = normalized[index];
      const next = `${current}${ch}`;
      if (next.length <= maxChars || !current) {
        current = next;
        index += 1;
        continue;
      }

      let line = current.trimEnd();
      if (line && index < normalized.length && normalized[index] !== " ") {
        line = line.length >= maxChars ? `${line.slice(0, Math.max(0, maxChars - 1))}-` : `${line}-`;
      }
      pushLine(line);
      current = "";
      while (index < normalized.length && normalized[index] === " ") index += 1;
      if (lines.length >= maxLines) {
        consumedAll = false;
        break;
      }
    }

    if (lines.length < maxLines && current) pushLine(current.trimEnd());
    if (lines.length > maxLines) lines.length = maxLines;
    if (index < normalized.length) consumedAll = false;

    if (!consumedAll) {
      const last = lines[lines.length - 1] ?? "";
      if (last.length > maxChars) {
        lines[lines.length - 1] = `${last.slice(0, Math.max(0, maxChars - 1))}…`;
      } else if (!last.endsWith("…") && last.length) {
        lines[lines.length - 1] = `${last}…`;
      }
    }

    return lines;
  }

  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let current = "";
  let consumedAllWords = true;

  const pushLine = (line: string) => {
    if (!line) return;
    lines.push(line);
  };

  for (let index = 0; index < words.length; index += 1) {
    const word = words[index];
    const next = current ? `${current} ${word}` : word;
    if (next.length <= maxChars) {
      current = next;
      continue;
    }
    pushLine(current);
    current = word;
    if (lines.length >= maxLines) {
      consumedAllWords = false;
      break;
    }
  }

  if (lines.length < maxLines && current) pushLine(current);
  if (lines.length > maxLines) lines.length = maxLines;

  if (!consumedAllWords) {
    const last = lines[lines.length - 1] ?? "";
    if (last.length > maxChars) {
      lines[lines.length - 1] = `${last.slice(0, Math.max(0, maxChars - 1))}…`;
    } else if (!last.endsWith("…") && last.length) {
      lines[lines.length - 1] = `${last}…`;
    }
  }

  return lines;
}
