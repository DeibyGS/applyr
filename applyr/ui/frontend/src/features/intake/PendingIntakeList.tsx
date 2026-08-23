import { Card } from "@/components/ui/card";
import type { IntakeRow } from "@/api/intake";

export function PendingIntakeList({ rows }: { rows: IntakeRow[] }) {
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
          <li key={row.id} className="border-b border-border pb-2 text-sm text-muted-foreground last:border-0">
            <span className="text-foreground">#{row.id}</span> {row.raw_text.slice(0, 80)}
            {row.raw_text.length > 80 ? "..." : ""}
            {row.source_note ? ` (${row.source_note})` : ""}
          </li>
        ))}
      </ul>
    </Card>
  );
}
