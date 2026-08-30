import { JobCard } from "./JobCard";
import { OFFER_STATUSES, formatStatusLabel, groupByStatus } from "./group-by-status";
import type { JobSummary } from "@/api/jobs";
import type { Thresholds } from "@/api/config";

type KanbanBoardProps = {
  jobs: JobSummary[];
  thresholds: Thresholds;
  onSelect: (id: number) => void;
  filtersActive: boolean;
};

export function KanbanBoard({ jobs, thresholds, onSelect, filtersActive }: KanbanBoardProps) {
  const grouped = groupByStatus(jobs);
  const visibleStatuses = OFFER_STATUSES.filter((status) => grouped[status].length > 0);
  const emptyStatuses = OFFER_STATUSES.filter((status) => grouped[status].length === 0);

  if (visibleStatuses.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        {filtersActive ? "No offers match these filters." : "No jobs yet."}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-start gap-4 overflow-x-auto pb-2">
        {visibleStatuses.map((status) => (
          <section key={status} className="flex w-64 shrink-0 flex-col gap-3">
            <h3 className="font-display text-sm font-medium text-foreground">
              {formatStatusLabel(status)} ({grouped[status].length})
            </h3>
            <div className="flex min-h-0 max-h-[60vh] flex-col gap-3 overflow-y-auto pr-1">
              {grouped[status].map((job) => (
                <JobCard key={job.id} job={job} thresholds={thresholds} onSelect={onSelect} />
              ))}
            </div>
          </section>
        ))}
      </div>

      {emptyStatuses.length > 0 && (
        <p className="text-xs text-muted-foreground">
          {emptyStatuses.length} empty: {emptyStatuses.map(formatStatusLabel).join(", ")}
        </p>
      )}
    </div>
  );
}
