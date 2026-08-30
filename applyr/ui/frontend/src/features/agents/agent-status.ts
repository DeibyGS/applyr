import type { IntakeRow } from "@/api/intake";
import type { JobSummary } from "@/api/jobs";
import type { AgentStatus, IntakeQueueItem, JobQueueItem, PipelineStage } from "./types";

const INTAKE_PREVIEW_MAX_CHARS = 120;

function byCreatedAtDesc<T extends { created_at: string }>(a: T, b: T): number {
  return b.created_at.localeCompare(a.created_at);
}

function toIntakeQueueItem(row: IntakeRow): IntakeQueueItem {
  const preview =
    row.raw_text.length > INTAKE_PREVIEW_MAX_CHARS
      ? `${row.raw_text.slice(0, INTAKE_PREVIEW_MAX_CHARS)}…`
      : row.raw_text;
  return { intakeId: row.id, preview, createdAt: row.created_at };
}

function toJobQueueItem(job: JobSummary): JobQueueItem {
  return {
    offerId: job.id,
    company: job.company,
    title: job.title,
    compatibilityPct: job.compatibility_pct,
    createdAt: job.created_at,
  };
}

function pipelineZoneStatus(agentId: "cv" | "ats" | "application", jobs: JobSummary[]): AgentStatus {
  const zoneJobs = jobs
    .filter((job) => {
      if (job.pipeline_stage !== agentId) return false;
      if (agentId === "application" && (job.status === "applied" || job.status === "rejected")) return false;
      return true;
    })
    .sort(byCreatedAtDesc);
  return zoneJobs.length > 0
    ? { agentId, state: "working", count: zoneJobs.length, items: zoneJobs.map(toJobQueueItem), pipelineStage: agentId as PipelineStage }
    : { agentId, state: "idle" };
}

/**
 * Derives every agent's status from real API data only — never simulated.
 * Recruiter/Matching are backed by Slice 1 data (pending intake / pending
 * offers); CV/ATS/Application are backed by ADR-013's `pipeline_stage`
 * column — a job "in" one of those stages means at least one real offer is
 * currently there, same as Matching's own pending-offer count.
 *
 * Each "working" status also carries the full backlog (`items`) behind it,
 * not just the single most-recent one — the agent queue modal reads that to
 * show what else is waiting.
 */
export function deriveAgentStatuses(intake: IntakeRow[], jobs: JobSummary[]): AgentStatus[] {
  const pendingIntake = [...intake.filter((row) => row.status === "pending")].sort(byCreatedAtDesc);
  const pendingJobs = [...jobs.filter((job) => job.status === "pending")].sort(byCreatedAtDesc);
  const mostRecentPendingJob = pendingJobs[0];

  const recruiter: AgentStatus =
    pendingIntake.length > 0
      ? {
          agentId: "recruiter",
          state: "working",
          pendingCount: pendingIntake.length,
          items: pendingIntake.map(toIntakeQueueItem),
          pipelineStage: undefined,
        }
      : { agentId: "recruiter", state: "idle" };

  const matching: AgentStatus = mostRecentPendingJob
    ? {
        agentId: "matching",
        state: "working",
        company: mostRecentPendingJob.company,
        compatibilityPct: mostRecentPendingJob.compatibility_pct,
        items: pendingJobs.map(toJobQueueItem),
        pipelineStage: mostRecentPendingJob.pipeline_stage ?? undefined,
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
