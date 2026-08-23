import type { FunnelPct, Funnel, StatsPayload, TrendEntry } from "../../api/analytics";

export const TOOLTIP_CONTENT_STYLE = {
  background: "var(--card)",
  border: "1px solid var(--border)",
  color: "var(--foreground)",
};

export type FunnelStage = {
  key: keyof Funnel;
  label: string;
  count: number;
  pct: number | null;
};

const FUNNEL_STAGE_LABELS: Record<keyof Funnel, string> = {
  applied: "Applied",
  responded: "Responded",
  interview: "Interview",
  offer: "Offer",
};

const FUNNEL_STAGE_ORDER: (keyof Funnel)[] = ["applied", "responded", "interview", "offer"];

/** Ordered funnel stages with the percentages already computed by the backend
 * (`_stats_payload`'s `funnel_pct`) — never re-derived here, so the CLI and
 * the UI can never disagree about the same number. */
export function funnelStages(stats: Pick<StatsPayload, "funnel" | "funnel_pct">): FunnelStage[] {
  return FUNNEL_STAGE_ORDER.map((key) => ({
    key,
    label: FUNNEL_STAGE_LABELS[key],
    count: stats.funnel[key],
    pct: (stats.funnel_pct as FunnelPct)[key],
  }));
}

export type BreakdownEntry = {
  key: string;
  count: number;
};

/** Converts a `{label: count}` record (channels, work_modes) into a chart-ready
 * array, sorted by count descending — defensive re-sort, does not assume the
 * backend's dict insertion order survives JSON round-tripping. */
export function breakdownEntries(record: Record<string, number>): BreakdownEntry[] {
  return Object.entries(record)
    .map(([key, count]) => ({ key, count }))
    .sort((a, b) => b.count - a.count);
}

export type TrendPoint = {
  period: string;
  count: number;
  growthPct: number | null;
};

/** The backend returns trend rows newest-first (`ORDER BY period DESC`) for
 * the CLI's top-to-bottom reading; a time-series chart reads left-to-right
 * chronologically, so this reverses the order — the only reshaping this
 * function does, growth_pct passes through unchanged. */
export function trendChartData(entries: TrendEntry[]): TrendPoint[] {
  return [...entries].reverse().map((e) => ({
    period: e.period,
    count: e.count,
    growthPct: e.growth_pct,
  }));
}
