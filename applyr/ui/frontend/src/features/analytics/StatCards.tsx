import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { StatsPayload } from "@/api/analytics";

const CALIBRATION_LABELS: Record<keyof StatsPayload["score_calibration"], string> = {
  apply: "Apply band",
  maybe: "Maybe band",
  low_match: "Low match band",
};

export function StatCards({ stats }: { stats: StatsPayload }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Average Compatibility</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-3xl font-semibold">{stats.avg_compatibility_pct.toFixed(1)}%</p>
          {stats.excluded_unknown_weights > 0 && (
            <p className="mt-1 text-xs text-muted-foreground">
              {stats.excluded_unknown_weights} offer(s) excluded — scored before weight tracking (ADR-009)
            </p>
          )}
        </CardContent>
      </Card>

      {stats.salary && (
        <Card>
          <CardHeader>
            <CardTitle>Salary (salary_min, where provided)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-6">
              <div>
                <p className="text-xs text-muted-foreground">Min</p>
                <p className="text-xl font-semibold">{stats.salary.min.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Avg</p>
                <p className="text-xl font-semibold">{stats.salary.avg.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Max</p>
                <p className="text-xl font-semibold">{stats.salary.max.toLocaleString()}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="sm:col-span-2">
        <CardHeader>
          <CardTitle>Score Calibration</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {(Object.keys(stats.score_calibration) as (keyof StatsPayload["score_calibration"])[]).map((key) => {
              const band = stats.score_calibration[key];
              return (
                <div key={key}>
                  <p className="text-xs text-muted-foreground">
                    {CALIBRATION_LABELS[key]} ({band.label})
                  </p>
                  <p className="text-sm">
                    {band.total === 0 ? "No data" : `${band.total} applied`}
                  </p>
                </div>
              );
            })}
          </div>
          {stats.excluded_unknown_weights > 0 && (
            <p className="mt-3 text-xs text-muted-foreground">
              {stats.excluded_unknown_weights} offer(s) excluded from calibration (scored before weight tracking or via manual override)
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
