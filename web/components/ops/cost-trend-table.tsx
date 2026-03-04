//© 2025 University of Aberdeen. All rights reserved


import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { OpsCostRun } from "@/lib/ops/types";

type Props = {
  buckets: OpsCostRun[];
};

function formatUsd(value: number): string {
  return `$${value.toFixed(4)}`;
}

function formatInt(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatRange(startIso: string, endIso: string): string {
  const start = new Date(startIso);
  const end = new Date(endIso);
  const startText = Number.isNaN(start.getTime()) ? startIso : start.toISOString();
  const endText = Number.isNaN(end.getTime()) ? endIso : end.toISOString();
  return `${startText} -> ${endText}`;
}

export function CostTrendTable({ buckets }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>LLM Cost Trends</CardTitle>
        <CardDescription>Recent time-bucketed cost and token usage from enriched rows.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="max-h-[320px] overflow-auto rounded-lg border border-border">
          <table className="w-full border-collapse text-left text-xs">
            <thead className="sticky top-0 bg-card">
              <tr className="border-b border-border">
                <th className="px-3 py-2">Window</th>
                <th className="px-3 py-2">LLM USD</th>
                <th className="px-3 py-2">Valyu USD</th>
                <th className="px-3 py-2">Prompt</th>
                <th className="px-3 py-2">Completion</th>
                <th className="px-3 py-2">Total</th>
              </tr>
            </thead>
            <tbody>
              {buckets.map((bucket) => (
                <tr key={bucket.bucketStartTs} className="border-b border-border/70">
                  <td className="px-3 py-2 align-top text-muted-foreground">
                    {formatRange(bucket.bucketStartTs, bucket.bucketEndTs)}
                  </td>
                  <td className="px-3 py-2 align-top">{formatUsd(bucket.llmUsd)}</td>
                  <td className="px-3 py-2 align-top">{formatUsd(bucket.valyuUsd)}</td>
                  <td className="px-3 py-2 align-top">{formatInt(bucket.promptTokens)}</td>
                  <td className="px-3 py-2 align-top">{formatInt(bucket.completionTokens)}</td>
                  <td className="px-3 py-2 align-top">{formatInt(bucket.totalTokens)}</td>
                </tr>
              ))}
              {buckets.length === 0 ? (
                <tr>
                  <td className="px-3 py-3 text-muted-foreground" colSpan={6}>
                    No cost buckets available.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
