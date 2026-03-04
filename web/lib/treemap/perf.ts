export function resolveAnimationDuration(baseDurationMs: number, nodeCount: number): number {
  if (nodeCount > 900) return Math.max(300, Math.round(baseDurationMs * 0.4));
  if (nodeCount > 400) return Math.max(450, Math.round(baseDurationMs * 0.62));
  return baseDurationMs;
}

