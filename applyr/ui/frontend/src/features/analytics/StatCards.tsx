import { CheckCircle2, AlertTriangle, XCircle, type LucideIcon } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getScoreBand, BAND_TEXT_CLASS, type ScoreBand } from "@/features/jobs/score-color";
import { cn } from "@/lib/utils";
import type { StatsPayload } from "@/api/analytics";
import type { Thresholds } from "@/api/config";

const CALIBRATION_LABELS: Record<keyof StatsPayload["score_calibration"], string> = {
  apply: "Apply",
  maybe: "Maybe",
  low_match: "Low match",
};

// score_calibration bands map 1:1 to score-color's success/warning/danger —
// reuse the same visual language the compatibility score uses elsewhere.
const CALIBRATION_BAND_COLOR: Record<keyof StatsPayload["score_calibration"], ScoreBand> = {
  apply: "success",
  maybe: "warning",
  low_match: "danger",
};

const CALIBRATION_ICON: Record<keyof StatsPayload["score_calibration"], LucideIcon> = {
  apply: CheckCircle2,
  maybe: AlertTriangle,
  low_match: XCircle,
};

// Stat cards for the left rail (refactoring-ui Component Variation: the
// number is the hero, compact padding, minimal decoration — the data is
// the design). Stacked vertically so they read top-to-bottom next to the
// charts rather than competing with them for the eye.
export function StatCards({ stats, thresholds }: { stats: StatsPayload; thresholds: Thresholds }) {
  const avgBand = getScoreBand(stats.avg_compatibility_pct, thresholds);

  return (
    <div className="flex flex-col gap-3">
      <Card className="gap-2 p-4">
        <CardHeader className="p-0">
          <CardTitle className="font-display text-sm">Average Compatibility</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <p className={cn("font-display text-3xl font-semibold", BAND_TEXT_CLASS[avgBand])}>
            {stats.avg_compatibility_pct.toFixed(1)}%
          </p>
          {stats.excluded_unknown_weights > 0 && (
            <p className="mt-1 text-xs text-muted-foreground">
              {stats.excluded_unknown_weights} offer(s) excluded — scored before weight tracking (ADR-009)
            </p>
          )}
        </CardContent>
      </Card>

      {(Object.keys(stats.score_calibration) as (keyof StatsPayload["score_calibration"])[]).map((key) => {
        const band = stats.score_calibration[key];
        const color = CALIBRATION_BAND_COLOR[key];
        const Icon = CALIBRATION_ICON[key];

        return (
          <Card key={key} className="gap-2 p-4">
            <CardHeader className="flex-row items-center gap-2 p-0">
              <Icon className={cn("size-4", band.total > 0 && BAND_TEXT_CLASS[color])} aria-hidden />
              <CardTitle className="font-display text-sm">{CALIBRATION_LABELS[key]}</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <p className="text-xs text-muted-foreground">{band.label}</p>
              {band.total === 0 ? (
                <p className="mt-1 text-sm text-muted-foreground">No data</p>
              ) : (
                <>
                  <p className={cn("font-display text-3xl font-semibold", BAND_TEXT_CLASS[color])}>
                    {band.total}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {Math.round((band.responded / band.total) * 100)}% responded
                  </p>
                </>
              )}
            </CardContent>
          </Card>
        );
      })}

      {stats.excluded_unknown_weights > 0 && (
        <p className="text-xs text-muted-foreground">
          {stats.excluded_unknown_weights} offer(s) excluded from calibration (scored before weight tracking or via manual override)
        </p>
      )}

      {stats.salary && (
        <Card className="gap-2 p-4">
          <CardHeader className="p-0">
            <CardTitle className="font-display text-sm">Salary (salary_min, where provided)</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <p className="font-display text-3xl font-semibold">{stats.salary.median.toLocaleString()}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Range: {stats.salary.min.toLocaleString()} – {stats.salary.max.toLocaleString()}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Based on {stats.salary.count} offer{stats.salary.count === 1 ? "" : "s"} with salary data
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
