import { Cell, Funnel, FunnelChart as RechartsFunnelChart, LabelList, ResponsiveContainer, Tooltip } from "recharts";
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
  const data = stages.map((s) => ({
    name: s.label,
    value: s.count,
    pctLabel: s.pct === null ? "" : `${s.pct}%`,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Conversion Funnel</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-64 w-full" role="img" aria-label={stages.map((s) => `${s.label}: ${s.count}${s.pct !== null ? ` (${s.pct}%)` : ""}`).join(", ")}>
          <ResponsiveContainer width="100%" height="100%">
            <RechartsFunnelChart>
              <Tooltip
                contentStyle={TOOLTIP_CONTENT_STYLE}
                formatter={(value) => [value, "Offers"]}
              />
              <Funnel dataKey="value" data={data} isAnimationActive={false}>
                <LabelList dataKey="name" position="left" fill="var(--foreground)" stroke="none" />
                <LabelList dataKey="value" position="right" fill="var(--foreground)" stroke="none" />
                {data.map((entry, i) => (
                  <Cell key={entry.name} fill={STAGE_FILLS[i % STAGE_FILLS.length]} />
                ))}
              </Funnel>
            </RechartsFunnelChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
