import type { LucideIcon } from "lucide-react";
import { Construction } from "lucide-react";

type ComingSoonProps = {
  title: string;
  message?: string;
  icon?: LucideIcon;
};

export function ComingSoon({ title, message, icon: Icon = Construction }: ComingSoonProps) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-border bg-card p-12 text-center">
      <Icon className="size-8 text-muted-foreground" />
      <h1 className="font-display text-xl font-medium text-foreground">{title}</h1>
      <p className="max-w-md text-sm text-muted-foreground">
        {message ?? "This view is coming in a future update."}
      </p>
    </div>
  );
}
