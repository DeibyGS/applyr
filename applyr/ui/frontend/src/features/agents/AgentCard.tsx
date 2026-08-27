import { useState } from "react";
import { Cloud } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AGENT_CONFIG } from "./agent-config";
import { AgentQueueModal } from "./AgentQueueModal";
import { BADGE_COPY } from "./badge-copy";
import type { AgentStatus } from "./types";

const PIPELINE_ZONE_LABELS: Record<"cv" | "ats" | "application", string> = {
  cv: "CV",
  ats: "ATS",
  application: "application",
};

function taskText(status: AgentStatus): string | null {
  if (status.agentId === "recruiter" && status.state === "working") {
    const n = status.pendingCount;
    return `${n} offer${n === 1 ? "" : "s"} waiting for analysis`;
  }
  if (status.agentId === "matching" && status.state === "working") {
    return `${status.company} — ${status.compatibilityPct}% match`;
  }
  if (
    (status.agentId === "cv" || status.agentId === "ats" || status.agentId === "application") &&
    status.state === "working"
  ) {
    const n = status.count;
    return `${n} offer${n === 1 ? "" : "s"} in ${PIPELINE_ZONE_LABELS[status.agentId]} stage`;
  }
  return null;
}

type AgentCardProps = {
  status: AgentStatus;
  variant?: "compact" | "detailed";
};

export function AgentCard({ status, variant = "compact" }: AgentCardProps) {
  const [queueOpen, setQueueOpen] = useState(false);
  const config = AGENT_CONFIG[status.agentId];
  const task = taskText(status);
  const detailed = variant === "detailed";
  const working = status.state === "working";
  const badgeText = working ? BADGE_COPY[status.agentId].working : BADGE_COPY[status.agentId].idle;

  return (
    <Card
      className={`relative flex flex-col items-center gap-2 border-border bg-card text-center ${
        detailed ? "w-64 p-6" : "w-44 p-4"
      } ${working ? "agent-card-glow" : ""}`}
    >
      {working && (
        <>
          <button
            type="button"
            aria-label={`${config.name} queue — ${status.items.length} item${status.items.length === 1 ? "" : "s"}`}
            onClick={() => setQueueOpen(true)}
            className="absolute top-2 right-2 animate-pulse rounded-full p-2 text-muted-foreground transition-all hover:scale-110 hover:animate-none hover:bg-muted hover:text-foreground"
          >
            <Cloud className="size-6" />
          </button>
          <AgentQueueModal
            agentId={status.agentId}
            agentName={config.name}
            items={status.items}
            open={queueOpen}
            onOpenChange={setQueueOpen}
          />
        </>
      )}

      <img
        src={config.illustration}
        alt={config.name}
        className={`w-auto object-contain ${detailed ? "h-48" : "h-32"}`}
      />
      <p className="font-display text-sm font-medium text-foreground">{config.name}</p>

      <Badge className={working ? "bg-success text-background" : ""} variant={working ? undefined : "outline"}>
        {badgeText}
      </Badge>

      {detailed ? (
        <>
          <p className="text-xs text-muted-foreground">{config.role}</p>
          {task && <p className="text-xs text-foreground">{task}</p>}
        </>
      ) : (
        <p className="min-h-8 text-xs text-muted-foreground">{task ?? config.role}</p>
      )}
    </Card>
  );
}
