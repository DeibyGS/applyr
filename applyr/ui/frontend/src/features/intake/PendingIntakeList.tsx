import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { retryIntakeJob, type IntakeRow } from "@/api/intake";
import { JOB_STATE_LABEL, JOB_STATE_VARIANT } from "./job-state-copy";

type PendingIntakeListProps = {
  rows: IntakeRow[];
  onRetried?: () => void;
};

export function PendingIntakeList({ rows, onRetried }: PendingIntakeListProps) {
  const [retryingId, setRetryingId] = useState<number | null>(null);

  async function handleRetry(intakeId: number) {
    setRetryingId(intakeId);
    try {
      await retryIntakeJob(intakeId);
      onRetried?.();
    } finally {
      setRetryingId(null);
    }
  }

  return (
    <Card className="flex flex-col gap-2 border-border bg-card p-4">
      <h2 className="font-display text-base font-medium text-foreground">
        Waiting for your agent ({rows.length})
      </h2>
      {rows.length === 0 && (
        <p className="text-sm text-muted-foreground">Nothing pending — paste an offer above.</p>
      )}
      <ul className="flex flex-col gap-2">
        {rows.map((row) => (
          <li
            key={row.id}
            className="flex flex-col gap-1 border-b border-border pb-2 text-sm text-muted-foreground last:border-0"
          >
            <div className="flex items-center justify-between gap-2">
              <span>
                <span className="text-foreground">#{row.id}</span> {row.raw_text.slice(0, 80)}
                {row.raw_text.length > 80 ? "..." : ""}
                {row.source_note ? ` (${row.source_note})` : ""}
              </span>
              {row.job && <Badge variant={JOB_STATE_VARIANT[row.job.state]}>{JOB_STATE_LABEL[row.job.state]}</Badge>}
            </div>
            {row.job?.state === "failed" && (
              <div className="flex items-center gap-2">
                {row.job.error_message && <span className="text-xs text-destructive">{row.job.error_message}</span>}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={retryingId === row.id}
                  onClick={() => handleRetry(row.id)}
                >
                  {retryingId === row.id ? "Retrying…" : "Retry"}
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}
