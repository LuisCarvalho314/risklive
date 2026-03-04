//© 2025 University of Aberdeen. All rights reserved


import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { OpsOverview } from "@/lib/ops/types";

type Props = {
  overview: OpsOverview;
};

function summaryVariant(status: OpsOverview["overallStatus"]): "green" | "yellow" | "red" {
  if (status === "healthy") return "green";
  if (status === "error") return "red";
  return "yellow";
}

export function OpsOverviewCards({ overview }: Props) {
  const formatUsd = (value: number) => `$${value.toFixed(4)}`;
  const formatInt = (value: number) => new Intl.NumberFormat("en-US").format(value);

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
      <Card>
        <CardHeader>
          <CardDescription>Overall Status</CardDescription>
          <CardTitle className="text-2xl capitalize">{overview.overallStatus}</CardTitle>
        </CardHeader>
        <CardContent>
          <Badge variant={summaryVariant(overview.overallStatus)}>{overview.overallStatus}</Badge>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardDescription>Errors (24 hours)</CardDescription>
          <CardTitle className="text-2xl">{overview.errorCounts.day}</CardTitle>
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground">
          Week: {overview.errorCounts.week} | Month: {overview.errorCounts.month}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardDescription>Warnings (24 hours)</CardDescription>
          <CardTitle className="text-2xl">{overview.warningCounts.day}</CardTitle>
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground">
          Week: {overview.warningCounts.week} | Month: {overview.warningCounts.month}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardDescription>Log Parse Errors</CardDescription>
          <CardTitle className="text-2xl">{overview.parseErrors}</CardTitle>
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground">
          Rolling windows: day/week/month. Generated at {overview.generatedAt}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardDescription>LLM Cost (24 hours)</CardDescription>
          <CardTitle className="text-2xl">{formatUsd(overview.costs.llm.dayUsd)}</CardTitle>
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground">
          Week: {formatUsd(overview.costs.llm.weekUsd)} | Month: {formatUsd(overview.costs.llm.monthUsd)}
          <br />
          Quality: <span className="capitalize">{overview.costs.llm.quality.status}</span>.{" "}
          {overview.costs.llm.quality.reason}
          <br />
          Explicit: {overview.costs.llm.quality.rowsWithExplicitPrice} | Derived:{" "}
          {overview.costs.llm.quality.rowsWithDerivedPrice} | Missing: {overview.costs.llm.quality.rowsWithoutPrice}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardDescription>Tokens (24 hours)</CardDescription>
          <CardTitle className="text-2xl">{formatInt(overview.costs.llm.dayTokens)}</CardTitle>
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground">
          Week: {formatInt(overview.costs.llm.weekTokens)} | Month: {formatInt(overview.costs.llm.monthTokens)}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardDescription>Valyu Cost (24 hours)</CardDescription>
          <CardTitle className="text-2xl">{formatUsd(overview.costs.valyu.dayUsd)}</CardTitle>
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground">
          Status: <span className="capitalize">{overview.costs.valyu.status}</span>. Week:{" "}
          {formatUsd(overview.costs.valyu.weekUsd)} | Month: {formatUsd(overview.costs.valyu.monthUsd)}
          <br />
          {overview.costs.valyu.reason}
        </CardContent>
      </Card>
    </div>
  );
}
