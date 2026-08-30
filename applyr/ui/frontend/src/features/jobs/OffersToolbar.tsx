import { LayoutGrid, ListFilter, Rows3 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { ActiveFilterChips, FilterGroup, FilterPill, SegmentedControl } from "@/components/ui/filter-bar";
import { OFFER_STATUSES, formatStatusLabel } from "./group-by-status";
import {
  DEFAULT_FILTERS,
  describeActiveFilters,
  hasActiveFilters,
  type OfferFilters,
  type SortDirection,
  type SortField,
} from "./offer-filters";

const WORK_MODES = ["remote", "hybrid", "onsite"] as const;

export type OffersView = "list" | "kanban";

type OffersToolbarProps = {
  view: OffersView;
  onViewChange: (view: OffersView) => void;
  filters: OfferFilters;
  onFiltersChange: (filters: OfferFilters) => void;
  sortField: SortField;
  sortDirection: SortDirection;
  onSortChange: (field: SortField) => void;
};

export function OffersToolbar({
  view,
  onViewChange,
  filters,
  onFiltersChange,
  sortField,
  sortDirection,
  onSortChange,
}: OffersToolbarProps) {
  const sortArrow = sortDirection === "desc" ? "↓" : "↑";
  const chips = describeActiveFilters(filters, formatStatusLabel).map((chip) => ({
    ...chip,
    onRemove: () =>
      onFiltersChange({
        ...filters,
        ...(chip.key === "status" && { status: null }),
        ...(chip.key === "workMode" && { workMode: null }),
        ...(chip.key === "minScore" && { minScore: 0 }),
      }),
  }));

  return (
    <Card className="gap-4 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-medium text-foreground">
          <ListFilter className="size-4 text-muted-foreground" aria-hidden />
          Filters
        </div>

        <div className="flex items-center gap-4">
          <SegmentedControl
            aria-label="View"
            value={view}
            onChange={onViewChange}
            options={[
              { value: "list", label: "List", icon: <Rows3 className="size-3.5" aria-hidden /> },
              { value: "kanban", label: "Kanban", icon: <LayoutGrid className="size-3.5" aria-hidden /> },
            ]}
          />

          <div className="flex items-center gap-1.5">
            <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Sort</span>
            <FilterPill active={sortField === "date"} onClick={() => onSortChange("date")}>
              Date{sortField === "date" ? ` ${sortArrow}` : ""}
            </FilterPill>
            <FilterPill active={sortField === "score"} onClick={() => onSortChange("score")}>
              Score{sortField === "score" ? ` ${sortArrow}` : ""}
            </FilterPill>
          </div>
        </div>
      </div>

      <FilterGroup label="Status">
        <SegmentedControl
          aria-label="Status"
          value={filters.status ?? "all"}
          onChange={(status) => onFiltersChange({ ...filters, status: status === "all" ? null : status })}
          options={[
            { value: "all", label: "All" },
            ...OFFER_STATUSES.map((status) => ({ value: status, label: formatStatusLabel(status) })),
          ]}
        />
      </FilterGroup>

      <FilterGroup label="Work mode">
        <SegmentedControl
          aria-label="Work mode"
          value={filters.workMode ?? "all"}
          onChange={(mode) => onFiltersChange({ ...filters, workMode: mode === "all" ? null : mode })}
          options={[{ value: "all", label: "All" }, ...WORK_MODES.map((mode) => ({ value: mode, label: mode }))]}
        />
      </FilterGroup>

      <div className="flex flex-col gap-2">
        <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Min score {filters.minScore > 0 ? `— ${filters.minScore}%` : ""}
        </span>
        <Slider
          aria-label="Minimum compatibility score"
          value={[filters.minScore]}
          onValueChange={([value]) => onFiltersChange({ ...filters, minScore: value })}
          min={0}
          max={100}
          step={5}
          className="max-w-xs"
        />
      </div>

      {hasActiveFilters(filters) && (
        <ActiveFilterChips chips={chips} onClearAll={() => onFiltersChange(DEFAULT_FILTERS)} />
      )}
    </Card>
  );
}
