import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AGENT_CONFIG } from "./agent-config";
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
  const config = AGENT_CONFIG[status.agentId];
  const task = taskText(status);
  const detailed = variant === "detailed";

  return (
    <Card
      className={`flex flex-col items-center gap-2 border-border bg-card text-center ${
        detailed ? "w-64 p-6" : "w-44 p-4"
      }`}
    >
      <img
        src={config.illustration}
        alt={config.name}
        className={`w-auto object-contain ${detailed ? "h-48" : "h-32"}`}
      />
      <p className="font-display text-sm font-medium text-foreground">{config.name}</p>

      {status.state === "working" && (
        <Badge className="bg-success text-background">Working</Badge>
      )}
      {status.state === "idle" && <Badge variant="outline">Idle</Badge>}

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
