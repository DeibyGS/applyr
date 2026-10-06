import { useEffect, useState } from "react";
import { listIntake, type IntakeRow } from "@/api/intake";
import { listJobs, type JobSummary } from "@/api/jobs";
import { useApplyrEvents } from "@/hooks/useApplyrEvents";

const POLL_INTERVAL_MS = 3000;

/**
 * Shared polling source for pending intake + jobs — used by every page that
 * needs live data (Office, Agents, Archive). One fetch cycle, not one per
 * page, so they never drift out of sync with each other.
 */
export function useIntakeAndJobs() {
  const [pendingIntake, setPendingIntake] = useState<IntakeRow[]>([]);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  // Distinct from `jobs.length > 0` — a fresh install with zero offers must
  // still report "loaded" after its first real fetch, or a consumer gating
  // a one-time action on it would wait forever (code-review finding).
  const [loaded, setLoaded] = useState(false);

  async function refresh() {
    const [intakeRows, jobRows] = await Promise.all([listIntake("pending"), listJobs()]);
    setPendingIntake(intakeRows);
    setJobs(jobRows);
    setLoaded(true);
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  // ADR-014: refresh immediately on a job state transition instead of
  // waiting up to POLL_INTERVAL_MS. The poll above stays as a recovery net
  // (page reload, a missed SSE event) — this just makes live updates feel
  // instant instead of laggy for the one thing that changes fast: intake
  // rows moving through the pipeline.
  const { subscribe, unsubscribe } = useApplyrEvents({ autoConnect: true });
  useEffect(() => {
    const id = subscribe(
      () => refresh(),
      // ApplyrEvent only models agent/handoff/pipeline events; the backend
      // also sends this flat job event over the same stream (no agent_id),
      // so widen to a plain string before comparing.
      (event) => (event as { type: string }).type === "job.state_changed",
    );
    return () => unsubscribe(id);
  }, [subscribe, unsubscribe]);

  return { pendingIntake, jobs, loaded, refresh };
}
