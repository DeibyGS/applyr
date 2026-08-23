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

export function AgentCard({ status }: { status: AgentStatus }) {
  const config = AGENT_CONFIG[status.agentId];
  const notConnected = status.state === "not_connected";
  const task = taskText(status);

  return (
    <Card
      className={`flex w-44 flex-col items-center gap-2 border-border bg-card p-4 text-center ${
        notConnected ? "opacity-60" : ""
      }`}
    >
      <img
        src={config.illustration}
        alt={config.name}
        className={`h-32 w-auto object-contain ${notConnected ? "grayscale" : ""}`}
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

      <p className="min-h-8 text-xs text-muted-foreground">{task ?? config.role}</p>
    </Card>
  );
}
