export type AgentId = "recruiter" | "matching" | "cv" | "ats" | "application";

// ADR-013 gave cv/ats/application real backing data (offers.pipeline_stage),
// so — like recruiter/matching before them — they now report working/idle
// from that real state instead of a permanent "not_connected" placeholder.
export type AgentStatus =
  | { agentId: "recruiter"; state: "working"; pendingCount: number }
  | { agentId: "recruiter"; state: "idle" }
  | { agentId: "matching"; state: "working"; company: string; compatibilityPct: number }
  | { agentId: "matching"; state: "idle" }
  | { agentId: "cv" | "ats" | "application"; state: "working"; count: number }
  | { agentId: "cv" | "ats" | "application"; state: "idle" };
