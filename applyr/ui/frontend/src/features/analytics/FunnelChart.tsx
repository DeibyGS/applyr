import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { StatsPayload } from "@/api/analytics";
import { funnelStages, TOOLTIP_CONTENT_STYLE } from "./analytics-data";

// Single hue, light->dark down the funnel — an ordinal encoding (ordered
// stages of one flow), not a categorical one, per the dataviz skill's
// sequential/ordinal guidance. Validated with the dataviz skill's
// validate_palette.js --ordinal check against the real --background
// (#1a1917): lightness monotone, adjacent-step gaps, single hue, and the
// darkest step clearing the 2:1 contrast-vs-surface floor all PASS.
const STAGE_FILLS = ["#5cc4a3", "#3aad88", "#238a6c", "#1c6e57"];

export function FunnelChart({ stats }: { stats: Pick<StatsPayload, "funnel" | "funnel_pct"> }) {
  const stages = funnelStages(stats);
  // Horizontal bars (not the proportional-area Funnel shape) so a count of
  // 0 renders as a zero-length bar instead of collapsing the funnel
  // silhouette — see analytics-filters-and-fixes spec, T6.
  const data = stages.map((s) => ({
    name: s.label,
    value: s.count,
    label: s.pct === null ? `${s.count}` : `${s.count} (${s.pct}%)`,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-display">Conversion Funnel</CardTitle>
      </CardHeader>
      <CardContent>
        <div
          className="h-64 w-full"
          role="img"
          aria-label={stages
            .map((s) => `${s.label}: ${s.count}${s.pct !== null ? ` (${s.pct}%)` : ""}`)
            .join(", ")}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical" margin={{ left: 16, right: 48 }}>
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="name"
                stroke="var(--muted-foreground)"
                fontSize={12}
                width={80}
              />
              <Tooltip contentStyle={TOOLTIP_CONTENT_STYLE} formatter={(value) => [value, "Offers"]} />
              <Bar dataKey="value" isAnimationActive={false} radius={[0, 4, 4, 0]}>
                <LabelList dataKey="label" position="right" fill="var(--foreground)" stroke="none" fontSize={12} />
                {data.map((entry, i) => (
                  <Cell key={entry.name} fill={STAGE_FILLS[i % STAGE_FILLS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
