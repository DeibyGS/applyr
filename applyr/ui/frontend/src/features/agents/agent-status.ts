import type { IntakeRow } from "@/api/intake";
import type { JobSummary } from "@/api/jobs";
import type { AgentStatus } from "./types";

/**
 * Derives every agent's status from real API data only — never simulated.
 * Recruiter/Matching are backed by Slice 1 data; CV/ATS/Application have no
 * persisted state yet (docs/visual-ui/AGENTS.md), so they always report
 * "not_connected" rather than an invented activity.
 */
export function deriveAgentStatuses(intake: IntakeRow[], jobs: JobSummary[]): AgentStatus[] {
  const pendingIntake = intake.filter((row) => row.status === "pending");
  const pendingJobs = jobs.filter((job) => job.status === "pending");
  const mostRecentPendingJob = [...pendingJobs].sort((a, b) =>
    b.created_at.localeCompare(a.created_at)
  )[0];

  const recruiter: AgentStatus =
    pendingIntake.length > 0
      ? { agentId: "recruiter", state: "working", pendingCount: pendingIntake.length }
      : { agentId: "recruiter", state: "idle" };

  const matching: AgentStatus = mostRecentPendingJob
    ? {
        agentId: "matching",
        state: "working",
        company: mostRecentPendingJob.company,
        compatibilityPct: mostRecentPendingJob.compatibility_pct,
      }
    : { agentId: "matching", state: "idle" };

  return [
    recruiter,
    matching,
    { agentId: "cv", state: "not_connected" },
    { agentId: "ats", state: "not_connected" },
    { agentId: "application", state: "not_connected" },
  ];
}
