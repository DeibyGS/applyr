import { deriveAgentStatuses } from "@/features/agents/agent-status";
import { IntakeForm } from "@/features/intake/IntakeForm";
import { PendingIntakeList } from "@/features/intake/PendingIntakeList";
import { OfficeScene } from "@/features/office-scene/OfficeScene";
import { useIntakeAndJobs } from "@/hooks/useIntakeAndJobs";

export default function OfficePage() {
  const { pendingIntake, jobs, loaded, refresh } = useIntakeAndJobs();

  const agentStatuses = deriveAgentStatuses(pendingIntake, jobs);

  return (
    <div className="office-bg flex flex-col gap-8 rounded-lg p-6">
      <header className="flex flex-col gap-1">
        <h1 className="font-display text-2xl font-medium text-foreground">applyr</h1>
        <p className="text-sm text-muted-foreground">Your AI recruiting team, working in the open.</p>
      </header>

      <OfficeScene statuses={agentStatuses} jobs={jobs} jobsLoaded={loaded} />

      <section className="flex flex-col gap-4 lg:max-w-md">
        <IntakeForm onCreated={refresh} />
        <PendingIntakeList rows={pendingIntake} />
      </section>
    </div>
  );
}
