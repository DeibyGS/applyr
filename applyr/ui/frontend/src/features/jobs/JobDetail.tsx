import { ArrowLeft } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { JobDetail as JobDetailType } from "@/api/jobs";
import type { Thresholds } from "@/api/config";
import { getScoreBand, BAND_CLASS } from "./score-color";

type JobDetailProps = {
  job: JobDetailType;
  thresholds: Thresholds;
  onBack: () => void;
};

export function JobDetail({ job, thresholds, onBack }: JobDetailProps) {
  const band = getScoreBand(job.compatibility_pct, thresholds);

  return (
    <Card className="flex flex-col gap-4 border-border bg-card p-6">
      <Button variant="ghost" size="sm" className="w-fit gap-1 text-muted-foreground" onClick={onBack}>
        <ArrowLeft className="size-4" />
        Back
      </Button>

      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="font-display text-xl font-medium text-foreground">{job.title}</h2>
          <p className="text-sm text-muted-foreground">{job.company}</p>
        </div>
        <Badge className={BAND_CLASS[band]}>{job.compatibility_pct}%</Badge>
      </div>

      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
        <Badge variant="outline">{job.status}</Badge>
        {job.work_mode && <span>{job.work_mode}</span>}
        {job.location && <span>{job.location}</span>}
      </div>

      <div className="flex flex-col gap-2">
        <h3 className="font-display text-sm font-medium text-foreground">Score breakdown</h3>
        {job.topics.length === 0 && (
          <p className="text-sm text-muted-foreground">No scored topics for this offer.</p>
        )}
        {job.topics.map((topic) => (
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
    </Card>
  );
}
