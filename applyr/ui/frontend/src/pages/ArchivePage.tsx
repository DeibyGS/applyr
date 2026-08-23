import { useState } from "react";
import { JobList } from "@/features/jobs/JobList";
import { JobDetail } from "@/features/jobs/JobDetail";
import { groupByStatus, OFFER_STATUSES } from "@/features/jobs/group-by-status";
import { useIntakeAndJobs } from "@/hooks/useIntakeAndJobs";
import { useThresholds } from "@/hooks/useThresholds";
import { useSelectedJob } from "@/hooks/useSelectedJob";

const STATUS_LABELS: Record<(typeof OFFER_STATUSES)[number], string> = {
  pending: "Pending",
  applied: "Applied",
  waiting: "Waiting",
  in_process: "In Process",
  rejected: "Rejected",
  discarded: "Discarded",
  offer: "Offer",
};

export default function ArchivePage() {
  const { jobs } = useIntakeAndJobs();
  const thresholds = useThresholds();
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const selectedJob = useSelectedJob(selectedJobId);

  const grouped = groupByStatus(jobs);

  if (selectedJob) {
    return <JobDetail job={selectedJob} thresholds={thresholds} onBack={() => setSelectedJobId(null)} />;
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-1">
        <h1 className="font-display text-2xl font-medium text-foreground">Archive</h1>
        <p className="text-sm text-muted-foreground">Every offer, grouped by its real status.</p>
      </header>
      {OFFER_STATUSES.map((status) => (
        <section key={status} className="flex flex-col gap-3">
          <h2 className="font-display text-lg font-medium text-foreground">
            {STATUS_LABELS[status]} ({grouped[status].length})
          </h2>
          <JobList jobs={grouped[status]} thresholds={thresholds} onSelect={setSelectedJobId} />
        </section>
      ))}
    </div>
  );
}
