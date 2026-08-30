import { Building2, Home, MapPin, Repeat } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { JobSummary } from "@/api/jobs";
import type { Thresholds } from "@/api/config";
import { getScoreBand, BAND_BORDER_CLASS, BAND_TEXT_CLASS } from "./score-color";
import { formatStatusLabel, statusAccentClass } from "./group-by-status";

type JobCardProps = {
  job: JobSummary;
  thresholds: Thresholds;
  onSelect: (id: number) => void;
};

const WORK_MODE_ICON = { remote: Home, hybrid: Repeat, onsite: Building2 } as const;

export function JobCard({ job, thresholds, onSelect }: JobCardProps) {
  const band = getScoreBand(job.compatibility_pct, thresholds);
  const WorkModeIcon = job.work_mode ? WORK_MODE_ICON[job.work_mode as keyof typeof WORK_MODE_ICON] : null;

  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={() => onSelect(job.id)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") onSelect(job.id);
      }}
      className={cn(
        "flex cursor-pointer flex-col gap-3 border-l-[3px] bg-card p-4 text-left transition-colors hover:bg-secondary/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
        BAND_BORDER_CLASS[band]
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-display text-base leading-snug font-medium text-foreground">{job.title}</p>
          <p className="mt-0.5 text-sm text-muted-foreground">{job.company}</p>
        </div>
        <div className="flex shrink-0 flex-col items-end">
          <span className={cn("font-display text-xl leading-none font-semibold", BAND_TEXT_CLASS[band])}>
            {job.compatibility_pct}%
          </span>
          <span className="mt-1 text-[10px] font-medium tracking-wide text-muted-foreground uppercase">
            Match
          </span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t border-border/60 pt-2.5 text-xs text-muted-foreground">
        <Badge variant="outline" className={statusAccentClass(job.status)}>
          {formatStatusLabel(job.status)}
        </Badge>
        {job.work_mode && (
          <span className="inline-flex items-center gap-1">
            {WorkModeIcon && <WorkModeIcon className="size-3.5" aria-hidden />}
            {job.work_mode}
          </span>
        )}
        {job.location && (
          <span className="inline-flex items-center gap-1">
            <MapPin className="size-3.5" aria-hidden />
            {job.location}
          </span>
        )}
      </div>
    </Card>
  );
}
