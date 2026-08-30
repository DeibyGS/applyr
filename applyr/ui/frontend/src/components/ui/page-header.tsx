import type { ReactNode } from "react";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export type PageHeaderChipTone = "default" | "success" | "warning" | "danger";

export interface PageHeaderChip {
  label: string;
  value: string | number;
  tone?: PageHeaderChipTone;
  onClick?: () => void;
}

const TONE_TEXT_CLASS: Record<PageHeaderChipTone, string> = {
  default: "text-foreground",
  success: "text-emerald-600 dark:text-emerald-400",
  warning: "text-amber-600 dark:text-amber-400",
  danger: "text-destructive",
};

function ChipContent({ chip }: { chip: PageHeaderChip }) {
  return (
    <>
      <span className={cn("font-display text-base font-medium", TONE_TEXT_CLASS[chip.tone ?? "default"])}>
        {chip.value}
      </span>
      <span className="text-xs text-muted-foreground">{chip.label}</span>
    </>
  );
}

function PageHeaderChipItem({ chip }: { chip: PageHeaderChip }) {
  if (!chip.onClick) {
    return (
      <div className="flex items-baseline gap-1.5 rounded-md border border-border bg-card px-3 py-1.5">
        <ChipContent chip={chip} />
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={chip.onClick}
      className="group flex cursor-pointer items-baseline gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 transition-colors hover:bg-muted hover:text-foreground"
    >
      <ChipContent chip={chip} />
      <ChevronRight className="size-3.5 text-muted-foreground transition-transform group-hover:translate-x-0.5" aria-hidden />
    </button>
  );
}

export function PageHeader({
  title,
  description,
  chips,
}: {
  title: string;
  description: ReactNode;
  chips?: PageHeaderChip[];
}) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h1 className="font-display text-2xl font-medium text-foreground">{title}</h1>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      {chips && chips.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {chips.map((chip) => (
            <PageHeaderChipItem key={chip.label} chip={chip} />
          ))}
        </div>
      )}
    </header>
  );
}
