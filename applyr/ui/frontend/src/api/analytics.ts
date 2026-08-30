import { request } from "./client";
import type { AnalyticsQueryParams } from "@/features/analytics/analytics-filters";

export type Funnel = {
  applied: number;
  responded: number;
  interview: number;
  offer: number;
};

export type FunnelPct = {
  applied: number | null;
  responded: number | null;
  interview: number | null;
  offer: number | null;
};

export type CalibrationBand = {
  label: string;
  total: number;
  responded: number;
  interview: number;
  offer: number;
};

export type ScoreCalibration = {
  apply: CalibrationBand;
  maybe: CalibrationBand;
  low_match: CalibrationBand;
};

export type StatsEmpty = { total: 0; filtered?: boolean };

export type StatsPayload = {
  total: number;
  pending: number;
  discarded: number;
  avg_compatibility_pct: number;
  avg_compatibility_pct_excluded_unknown_weights: number;
  funnel: Funnel;
  funnel_pct: FunnelPct;
  channels: Record<string, number>;
  work_modes: Record<string, number>;
  score_calibration: ScoreCalibration;
  excluded_unknown_weights: number;
  salary?: { min: number; max: number; avg: number; median: number; count: number };
};

export type TrendPeriod = "week" | "month";

export type TrendEntry = {
  period: string;
  count: number;
  growth_pct: number | null;
};

export function isEmptyStats(payload: StatsPayload | StatsEmpty): payload is StatsEmpty {
  return payload.total === 0;
}

/**
 * Distinguishes "filters matched zero offers" from "the DB has no offers at
 * all" — the backend only sets `filtered: true` in the former case (see
 * `_stats_payload`).
 */
export function isFilteredEmptyStats(payload: StatsPayload | StatsEmpty): boolean {
  return isEmptyStats(payload) && payload.filtered === true;
}

function buildQuery(params: Record<string, string | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) search.set(key, value);
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export function getStats(filters: AnalyticsQueryParams = {}): Promise<StatsPayload | StatsEmpty> {
  return request(`/api/stats${buildQuery(filters)}`);
}

export function getTrends(
  period: TrendPeriod = "week",
  filters: AnalyticsQueryParams = {}
): Promise<TrendEntry[]> {
  return request(`/api/trends${buildQuery({ period, ...filters })}`);
}
