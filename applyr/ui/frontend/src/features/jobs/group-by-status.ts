import type { JobSummary } from "@/api/jobs";

/**
 * Mirrors applyr's real VALID_STATUSES enum (applyr/db.py). Hardcoded here
 * rather than fetched, per Slice 3's explicit assumption — the accompanying
 * test asserts this exact set so Python/TS drift fails loudly instead of
 * silently dropping a status section.
 */
export const OFFER_STATUSES = [
  "pending",
  "applied",
  "waiting",
  "in_process",
  "rejected",
  "discarded",
  "offer",
] as const;

export type OfferStatus = (typeof OFFER_STATUSES)[number];

export function groupByStatus(jobs: JobSummary[]): Record<OfferStatus, JobSummary[]> {
  const grouped = Object.fromEntries(
    OFFER_STATUSES.map((status) => [status, [] as JobSummary[]])
  ) as Record<OfferStatus, JobSummary[]>;

  for (const job of jobs) {
    const status = job.status as OfferStatus;
    if (status in grouped) {
      grouped[status].push(job);
    }
  }

  return grouped;
}
