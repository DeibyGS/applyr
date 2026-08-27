import { deriveAgentStatuses } from "@/features/agents/agent-status";
import { AgentFlowDiagram } from "@/features/agents/AgentFlowDiagram";
import { IntakePanel } from "@/features/office/IntakePanel";
import { OfficeHeader } from "@/features/office/OfficeHeader";
import { deriveOfficeStats } from "@/features/office/office-stats";
import { useIntakeAndJobs } from "@/hooks/useIntakeAndJobs";

export default function OfficePage() {
  const { pendingIntake, jobs, refresh } = useIntakeAndJobs();

  const agentStatuses = deriveAgentStatuses(pendingIntake, jobs);
  const stats = deriveOfficeStats(pendingIntake, agentStatuses);

  return (
    <div className="office-bg relative flex flex-col gap-6 rounded-lg p-6">
      <OfficeHeader stats={stats} />
      <AgentFlowDiagram statuses={agentStatuses} />
      <IntakePanel rows={pendingIntake} onCreated={refresh} />
    </div>
  );
}
