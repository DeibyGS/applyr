import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { OFFER_STATUSES, formatStatusLabel } from "./group-by-status";
import type { OfferFilters, SortDirection, SortField } from "./offer-filters";

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

function FilterPill({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <Button type="button" variant={active ? "default" : "outline"} size="sm" onClick={onClick}>
      {label}
    </Button>
  );
}

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

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Button type="button" variant={view === "list" ? "default" : "outline"} size="sm" onClick={() => onViewChange("list")}>
          List
        </Button>
        <Button type="button" variant={view === "kanban" ? "default" : "outline"} size="sm" onClick={() => onViewChange("kanban")}>
          Kanban
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-muted-foreground">Status</span>
        <FilterPill label="All" active={filters.status === null} onClick={() => onFiltersChange({ ...filters, status: null })} />
        {OFFER_STATUSES.map((status) => (
          <FilterPill
            key={status}
            label={formatStatusLabel(status)}
            active={filters.status === status}
            onClick={() =>
              onFiltersChange({ ...filters, status: filters.status === status ? null : status })
            }
          />
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-muted-foreground">Work mode</span>
        <FilterPill label="All" active={filters.workMode === null} onClick={() => onFiltersChange({ ...filters, workMode: null })} />
        {WORK_MODES.map((mode) => (
          <FilterPill
            key={mode}
            label={mode}
            active={filters.workMode === mode}
            onClick={() =>
              onFiltersChange({ ...filters, workMode: filters.workMode === mode ? null : mode })
            }
          />
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          Min score
          <Input
            type="number"
            min={0}
            max={100}
            value={filters.minScore || ""}
            onChange={(event) => onFiltersChange({ ...filters, minScore: Number(event.target.value) || 0 })}
            className="w-20"
          />
        </label>

        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground">Sort</span>
          <FilterPill
            label={`Date${sortField === "date" ? ` ${sortArrow}` : ""}`}
            active={sortField === "date"}
            onClick={() => onSortChange("date")}
          />
          <FilterPill
            label={`Score${sortField === "score" ? ` ${sortArrow}` : ""}`}
            active={sortField === "score"}
            onClick={() => onSortChange("score")}
          />
        </div>
      </div>
    </div>
  );
}
