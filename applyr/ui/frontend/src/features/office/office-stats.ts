import type { AgentStatus } from "@/features/agents/types";
import type { IntakeRow } from "@/api/intake";

export type OfficeStats = {
  pendingCount: number;
  activeAgentCount: number;
};

export function deriveOfficeStats(pendingIntake: IntakeRow[], agentStatuses: AgentStatus[]): OfficeStats {
  return {
    pendingCount: pendingIntake.length,
    activeAgentCount: agentStatuses.filter((agent) => agent.state === "working").length,
  };
}
