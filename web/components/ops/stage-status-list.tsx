import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { OpsStageStatus } from "@/lib/ops/types";

type Props = {
  stages: OpsStageStatus[];
};

function stageVariant(status: OpsStageStatus["status"]): "green" | "yellow" | "red" {
  if (status === "healthy") return "green";
  if (status === "error" || status === "missing") return "red";
  return "yellow";
}

export function StageStatusList({ stages }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Pipeline Stages</CardTitle>
        <CardDescription>Status from pipeline_stage_end and pipeline_run_end logs.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {stages.map((stage) => (
          <div key={stage.stage} className="rounded-lg border border-border p-3">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold capitalize">{stage.stage.replace("_", " ")}</p>
              <Badge variant={stageVariant(stage.status)}>{stage.status}</Badge>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">Last success: {stage.lastSuccessTs ?? "n/a"}</p>
            <p className="text-xs text-muted-foreground">Duration: {stage.lastRunDurationMs ?? "n/a"} ms</p>
            <p className="text-xs text-muted-foreground">Log evidence: {stage.evidence.join(", ") || "none"}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
