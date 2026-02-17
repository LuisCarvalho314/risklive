import Link from "next/link";

export function Topbar() {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-background px-4 py-2">
      <div className="leading-tight">
        <p className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          Risklive Ops
        </p>
        <h1 className="font-display text-xl sm:text-2xl">
          Dashboard
        </h1>
      </div>

      <nav className="flex flex-wrap items-center gap-2">
        <Link
          href="/topics"
          className="rounded-full border border-border px-3 py-1 text-[11px] font-semibold text-foreground transition hover:bg-accent hover:text-accent-foreground"
        >
          Daily Report
        </Link>
        <Link
          href="/newsmap"
          className="rounded-full border border-border px-3 py-1 text-[11px] font-semibold text-foreground transition hover:bg-accent hover:text-accent-foreground"
        >
          Newsmap
        </Link>
        <Link
          href="/alerts"
          className="rounded-full border border-border px-3 py-1 text-[11px] font-semibold text-foreground transition hover:bg-accent hover:text-accent-foreground"
        >
          Alerts
        </Link>
      </nav>
    </header>
  );
}
