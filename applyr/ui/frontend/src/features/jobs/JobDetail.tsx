import { ArrowLeft } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { JobDetail as JobDetailType } from "@/api/jobs";
import type { Thresholds } from "@/api/config";
import { getScoreBand, BAND_CLASS } from "./score-color";
import { ScoreBreakdown } from "./ScoreBreakdown";

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

      <ScoreBreakdown topics={job.topics} />
    </Card>
  );
}
