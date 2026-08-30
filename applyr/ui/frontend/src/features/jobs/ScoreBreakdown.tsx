import type { Topic } from "@/api/jobs";

export function ScoreBreakdown({ topics }: { topics: Topic[] }) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="font-display text-sm font-medium text-foreground">Score breakdown</h3>
      {topics.length === 0 && (
        <p className="text-sm text-muted-foreground">No scored topics for this offer.</p>
      )}
      {topics.map((topic) => (
        <div key={topic.topic} className="flex flex-col gap-1 border-b border-border pb-2 last:border-0">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-foreground capitalize">{topic.topic.replace("_", " ")}</span>
            <span className="text-muted-foreground">
              {topic.score}
              {topic.confidence ? ` · ${topic.confidence} confidence` : ""}
            </span>
          </div>
          {topic.detail && <p className="text-xs text-muted-foreground">{topic.detail}</p>}
        </div>
      ))}
    </div>
  );
}
