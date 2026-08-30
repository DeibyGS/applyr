import { useEffect, useRef } from "react";
import { Badge } from "@/components/ui/badge";
import { useApplyrEvents } from "@/hooks/useApplyrEvents";
import { AGENT_CONFIG } from "./agent-config";
import type { AgentId, ApplyrEvent } from "@/lib/applyr-events";

const USER_BADGE = "You" as const;

function agentName(agentId: AgentId): string {
  return AGENT_CONFIG[agentId]?.name ?? agentId;
}

function formatTime(timestamp: string): string {
  try {
    return new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return timestamp;
  }
}

function eventLabel(event: ApplyrEvent): string {
  switch (event.type) {
    case "agent.started":
      return event.payload.task;
    case "agent.command":
      return `${event.payload.command} ${event.payload.args.join(" ")}`.trim();
    case "agent.output":
      return event.payload.stdout.slice(0, 120) + (event.payload.stdout.length > 120 ? "..." : "");
    case "agent.completed":
      return event.payload.output_summary;
    case "agent.failed":
      return `Error: ${event.payload.error}`;
    case "agent.waiting":
      return event.payload.reason;
    case "agent.blocked":
      return event.payload.reason;
    case "agent.receiving":
      return `Receiving from ${agentName(event.payload.from_agent)}`;
    case "handoff.started":
      return `Sending to ${agentName(event.payload.to_agent)}`;
    case "handoff.completed":
      return `Received from ${agentName(event.payload.from_agent)}`;
    case "user.response":
      return event.payload.message;
    default:
      return event.type;
  }
}

function eventBadgeLabel(event: ApplyrEvent): string {
  switch (event.type) {
    case "agent.started":
      return "started";
    case "agent.command":
      return "cmd";
    case "agent.output":
      return "output";
    case "agent.completed":
      return "done";
    case "agent.failed":
      return "error";
    case "agent.waiting":
      return "waiting";
    case "agent.blocked":
      return "blocked";
    case "agent.receiving":
      return "recv";
    case "handoff.started":
      return "→ handoff";
    case "handoff.completed":
      return "✓ handoff";
    case "user.response":
      return USER_BADGE;
    default:
      return event.type.replace("agent.", "").replace("handoff.", "handoff:");
  }
}

function eventBadgeVariant(event: ApplyrEvent): "default" | "outline" | "secondary" | "destructive" {
  switch (event.type) {
    case "agent.failed":
      return "destructive";
    case "agent.waiting":
    case "agent.blocked":
      return "outline";
    case "user.response":
      return "secondary";
    case "agent.completed":
    case "handoff.completed":
      return "default";
    default:
      return "secondary";
  }
}

type AgentLiveTranscriptProps = {
  agentId: AgentId;
};

export function AgentLiveTranscript({ agentId }: AgentLiveTranscriptProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const { getAgentEvents } = useApplyrEvents({ agentIds: [agentId] });
  const events = getAgentEvents(agentId);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events.length]);

  if (events.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4 text-center">
        No activity yet — waiting for agent events...
      </p>
    );
  }

  return (
    <div
      ref={scrollRef}
      className="flex flex-col gap-1 max-h-64 overflow-y-auto rounded-lg border border-border bg-background/50 p-3"
    >
      {events.map((event, i) => (
        <div key={`${event.correlation_id}-${event.timestamp}-${i}`} className="flex items-start gap-2 text-xs">
          <span className="shrink-0 text-muted-foreground font-mono mt-0.5">
            {formatTime(event.timestamp)}
          </span>
          <Badge variant={eventBadgeVariant(event)} className="shrink-0 text-[10px] px-1.5 py-0">
            {eventBadgeLabel(event)}
          </Badge>
          <span className="text-foreground break-words">{eventLabel(event)}</span>
        </div>
      ))}
    </div>
  );
}
