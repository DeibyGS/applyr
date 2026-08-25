import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { EventBus } from "./event-bus";
import type { ApplyrEvent, AgentId } from "./types";
import { ARTIFACT_ICONS } from "./types";

interface TerminalPanelProps {
  eventBus: EventBus;
  className?: string;
}

type LogLevel = "all" | "agent" | "handoff" | "pipeline" | "errors";

const LOG_LEVELS: { id: LogLevel; label: string; icon: string }[] = [
  { id: "all", label: "All", icon: "📋" },
  { id: "agent", label: "Agent", icon: "🤖" },
  { id: "handoff", label: "Handoff", icon: "🤝" },
  { id: "pipeline", label: "Pipeline", icon: "📦" },
  { id: "errors", label: "Errors", icon: "❌" },
];

/**
 * TerminalPanel — terminal-style event log display.
 * 
 * Features:
 * - Real-time event streaming from shared EventBus
 * - Filter by event type (agent/handoff/pipeline/errors)
 * - Search/filter by text
 * - Agent color coding
 * - Pause/resume streaming
 * - Clear log
 * - Auto-scroll toggle
 * - Copy event to clipboard
 * - Monospace font, terminal aesthetic
 */
export function TerminalPanel({ eventBus, className = "" }: TerminalPanelProps) {
  const [events, setEvents] = useState<ApplyrEvent[]>([]);
  const [filterLevel, setFilterLevel] = useState<LogLevel>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [isPaused, setIsPaused] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [maxEvents, setMaxEvents] = useState(200);
  
  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Subscribe to EventBus
  useEffect(() => {
    const subId = eventBus.subscribe((event) => {
      if (isPaused) return;
      setEvents((prev) => {
        const next = [event, ...prev].slice(0, maxEvents);
        return next;
      });
    });
    return () => {
      eventBus.unsubscribe(subId);
    };
  }, [eventBus, isPaused, maxEvents]);

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [events, autoScroll]);

  // Filter events
  const filteredEvents = useMemo(() => {
    return events.filter((event) => {
      // Level filter
      if (filterLevel !== "all") {
        if (filterLevel === "agent" && !event.type.startsWith("agent.")) return false;
        if (filterLevel === "handoff" && !event.type.startsWith("handoff.")) return false;
        if (filterLevel === "pipeline" && event.type !== "pipeline.stage") return false;
        if (filterLevel === "errors" && !event.type.endsWith(".failed") && event.type !== "agent.failed") return false;
      }
      
      // Search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const searchable = [
          event.type,
          event.agent_id,
          event.correlation_id,
          JSON.stringify(event.payload || {}),
        ].join(" ").toLowerCase();
        if (!searchable.includes(query)) return false;
      }
      
      return true;
    });
  }, [events, filterLevel, searchQuery]);

  // Format timestamp
  const formatTime = (iso: string): string => {
    try {
      const date = new Date(iso);
      const timeStr = date.toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
      const ms = date.getMilliseconds().toString().padStart(3, "0");
      return `${timeStr}.${ms}`;
    } catch {
      return iso;
    }
  };

  // Get agent color
  const getAgentColor = (agentId: AgentId): string => {
    const colors: Record<AgentId, string> = {
      recruiter: "#3fa98b",
      matching: "#2dd4bf",
      cv: "#3987e5",
      ats: "#c98500",
      application: "#008300",
    };
    return colors[agentId] || "#9ca3af";
  };

  // Get event type color
  const getEventTypeColor = (type: string): string => {
    if (type.startsWith("handoff.")) return "#cb6e45";
    if (type.startsWith("agent.")) {
      if (type.endsWith(".failed")) return "#c96b52";
      if (type.endsWith(".completed")) return "#4fa98a";
      if (type.endsWith(".started")) return "#3fa98b";
      return "#2dd4bf";
    }
    if (type === "pipeline.stage") return "#6366f1";
    return "#9ca3af";
  };

  // Format payload for display
  const formatPayload = (payload: any): string => {
    if (!payload) return "";
    if (typeof payload === "string") return payload;
    try {
      return JSON.stringify(payload, null, 2);
    } catch {
      return String(payload);
    }
  };

  // Copy event to clipboard
  const copyEvent = (event: ApplyrEvent) => {
    navigator.clipboard.writeText(JSON.stringify(event, null, 2));
  };

  // Clear log
  const handleClear = () => {
    setEvents([]);
  };

  return (
    <div className={`flex flex-col h-full bg-[#0d1117] border-l border-border ${className}`}>
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 p-3 border-b border-border bg-[#161b22]">
        {/* Filter tabs */}
        <div className="flex items-center gap-1" role="tablist">
          {LOG_LEVELS.map((level) => (
            <button
              key={level.id}
              onClick={() => setFilterLevel(level.id)}
              className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                filterLevel === level.id
                  ? "bg-primary/20 text-primary border border-primary/30"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/30"
              }`}
              role="tab"
              aria-selected={filterLevel === level.id}
            >
              <span className="flex items-center gap-1">
                <span aria-hidden="true">{level.icon}</span>
                {level.label}
              </span>
            </button>
          ))}
        </div>

        <div className="flex-1" />

        {/* Search */}
        <div className="relative flex items-center gap-2">
          <input
            ref={searchInputRef}
            type="text"
            placeholder="Search events..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-48 px-2.5 py-1.5 text-xs bg-[#0d1117] border border-border rounded text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            aria-label="Search events"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="p-1 text-muted-foreground hover:text-foreground"
              aria-label="Clear search"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="w-4 h-4 accent-primary"
            />
            Auto-scroll
          </label>
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
            <input
              type="checkbox"
              checked={isPaused}
              onChange={(e) => setIsPaused(e.target.checked)}
              className="w-4 h-4 accent-primary"
            />
            Pause
          </label>
          <button
            onClick={handleClear}
            className="px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/30 rounded transition-colors"
            aria-label="Clear log"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Event Log */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto p-3 space-y-1 font-mono text-[11px] text-[#e6edf3]"
        role="log"
        aria-live="polite"
        aria-label="Event log"
      >
        {filteredEvents.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground/50 text-sm">
            {isPaused ? "Paused — uncheck to resume" : "No events yet"}
          </div>
        ) : (
          filteredEvents.map((event, idx) => (
            <EventRow
              key={`${event.correlation_id}-${event.timestamp}-${idx}`}
              event={event}
              index={idx}
              formatTime={formatTime}
              getAgentColor={getAgentColor}
              getEventTypeColor={getEventTypeColor}
              formatPayload={formatPayload}
              onCopy={() => copyEvent(event)}
            />
          ))
        )}
      </div>

      {/* Status Bar */}
      <div className="flex items-center justify-between px-3 py-2 border-t border-border bg-[#161b22] text-[10px] text-muted-foreground">
        <span>{filteredEvents.length} / {events.length} events</span>
        <span>{isPaused ? "⏸ Paused" : "▶ Live"}</span>
      </div>
    </div>
  );
}

interface EventRowProps {
  event: ApplyrEvent;
  index: number;
  formatTime: (iso: string) => string;
  getAgentColor: (agentId: AgentId) => string;
  getEventTypeColor: (type: string) => string;
  formatPayload: (payload: any) => string;
  onCopy: () => void;
}

function EventRow({
  event,
  formatTime,
  getAgentColor,
  getEventTypeColor,
  formatPayload,
  onCopy,
}: EventRowProps) {
  const isExpanded = false; // Could add click to expand

  return (
    <div
      className="group border-b border-border/30 last:border-0"
      onClick={onCopy}
      title="Click to copy JSON"
    >
      <div className="flex items-start gap-2 px-2 py-1.5">
        {/* Timestamp */}
        <span className="text-[#8b949e] shrink-0 w-24 font-mono">
          {formatTime(event.timestamp)}
        </span>

        {/* Agent ID with color */}
        <span
          className="shrink-0 font-medium px-1.5 py-0.5 rounded text-[10px]"
          style={{ color: getAgentColor(event.agent_id), backgroundColor: `${getAgentColor(event.agent_id)}20` }}
        >
          {event.agent_id}
        </span>

        {/* Event type with color */}
        <span
          className="shrink-0 font-medium px-1.5 py-0.5 rounded text-[10px]"
          style={{ color: getEventTypeColor(event.type), backgroundColor: `${getEventTypeColor(event.type)}20` }}
        >
          {event.type}
        </span>

        {/* Correlation ID (short) */}
        <span className="text-[#8b949e] shrink-0 w-20 font-mono truncate">
          {event.correlation_id.slice(0, 8)}
        </span>

        {/* Offer ID */}
        {event.offer_id !== undefined && (
          <span className="text-[#8b949e] shrink-0">
            #{event.offer_id}
          </span>
        )}

        {/* Payload summary */}
        <span className="flex-1 min-w-0 text-[#c9d1d9] truncate">
          {formatPayload(event.payload).slice(0, 100)}
        </span>

        {/* Copy hint */}
        <span className="text-[#484f58] shrink-0">
          ↬
        </span>
      </div>

      {/* Expanded payload (on hover) */}
      {event.payload && (
        <div className="pl-8 pr-2 pb-2 text-[10px] text-[#8b949e] bg-[#161b22]/50 rounded-bl rounded-br opacity-0 group-hover:opacity-100 transition-opacity duration-100">
          <pre>{formatPayload(event.payload)}</pre>
        </div>
      )}
    </div>
  );
}