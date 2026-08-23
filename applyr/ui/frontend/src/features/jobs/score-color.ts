import type { Thresholds } from "@/api/config";

export type ScoreBand = "success" | "warning" | "danger";

/**
 * Color-codes a compatibility score against the user's real, configured
 * thresholds (fetched from GET /api/config) — never a hardcoded guess at
 * what "good" means for this user.
 */
export function getScoreBand(score: number, thresholds: Thresholds): ScoreBand {
  if (score >= thresholds.threshold_apply) return "success";
  if (score >= thresholds.threshold_maybe) return "warning";
  return "danger";
}

/**
 * Maps each score band to its corresponding badge CSS classes.
 * Pairs with getScoreBand() to provide both the logic and styling layer.
 */
export const BAND_CLASS: Record<ScoreBand, string> = {
  success: "bg-success text-background",
  warning: "bg-warning text-background",
  danger: "bg-danger text-background",
};
