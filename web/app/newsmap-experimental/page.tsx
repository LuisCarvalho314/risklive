//© 2025 University of Aberdeen. All rights reserved


import { TreemapExperimentalClient } from "@/components/newsmap/treemap-experimental-client";
import { loadDashboard } from "@/lib/dashboard";
import { loadExperimentalNewsmap } from "@/lib/newsmap-experimental";

export default async function NewsmapExperimentalPage() {
  const [dashboard, timelineResult] = await Promise.all([
    loadDashboard(),
    loadExperimentalNewsmap(),
  ]);

  return (
    <div className="h-full min-h-0 p-1">
      <div className="h-full w-full overflow-hidden rounded-2xl">
        <div className="h-full w-full p-1.5">
          <TreemapExperimentalClient
            fallbackTree={dashboard.newsmap}
            timelineResult={timelineResult}
          />
        </div>
      </div>
    </div>
  );
}
