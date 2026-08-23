import { request } from "./client";

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

export type StatsEmpty = { total: 0 };

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
  salary?: { min: number; max: number; avg: number };
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

export function getStats(): Promise<StatsPayload | StatsEmpty> {
  return request("/api/stats");
}

export function getTrends(period: TrendPeriod = "week"): Promise<TrendEntry[]> {
  return request(`/api/trends?period=${period}`);
}
