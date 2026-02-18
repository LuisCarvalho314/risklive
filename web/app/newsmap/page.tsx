import { TreemapClient } from "@/components/newsmap/treemap-client";
import { loadDashboard } from "@/lib/dashboard";

export default async function NewsmapPage() {
  const dashboard = await loadDashboard();

  return (
    <div className="h-full min-h-0 p-1">
      <div className="h-full w-full overflow-hidden rounded-2xl">
        <div className="h-full w-full p-1.5">
          <TreemapClient data={dashboard.newsmap} />
        </div>
      </div>
    </div>
  );
}
