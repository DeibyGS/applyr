import { PageHeader } from "@/components/ui/page-header";
import type { OfficeStats } from "./office-stats";

export function OfficeHeader({ stats }: { stats: OfficeStats }) {
  return (
    <PageHeader
      title="Office"
      description="Paste an offer and follow it through the pipeline."
      chips={[
        { label: "pending", value: stats.pendingCount },
        { label: "agents active", value: stats.activeAgentCount },
      ]}
    />
  );
}
