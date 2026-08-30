export type DateRangePreset = "7d" | "30d" | "90d" | "all";

export type AnalyticsFilters = {
  dateRange: DateRangePreset;
  workMode: string | null;
  canal: string | null;
  seniorityLevel: string | null;
  roleCategory: string | null;
};

export const DEFAULT_ANALYTICS_FILTERS: AnalyticsFilters = {
  dateRange: "all",
  workMode: null,
  canal: null,
  seniorityLevel: null,
  roleCategory: null,
};

export type AnalyticsQueryParams = {
  from?: string;
  to?: string;
  work_mode?: string;
  canal?: string;
  seniority_level?: string;
  role_category?: string;
};

const PRESET_DAYS: Record<Exclude<DateRangePreset, "all">, number> = {
  "7d": 7,
  "30d": 30,
  "90d": 90,
};

/**
 * Derives from/to ISO date strings (YYYY-MM-DD) for a preset. "all" omits
 * both entirely rather than sending a wide literal range — the backend's
 * date filter is only applied when the param is present at all.
 */
export function dateRangeFromPreset(
  preset: DateRangePreset,
  now: Date = new Date()
): { from?: string; to?: string } {
  if (preset === "all") return {};
  const to = now.toISOString().slice(0, 10);
  const from = new Date(now);
  from.setDate(from.getDate() - PRESET_DAYS[preset]);
  return { from: from.toISOString().slice(0, 10), to };
}

/** Converts filter state into the query params `getStats`/`getTrends` send. */
export function toQueryParams(filters: AnalyticsFilters): AnalyticsQueryParams {
  const { from, to } = dateRangeFromPreset(filters.dateRange);
  return {
    ...(from && { from }),
    ...(to && { to }),
    ...(filters.workMode && { work_mode: filters.workMode }),
    ...(filters.canal && { canal: filters.canal }),
    ...(filters.seniorityLevel && { seniority_level: filters.seniorityLevel }),
    ...(filters.roleCategory && { role_category: filters.roleCategory }),
  };
}

export function hasActiveFilters(filters: AnalyticsFilters): boolean {
  return (
    filters.dateRange !== "all" ||
    filters.workMode !== null ||
    filters.canal !== null ||
    filters.seniorityLevel !== null ||
    filters.roleCategory !== null
  );
}

export type ActiveFilterChip = {
  key: "dateRange" | "workMode" | "canal" | "seniorityLevel" | "roleCategory";
  label: string;
};

const DATE_RANGE_LABELS: Record<DateRangePreset, string> = {
  "7d": "Last 7 days",
  "30d": "Last 30 days",
  "90d": "Last 90 days",
  all: "All time",
};

/**
 * Describes each active filter as a removable chip. Formatting for enum
 * values (work mode, canal, etc.) is the caller's job — this only decides
 * which chips exist, mirroring `features/jobs/offer-filters.ts`.
 */
export function describeActiveFilters(
  filters: AnalyticsFilters,
  formatLabel: (value: string) => string
): ActiveFilterChip[] {
  const chips: ActiveFilterChip[] = [];
  if (filters.dateRange !== "all") {
    chips.push({ key: "dateRange", label: `Date: ${DATE_RANGE_LABELS[filters.dateRange]}` });
  }
  if (filters.workMode !== null) {
    chips.push({ key: "workMode", label: `Work mode: ${formatLabel(filters.workMode)}` });
  }
  if (filters.canal !== null) {
    chips.push({ key: "canal", label: `Canal: ${formatLabel(filters.canal)}` });
  }
  if (filters.seniorityLevel !== null) {
    chips.push({ key: "seniorityLevel", label: `Seniority: ${formatLabel(filters.seniorityLevel)}` });
  }
  if (filters.roleCategory !== null) {
    chips.push({ key: "roleCategory", label: `Role: ${formatLabel(filters.roleCategory)}` });
  }
  return chips;
}
