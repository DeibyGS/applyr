import { JobCard } from "./JobCard";
import { OFFER_STATUSES, formatStatusLabel, groupByStatus } from "./group-by-status";
import type { JobSummary } from "@/api/jobs";
import type { Thresholds } from "@/api/config";

type KanbanBoardProps = {
  jobs: JobSummary[];
  thresholds: Thresholds;
  onSelect: (id: number) => void;
};

export function KanbanBoard({ jobs, thresholds, onSelect }: KanbanBoardProps) {
  const grouped = groupByStatus(jobs);

  return (
    <div className="flex gap-4 overflow-x-auto pb-2">
      {OFFER_STATUSES.map((status) => (
        <section key={status} className="flex w-64 shrink-0 flex-col gap-3">
          <h3 className="font-display text-sm font-medium text-foreground">
            {formatStatusLabel(status)} ({grouped[status].length})
          </h3>
          <div className="flex flex-col gap-3">
            {grouped[status].length === 0 ? (
              <p className="text-xs text-muted-foreground">No offers.</p>
            ) : (
              grouped[status].map((job) => (
                <JobCard key={job.id} job={job} thresholds={thresholds} onSelect={onSelect} />
              ))
            )}
          </div>
        </section>
      ))}
    </div>
  );
}
