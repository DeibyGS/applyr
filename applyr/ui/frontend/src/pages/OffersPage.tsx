import { useState } from "react";
import { useSearchParams } from "react-router";
import { JobList } from "@/features/jobs/JobList";
import { JobDetail } from "@/features/jobs/JobDetail";
import { KanbanBoard } from "@/features/jobs/KanbanBoard";
import { OffersToolbar, type OffersView } from "@/features/jobs/OffersToolbar";
import {
  DEFAULT_FILTERS,
  filterJobs,
  nextSortState,
  sortJobs,
  type SortDirection,
  type SortField,
} from "@/features/jobs/offer-filters";
import { useIntakeAndJobs } from "@/hooks/useIntakeAndJobs";
import { useThresholds } from "@/hooks/useThresholds";
import { useSelectedJob } from "@/hooks/useSelectedJob";

export default function OffersPage() {
  const { jobs } = useIntakeAndJobs();
  const thresholds = useThresholds();
  const [searchParams] = useSearchParams();
  const [selectedJobId, setSelectedJobId] = useState<number | null>(() => {
    const jobId = searchParams.get("jobId");
    return jobId ? Number(jobId) : null;
  });
  const selectedJob = useSelectedJob(selectedJobId);

  const [view, setView] = useState<OffersView>("list");
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [sortField, setSortField] = useState<SortField>("date");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  function handleSortChange(field: SortField) {
    const next = nextSortState(sortField, sortDirection, field);
    setSortField(next.field);
    setSortDirection(next.direction);
  }

  if (selectedJob) {
    return <JobDetail job={selectedJob} thresholds={thresholds} onBack={() => setSelectedJobId(null)} />;
  }

  const visibleJobs = sortJobs(filterJobs(jobs, filters), sortField, sortDirection);
  const hasActiveFilters = filters.status !== null || filters.workMode !== null || filters.minScore > 0;

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-1">
        <h1 className="font-display text-2xl font-medium text-foreground">Offers</h1>
        <p className="text-sm text-muted-foreground">Every offer, filterable and sortable.</p>
      </header>

      <OffersToolbar
        view={view}
        onViewChange={setView}
        filters={filters}
        onFiltersChange={setFilters}
        sortField={sortField}
        sortDirection={sortDirection}
        onSortChange={handleSortChange}
      />

      {view === "kanban" ? (
        <KanbanBoard jobs={visibleJobs} thresholds={thresholds} onSelect={setSelectedJobId} />
      ) : visibleJobs.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {hasActiveFilters ? "No offers match these filters." : "No jobs yet."}
        </p>
      ) : (
        <JobList jobs={visibleJobs} thresholds={thresholds} onSelect={setSelectedJobId} />
      )}
    </div>
  );
}
