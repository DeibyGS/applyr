export type AgentId = "recruiter" | "matching" | "cv" | "ats" | "application";

export type AgentStatus =
  | { agentId: "recruiter"; state: "working"; pendingCount: number }
  | { agentId: "recruiter"; state: "idle" }
  | { agentId: "matching"; state: "working"; company: string; compatibilityPct: number }
  | { agentId: "matching"; state: "idle" }
  | { agentId: "cv" | "ats" | "application"; state: "not_connected" };
