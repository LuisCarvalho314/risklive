import type { RefObject } from "react";
import { useEffect, useRef, useState } from "react";

import { TreemapNode } from "@/lib/dashboard";
import { TreemapTuning } from "@/lib/treemap/config";
import { LayoutMap, useLayoutMap } from "@/lib/treemap/layout";

type TreemapCanvasProps = {
  width: number;
  height: number;
  root: TreemapNode;
  tuning: TreemapTuning;
  containerRef: RefObject<HTMLDivElement>;
  setFocusId: (id: string) => void;
  setTooltip: (value: { x: number; y: number; node: TreemapNode } | null) => void;
};

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function parseColor(input: string): { r: number; g: number; b: number } | null {
  const hexMatch = input.trim().match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hexMatch) {
    const hex = hexMatch[1].toLowerCase();
    const full = hex.length === 3 ? hex.split("").map((c) => c + c).join("") : hex;
    const num = parseInt(full, 16);
    return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
  }

  const rgbMatch = input.trim().match(/^rgba?\(([^)]+)\)$/i);
  if (rgbMatch) {
    const parts = rgbMatch[1].split(",").map((part) => part.trim());
    if (parts.length >= 3) {
      const r = Number(parts[0]);
      const g = Number(parts[1]);
      const b = Number(parts[2]);
      if ([r, g, b].every((val) => Number.isFinite(val))) {
        return { r, g, b };
      }
    }
  }

  return null;
}

function relativeLuminance({ r, g, b }: { r: number; g: number; b: number }): number {
  const toLinear = (value: number) => {
    const v = value / 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  };
  const R = toLinear(r);
  const G = toLinear(g);
  const B = toLinear(b);
  return 0.2126 * R + 0.7152 * G + 0.0722 * B;
}

function contrastRatio(l1: number, l2: number): number {
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

function getReadableTextColor(fill: string): string {
  const parsed = parseColor(fill);
  if (!parsed) return "#f8fafc";
  const lum = relativeLuminance(parsed);
  const whiteLum = 1;
  const blackLum = 0;
  const contrastWhite = contrastRatio(lum, whiteLum);
  const contrastBlack = contrastRatio(lum, blackLum);
  return contrastWhite >= contrastBlack ? "#f8fafc" : "#0b0b0b";
}

function getContrastTextColor(fill: string, preferred: string | null, minContrast: number): string {
  const fillParsed = parseColor(fill);
  if (!fillParsed) return preferred || "#f8fafc";

  if (preferred) {
    const prefParsed = parseColor(preferred);
    if (prefParsed) {
      const ratio = contrastRatio(relativeLuminance(fillParsed), relativeLuminance(prefParsed));
      if (ratio >= minContrast) return preferred;
    }
  }

  return getReadableTextColor(fill);
}


function estimateFontSizeToFitSingleLine(
  params: {
  text: string;
  rectWidth: number;
  rectHeight: number;
  paddingX?: number;
  paddingY?: number;
  minFontSize?: number;
  maxFontSize?: number;
  },
  tuning: TreemapTuning
): number {
  const {
    text,
    rectWidth,
    rectHeight,
    paddingX = 8,
    paddingY = 6,
    minFontSize = 8,
    maxFontSize = 28,
  } = params;

  const safeWidth = Math.max(0, rectWidth - paddingX * 2);
  const safeHeight = Math.max(0, rectHeight - paddingY * 2);

  if (!text || safeWidth <= 2 || safeHeight <= 2) return minFontSize;

  const byWidth = safeWidth / (Math.max(1, text.length) * tuning.avgGlyphWidthFactor);
  const byHeight = safeHeight * tuning.textHeightFactor;

  const raw = Math.min(byWidth, byHeight);
  return clamp(Math.floor(raw), minFontSize, maxFontSize);
}

function wrapTextLines(
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

function renderNodes(params: {
  layout: LayoutMap;
  visibility: Map<string, number>;
  tuning: TreemapTuning;
  containerRef: RefObject<HTMLDivElement>;
  setFocusId: (id: string) => void;
  setTooltip: (value: { x: number; y: number; node: TreemapNode } | null) => void;
}) {
  const { layout, visibility, tuning, containerRef, setFocusId, setTooltip } = params;

  const orderedNodes = [...layout.nodes].sort((a, b) => a.depth - b.depth);

  return orderedNodes.map((node) => {
    if (node.depth === 0) return null;

    const data = node.data;
    const isLeaf = !Array.isArray(data.children) || data.children.length === 0;
    const isCategory = node.depth === 1;
    const isTopic = node.depth === 2;
    const x = node.x0;
    const y = node.y0;
    const w = Math.max(0, node.x1 - node.x0);
    const h = Math.max(0, node.y1 - node.y0);
    const area = w * h;
    const isSkinny = w < tuning.minTileWidth || h < tuning.minTileHeight;
    if (tuning.hideSkinnyTiles && isSkinny) return null;

    const baseOpacity = clamp((area - tuning.minArea) / tuning.opacityFadeRange, 0, 1);
    const rectOpacity = clamp(baseOpacity, tuning.minRectOpacity, 1);
    const interactive =
      rectOpacity > tuning.interactiveMinOpacity &&
      w > tuning.interactiveMinWidth &&
      h > tuning.interactiveMinHeight;

    const showLabel = isCategory
      ? area > tuning.categoryLabelArea
      : isLeaf
      ? area > tuning.leafLabelArea
      : area > tuning.labelArea;

    const fill = data.itemStyle?.color ?? tuning.baseFillColor;
    const labelFill = getContrastTextColor(
      fill,
      tuning.labelColor === "auto" ? null : tuning.labelColor,
      7
    );
    const rectAlpha = isCategory
      ? tuning.categoryRectOpacity
      : isTopic
      ? tuning.topicRectOpacity
      : rectOpacity;
    const vis = visibility.get(node.id) ?? 1;
    const interactiveNow = interactive && vis > tuning.interactiveMinOpacity;

    const label = data.name || "";
    const fontSize = isLeaf
      ? estimateFontSizeToFitSingleLine(
          {
            text: label,
            rectWidth: w,
            rectHeight: h,
            paddingX: tuning.leafTextPaddingX,
            paddingY: tuning.leafTextPaddingY,
            minFontSize: tuning.leafFontMin,
            maxFontSize: tuning.leafFontMax,
          },
          tuning
        )
      : clamp(
          Math.floor(
            Math.min(w, h) * (isCategory ? tuning.groupFontScaleCategory : tuning.groupFontScaleTopic)
          ),
          tuning.groupFontMin,
          tuning.groupFontMax
        );

    const title = isCategory ? label.toUpperCase() : label;
    const lineHeight = fontSize * tuning.lineHeight;
    const padding = isLeaf ? tuning.labelPaddingLeaf : tuning.labelPaddingGroup;
    const rawLines = Math.max(1, Math.floor((h - padding * 2) / lineHeight));
    const maxLines = isLeaf
      ? Math.min(tuning.maxLeafLines, rawLines)
      : Math.min(tuning.maxGroupLines, rawLines);
    const availableWidth = w - padding * 2;
    const forceSingleLine = isCategory || isTopic;
    const leafWidth = availableWidth * clamp(tuning.leafTruncationFactor, tuning.leafTruncationMinFactor, 1);
    const lines = isLeaf
      ? tuning.truncateLeafLabels
        ? [truncateToWidth(title, leafWidth, fontSize, tuning)]
        : wrapTextLines(title, availableWidth, fontSize, maxLines, tuning)
      : forceSingleLine
      ? [truncateToWidth(title, availableWidth, fontSize, tuning)]
      : wrapTextLines(title, availableWidth, fontSize, maxLines, tuning);
    const labelX = x + padding;
    const labelY = y + padding;

    return (
      <g
        key={node.id}
        onClick={() => {
          if (!data.id) return;
          if (!isLeaf) {
            setFocusId(data.id);
            return;
          }
          const meta = (data.meta ?? {}) as NonNullable<TreemapNode["meta"]>;
          if (meta.url) window.open(meta.url, "_blank", "noreferrer");
        }}
        onMouseMove={(event) => {
          const bounds = containerRef.current?.getBoundingClientRect();
          if (!bounds) return;
          setTooltip({
            x: event.clientX - bounds.left,
            y: event.clientY - bounds.top,
            node: data,
          });
        }}
        onMouseLeave={() => setTooltip(null)}
        style={{
          cursor: !isLeaf || (isLeaf && data.meta?.url) ? "pointer" : "default",
          pointerEvents: interactiveNow ? "auto" : "none",
        }}
      >
        <defs>
          <clipPath id={`${node.id}-clip`}>
            <rect x={x} y={y} width={w} height={h} rx={tuning.tileRadius} ry={tuning.tileRadius} />
          </clipPath>
        </defs>
        <rect
          x={x}
          y={y}
          width={w}
          height={h}
          rx={tuning.tileRadius}
          ry={tuning.tileRadius}
          fill={fill}
          opacity={rectAlpha * vis}
          stroke={tuning.rectStrokeColor}
        />
        {showLabel && vis > 0.2 ? (
          <text
            x={labelX}
            y={labelY}
            fill={labelFill}
            fontSize={fontSize}
            dominantBaseline="hanging"
            clipPath={`url(#${node.id}-clip)`}
            style={{
              textTransform: isCategory ? "uppercase" : undefined,
              letterSpacing: isCategory ? tuning.labelLetterSpacing : undefined,
            }}
          >
            {lines.map((line, index) => (
              <tspan key={`${node.id}-line-${index}`} x={labelX} dy={index === 0 ? 0 : lineHeight}>
                {line}
              </tspan>
            ))}
          </text>
        ) : null}
      </g>
    );
  });
}

function useMorphLayout(target: LayoutMap | null, durationMs: number) {
  const [state, setState] = useState<{ layout: LayoutMap; visibility: Map<string, number> } | null>(null);
  const prevRef = useRef<LayoutMap | null>(null);

  useEffect(() => {
    if (!target) return;
    if (!prevRef.current) {
      prevRef.current = target;
      setState({ layout: target, visibility: new Map(target.nodes.map((n) => [n.id, 1])) });
      return;
    }
    const from = prevRef.current;
    const start = performance.now();
    let raf = 0;

    const tick = (now: number) => {
      const t = clamp((now - start) / durationMs, 0, 1);
      const eased = t * t * (3 - 2 * t);

      const byId = new Map<string, any>();
      const nodes: any[] = [];
      const visibility = new Map<string, number>();

      const allIds = new Set<string>();
      for (const n of from.nodes) allIds.add(n.id);
      for (const n of target.nodes) allIds.add(n.id);

      const fromById = from.byId;
      const toById = target.byId;

      const resolveTargetRect = (id: string) => {
        const targetNode = toById.get(id);
        if (targetNode) return targetNode;
        const fromNode = fromById.get(id);
        const parentId = fromNode?.parentId;
        const parent = parentId ? toById.get(parentId) || fromById.get(parentId) : undefined;
        const siblingHint = parentId
          ? target.nodes.find((n) => n.parentId === parentId) || from.nodes.find((n) => n.parentId === parentId)
          : undefined;
        if (parent) {
          const toward = siblingHint ?? parent;
          const edgeX = (fromNode?.x0 ?? parent.x0) < toward.x0 ? parent.x0 : parent.x1;
          const edgeY = (fromNode?.y0 ?? parent.y0) < toward.y0 ? parent.y0 : parent.y1;
          return {
            ...fromNode,
            x0: edgeX,
            y0: edgeY,
            x1: edgeX,
            y1: edgeY,
          };
        }
        return fromNode;
      };

      const resolveFromRect = (id: string) => {
        const fromNode = fromById.get(id);
        if (fromNode) return fromNode;
        const toNode = toById.get(id);
        const parentId = toNode?.parentId;
        const parent = parentId ? fromById.get(parentId) || toById.get(parentId) : undefined;
        const siblingHint = parentId
          ? from.nodes.find((n: LayoutMap["nodes"][number]) => n.parentId === parentId) ||
            target.nodes.find((n: LayoutMap["nodes"][number]) => n.parentId === parentId)
          : undefined;
        if (parent) {
          const toward = siblingHint ?? parent;
          const edgeX = (toNode?.x0 ?? parent.x0) < toward.x0 ? parent.x0 : parent.x1;
          const edgeY = (toNode?.y0 ?? parent.y0) < toward.y0 ? parent.y0 : parent.y1;
          return {
            ...toNode,
            x0: edgeX,
            y0: edgeY,
            x1: edgeX,
            y1: edgeY,
          };
        }
        return toNode;
      };

      for (const id of allIds) {
        const a = resolveFromRect(id);
        const b = resolveTargetRect(id);
        if (!a || !b) continue;
        const node = {
          ...b,
          x0: a.x0 + (b.x0 - a.x0) * eased,
          y0: a.y0 + (b.y0 - a.y0) * eased,
          x1: a.x1 + (b.x1 - a.x1) * eased,
          y1: a.y1 + (b.y1 - a.y1) * eased,
        };
        nodes.push(node);
        byId.set(id, node);

        const inFrom = fromById.has(id);
        const inTo = toById.has(id);
        if (inFrom && inTo) visibility.set(id, 1);
        else if (inTo) visibility.set(id, eased);
        else visibility.set(id, 1 - eased);
      }

      setState({ layout: { byId, nodes }, visibility });

      if (t < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        prevRef.current = target;
        setState({ layout: target, visibility: new Map(target.nodes.map((n) => [n.id, 1])) });
      }
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, durationMs]);

  return state;
}

export function TreemapCanvas({
  width,
  height,
  root,
  tuning,
  containerRef,
  setFocusId,
  setTooltip,
}: TreemapCanvasProps) {
  const targetLayout = useLayoutMap(root, width, height, tuning);
  const animated = useMorphLayout(targetLayout, tuning.animationDurationMs);

  if (!animated) return null;

  return (
    <svg width={width} height={height} role="img" aria-label="Newsmap">
      {renderNodes({
        layout: animated.layout,
        visibility: animated.visibility,
        tuning,
        containerRef,
        setFocusId,
        setTooltip,
      })}
    </svg>
  );
}
function truncateToWidth(text: string, width: number, fontSize: number, tuning: TreemapTuning): string {
  if (!text) return "";
  if (width <= 0 || fontSize <= 0) return "";
  const avgGlyphWidth = fontSize * tuning.wrapGlyphWidthFactor;
  const maxChars = Math.max(1, Math.floor(width / avgGlyphWidth));
  if (text.length <= maxChars) return text;
  if (maxChars <= 1) return "…";
  return `${text.slice(0, Math.max(0, maxChars - 1))}…`;
}
