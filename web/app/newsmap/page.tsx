import { TreemapClient } from "@/components/newsmap/treemap-client";
import { loadDashboard } from "@/lib/dashboard";

export default async function NewsmapPage() {
  const dashboard = await loadDashboard();

  return (
    <div className="h-full w-full overflow-hidden">
      <TreemapClient data={dashboard.newsmap} />
    </div>
  );
}
