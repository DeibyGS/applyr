import { Lock } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AGENT_CONFIG } from "./agent-config";
import type { AgentStatus } from "./types";

function taskText(status: AgentStatus): string | null {
  if (status.agentId === "recruiter" && status.state === "working") {
    const n = status.pendingCount;
    return `${n} offer${n === 1 ? "" : "s"} waiting for analysis`;
  }
  if (status.agentId === "matching" && status.state === "working") {
    return `${status.company} — ${status.compatibilityPct}% match`;
  }
  return null;
}

type AgentCardProps = {
  status: AgentStatus;
  variant?: "compact" | "detailed";
};

export function AgentCard({ status, variant = "compact" }: AgentCardProps) {
  const config = AGENT_CONFIG[status.agentId];
  const notConnected = status.state === "not_connected";
  const task = taskText(status);
  const detailed = variant === "detailed";

  return (
    <Card
      className={`flex flex-col items-center gap-2 border-border bg-card text-center ${
        detailed ? "w-64 p-6" : "w-44 p-4"
      } ${notConnected ? "opacity-60" : ""}`}
    >
      <img
        src={config.illustration}
        alt={config.name}
        className={`w-auto object-contain ${detailed ? "h-48" : "h-32"} ${notConnected ? "grayscale" : ""}`}
      />
      <p className="font-display text-sm font-medium text-foreground">{config.name}</p>

      {status.state === "working" && (
        <Badge className="bg-success text-background">Working</Badge>
      )}
      {status.state === "idle" && <Badge variant="outline">Idle</Badge>}
      {notConnected && (
        <Badge variant="secondary" className="gap-1 text-muted-foreground">
          <Lock className="size-3" />
          Not connected yet
        </Badge>
      )}

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
