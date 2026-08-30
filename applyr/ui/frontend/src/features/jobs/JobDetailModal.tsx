import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import type { JobDetail } from "@/api/jobs";
import type { Thresholds } from "@/api/config";
import { getScoreBand, BAND_CLASS } from "./score-color";
import { ScoreBreakdown } from "./ScoreBreakdown";

type JobDetailModalProps = {
  job: JobDetail | null;
  thresholds: Thresholds;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function JobDetailModal({ job, thresholds, open, onOpenChange }: JobDetailModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
        {job ? (
          <JobDetailModalContent job={job} thresholds={thresholds} />
        ) : (
          <DialogHeader>
            <DialogTitle>Loading…</DialogTitle>
          </DialogHeader>
        )}
      </DialogContent>
    </Dialog>
  );
}

function JobDetailModalContent({ job, thresholds }: { job: JobDetail; thresholds: Thresholds }) {
  const band = getScoreBand(job.compatibility_pct, thresholds);

  return (
    <>
      <DialogHeader>
        <div className="flex items-start justify-between gap-3 pr-6">
          <div>
            <DialogTitle className="font-display text-lg">{job.title}</DialogTitle>
            <DialogDescription>{job.company}</DialogDescription>
          </div>
          <Badge className={BAND_CLASS[band]}>{job.compatibility_pct}%</Badge>
        </div>
      </DialogHeader>

      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
        <Badge variant="outline">{job.status}</Badge>
        {job.work_mode && <span>{job.work_mode}</span>}
        {job.location && <span>{job.location}</span>}
      </div>

      <ScoreBreakdown topics={job.topics} />
    </>
  );
}
