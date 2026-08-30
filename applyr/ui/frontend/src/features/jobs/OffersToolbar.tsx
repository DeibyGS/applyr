import { useState } from "react";
import { Popover as PopoverPrimitive } from "radix-ui";
import { LayoutGrid, ListFilter, Rows3 } from "lucide-react";
import { Button } from "@/components/ui/button";
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
  const [open, setOpen] = useState(false);
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
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PopoverPrimitive.Root open={open} onOpenChange={setOpen}>
          <div className="flex flex-wrap items-center gap-2">
            <PopoverPrimitive.Trigger asChild>
              <Button variant="outline" size="sm">
                <ListFilter className="size-4 text-muted-foreground" aria-hidden />
                Filters
              </Button>
            </PopoverPrimitive.Trigger>

            {!open && hasActiveFilters(filters) && (
              <ActiveFilterChips
                chips={chips}
                onClearAll={() => onFiltersChange(DEFAULT_FILTERS)}
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
              </div>

              <div className="flex flex-col gap-2 border-t border-border pt-3 mt-3">
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
                <ActiveFilterChips
                  chips={chips}
                  onClearAll={() => onFiltersChange(DEFAULT_FILTERS)}
                  className="mt-4"
                />
              )}
            </PopoverPrimitive.Content>
          </PopoverPrimitive.Portal>
        </PopoverPrimitive.Root>

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
    </>
  );
}
