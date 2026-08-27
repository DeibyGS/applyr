import type { OfficeStats } from "./office-stats";

function StatBadge({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-baseline gap-1.5 rounded-md border border-border bg-card px-3 py-1.5">
      <span className="font-display text-base font-medium text-foreground">{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  );
}

export function OfficeHeader({ stats }: { stats: OfficeStats }) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h1 className="font-display text-xl font-medium text-foreground">Office</h1>
        <p className="text-sm text-muted-foreground">Paste an offer and follow it through the pipeline.</p>
      </div>
      <div className="flex items-center gap-2">
        <StatBadge label="pending" value={stats.pendingCount} />
        <StatBadge label="agents active" value={stats.activeAgentCount} />
      </div>
    </header>
  );
}
