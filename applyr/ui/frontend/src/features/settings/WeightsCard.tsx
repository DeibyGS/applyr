import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TOPIC_LABELS } from "./topic-labels";

export function WeightsCard({ weights }: { weights: Record<string, number> }) {
  // Raw integers as written in applyr.toml's [weights] section — NOT the
  // normalized decimals calculate_score() uses internally. "30" means
  // something to a human reading their own config; "0.3" doesn't.
  const entries = Object.entries(weights);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Scoring Weights</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {entries.map(([topic, value]) => (
            <div key={topic}>
              <p className="text-xs text-muted-foreground">{TOPIC_LABELS[topic] ?? topic}</p>
              <p className="text-lg font-semibold">{value}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
