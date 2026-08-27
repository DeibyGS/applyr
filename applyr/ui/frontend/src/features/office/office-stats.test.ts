import { describe, expect, it } from "vitest";
import { deriveOfficeStats } from "./office-stats";
import type { AgentStatus } from "@/features/agents/types";
import type { IntakeRow } from "@/api/intake";

function intakeRow(id: number): IntakeRow {
  return {
    id,
    raw_text: "text",
    source_note: null,
    status: "pending",
    offer_id: null,
    created_at: "2026-08-28T00:00:00Z",
    promoted_at: null,
  };
}

describe("deriveOfficeStats", () => {
  it("returns zero counts when nothing is pending or working", () => {
    const idleAgents: AgentStatus[] = [
      { agentId: "recruiter", state: "idle" },
      { agentId: "matching", state: "idle" },
    ];

    expect(deriveOfficeStats([], idleAgents)).toEqual({ pendingCount: 0, activeAgentCount: 0 });
  });

  it("counts pending intake rows regardless of agent state", () => {
    const idleAgents: AgentStatus[] = [{ agentId: "recruiter", state: "idle" }];

    expect(deriveOfficeStats([intakeRow(1), intakeRow(2)], idleAgents)).toEqual({
      pendingCount: 2,
      activeAgentCount: 0,
    });
  });

  it("counts only agents in the working state", () => {
    const agents: AgentStatus[] = [
      { agentId: "recruiter", state: "working", pendingCount: 1, items: [] },
      { agentId: "matching", state: "idle" },
      { agentId: "cv", state: "working", count: 1, items: [] },
    ];

    expect(deriveOfficeStats([intakeRow(1)], agents)).toEqual({ pendingCount: 1, activeAgentCount: 2 });
  });
});
