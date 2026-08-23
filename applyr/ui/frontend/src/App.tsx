import { useEffect, useState } from "react";
import { AgentRow } from "@/features/agents/AgentRow";
import { deriveAgentStatuses } from "@/features/agents/agent-status";
import { IntakeForm } from "@/features/intake/IntakeForm";
import { PendingIntakeList } from "@/features/intake/PendingIntakeList";
import { JobList } from "@/features/jobs/JobList";
import { JobDetail } from "@/features/jobs/JobDetail";
import { listIntake, type IntakeRow } from "@/api/intake";
import { listJobs, getJob, type JobSummary, type JobDetail as JobDetailType } from "@/api/jobs";
import { getConfig, type Thresholds } from "@/api/config";

const POLL_INTERVAL_MS = 3000;
const DEFAULT_THRESHOLDS: Thresholds = { threshold_apply: 80, threshold_maybe: 60 };

export default function App() {
  const [pendingIntake, setPendingIntake] = useState<IntakeRow[]>([]);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [thresholds, setThresholds] = useState<Thresholds>(DEFAULT_THRESHOLDS);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [selectedJob, setSelectedJob] = useState<JobDetailType | null>(null);

  async function refresh() {
    const [intakeRows, jobRows] = await Promise.all([listIntake("pending"), listJobs()]);
    setPendingIntake(intakeRows);
    setJobs(jobRows);
  }

  useEffect(() => {
    getConfig().then(setThresholds).catch(() => setThresholds(DEFAULT_THRESHOLDS));
    refresh();
    const id = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (selectedJobId === null) {
      setSelectedJob(null);
      return;
    }
    getJob(selectedJobId).then(setSelectedJob);
  }, [selectedJobId]);

  const agentStatuses = deriveAgentStatuses(pendingIntake, jobs);

  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-8 p-6">
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
    </main>
  );
}
