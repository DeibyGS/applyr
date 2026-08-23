import { AgentCard } from "@/features/agents/AgentCard";
import { deriveAgentStatuses } from "@/features/agents/agent-status";
import { useIntakeAndJobs } from "@/hooks/useIntakeAndJobs";

export default function AgentsPage() {
  const { pendingIntake, jobs } = useIntakeAndJobs();
  const agentStatuses = deriveAgentStatuses(pendingIntake, jobs);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="font-display text-2xl font-medium text-foreground">Agents</h1>
        <p className="text-sm text-muted-foreground">Your AI recruiting team, one card each.</p>
      </header>
      <div className="flex flex-wrap gap-6">
        {agentStatuses.map((status) => (
          <AgentCard key={status.agentId} status={status} variant="detailed" />
        ))}
      </div>
    </div>
  );
}
