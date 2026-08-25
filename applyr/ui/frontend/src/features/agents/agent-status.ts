import type { IntakeRow } from "@/api/intake";
import type { JobSummary } from "@/api/jobs";
import type { AgentStatus } from "./types";

function pipelineZoneStatus(agentId: "cv" | "ats" | "application", jobs: JobSummary[]): AgentStatus {
  const count = jobs.filter((job) => job.pipeline_stage === agentId).length;
  return count > 0 ? { agentId, state: "working", count } : { agentId, state: "idle" };
}

/**
 * Derives every agent's status from real API data only — never simulated.
 * Recruiter/Matching are backed by Slice 1 data (pending intake / pending
 * offers); CV/ATS/Application are backed by ADR-013's `pipeline_stage`
 * column — a job "in" one of those stages means at least one real offer is
 * currently there, same as Matching's own pending-offer count.
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
    pipelineZoneStatus("cv", jobs),
    pipelineZoneStatus("ats", jobs),
    pipelineZoneStatus("application", jobs),
  ];
}
