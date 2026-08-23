import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function ThresholdsCard({
  thresholdApply,
  thresholdMaybe,
}: {
  thresholdApply: number;
  thresholdMaybe: number;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Scoring Thresholds</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex gap-8">
          <div>
            <p className="text-xs text-muted-foreground">Apply</p>
            <p className="text-2xl font-semibold">{thresholdApply}%</p>
            <p className="text-xs text-muted-foreground">score &gt;= this recommends APPLY</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Maybe</p>
            <p className="text-2xl font-semibold">{thresholdMaybe}%</p>
            <p className="text-xs text-muted-foreground">score &gt;= this recommends MAYBE</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
