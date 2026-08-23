import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getTrends, type TrendEntry, type TrendPeriod } from "@/api/analytics";
import { trendChartData, TOOLTIP_CONTENT_STYLE } from "./analytics-data";

export function TrendChart({
  initialData,
  initialPeriod,
}: {
  initialData: TrendEntry[];
  initialPeriod: TrendPeriod;
}) {
  const [period, setPeriod] = useState<TrendPeriod>(initialPeriod);
  const [entries, setEntries] = useState<TrendEntry[]>(initialData);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(false);

  // The one interaction in this whole slice allowed to trigger a second
  // fetch (spec AC) — aggregate stats otherwise load once on page mount,
  // no polling, since they don't change on a 2-3s timescale. `period` only
  // flips (and the active-button styling with it) once the new data has
  // actually loaded — flipping it eagerly would leave the toggle pointing
  // at a period whose chart never arrived if the fetch fails.
  async function handlePeriodChange(next: TrendPeriod) {
    if (next === period) return;
    setLoading(true);
    setLoadError(false);
    try {
      const data = await getTrends(next);
      setEntries(data);
      setPeriod(next);
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }

  const data = trendChartData(entries);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Applications Over Time</CardTitle>
        <CardAction>
          <div className="flex gap-1">
            <Button
              size="sm"
              variant={period === "week" ? "default" : "outline"}
              onClick={() => handlePeriodChange("week")}
            >
              Week
            </Button>
            <Button
              size="sm"
              variant={period === "month" ? "default" : "outline"}
              onClick={() => handlePeriodChange("month")}
            >
              Month
            </Button>
          </div>
        </CardAction>
      </CardHeader>
      <CardContent>
        {loadError && (
          <p className="mb-2 text-sm text-destructive">
            Could not load {period} trends — showing the last successful data.
          </p>
        )}
        {data.length === 0 ? (
          <p className="text-sm text-muted-foreground">No dated offers found.</p>
        ) : (
          <div className="h-64 w-full" aria-hidden={loading}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data}>
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis dataKey="period" stroke="var(--muted-foreground)" fontSize={12} />
                <YAxis stroke="var(--muted-foreground)" fontSize={12} allowDecimals={false} />
                <Tooltip
                  contentStyle={TOOLTIP_CONTENT_STYLE}
                  formatter={(value) => [value, "Applications"]}
                />
                <Bar dataKey="count" fill="var(--chart-1)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
