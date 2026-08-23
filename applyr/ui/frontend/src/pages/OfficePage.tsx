import { useState } from "react";
import { AgentRow } from "@/features/agents/AgentRow";
import { deriveAgentStatuses } from "@/features/agents/agent-status";
import { IntakeForm } from "@/features/intake/IntakeForm";
import { PendingIntakeList } from "@/features/intake/PendingIntakeList";
import { JobList } from "@/features/jobs/JobList";
import { JobDetail } from "@/features/jobs/JobDetail";
import { useIntakeAndJobs } from "@/hooks/useIntakeAndJobs";
import { useThresholds } from "@/hooks/useThresholds";
import { useSelectedJob } from "@/hooks/useSelectedJob";

export default function OfficePage() {
  const { pendingIntake, jobs, refresh } = useIntakeAndJobs();
  const thresholds = useThresholds();
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const selectedJob = useSelectedJob(selectedJobId);

  const agentStatuses = deriveAgentStatuses(pendingIntake, jobs);

  return (
    <div className="office-bg flex flex-col gap-8 rounded-lg p-6">
      <header className="flex flex-col gap-1">
        <h1 className="font-display text-2xl font-medium text-foreground">applyr</h1>
        <p className="text-sm text-muted-foreground">Your AI recruiting team, working in the open.</p>
      </header>

      <AgentRow statuses={agentStatuses} />

      {selectedJob ? (
        <JobDetail job={selectedJob} thresholds={thresholds} onBack={() => setSelectedJobId(null)} />
      ) : (
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
          <div className="flex flex-col gap-4">
            <IntakeForm onCreated={refresh} />
            <PendingIntakeList rows={pendingIntake} />
          </div>
          <div className="flex flex-col gap-3">
            <h2 className="font-display text-lg font-medium text-foreground">Jobs ({jobs.length})</h2>
            <JobList jobs={jobs} thresholds={thresholds} onSelect={setSelectedJobId} />
          </div>
        </section>
      )}
    </div>
  );
}
