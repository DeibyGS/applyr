import { JobCard } from "./JobCard";
import type { JobSummary } from "@/api/jobs";
import type { Thresholds } from "@/api/config";

type JobListProps = {
  jobs: JobSummary[];
  thresholds: Thresholds;
  onSelect: (id: number) => void;
};

export function JobList({ jobs, thresholds, onSelect }: JobListProps) {
  if (jobs.length === 0) {
    return <p className="text-sm text-muted-foreground">No jobs yet.</p>;
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {jobs.map((job) => (
        <JobCard key={job.id} job={job} thresholds={thresholds} onSelect={onSelect} />
      ))}
    </div>
  );
}
