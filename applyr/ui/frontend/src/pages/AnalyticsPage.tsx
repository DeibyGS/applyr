import { useEffect, useState } from "react";
import { BarChart3 } from "lucide-react";
import { ComingSoon } from "@/layout/ComingSoon";
import { getStats, getTrends, isEmptyStats, type StatsEmpty, type StatsPayload, type TrendEntry } from "@/api/analytics";
import { FunnelChart } from "@/features/analytics/FunnelChart";
import { TrendChart } from "@/features/analytics/TrendChart";
import { BreakdownChart } from "@/features/analytics/BreakdownChart";
import { StatCards } from "@/features/analytics/StatCards";

export default function AnalyticsPage() {
  // Single fetch on mount, deliberately not polled — aggregate stats don't
  // change on a 2-3s timescale the way Office/Offers' underlying tables do
  // (spec: specs/visual-ui-slice-5-analytics/spec.md).
  const [stats, setStats] = useState<StatsPayload | StatsEmpty | null>(null);
  const [trends, setTrends] = useState<TrendEntry[] | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    Promise.all([getStats(), getTrends("week")])
      .then(([statsResult, trendsResult]) => {
        setStats(statsResult);
        setTrends(trendsResult);
      })
      // No safe fallback for aggregate data (unlike useThresholds, which can
      // fall back to sane defaults) — surface a clear message instead of
      // leaving the page blank forever on a failed fetch.
      .catch(() => setLoadError(true));
  }, []);

  if (loadError) {
    return (
      <ComingSoon
        title="Analytics"
        message="Could not load analytics data. Is the applyr backend running?"
        icon={BarChart3}
      />
    );
  }

  if (stats === null || trends === null) {
    return null;
  }

  if (isEmptyStats(stats)) {
    return (
      <ComingSoon
        title="Analytics"
        message="No offers in the database yet."
        icon={BarChart3}
      />
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-1">
        <h1 className="font-display text-2xl font-medium text-foreground">Analytics</h1>
        <p className="text-sm text-muted-foreground">
          {stats.total} offers total &middot; {stats.pending} pending &middot; {stats.discarded} discarded
        </p>
      </header>

      <StatCards stats={stats} />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <FunnelChart stats={stats} />
        <TrendChart initialData={trends} initialPeriod="week" />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <BreakdownChart title="Channel Breakdown" data={stats.channels} />
        <BreakdownChart title="Work Mode Breakdown" data={stats.work_modes} />
      </div>
    </div>
  );
}
