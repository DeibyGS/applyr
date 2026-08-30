import { useState } from "react";
import { CalendarClock } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
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
  const successCount = jobs.filter((job) => job.status === "offer").length;

  if (selectedJob) {
    return <JobDetail job={selectedJob} thresholds={thresholds} onBack={() => setSelectedJobId(null)} />;
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Interviews"
        description={`Offers currently in the interview stage (${interviews.length}). applyr doesn't track interview dates or times — only that an offer reached this stage.`}
        chips={[
          { label: "waiting", value: interviews.length },
          { label: "success", value: successCount },
        ]}
      />
      {interviews.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-border bg-card p-12 text-center">
          <CalendarClock className="size-8 text-muted-foreground" aria-hidden />
          <p className="text-sm text-muted-foreground">No offers currently in interview stage.</p>
        </div>
      ) : (
        <JobList jobs={interviews} thresholds={thresholds} onSelect={setSelectedJobId} />
      )}
    </div>
  );
}
