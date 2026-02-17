import { Topbar } from "@/components/layout/topbar";

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-full min-h-0 w-full bg-background text-foreground overflow-hidden">
      <div className="flex h-full min-h-0 flex-col">
        <div className="shrink-0">
          <Topbar />
        </div>

        <main className="flex-1 min-h-0 w-full overflow-hidden">
          {children}
        </main>
      </div>
    </div>
  );
}
