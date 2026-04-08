//© 2025 University of Aberdeen. All rights reserved


"use client";

import { TreemapClient } from "@/components/newsmap/treemap-client";
import { useDashboardData } from "@/lib/dashboard-client";

export function NewsmapLivePage() {
  const { dashboard } = useDashboardData();

  return (
    <div className="h-full min-h-0 p-1">
      <div className="h-full w-full overflow-hidden rounded-2xl">
        <div className="h-full w-full p-1.5">
          <div className="h-full min-h-[30rem]">
            <TreemapClient data={dashboard.newsmap} />
          </div>
        </div>
      </div>
    </div>
  );
}
