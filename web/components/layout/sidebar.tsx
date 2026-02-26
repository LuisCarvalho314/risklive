import Link from "next/link";

const navItems = [
  { href: "/newsmap", label: "Newsmap" },
  { href: "/alerts", label: "Alerts" },
  { href: "/topics", label: "Topics" },
  { href: "/ops", label: "Ops" },
];

export function Sidebar() {
  return (
    <aside className="relative hidden min-h-screen flex-col gap-6 border-r border-border bg-card px-6 py-8 lg:flex">
      <div>
        <p className="font-display text-2xl">RiskLive</p>
        <p className="text-sm text-muted-foreground">Intelligence dashboard</p>
      </div>

      <nav className="flex flex-1 flex-col gap-2">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="rounded-lg px-3 py-2 text-sm font-medium text-foreground transition hover:bg-accent"
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
