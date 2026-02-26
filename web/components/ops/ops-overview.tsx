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
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
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
    </div>
  );
}
