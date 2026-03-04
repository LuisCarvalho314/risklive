//© 2025 University of Aberdeen. All rights reserved


import { memo, type RefObject, useMemo } from "react";
import { useEffect, useRef, useState } from "react";

import { TreemapNode } from "@/lib/dashboard";
import { TreemapTuning } from "@/lib/treemap/config";
import { LayoutMap, useLayoutMap } from "@/lib/treemap/layout";
import { resolveAnimationDuration } from "@/lib/treemap/perf";
import {
  measureTextWidth,
  refineFontSizeToFitSingleLineMeasured,
  refineFontSizeToFitWrappedMeasured,
  truncateToWidthMeasured,
  wrapTextLines,
  wrapTextLinesMeasured,
} from "@/lib/treemap/text";

type TreemapCanvasProps = {
  width: number;
  height: number;
  root: TreemapNode;
  tuning: TreemapTuning;
  containerRef: RefObject<HTMLDivElement>;
  setFocusId: (id: string) => void;
  setTooltip: (
    value: { x: number; y: number; node: TreemapNode } | null,
    options?: { pinMs?: number; showSources?: boolean }
  ) => void;
  experimentalInteractions?: boolean;
};
type HoverPayload = { x: number; y: number; node: TreemapNode };
type LabelLayoutCache = Map<string, LabelLayout>;

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function hashString(input: string): string {
  let hash = 5381;
  for (let i = 0; i < input.length; i += 1) {
    hash = ((hash << 5) + hash) ^ input.charCodeAt(i);
  }
  return (hash >>> 0).toString(36);
}

function makeClipId(id: string, suffix: string): string {
  const safe = id.replace(/[^a-zA-Z0-9_-]/g, "_");
  return `${safe}-${hashString(id)}-${suffix}`;
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
  widthGlyphFactor?: number;
  heightFactor?: number;
  fontFamily?: string;
  },
  tuning: TreemapTuning
): number {
  const {
    text,
    rectWidth,
    rectHeight,
    paddingX = 16,
    paddingY = 12,
    minFontSize = 8,
    maxFontSize = 28,
    widthGlyphFactor = tuning.avgGlyphWidthFactor,
    heightFactor = tuning.textHeightFactor,
    fontFamily,
  } = params;

  const safeWidth = Math.max(0, rectWidth - paddingX);
  const safeHeight = Math.max(0, rectHeight - paddingY);

  if (!text || safeWidth <= 2 || safeHeight <= 2) return minFontSize;

  const measured = measureTextWidth(text, 1, fontFamily);
  const byWidth =
    measured > 0 ? safeWidth / measured : safeWidth / (Math.max(1, text.length) * widthGlyphFactor);
  const byHeight = safeHeight * heightFactor;

  const raw = Math.min(byWidth, byHeight);
  return clamp(Math.floor(raw), minFontSize, maxFontSize);
}

function estimateFontSizeToFitWrappedText(
  params: {
    text: string;
    rectWidth: number;
    rectHeight: number;
    paddingX?: number;
    paddingY?: number;
    minFontSize?: number;
    maxFontSize?: number;
    fontFamily?: string;
  },
  tuning: TreemapTuning
): number {
  const {
    text,
    rectWidth,
    rectHeight,
    paddingX = 16,
    paddingY = 12,
    minFontSize = 8,
    maxFontSize = 28,
    fontFamily,
  } = params;

  const safeWidth = Math.max(0, rectWidth - paddingX);
  const safeHeight = Math.max(0, rectHeight - paddingY);

  if (!text || safeWidth <= 2 || safeHeight <= 2) return minFontSize;

  let low = minFontSize;
  let high = Math.max(minFontSize, maxFontSize);
  let best = minFontSize;

  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    const lineHeight = mid * tuning.lineHeight;
    const allowedLines = Math.max(1, Math.floor(safeHeight / Math.max(1, lineHeight)));
    const lines = wrapTextLines(text, safeWidth, mid, allowedLines, tuning);
    const fits = lines.length > 0 && lines.length <= allowedLines && !lines[lines.length - 1]?.endsWith("…");
    if (fits) {
      best = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }

  return best;
}

type LabelLayout = {
  fontSize: number;
  adjustedLineHeight: number;
  lines: string[];
  labelX: number;
  labelY: number;
  showLabel: boolean;
  labelBandHeight: number;
  groupOverlapAllowance: number;
  padLeft: number;
  padRight: number;
  padTop: number;
  padBottom: number;
  availableWidth: number;
};

function getLabelBandHeight(fontSize: number, depth: number, tuning: TreemapTuning): number {
  if (!tuning.useLayoutLabelBand) return 0;
  if (depth < tuning.labelBandMinDepth || depth > tuning.labelBandMaxDepth) return 0;
  return Math.min(60, Math.max(30, Math.ceil(fontSize * 1.6)));
}

function computeLabelLayout(params: {
  label: string;
  isLeaf: boolean;
  isCategory: boolean;
  depth: number;
  x: number;
  y: number;
  w: number;
  h: number;
  tuning: TreemapTuning;
}): LabelLayout {
  const { label, isLeaf, isCategory, depth, x, y, w, h, tuning } = params;
  const minSide = Math.min(w, h);
  const padScale = clamp(minSide * 0.04, 1, 10);
  const padScaleLeafX = clamp(minSide * 0.03, 0, 8);
  const padScaleLeafY = clamp(minSide * 0.02, 0, 6);
  const radiusPad = Math.max(0, tuning.tileRadius - 1) * 0.2;

  let groupPadLeft = tuning.labelPaddingGroup + radiusPad * 0.4;
  let groupPadRight = groupPadLeft;
  let groupPadTop = groupPadLeft;
  let groupPadBottom = groupPadLeft;

  const leafPadLeft =
    tuning.labelPaddingLeaf + tuning.leafTextPaddingX + padScaleLeafX + radiusPad + tuning.leafPaddingExtra;
  const leafPadRight =
    tuning.labelPaddingLeaf + tuning.leafTextPaddingX + padScaleLeafX + radiusPad + tuning.leafPaddingExtra;
  const leafPadTop =
    tuning.labelPaddingLeaf + tuning.leafTextPaddingY + padScaleLeafY + radiusPad + tuning.leafPaddingExtra;
  const leafPadBottom =
    tuning.labelPaddingLeaf + tuning.leafTextPaddingY + padScaleLeafY + radiusPad + tuning.leafPaddingExtra;

  let fontSize = isLeaf
    ? estimateFontSizeToFitWrappedText(
        {
          text: label,
          rectWidth: w,
          rectHeight: h,
          paddingX: leafPadLeft + leafPadRight,
          paddingY: leafPadTop + leafPadBottom,
          minFontSize: tuning.leafFontMin,
          maxFontSize: tuning.leafFontMax,
        },
        tuning
      )
    : estimateFontSizeToFitSingleLine(
        {
          text: label,
          rectWidth: w,
          rectHeight: h,
          paddingX: (groupPadLeft + groupPadRight) + (padScale * 0.4),
          paddingY: (groupPadTop + groupPadBottom) + (padScale * 0.4),
          minFontSize: tuning.groupFontMin,
          maxFontSize: tuning.groupFontMax,
          widthGlyphFactor: tuning.wrapGlyphWidthFactor,
        },
        tuning
      );

  if (!isLeaf) {
    const fontPad = Math.max(2, Math.round(fontSize * 0.1));
    groupPadLeft += fontPad;
    groupPadRight += fontPad;
    groupPadTop += fontPad;
    groupPadBottom += fontPad;
  }

  const title = isCategory ? label.toUpperCase() : label;
  const lineHeight = fontSize * tuning.lineHeight;
  const padLeft = isLeaf ? leafPadLeft : groupPadLeft;
  const padRight = isLeaf ? leafPadRight : groupPadRight;
  const padTop = isLeaf ? leafPadTop : groupPadTop;
  const padBottom = isLeaf ? leafPadBottom : groupPadBottom;
  const rawLines = Math.max(1, Math.floor((h - (padTop + padBottom)) / lineHeight));
  const maxLines = isLeaf
    ? Math.min(tuning.maxLeafLines, rawLines)
    : Math.min(tuning.maxGroupLines, rawLines);
  const availableWidth = Math.max(0, w - (padLeft + padRight) - 1);
  const forceSingleLine = !isLeaf;
  const leafWidth = availableWidth * clamp(tuning.leafTruncationFactor, tuning.leafTruncationMinFactor, 1);
  const labelBandHeight = !isLeaf ? getLabelBandHeight(fontSize, depth, tuning) : 0;
  const groupOverlapAllowance = 0;
  const groupBandContentHeight = !isLeaf && labelBandHeight > 0
    ? Math.max(0, labelBandHeight - (padTop + padBottom) + groupOverlapAllowance)
    : 0;
  const groupBandMaxLines =
    !isLeaf && labelBandHeight > 0
      ? Math.max(1, Math.floor(groupBandContentHeight / Math.max(1, fontSize * tuning.lineHeight)))
      : 1;

  if (isLeaf) {
    const availableHeight = h - (padTop + padBottom);
    fontSize = refineFontSizeToFitWrappedMeasured(
      title,
      availableWidth,
      availableHeight,
      fontSize,
      tuning.leafFontMin,
      maxLines,
      tuning.lineHeight,
      6,
      tuning.allowMidWordWrap
    );
  } else {
    fontSize = refineFontSizeToFitSingleLineMeasured(title, availableWidth, fontSize, tuning.groupFontMin);
  }

  const adjustedLineHeight = fontSize * tuning.lineHeight;
  const lines = isLeaf
    ? tuning.truncateLeafLabels
      ? [truncateToWidthMeasured(title, leafWidth, fontSize)]
      : wrapTextLinesMeasured(title, availableWidth, fontSize, maxLines, undefined, tuning.allowMidWordWrap)
    : forceSingleLine
    ? groupBandMaxLines > 1
      ? wrapTextLinesMeasured(
          title,
          availableWidth,
          fontSize,
          Math.min(groupBandMaxLines, maxLines),
          undefined,
          tuning.allowMidWordWrap
        )
      : [truncateToWidthMeasured(title, availableWidth, fontSize)]
    : wrapTextLinesMeasured(title, availableWidth, fontSize, maxLines, undefined, tuning.allowMidWordWrap);
  const safeLines = lines.map((line) => truncateToWidthMeasured(line, availableWidth, fontSize));

  const showLabel =
    fontSize >= (isLeaf ? tuning.leafFontMin : tuning.groupFontMin) &&
    w > 2 &&
    h > 2 &&
    safeLines.length > 0;

  const labelX = x + padLeft;
  const labelY = !isLeaf && labelBandHeight
    ? y + Math.max(0, Math.min(padTop, labelBandHeight - Math.max(1, fontSize * tuning.lineHeight)))
    : y + padTop;

  return {
    fontSize,
    adjustedLineHeight,
    lines: safeLines,
    labelX,
    labelY,
    showLabel,
    labelBandHeight,
    groupOverlapAllowance,
    padLeft,
    padRight,
    padTop,
    padBottom,
    availableWidth,
  };
}

function quantize(value: number): number {
  return Math.round(value * 2) / 2;
}

function makeLabelCacheKey(
  node: LayoutMap["nodes"][number],
  label: string,
  tuningSignature: string
): string {
  return [
    node.id,
    label,
    quantize(node.x0),
    quantize(node.y0),
    quantize(node.x1),
    quantize(node.y1),
    tuningSignature,
  ].join("|");
}

function makeHoverKey(payload: HoverPayload): string {
  return `${payload.node.id ?? "__none__"}|${Math.round(payload.x)}|${Math.round(payload.y)}`;
}

function renderNodes(params: {
  orderedNodes: LayoutMap["nodes"];
  visibility: Map<string, number>;
  tuning: TreemapTuning;
  tuningSignature: string;
  labelLayoutCache: LabelLayoutCache;
  containerRef: RefObject<HTMLDivElement>;
  setFocusId: (id: string) => void;
  setTooltip: (
    value: { x: number; y: number; node: TreemapNode } | null,
    options?: { pinMs?: number; showSources?: boolean }
  ) => void;
  setTooltipThrottled: (value: HoverPayload | null) => void;
  experimentalInteractions: boolean;
  clickTimerRef: RefObject<number | null>;
}) {
  const {
    orderedNodes,
    visibility,
    tuning,
    tuningSignature,
    labelLayoutCache,
    containerRef,
    setFocusId,
    setTooltip,
    setTooltipThrottled,
    experimentalInteractions,
    clickTimerRef,
  } = params;

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
    const labelCacheKey = makeLabelCacheKey(node, label, tuningSignature);
    let cachedLayout = labelLayoutCache.get(labelCacheKey);
    if (!cachedLayout) {
      cachedLayout = computeLabelLayout({
        label,
        isLeaf,
        isCategory,
        depth: node.depth,
        x,
        y,
        w,
        h,
        tuning,
      });
      labelLayoutCache.set(labelCacheKey, cachedLayout);
    }

    const {
      fontSize,
      adjustedLineHeight,
      lines,
      labelX,
      labelY,
      showLabel,
      labelBandHeight,
      groupOverlapAllowance,
    } = cachedLayout;

    return (
      <g
        key={node.id}
        onClick={(event) => {
          const bounds = containerRef.current?.getBoundingClientRect();
          if (bounds) {
            setTooltip(
              {
                x: event.clientX - bounds.left,
                y: event.clientY - bounds.top,
                node: data,
              }
            );
          }
          if (experimentalInteractions && data.id && !isLeaf) {
            if (clickTimerRef.current != null) {
              window.clearTimeout(clickTimerRef.current);
            }
            clickTimerRef.current = window.setTimeout(() => {
              setFocusId(data.id ?? "root::newsmap");
              clickTimerRef.current = null;
            }, 220);
            return;
          }
          if (!experimentalInteractions && data.id && !isLeaf) {
            setFocusId(data.id);
          }
        }}
        onDoubleClick={(event) => {
          if (clickTimerRef.current != null) {
            window.clearTimeout(clickTimerRef.current);
            clickTimerRef.current = null;
          }
          if (experimentalInteractions) {
            const bounds = containerRef.current?.getBoundingClientRect();
            if (bounds) {
              setTooltip(
                {
                  x: event.clientX - bounds.left,
                  y: event.clientY - bounds.top,
                  node: data,
                },
                { pinMs: 8000, showSources: true }
              );
            }
            return;
          }
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
          setTooltipThrottled({
            x: event.clientX - bounds.left,
            y: event.clientY - bounds.top,
            node: data,
          });
        }}
        onMouseLeave={() => setTooltipThrottled(null)}
        style={{
          cursor: !isLeaf || (isLeaf && data.meta?.url) ? "pointer" : "default",
          pointerEvents: interactiveNow ? "auto" : "none",
        }}
      >
        <defs>
          <clipPath id={makeClipId(node.id, "clip")}>
            <rect x={x} y={y} width={w} height={h} rx={tuning.tileRadius} ry={tuning.tileRadius} />
          </clipPath>
          {labelBandHeight ? (
            <clipPath id={makeClipId(node.id, "label-clip")}>
              <rect
                x={x}
                y={y}
                width={w}
                height={Math.max(0, Math.min(h, labelBandHeight + groupOverlapAllowance))}
                rx={tuning.tileRadius}
                ry={tuning.tileRadius}
              />
            </clipPath>
          ) : null}
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
            clipPath={`url(#${
              labelBandHeight ? makeClipId(node.id, "label-clip") : makeClipId(node.id, "clip")
            })`}
            style={{
              textTransform: isCategory ? "uppercase" : undefined,
              letterSpacing: isCategory ? tuning.labelLetterSpacing : undefined,
            }}
          >
            {lines.map((line, index) => (
              <tspan key={`${node.id}-line-${index}`} x={labelX} dy={index === 0 ? 0 : adjustedLineHeight}>
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

      // Render a single canonical layer (target ids only) to avoid ghost overlays.
      const allIds = new Set<string>();
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
        visibility.set(id, inFrom ? 1 : eased);
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

function TreemapCanvasImpl({
  width,
  height,
  root,
  tuning,
  containerRef,
  setFocusId,
  setTooltip,
  experimentalInteractions = false,
}: TreemapCanvasProps) {
  const targetLayout = useLayoutMap(root, width, height, tuning);
  const nodeCount = targetLayout?.nodes.length ?? 0;
  const animationDurationMs = useMemo(
    () => resolveAnimationDuration(tuning.animationDurationMs, nodeCount),
    [nodeCount, tuning.animationDurationMs]
  );
  const animated = useMorphLayout(targetLayout, animationDurationMs);
  const clickTimerRef = useRef<number | null>(null);
  const hoverFrameRef = useRef<number | null>(null);
  const lastHoverKeyRef = useRef<string | null>(null);
  const pendingHoverRef = useRef<HoverPayload | null>(null);
  const labelLayoutCacheRef = useRef<LabelLayoutCache>(new Map());
  const orderedNodes = useMemo(
    () => [...(animated?.layout.nodes ?? [])].sort((a, b) => a.depth - b.depth),
    [animated?.layout.nodes]
  );
  const tuningSignature = useMemo(
    () =>
      [
        tuning.lineHeight,
        tuning.labelPaddingLeaf,
        tuning.leafTextPaddingX,
        tuning.leafTextPaddingY,
        tuning.maxLeafLines,
        tuning.maxGroupLines,
        tuning.tileRadius,
        tuning.labelColor,
        tuning.allowMidWordWrap,
        tuning.truncateLeafLabels,
        tuning.leafTruncationFactor,
      ].join("|"),
    [tuning]
  );

  const setTooltipThrottled = useMemo(
    () =>
      (value: HoverPayload | null) => {
        if (!value) {
          pendingHoverRef.current = null;
          lastHoverKeyRef.current = null;
          if (hoverFrameRef.current != null) {
            cancelAnimationFrame(hoverFrameRef.current);
            hoverFrameRef.current = null;
          }
          setTooltip(null);
          return;
        }
        const key = makeHoverKey(value);
        if (key === lastHoverKeyRef.current) return;
        pendingHoverRef.current = value;
        if (hoverFrameRef.current != null) return;
        hoverFrameRef.current = requestAnimationFrame(() => {
          hoverFrameRef.current = null;
          const next = pendingHoverRef.current;
          if (!next) return;
          const nextKey = makeHoverKey(next);
          if (nextKey === lastHoverKeyRef.current) return;
          lastHoverKeyRef.current = nextKey;
          setTooltip(next);
        });
      },
    [setTooltip]
  );

  useEffect(() => {
    return () => {
      if (clickTimerRef.current != null) {
        window.clearTimeout(clickTimerRef.current);
      }
      if (hoverFrameRef.current != null) {
        cancelAnimationFrame(hoverFrameRef.current);
      }
    };
  }, []);

  useEffect(() => {
    labelLayoutCacheRef.current.clear();
  }, [root]);

  if (!animated) return null;

  return (
    <svg
      width={width}
      height={height}
      role="img"
      aria-label="Newsmap"
      style={{ userSelect: "none", WebkitUserSelect: "none" }}
      onMouseLeave={() => setTooltipThrottled(null)}
      onMouseMove={(event) => {
        if (event.target === event.currentTarget) {
          setTooltipThrottled(null);
        }
      }}
    >
      {renderNodes({
        orderedNodes,
        visibility: animated.visibility,
        tuning,
        tuningSignature,
        labelLayoutCache: labelLayoutCacheRef.current,
        containerRef,
        setFocusId,
        setTooltip,
        setTooltipThrottled,
        experimentalInteractions,
        clickTimerRef,
      })}
    </svg>
  );
}

export const TreemapCanvas = memo(TreemapCanvasImpl);
function truncateToWidth(text: string, width: number, fontSize: number, tuning: TreemapTuning): string {
  if (!text) return "";
  if (width <= 0 || fontSize <= 0) return "";
  const avgGlyphWidth = fontSize * tuning.wrapGlyphWidthFactor;
  const maxChars = Math.max(1, Math.floor(width / avgGlyphWidth));
  if (text.length <= maxChars) return text;
  if (maxChars <= 1) return "…";
  return `${text.slice(0, Math.max(0, maxChars - 1))}…`;
}
