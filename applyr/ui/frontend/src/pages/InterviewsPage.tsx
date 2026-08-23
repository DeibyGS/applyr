import { useState } from "react";
import { JobList } from "@/features/jobs/JobList";
import { JobDetail } from "@/features/jobs/JobDetail";
import { filterInProcess } from "@/features/jobs/filter-in-process";
import { useIntakeAndJobs } from "@/hooks/useIntakeAndJobs";
import { useThresholds } from "@/hooks/useThresholds";
import { useSelectedJob } from "@/hooks/useSelectedJob";

export default function InterviewsPage() {
  const { jobs } = useIntakeAndJobs();
  const thresholds = useThresholds();
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const selectedJob = useSelectedJob(selectedJobId);

  const interviews = filterInProcess(jobs);

  if (selectedJob) {
    return <JobDetail job={selectedJob} thresholds={thresholds} onBack={() => setSelectedJobId(null)} />;
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-1">
        <h1 className="font-display text-2xl font-medium text-foreground">Interviews</h1>
        <p className="text-sm text-muted-foreground">
          Offers currently in the interview stage ({interviews.length}). applyr doesn't
          track interview dates or times — only that an offer reached this stage.
        </p>
      </header>
      {interviews.length === 0 ? (
        <p className="text-sm text-muted-foreground">No offers currently in interview stage.</p>
      ) : (
        <JobList jobs={interviews} thresholds={thresholds} onSelect={setSelectedJobId} />
      )}
    </div>
  );
}
