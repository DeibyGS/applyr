import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Generic filter-bar primitives — built for OffersToolbar but deliberately
 * content-agnostic so Interviews/Archive/Analytics can reuse them instead of
 * each page growing its own ad hoc pile of Buttons.
 */

function FilterGroup({
  label,
  children,
  className,
}: {
  label: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {label}
      </span>
      <div className="flex flex-wrap items-center gap-1.5">{children}</div>
    </div>
  )
}

function FilterPill({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "h-7 shrink-0 rounded-full border px-3 text-xs font-medium whitespace-nowrap transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
        active
          ? "border-transparent bg-primary text-primary-foreground"
          : "border-border bg-transparent text-muted-foreground hover:border-primary/40 hover:text-foreground"
      )}
    >
      {children}
    </button>
  )
}

type SegmentedOption<T extends string> = {
  value: T
  label: string
  icon?: React.ReactNode
}

function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  "aria-label": ariaLabel,
}: {
  options: SegmentedOption<T>[]
  value: T
  onChange: (value: T) => void
  "aria-label": string
}) {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className="flex w-fit flex-wrap items-center gap-0.5 rounded-lg border border-border bg-background p-0.5"
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={cn(
            "inline-flex h-7 items-center gap-1.5 rounded-[calc(var(--radius-lg)-2px)] px-2.5 text-xs font-medium transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
            value === option.value
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {option.icon}
          {option.label}
        </button>
      ))}
    </div>
  )
}

function ActiveFilterChips({
  chips,
  onClearAll,
}: {
  chips: { key: string; label: string; onRemove: () => void }[]
  onClearAll: () => void
}) {
  if (chips.length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-1.5 border-t border-border pt-3">
      {chips.map((chip) => (
        <button
          key={chip.key}
          type="button"
          onClick={chip.onRemove}
          className="inline-flex h-6 items-center gap-1 rounded-full bg-primary/15 px-2.5 text-xs font-medium text-primary transition-colors hover:bg-primary/25"
        >
          {chip.label}
          <span aria-hidden className="text-primary/70">
            ×
          </span>
        </button>
      ))}
      <button
        type="button"
        onClick={onClearAll}
        className="text-xs font-medium text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
      >
        Clear all
      </button>
    </div>
  )
}

export { FilterGroup, FilterPill, SegmentedControl, ActiveFilterChips }
