import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { JobSummary } from "@/api/jobs";
import type { Thresholds } from "@/api/config";
import { getScoreBand, BAND_CLASS } from "./score-color";

type JobCardProps = {
  job: JobSummary;
  thresholds: Thresholds;
  onSelect: (id: number) => void;
};

export function JobCard({ job, thresholds, onSelect }: JobCardProps) {
  const band = getScoreBand(job.compatibility_pct, thresholds);

  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={() => onSelect(job.id)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") onSelect(job.id);
      }}
      className="flex cursor-pointer flex-col gap-2 border-border bg-card p-4 text-left transition-colors hover:border-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-display text-base font-medium text-foreground">{job.title}</p>
          <p className="text-sm text-muted-foreground">{job.company}</p>
        </div>
        <Badge className={BAND_CLASS[band]}>{job.compatibility_pct}%</Badge>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge variant="outline">{job.status}</Badge>
        {job.work_mode && <span>{job.work_mode}</span>}
        {job.location && <span>{job.location}</span>}
      </div>
    </Card>
  );
}
