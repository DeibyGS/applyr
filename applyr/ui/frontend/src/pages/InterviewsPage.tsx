import { useState } from "react";
import { CalendarClock } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { JobList } from "@/features/jobs/JobList";
import { JobDetail } from "@/features/jobs/JobDetail";
import { InterviewsToolbar } from "@/features/interviews/InterviewsToolbar";
import {
  DEFAULT_FILTERS,
  filterJobs,
  hasActiveFilters,
  nextSortState,
  sortJobs,
  type SortDirection,
  type SortField,
} from "@/features/interviews/interview-filters";
import { useIntakeAndJobs } from "@/hooks/useIntakeAndJobs";
import { useThresholds } from "@/hooks/useThresholds";
import { useSelectedJob } from "@/hooks/useSelectedJob";

export default function InterviewsPage() {
  const { jobs } = useIntakeAndJobs();
  const thresholds = useThresholds();
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const selectedJob = useSelectedJob(selectedJobId);

  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [sortField, setSortField] = useState<SortField>("date");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  function handleSortChange(field: SortField) {
    const next = nextSortState(sortField, sortDirection, field);
    setSortField(next.field);
    setSortDirection(next.direction);
  }

  const visibleJobs = sortJobs(filterJobs(jobs, filters), sortField, sortDirection);
  const filtersActive = hasActiveFilters(filters);
  const successCount = jobs.filter((job) => job.status === "offer").length;

  if (selectedJob) {
    return <JobDetail job={selectedJob} thresholds={thresholds} onBack={() => setSelectedJobId(null)} />;
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Interviews"
        description={`Offers currently in the interview stage (${visibleJobs.length}). applyr doesn't track interview dates or times — only that an offer reached this stage.`}
        chips={[
          { label: "waiting", value: visibleJobs.length },
          { label: "success", value: successCount },
        ]}
      />

      <InterviewsToolbar
        filters={filters}
        onFiltersChange={setFilters}
        sortField={sortField}
        sortDirection={sortDirection}
        onSortChange={handleSortChange}
      />

      {visibleJobs.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-border bg-card p-12 text-center">
          <CalendarClock className="size-8 text-muted-foreground" aria-hidden />
          <p className="text-sm text-muted-foreground">
            {filtersActive ? "No offers match these filters." : "No offers currently in interview stage."}
          </p>
        </div>
      ) : (
        <JobList jobs={visibleJobs} thresholds={thresholds} onSelect={setSelectedJobId} />
      )}
    </div>
  );
}
