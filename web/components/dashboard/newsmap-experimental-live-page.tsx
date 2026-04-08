//© 2025 University of Aberdeen. All rights reserved


"use client";

import { TreemapExperimentalClient } from "@/components/newsmap/treemap-experimental-client";
import { useDashboardData } from "@/lib/dashboard-client";
import type { ExperimentalTimelineResult } from "@/lib/newsmap-experimental-shared";

type Props = {
  timelineResult: ExperimentalTimelineResult;
};

export function NewsmapExperimentalLivePage({ timelineResult }: Props) {
  const { dashboard } = useDashboardData();

  return (
    <div className="h-full min-h-0 p-1">
      <div className="h-full w-full overflow-hidden rounded-2xl">
        <div className="h-full w-full p-1.5">
          <div className="h-full min-h-[30rem]">
            <TreemapExperimentalClient
              fallbackTree={dashboard.newsmap}
              timelineResult={timelineResult}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
