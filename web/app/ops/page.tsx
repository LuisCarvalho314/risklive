import { OpsAutoRefresh } from "@/components/ops/auto-refresh";
import { ArtifactTable } from "@/components/ops/artifact-table";
import { LogTable } from "@/components/ops/log-table";
import { OpsOverviewCards } from "@/components/ops/ops-overview";
import { ScheduleStatusList } from "@/components/ops/schedule-status-list";
import { StageStatusList } from "@/components/ops/stage-status-list";
import { inspectArtifacts } from "@/lib/ops/artifact-inspector";
import { readLogEvents } from "@/lib/ops/log-parser";
import { buildOpsOverview } from "@/lib/ops/status-aggregator";

export const dynamic = "force-dynamic";

export default async function OpsPage() {
  const [overview, artifactList, parsedLogs] = await Promise.all([
    buildOpsOverview(),
    inspectArtifacts(),
    readLogEvents(500)
  ]);

  return (
    <div className="h-full min-h-0 overflow-y-auto p-6">
      <OpsAutoRefresh intervalMs={5000} />
      <div className="space-y-6">
        <div>
          <h1 className="font-display text-3xl">Operations</h1>
          <p className="text-sm text-muted-foreground">
            Stage and run health is derived from structured pipeline logs. Artifacts are shown for visibility only.
          </p>
        </div>

        <OpsOverviewCards overview={overview} />

        <ScheduleStatusList schedule={overview.schedule} />

        <StageStatusList stages={overview.stages} />

        <ArtifactTable artifacts={artifactList} />

        <LogTable events={parsedLogs.events} />
      </div>
    </div>
  );
}
