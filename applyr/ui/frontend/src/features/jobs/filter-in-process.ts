import type { JobSummary } from "@/api/jobs";

// "in interview stage" means exactly status == 'in_process' — the same single
// value applyr's CLI funnel (cmd_stats) already counts as `interview`. applyr
// has no interview date/time field, so this is the only honest signal
// available; never broadened to include e.g. 'waiting'.
export function filterInProcess(jobs: JobSummary[]): JobSummary[] {
  return jobs.filter((job) => job.status === "in_process");
}
