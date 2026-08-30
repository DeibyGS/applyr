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

export function formatStatusLabel(status: string): string {
  return status
    .split("_")
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

/**
 * Status badge accent — deliberately restrained. "offer" is the one status
 * that deserves --highlight (reserved for high-value moments, see
 * index.css); rejected/discarded are muted since they're a closed loop, not
 * something to draw the eye to. Everything else stays neutral.
 */
export function statusAccentClass(status: string): string {
  if (status === "offer") return "border-highlight/40 bg-highlight/10 text-highlight";
  if (status === "rejected" || status === "discarded") return "border-border text-muted-foreground/70";
  return "border-border text-foreground";
}

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
