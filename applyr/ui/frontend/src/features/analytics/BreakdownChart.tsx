import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { breakdownEntries, TOOLTIP_CONTENT_STYLE } from "./analytics-data";

// Fixed categorical order — validated against the app's dark surface
// (--background #1a1917) with the dataviz skill's CVD-safety script: all 6
// checks PASS, worst adjacent CVD deltaE 9.4, worst normal-vision deltaE 19.3.
// Never cycled, never reassigned per-filter — see index.css for the source
// tokens and validation note.
const CATEGORY_FILLS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
];

export function BreakdownChart({ title, data }: { title: string; data: Record<string, number> }) {
  const entries = breakdownEntries(data);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-display">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {entries.length === 0 ? (
          <p className="text-sm text-muted-foreground">No data yet.</p>
        ) : (
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={entries} layout="vertical" margin={{ left: 16 }}>
                <XAxis type="number" stroke="var(--muted-foreground)" fontSize={12} allowDecimals={false} />
                <YAxis type="category" dataKey="key" stroke="var(--muted-foreground)" fontSize={12} width={110} />
                <Tooltip
                  contentStyle={TOOLTIP_CONTENT_STYLE}
                  formatter={(value) => [value, "Offers"]}
                />
                <Bar dataKey="count" radius={[0, 4, 4, 0]} isAnimationActive={false}>
                  {entries.map((entry, i) => (
                    <Cell key={entry.key} fill={CATEGORY_FILLS[i % CATEGORY_FILLS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
