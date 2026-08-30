import { useState } from "react";
import { Popover as PopoverPrimitive } from "radix-ui";
import { ListFilter } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ActiveFilterChips, FilterSelect, SegmentedControl } from "@/components/ui/filter-bar";
import { formatStatusLabel } from "@/features/jobs/group-by-status";
import {
  DEFAULT_ANALYTICS_FILTERS,
  describeActiveFilters,
  hasActiveFilters,
  type AnalyticsFilters,
  type DateRangePreset,
} from "./analytics-filters";

// Mirrors applyr's real VALID_* enums (applyr/db.py) — hardcoded per the
// same precedent as features/jobs/group-by-status.ts's OFFER_STATUSES.
const WORK_MODES = ["remote", "hybrid", "onsite"] as const;
const CHANNELS = ["linkedin_easy", "linkedin_direct", "email", "portal", "referral", "other"] as const;
const SENIORITY_LEVELS = ["trainee", "entry_level", "junior", "mid", "senior", "lead", "director"] as const;
const ROLE_CATEGORIES = [
  "backend",
  "frontend",
  "fullstack",
  "ai",
  "devops",
  "data",
  "mobile",
  "qa",
  "other",
] as const;

const DATE_RANGE_OPTIONS: { value: DateRangePreset; label: string }[] = [
  { value: "7d", label: "7d" },
  { value: "30d", label: "30d" },
  { value: "90d", label: "90d" },
  { value: "all", label: "All" },
];

// Converts enum-like arrays to filter options with "All" fallback + formatted labels.
// Avoids repeating the .map(x => ({ value: x, label: formatStatusLabel(x) })) pattern.
const toFilterOptions = <T extends string>(items: readonly T[]): { value: T | "all"; label: string }[] => [
  { value: "all", label: "All" },
  ...items.map((item) => ({ value: item, label: formatStatusLabel(item) })),
];

type AnalyticsFilterBarProps = {
  filters: AnalyticsFilters;
  onFiltersChange: (filters: AnalyticsFilters) => void;
};

export function AnalyticsFilterBar({ filters, onFiltersChange }: AnalyticsFilterBarProps) {
  const [open, setOpen] = useState(false);

  const chips = describeActiveFilters(filters, formatStatusLabel).map((chip) => ({
    ...chip,
    onRemove: () =>
      onFiltersChange({
        ...filters,
        ...(chip.key === "dateRange" && { dateRange: "all" as const }),
        ...(chip.key === "workMode" && { workMode: null }),
        ...(chip.key === "canal" && { canal: null }),
        ...(chip.key === "seniorityLevel" && { seniorityLevel: null }),
        ...(chip.key === "roleCategory" && { roleCategory: null }),
      }),
  }));

  return (
    <PopoverPrimitive.Root open={open} onOpenChange={setOpen}>
      <div className="flex flex-wrap items-center gap-2">
        <PopoverPrimitive.Trigger asChild>
          <Button variant="outline" size="sm">
            <ListFilter className="size-4 text-muted-foreground" aria-hidden />
            Filters
          </Button>
        </PopoverPrimitive.Trigger>

        {/* Chips substitute for the panel while it's closed — once it's open,
            the controls inside already show every active value. */}
        {!open && hasActiveFilters(filters) && (
          <ActiveFilterChips
            chips={chips}
            onClearAll={() => onFiltersChange(DEFAULT_ANALYTICS_FILTERS)}
            className="border-t-0 pt-0"
          />
        )}
      </div>

      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align="start"
          sideOffset={8}
          className="z-50 w-max rounded-xl border border-border bg-card p-4 text-card-foreground shadow-md outline-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95"
        >
          <div className="flex flex-wrap items-end gap-6">
            {/* Cluster A: when + where you worked. Tight gap-3 signals these two
                belong together; the gap-6 above and the divider below separate
                this cluster from Cluster B (refactoring-ui: proximity implies
                relationship, not color or decoration). */}
            <div className="flex flex-wrap items-end gap-3">
              <SegmentedControl
                aria-label="Date range"
                value={filters.dateRange}
                onChange={(dateRange) => onFiltersChange({ ...filters, dateRange })}
                options={DATE_RANGE_OPTIONS}
              />

              <SegmentedControl
                aria-label="Work mode"
                value={filters.workMode ?? "all"}
                onChange={(mode) => onFiltersChange({ ...filters, workMode: mode === "all" ? null : mode })}
                options={toFilterOptions(WORK_MODES)}
              />
            </div>

            <div className="flex flex-wrap items-end gap-3 border-l border-border pl-6">
              <FilterSelect
                label="Canal"
                value={filters.canal ?? "all"}
                onChange={(canal) => onFiltersChange({ ...filters, canal: canal === "all" ? null : canal })}
                options={toFilterOptions(CHANNELS)}
              />

              <FilterSelect
                label="Seniority"
                value={filters.seniorityLevel ?? "all"}
                onChange={(level) => onFiltersChange({ ...filters, seniorityLevel: level === "all" ? null : level })}
                options={toFilterOptions(SENIORITY_LEVELS)}
              />

              <FilterSelect
                label="Role category"
                value={filters.roleCategory ?? "all"}
                onChange={(role) => onFiltersChange({ ...filters, roleCategory: role === "all" ? null : role })}
                options={toFilterOptions(ROLE_CATEGORIES)}
              />
            </div>
          </div>

          {hasActiveFilters(filters) && (
            <ActiveFilterChips
              chips={chips}
              onClearAll={() => onFiltersChange(DEFAULT_ANALYTICS_FILTERS)}
              className="mt-4"
            />
          )}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}
