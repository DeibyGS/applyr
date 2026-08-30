import { useEffect, useState } from "react";
import { BarChart3 } from "lucide-react";
import { ComingSoon } from "@/layout/ComingSoon";
import { PageHeader } from "@/components/ui/page-header";
import {
  getStats,
  getTrends,
  isEmptyStats,
  isFilteredEmptyStats,
  type StatsEmpty,
  type StatsPayload,
  type TrendEntry,
} from "@/api/analytics";
import { FunnelChart } from "@/features/analytics/FunnelChart";
import { TrendChart } from "@/features/analytics/TrendChart";
import { BreakdownChart } from "@/features/analytics/BreakdownChart";
import { StatCards } from "@/features/analytics/StatCards";
import { AnalyticsFilterBar } from "@/features/analytics/AnalyticsFilterBar";
import { DEFAULT_ANALYTICS_FILTERS, toQueryParams, type AnalyticsFilters } from "@/features/analytics/analytics-filters";
import { useThresholds } from "@/hooks/useThresholds";

export default function AnalyticsPage() {
  const thresholds = useThresholds();
  const [filters, setFilters] = useState<AnalyticsFilters>(DEFAULT_ANALYTICS_FILTERS);
  const [stats, setStats] = useState<StatsPayload | StatsEmpty | null>(null);
  const [trends, setTrends] = useState<TrendEntry[] | null>(null);
  const [monthTrends, setMonthTrends] = useState<TrendEntry[] | null>(null);
  const [loadError, setLoadError] = useState(false);

  // Re-fetches whenever the filter row changes — every chart on the page
  // re-renders against the same filtered slice (spec AC). TrendChart's own
  // Week/Month toggle stays independent: it re-fetches itself on top of
  // whatever `filters` this effect last passed it as a prop.
  useEffect(() => {
    const params = toQueryParams(filters);
    setLoadError(false);
    Promise.all([getStats(params), getTrends("week", params), getTrends("month", params)])
      .then(([statsResult, trendsResult, monthTrendsResult]) => {
        setStats(statsResult);
        setTrends(trendsResult);
        setMonthTrends(monthTrendsResult);
      })
      // No safe fallback for aggregate data (unlike useThresholds, which can
      // fall back to sane defaults) — surface a clear message instead of
      // leaving the page blank forever on a failed fetch.
      .catch(() => setLoadError(true));
  }, [filters]);

  if (loadError) {
    return (
      <ComingSoon
        title="Analytics"
        message="Could not load analytics data. Is the applyr backend running?"
        icon={BarChart3}
      />
    );
  }

  if (stats === null || trends === null || monthTrends === null) {
    return null;
  }

  if (isEmptyStats(stats)) {
    return (
      <div className="flex flex-col gap-8">
        <AnalyticsFilterBar filters={filters} onFiltersChange={setFilters} />
        <ComingSoon
          title="Analytics"
          message={
            isFilteredEmptyStats(stats)
              ? "No offers match these filters."
              : "No offers in the database yet."
          }
          icon={BarChart3}
        />
      </div>
    );
  }

  // Header KPI chips — use most recent period from each trend series
  // (index 0 because _trends_payload orders DESC).
  const appliedCount = stats.funnel.applied;
  const thisWeekCount = trends[0]?.count ?? 0;
  const thisMonthCount = monthTrends[0]?.count ?? 0;

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Analytics"
        description={`${stats.total} offers total · ${stats.pending} pending · ${stats.discarded} discarded`}
        chips={[
          { label: "applied", value: appliedCount },
          { label: "this week", value: thisWeekCount },
          { label: "this month", value: thisMonthCount },
        ]}
      />

      <AnalyticsFilterBar filters={filters} onFiltersChange={setFilters} />

      {/* xl: matches the charts' own xl:grid-cols-2 breakpoint below — the
          rail only makes sense once there's enough width for a 280px KPI
          column beside two-across charts without either side cramping. */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[280px_1fr]">
        <StatCards stats={stats} thresholds={thresholds} />

        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <FunnelChart stats={stats} />
            <TrendChart initialData={trends} initialPeriod="week" filters={toQueryParams(filters)} />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <BreakdownChart title="Channel Breakdown" data={stats.channels} />
            <BreakdownChart title="Work Mode Breakdown" data={stats.work_modes} />
          </div>
        </div>
      </div>
    </div>
  );
}
