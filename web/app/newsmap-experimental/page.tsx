//© 2025 University of Aberdeen. All rights reserved

import { NewsmapExperimentalLivePage } from "@/components/dashboard/newsmap-experimental-live-page";
import { loadExperimentalNewsmap } from "@/lib/newsmap-experimental";

export const dynamic = "force-dynamic";

export default async function NewsmapExperimentalPage() {
  const timelineResult = await loadExperimentalNewsmap();

  return (
    <NewsmapExperimentalLivePage timelineResult={timelineResult} />
  );
}
