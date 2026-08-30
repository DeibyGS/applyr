import type { JobSummary } from "@/api/jobs";

export type SortField = "date" | "score";
export type SortDirection = "asc" | "desc";

export type OfferFilters = {
  status: string | null;
  workMode: string | null;
  minScore: number;
};

export const DEFAULT_FILTERS: OfferFilters = { status: null, workMode: null, minScore: 0 };

export function hasActiveFilters(filters: OfferFilters): boolean {
  return filters.status !== null || filters.workMode !== null || filters.minScore > 0;
}

export type ActiveFilterChip = { key: "status" | "workMode" | "minScore"; label: string };

/**
 * Describes each active filter as a removable chip. Formatting (e.g. status
 * label casing) is the caller's job — this only decides which chips exist.
 */
export function describeActiveFilters(
  filters: OfferFilters,
  formatStatus: (status: string) => string
): ActiveFilterChip[] {
  const chips: ActiveFilterChip[] = [];
  if (filters.status !== null) {
    chips.push({ key: "status", label: `Status: ${formatStatus(filters.status)}` });
  }
  if (filters.workMode !== null) {
    chips.push({ key: "workMode", label: `Work mode: ${filters.workMode}` });
  }
  if (filters.minScore > 0) {
    chips.push({ key: "minScore", label: `Min score: ${filters.minScore}%` });
  }
  return chips;
}

export function filterJobs(jobs: JobSummary[], filters: OfferFilters): JobSummary[] {
  return jobs.filter((job) => {
    if (filters.status && job.status !== filters.status) return false;
    if (filters.workMode && job.work_mode !== filters.workMode) return false;
    if (filters.minScore > 0 && job.compatibility_pct < filters.minScore) return false;
    return true;
  });
}

export function nextSortState(
  currentField: SortField,
  currentDirection: SortDirection,
  clickedField: SortField
): { field: SortField; direction: SortDirection } {
  if (clickedField === currentField) {
    return { field: currentField, direction: currentDirection === "desc" ? "asc" : "desc" };
  }
  return { field: clickedField, direction: "desc" };
}

export function sortJobs(jobs: JobSummary[], field: SortField, direction: SortDirection): JobSummary[] {
  const sorted = [...jobs].sort((a, b) =>
    field === "score"
      ? a.compatibility_pct - b.compatibility_pct
      : a.created_at.localeCompare(b.created_at)
  );
  return direction === "desc" ? sorted.reverse() : sorted;
}
