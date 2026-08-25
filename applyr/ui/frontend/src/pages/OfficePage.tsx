import { deriveAgentStatuses } from "@/features/agents/agent-status";
import { IntakeForm } from "@/features/intake/IntakeForm";
import { PendingIntakeList } from "@/features/intake/PendingIntakeList";
import { OfficeScene } from "@/features/office-scene/OfficeScene";
import { useIntakeAndJobs } from "@/hooks/useIntakeAndJobs";

export default function OfficePage() {
  const { pendingIntake, jobs, loaded, refresh } = useIntakeAndJobs();

  const agentStatuses = deriveAgentStatuses(pendingIntake, jobs);

  return (
    <div className="office-bg grid grid-cols-1 gap-6 rounded-lg p-6">
      <OfficeScene statuses={agentStatuses} jobs={jobs} jobsLoaded={loaded} />
      <section className="col-span-1 lg:col-span-2 p-4 bg-white/80 rounded-xl backdrop-blur-md max-w-sm">
        <IntakeForm onCreated={refresh} />
        <PendingIntakeList rows={pendingIntake} />
      </section>
    </div>
  );
}
