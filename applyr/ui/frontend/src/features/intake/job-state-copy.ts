import type { JobState } from "@/api/intake";

/**
 * ADR-014: short status copy + badge variant per pipeline job state.
 * `duplicate` and `failed` are terminal-but-distinct — a duplicate is a
 * correct outcome (nothing to retry), a failure is not (Retry button shows).
 */
export const JOB_STATE_LABEL: Record<JobState, string> = {
  queued: "Queued",
  structuring: "Reading details…",
  deduping: "Checking for duplicates…",
  duplicate: "Already tracked",
  pending_agent: "Waiting for your agent",
  ready: "Added",
  failed: "Failed",
};

export const JOB_STATE_VARIANT: Record<JobState, "default" | "secondary" | "destructive" | "outline"> = {
  queued: "outline",
  structuring: "outline",
  deduping: "outline",
  duplicate: "secondary",
  pending_agent: "default",
  ready: "secondary",
  failed: "destructive",
};
