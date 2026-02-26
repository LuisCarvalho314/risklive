import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { OpsScheduleStatus } from "@/lib/ops/types";

type Props = {
  schedule: OpsScheduleStatus[];
};

function statusVariant(status: OpsScheduleStatus["status"]): "green" | "yellow" | "red" {
  if (status === "healthy") return "green";
  if (status === "error") return "red";
  return "yellow";
}

export function ScheduleStatusList({ schedule }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Schedule Health</CardTitle>
        <CardDescription>
          Scheduler SLA from job_start/job_complete/job_failed logs (grace: 10% interval, min 5 minutes).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {schedule.map((item) => (
          <div key={item.job} className="rounded-lg border border-border p-3">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold">{item.job}</p>
              <Badge variant={statusVariant(item.status)}>{item.status}</Badge>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">Last start: {item.lastStartTs ?? "n/a"}</p>
            <p className="text-xs text-muted-foreground">Last complete: {item.lastCompleteTs ?? "n/a"}</p>
            <p className="text-xs text-muted-foreground">Last failed: {item.lastFailedTs ?? "n/a"}</p>
            <p className="text-xs text-muted-foreground">Next expected: {item.nextExpectedTs ?? "n/a"}</p>
            <p className="text-xs text-muted-foreground">Grace: {item.graceMinutes} minutes</p>
            <p className="text-xs text-muted-foreground">Evidence: {item.evidence.join(", ") || "none"}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
