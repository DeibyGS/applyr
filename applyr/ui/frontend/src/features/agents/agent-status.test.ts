import { describe, expect, it } from "vitest";
import type { IntakeRow } from "@/api/intake";
import type { JobSummary } from "@/api/jobs";
import { deriveAgentStatuses } from "./agent-status";

function intakeRow(overrides: Partial<IntakeRow> = {}): IntakeRow {
  return {
    id: 1,
    raw_text: "some offer",
    source_note: null,
    status: "pending",
    offer_id: null,
    created_at: "2026-08-23 10:00:00",
    promoted_at: null,
    ...overrides,
  };
}

function job(overrides: Partial<JobSummary> = {}): JobSummary {
  return {
    id: 1,
    title: "Backend Dev",
    company: "Acme",
    status: "pending",
    compatibility_pct: 80,
    work_mode: null,
    location: null,
    seniority_level: null,
    role_category: null,
    created_at: "2026-08-23 10:00:00",
    date_applied: null,
    pipeline_stage: null,
    ...overrides,
  };
}

describe("deriveAgentStatuses", () => {
  it("always returns exactly 5 agents in a fixed order", () => {
    const result = deriveAgentStatuses([], []);
    expect(result.map((a) => a.agentId)).toEqual([
      "recruiter",
      "matching",
      "cv",
      "ats",
      "application",
    ]);
  });

  it("recruiter is idle when there is no pending intake", () => {
    const [recruiter] = deriveAgentStatuses([], []);
    expect(recruiter).toEqual({ agentId: "recruiter", state: "idle" });
  });

  it("recruiter is working with the real pending count", () => {
    const intake = [intakeRow({ id: 1 }), intakeRow({ id: 2 }), intakeRow({ id: 3, status: "promoted" })];
    const [recruiter] = deriveAgentStatuses(intake, []);
    expect(recruiter).toEqual({ agentId: "recruiter", state: "working", pendingCount: 2 });
  });

  it("matching is idle when there are no pending offers", () => {
    const [, matching] = deriveAgentStatuses([], []);
    expect(matching).toEqual({ agentId: "matching", state: "idle" });
  });

  it("matching shows the real company and score of the most recently created pending offer", () => {
    const jobs = [
      job({ id: 1, company: "Old Co", compatibility_pct: 40, created_at: "2026-08-20 09:00:00" }),
      job({ id: 2, company: "New Co", compatibility_pct: 91, created_at: "2026-08-23 09:00:00" }),
      job({ id: 3, company: "Applied Co", status: "applied", created_at: "2026-08-24 09:00:00" }),
    ];
    const [, matching] = deriveAgentStatuses([], jobs);
    expect(matching).toEqual({
      agentId: "matching",
      state: "working",
      company: "New Co",
      compatibilityPct: 91,
    });
  });

  it("cv, ats, and application are always not_connected regardless of data", () => {
    const jobs = [job(), job({ id: 2 })];
    const intake = [intakeRow()];
    const result = deriveAgentStatuses(intake, jobs);
    const [, , cv, ats, application] = result;
    expect(cv).toEqual({ agentId: "cv", state: "not_connected" });
    expect(ats).toEqual({ agentId: "ats", state: "not_connected" });
    expect(application).toEqual({ agentId: "application", state: "not_connected" });
  });
});
