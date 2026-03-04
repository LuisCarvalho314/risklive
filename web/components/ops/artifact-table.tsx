//© 2025 University of Aberdeen. All rights reserved


import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { OpsArtifact } from "@/lib/ops/types";

type Props = {
  artifacts: OpsArtifact[];
};

export function ArtifactTable({ artifacts }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Artifacts</CardTitle>
        <CardDescription>Pipeline outputs for inspection. Artifact presence does not determine stage health.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-auto rounded-lg border border-border">
          <table className="w-full border-collapse text-left text-xs">
            <thead className="bg-card">
              <tr className="border-b border-border">
                <th className="px-3 py-2">id</th>
                <th className="px-3 py-2">path</th>
                <th className="px-3 py-2">exists</th>
                <th className="px-3 py-2">modified</th>
                <th className="px-3 py-2">size</th>
                <th className="px-3 py-2">rows</th>
              </tr>
            </thead>
            <tbody>
              {artifacts.map((artifact) => (
                <tr key={artifact.id} className="border-b border-border/70">
                  <td className="px-3 py-2">{artifact.id}</td>
                  <td className="px-3 py-2 text-muted-foreground">{artifact.path}</td>
                  <td className="px-3 py-2">{artifact.exists ? "yes" : "no"}</td>
                  <td className="px-3 py-2 text-muted-foreground">{artifact.modifiedAt ?? "-"}</td>
                  <td className="px-3 py-2">{artifact.sizeBytes}</td>
                  <td className="px-3 py-2">{artifact.rowCount ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
